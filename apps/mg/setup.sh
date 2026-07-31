#!/usr/bin/env bash
# 모션그래픽 렌더러 — 환경 준비(멱등). .github/scripts/mg_render.py 무수정(절대규칙: 호출만).
#   필요한 것 = Chromium(헤드리스 프레임 캡처) + ffmpeg(인코딩) + CJK 폰트(한글 자막).
#   골격 = apps/comp/setup.sh 미러(양쪽 호환 sudo · 타임아웃 폴백 · 멱등 체크).
set -e
# 양쪽 호환: Claude Code(root) / GitHub 러너(non-root → sudo)
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# 폰트(Noto Sans CJK) + ffmpeg — 러너선 runner-setup이 apt .deb 캐시로 선설치 → 보통 스킵.
# (아래는 타임아웃 폴백 — 미러 스톨 무한행 차단 = comp/setup.sh 동일 패턴)
NEED_APT=""
fc-list 2>/dev/null | grep -qi "noto sans cjk" || NEED_APT="$NEED_APT fonts-noto-cjk"
command -v ffmpeg >/dev/null 2>&1 || NEED_APT="$NEED_APT ffmpeg"
if [ -n "$NEED_APT" ]; then
  timeout 150 $SUDO apt-get update -qq || true
  timeout 300 $SUDO apt-get install -y -qq $NEED_APT \
    || { sleep 3; timeout 300 $SUDO apt-get install -y -qq $NEED_APT; }
fi

# Playwright(파이썬 바인딩) + edge-tts(나레이션 · API 키 불필요·무료)
python3 -c "import playwright" 2>/dev/null \
  || timeout 300 pip3 install -q playwright \
  || { sleep 3; timeout 300 pip3 install -q playwright; }
python3 -c "import edge_tts" 2>/dev/null \
  || timeout 300 pip3 install -q edge-tts \
  || { sleep 3; timeout 300 pip3 install -q edge-tts; }

# Chromium 본체 — 이미 있는 브라우저를 재다운로드하지 않는다.
#   ① 이 환경(Claude Code)엔 /opt/pw-browsers에 선설치 = PLAYWRIGHT_BROWSERS_PATH가 잡아준다(다운로드 금지 계약).
#   ② 러너엔 없으니 1회 설치(~/.cache/ms-playwright · 워크플로가 actions/cache로 보존).
if [ -x "${MG_CHROMIUM:-}" ]; then
  echo "[setup] chromium = \$MG_CHROMIUM($MG_CHROMIUM) 사용 — 설치 생략"
elif [ -d "${PLAYWRIGHT_BROWSERS_PATH:-/nonexistent}" ] && ls "${PLAYWRIGHT_BROWSERS_PATH}"/chromium* >/dev/null 2>&1; then
  echo "[setup] chromium = $PLAYWRIGHT_BROWSERS_PATH 선설치본 사용 — 설치 생략"
else
  timeout 420 python3 -m playwright install chromium \
    || { sleep 3; timeout 420 python3 -m playwright install chromium; }
  # 러너 공유 라이브러리(libnss3 등) — 컨테이너/최소 이미지에서만 필요, 실패해도 위 chromium이 대개 뜬다.
  timeout 300 python3 -m playwright install-deps chromium 2>/dev/null || true
fi

echo "[setup] mg env ready (chromium+ffmpeg+fonts)"
