#!/usr/bin/env bash
# 노뮤트 썸네일 제작기 — 환경 준비(멱등·2단). nomute_*.py 불변(절대규칙 1).
# ⚡ 환경 Setup script에 `bash apps/thumbnail/setup.sh` 등록 권장(ly Whisper prefetch와 동일 방식):
#    1단(무거운 설치)이 스냅샷 캐시에 들어가 /th 진입이 즉시가 된다(7일 만료 시만 재빌드).
#    미등록 환경도 동작 동일 — 첫 /th 때 설치(기존 폴백). 강제 재설치 = rm ~/.cache/nomute_th_env_ready 후 재실행.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1단: 무거운 설치(apt 폰트 + pip 패키지) — 성공 후 스탬프, 이후 단락 ──
STAMP="$HOME/.cache/nomute_th_env_ready"
if [ ! -f "$STAMP" ]; then
  if ! fc-list 2>/dev/null | grep -qi "noto sans cjk"; then
    apt-get update -qq && apt-get install -y -qq fonts-noto-cjk
  fi
  python3 -c "import PIL,numpy,cv2,mediapipe" 2>/dev/null || \
    pip3 install -q pillow numpy opencv-python-headless mediapipe
  mkdir -p "$HOME/.cache" && touch "$STAMP"
fi

# ── 2단: 가벼운 경로·심볼릭(매 세션 — 레포가 세션마다 새로 풀리므로 항상 재링크) ──
mkdir -p /mnt/project /home/claude /mnt/user-data/outputs /mnt/user-data/uploads
ln -sf "$DIR/nomute_overlay.py"   /mnt/project/nomute_overlay.py
ln -sf "$DIR/nomute_compose.py"   /mnt/project/nomute_compose.py
ln -sf "$DIR/nomute_copyright.py" /mnt/project/nomute_copyright.py
ln -sf "$DIR/nomute_reels2.py"    /mnt/project/nomute_reels2.py
ln -sf "$DIR/assets/reels2_base.png" /mnt/project/reels2_base.png
ln -sf "$DIR/assets/reels2_base.png" /home/claude/reels2_base.png
echo "[setup] thumbnail env ready (fonts+pkgs+paths+reels2)"
