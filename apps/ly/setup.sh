#!/usr/bin/env bash
# 노뮤트 릴스/쇼츠 자막 생성기 — 환경 준비(멱등). STT = 로컬 Whisper(키 불필요).
set -e
# 양쪽 호환: Claude Code(root) / GitHub 러너(non-root → sudo)
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# ffmpeg (오디오 추출 STEP 0-1) — 러너선 runner-setup이 .deb 캐시로 선설치(보통 스킵). 아래는 타임아웃 폴백(미러 스톨 무한행 차단).
if ! command -v ffmpeg >/dev/null 2>&1; then
  timeout 150 $SUDO apt-get update -qq || true
  timeout 300 $SUDO apt-get install -y -qq ffmpeg || { sleep 3; timeout 300 $SUDO apt-get install -y -qq ffmpeg; }
fi

# Whisper(로컬 STT — 키 불필요) / yt-dlp(영상 URL Case C)
python3 -c "import faster_whisper" 2>/dev/null || timeout 300 pip3 install -q faster-whisper
command -v yt-dlp >/dev/null 2>&1 || timeout 180 pip3 install -q yt-dlp

# 작업 경로 (Claude Code 임시 파일 — 러너선 /tmp 사용하므로 실패해도 무방)
mkdir -p /home/claude 2>/dev/null || true

# large-v3 모델 prefetch (최고 정확도·3.1GB — 운영자 260726 turbo→large-v3 승격: 소음·현장음 클립 발화 누락·오인식 봉합)
# 환경 Setup script로 등록하면 이 결과가 스냅샷 캐시 → 매 세션 재다운로드 없음(7일 만료 시만 재빌드).
# 이미 있으면 즉시 통과(멱등). 네트워크 막히면 STT 시점에 재시도.
# ⚡ 260728 Q999 — 구본은 캐시가 적중해도 매 런 **모델을 메모리에 통째 로드**했다(실측 ~34s 순수 낭비 · 곧이어 ly_stt.py가 또 로드).
#    prefetch의 목적은 '파일 확보'뿐이므로 파일이 있으면 로드 없이 통과한다. **품질 무손실** — 모델·정밀도·추론 설정 무접촉이고
#    실제 전사는 종전대로 ly_stt.py가 담당한다(여기서 compute_type을 무엇으로 로드했는지는 전사 결과에 영향 0 = 같은 가중치 파일).
HF="${HF_HOME:-${HOME}/.cache/huggingface}"
if ls "$HF"/hub/models--Systran--faster-whisper-large-v3/snapshots/*/model.bin >/dev/null 2>&1; then
  echo "[setup] large-v3 캐시 적중 — prefetch 로드 생략(~34s 절감 · 파일 존재만 확인)"
else
  python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu', compute_type='int8')" 2>/dev/null \
    && echo "[setup] large-v3 ready(신규 다운로드)" || echo "[setup] ⚠ large-v3 prefetch 실패(네트워크?) — STT 시점 재시도"
fi

echo "[setup] ly env ready (ffmpeg+faster-whisper+yt-dlp+large-v3+paths)"
