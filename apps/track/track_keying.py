#!/usr/bin/env python3
# 피사체 키잉 렌더 — 선택 피사체만 남기고 나머지 전부 투명(알파). track_render.py mode='keying'에서
#   lazy import로 위임(torch 스택 = 키잉 러너에서만 · 모자이크/핀셋 경로는 이 파일을 import조차 안 함).
# env RENDER = {"mode":"keying","keep":[sid],"keepP":[pid],"extra":[{"t":초,"x":0..1,"y":0..1}],"opts":{"feather":px}}
#   keepP = 얼굴 단위 남기기(people[].pf/pb 프롬프트 · 260710) — keep(전신 피사체)과 별도 배열(keep 정수 계약 불변)
# 파이프(정본 = apps/track/00_지침 §1.5):
#   ① 프롬프트 계획 — keep 피사체 = 첫 양호 등장 프레임(pf)의 박스 프롬프트 · extra = 운영자 탭 포인트.
#      SAM2는 전파 시작 후 새 객체 추가 금지(가드 실측) → 프롬프트 프레임 그룹별 멀티패스(그 프레임→끝).
#      박스와 포인트는 한 콜에 섞으면 같은 객체로 접힘(_prepare_prompts cat dim=1) → 패스 = 박스 전용/포인트 전용.
#      extra는 역패스([0,t0) 역재생 트림 · 512급 스케일) 추가 = 어느 장면에서 찍어도 앞뒤 전체 커버(운영자 승인).
#   ② 패스별 세그 스트림 — ffmpeg 트림(-ss 정확탐색)+15fps 데시메이션본에 SAM2.1 tiny(512) 전파 → 마스크 PNG(/tmp).
#      트림본은 회전 메타가 베이크되어 cv2/ffmpeg 로더 좌표 일치(원본 좌표 계약 = 분석과 동일 · 00_지침 좌표 불변).
#   ③ 합성 — 원본 풀해상 순차 디코드 + 마스크 hold(세그 15fps → 원 fps) + 페더 → BGRA 두 파이프 동시 인코딩:
#      마스터 = ProRes 4444 MOV(yuva444p10le · 프리미어 네이티브 알파) · 프리뷰 = VP9 webm(yuva420p · 뷰어 재생).
# 실측(260709 · 4vCPU=러너 동급): 전파 512 = 627ms/f(1객체)·1030ms/f(3객체) · ProRes 22s/10초분 ·
#   VP9 37s/10초분(1080p — 프리뷰는 540p라 더 빠름) → 60s 클립 총 ≈15분 · 90s ≈25분(잡 40분 캡 내).
import json
import math
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".github", "scripts"))
import thumb_gen as tg   # r2_upload · R2_ON 재사용(track_render와 동일)

MODELS = os.environ.get("NOMUTE_TRACK_MODELS", os.path.expanduser("~/.cache/nomute-track"))
SAM_CKPT = os.path.join(MODELS, "sam2.1_t.pt")
KEY_MAX_SEC = 90         # 키잉 길이 캡 · 분석/모자이크 300s 캡과 별개(실측 = 30fps·단일 패스 기준 90s ≈ 25분 — 평의회9 정직화)
KEY_MAX_OBJ = 4          # keep+keepP+extra 합계 캡 — 3객체 1030ms/f 실측(객체당 +0.2s) · 총량은 아래 예산 가드가 최종 강제
KEY_MAX_LONG = 1920      # 해상도 캡(긴 변) — 4K는 트림·마스크·인코딩·업로드 전 축 폭발(평의회9 F2 · 분석 DET_LONG 선례)
KEY_BUDGET_SEC = 1620    # 발사 전 예상 전파 예산(27분) — 멀티패스 총량이 스텝 35분 캡을 못 넘게 사전 거절(평의회4·9)
PASS_HARD_SEC = 1800     # 전파 루프 경과 백스톱(30분) — 예산 추정이 빗나가도 스텝 타임아웃 전에 정직 에러
SEG_S_1 = 0.63           # 실측 단가: 1객체 전파 s/세그프레임(512) — 예산 추정용(단위 초 — MS 아님·재검증 개명)
SEG_S_OBJ = 0.20         # 실측 단가: 추가 객체당 s/세그프레임
TAIL_S_PF = 0.25         # 실측 단가: 합성+인코딩+업로드 꼬리 s/원본프레임(1080×1920 기준·해상도 비례) —
                         #   합성은 원 fps 전량 순회라 60fps = 꼬리 2배(재검증9: 예산에 미반영 시 통과 후 타임아웃)
