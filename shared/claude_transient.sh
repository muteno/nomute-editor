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
  # ⚠️ 'weekly limit'·'hit your … limit'·'limit … resets <날짜>' 추가(260629·동시세션 합본) = Claude Code 주간 한도 메시지 "You've hit your weekly limit · resets Jul 3" 포착.
  #   이게 빠져 있어 주간한도 시 failover가 안 걸리고 활성계정에서 즉시 실패(서브계정 미시도)했음 — ask/analyze/card 전부 영향(SSOT).
  # + 'Failed to authenticate|API Error: 403' 추가(260712 실측 · pending/failed/260712-135654 — 운영자가 같은 OAuth 계정을 대화형으로 몰아 쓸 때 활성 계정이 쿼터 문구 없이 403 socket-close 인증 실패를 뱉음 → 미포착 = 서브계정 미시도 즉사 = "요약이 막힌다").
  #   위 15줄 '인증죽음 전환 무의미' 전제는 *전 계정 공통 고장* 가정 — 403은 활성 계정 국한(사용량 상관)이라 전환이 정확한 처방. 진짜 전 계정 고장이면 체인 소진 후 종전과 동일 실패 = 부작용 0.
  # + '토큰 비용/크레딧 부족' 계열 추가(운영자 260714 "막혔다→이유가 토큰 비용이면 바로 다른 거로 전환·대기하지 마") — credit balance/insufficient/out of credits/billing 문구가 감지망에 없어 그 경우 전환 없이 종료했음. 구체 구문만(단독 'credit' 금지 = 본문 인용 오탐 억제·앞 8줄 검사와 이중 가드).
  grep -qiE 'usage limit|weekly limit|hit your .{0,40}limit|rate.?limit|rate_limit|429|too many requests|quota|limit reached|limit.{0,40}reset|resets? (at|in)|failed to authenticate|api error:? 403|credit balance|insufficient (credit|fund)|out of (credit|token)s?|billing (issue|error|problem)' <<<"$s"
}

# _claude_mark_active_quota(): 활성 계정(체인 첫 계정)이 이번 런에 쿼터로 폴오버됐음을 신호 파일에 남긴다.
#   account_failover.py(활성 계정 자동 승격)가 이 파일 존재를 보고 누적 카운트 → 임계 시 vars.ACTIVE_ACCOUNT 전진(sticky failover).
#   best-effort(실패 무시) · n==0(활성→서브1) 첫 스왑에서만 호출 = '활성 계정이 이번 런에 막혔다'는 뜻(서브 쿼터는 신호 안 냄).
#   정본 문서 = docs/oauth_계정_자동승격_이식가이드.md.
_claude_mark_active_quota() {
  : > "${NOMUTE_QUOTA_SIGNAL:-${GITHUB_WORKSPACE:-/tmp}/.nomute_active_quota}" 2>/dev/null || true
}

