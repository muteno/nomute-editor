#!/usr/bin/env bash
# 노뮤트 릴스/쇼츠 자막 생성기 — 환경 준비(멱등). STT = 로컬 Whisper(키 불필요).
set -e

# ffmpeg (오디오 추출 STEP 0-1)
command -v ffmpeg >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq ffmpeg; }

# Whisper(로컬 STT — 키 불필요) / yt-dlp(영상 URL Case C)
python3 -c "import faster_whisper" 2>/dev/null || pip3 install -q faster-whisper
command -v yt-dlp >/dev/null 2>&1 || pip3 install -q yt-dlp

# 작업 경로 (오디오/영상 임시 파일)
mkdir -p /home/claude

echo "[setup] ly env ready (ffmpeg+faster-whisper+yt-dlp+paths)"
