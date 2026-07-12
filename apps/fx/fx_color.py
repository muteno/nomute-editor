#!/usr/bin/env python3
# FX3 색보정 프리셋/LUT — 프리미어 루메트리 프리셋 대체. 닫힌 프리셋 집합(임의 색 창작 아님 · 산출물 색 축).
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import ff, cap_duration, done

PRESETS = {
    "news":      "eq=contrast=1.07:saturation=1.10:brightness=0.008,unsharp=3:3:0.5:3:3:0.0",
    "cinematic": "curves=r='0/0.02 0.5/0.52 1/0.98':b='0/0.05 0.5/0.47 1/0.93',eq=contrast=1.09:saturation=0.92",
    "bright":    "eq=brightness=0.055:contrast=1.04:saturation=1.06",
    "warm":      "colortemperature=temperature=5100,eq=saturation=1.04",
    "cool":      "colortemperature=temperature=8600",
    "vivid":     "vibrance=intensity=0.35,eq=contrast=1.05",
    "bw":        "hue=s=0,eq=contrast=1.12",
}
CAP_S = 600


def grade(video, out, preset=None, lut=None):
    cap_duration(video, CAP_S, "FX3 color")
    if lut:
        if not os.path.exists(lut):
            raise RuntimeError(f"FX3 color: LUT 파일 없음({lut})")
        vf = f"lut3d='{lut}'"
        tag = f"lut:{os.path.basename(lut)}"
    else:
        if preset not in PRESETS:
            raise RuntimeError(f"FX3 color: 프리셋 없음({preset}) — {', '.join(PRESETS)}")
        vf, tag = PRESETS[preset], preset
    ff(["-i", video, "-vf", vf, "-c:a", "copy", out])
    return {"module": "FX3", "out": out, "preset": tag}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX3 색보정")
    ap.add_argument("video"); ap.add_argument("out")
    ap.add_argument("--preset", default="news", help=", ".join(PRESETS))
    ap.add_argument("--lut", help=".cube LUT 경로(지정 시 preset 무시)")
    a = ap.parse_args()
    done(grade(a.video, a.out, a.preset, a.lut))
