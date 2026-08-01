#!/usr/bin/env bash
# video/env.sh — 렌더 환경 변수(source 해서 쓴다: `source video/env.sh`)
# 목적: 텔레메트리 차단 + 이미 깔린 크로미움 재사용(중복 다운로드 방지).

# 텔레메트리 opt-out(hyperframes CLI 기본 on → 차단).
export HYPERFRAMES_NO_TELEMETRY=1
export DO_NOT_TRACK=1

# 렌더용 크롬. 이미 있는 headless shell / chromium을 우선 재사용하고,
# 없으면 비워둔 채로 `npx hyperframes browser ensure`가 받도록 둔다.
if [ -z "${PRODUCER_HEADLESS_SHELL_PATH:-}" ]; then
  for _cand in \
    /opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell \
    /opt/pw-browsers/chromium-*/chrome-linux/chrome \
    /usr/bin/chromium /usr/bin/chromium-browser /usr/bin/google-chrome
  do
    if [ -x "$_cand" ]; then export PRODUCER_HEADLESS_SHELL_PATH="$_cand"; break; fi
  done
  unset _cand
fi
