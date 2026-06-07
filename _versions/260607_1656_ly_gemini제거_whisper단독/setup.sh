#!/usr/bin/env bash
# 노뮤트 릴스/쇼츠 자막 생성기 — 환경 준비(멱등). STT 파이프라인용 도구 설치.
set -e

# ffmpeg (오디오 추출 STEP 0-1)
command -v ffmpeg >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq ffmpeg; }

# Whisper(기본 STT — 로컬·키 불필요) / requests(Gemini 폴백 STT) / yt-dlp(영상 URL Case C)
python3 -c "import faster_whisper" 2>/dev/null || pip3 install -q faster-whisper
python3 -c "import requests" 2>/dev/null || pip3 install -q requests
command -v yt-dlp >/dev/null 2>&1 || pip3 install -q yt-dlp

# 작업 경로 (오디오/영상 임시 파일)
mkdir -p /home/claude

# Gemini는 선택적 폴백 — 키 평문 금지(환경변수로만). 미설정이어도 기본 Whisper로 영상 STT 동작.
if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "[setup] ℹ GEMINI_API_KEY 미설정 — 기본 Whisper(로컬·키불필요)로 STT. (Gemini 폴백 쓰려면 export GEMINI_API_KEY=...)"
fi

echo "[setup] ly env ready (ffmpeg+faster-whisper+requests+yt-dlp+paths)"
