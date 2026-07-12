#!/usr/bin/env python3
# FX2 손떨림 보정 — vidstab 2패스(프리미어 워프 스태빌라이저 대체). libvidstab 없는 빌드는 deshake 폴백(정직 표기).
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import ff, cap_duration, has_filter, done

PRESET = {"basic": (5, 12), "strong": (8, 28)}  # (shakiness, smoothing)
CAP_S = 600


def stabilize(video, out, strength="basic"):
    cap_duration(video, CAP_S, "FX2 stab")
    sh, sm = PRESET.get(strength, PRESET["basic"])
    if has_filter("vidstabdetect") and has_filter("vidstabtransform"):
        trf = out + ".trf"
        try:
            ff(["-i", video, "-vf", f"vidstabdetect=shakiness={sh}:accuracy=15:result={trf}",
                "-f", "null", "-"])
            ff(["-i", video, "-vf",
                f"vidstabtransform=input={trf}:smoothing={sm}:optzoom=2:interpol=bicubic,"
                "unsharp=5:5:0.6:3:3:0.3",
                "-c:a", "copy", out])
        finally:
            if os.path.exists(trf):
                os.remove(trf)
        eng = "vidstab"
    else:
        # 폴백 = 단일패스 deshake(품질 낮음) — 러너에선 ffmpeg(libvidstab 포함) 권장
        ff(["-i", video, "-vf", "deshake=edge=mirror", "-c:a", "copy", out])
        eng = "deshake-fallback"
    return {"module": "FX2", "out": out, "engine": eng, "strength": strength}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX2 손떨림 보정")
    ap.add_argument("video"); ap.add_argument("out")
    ap.add_argument("--strength", choices=list(PRESET), default="basic")
    a = ap.parse_args()
    done(stabilize(a.video, a.out, a.strength))
