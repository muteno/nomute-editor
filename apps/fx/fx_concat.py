#!/usr/bin/env python3
# FX5 이어붙이기(미니 타임라인 엔진) — 클립 N개 → 규격 통일 재인코딩 → 컷/디졸브(xfade) 연결 + 인트로/아웃트로 스팅어.
# 프리미어 시퀀스의 엔진분. 순서·선택 UI는 부착층(클리퍼 후보 다중 선택과 시너지).
import argparse, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import ff, duration, has_audio, probe, done

CAP_CLIPS = 10
CAP_TOTAL_S = 600


def _target_spec(clip, w=None, h=None, fps=None):
    vs = [s for s in probe(clip)["streams"] if s["codec_type"] == "video"][0]
    tw = int(w or vs["width"]); th = int(h or vs["height"])
    return tw - tw % 2, th - th % 2, int(fps or 30)


def _normalize(clip, idx, tmp, w, h, fps):
    # 전 클립 동일 규격(해상도·SAR·fps·48k 스테레오) 중간본 — 무음 클립은 무음 트랙 합성
    o = os.path.join(tmp, f"n{idx:02d}.mp4")
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps},setsar=1,format=yuv420p")
    args = ["-i", clip]
    if has_audio(clip):
        args += ["-vf", vf, "-af", "aresample=48000:async=1", "-ac", "2"]
    else:
        args += ["-f", "lavfi", "-t", f"{duration(clip):.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                 "-map", "0:v", "-map", "1:a", "-vf", vf, "-shortest"]
    ff(args + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-c:a", "aac", "-ar", "48000", "-b:a", "192k", o])
    return o


def concat(clips, out, transition="cut", tdur=0.5, intro=None, outro=None, w=None, h=None, fps=None):
    clips = ([intro] if intro else []) + list(clips) + ([outro] if outro else [])
    if not 2 <= len(clips) <= CAP_CLIPS:
        raise RuntimeError(f"FX5 concat: 클립 2~{CAP_CLIPS}개만")
    total = sum(duration(c) for c in clips)
    if total > CAP_TOTAL_S:
        raise RuntimeError(f"FX5 concat: 합계 {int(total)}s > 캡 {CAP_TOTAL_S}s")
    tw, th, tfps = _target_spec(clips[0], w, h, fps)
    with tempfile.TemporaryDirectory() as tmp:
        norm = [_normalize(c, i, tmp, tw, th, tfps) for i, c in enumerate(clips)]
        if transition == "cut":
            lst = os.path.join(tmp, "list.txt")
            with open(lst, "w") as f:
                f.writelines(f"file '{p}'\n" for p in norm)
            ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
        else:  # dissolve = xfade+acrossfade 체인
            if not 0.2 <= tdur <= 2.0:
                raise RuntimeError("FX5 concat: 디졸브 0.2~2.0s만")
            durs = [duration(p) for p in norm]
            ins = sum((["-i", p] for p in norm), [])
            fc, cum = [], durs[0]
            pv, pa = "[0:v]", "[0:a]"
            for i in range(1, len(norm)):
                off = max(0.0, cum - tdur)
                nv, na = f"[v{i}]", f"[a{i}]"
                fc.append(f"{pv}[{i}:v]xfade=transition=fade:duration={tdur}:offset={off:.3f}{nv}")
                fc.append(f"{pa}[{i}:a]acrossfade=d={tdur}{na}")
                pv, pa, cum = nv, na, cum + durs[i] - tdur
            ff(ins + ["-filter_complex", ";".join(fc), "-map", pv, "-map", pa,
                      "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                      "-c:a", "aac", "-b:a", "192k", out])
    return {"module": "FX5", "out": out, "clips": len(clips), "transition": transition,
            "size": f"{tw}x{th}@{tfps}"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX5 이어붙이기")
    ap.add_argument("clips", nargs="+", help="클립 경로들(순서대로)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--transition", choices=["cut", "dissolve"], default="cut")
    ap.add_argument("--tdur", type=float, default=0.5, help="디졸브 길이 s")
    ap.add_argument("--intro"); ap.add_argument("--outro")
    ap.add_argument("--w", type=int); ap.add_argument("--h", type=int); ap.add_argument("--fps", type=int)
    a = ap.parse_args()
    done(concat(a.clips, a.out, a.transition, a.tdur, a.intro, a.outro, a.w, a.h, a.fps))
