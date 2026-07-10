#!/usr/bin/env python3
# 인물 트래킹 분석 — 얼굴 검출(YuNet) + IoU 트랙 + 정체성 군집(SFace) → viewer/track_out/<id>/tracks.json + crops/
#   사용: track_analyze.py <id> <video_path>   (track-make.yml analyze 스텝 전용 · 이 스크립트 = 순수 CV — 캡션 LLM은 별도 스텝 track_caption.sh)
# 설계 불변(정본 = apps/track/00_지침):
#   - 검출 기반 트래킹 = 드리프트 0 — 매 검출이 위치를 재접지(프리미어 포인트 트래커의 누적 어긋남 대체가 이 앱의 존재 이유).
#   - 과분할 > 과병합: 동일인 카드 2장 = 무해(둘 다 선택하면 끝) / 남남 병합 = 엉뚱한 얼굴 모자이크 = 치명 → SIM_MERGE 보수.
#   - 좌표는 항상 원본 픽셀 공간(검출만 축소 프레임) · 분석/렌더 모두 cv2 디코드(회전 메타 처리 일관 = 좌표 어긋남 0).
#   - 원본 영상은 R2에 보관(track_src/<id>) → 렌더·재렌더가 재업로드 없이 소스 회수(분석 1회 = 렌더 N회).
# env: R2 5종(thumb_gen 재사용 · 없으면 작은 파일만 git 폴백) · TRACK_MAX_SEC(기본 300 · 260710 운영자 승인)
# 실패 = /tmp/track_err.txt(사용자 문구) + rc 1 → 워크플로 failure 스텝이 error.log로 커밋(뷰어 즉시 표시 · ly 패턴).
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".github", "scripts"))
import thumb_gen as tg   # r2_upload · R2_ON 재사용(모듈 import = main 미실행 · ly_burn 선례)

MODELS = os.environ.get("NOMUTE_TRACK_MODELS", os.path.expanduser("~/.cache/nomute-track"))
MAX_SEC = int(os.environ.get("TRACK_MAX_SEC", "300"))   # CPU 러너 보호 — 초과 = 명시 거절(조용한 부분처리 금지) · 180→300 = 운영자 승인 260710(분석 ~4.5분·렌더 ~9분 = 잡 40분 내 실측 외삽)
DET_LONG = 960          # 검출 입력 긴 변(원본이 더 작으면 원본 그대로) — 속도·소형 얼굴 균형
DET_PER_SEC = 12        # 초당 검출 횟수(사이 프레임은 렌더서 보간) — 전 프레임 검출 대비 ~3배 절약·마진이 커버
SCORE_TH = 0.65         # YuNet 신뢰 임계(기본 .9는 소형·측면 얼굴을 놓침 → 완화 + 트랙 최소 검출수로 오탐 상쇄)
NMS_TH = 0.3
IOU_MATCH = 0.25        # 검출 스텝 간격(~0.08s)에서 얼굴 이동은 작음 — 동일 트랙 판정 IoU
IOU_MISS_RAMP = 0.06    # 미스 1스텝당 매칭 임계 가산 — 가려진 트랙의 정지 박스 자리로 딴 사람이 지나가면
                        #   기본 0.25로 흡수(ID 스위치 → 트랙 임베딩 오염 = SIM_MERGE 남남병합 방어 우회) 차단(260710)
IOU_MISS_MAX = 0.50     # 미스 누적 임계 상한 — 과상향은 재획득 실패 = 트랙 분열만 늘림(과분할 무해라 상한으로 균형)
MISS_TTL_SEC = 0.7      # 이만큼 검출이 끊기면 트랙 종료(재등장은 새 트랙 → 군집이 같은 사람으로 재결합)
MIN_TRACK_DETS = 3      # 3회 미만 검출 트랙 = 오탐 취급(12/s = 검출 간격 0.083s × 2구간 ≈ 0.17s)
EMB_MIN_PX = 20         # 임베딩 절대 하한(원본 픽셀 얼굴 폭) — 이 밑은 임베딩 안 씀. ⚠ 구 42 단일 게이트는
                        #   소형 얼굴(원거리 인물)의 임베딩을 전면 차단 → 이탈·재진입 재군집이 조용히 실패
                        #   (2인 실측: 36px 얼굴 emb=None → 같은 사람이 pid 2개로 분열 · 260708)
EMB_HQ_PX = 42          # 고품질 기준(구 게이트 값) — 이 위는 표준 임계, 밑은 보수 임계(2단·아래)
EMB_TOP_N = 6           # 트랙당 임베딩 대표 크롭 수(고신뢰·대형 우선)
SIM_MERGE = 0.48        # SFace 코사인 동일인 병합 임계 · 고품질↔고품질(공식 동일인 0.363보다 보수 = 과분할 편향)
SIM_MERGE_LQ = 0.60     # 저품질(소형 얼굴) 개입 병합 임계 — 저해상 임베딩 과병합 꼬리위험(평의회3) 상쇄
                        #   {실측: 동일인 36px 0.876 vs 남남 −0.11 = 0.60도 여유 · 소형 재군집은 살리고 오병합은 조임}
MAX_PEOPLE = 12         # 카드 상한(등장시간 순) — 초과분은 meta.dropped로 정직 표기
GIT_FALLBACK_MAX = 30 * 1024 * 1024   # R2 미설정 시 원본 git 보관 상한(ly_burn 동일)

