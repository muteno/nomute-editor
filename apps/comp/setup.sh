#!/usr/bin/env bash
# 노뮤트 카드뉴스 합성기 — 환경 준비(멱등). card_news.py 불변(절대규칙: import/호출만).
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 폰트 (Noto Sans CJK) — 지침이 /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc 를 기대
if ! fc-list 2>/dev/null | grep -qi "noto sans cjk"; then
  apt-get update -qq && apt-get install -y -qq fonts-noto-cjk
fi

# 합성 의존성
python3 -c "import PIL,numpy,cv2,mediapipe" 2>/dev/null || \
  pip3 install -q pillow numpy opencv-python-headless mediapipe

# 표준 경로 — 지침의 bash/Path 가 그대로 동작하도록 심볼릭
mkdir -p /mnt/project /home/claude /mnt/user-data/outputs /mnt/user-data/uploads
ln -sf "$DIR/card_news.py" /mnt/project/card_news.py
ln -sf "$DIR/card_news.py" /home/claude/card_news.py

echo "[setup] comp env ready (fonts+pkgs+paths)"
