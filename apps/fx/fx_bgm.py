#!/usr/bin/env python3
# FX1 배경음 넣기 + 자동 더킹 — 음성 구간에서 BGM 자동 감쇠(sidechaincompress) · 프리미어 오디오 트랙 대체
# 음원(리틀 수노 Lyria 곡) → 쇼츠 BGM 연결용. 음량 최종 통일은 shared/audio_norm.py 후처리(여기서 재구현 금지).
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import ff, cap_duration, has_audio, has_video, done

DUCK_RATIO = {"light": 4, "med": 8, "strong": 14}  # 감쇠 세기(압축비)
CAP_S = 600  # 편집기 캡 계승(10분)


def add_bgm(video, music, out, db=-16.0, duck="med", fade=1.5):
    d = cap_duration(video, CAP_S, "FX1 bgm")
    if not has_video(video):
        raise RuntimeError("FX1 bgm: 입력에 영상 스트림 없음")
    st = max(0.0, d - fade)
    bg = f"[1:a]volume={db}dB,afade=t=out:st={st:.3f}:d={fade}[bg]"
    voiced = has_audio(video) and duck != "off"
    if voiced:
        fc = (bg + f";[bg][0:a]sidechaincompress=threshold=0.03:ratio={DUCK_RATIO.get(duck, 8)}"
              f":attack=20:release=400[duckd];"
              f"[0:a][duckd]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
    elif has_audio(video):
        fc = bg + ";[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
    else:
        fc = bg + ";[bg]anull[aout]"
    ff(["-i", video, "-stream_loop", "-1", "-i", music, "-filter_complex", fc,
        "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", out])
    return {"module": "FX1", "out": out, "duck": duck if voiced else "off", "db": db, "dur": round(d, 2)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX1 배경음 넣기+자동 더킹")
    ap.add_argument("video"); ap.add_argument("music"); ap.add_argument("out")
    ap.add_argument("--db", type=float, default=-16.0, help="BGM 음량 dB(기본 -16)")
    ap.add_argument("--duck", choices=["off", "light", "med", "strong"], default="med")
    ap.add_argument("--fade", type=float, default=1.5, help="끝 페이드아웃 초")
    a = ap.parse_args()
    done(add_bgm(a.video, a.music, a.out, a.db, a.duck, a.fade))
