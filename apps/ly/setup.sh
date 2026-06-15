#!/usr/bin/env bash
# 노뮤트 릴스/쇼츠 자막 생성기 — 환경 준비(멱등). STT = 로컬 Whisper(키 불필요).
set -e
# 양쪽 호환: Claude Code(root) / GitHub 러너(non-root → sudo)
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# ffmpeg (오디오 추출 STEP 0-1)
command -v ffmpeg >/dev/null 2>&1 || { $SUDO apt-get update -qq && $SUDO apt-get install -y -qq ffmpeg; }

# Whisper(로컬 STT — 키 불필요) / yt-dlp(영상 URL Case C)
python3 -c "import faster_whisper" 2>/dev/null || pip3 install -q faster-whisper
command -v yt-dlp >/dev/null 2>&1 || pip3 install -q yt-dlp

# 작업 경로 (Claude Code 임시 파일 — 러너선 /tmp 사용하므로 실패해도 무방)
mkdir -p /home/claude 2>/dev/null || true

# large-v3-turbo 모델 prefetch (정확도≈large-v3·1.6GB·4배 빠름)
# 환경 Setup script로 등록하면 이 결과가 스냅샷 캐시 → 매 세션 재다운로드 없음(7일 만료 시만 재빌드).
# 이미 있으면 즉시 통과(멱등). 네트워크 막히면 STT 시점에 재시도.
python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')" 2>/dev/null \
  && echo "[setup] large-v3-turbo ready" || echo "[setup] ⚠ turbo prefetch 실패(네트워크?) — STT 시점 재시도"

echo "[setup] ly env ready (ffmpeg+faster-whisper+yt-dlp+large-v3-turbo+paths)"
