#!/usr/bin/env bash
# 인스타 수집 폰 진단 진입점(운영자 260731) — 쿠키가 든 ~/.nomute_phone_env를 source한 뒤 진단을 돌린다.
# 왜 래퍼가 필요하냐 = 쿠키는 git 밖 로컬 env 파일에 있고, python을 직접 돌리면 그 파일을 안 읽어
#   **멀쩡히 쿠키가 있는데도 "게스트"로 진단**돼 오진한다(phone_subs.sh와 같은 축 · 그쪽이 정본).
# 사용:  bash scripts/insta_check.sh [계정]
set -e
cd "$(dirname "$0")/.."
# 보안 가드 = phone_subs.sh 정본 그대로(600 강제 후 source · 쿠키 평문 집결 파일)
[ -f "$HOME/.nomute_phone_env" ] && { [ "$(stat -c %a "$HOME/.nomute_phone_env" 2>/dev/null || stat -f %A "$HOME/.nomute_phone_env" 2>/dev/null)" = 600 ] || chmod 600 "$HOME/.nomute_phone_env"; . "$HOME/.nomute_phone_env"; }
exec python3 scripts/insta_check.py "$@"
