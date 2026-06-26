#!/usr/bin/env bash
# claude_transient.sh — is_transient(): claude -p 출력/에러가 '서버측 일시 과부하(5xx·Overloaded·게이트웨이)'인지 판정.
# analyze.sh·ask.sh·cardmake.sh 공용 단일 출처(SSOT) = 재시도 판정 정규식이 셋으로 갈라지는 드리프트 차단(260622).
#
# ⚠️ 좁게 잡음 = 오직 서버 과부하(공짜·일시)만. 429/쿼터/인증은 제외(재시도해도 그대로라 격리·프로필 점등이 맞음).
#   ANALYSIS_FAILED(입력 막다른길)·정상출력도 여기 안 걸림(호출부에서 따로 즉시 탈출).
#   ① 5xx 전체(502 Bad Gateway·504 Gateway Timeout·520 등 게이트웨이 포함 — Anthropic 앞단 일시장애) 커버.
#   ② 출력 '앞부분(8줄)'만 검사 = CLI 에러는 맨 앞 줄 → 기사 본문 산문의 '503호'·'Service Unavailable' 인용 오탐 억제.
is_transient() {
  local s; s="$(printf '%s\n' "${1:-}" | head -n 8)"
  grep -qiE 'API Error: 5[0-9][0-9]|overloaded_error|Overloaded|"status": ?5[0-9][0-9]|Service (Unavailable|Temporarily Unavailable)|Bad Gateway|Gateway Time-?out' <<<"$s"
}

# is_quota(): claude -p 출력/에러가 '계정 사용량 한도(쿼터·레이트리밋·429)'인지 — *다른 계정으로 전환* 트리거.
#   인증죽음(401/oauth만료)·5xx 과부하와 구분(그건 전환해도 무의미·is_transient/health 담당). 앞 8줄만 검사(본문 인용 오탐 억제).
is_quota() {
  local s; s="$(printf '%s\n' "${1:-}" | head -n 8)"
  grep -qiE 'usage limit|rate.?limit|rate_limit|429|too many requests|quota|limit reached|resets? (at|in)' <<<"$s"
}

# claude_failover(): 출력이 쿼터 한도면 *대체 계정 토큰*(CLAUDE_CODE_OAUTH_TOKEN_ALT)으로 1회 전환.
#   전환함=0(호출부가 같은 프롬프트로 재시도) / 못 함(쿼터 아님·ALT 없음·이미 전환)=1.
#   2계정 한 쌍이라 1회 스왑이면 충분(둘 다 한도면 더 못 피함 → 기존 격리/대기로).
claude_failover() {
  is_quota "${1:-}" || return 1
  [ -n "${CLAUDE_CODE_OAUTH_TOKEN_ALT:-}" ] || return 1
  [ "${_CLAUDE_SWAPPED:-0}" = "1" ] && return 1
  export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_ALT"; _CLAUDE_SWAPPED=1
  echo "  🔄 계정 사용량 한도 감지 — 대체 계정 토큰으로 전환 후 재시도(account failover)"
  return 0
}
