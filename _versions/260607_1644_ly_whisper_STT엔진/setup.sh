#!/usr/bin/env bash
# 노뮤트 릴스/쇼츠 자막 생성기 — 환경 준비(멱등). STT 파이프라인용 도구 설치.
set -e

# ffmpeg (오디오 추출 STEP 0-1)
command -v ffmpeg >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq ffmpeg; }

# requests (Gemini STT 호출) / yt-dlp (영상 URL 입력 Case C)
python3 -c "import requests" 2>/dev/null || pip3 install -q requests
command -v yt-dlp >/dev/null 2>&1 || pip3 install -q yt-dlp

# 작업 경로 (오디오/영상 임시 파일)
mkdir -p /home/claude

# Gemini 키는 평문 금지 — 환경변수로만 주입
if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "[setup] ⚠ GEMINI_API_KEY 환경변수 미설정 — STT(영상 입력) 쓰려면 export GEMINI_API_KEY=... 필요 (SRT/STT 텍스트 입력은 키 없이 동작)"
fi

echo "[setup] ly env ready (ffmpeg+requests+yt-dlp+paths)"
