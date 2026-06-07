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

# large-v3 모델 prefetch (제일 정확한 모델 미리 받기 — ~3GB. 컨테이너 휘발이라 매 세션 재다운로드)
# 이미 캐시에 있으면 즉시 통과(멱등). 네트워크 막히면 STT 시점에 재시도.
python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu', compute_type='int8')" 2>/dev/null \
  && echo "[setup] large-v3 ready" || echo "[setup] ⚠ large-v3 prefetch 실패(네트워크?) — STT 시점 재시도"

echo "[setup] ly env ready (ffmpeg+faster-whisper+yt-dlp+large-v3+paths)"