# ── 피사체(전신·사물) 검출 — 키잉(선택 피사체만 남김) 카드용 · YOLO11n cv2.dnn(추가 의존 0 · 53ms/f 실측 260709) ──
#   모델 = 레포 커밋본 apps/track/yolo11n.onnx(Ultralytics YOLO11n 변환 · AGPL-3.0 · 원본 https://github.com/ultralytics/assets)
#   없으면 fail-soft: subjects=[] + 경고(얼굴 파이프·모자이크·핀셋 무영향).
YOLO_ONNX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolo11n.onnx")
SUBJ_PER_SEC = 4        # 초당 검출 횟수 — 2→4(260710 전신 폴백): 폴백 커버가 이 kf를 보간하므로 0.5s→0.25s 간격 = 편차 절반 · 비용 = 5분 영상 YOLO 총 ~64s(1200검출×53ms 실측 · 2/s 대비 증분 +32s) · 키잉 마스크는 여전히 SAM2가 매 프레임
SUBJ_CONF = 0.40
SUBJ_NMS = 0.45
SUBJ_IOU_MATCH = 0.20   # 0.5s 간격 = 이동 큼 → 얼굴(0.25/0.083s)보다 완화
SUBJ_TTL_SEC = 1.6      # 저주기 샘플링 = 미검출 3샘플 관용
SUBJ_MIN_DETS = 3       # ≥약 1.5s 등장만 카드(스쳐가는 잡음 컷)
SUBJ_MIN_AREA = 0.004   # 중앙값 면적 프레임 대비 0.4% 미만 = 원경 잡음 컷
SUBJ_GOOD_AREA = 0.70   # 프롬프트 프레임 = 면적이 중앙값 70% 이상인 첫 검출(진입 슬리버 프롬프트 방지)
MAX_SUBJECTS = 12       # 카드 상한(people 캡과 동일 철학 · 초과 = meta.subj_dropped)
SUBJ_CLS = {0: "인물", 1: "자전거", 2: "차량", 3: "오토바이", 5: "버스", 7: "트럭",
            14: "새", 15: "고양이", 16: "개"}   # COCO 화이트리스트(뉴스 릴스 맥락) — 확장 = 여기 + 뷰어 무변경

# ── 전신 폴백·pid 봉합(운영자 260710 "종료지점까지 구분 가능하게") — people에 body/hr/pf/pb 추가(v3 additive) ──
PEOPLE_GOOD_AREA = 0.70   # 인물 키잉 프롬프트 pf 선정 — SUBJ_GOOD_AREA 미러(진입 슬리버 프롬프트 방지 동일 철학)
BODY_LINK_MIN_VOTES = 2   # 전신↔얼굴 링크 인정 최소 투표 수(기존 pid 확정 임계와 동일값)
BODY_LINK_MIN_VOTES_NOEMB = 4   # 양쪽 그룹 모두 임베딩 부재 시 병합 투표 하한 상향 — veto②가 원천 무력한 조합이라
                                #   공존 증거를 더 요구(컷 크로스 IoU 오연결 슬리버 배제 · 평의회2 ⑥ 보수화)
BODY_LINK_VETO_SIM = 0.05   # must-link 임베딩 강반대 veto — 실측 남남 −0.11~−0.15 · 동일인 소형 0.876 → 0.05는 넉넉한 분리대
BODY_LINK_OVL_TOL_SEC = 0.2   # 병합 후보 두 사람의 얼굴 세그 시간중첩 허용치(경계 지터만 허용 · 초과 = 동시존재 = 남남 확정)
HEAD_CAL_MIN = 3          # pid별 얼굴/전신 비율(hr) 캘리브레이션 최소 샘플 — 미달 = hr 생략(렌더가 고정 기본비)
R2_FILE_UPLOAD_MIN = 80 * 1024 * 1024   # 이 초과 원본 = bytes RAM 적재 대신 파일 직접 업로드(300s 상향 파급 — tg.r2_upload는 90s 캡·전량 RAM)


def die(user_msg, log_msg=""):
    with open("/tmp/track_err.txt", "w", encoding="utf-8") as f:
        f.write(user_msg)
    print("::error::" + (log_msg or user_msg))
    sys.exit(1)


