#!/usr/bin/env python3
# FX 모듈뱅크 공통 러너 — UI 무의존 · LLM 토큰 0(ffmpeg/OpenCV) · 부착층(워크플로/뷰어)이 발사·알림·R2 담당
# 실패 계약: 예외 → rc≠0 + stderr 마지막 줄이 사유 한 줄(부착층 fail-soft 소비용). 산출은 성공 시에만 존재.
import json, os, shlex, subprocess, sys

FFMPEG = os.environ.get("FX_FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FX_FFPROBE", "ffprobe")
DEF_TIMEOUT = int(os.environ.get("FX_TIMEOUT", "1500"))  # 편집기 CARD_TIMEOUT 계승 — 무한 행 방지(§9-1)


def run(cmd, timeout=DEF_TIMEOUT):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-6:]
        raise RuntimeError(f"{os.path.basename(cmd[0])} rc={p.returncode}: " + " | ".join(tail))
    return p


def ff(args, timeout=DEF_TIMEOUT):
    return run([FFMPEG, "-hide_banner", "-y"] + args, timeout)


def probe(path):
    p = run([FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path], 120)
    return json.loads(p.stdout)


def duration(path):
    try:
        return float(probe(path)["format"]["duration"])
    except Exception:
        return 0.0


def streams(path, kind):
    return [s for s in probe(path).get("streams", []) if s.get("codec_type") == kind]


def has_audio(path):
    return bool(streams(path, "audio"))


def has_video(path):
    return bool(streams(path, "video"))


def has_filter(name):
    try:
        p = run([FFMPEG, "-hide_banner", "-filters"], 60)
        return any(line.split()[1:2] == [name] for line in p.stdout.splitlines() if line.strip())
    except Exception:
        return False


def cap_duration(path, cap_s, label):
    d = duration(path)
    if d <= 0:
        raise RuntimeError(f"{label}: 길이를 못 읽음({path})")
    if d > cap_s:
        raise RuntimeError(f"{label}: {int(d)}s > 캡 {cap_s}s — 구간을 잘라 다시(정직 거절)")
    return d


def done(payload):
    # 성공 계약: stdout 마지막 줄 = JSON 1줄(부착층 파싱용)
    print(json.dumps(payload, ensure_ascii=False))
