#!/usr/bin/env bash
# 이야기 입력(env STORY) → claude -p(헤드리스, 감독 모델 스위치 · storyboard-v1 스킬 런타임 Read)
#   → 텍스트 콘티 md → viewer/sb_out/<id>/board.md. 인증 = CLAUDE_CODE_OAUTH_TOKEN(구독 OAuth·무료, kmake와 동일).
# 감독 모델 = env DIRECTOR(opus|fable) → --model 매핑(2축 분리 설계 · apps/storyboard/260714_설계확정_2축분리_v1.md).
# 워크플로가 커밋·push(kmake와 동일 가드 패턴). 실패 = error.log + exit 1(잡 빨갛게).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/sb-make.md"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL — 감독 미지정 폴백)
case "${DIRECTOR:-}" in
  opus) MODEL="claude-opus-4-8" ;;    # 감독 = 오퍼스 4.8(정적·감성·가성비)
  fable) MODEL="claude-fable-5" ;;    # 감독 = 페이블 5(역동·서사·재생성 절약)
  *) MODEL="$PIPE_MODEL" ;;
esac
source "$ROOT/shared/claude_transient.sh"  # is_quota()/claude_failover()/is_transient() SSOT — 쿼터 한도 시 4계정 자동 로테이션·일시 과부하 재시도(kmake와 통일·§📰)
source "$ROOT/shared/claude_meter.sh"   # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard)
INLINE_TRIES="${INLINE_TRIES:-4}"   # 쿼터 폴오버(서브1→서브2→서브3)·일시 과부하 인라인 재시도(kmake와 동일)
ID="${1:?usage: sbmake.sh <id> (STORY=env)}"
OUTDIR="viewer/sb_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${STORY:-}" ] || { echo "::error::STORY(이야기 입력) 비어있음"; echo "exit: 빈 입력" > "$OUTDIR/error.log"; exit 1; }

# 지침 프리플라이트 — sb-make.md가 Read시키는 스킬 파일 실존 확인(리네임 시 무성 실패 → 명시 실패 · kmake 프리플라이트 패턴 계승)
for REF_PAT in '\.claude/skills/storyboard-v1/SKILL\.md' '\.claude/skills/master-sheet-v2/SKILL\.md'; do
  GUIDE_REF="$(grep -om1 "$REF_PAT" "$PROMPT_FILE" | head -1 || true)"
  if [ -z "$GUIDE_REF" ]; then
    echo "::error::sb-make.md에 스킬 참조 소실: $REF_PAT (경로 리네임이 패턴을 벗어남?)"
    echo "sb-make.md 참조 소실: $REF_PAT — 프리플라이트 패턴·참조 경로 동시 확인 필요" > "$OUTDIR/error.log"; exit 1
  fi
  REF_FILE="${GUIDE_REF//\\/}"
  if [ ! -f "$REF_FILE" ]; then
    echo "::error::참조 파일 부재: $REF_FILE (sb-make.md 참조 경로 확인 — 스킬 이식 누락?)"
    echo "참조 파일 부재: $REF_FILE — .claude/skills 스킬 5종 이식 상태 확인 필요" > "$OUTDIR/error.log"; exit 1
  fi
done

# 고정부(프롬프트) → 가변부(이야기). stdin 전달 = ARG_MAX 회피(kmake와 동일).
prompt="$(cat "$PROMPT_FILE")
${STORY}"

# 허용 도구 = Read/Glob/Grep(스킬 런타임 로드) + WebFetch/WebSearch(리서치).
# Write/Edit/Bash/Task 불허 = 헤드리스 무중단(kmake와 동일).
inline_delay=15
_to_tried=0   # 타임아웃(rc=124) 계정 강제전환 1회 제한(kmake 패턴 계승)
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=sb METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
        --model "$MODEL" \
        --effort max \
        --allowedTools "Read,Glob,Grep,WebFetch,WebSearch" \
        --disallowedTools "Write,Edit,NotebookEdit,Bash,Task" \
        --max-turns 40 \
        2> "${OUTDIR}/stderr.log")"
  rc=$?
  if { [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '^#' <<<"$out"; } || grep -qm1 '^SBMAKE_FAILED' <<<"$out"; then
    break
  fi
  if [ $rc -eq 124 ] && [ "$_to_tried" = "0" ] && claude_failover_force; then _to_tried=1; continue; fi   # 900s 타임아웃 = 계정 강제 1회 전환(kmake 동일)
  if claude_failover "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 전환(SSOT)
  if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then
    echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
    sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
  fi
  break
done

# 실패 판정: 비정상 종료 / 빈 출력 / 실패 신호 / '#' 제목 부재 (kmake 동일)
if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^SBMAKE_FAILED' <<<"$out" || ! grep -qm1 '^#' <<<"$out"; then
  {
    echo "exit_code: $rc"
    echo "---- stderr ----"; cat "${OUTDIR}/stderr.log" 2>/dev/null
    echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 20
  } > "${OUTDIR}/error.log"
  echo "::error::스토리보드 생성 실패 (rc=$rc)"
  exit 1
fi

# 모델 사족 방어 — 첫 '#'(제목)부터 저장.
printf '%s\n' "$out" | sed -n '/^#/,$p' > "${OUTDIR}/board.md"
rm -f "${OUTDIR}/stderr.log"
echo "성공 → ${OUTDIR}/board.md ($(wc -c < "${OUTDIR}/board.md") bytes)"
