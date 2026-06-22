#!/usr/bin/env bash
# claude_retry.sh — claude -p 호출을 *일시적* API 과부하(529/503/500/429·Overloaded·rate limit)에
# 끈질기게 재시도하는 단일 공유 헬퍼. 요약(analyze.sh·ask.sh)·카드(cardmake.sh)가 모두 source 해 쓴다.
#
# 왜(운영자 우선순위 260622): 입력을 몰아넣으면(버스트) 요약 콜이 동시다발 → Anthropic 529 Overloaded →
#   재시도가 없으면 그 기사 요약이 '실패'로 격리(pending/failed/)돼 재픽해야 했다. 운영자 요구 =
#   "들어온 건 전부 요약을 끝까지 수용, 최대한 실패 안 뜨고 큐에서 대기·재시도". → 일시 오류면 대기·재시도.
#
# 무엇을 재시도/안 하나(낭비 차단):
#   · 재시도 O = rc≠0 또는 빈 출력 + 출력/stderr에 *일시적* 과부하·레이트리밋·5xx·네트워크 신호.
#   · 재시도 X = 성공(정상 출력) / 비일시적 실패(ANALYSIS_FAILED·기사 아님 등 = 모델의 정상 거절).
#     → 진짜 안 될 건 즉시 떨궈 토큰·시간 낭비 0, 일시 과부하만 끈질기게 버틴다.
#
# 사용:
#   source "$ROOT/shared/claude_retry.sh"
#   out="$(printf '%s' "$prompt" | claude_retry "/tmp/x.err" -- timeout 900 claude -p --model … )"
#   rc=$?
#   - stdin = 프롬프트(매 시도 동일 재전달) · stdout = claude stdout · 반환 = 최종 claude rc.
#   - errfile($1) = 매 시도 stderr 가 기록됨(마지막 시도분이 남음 → 호출 측 실패 로그에 그대로 쓰임).
#
# 정책(요약=끈질김 기본 / 카드=양보) = env 로 호출 측이 조정(요약 우선순위 = 카드가 백오프 크게 줘 API 양보):
#   CR_MAX   최대 시도 횟수            (기본 6)
#   CR_BASE  초기 백오프 초            (기본 15 · 카드는 45 권장 = 요약에 양보)
#   CR_CAP   백오프 상한 초            (기본 120 · 카드는 240 권장)
# ⚠️ 실제 천장 = GitHub 잡 timeout-minutes(무한 대기 불가). 워크플로에서 요약/카드 잡 timeout 을 넉넉히 둔다.

# 출력+stderr 에 일시적(재시도 가치 있는) 오류 신호가 있으면 0 반환.
_cr_is_transient() {   # $1=stdout텍스트 $2=errfile
  grep -qiE \
    '(^|[^0-9])(429|500|502|503|529)([^0-9]|$)|overloaded|rate[ _-]?limit|too many requests|api error: 5|service unavailable|internal server error|timed? ?out|connection (reset|error|refused)|temporarily' \
    <(printf '%s' "${1:-}") "$2" 2>/dev/null
}

claude_retry() {
  local errf="$1"; shift
  [ "${1:-}" = "--" ] && shift            # 가독용 구분자(선택)
  local prompt; prompt="$(cat)"           # stdin = 프롬프트(매 시도 재전달용 보관)
  local max="${CR_MAX:-6}" base="${CR_BASE:-15}" cap="${CR_CAP:-120}"
  local attempt=1 out rc wait
  while :; do
    out="$(printf '%s' "$prompt" | "$@" 2> "$errf")"
    rc=$?
    # 성공(rc=0·비어있지 않음) → 즉시 반환 / 시도 소진 → 반환 / 비일시적 실패 → 즉시 반환(낭비 0)
    if { [ "$rc" -eq 0 ] && [ -n "${out// }" ]; } \
       || [ "$attempt" -ge "$max" ] \
       || ! _cr_is_transient "$out" "$errf"; then
      printf '%s' "$out"
      return "$rc"
    fi
    # 일시적 과부하/오류 → 지수 백오프(+지터)로 대기 후 재시도.
    wait=$(( base * (1 << (attempt - 1)) ))
    [ "$wait" -gt "$cap" ] && wait="$cap"
    wait=$(( wait + (RANDOM % 6) ))        # 지터 = 동시 재시도 분산(thundering herd 완화)
    echo "  ⏳ 일시적 API 과부하/오류 감지 — ${wait}s 후 재시도 (${attempt}/${max})" >&2
    sleep "$wait"
    attempt=$(( attempt + 1 ))
  done
}
