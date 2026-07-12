#!/usr/bin/env bash
# 노뮤트 편집(피사체 모자이크) — 환경 준비(멱등). 검출·모자이크 = 로컬(키·LLM 불필요 = 토큰 0).
#   경량(검출·박스 모자이크) = opencv + numpy + pillow + YuNet 모델(YOLO11n은 apps/track 레포 커밋본 재사용).
#   정밀(IMG_HEAVY=1 = SAM2 실루엣) = torch CPU + ultralytics + SAM2.1 tiny(track 키잉과 동일 스택·캐시 키 분리).
# 골격 = apps/track/setup.sh 미러(영상 전용 ffmpeg/yt-dlp는 이미지엔 불요라 제외).
set -e
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# opencv(YuNet 검출 내장 ≥4.8) / numpy / pillow(EXIF 회전·인코딩)
python3 - <<'PY' 2>/dev/null || timeout 300 pip3 install -q "opencv-python-headless>=4.8" numpy pillow
import cv2
assert hasattr(cv2, "FaceDetectorYN")
import numpy, PIL
PY

# 모델 = track과 공유 캐시(~/.cache/nomute-track) — YuNet 232KB(검출). SFace는 단일 이미지엔 미사용(load_models가 없으면 rec=None).
#   ⚠ opencv_zoo = Git LFS → 반드시 media.githubusercontent.com(raw는 131바이트 포인터 함정) · sha256 핀.
MDIR="${NOMUTE_TRACK_MODELS:-$HOME/.cache/nomute-track}"
mkdir -p "$MDIR"
ZOO="https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
fetch_model() { # $1=URL 또는 ZOO 상대 $2=저장명 $3=sha256
  local out="$MDIR/$2" url="$1"
  case "$url" in https://*) ;; *) url="$ZOO/$1";; esac
  if [ -f "$out" ] && printf '%s  %s\n' "$3" "$out" | sha256sum -c --status 2>/dev/null; then echo "[setup] $2 ready(캐시)"; return 0; fi
  rm -f "$out"
  timeout 600 curl -fsSL "$url" -o "$out.part" || { sleep 3; timeout 600 curl -fsSL "$url" -o "$out.part"; } || { echo "[setup] ⚠ $2 다운 실패 — 실행 시점 재시도"; rm -f "$out.part"; return 0; }
  if ! printf '%s  %s\n' "$3" "$out.part" | sha256sum -c --status 2>/dev/null; then echo "[setup] ⚠ $2 해시 불일치 — 실행 시점 재시도"; rm -f "$out.part"; return 0; fi
  mv "$out.part" "$out"; echo "[setup] $2 ready(다운)"
}

if [ "${IMG_HEAVY:-}" = "1" ]; then
  # ── 정밀(SAM2 실루엣) 전용 헤비 스택 — track 키잉과 동일(torch CPU + ultralytics + SAM2.1 tiny) ──
  python3 - <<'PY' 2>/dev/null || {
import torch, ultralytics, cv2
assert cv2.getBuildInformation()
PY
    timeout 600 pip3 install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu || { sleep 3; timeout 600 pip3 install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu; }
    timeout 600 pip3 install -q ultralytics || { sleep 3; timeout 600 pip3 install -q ultralytics; }
    # ultralytics가 GUI판 opencv-python을 끌고 옴 → headless 재설치로 단일화(libGL 함정 차단 · track 동일)
    timeout 300 pip3 uninstall -y -q opencv-python opencv-python-headless 2>/dev/null || true
    timeout 300 pip3 install -q "opencv-python-headless>=4.8"
  }
  fetch_model "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt" "sam2.1_t.pt" "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"
fi

# YuNet(검출) — 경량·정밀 공통 필요
fetch_model "face_detection_yunet/face_detection_yunet_2023mar.onnx" "yunet_2023mar.onnx" "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"

echo "[setup] imgedit env ready (opencv+numpy+pillow+YuNet${IMG_HEAVY:+ +torch+sam2.1_t})"