# claude_failover(): 출력이 쿼터 한도면 *대체 계정 토큰*으로 1단계씩 전환(4계정 체인 = 메인1 + 세부3).
#   1차 = CLAUDE_CODE_OAUTH_TOKEN_ALT(서브1) · 2차 = CLAUDE_CODE_OAUTH_TOKEN_ALT2(서브2) · 3차 = CLAUDE_CODE_OAUTH_TOKEN_ALT3(서브3).
#   전환함=0(호출부가 같은 프롬프트로 재시도) / 못 함(쿼터 아님·다음 대체 없음·체인 소진)=1.
#   _CLAUDE_SWAPPED = 지금까지 전환 횟수(0→1→2→3). ⚠️ ALT2/ALT3 미설정이면 그 단계에서 멈춤 = 옛 동작(하위호환).
claude_failover() {
  is_quota "${1:-}" || return 1
  local n="${_CLAUDE_SWAPPED:-0}"
  if [ "$n" = "0" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_ALT:-}" ]; then
    _claude_mark_active_quota   # 활성 계정 쿼터 신호(sticky 승격용 · account_failover.py 가 읽음)
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_ALT"; _CLAUDE_SWAPPED=1
    echo "  🔄 계정 사용량 한도 — 서브1 계정으로 전환 후 재시도(account failover 1/3)"
    return 0
  fi
  if [ "$n" = "1" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_ALT2:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_ALT2"; _CLAUDE_SWAPPED=2
    echo "  🔄 서브1도 한도 — 서브2 계정으로 전환 후 재시도(account failover 2/3)"
    return 0
  fi
  if [ "$n" = "2" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_ALT3:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_ALT3"; _CLAUDE_SWAPPED=3
    echo "  🔄 서브2도 한도 — 서브3 계정으로 전환 후 재시도(account failover 3/3)"
    return 0
  fi
  return 1
}

# claude_failover_force(): 쿼터 판정(is_quota) 없이 다음 계정으로 강제 전환. 타임아웃(rc=124)처럼
#   '출력이 비어 is_quota 가 못 잡지만 계정 바꾸면 나을 수도 있는' 상황용(서버 응답지연·계정별 부하 편차 · 운영자 260704).
#   ⚠️ 토큰 슬롯은 claude_failover(쿼터)와 공유하되, force 로 올린 스텝은 _FORCE_SWAPS 로 따로 센다 →
#     claude_reset_force_swap()이 기사마다 되돌려, 타임아웃(대개 입력바운드 = 계정 바꿔도 반복)이 쿼터 4계정 체인
#     예산을 *영구* 소진하는 것을 막는다(평의회 260704 Q5). 쿼터 스왑은 sticky 유지, force 스왑만 per-기사 임시.
#   전환함=0(호출부가 같은 프롬프트로 재시도) / 다음 대체 없음·체인 소진=1(→ 호출부는 격리).
claude_failover_force() {
  local n="${_CLAUDE_SWAPPED:-0}"
  if [ "$n" = "0" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_ALT:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_ALT"; _CLAUDE_SWAPPED=1; _FORCE_SWAPS=$(( ${_FORCE_SWAPS:-0} + 1 ))
    echo "  🔄 처리 지연/시간초과 — 서브1 계정으로 전환 후 재시도(force failover 1/3)"
    return 0
  fi
  if [ "$n" = "1" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_ALT2:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_ALT2"; _CLAUDE_SWAPPED=2; _FORCE_SWAPS=$(( ${_FORCE_SWAPS:-0} + 1 ))
    echo "  🔄 서브1도 지연 — 서브2 계정으로 전환 후 재시도(force failover 2/3)"
    return 0
  fi
  if [ "$n" = "2" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_ALT3:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_ALT3"; _CLAUDE_SWAPPED=3; _FORCE_SWAPS=$(( ${_FORCE_SWAPS:-0} + 1 ))
    echo "  🔄 서브2도 지연 — 서브3 계정으로 전환 후 재시도(force failover 3/3)"
    return 0
  fi
  return 1
}

# claude_preflight(모델): 본선(수백초 timeout LLM 콜) 직전 60초 미니 핑으로 '산 계정'을 먼저 골라 탑승(운영자 260717
#   "몇십분 통째로 안태우게 공회전 없애게 ㄱㄱ" — 실측 7/16 run 87487242035: 죽은 활성계정은 쿼터 문구 없이 *침묵 행*이라
#   첫 시도가 본선 timeout 600s를 통째로 태우고, 서브계정은 2초 만에 '한도' 즉답 = 공회전이 사고 증폭기).
#   동작: 현재 계정에 1턴 핑(timeout PREFLIGHT_TIMEOUT 기본 60s·effort low·툴 0 = 최소비) → 성공 = 0 반환(본선 GO) ·
#   쿼터 문구 = claude_failover(sticky·승격 신호) · 침묵/그외 = claude_failover_force(임시 카운트) → 다음 계정 재핑, 체인 소진까지.
#   전 계정 실패 = 1 반환하되 마지막 계정 토큰 유지 → 호출부는 그대로 본선 강행(fail-soft — 핑과 본선은 성격이 달라 본선이 살 수도 · 종전 동작 보존).
#   비용: 산 계정 = 수초·수십 토큰(본선 대비 0급) · 죽은 계정 = 60s(종전 600~900s 공회전의 1/10~1/15) · 모델 = 본선과 동일 인자 필수(쿼터·부하가 모델축과 얽혀 딴 모델 핑 = 무효 신호).
claude_preflight() {
  local _pf_model="${1:?claude_preflight: 본선과 동일한 모델 인자 필수}"
  local _pf_to="${PREFLIGHT_TIMEOUT:-60}" _pf_out _pf_rc
  while :; do
    _pf_out="$(printf 'preflight: ok 한 단어만 답해' | timeout "$_pf_to" claude -p --model "$_pf_model" --effort low --safe-mode --max-turns 1 \
      --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,Task,WebFetch,WebSearch,NotebookEdit,TodoWrite" 2>&1)"; _pf_rc=$?
    if [ "$_pf_rc" -eq 0 ] && [ -n "$_pf_out" ] && ! is_quota "$_pf_out"; then
      return 0   # 산 계정 확보 — 본선 GO
    fi
    echo "  🩺 프리플라이트: 계정 응답 이상(rc=$_pf_rc) — 다음 계정 핑"
    claude_failover "$_pf_out" && continue        # 쿼터 문구 = sticky 전환 + 승격 신호(종전 회계 그대로)
    claude_failover_force && continue             # 침묵 행/그외 = 임시 전환(_FORCE_SWAPS 계상 = reset 회계 일관)
    echo "::warning::프리플라이트 전 계정 무응답 — 마지막 계정으로 본선 강행(fail-soft)"
    return 1
  done
}

# 계정 슬롯(0=primary·1=ALT·2=ALT2·3=ALT3) → 토큰. primary = 이 파일 source 시점의 CLAUDE_CODE_OAUTH_TOKEN(활성계정) 스냅샷.
: "${_CLAUDE_TOK0:=${CLAUDE_CODE_OAUTH_TOKEN:-}}"
_claude_slot_token() { case "${1:-0}" in 0) printf '%s' "${_CLAUDE_TOK0:-}";; 1) printf '%s' "${CLAUDE_CODE_OAUTH_TOKEN_ALT:-}";; 2) printf '%s' "${CLAUDE_CODE_OAUTH_TOKEN_ALT2:-}";; 3) printf '%s' "${CLAUDE_CODE_OAUTH_TOKEN_ALT3:-}";; esac; }
# claude_reset_force_swap(): force(타임아웃)로 임시 전환된 계정을 쿼터 확정 위치로 되돌린다(각 기사 처리 진입 시 호출).
#   쿼터 스왑(claude_failover, _FORCE_SWAPS 미증가)은 그대로 유지 · force 로 올린 분(_FORCE_SWAPS)만 차감 → 토큰 복원.
#   ⚠️ 한 기사에서 쿼터+타임아웃이 겹쳐도 force 분만 정확히 빠지고 쿼터 스왑은 보존(스텝 차감식).
#   ⚠️ 차감식 전제 = claude_failover(쿼터)·claude_failover_force(타임아웃)가 *동일 슬롯 사다리(0→1→2→3)를 lockstep* 으로 오른다는 것 → 둘의 슬롯 순서·_claude_slot_token 매핑을 항상 동기화 유지(한쪽만 순서 바꾸면 reset 이 조용히 오복원 · 재검증 260704).
claude_reset_force_swap() {
  local f="${_FORCE_SWAPS:-0}"; [ "$f" = "0" ] && return 0
  local q=$(( ${_CLAUDE_SWAPPED:-0} - f )); [ "$q" -lt 0 ] && q=0
  _CLAUDE_SWAPPED="$q"; _FORCE_SWAPS=0
  local tok; tok="$(_claude_slot_token "$q")"; [ -n "$tok" ] && export CLAUDE_CODE_OAUTH_TOKEN="$tok"
}
