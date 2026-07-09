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

# 모델 prefetch → ~/.cache/nomute-track (track-make.yml actions/cache 7일)
#   ⚠ opencv_zoo는 Git LFS: raw.githubusercontent.com은 131바이트 포인터 텍스트를 줌(실측) → 반드시 media.githubusercontent.com.
#   핀 고정 = sha256(파일명 자체가 날짜 버전이라 main 참조 + 해시 검증 = 내용 드리프트 차단 · 실측 260707).
MDIR="${NOMUTE_TRACK_MODELS:-$HOME/.cache/nomute-track}"
mkdir -p "$MDIR"
ZOO="https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
fetch_model() { # $1=URL(https:// 시작) 또는 ZOO 상대경로 $2=저장명 $3=sha256
  local out="$MDIR/$2" url="$1"
  case "$url" in https://*) ;; *) url="$ZOO/$1";; esac
  if [ -f "$out" ] && printf '%s  %s\n' "$3" "$out" | sha256sum -c --status 2>/dev/null; then echo "[setup] $2 ready(캐시)"; return 0; fi
  rm -f "$out"
  timeout 600 curl -fsSL "$url" -o "$out.part" || { sleep 3; timeout 600 curl -fsSL "$url" -o "$out.part"; } || { echo "[setup] ⚠ $2 다운 실패 — 실행 시점 재시도"; rm -f "$out.part"; return 0; }
  if ! printf '%s  %s\n' "$3" "$out.part" | sha256sum -c --status 2>/dev/null; then echo "[setup] ⚠ $2 해시 불일치(LFS 포인터/드리프트?) — 실행 시점 재시도"; rm -f "$out.part"; return 0; fi
  mv "$out.part" "$out"; echo "[setup] $2 ready(다운)"
}

if [ "${TRACK_MODE:-}" = "render" ]; then
  if [ "${TRACK_HEAVY:-}" = "1" ]; then
    # ── 키잉 렌더 전용 헤비 스택 — torch CPU + ultralytics(SAM2 비디오 전파) · 모자이크/핀셋·분석은 이 블록 안 탐 ──
    #   site-packages 캐시 키가 TRACK_HEAVY로 분리(track-make.yml)라 경량 경로 캐시 오염 0.
    python3 - <<'PY' 2>/dev/null || {
import torch, ultralytics, cv2
assert cv2.getBuildInformation()
PY
      timeout 600 pip3 install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu || { sleep 3; timeout 600 pip3 install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu; }
      timeout 600 pip3 install -q ultralytics || { sleep 3; timeout 600 pip3 install -q ultralytics; }
      # ultralytics가 GUI판 opencv-python을 끌고 옴 → headless 최종 재설치로 단일화(이중 설치 = cv2 파손·libGL 의존 함정)
      timeout 300 pip3 uninstall -y -q opencv-python opencv-python-headless 2>/dev/null || true
      timeout 300 pip3 install -q "opencv-python-headless>=4.8"
    }
    # SAM2.1 tiny 공식 체크포인트(Meta CDN · Apache-2.0) — ultralytics 로더가 {"model":…} 포맷 그대로 읽음(실측 260709)
    fetch_model "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt" "sam2.1_t.pt" "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"
    echo "[setup] track env ready (keying — torch+ultralytics+sam2.1_t)"
    exit 0
  fi
  echo "[setup] track env ready (render — 모델 스킵)"   # 모자이크/핀셋 = 모델 불사용(cv2+PIL+ffmpeg만 · 평의회1 L-5)
  exit 0
fi
# analyze — 얼굴 2종(YuNet 232KB + SFace 37MB). 피사체 검출 yolo11n.onnx는 레포 커밋본(apps/track/) = fetch 불필요.
fetch_model "face_detection_yunet/face_detection_yunet_2023mar.onnx" "yunet_2023mar.onnx" "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
fetch_model "face_recognition_sface/face_recognition_sface_2021dec.onnx" "sface_2021dec.onnx" "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"

echo "[setup] track env ready (ffmpeg+opencv+numpy+pillow+yt-dlp+models)"
