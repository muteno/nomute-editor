#!/usr/bin/env python3
# FX6 오디오 클린업 — 노이즈 제거(afftdn)+저역 컷+디에서(프리미어 에센셜 사운드 대체).
# 음량(loudnorm)은 shared/audio_norm.py SSOT 후처리 전담 — 여기서 재구현 절대 금지(§10-1-m).
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import ff, cap_duration, has_video, done

NR = {"light": 8, "med": 12, "strong": 20}  # afftdn 감쇠 dB
CAP_S = 600


def clean(inp, out, level="med", highpass=True, deess=False):
    cap_duration(inp, CAP_S, "FX6 audiofix")
    af = []
    if highpass:
        af.append("highpass=f=80")
    af.append(f"afftdn=nr={NR.get(level, 12)}")
    if deess:
        af.append("deesser=i=0.3")
    args = ["-i", inp, "-af", ",".join(af)]
    if has_video(inp):
        args += ["-c:v", "copy"]
    ff(args + ["-c:a", "aac", "-b:a", "192k", out])
    return {"module": "FX6", "out": out, "level": level, "deess": deess}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX6 오디오 클린업")
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--level", choices=list(NR), default="med")
    ap.add_argument("--no-highpass", action="store_true")
    ap.add_argument("--deess", action="store_true")
    a = ap.parse_args()
    done(clean(a.inp, a.out, a.level, not a.no_highpass, a.deess))
