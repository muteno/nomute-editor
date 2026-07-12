#!/usr/bin/env python3
# FX7 베스트 프레임 추출 — 선명도(라플라시안)+노출 점수 상위 N장 PNG(시간 간격 보장).
# 용도: 영상 → 스틸 → 이미지 스튜디오(생성형 확장/썸네일) 체인의 엔진분. 토큰 0(OpenCV).
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import done


def best_frames(video, outdir, n=3, min_gap=1.5, samples=120):
    import cv2  # lazy — 미설치면 setup.sh 안내가 사유로 뜸
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"FX7 frame: 영상 못 엶({video})")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        raise RuntimeError("FX7 frame: 프레임 수 0")
    stride = max(1, total // max(8, samples))
    scored = []
    for idx in range(0, total, stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        sharp = cv2.Laplacian(g, cv2.CV_64F).var()
        mean = float(g.mean())
        w = 1.0 if 35 <= mean <= 220 else 0.3  # 암전·백화 컷
        scored.append((sharp * w, idx / fps, idx))
    cap.release()
    if not scored:
        raise RuntimeError("FX7 frame: 읽힌 프레임 0")
    scored.sort(reverse=True)
    picks = []
    for s, t, idx in scored:
        if len(picks) >= n:
            break
        if all(abs(t - pt) >= min_gap for _, pt, _ in picks):
            picks.append((s, t, idx))
    os.makedirs(outdir, exist_ok=True)
    outs = []
    cap = cv2.VideoCapture(video)
    for s, t, idx in sorted(picks, key=lambda x: x[1]):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        if not ok:
            continue
        p = os.path.join(outdir, f"best_{t:07.2f}s.png")
        cv2.imwrite(p, fr)
        outs.append({"t": round(t, 2), "path": p, "score": round(s, 1)})
    cap.release()
    return {"module": "FX7", "frames": outs}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX7 베스트 프레임")
    ap.add_argument("video"); ap.add_argument("outdir")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--min-gap", type=float, default=1.5)
    a = ap.parse_args()
    done(best_frames(a.video, a.outdir, a.n, a.min_gap))
