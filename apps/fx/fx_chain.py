#!/usr/bin/env python3
# CH1 베스트컷 썸네일 체인(엔진분) — FX7 베스트 프레임 → FX10 업스케일. LLM 토큰 0.
# 생성형 확장(Gemini·유료)은 파이프라인 층(.github/scripts/framethumb.py) 몫 — fx 기틀 1(토큰 0) 유지.
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import done
from fx_frame import best_frames
from fx_upscale import upscale


def chain(video, outdir, n=1, scale=2):
    if not 1 <= n <= 3:
        raise RuntimeError("CH1 chain: n 1~3만")
    if scale not in (2, 3):
        raise RuntimeError("CH1 chain: scale 2/3만")
    r = best_frames(video, outdir, n=n)
    outs = []
    for fr in r["frames"]:
        up = fr["path"][:-4] + f"_x{scale}.png"
        u = upscale(fr["path"], up, scale=scale)
        outs.append({"t": fr["t"], "src": fr["path"], "up": up,
                     "engine": u["engine"], "size": u["size"]})
    if not outs:
        raise RuntimeError("CH1 chain: 추출 프레임 0")
    return {"module": "CH1", "frames": outs}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CH1 베스트컷 썸네일 체인")
    ap.add_argument("video"); ap.add_argument("outdir")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--scale", type=int, default=2, choices=[2, 3])
    a = ap.parse_args()
    done(chain(a.video, a.outdir, a.n, a.scale))
