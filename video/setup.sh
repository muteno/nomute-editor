#!/usr/bin/env bash
# 큐영상(video) 환경 — hyperframes CLI + 렌더용 크롬. 멱등(재실행 안전 · conv/setup.sh 문법 계승).
# ffmpeg = runner-setup apt 캐시가 선설치(§9 네트워크 op = timeout+1회 재시도).
set -e
cd "$(dirname "$0")"

command -v node >/dev/null || { echo "node 없음 — setup-node 스텝 확인"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg 없음 — runner-setup apt 입력 확인"; exit 1; }

if [ ! -x node_modules/.bin/hyperframes ]; then
  if [ -f package-lock.json ]; then
    timeout 420 npm ci --no-audit --no-fund || { sleep 3; timeout 420 npm ci --no-audit --no-fund; }
  else
    timeout 420 npm install --no-audit --no-fund || { sleep 3; timeout 420 npm install --no-audit --no-fund; }
  fi
fi
node_modules/.bin/hyperframes --version >/dev/null   # 콘솔 스크립트 실호출 검증(캐시 적중 러너 함정 = conv setup.sh 선례)

# 렌더용 크롬 — 이미 있는 것(러너 기본 google-chrome 등)이 잡히면 스킵, 없으면 headless shell 내려받기.
# shellcheck source=/dev/null
. ./env.sh
if [ -z "${PRODUCER_HEADLESS_SHELL_PATH:-}" ]; then
  timeout 300 node_modules/.bin/hyperframes browser ensure || { sleep 3; timeout 300 node_modules/.bin/hyperframes browser ensure; }
fi

echo "video setup 완료 (chrome=${PRODUCER_HEADLESS_SHELL_PATH:-hyperframes 관리})"