FACE_KEY_EXPAND = 1.3    # 얼굴(keepP) 박스 프롬프트 팽창 — 얼굴 검출 박스 그대로는 SAM2가 '떠 있는 얼굴 타원'만 물 수
                         #   있어 머리카락·두상까지 포함 유도(260710) · 정직 한계: 두상 박스에서 상체까지 물 수 있음(지침 §3)
SEG_FPS = 15.0           # 세그멘테이션 프레임레이트(원 30fps 대비 절반 = 비용 절반 · 마스크는 hold)
IMGSZ = 512              # SAM2 입력 긴 변 — 1024는 3937ms/f로 불가(실측) · 512 마스크 오차 0.35%
FEATHER_DFLT = 3         # 512 업스케일 계단 완화 기본 페더 px
PREVIEW_LONG = 960       # 프리뷰 긴 변(9:16 = 540×960)
GIT_FALLBACK_MAX = 30 * 1024 * 1024


def _r2_upload_file(path, key, ctype):
    """대용량 산출물 파일 직접 업로드 — thumb_gen.r2_upload(bytes 전량 RAM + 임시파일 복제 + 90s 캡)는
    썸네일 PNG용이라 GB급 마스터 MOV에 부적합(평의회2·9: RAM 스파이크·디스크 2배·타임아웃 상시 유실)
    → 같은 aws cli 경로를 파일 인자·timeout 900으로 미러링. 실패 = ""(fail-soft — 콜러가 폴백/에러 판단)."""
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


def _num(v, lo, hi, dflt):
    try:
        x = float(v)
        if math.isnan(x):
            return dflt
        return max(lo, min(hi, x))
    except (TypeError, ValueError):
        return dflt


def _sample_box(subj, f):
    """피사체 segs에서 프레임 f의 박스 선형보간 — 밖이면 None (track_render.sample 등가 · 2/s kf)."""
    for seg in subj.get("segs") or []:
        kf = seg.get("kf") or []
        if not kf or f < kf[0][0] or f > kf[-1][0]:
            continue
        for i in range(len(kf) - 1):
            a, b = kf[i], kf[i + 1]
            if a[0] <= f <= b[0]:
                t = 0.0 if b[0] == a[0] else (f - a[0]) / float(b[0] - a[0])
                return [a[j] + (b[j] - a[j]) * t for j in range(1, 5)]
        return list(kf[-1][1:5])
    return None


def _expand_box(b, W, H, k):
    """박스 [x,y,w,h] 중심 기준 k× 팽창 + 프레임 클램프 — 얼굴 프롬프트의 두상 포함 유도(260710)."""
    cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
    w2, h2 = b[2] * k, b[3] * k
    x0, y0 = max(0.0, cx - w2 / 2), max(0.0, cy - h2 / 2)
    x1, y1 = min(float(W), cx + w2 / 2), min(float(H), cy + h2 / 2)
    return [x0, y0, max(1.0, x1 - x0), max(1.0, y1 - y0)]


