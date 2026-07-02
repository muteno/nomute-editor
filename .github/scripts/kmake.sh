#!/usr/bin/env bash
# 장면 입력(env SCENE) → claude -p(헤드리스, /k 지침 런타임 Read) → Kling 복붙 프롬프트 md
#   → viewer/k_out/<id>/prompt.md. 인증 = CLAUDE_CODE_OAUTH_TOKEN(구독 OAuth·무료, news/card와 동일).
# 워크플로가 커밋·push(thumb-make와 동일 가드 패턴). 실패 = error.log + exit 1(잡 빨갛게).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/k-make.md"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL · 260702 SYS-08)
MODEL="$PIPE_MODEL"
source "$ROOT/shared/claude_transient.sh"  # is_quota()/claude_failover()/is_transient() SSOT — 쿼터 한도 시 3계정 자동 로테이션·일시 과부하 재시도(analyze·ask·card와 통일·§📰)
source "$ROOT/shared/claude_meter.sh"   # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard · 옛 동작 호환)
INLINE_TRIES="${INLINE_TRIES:-3}"   # 쿼터 폴오버(서브1→서브2 = 3계정 체인)·일시 과부하(5xx/Overloaded) 인라인 재시도(15s·30s 백오프) — analyze·ask·card와 동일
ID="${1:?usage: kmake.sh <id> (SCENE=env)}"
OUTDIR="viewer/k_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${SCENE:-}" ] || { echo "::error::SCENE(장면 입력) 비어있음"; echo "exit: 빈 입력" > "$OUTDIR/error.log"; exit 1; }

# 고정부(프롬프트) → 가변부(장면). stdin 전달 = ARG_MAX 회피(analyze.sh와 동일).
prompt="$(cat "$PROMPT_FILE")
${SCENE}"

# 허용 도구 = Read/Glob/Grep(apps/k 지침·라이브러리 런타임 로드) + WebFetch/WebSearch(리서치).
# Write/Edit/Bash/Task 불허 = 헤드리스 무중단(권한 대기로 멈춤 차단, analyze.sh와 동일).
# 인라인 재시도 — 쿼터 한도면 대체 계정 전환(claude_failover·서브1→서브2), 일시 과부하(5xx/Overloaded)면 백오프 재시도. 성공·KMAKE_FAILED(막다른길)는 즉시 탈출(쿼터 낭비 0).
inline_delay=15
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=k METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
        --model "$MODEL" \
        --effort max \
        --allowedTools "Read,Glob,Grep,WebFetch,WebSearch" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task" \
        --max-turns 40 \
        2> "${OUTDIR}/stderr.log")"
  rc=$?
  if { [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '^#' <<<"$out"; } || grep -qm1 '^KMAKE_FAILED' <<<"$out"; then
    break
  fi
  if claude_failover "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 1단계씩 전환·재시도(서브1→서브2 · SSOT)
  if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then
    echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
    sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
  fi
  break
done

# 실패 판정: 비정상 종료 / 빈 출력 / 실패 신호 / '#' 제목 부재
if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^KMAKE_FAILED' <<<"$out" || ! grep -qm1 '^#' <<<"$out"; then
  {
    echo "exit_code: $rc"
    echo "---- stderr ----"; cat "${OUTDIR}/stderr.log" 2>/dev/null
    echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 20
  } > "${OUTDIR}/error.log"
  echo "::error::k 프롬프트 생성 실패 (rc=$rc)"
  exit 1
fi

# 모델 사족 방어 — 첫 '#'(제목)부터 저장.
printf '%s\n' "$out" | sed -n '/^#/,$p' > "${OUTDIR}/prompt.md"
rm -f "${OUTDIR}/stderr.log"
echo "성공 → ${OUTDIR}/prompt.md ($(wc -c < "${OUTDIR}/prompt.md") bytes)"
