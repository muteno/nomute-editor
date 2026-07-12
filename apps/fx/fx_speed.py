#!/usr/bin/env python3
# FX4 배속/슬로모 — setpts+atempo 체인. smooth 슬로모 = minterpolate 프레임 생성(고비용 → 60s 캡 · conv 예산 실측 계승).
# 순수 프레임업(60i)은 편집기 프레임 카드 전담 — 여기선 배속률 변경만.
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import ff, cap_duration, has_audio, done

CAP_S = 600
CAP_SMOOTH_S = 60  # minterpolate 예산 가드(0.30s/출력프레임 실측 계승)


def _atempo_chain(factor):
    parts, f = [], factor
    while f > 2.0:
        parts.append("atempo=2.0"); f /= 2.0
    while f < 0.5:
        parts.append("atempo=0.5"); f /= 0.5
    parts.append(f"atempo={f:.6f}")
    return ",".join(parts)


def speed(video, out, factor, smooth=False, fps=60):
    if not 0.25 <= factor <= 4.0:
        raise RuntimeError("FX4 speed: 배속률 0.25~4.0만")
    if abs(factor - 1.0) < 1e-6:
        raise RuntimeError("FX4 speed: 1.0배는 무의미 — 프레임업은 편집기 프레임 카드(60i) 전담")
    cap = CAP_SMOOTH_S if (smooth and factor < 1.0) else CAP_S
    cap_duration(video, cap, "FX4 speed")
    vf = f"setpts=PTS/{factor:.6f}"
    if smooth and factor < 1.0:
        vf += f",minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1"
    args = ["-i", video]
    if has_audio(video):
        args += ["-filter_complex", f"[0:v]{vf}[v];[0:a]{_atempo_chain(factor)}[a]",
                 "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    else:
        args += ["-vf", vf, "-an"]
    ff(args + [out])
    return {"module": "FX4", "out": out, "factor": factor, "smooth": bool(smooth and factor < 1.0)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX4 배속/슬로모")
    ap.add_argument("video"); ap.add_argument("out")
    ap.add_argument("--factor", type=float, required=True, help=">1 배속 · <1 슬로모")
    ap.add_argument("--smooth", action="store_true", help="슬로모 프레임 생성 보간(60s 캡)")
    ap.add_argument("--fps", type=int, default=60)
    a = ap.parse_args()
    done(speed(a.video, a.out, a.factor, a.smooth, a.fps))
