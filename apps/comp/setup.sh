#!/usr/bin/env bash
# 노뮤트 카드뉴스 합성기 — 환경 준비(멱등). card_news.py 불변(절대규칙: import/호출만).
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 양쪽 호환: Claude Code(root) / GitHub 러너(non-root → sudo)
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# 폰트 (Noto Sans CJK) — 지침이 /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc 를 기대.
# (러너선 runner-setup이 apt .deb 캐시로 선설치 → 보통 여기서 스킵. 아래는 타임아웃 폴백 — 미러 스톨 무한행 차단.)
if ! fc-list 2>/dev/null | grep -qi "noto sans cjk"; then
  timeout 150 $SUDO apt-get update -qq || true
  timeout 240 $SUDO apt-get install -y -qq fonts-noto-cjk \
    || { sleep 3; timeout 240 $SUDO apt-get install -y -qq fonts-noto-cjk; }
fi

# 합성 의존성
python3 -c "import PIL,numpy,cv2,mediapipe" 2>/dev/null \
  || timeout 300 pip3 install -q pillow numpy opencv-python-headless mediapipe \
  || { sleep 3; timeout 300 pip3 install -q pillow numpy opencv-python-headless mediapipe; }

# 표준 경로 심볼릭 — Claude Code용. 러너(/mnt 권한 없음)선 자동 스킵.
if mkdir -p /mnt/project /home/claude /mnt/user-data/outputs /mnt/user-data/uploads 2>/dev/null; then
  ln -sf "$DIR/card_news.py" /mnt/project/card_news.py
  ln -sf "$DIR/card_news.py" /home/claude/card_news.py
fi

echo "[setup] comp env ready (fonts+pkgs+paths)"
