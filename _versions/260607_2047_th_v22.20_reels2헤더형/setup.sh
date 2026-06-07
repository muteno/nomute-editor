#!/usr/bin/env bash
# 노뮤트 썸네일 제작기 — 환경 준비(멱등). nomute_*.py 불변(절대규칙 1).
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! fc-list 2>/dev/null | grep -qi "noto sans cjk"; then
  apt-get update -qq && apt-get install -y -qq fonts-noto-cjk
fi
python3 -c "import PIL,numpy,cv2,mediapipe" 2>/dev/null || \
  pip3 install -q pillow numpy opencv-python-headless mediapipe
mkdir -p /mnt/project /home/claude /mnt/user-data/outputs /mnt/user-data/uploads
ln -sf "$DIR/nomute_overlay.py"   /mnt/project/nomute_overlay.py
ln -sf "$DIR/nomute_compose.py"   /mnt/project/nomute_compose.py
ln -sf "$DIR/nomute_copyright.py" /mnt/project/nomute_copyright.py
echo "[setup] thumbnail env ready (fonts+pkgs+paths)"
