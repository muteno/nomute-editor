#!/usr/bin/env bash
# claude -p 실패가 '시스템성'(인증·쿼터/레이트리밋)인지 분류 — 단발 콘텐츠 실패(ANALYSIS_FAILED·타임아웃)와 구분.
# 시스템성이면 사용자에게 '작동할 때까지' 알릴 가치가 있음(전 분석이 다 막힘). 콘텐츠 실패는 그 건만의 문제라 알림 X.
#
# claude_systemic_reason <stderr_file>
#   → 시스템성이면 한국어 사유를 stdout 으로 echo + return 0, 아니면 return 1.
# (소문자화한 stderr 에 대해 case 글로브 매칭 — regex 이스케이프 회피.)
claude_systemic_reason() {
  local s
  s="$(cat "${1:-/dev/null}" 2>/dev/null | tr 'A-Z' 'a-z')"
  case "$s" in
    *"invalid x-api-key"*|*"authentication_error"*|*"oauth"*|*"unauthorized"*|*"please run /login"*|*"invalid api key"*|*"401"*|*"403"*|*"credit balance"*|*"login expired"*)
      echo "인증 오류(키·토큰 만료·무효 — 운영자 OAuth 토큰 점검 필요)"; return 0 ;;
    *"rate_limit"*|*"rate limit"*|*"overloaded"*|*"usage limit"*|*"weekly limit"*|*"hit your"*|*"quota"*|*"429"*|*"529"*|*"too many requests"*)
      echo "사용량 한도(쿼터·레이트리밋 — 잠시 후 자동 복구)"; return 0 ;;
  esac
  return 1
}

# claude_health_update <out> <stderr_file>
#   분석 호출 직후 1줄 호출. claude 가 응답했으면(출력 있음)=시스템 정상 → 'claude-down' 경고 해제.
#   출력 비었고 stderr 가 시스템성이면 → 경고 박음(프로필 점등). 그 외(콘텐츠·타임아웃)는 무변경.
#   ROOT 기준 실행(스크립트가 cd "$ROOT" 후 source). 실패해도 본 파이프라인 안 깨지게 || true.
claude_health_update() {
  local out="$1" errf="$2" reason
  if [ -n "${out//[$' \t\r\n']/}" ]; then
    python3 shared/msg.py clear claude-down 2>/dev/null || true
  else
    reason="$(claude_systemic_reason "$errf")" && \
      python3 shared/msg.py set claude-down "⚠️ 분석 도구 일시 중단 — ${reason}. 복구되면 자동으로 사라져(요청은 다시 보내줘)." 2>/dev/null || true
  fi
}
