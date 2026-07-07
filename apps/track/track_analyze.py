#!/usr/bin/env python3
# 인물 트래킹 분석 — 얼굴 검출(YuNet) + IoU 트랙 + 정체성 군집(SFace) → viewer/track_out/<id>/tracks.json + crops/
#   사용: track_analyze.py <id> <video_path>   (track-make.yml analyze 스텝 전용 · LLM 0콜 = 순수 CV)
# 설계 불변(정본 = apps/track/00_지침):
#   - 검출 기반 트래킹 = 드리프트 0 — 매 검출이 위치를 재접지(프리미어 포인트 트래커의 누적 어긋남 대체가 이 앱의 존재 이유).
#   - 과분할 > 과병합: 동일인 카드 2장 = 무해(둘 다 선택하면 끝) / 남남 병합 = 엉뚱한 얼굴 모자이크 = 치명 → SIM_MERGE 보수.
#   - 좌표는 항상 원본 픽셀 공간(검출만 축소 프레임) · 분석/렌더 모두 cv2 디코드(회전 메타 처리 일관 = 좌표 어긋남 0).
#   - 원본 영상은 R2에 보관(track_src/<id>) → 렌더·재렌더가 재업로드 없이 소스 회수(분석 1회 = 렌더 N회).
# env: R2 5종(thumb_gen 재사용 · 없으면 작은 파일만 git 폴백) · TRACK_MAX_SEC(기본 180)
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
MAX_SEC = int(os.environ.get("TRACK_MAX_SEC", "180"))   # CPU 러너 보호 — 초과 = 명시 거절(조용한 부분처리 금지)
DET_LONG = 960          # 검출 입력 긴 변(원본이 더 작으면 원본 그대로) — 속도·소형 얼굴 균형
DET_PER_SEC = 12        # 초당 검출 횟수(사이 프레임은 렌더서 보간) — 전 프레임 검출 대비 ~3배 절약·마진이 커버
SCORE_TH = 0.65         # YuNet 신뢰 임계(기본 .9는 소형·측면 얼굴을 놓침 → 완화 + 트랙 최소 검출수로 오탐 상쇄)
NMS_TH = 0.3
IOU_MATCH = 0.25        # 검출 스텝 간격(~0.08s)에서 얼굴 이동은 작음 — 동일 트랙 판정 IoU
MISS_TTL_SEC = 0.7      # 이만큼 검출이 끊기면 트랙 종료(재등장은 새 트랙 → 군집이 같은 사람으로 재결합)
MIN_TRACK_DETS = 3      # 3회 미만 검출 트랙 = 오탐 취급(12/s 기준 0.25s)
EMB_MIN_PX = 42         # 임베딩 품질 하한(원본 픽셀 얼굴 폭) — 너무 작으면 임베딩 자체를 안 씀
EMB_TOP_N = 6           # 트랙당 임베딩 대표 크롭 수(고신뢰·대형 우선)
SIM_MERGE = 0.48        # SFace 코사인 동일인 병합 임계(공식 동일인 기준 0.363보다 보수 = 과분할 편향)
MAX_PEOPLE = 12         # 카드 상한(등장시간 순) — 초과분은 meta.dropped로 정직 표기
GIT_FALLBACK_MAX = 30 * 1024 * 1024   # R2 미설정 시 원본 git 보관 상한(ly_burn 동일)


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
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = nframes / fps if nframes > 0 else 0
    if dur > MAX_SEC + 2:
        die(f"영상이 너무 길어 — {MAX_SEC//60}분 이하만 돼(지금 {int(dur//60)}분 {int(dur%60)}초). 잘라서 올려줘.", f"길이 초과 {dur:.0f}s")

    det, rec = load_models()
    step = max(1, round(fps / DET_PER_SEC))

    tracks = []   # {kf:[[f,x,y,w,h,score]], last_f, cand:[(quality, aligned112, crop_bgr, score)], done}
    active = []
    f = -1
    first_shape = None
    hard_cap = int((MAX_SEC + 2) * fps)   # 컨테이너 메타가 거짓(frames=0 등)이어도 실측으로 하드캡
    while True:
        f += 1
        if f > hard_cap:
            die(f"영상이 너무 길어 — {MAX_SEC//60}분 이하만 돼. 잘라서 올려줘.", f"실측 길이 초과 f={f}")
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
        for d in dets:
            best, bi = 0.0, -1
            for i, t in enumerate(active):
                if i in used:
                    continue
                v = iou(d[:4], t["kf"][-1][1:5])
                if v > best:
                    best, bi = v, i
            box = [f, int(d[0]), int(d[1]), int(d[2]), int(d[3]), d[4]]
            if best >= IOU_MATCH and bi >= 0:
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
            # 임베딩·크롭 후보(고신뢰·대형 우선 top-N) — 정렬크롭은 검출 프레임에서 즉시(프레임 버퍼 재방문 불가)
            t = active[bi] if bi < len(active) else None
            if t is not None and d[3] >= 12:
                q = d[4] * math.sqrt(max(1.0, d[2]))
                if len(t["cand"]) < EMB_TOP_N or q > t["cand"][-1][0]:
                    aligned = None
                    if rec is not None and d[2] >= EMB_MIN_PX:
                        try:
                            aligned = rec.alignCrop(small, d[5])
                        except Exception:
                            aligned = None
                    # 대표 크롭(카드용) = 원본 프레임에서 40% 여유
                    mx, my = d[2] * 0.4, d[3] * 0.5
                    x0, y0 = int(max(0, d[0] - mx)), int(max(0, d[1] - my))
                    x1, y1 = int(min(W, d[0] + d[2] + mx)), int(min(H, d[1] + d[3] + my))
                    crop = frame[y0:y1, x0:x1].copy() if (x1 - x0 > 8 and y1 - y0 > 8) else None
                    t["cand"].append((q, aligned, crop, d[4]))
                    t["cand"].sort(key=lambda c: -c[0])
                    del t["cand"][EMB_TOP_N:]
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

    # 트랙 대표 임베딩 → 정체성 군집(그리디 · 과분할 편향)
    for t in tracks:
        embs = []
        if rec is not None:
            for q, aligned, crop, sc in t["cand"]:
                if aligned is None:
                    continue
                try:
                    e = rec.feature(aligned).flatten().astype(np.float32)
                    n = np.linalg.norm(e)
                    if n > 0:
                        embs.append(e / n)
                except Exception:
                    pass
        t["emb"] = np.mean(embs, axis=0) if embs else None
        if t["emb"] is not None:
            n = np.linalg.norm(t["emb"])
            t["emb"] = t["emb"] / n if n > 0 else None
        t["dur"] = (t["kf"][-1][0] - t["kf"][0][0]) / fps
    tracks.sort(key=lambda t: -t["dur"])

    people = []   # {tracks:[], emb(이동평균), n_emb}
    for t in tracks:
        best, bi = 0.0, -1
        if t["emb"] is not None:
            for i, p in enumerate(people):
                if p["emb"] is None:
                    continue
                v = float(np.dot(t["emb"], p["emb"]))
                if v > best:
                    best, bi = v, i
        if bi >= 0 and best >= SIM_MERGE:
            p = people[bi]
            p["tracks"].append(t)
            k = p["n_emb"]
            p["emb"] = (p["emb"] * k + t["emb"]) / (k + 1)
            n = np.linalg.norm(p["emb"])
            p["emb"] = p["emb"] / n if n > 0 else p["emb"]
            p["n_emb"] = k + 1
        else:
            people.append({"tracks": [t], "emb": t["emb"], "n_emb": 1 if t["emb"] is not None else 0})

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

    # 대표 크롭 저장(카드) — 사람별 최고 품질 크롭
    out_people = []
    for idx, p in enumerate(people, start=1):
        best_crop, best_q = None, -1.0
        for t in p["tracks"]:
            for q, aligned, crop, sc in t["cand"]:
                if crop is not None and q > best_q:
                    best_q, best_crop = q, crop
        crop_rel = ""
        if best_crop is not None:
            ch, cw = best_crop.shape[:2]
            s = 256.0 / max(ch, cw)
            if s < 1.0:
                best_crop = cv2.resize(best_crop, (max(1, int(cw * s)), max(1, int(ch * s))), interpolation=cv2.INTER_AREA)
            crop_rel = f"crops/p{idx}.jpg"
            cv2.imwrite(os.path.join(outdir, crop_rel), best_crop, [cv2.IMWRITE_JPEG_QUALITY, 82])
        segs = []
        for t in sorted(p["tracks"], key=lambda t: t["kf"][0][0]):
            segs.append({"f0": t["kf"][0][0], "f1": t["kf"][-1][0],
                         "kf": [[k[0], k[1], k[2], k[3], k[4]] for k in t["kf"]]})
        out_people.append({"pid": idx, "dur": round(p["dur"], 2), "first": round(p["first"], 2),
                           "last": round(p["last"], 2), "n": p["n"], "crop": crop_rel, "segs": segs})

    # 원본 보관 = R2(렌더·재렌더 소스) — 실패·미설정이면 작은 파일만 git 폴백(비대 방지)
    src_url, src_note = "", ""
    ext = (os.path.splitext(src)[1] or ".mp4").lstrip(".").lower()
    if ext not in ("mp4", "mov", "m4v", "webm", "mkv", "avi"):
        ext = "mp4"
    size = os.path.getsize(src)
    if tg.R2_ON:
        with open(src, "rb") as fsrc:
            src_url = tg.r2_upload(fsrc.read(), f"track_src/{vid_id}.{ext}", "video/" + ("mp4" if ext in ("mp4", "m4v") else ext)) or ""
    if not src_url:
        if size <= GIT_FALLBACK_MAX:
            import shutil
            shutil.copyfile(src, os.path.join(outdir, f"src.{ext}"))
            src_url = f"/track_out/{vid_id}/src.{ext}"
            src_note = "git-fallback"
        else:
            src_note = "src-lost"   # 렌더 시점에 명확 에러(원본 보관 실패 — 재분석 안내)
            print("⚠ R2 미설정·원본 대용량 — 렌더 소스 보관 실패(재분석 필요해질 수 있음)", flush=True)

    doc = {"v": 1, "id": vid_id,
           "meta": {"w": W, "h": H, "fps": round(fps, 3), "frames": total_frames, "dur": round(real_dur, 2),
                    "step": step, "src": src_url, "src_note": src_note, "dropped": dropped, "made": kst_now()},
           "people": out_people}
    with open(os.path.join(outdir, "tracks.json"), "w", encoding="utf-8") as fj:
        json.dump(doc, fj, ensure_ascii=False, separators=(",", ":"))
    print(f"tracks.json: 인물 {len(out_people)}명(드롭 {dropped}) · {real_dur:.1f}s · 검출스텝 {step}f", flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        die("분석 중 오류 — 다른 영상으로 해보거나 다시 시도해줘.", f"unhandled: {type(e).__name__}: {e}")