def plan_passes(subjects, keep, people, keepP, extras, fps, W, H, total_f=0):
    """멀티패스 계획 — [{f0(프롬프트 프레임), kind:'box'|'point', prompts:[…]}] · 근접(≤0.5s) 박스는 한 패스.
    수동 포인트는 프레임이 같아도 별도 패스(박스+포인트 혼합 = 같은 객체로 접히는 함정 회피).
    keepP(얼굴 단위 · 260710) = people의 pf/pb 박스 프롬프트를 FACE_KEY_EXPAND 팽창해 subjects 박스와 동일 경로
    편입(people segs도 {segs:[{kf}]} 동형이라 _sample_box 재사용)."""
    win = max(1, int(round(0.5 * fps)))
    boxes = []   # (pf, subj_like, expand)
    for s in subjects:
        if s["sid"] in keep:
            boxes.append((int(s.get("pf") or 0), s, 1.0))
    for p in people:
        if p.get("pid") in keepP:
            boxes.append((int(p.get("pf") or 0), p, FACE_KEY_EXPAND))
    boxes.sort(key=lambda x: x[0])
    passes = []
    for pf, s, ex in boxes:
        joined = False
        for p in passes:
            if p["kind"] == "box" and abs(pf - p["f0"]) <= win:
                b = _sample_box(s, p["f0"]) or s.get("pb")   # 그룹 대표 프레임 시점의 실측 박스(없으면 자기 pf 박스)
                if b:
                    if ex != 1.0:
                        b = _expand_box(b, W, H, ex)
                    p["prompts"].append([b[0], b[1], b[0] + b[2], b[1] + b[3]])
                    joined = True
                    break
        if not joined:
            b = s.get("pb") or [0, 0, W, H]
            if ex != 1.0:
                b = _expand_box(b, W, H, ex)
            passes.append({"f0": pf, "kind": "box", "prompts": [[b[0], b[1], b[0] + b[2], b[1] + b[3]]]})
    margin = int(round(0.7 * fps))
    for e in extras:   # 수동 지정 — 순방향(탭→끝) + 역방향(탭→0 · 앞 구간 커버 = 어느 장면에서 찍어도 전체 추적 · 운영자 승인)
        f0 = max(0, int(round(float(e["t"]) * fps)))
        head_ok = f0 > margin                                     # 앞 구간 유의미(0.7초 초과)
        tail_ok = (total_f <= 0) or (f0 < total_f - margin)       # 뒤 구간 유의미 — 탭=끝이면 순패스가 0프레임으로
        if tail_ok or not head_ok:                                #   죽어 역패스까지 무산(평의회9 M1) → 대칭 생략·초단편은 순 폴백
            passes.append({"f0": f0, "kind": "point", "prompts": [[float(e["x"]) * W, float(e["y"]) * H]]})
        if head_ok:
            # ⚠ 좌표는 정규(0..1)로 보관 — 역트림은 512급 스케일이라 원본 픽셀 좌표를 그대로 주면 프레임 밖/엉뚱한
            #   세그먼트를 찍는다(E2E 실측 적발: 포인트가 트림 좌표계여야 함). 세그 직전에 트림 실해상으로 곱한다.
            passes.append({"f0": f0, "kind": "point", "pt_norm": [[float(e["x"]), float(e["y"])]], "prompts": [], "rev": True})   # 커버 = [0, f0)
    passes.sort(key=lambda p: p["f0"])
    return passes


