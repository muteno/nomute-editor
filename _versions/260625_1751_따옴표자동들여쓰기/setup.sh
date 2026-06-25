#!/usr/bin/env bash
# 노뮤트 썸네일 제작기 — 환경 준비(멱등·2단). nomute_*.py 불변(절대규칙 1).
# ⚡ 환경 Setup script에 `bash apps/thumbnail/setup.sh` 등록 권장(ly Whisper prefetch와 동일 방식):
#    1단(무거운 설치)이 스냅샷 캐시에 들어가 /th 진입이 즉시가 된다(7일 만료 시만 재빌드).
#    미등록 환경도 동작 동일 — 첫 /th 때 설치(기존 폴백). 강제 재설치 = rm ~/.cache/nomute_th_env_ready 후 재실행.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 양쪽 호환: Claude Code(root) / GitHub 러너(non-root → sudo)
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# ── 1단: 무거운 설치(apt 폰트 + pip 패키지) — 성공 후 스탬프, 이후 단락 ──
STAMP="$HOME/.cache/nomute_th_env_ready"
if [ ! -f "$STAMP" ]; then
  if ! fc-list 2>/dev/null | grep -qi "noto sans cjk"; then
    # ⚠️ apt/pip 무한 행 차단 — 간헐 미러/네트워크 스톨 시 timeout 없으면 20분 잡 한도까지 행 → cancel(="되다 안되다"의 근인 · 실측 260618).
    #    timeout으로 빠른 실패 + 1회 재시도. set -e라 최종 실패 시 즉시 종료(클라가 3분 실패 표시 → 재시도하면 보통 성공).
    timeout 150 $SUDO apt-get update -qq || timeout 150 $SUDO apt-get update -qq || true
    timeout 240 $SUDO apt-get install -y -qq fonts-noto-cjk \
      || { sleep 3; timeout 240 $SUDO apt-get install -y -qq fonts-noto-cjk; }
  fi
  python3 -c "import PIL,numpy,cv2,mediapipe" 2>/dev/null \
    || timeout 300 pip3 install -q pillow numpy opencv-python-headless mediapipe \
    || { sleep 3; timeout 300 pip3 install -q pillow numpy opencv-python-headless mediapipe; }
  mkdir -p "$HOME/.cache" && touch "$STAMP"
fi

# ── 2단: 가벼운 경로·심볼릭(Claude Code용 — 러너[/mnt 권한 없음]선 자동 스킵) ──
if mkdir -p /mnt/project /home/claude /mnt/user-data/outputs /mnt/user-data/uploads 2>/dev/null; then
  ln -sf "$DIR/nomute_overlay.py"   /mnt/project/nomute_overlay.py
  ln -sf "$DIR/nomute_compose.py"   /mnt/project/nomute_compose.py
  ln -sf "$DIR/nomute_copyright.py" /mnt/project/nomute_copyright.py
  ln -sf "$DIR/nomute_reels2.py"    /mnt/project/nomute_reels2.py
  ln -sf "$DIR/assets/reels2_base.png" /mnt/project/reels2_base.png
  ln -sf "$DIR/assets/reels2_base.png" /home/claude/reels2_base.png
  ln -sf "$DIR/../../shared/attach.py" /mnt/project/attach.py   # BG 첨부 해석(라우터 §미디어 첨부)
fi
echo "[setup] thumbnail env ready (fonts+pkgs+paths+reels2+attach)"