def kst_now():
    from datetime import datetime, timedelta, timezone
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def load_models():
    ydp = os.path.join(MODELS, "yunet_2023mar.onnx")
    sfp = os.path.join(MODELS, "sface_2021dec.onnx")
    # setup.sh 미완(네트워크)이었으면 여기서 재시도 — 동일 다운로드 로직(멱등)
    if not (os.path.isfile(ydp) and os.path.getsize(ydp) > 150000 and os.path.isfile(sfp) and os.path.getsize(sfp) > 30000000):
        subprocess.run(["bash", os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup.sh")], check=False, timeout=900)
    if not (os.path.isfile(ydp) and os.path.getsize(ydp) > 150000):
        die("분석 모델 준비 실패(네트워크) — 잠시 후 다시 해줘.", "YuNet 모델 없음")
    det = cv2.FaceDetectorYN.create(ydp, "", (320, 320), SCORE_TH, NMS_TH, 5000)
    rec = None
    if os.path.isfile(sfp) and os.path.getsize(sfp) > 30000000:
        rec = cv2.FaceRecognizerSF.create(sfp, "")
    else:
        print("⚠ SFace 없음 — 군집 생략(트랙=인물 1:1 · 과분할만 늘 뿐 렌더는 정상)", flush=True)
    return det, rec


def iou(a, b):
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    ix = max(0, min(ax2, bx2) - max(a[0], b[0]))
    iy = max(0, min(ay2, by2) - max(a[1], b[1]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    return inter / float(a[2] * a[3] + b[2] * b[3] - inter)


def load_subj_net():
    """YOLO11n onnx(cv2.dnn) — 없거나 로드 실패 = None(fail-soft · 얼굴 파이프 무영향)."""
    if not (os.path.isfile(YOLO_ONNX) and os.path.getsize(YOLO_ONNX) > 5_000_000):
        print("::warning::yolo11n.onnx 없음 — subjects 생략(키잉 카드만 빔 · 얼굴 파이프 정상)", flush=True)
        return None
    try:
        return cv2.dnn.readNetFromONNX(YOLO_ONNX)
    except Exception as e:
        print(f"::warning::피사체 모델 로드 실패({type(e).__name__}) — subjects 생략(키잉 카드만 빔)", flush=True)
        return None


def yolo_detect(net, frame, imgsz=640, conf_th=SUBJ_CONF, nms_th=SUBJ_NMS):
    """YOLO11 onnx 디코드+NMS — ultralytics 출력과 대조 검증(bus.jpg 5박스 수px 일치 · 260709).
    반환 [(x, y, w, h, score, cls)] 원본 픽셀 공간."""
    H, W = frame.shape[:2]
    s = min(imgsz / W, imgsz / H)
    nw, nh = round(W * s), round(H * s)
    x0, y0 = int(round((imgsz - nw) / 2 - 0.1)), int(round((imgsz - nh) / 2 - 0.1))
    canvas = np.full((imgsz, imgsz, 3), 114, np.uint8)
    canvas[y0:y0 + nh, x0:x0 + nw] = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255.0, (imgsz, imgsz), swapRB=True))
    out = net.forward()[0].T          # (8400, 84) = cx cy w h + 80cls
    scores = out[:, 4:].max(1)
    keep = scores >= conf_th
    out, scores = out[keep], scores[keep]
    if not len(out):
        return []
    cls = out[:, 4:].argmax(1)
    wl = np.isin(cls, list(SUBJ_CLS))   # 화이트리스트 선필터 — 밖 클래스(tie 등)가 NMS에서 사람을 억제 후
    out, scores, cls = out[wl], scores[wl], cls[wl]   #   같이 소실되는 이중 손실 차단(평의회1 F1)
    if not len(out):
        return []
    bx = (out[:, 0] - out[:, 2] / 2 - x0) / s
    by = (out[:, 1] - out[:, 3] / 2 - y0) / s
    boxes = np.stack([bx, by, out[:, 2] / s, out[:, 3] / s], 1)
    # 클래스별 NMS — 사람↔차량 등 교차 클래스 상호 억제 방지(겹쳐 선 사람이 버스에 먹히는 케이스)
    idx = cv2.dnn.NMSBoxesBatched(boxes.tolist(), scores.tolist(), cls.astype(np.int32).tolist(), conf_th, nms_th)
    idx = np.array(idx).flatten() if len(idx) else []
    res = []
    for i in idx:
        x, y, w, h = boxes[i]
        x2, y2 = min(float(x + w), W), min(float(y + h), H)   # 표준 클램프 = 반대변 보존(구식은 음수 x에서
        x, y = max(0.0, float(x)), max(0.0, float(y))          #   우변이 검출 밖으로 확장 — 평의회1 F2)
        w, h = x2 - x, y2 - y
        if w >= 8 and h >= 8:
            res.append((x, y, w, h, float(scores[i]), int(cls[i])))
    return res


def r2_upload_file(path, key, ctype):
    """대용량 원본 파일 직접 업로드 — track_keying._r2_upload_file 미러(출처 정본 = 그쪽 주석 · 300s 상향으로
    URL 원본이 수백 MB 가능 → tg.r2_upload(bytes 전량 RAM + 90s 캡)는 타임아웃·RAM 스파이크 상시 유실).
    keying 모듈 import는 안 함(가벼워도 결합 = 미래 헤비 top-level import 한 줄에 분석이 죽는 경로) — 미러 유지."""
    if not tg.R2_ON:
        return ""
    env = dict(os.environ, AWS_ACCESS_KEY_ID=tg.R2_KEY, AWS_SECRET_ACCESS_KEY=tg.R2_SECRET,
               AWS_DEFAULT_REGION="auto")
    try:
        subprocess.run(["aws", "s3", "cp", path, f"s3://{tg.R2_BUCKET}/{key}",
                        "--endpoint-url", f"https://{tg.R2_ACCOUNT}.r2.cloudflarestorage.com",
                        "--content-type", ctype, "--only-show-errors"],
                       check=True, env=env, timeout=900)
        return f"{tg.R2_PUBLIC}/{key}"
    except Exception as e:
        print(f"::warning::R2 파일 업로드 실패({key}): {e}", flush=True)
        return ""


def _tracks_overlap_sec(ta, tb, fps):
    """두 얼굴 트랙 묶음의 시간중첩 총합(초) — 동시존재 = 두 사람이 같은 순간 각자 검출 = 남남 확정 증거."""
    tot = 0
    for x in ta:
        a0, a1 = x["kf"][0][0], x["kf"][-1][0]
        for y in tb:
            b0, b1 = y["kf"][0][0], y["kf"][-1][0]
            tot += max(0, min(a1, b1) - max(a0, b0))
    return tot / fps


def merge_people_by_body(people, s_tracks, fps, W=0, H=0):
    """pid 분열 봉합(260710) — 같은 *연속 전신 트랙*에 투표(≥BODY_LINK_MIN_VOTES)로 연결된 얼굴 트랙들의
    people을 must-link 병합. 측면·소형 얼굴로 임베딩이 SIM_MERGE 미달이어도 전신 IoU 트랙의 구조적 연속성이
    같은 사람 증거다. SIM_MERGE 임계 자체는 불변(과분할>과병합 기틀 유지) — 이 병합은 임계 완화가 아니라
    별도 고정밀 증거 축. 오병합 방어(평의회2 반영 260710):
      · 증거 자격 — 메인 카드 필터와 동일 기준(SUBJ_MIN_DETS + SUBJ_MIN_AREA): 원경 잡음 전신(느슨한 IoU로
        정체성 오염이 가장 심한 부류)은 병합 증거에서 배제. 처리 순서 = 긴 트랙(강한 증거) 우선 정렬 = 결정적.
      ① 동시존재 veto — 두 그룹 얼굴 세그 시간중첩 > BODY_LINK_OVL_TOL_SEC = 한 사람이 동시에 두 곳(불가능)
         = 전신 트랙이 교차 시 남남을 IoU로 잘못 이은 것 → 그 전신 트랙의 링크 증거 통째 폐기.
      ② 임베딩 강반대 veto — *멤버 쌍별* 검사(그룹 평균이 강반대를 희석하는 전이 공백 봉합): 두 그룹의 멤버
         emb 중 어느 쌍이라도 cos < BODY_LINK_VETO_SIM → 그 짝 거부(강반대는 전신 증거보다 우선).
      ③ 무임베딩 보수화 — 양쪽 그룹 모두 emb 부재(veto② 원천 무력)면 투표 하한을 BODY_LINK_MIN_VOTES_NOEMB로
         상향(컷 크로스 IoU 오연결 배제 강화).
    호출 = 임베딩 군집 직후 · dur 정렬/MAX_PEOPLE 캡 *전*(동일인 2카드가 캡을 이중 점유 못 하게)."""
    tid2p = {id(t): pi for pi, p in enumerate(people) for t in p["tracks"]}
    parent = list(range(len(people)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # 그룹 상태(루트 기준) — 병합 판정은 항상 현재 그룹 전체로(원본 쌍이 아니라)
    # embs = 멤버 people 임베딩 목록(쌍별 veto용) · emb_sum = 최종 대표(가중합)
    grp = {i: {"tracks": list(p["tracks"]),
               "embs": ([p["emb"]] if p["emb"] is not None else []),
               "emb_sum": (p["emb"] * p["n_emb"]) if p["emb"] is not None and p["n_emb"] else None,
               "n_emb": p["n_emb"], "hq": p["hq"]} for i, p in enumerate(people)}

    def gemb(g):
        if g["emb_sum"] is None:
            return None
        n = np.linalg.norm(g["emb_sum"])
        return g["emb_sum"] / n if n > 0 else None

    # 증거 자격 필터 + 강한 증거 우선 정렬(결정적 순서 — 검출 append 순서 의존 제거)
    evid = []
    for st in s_tracks:
        if st["cls"] != 0 or len(st["kf"]) < SUBJ_MIN_DETS:
            continue
        areas = sorted(k[3] * k[4] for k in st["kf"])
        if W and H and areas[len(areas) // 2] < SUBJ_MIN_AREA * W * H:
            continue   # 원경 잡음 배제(메인 카드 필터와 동일 기준 — 병합 증거만 더 일찍 적용)
        evid.append(st)
    evid.sort(key=lambda st: -(st["kf"][-1][0] - st["kf"][0][0]))

    merged_any = False
    for st in evid:
        root_votes = {}   # 원본 루트 → 그 루트에 속한 링크 얼굴의 최대 투표수(무임베딩 보수화 판정용)
        for tid, v in st["votes"].items():
            if v >= BODY_LINK_MIN_VOTES and tid in tid2p:
                r = find(tid2p[tid])
                root_votes[r] = max(root_votes.get(r, 0), v)
        roots = sorted(root_votes)
        if len(roots) < 2:
            continue
        # veto ① — 링크된 그룹들끼리 동시존재가 하나라도 있으면 이 전신 트랙 증거 통째 폐기
        corrupt = any(_tracks_overlap_sec(grp[a]["tracks"], grp[b]["tracks"], fps) > BODY_LINK_OVL_TOL_SEC
                      for x, a in enumerate(roots) for b in roots[x + 1:])
        if corrupt:
            if os.environ.get("TRACK_DEBUG"):
                print(f"DBG bodylink veto① f{st['kf'][0][0]}-{st['kf'][-1][0]} groups={roots} 동시존재 — 증거 폐기", flush=True)
            continue
        base = roots[0]
        for b in roots[1:]:
            ra, rb = find(base), find(b)
            if ra == rb:
                continue
            # veto ② — 멤버 쌍별 강반대 검사(그룹 평균 희석 방지)
            neg = any(float(np.dot(ea, eb)) < BODY_LINK_VETO_SIM
                      for ea in grp[ra]["embs"] for eb in grp[rb]["embs"])
            if neg:
                if os.environ.get("TRACK_DEBUG"):
                    print(f"DBG bodylink veto② {ra}+{rb} 멤버 쌍 강반대 — 짝 거부", flush=True)
                continue
            # ③ — 양쪽 다 emb 없으면 투표 하한 상향
            if not grp[ra]["embs"] and not grp[rb]["embs"] and \
                    min(root_votes.get(roots[0], 0), root_votes.get(b, 0)) < BODY_LINK_MIN_VOTES_NOEMB:
                if os.environ.get("TRACK_DEBUG"):
                    print(f"DBG bodylink veto③ {ra}+{rb} 무임베딩 투표 미달(<{BODY_LINK_MIN_VOTES_NOEMB}) — 짝 거부", flush=True)
                continue
            parent[rb] = ra
            ga, gb = grp[ra], grp.pop(rb)
            ga["tracks"].extend(gb["tracks"])
            ga["embs"].extend(gb["embs"])
            if ga["emb_sum"] is None:
                ga["emb_sum"], ga["n_emb"] = gb["emb_sum"], gb["n_emb"]
            elif gb["emb_sum"] is not None:
                ga["emb_sum"] = ga["emb_sum"] + gb["emb_sum"]
                ga["n_emb"] += gb["n_emb"]
            ga["hq"] = ga["hq"] or gb["hq"]
            merged_any = True
            if os.environ.get("TRACK_DEBUG"):
                print(f"DBG bodylink merge {ra}+{rb} via strack f{st['kf'][0][0]}-{st['kf'][-1][0]}", flush=True)
    if not merged_any:
        return people
    out = []
    for i in range(len(people)):
        if find(i) != i:
            continue
        g = grp[i]
        out.append({"tracks": g["tracks"], "emb": gemb(g), "n_emb": g["n_emb"], "hq": g["hq"]})
    return out


def main():
    if len(sys.argv) < 3:
        die("분석 실패 — 입력이 비었어. 다시 해줘.", "usage: track_analyze.py <id> <video>")
    vid_id, src = sys.argv[1], sys.argv[2]
    if not os.path.isfile(src):
        die("영상 파일을 못 받았어 — 다시 올려줘.", "src 없음: " + src)

    cap = cv2.VideoCapture(src)
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)   # 폰 세로영상 회전 메타 정립(분석·렌더 동일 설정 = 좌표 일관)
    except Exception:
        pass
    if not cap.isOpened():
        die("영상을 못 열었어 — 지원 안 되는 형식일 수 있어. mp4로 다시 해줘.", "VideoCapture 실패")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    if not fps or fps <= 1 or fps > 240 or math.isnan(fps):
        fps = 30.0
    raw_n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    nframes = int(raw_n) if (raw_n and not math.isnan(raw_n) and raw_n > 0) else 0   # NaN 메타 → int() ValueError 방지(평의회3)
    dur = nframes / fps if nframes > 0 else 0
    if dur > MAX_SEC + 2:
        die(f"영상이 너무 길어 — {MAX_SEC//60}분 이하만 돼(지금 {int(dur//60)}분 {int(dur%60)}초). 잘라서 올려줘.", f"길이 초과 {dur:.0f}s")

    det, rec = load_models()
    subj_net = load_subj_net()
    subj_state = "" if subj_net is not None else "no-model"   # ""(정상)/no-model/partial(중도 실패)
    step = max(1, round(fps / DET_PER_SEC))
    ystep = step * max(1, round(DET_PER_SEC / SUBJ_PER_SEC))   # 피사체 검출 = 검출 스텝의 부분집합(추가 디코드 0)

    tracks = []   # {kf:[[f,x,y,w,h,score]], last_f, cand:[(quality, aligned112, crop_bgr, score)], done}
    active = []
    s_tracks = []   # 피사체 트랙 {cls, kf:[[f,x,y,w,h,score]], last_f, votes:{id(얼굴트랙):n}, best_q, crop}
    s_active = []
    f = -1
    first_shape = None
    hard_cap = int((MAX_SEC + 2) * fps)   # 프레임 수 캡(1차) — fps 메타 거짓이면 아래 POS_MSEC(fps 비의존 실측)이 2차로 잡음(평의회3)
    while True:
        f += 1
        if f > hard_cap:
            die(f"영상이 너무 길어 — {MAX_SEC//60}분 이하만 돼. 잘라서 올려줘.", f"실측 길이 초과 f={f}")
        if f % 300 == 0 and f > 0:
            pos = cap.get(cv2.CAP_PROP_POS_MSEC) or 0
            if pos and not math.isnan(pos) and pos > (MAX_SEC + 2) * 1000:
                die(f"영상이 너무 길어 — {MAX_SEC//60}분 이하만 돼. 잘라서 올려줘.", f"실측 시각 초과 {pos/1000:.0f}s")
        # 검출 안 하는 프레임 = grab만(디코드 스킵 = 3~5배 빠름)
        if f % step != 0:
            if not cap.grab():
                break
            continue
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        if first_shape is None:
            first_shape = frame.shape
        H, W = frame.shape[:2]
        scale = min(1.0, DET_LONG / max(W, H))
        if scale < 1.0:
            small = cv2.resize(frame, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
        else:
            small = frame
        det.setInputSize((small.shape[1], small.shape[0]))
        _, faces = det.detect(small)
        dets = []
        if faces is not None:
            for row in faces:
                x, y, w, h = row[0] / scale, row[1] / scale, row[2] / scale, row[3] / scale
                if w < 12 or h < 12:
                    continue
                dets.append((max(0, x), max(0, y), w, h, float(row[-1]), row))
        # 그리디 IoU 매칭(점수 큰 검출부터) — 검출 기반이라 예측 모델 불요(스텝 간 이동 미소)
        dets.sort(key=lambda d: -d[4])
        used = set()
        frame_faces = []   # 이 프레임의 (얼굴박스, 얼굴트랙) 짝 — 피사체(전신)↔얼굴 연결 투표용
        for d in dets:
            best, bi = 0.0, -1
            for i, t in enumerate(active):
                if i in used:
                    continue
                v = iou(d[:4], t["kf"][-1][1:5])
                # 트랙별 임계 = 기본 + 미스 스텝 비례 상향(직전 스텝 검출 = 기본) — 정지 박스에 오래 매달린
                #   트랙일수록 그 자리의 새 얼굴을 흡수하기 어렵게(ID 스위치·임베딩 오염 차단 · 260710)
                miss = max(0, (f - t["last_f"]) // step - 1)
                if v >= min(IOU_MISS_MAX, IOU_MATCH + IOU_MISS_RAMP * miss) and v > best:
                    best, bi = v, i
            box = [f, int(d[0]), int(d[1]), int(d[2]), int(d[3]), d[4]]
            if bi >= 0:
                t = active[bi]
                used.add(bi)
                t["kf"].append(box)
                t["last_f"] = f
            else:
                t = {"kf": [box], "last_f": f, "cand": []}
                tracks.append(t)
                active.append(t)
                used.add(len(active) - 1)
                bi = len(active) - 1
                best = 1.0
            if bi < len(active):
                frame_faces.append((d[:4], active[bi]))
            # 임베딩·크롭 후보(고신뢰·대형 우선 top-N) — 정렬크롭은 검출 프레임에서 즉시(프레임 버퍼 재방문 불가)
            t = active[bi] if bi < len(active) else None
            if t is not None and d[3] >= 12:
                q = d[4] * math.sqrt(max(1.0, d[2]))
                if len(t["cand"]) < EMB_TOP_N or q > t["cand"][-1][0]:
                    aligned = None
                    if rec is not None and d[2] >= EMB_MIN_PX:
                        try:
                            # 정렬크롭은 원본 프레임 + 좌표 업스케일 — 축소 프레임(small) 정렬은 고해상 소스에서
                            #   저질 임베딩(≈업스케일 112px) → 과병합 꼬리위험까지(평의회3 ①). 좌표·이미지는 반드시 짝.
                            row = d[5].astype(np.float32).copy()
                            if scale < 1.0:
                                row[:14] = row[:14] / scale
                            aligned = rec.alignCrop(frame, row)
                        except Exception:
                            aligned = None
                    # 대표 크롭(카드용) = 원본 프레임에서 40% 여유 · 즉시 256px 축소(풀해상 보관 = 순수 낭비
                    #   → 다인원·4K서 메모리 폭주 — 평의회3 ② · 출력은 어차피 256px 저장)
                    mx, my = d[2] * 0.4, d[3] * 0.5
                    x0, y0 = int(max(0, d[0] - mx)), int(max(0, d[1] - my))
                    x1, y1 = int(min(W, d[0] + d[2] + mx)), int(min(H, d[1] + d[3] + my))
                    crop = None
                    if x1 - x0 > 8 and y1 - y0 > 8:
                        crop = frame[y0:y1, x0:x1]
                        s2 = 256.0 / max(crop.shape[0], crop.shape[1])
                        crop = cv2.resize(crop, (max(1, int(crop.shape[1] * s2)), max(1, int(crop.shape[0] * s2))),
                                          interpolation=cv2.INTER_AREA) if s2 < 1.0 else crop.copy()
                    t["cand"].append((q, aligned, crop, d[2]))   # [3] = 검출 폭(임베딩 품질 판정용)
                    t["cand"].sort(key=lambda c: -c[0])
                    del t["cand"][EMB_TOP_N:]
        # ── 피사체(전신·사물) 검출 — 같은 디코드 프레임 재사용(추가 디코드 0 · 키잉 카드·프롬프트용) ──
        if subj_net is not None and f % ystep == 0:
            try:
                sdets = yolo_detect(subj_net, frame)
            except Exception as e:   # 피사체 검출 실패가 얼굴 분석을 죽이면 안 됨(fail-soft)
                print(f"::warning::피사체 검출 오류 f={f}: {type(e).__name__} — 이후 생략", flush=True)
                subj_net, sdets = None, []
                subj_state = "partial"   # 중도 실패 = 부분 산출(no-model 오표기 방지 · 평의회1 F3)
            sdets.sort(key=lambda d: -d[4])
            s_used = set()
            for sx, sy, sw, sh, ssc, scls in sdets:
                best, sbi = 0.0, -1
                for i, st in enumerate(s_active):
                    if i in s_used or st["cls"] != scls:
                        continue
                    v = iou((sx, sy, sw, sh), st["kf"][-1][1:5])
                    if v > best:
                        best, sbi = v, i
                box = [f, int(sx), int(sy), int(sw), int(sh), ssc]
                if best >= SUBJ_IOU_MATCH and sbi >= 0:
                    st = s_active[sbi]
                    s_used.add(sbi)
                    st["kf"].append(box)
                    st["last_f"] = f
                else:
                    st = {"cls": scls, "kf": [box], "last_f": f, "votes": {}, "cal": {}, "best_q": -1.0, "crop": None}
                    s_tracks.append(st)
                    s_active.append(st)
                    s_used.add(len(s_active) - 1)
                # 얼굴 연결 투표 — 얼굴박스 중심이 전신박스 상단 55% 안 + 폭이 전신의 60% 미만
                #   키 = id(얼굴트랙): 트랙 dict가 tracks 리스트에 참조 유지 = 함수 수명 내 id 안정(불변식 —
                #   트랙을 재생성하는 리팩터 시 이 키부터 깨짐 · 평의회1 F5)
                if scls == 0:
                    for fb, ft in frame_faces:
                        fcx, fcy = fb[0] + fb[2] / 2, fb[1] + fb[3] / 2
                        if sx <= fcx <= sx + sw and sy <= fcy <= sy + sh * 0.55 and fb[2] < sw * 0.6:
                            st["votes"][id(ft)] = st["votes"].get(id(ft), 0) + 1
                            # 얼굴/전신 비율 캘리브레이션(hr) 샘플 — 투표 프레임 = 얼굴·전신 동시 검출(ystep이
                            #   step 배수 = 같은 디코드 프레임)이라 좌표 짝 정확. (rw, rh, rcx, rcy) = 폭비·높이비·
                            #   중심x오프셋비·머리y위치비 → 렌더 head_from_body가 소비(전신 폴백 · 260710)
                            st["cal"].setdefault(id(ft), []).append(
                                (fb[2] / sw, fb[3] / sh, (fcx - (sx + sw / 2)) / sw, (fcy - sy) / sh))
                # 대표 크롭(카드용 · 256px 즉시 축소 = people cand와 동일 메모리 원칙)
                q = ssc * math.sqrt(max(1.0, sw * sh))
                if q > st["best_q"]:
                    x0c, y0c = int(max(0, sx)), int(max(0, sy))
                    x1c, y1c = int(min(W, sx + sw)), int(min(H, sy + sh))
                    if x1c - x0c > 8 and y1c - y0c > 8:
                        crop = frame[y0c:y1c, x0c:x1c]
                        s2 = 256.0 / max(crop.shape[0], crop.shape[1])
                        st["crop"] = cv2.resize(crop, (max(1, int(crop.shape[1] * s2)), max(1, int(crop.shape[0] * s2))),
                                                interpolation=cv2.INTER_AREA) if s2 < 1.0 else crop.copy()
                        st["best_q"] = q
            s_ttl = SUBJ_TTL_SEC * fps
            s_active = [st for st in s_active if f - st["last_f"] <= s_ttl]
        # 미스 트랙 정리
        ttl = MISS_TTL_SEC * fps
        active = [t for t in active if f - t["last_f"] <= ttl]

    total_frames = f
    cap.release()
    if first_shape is None:
        die("영상에서 프레임을 못 읽었어 — 다른 파일로 해줘.", "프레임 0")
    H, W = first_shape[:2]
    real_dur = total_frames / fps

    tracks = [t for t in tracks if len(t["kf"]) >= MIN_TRACK_DETS]

    # 트랙 대표 임베딩 → 정체성 군집(그리디 · 과분할 편향 · 2단 임계)
    for t in tracks:
        embs, widths = [], []
        if rec is not None:
            for q, aligned, crop, dw in t["cand"]:
                if aligned is None:
                    continue
                try:
                    e = rec.feature(aligned).flatten().astype(np.float32)
                    n = np.linalg.norm(e)
                    if n > 0:
                        embs.append(e / n)
                        widths.append(dw)
                except Exception:
                    pass
        t["emb"] = np.mean(embs, axis=0) if embs else None
        t["hq"] = bool(widths) and (sorted(widths)[len(widths) // 2] >= EMB_HQ_PX)   # 중앙값 폭 기준 고품질 판정
        if t["emb"] is not None:
            n = np.linalg.norm(t["emb"])
            t["emb"] = t["emb"] / n if n > 0 else None
        t["dur"] = (t["kf"][-1][0] - t["kf"][0][0]) / fps
    tracks.sort(key=lambda t: -t["dur"])
    if os.environ.get("TRACK_DEBUG"):   # 현장 진단(재군집 튜닝) — 라이브 무영향(env 미설정 = 침묵)
        for i, t in enumerate(tracks):
            print(f"DBG track{i} f{t['kf'][0][0]}-{t['kf'][-1][0]} dur{t['dur']:.2f} emb={'None' if t['emb'] is None else 'ok'} cand={len(t['cand'])}", flush=True)
        for i in range(len(tracks)):
            for j in range(i + 1, len(tracks)):
                if tracks[i]["emb"] is not None and tracks[j]["emb"] is not None:
                    print(f"DBG sim {i}-{j} = {float(np.dot(tracks[i]['emb'], tracks[j]['emb'])):.3f}", flush=True)

    people = []   # {tracks:[], emb(이동평균), n_emb, hq}
    for t in tracks:
        best, bi = 0.0, -1
        if t["emb"] is not None:
            for i, p in enumerate(people):
                if p["emb"] is None:
                    continue
                v = float(np.dot(t["emb"], p["emb"]))
                # 2단 임계 — 양쪽 다 고품질 = 표준(0.48) / 한쪽이라도 소형 얼굴 = 보수(0.60 · 과병합 꼬리 차단)
                th = SIM_MERGE if (t["hq"] and p["hq"]) else SIM_MERGE_LQ
                if v >= th and v > best:
                    best, bi = v, i
            # 동시존재 veto — 코사인 *최고* 후보가 물리적 공존(같은 순간 각자 검출 = 남남 확정)이면 병합
            #   *포기*(새 person). 후보 루프 안 continue로 차선에 폴스루시키면 닮은 남남 오귀속(분열보다
            #   나쁜 유일한 방향) 경로가 생김 — 과분할=무해 철학상 포기가 정본(평의회2 · body-link veto①
            #   동일 지표·톨러런스 = 이 분열은 body-link로도 재봉합 안 됨이 설계 의도 · 260710)
            if bi >= 0 and _tracks_overlap_sec([t], people[bi]["tracks"], fps) > BODY_LINK_OVL_TOL_SEC:
                best, bi = 0.0, -1
        if bi >= 0:
            p = people[bi]
            p["tracks"].append(t)
            k = p["n_emb"]
            p["emb"] = (p["emb"] * k + t["emb"]) / (k + 1)
            n = np.linalg.norm(p["emb"])
            p["emb"] = p["emb"] / n if n > 0 else p["emb"]
            p["n_emb"] = k + 1
            p["hq"] = p["hq"] or t["hq"]
        else:
            people.append({"tracks": [t], "emb": t["emb"], "n_emb": 1 if t["emb"] is not None else 0, "hq": t["hq"]})

    # pid 분열 봉합 — 전신 트랙 must-link 병합(캡 *전* = 동일인 2카드의 캡 이중 점유 방지 · 260710)
    people = merge_people_by_body(people, s_tracks, fps, W=W, H=H)

    for p in people:
        p["dur"] = sum(t["dur"] for t in p["tracks"])
        p["first"] = min(t["kf"][0][0] for t in p["tracks"]) / fps
        p["last"] = max(t["kf"][-1][0] for t in p["tracks"]) / fps
        p["n"] = sum(len(t["kf"]) for t in p["tracks"])
    people.sort(key=lambda p: -p["dur"])
    dropped = max(0, len(people) - MAX_PEOPLE)
    people = people[:MAX_PEOPLE]

    outdir = os.path.join("viewer", "track_out", vid_id)
    os.makedirs(os.path.join(outdir, "crops"), exist_ok=True)

    face_pid = {}      # id(얼굴트랙) → pid(캡 반영 후) — 피사체 연결 투표 해석·body/hr 귀속용
    for idx, p in enumerate(people, start=1):
        for t in p["tracks"]:
            face_pid[id(t)] = idx

    # 피사체 트랙 필터·pid 확정 — people 조립 *앞*으로 이동(260710): people[].body가 pid 확정분을 소비
    s_tracks = [st for st in s_tracks if len(st["kf"]) >= SUBJ_MIN_DETS]
    for st in s_tracks:
        areas = sorted(k[3] * k[4] for k in st["kf"])
        st["med_area"] = areas[len(areas) // 2]
    s_tracks = [st for st in s_tracks if st["med_area"] >= SUBJ_MIN_AREA * W * H]
    for st in s_tracks:   # 얼굴 연결 확정 — 투표 2표 이상 최다 pid
        best_p, best_v = 0, 0
        for tid, v in st["votes"].items():
            pidv = face_pid.get(tid, 0)
            if pidv and v > best_v:
                best_p, best_v = pidv, v
        st["pid"] = best_p if best_v >= 2 else 0
    body_by_pid = {}   # pid → 그 사람으로 확정된 전신 트랙들 — people[].body(폴백)·hr(비율) 원천.
    for st in s_tracks:   #   subjects 캡(MAX_SUBJECTS) *적용 전* s_tracks에서 직접 구축 = 캡과 디커플(전신이 카드에서 잘려도 폴백 생존)
        if st["cls"] == 0 and st["pid"]:
            body_by_pid.setdefault(st["pid"], []).append(st)

    # 대표 크롭 저장(카드) — 사람별 최고 품질 크롭 + v3 additive 4키(body·hr·pf·pb = 전신 폴백·키잉 얼굴 단위)
    out_people = []
    crop_by_pid = {}   # pid → 크롭 상대경로 — 얼굴 연결 피사체 카드가 얼굴 크롭 재사용
    for idx, p in enumerate(people, start=1):
        best_crop, best_q = None, -1.0
        for t in p["tracks"]:
            for q, aligned, crop, sc in t["cand"]:
                if crop is not None and q > best_q:
                    best_q, best_crop = q, crop
        crop_rel = ""
        if best_crop is not None:   # 캡처 시점에 이미 ≤256px(위 축소) — 그대로 저장
            crop_rel = f"crops/p{idx}.jpg"
            cv2.imwrite(os.path.join(outdir, crop_rel), best_crop, [cv2.IMWRITE_JPEG_QUALITY, 82])
            crop_by_pid[idx] = crop_rel
        segs = []
        for t in sorted(p["tracks"], key=lambda t: t["kf"][0][0]):
            segs.append({"f0": t["kf"][0][0], "f1": t["kf"][-1][0],
                         "kf": [[k[0], k[1], k[2], k[3], k[4]] for k in t["kf"]]})
        # pf/pb = 키잉 얼굴 프롬프트(첫 *양호* 얼굴 = 면적 ≥ 중앙값×PEOPLE_GOOD_AREA — subjects pf 산식 미러)
        kf_all = sorted((k for t in p["tracks"] for k in t["kf"]), key=lambda k: k[0])
        areas = sorted(k[3] * k[4] for k in kf_all)
        med = areas[len(areas) // 2]
        pf_k = next((k for k in kf_all if k[3] * k[4] >= PEOPLE_GOOD_AREA * med), kf_all[0])
        entry = {"pid": idx, "dur": round(p["dur"], 2), "first": round(p["first"], 2),
                 "last": round(p["last"], 2), "n": p["n"], "crop": crop_rel,
                 "pf": pf_k[0], "pb": [int(pf_k[1]), int(pf_k[2]), int(pf_k[3]), int(pf_k[4])], "segs": segs}
        # body = pid 확정 전신 트랙 세그 원본(머리 추정 kf는 저장 안 함 — 렌더가 body+hr에서 유도 = 공식 튜닝에 재분석 0)
        body = [{"f0": st["kf"][0][0], "f1": st["kf"][-1][0],
                 "kf": [[k[0], k[1], k[2], k[3], k[4]] for k in st["kf"]]}
                for st in sorted(body_by_pid.get(idx, []), key=lambda st: st["kf"][0][0])]
        if body:
            entry["body"] = body
        # hr = 얼굴/전신 비율 캘리브레이션 중앙값(이상치 강건) — 이 pid 얼굴 트랙의 투표 프레임 샘플만 귀속
        cal = [smp for st in body_by_pid.get(idx, []) for tid, ss in st.get("cal", {}).items()
               if face_pid.get(tid) == idx for smp in ss]
        if len(cal) >= HEAD_CAL_MIN:
            # float() 캐스팅 필수 — 샘플이 numpy float32(검출 좌표 유래)라 그대로면 json.dump가 TypeError로
            #   중간에 터져 tracks.json 잘림(합성 E2E 실측 적발 260710)
            med4 = [float(sorted(c[i] for c in cal)[len(cal) // 2]) for i in range(4)]
            entry["hr"] = {"rw": round(med4[0], 4), "rh": round(med4[1], 4),
                           "rcx": round(med4[2], 4), "rcy": round(med4[3], 4)}
        out_people.append(entry)

    # ── 피사체 조립(키잉 카드) — 사람은 pid로 재결합(얼굴 임베딩 승차) · 사물은 재등장 = 카드 분리(과분할 무해 철학 동일) ──
    merged = {}   # pid>0 인물 = pid로 병합 · 나머지 = 트랙 단독
    singles = []
    for st in s_tracks:
        if st["cls"] == 0 and st["pid"]:
            merged.setdefault(st["pid"], []).append(st)
        else:
            singles.append([st])
    subj_groups = list(merged.values()) + singles
    subj_list = []
    for grp in subj_groups:
        grp.sort(key=lambda st: st["kf"][0][0])
        kf_all = [k for st in grp for k in st["kf"]]
        kf_all.sort(key=lambda k: k[0])
        areas = sorted(k[3] * k[4] for k in kf_all)
        med = areas[len(areas) // 2]
        pf_k = next((k for k in kf_all if k[3] * k[4] >= SUBJ_GOOD_AREA * med), kf_all[0])   # 진입 슬리버 프롬프트 방지
        best_st = max(grp, key=lambda st: st["best_q"])
        subj_list.append({
            "cls": grp[0]["cls"], "pid": grp[0]["pid"] if grp[0]["cls"] == 0 else 0,
            "dur": sum((st["kf"][-1][0] - st["kf"][0][0]) / fps for st in grp),
            "first": kf_all[0][0] / fps, "last": kf_all[-1][0] / fps, "n": len(kf_all),
            "pf": pf_k[0], "pb": [pf_k[1], pf_k[2], pf_k[3], pf_k[4]],
            "crop_img": best_st["crop"],
            "segs": [{"f0": st["kf"][0][0], "f1": st["kf"][-1][0],
                      "kf": [[k[0], k[1], k[2], k[3], k[4]] for k in st["kf"]]} for st in grp]})
    subj_list.sort(key=lambda s: -s["dur"])
    subj_dropped = max(0, len(subj_list) - MAX_SUBJECTS)
    subj_list = subj_list[:MAX_SUBJECTS]
    out_subjects = []
    for sid, s in enumerate(subj_list, start=1):
        crop_rel = crop_by_pid.get(s["pid"], "")   # 얼굴 연결 = 얼굴 크롭 재사용(알아보기 최우선)
        if not crop_rel and s["crop_img"] is not None:
            crop_rel = f"crops/s{sid}.jpg"
            cv2.imwrite(os.path.join(outdir, crop_rel), s["crop_img"], [cv2.IMWRITE_JPEG_QUALITY, 82])
        out_subjects.append({"sid": sid, "kind": "person" if s["cls"] == 0 else "object",
                             "label": SUBJ_CLS.get(s["cls"], "피사체"), "pid": s["pid"], "crop": crop_rel,
                             "dur": round(s["dur"], 2), "first": round(s["first"], 2), "last": round(s["last"], 2),
                             "n": s["n"], "pf": s["pf"], "pb": [int(v) for v in s["pb"]], "segs": s["segs"]})

    # 원본 보관 = R2(렌더·재렌더 소스) — 실패·미설정이면 작은 파일만 git 폴백(비대 방지)
    src_url, src_note = "", ""
    ext = (os.path.splitext(src)[1] or ".mp4").lstrip(".").lower()
    if ext not in ("mp4", "mov", "m4v", "webm", "mkv", "avi"):
        ext = "mp4"
    size = os.path.getsize(src)
    if tg.R2_ON:
        key = f"track_src/{vid_id}.{ext}"
        ctype = "video/" + ("mp4" if ext in ("mp4", "m4v") else ext)
        if size > R2_FILE_UPLOAD_MIN:   # 대용량(300s URL 원본) = 파일 직접(aws cli·timeout 900) — bytes 경로는 90s 캡·전량 RAM
            src_url = r2_upload_file(src, key, ctype)
        else:
            with open(src, "rb") as fsrc:
                src_url = tg.r2_upload(fsrc.read(), key, ctype) or ""
    if not src_url:
        if size <= GIT_FALLBACK_MAX:
            import shutil
            shutil.copyfile(src, os.path.join(outdir, f"src.{ext}"))
            src_url = f"track_out/{vid_id}/src.{ext}"   # 상대경로 = ly_burn 관례(루트서빙 가정 제거 · 평의회9)
            src_note = "git-fallback"
        else:
            src_note = "src-lost"   # 렌더 시점에 명확 에러(원본 보관 실패 — 재분석 안내)
            print("⚠ R2 미설정·원본 대용량 — 렌더 소스 보관 실패(재분석 필요해질 수 있음)", flush=True)

    doc = {"v": 3, "id": vid_id,   # v3 = people에 body/hr/pf/pb 추가(additive · 260710 전신 폴백) — 소비자는 v 아닌 키 존재로 게이트(v2 subjects 선례)
           "meta": {"w": W, "h": H, "fps": round(fps, 3), "frames": total_frames, "dur": round(real_dur, 2),
                    "step": step, "ystep": ystep, "src": src_url, "src_note": src_note, "dropped": dropped,
                    "subj_dropped": subj_dropped, "subj_note": subj_state,
                    "made": kst_now()},
           "people": out_people, "subjects": out_subjects}
    with open(os.path.join(outdir, "tracks.json"), "w", encoding="utf-8") as fj:
        json.dump(doc, fj, ensure_ascii=False, separators=(",", ":"))
    print(f"tracks.json: 인물 {len(out_people)}명(드롭 {dropped}) · 피사체 {len(out_subjects)}개(드롭 {subj_dropped}) · {real_dur:.1f}s · 검출스텝 {step}f", flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        die("분석 중 오류 — 다른 영상으로 해보거나 다시 시도해줘.", f"unhandled: {type(e).__name__}: {e}")