def run(vid_id, req, doc, outdir):
    """track_render.main()에서 위임 — 예외는 그쪽 fail-soft 래퍼가 video.json{error}로 기록."""
    try:
        import torch
        from ultralytics.models.sam import SAM2VideoPredictor
    except Exception:
        raise RuntimeError("키잉 환경 준비 실패(의존 설치) — 잠시 후 다시 렌더해줘.")
    if not (os.path.isfile(SAM_CKPT) and os.path.getsize(SAM_CKPT) > 100_000_000):
        env = dict(os.environ, TRACK_MODE="render", TRACK_HEAVY="1")   # setup.sh 미완(네트워크) 재시도 — 멱등
        subprocess.run(["bash", os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup.sh")],
                       check=False, timeout=900, env=env)
    if not (os.path.isfile(SAM_CKPT) and os.path.getsize(SAM_CKPT) > 100_000_000):
        raise RuntimeError("키잉 모델 준비 실패(네트워크) — 잠시 후 다시 렌더해줘.")
    torch.set_num_threads(max(1, os.cpu_count() or 4))

    meta = doc.get("meta") or {}
    subjects = doc.get("subjects") or []
    people = [p for p in (doc.get("people") or []) if isinstance(p, dict) and p.get("pid")]
    if not subjects and not people and not (req.get("extra") or []):
        raise RuntimeError("이 분석엔 피사체 정보가 없어 — 처음(영상 분석)부터 다시 해줘.")
    dur = float(meta.get("dur") or 0)
    if dur > KEY_MAX_SEC + 1:
        raise RuntimeError(f"키잉은 {KEY_MAX_SEC}초까지야(지금 {int(dur)}초) — 잘라서 해줘.")

    all_sids = {s["sid"] for s in subjects}
    keep = {int(t) for t in (req.get("keep") or []) if isinstance(t, (int, float)) and not isinstance(t, bool)} & all_sids
    # keepP = 얼굴 단위(260710) — pb 없는 pid(구 v2 분석) 선택 = 명시 에러(조용한 무시 금지 · 정직)
    keepP = {int(t) for t in (req.get("keepP") or []) if isinstance(t, (int, float)) and not isinstance(t, bool)} \
        & {p["pid"] for p in people}
    if any(not (isinstance(p.get("pb"), list) and len(p["pb"]) == 4) for p in people if p["pid"] in keepP):
        raise RuntimeError("이 분석엔 얼굴 프롬프트가 없어(구 버전 분석) — 처음(영상 분석)부터 다시 해줘.")
    extras = []
    for e in (req.get("extra") or [])[:KEY_MAX_OBJ]:
        if not isinstance(e, dict):
            continue
        t = _num(e.get("t"), 0, min(KEY_MAX_SEC, dur) if dur > 0 else KEY_MAX_SEC, None)   # dur 클램프 = 직접 dispatch 방어심층(평의회9 M2)
        x, y = _num(e.get("x"), 0, 1, None), _num(e.get("y"), 0, 1, None)
        if t is not None and x is not None and y is not None:
            extras.append({"t": t, "x": x, "y": y})
    n_obj = len(keep) + len(keepP) + len(extras)
    if n_obj < 1:
        raise RuntimeError("남길 피사체를 골라줘 — 카드 선택이나 직접 지정 후 렌더.")
    if n_obj > KEY_MAX_OBJ:
        raise RuntimeError(f"피사체는 최대 {KEY_MAX_OBJ}개까지야 — 줄여서 렌더해줘.")

    # track_render의 소스 회수 재사용(순환 없음 — 그쪽은 이 모듈을 함수 안에서만 import)
    import track_render as tr
    src = tr.resolve_src(meta, vid_id, outdir)
    if not src:
        raise RuntimeError("원본 보관본을 못 가져왔어 — 처음(영상 분석)부터 다시 해줘.")

    cap = cv2.VideoCapture(src)
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)   # 분석과 동일 = 좌표 공간 일치(불변)
    except Exception:
        pass
    if not cap.isOpened():
        raise RuntimeError("원본을 못 열었어 — 처음부터 다시 해줘.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    if not fps or fps <= 1 or fps > 240 or math.isnan(fps):
        fps = float(meta.get("fps") or 30.0)
    ok, first = cap.read()
    if not ok:
        raise RuntimeError("원본 프레임을 못 읽었어 — 처음부터 다시 해줘.")
    H, W = first.shape[:2]
    if max(W, H) > KEY_MAX_LONG:   # 해상도 캡 — 4K는 시간·디스크·RAM 삼중 폭발(평의회9 F2 · 명시 거절이 정직)
        raise RuntimeError(f"키잉은 긴 변 {KEY_MAX_LONG}px까지야(지금 {max(W, H)}px) — 1080p로 줄여서 올려줘.")
    W2, H2 = W - (W % 2), H - (H % 2)
    real_dur = float(meta.get("frames") or 0) / fps if meta.get("frames") else dur
    if real_dur > KEY_MAX_SEC + 1:
        raise RuntimeError(f"키잉은 {KEY_MAX_SEC}초까지야 — 잘라서 해줘.")

    total_f = float(meta.get("frames") or 0) or (real_dur * fps)
    passes = plan_passes(subjects, keep, people, keepP, extras, fps, W, H, total_f=total_f)   # total_f = 탭=끝 순패스 대칭 생략 판정(평의회9 M1)
    if not passes:
        raise RuntimeError("남길 피사체를 골라줘 — 카드 선택이나 직접 지정 후 렌더.")
    # 발사 전 총량 예산 가드 — 캡(90s·4객체)은 객체 수만 묶고 멀티패스 총량은 못 묶는다(평의회9 F1: 수동 4개
    #   분산 지정 = 4패스 = 56분 > 잡 40분). 예상 = 전파(패스별 실측 단가) + 꼬리(합성·인코딩·업로드 = 원 fps
    #   전량 순회라 fps·해상도 비례 — 재검증9: 전파만 계산하면 60fps 다객체가 통과 후 스텝 타임아웃).
    est_seg = sum((min(float(p["f0"]), total_f) if p.get("rev") else max(0.0, total_f - p["f0"])) / fps
                  * SEG_FPS * (SEG_S_1 + SEG_S_OBJ * max(0, len(p.get("pt_norm") or p["prompts"]) - 1))
                  for p in passes)   # 역패스 커버 = [0, f0) — 예산에 자동 포함(직접 지정 1개 = 순+역 합이 영상 전체 1회분)
    est = est_seg + total_f * TAIL_S_PF * (W * H / 2_073_600.0)
    if est > KEY_BUDGET_SEC:
        raise RuntimeError(f"이 조합은 렌더가 너무 오래 걸려(예상 {int(est // 60)}분) — "
                           f"피사체 수·영상 길이를 줄이거나(60fps면 더 짧게) 등장 시점이 비슷한 것끼리 골라줘.")
    fe = int(round(_num((req.get("opts") or {}).get("feather"), 0, 40, FEATHER_DFLT)))

    # ── ② 패스별 SAM2 전파 → 마스크 PNG ──
    mask_root = "/tmp/keymasks"
    shutil.rmtree(mask_root, ignore_errors=True)
    predictor = None
    t_all = time.time()
    for k, p in enumerate(passes):
        t0_sec = p["f0"] / fps
        trim = f"/tmp/keypass{k}.mp4"
        if p.get("rev"):
            # 역방향 트림 = [0, t0) 구간을 512 긴변으로 줄여 역재생 인코딩 — reverse 필터는 전 프레임 램 버퍼라
            #   원해상이면 GB급 폭발(512급 ≈ 수백MB 안전). SAM2 입력이 어차피 512라 마스크 품질 동급 —
            #   마스크만 합성에서 원해상 업스케일. 역재생 프레임 0 = 원본 t0 직전 = 프롬프트 좌표 그대로 유효.
            vf = f"fps={SEG_FPS:g},scale='if(gt(iw,ih),{IMGSZ},-2)':'if(gt(iw,ih),-2,{IMGSZ})',reverse"
            # ⚠ -t는 반드시 입력 옵션(-i 앞): reverse는 EOF까지 버퍼 후 역방출이라 출력측 -t는 '역재생의 앞
            #   t0초 = 원본 꼬리'를 잘라 [T-t0,T]를 캡처한다(평의회 ffmpeg 실측 적발 — 의도 [0,t0)과 정반대).
            #   입력측 -t = [0,t0)만 디코드 = 의미 정확 + reverse 버퍼도 그만큼만.
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-t", f"{t0_sec:.3f}", "-i", src,
                   "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", trim]
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ss", f"{t0_sec:.3f}",
                   "-vf", f"fps={SEG_FPS:g}", "-an", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "18", trim]
        r = subprocess.run(cmd, timeout=600)
        if r.returncode != 0 or not os.path.isfile(trim) or os.path.getsize(trim) < 1024:
            raise RuntimeError("전처리(트림) 실패 — 다시 시도해줘.")
        if p.get("rev"):   # 역패스 프롬프트 = 정규좌표 × 트림 실해상(512급) — 원본 픽셀 좌표는 좌표계 불일치(실측 적발)
            tc = cv2.VideoCapture(trim)
            tw, th = int(tc.get(cv2.CAP_PROP_FRAME_WIDTH)), int(tc.get(cv2.CAP_PROP_FRAME_HEIGHT))
            tc.release()
            if tw < 2 or th < 2:
                raise RuntimeError("전처리(트림) 실패 — 다시 시도해줘.")
            p["prompts"] = [[nx * tw, ny * th] for nx, ny in p["pt_norm"]]
        mdir = os.path.join(mask_root, f"p{k}")
        os.makedirs(mdir, exist_ok=True)
        if predictor is None:
            predictor = SAM2VideoPredictor(overrides=dict(conf=0.25, task="segment", mode="predict",
                                                          imgsz=IMGSZ, model=SAM_CKPT, save=False, verbose=False))
        else:
            # ⚠ 패스 간 상태 리셋 필수(평의회2 치명 적발): 라이브러리 init_state는 `if len(inference_state)>0: return`
            #   가드라 두 번째 predict 콜에서 리셋이 스킵 → 새 프롬프트가 조용히 무시되고 이전 패스 객체를 계속
            #   추적(무증상 오출력). 비우면 on_predict_start의 init_state가 재초기화 = 패스 격리.
            predictor.inference_state = {}
        kwargs = {"bboxes": p["prompts"]} if p["kind"] == "box" else {"points": p["prompts"], "labels": [1] * len(p["prompts"])}
        n_masks = 0
        live_masks = 0   # 비어있지 않은 마스크 수 — 전 구간 세그 실패가 '성공 전-투명'으로 위장하는 것 차단(평의회2)
        t_p = time.time()
        for j, res in enumerate(predictor(source=trim, stream=True, **kwargs)):
            m = None
            if res.masks is not None and len(res.masks.data):
                m = (res.masks.data.any(0).cpu().numpy().astype(np.uint8)) * 255
                mh, mw = m.shape[:2]
                if p.get("rev"):   # 역패스 = 512급 스케일 트림 → 종횡비로 회전 파리티 검사(치수 직접 비교 불가)
                    if abs(mw / max(1, mh) - W / max(1, H)) > 0.05 * (W / max(1, H)):
                        raise RuntimeError("전처리 회전 불일치 — 영상을 mp4로 변환해 다시 올려줘.")
                elif (mh, mw) != (H, W):   # 순패스 = 원해상 트림 — ffmpeg↔cv2 회전 파리티 발산(90/270) = 정직 실패(평의회3)
                    raise RuntimeError("전처리 회전 불일치 — 영상을 mp4로 변환해 다시 올려줘.")
                if m.any():
                    live_masks += 1
            if m is None:
                m = np.zeros(res.orig_shape[:2], np.uint8)   # 객체 소실 프레임 = 빈 마스크(트림 해상 = 저장 규격 통일)
            cv2.imwrite(os.path.join(mdir, f"{j:06d}.png"), m)
            n_masks = j + 1
            if j % 150 == 0:
                print(f"패스{k + 1}/{len(passes)} 전파 {j}f · {time.time() - t_p:.0f}s", flush=True)
            if time.time() - t_all > PASS_HARD_SEC:   # 예산 추정 빗나감 백스톱 — 스텝 타임아웃 전 정직 에러(평의회9)
                raise RuntimeError("렌더 시간 초과 — 피사체 수를 줄이거나 영상을 잘라서 다시 해줘.")
        p["mdir"], p["n_masks"], p["t0"] = mdir, n_masks, t0_sec
        os.remove(trim)
        if n_masks == 0 or live_masks == 0:
            raise RuntimeError("피사체 마스크 생성 실패 — 다른 프레임에서 지정하거나 다시 시도해줘.")
        print(f"패스{k + 1}: {n_masks}마스크(실마스크 {live_masks}) · {time.time() - t_p:.0f}s", flush=True)

    # ── ③ 합성 + 이중 인코딩(마스터 ProRes4444 + 프리뷰 VP9) ──
    pscale = min(1.0, PREVIEW_LONG / max(W2, H2))
    PW, PH = max(2, int(W2 * pscale) & ~1), max(2, int(H2 * pscale) & ~1)   # 하한 2 = 병적 종횡비 0px 방어(평의회3)
    out_mov, out_webm = "/tmp/key_master.mov", "/tmp/key_preview.webm"
    enc_m = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W2}x{H2}", "-r", f"{fps:.4f}", "-i", "-",
         "-i", src, "-map", "0:v", "-map", "1:a?",
         "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "8", "-q:v", "11",
         "-c:a", "aac", "-b:a", "160k", "-shortest", out_mov], stdin=subprocess.PIPE)   # q11 = 기본比 −44% 용량·화질 고품질 구간(실측 260709)
    enc_p = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{PW}x{PH}", "-r", f"{fps:.4f}", "-i", "-",
         "-i", src, "-map", "0:v", "-map", "1:a?",
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "34", "-b:v", "0", "-cpu-used", "6", "-row-mt", "1",
         "-c:a", "libopus", "-b:a", "64k", "-shortest", out_webm], stdin=subprocess.PIPE)

    cap.release()
    cap = cv2.VideoCapture(src)   # 처음부터 재디코드(첫 프레임 포함 순차)
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    except Exception:
        pass
    for p in passes:
        p["last_j"], p["cur"] = -1, None
    kblur = 2 * fe + 1
    f = 0
    t0 = time.time()
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame = frame[:H2, :W2]
            alpha = None
            for p in passes:
                if p.get("rev"):   # 역패스 커버 = [0, f0) — 역재생이라 인덱스 뒤집기(원본 0초 = 마지막 마스크)
                    if f >= p["f0"]:
                        continue
                    j = min(p["n_masks"] - 1, max(0, p["n_masks"] - 1 - int((f / fps) * SEG_FPS + 1e-6)))
                else:
                    if f < p["f0"]:
                        continue
                    j = min(p["n_masks"] - 1, int((f / fps - p["t0"]) * SEG_FPS + 1e-6))
                    if j < 0:
                        continue
                if j != p["last_j"]:
                    m = cv2.imread(os.path.join(p["mdir"], f"{j:06d}.png"), cv2.IMREAD_GRAYSCALE)
                    if m is not None and m.shape[:2] != (H, W):   # 역패스 512급 트림 마스크 = 원해상 업스케일(순패스는 원해상 그대로)
                        m = cv2.resize(m, (W2, H2), interpolation=cv2.INTER_LINEAR)
                    p["cur"] = m if m is not None else None
                    p["last_j"] = j
                if p["cur"] is not None:
                    c = p["cur"][:H2, :W2]
                    alpha = c if alpha is None else np.maximum(alpha, c)
            if alpha is None:
                alpha = np.zeros((H2, W2), np.uint8)
            elif fe > 0:
                alpha = cv2.GaussianBlur(alpha, (kblur, kblur), fe * 0.6)
            bgra = np.dstack((frame, alpha))
            try:
                enc_m.stdin.write(bgra.tobytes())
                enc_p.stdin.write((bgra if pscale >= 1.0 else cv2.resize(bgra, (PW, PH), interpolation=cv2.INTER_AREA)).tobytes())
            except BrokenPipeError:
                break
            f += 1
            if f % 300 == 0:
                print(f"합성 {f}f · {time.time() - t0:.0f}s", flush=True)
        for enc in (enc_m, enc_p):
            try:
                enc.stdin.close()
            except Exception:
                pass
        rc_m = enc_m.wait(timeout=1200)
        rc_p = enc_p.wait(timeout=1200)
    finally:
        cap.release()
        for enc in (enc_m, enc_p):
            if enc.poll() is None:
                enc.kill()
        shutil.rmtree(mask_root, ignore_errors=True)
    if rc_m != 0 or not os.path.isfile(out_mov) or os.path.getsize(out_mov) < 1024:
        raise RuntimeError("영상 인코딩 실패(마스터) — 다시 시도해줘.")
    if rc_p != 0 or not os.path.isfile(out_webm) or os.path.getsize(out_webm) < 1024:
        raise RuntimeError("영상 인코딩 실패(프리뷰) — 다시 시도해줘.")
    print(f"키잉 완료 {f}프레임 · 총 {time.time() - t_all:.0f}s · 마스터 {os.path.getsize(out_mov) // 1048576}MB · "
          f"프리뷰 {os.path.getsize(out_webm) // 1048576}MB", flush=True)

    # 출력 키 = stable + ?v= 버스트(track_render 불변 계승) — 마스터/프리뷰 둘 다 파일 직접 업로드(GB급 RAM 적재 금지)
    bust = int(time.time())
    url = _r2_upload_file(out_mov, f"track_res/{vid_id}/keying.mov", "video/quicktime")
    prev = _r2_upload_file(out_webm, f"track_res/{vid_id}/keying_preview.webm", "video/webm")
    if not url and os.path.getsize(out_mov) <= GIT_FALLBACK_MAX:
        shutil.copyfile(out_mov, os.path.join(outdir, "result-keying.mov"))
        url = f"track_out/{vid_id}/result-keying.mov"
    if not prev and os.path.getsize(out_webm) <= GIT_FALLBACK_MAX:
        shutil.copyfile(out_webm, os.path.join(outdir, "result-keying.webm"))
        prev = f"track_out/{vid_id}/result-keying.webm"
    if not url and not prev:
        raise RuntimeError("결과 업로드 실패(R2) — 잠시 후 다시 렌더해줘.")
    tr.out_json(outdir, {"url": (f"{url}?v={bust}" if url else ""), "preview": (f"{prev}?v={bust}" if prev else ""),
                         "mode": "keying", "n": n_obj, "frames": f, "opts": {"feather": fe},
                         "note": ("" if url else "master-lost")})   # 마스터 유실(R2 미설정·대용량) = 프리뷰만 — 뷰어가 정직 표시
