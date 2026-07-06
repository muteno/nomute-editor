#!/usr/bin/env bash
# 입력(env SUBS = SRT/STT 텍스트) → claude -p(헤드리스, /ly 지침 런타임 Read) → 릴스 자막 md
#   → viewer/ly_out/<id>/subs.md. 인증 = CLAUDE_CODE_OAUTH_TOKEN(구독 OAuth·무료).
# 워크플로가 커밋·push(thumb-make 가드 패턴). 실패 = error.log + exit 1.
# 이 스크립트는 SUBS(텍스트/SRT 또는 Whisper STT 결과)만 처리. 영상 URL/파일→Whisper STT는 워크플로(ly-make.yml) 상위 스텝에서.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/ly-make.md"
MODEL="claude-opus-4-8"
source "$ROOT/shared/claude_transient.sh"  # is_quota()/claude_failover()/is_transient() SSOT — 쿼터 한도 시 3계정 자동 로테이션·일시 과부하 재시도(analyze·ask·card와 통일·§📰)
source "$ROOT/shared/claude_meter.sh"   # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard · 옛 동작 호환)
INLINE_TRIES="${INLINE_TRIES:-3}"   # 쿼터 폴오버(서브1→서브2 = 3계정 체인)·일시 과부하(5xx/Overloaded) 인라인 재시도(15s·30s 백오프) — analyze·ask·card와 동일
ID="${1:?usage: lymake.sh <id> (SUBS=env)}"
OUTDIR="viewer/ly_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${SUBS:-}" ] || { echo "::error::SUBS(자막/SRT 입력) 비어있음"; echo "exit: 빈 입력" > "$OUTDIR/error.log"; exit 1; }

prompt="$(cat "$PROMPT_FILE")
${SUBS}"

# 인라인 재시도 — 쿼터 한도면 대체 계정 전환(claude_failover·서브1→서브2), 일시 과부하(5xx/Overloaded)면 백오프 재시도. 성공·LYMAKE_FAILED(막다른길)는 즉시 탈출(쿼터 낭비 0).
inline_delay=15
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=ly METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
        --model "$MODEL" \
        --effort max \
        --allowedTools "Read,Glob,Grep" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch" \
        --max-turns 40 \
        2> "${OUTDIR}/stderr.log")"
  rc=$?
  if { [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '^#' <<<"$out"; } || grep -qm1 '^LYMAKE_FAILED' <<<"$out"; then
    break
  fi
  if claude_failover "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 1단계씩 전환·재시도(서브1→서브2 · SSOT)
  if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then
    echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
    sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
  fi
  break
done

if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^LYMAKE_FAILED' <<<"$out" || ! grep -qm1 '^#' <<<"$out"; then
  {
    echo "exit_code: $rc"
    echo "---- stderr ----"; cat "${OUTDIR}/stderr.log" 2>/dev/null
    echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 20
  } > "${OUTDIR}/error.log"
  echo "::error::ly 자막 생성 실패 (rc=$rc)"
  exit 1
fi

printf '%s\n' "$out" | sed -n '/^#/,$p' > "${OUTDIR}/subs.md"
rm -f "${OUTDIR}/stderr.log"
echo "성공 → ${OUTDIR}/subs.md ($(wc -c < "${OUTDIR}/subs.md") bytes)"
