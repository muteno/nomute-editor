#!/usr/bin/env bash
# 노뮤트 인물 트래킹(핀셋·모자이크) — 환경 준비(멱등). 검출·군집 = 로컬 OpenCV ONNX(키·LLM 불필요 = 토큰 0).
set -e
# 양쪽 호환: Claude Code(root) / GitHub 러너(non-root → sudo)
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# ffmpeg (렌더 인코딩·오디오 먹싱) — 러너선 runner-setup .deb 캐시가 선설치(보통 스킵). 아래는 타임아웃 폴백.
if ! command -v ffmpeg >/dev/null 2>&1; then
  timeout 150 $SUDO apt-get update -qq || true
  timeout 300 $SUDO apt-get install -y -qq ffmpeg || { sleep 3; timeout 300 $SUDO apt-get install -y -qq ffmpeg; }
fi

# opencv(YuNet 검출 + SFace 임베딩 내장 ≥4.8) / numpy / pillow(핀셋 한글 라벨) / yt-dlp(영상 URL)
python3 - <<'PY' 2>/dev/null || timeout 300 pip3 install -q "opencv-python-headless>=4.8" numpy pillow
import cv2
assert hasattr(cv2, "FaceDetectorYN") and hasattr(cv2, "FaceRecognizerSF")
import numpy, PIL
PY
command -v yt-dlp >/dev/null 2>&1 || timeout 180 pip3 install -q yt-dlp

# 모델 2종 prefetch — YuNet 얼굴검출 232KB + SFace 얼굴임베딩 37MB → ~/.cache/nomute-track (track-make.yml actions/cache 7일)
#   ⚠ opencv_zoo는 Git LFS: raw.githubusercontent.com은 131바이트 포인터 텍스트를 줌(실측) → 반드시 media.githubusercontent.com.
#   핀 고정 = sha256(파일명 자체가 날짜 버전이라 main 참조 + 해시 검증 = 내용 드리프트 차단 · 실측 260707).
MDIR="${NOMUTE_TRACK_MODELS:-$HOME/.cache/nomute-track}"
mkdir -p "$MDIR"
ZOO="https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
fetch_model() { # $1=상대경로 $2=저장명 $3=sha256
  local out="$MDIR/$2"
  if [ -f "$out" ] && printf '%s  %s\n' "$3" "$out" | sha256sum -c --status 2>/dev/null; then echo "[setup] $2 ready(캐시)"; return 0; fi
  rm -f "$out"
  timeout 300 curl -fsSL "$ZOO/$1" -o "$out.part" || { sleep 3; timeout 300 curl -fsSL "$ZOO/$1" -o "$out.part"; } || { echo "[setup] ⚠ $2 다운 실패 — 분석 시점 재시도"; rm -f "$out.part"; return 0; }
  if ! printf '%s  %s\n' "$3" "$out.part" | sha256sum -c --status 2>/dev/null; then echo "[setup] ⚠ $2 해시 불일치(LFS 포인터/드리프트?) — 분석 시점 재시도"; rm -f "$out.part"; return 0; fi
  mv "$out.part" "$out"; echo "[setup] $2 ready(다운)"
}
fetch_model "face_detection_yunet/face_detection_yunet_2023mar.onnx" "yunet_2023mar.onnx" "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
fetch_model "face_recognition_sface/face_recognition_sface_2021dec.onnx" "sface_2021dec.onnx" "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"

echo "[setup] track env ready (ffmpeg+opencv+numpy+pillow+yt-dlp+models)"
