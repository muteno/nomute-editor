#!/usr/bin/env bash
# 입력(env SUBS = SRT/STT 텍스트) → claude -p(헤드리스, /ly 지침 런타임 Read) → 릴스 자막 md
#   → viewer/ly_out/<id>/subs.md. 인증 = CLAUDE_CODE_OAUTH_TOKEN(구독 OAuth·무료).
# 워크플로가 커밋·push(thumb-make 가드 패턴). 실패 = error.log + exit 1.
# 이 스크립트는 SUBS(텍스트/SRT 또는 Whisper STT 결과)만 처리. 영상 URL/파일→Whisper STT는 워크플로(ly-make.yml) 상위 스텝에서.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/ly-make.md"
MODEL="claude-opus-4-8"
source "$ROOT/shared/claude_meter.sh"   # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard · 옛 동작 호환)
ID="${1:?usage: lymake.sh <id> (SUBS=env)}"
OUTDIR="viewer/ly_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${SUBS:-}" ] || { echo "::error::SUBS(자막/SRT 입력) 비어있음"; echo "exit: 빈 입력" > "$OUTDIR/error.log"; exit 1; }

prompt="$(cat "$PROMPT_FILE")
${SUBS}"

out="$(printf '%s' "$prompt" | METER_SRC=ly METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
      --model "$MODEL" \
      --effort max \
      --allowedTools "Read,Glob,Grep" \
      --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch" \
      --max-turns 40 \
      2> "${OUTDIR}/stderr.log")"
rc=$?

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
