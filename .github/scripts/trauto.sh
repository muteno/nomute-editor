#!/usr/bin/env bash
# OCR 라인(env LINES = [{i,t}] JSON) → claude -p(강조 선정+한글 번역) → viewer/tr_out/<id>/plan.json.
# 인증 = CLAUDE_CODE_OAUTH_TOKEN(구독 OAuth·무료). 골격 = kmake.sh 그대로(폴오버 SSOT·계측·인라인 재시도 — 운영자 260720 Q274).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/tr-auto.md"
source "$ROOT/shared/model_env.sh"          # 모델 단일 원천(PIPE_MODEL · SYS-08)
source "$ROOT/shared/claude_transient.sh"   # is_quota()/claude_failover()/is_transient() SSOT — 4계정 자동 로테이션(§📰)
source "$ROOT/shared/claude_meter.sh"       # claude_meter() SSOT — 토큰 계측(metrics shard)
MODEL="${TR_MODEL:-$PIPE_MODEL}"     # 모델 토글(운영자 260722 · 소넷5 등 · 기본 PIPE_MODEL=opus) — 워크플로 env TR_MODEL로 카나리
TR_EFFORT="${TR_EFFORT:-high}"       # OCR 강조선정+한글번역 = 정해진 변환 → high(운영자 260722 · max 헛사고 회피·정확도 우선) · 토글 high/medium/low
INLINE_TRIES="${INLINE_TRIES:-4}"
ID="${1:?usage: trauto.sh <id> (LINES=env)}"
OUTDIR="viewer/tr_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${LINES:-}" ] || { echo "::error::LINES(OCR 라인) 비어있음"; echo "exit: 빈 입력" > "$OUTDIR/error.log"; exit 1; }

# 입력을 번호 라인 텍스트로 정개(모델 친화 · JSON 원문도 뒤에 동봉)
NUM_LINES="$(python3 - <<'PY'
import json, os
try:
    ls = json.loads(os.environ['LINES'])
    print('\n'.join(f"[{l['i']}] {l['t']}" for l in ls if str(l.get('t','')).strip()))
except Exception as e:
    print(f"(파싱 실패: {e})")
PY
)"

# 참고 기사 원문 직접 읽기(운영자 260721 "서드파티 직접 읽기") — 수집 기사(u만 있고 본문 빈약)면 fetch_article.sh 정본 재사용(ask 파이프 동일 축 · 실패 = 제목만 fail-soft)
ART_BODY="$(python3 - <<'PY'
import json, os
try:
    c = json.loads(os.environ.get('CTX') or '{}')
except Exception:
    c = {}
a = c.get('art') or {}
u = str(a.get('u') or '')
print(u if (u.startswith('http') and len(str(a.get('b') or '')) < 80) else '')
PY
)"
if [ -n "$ART_BODY" ]; then
  ART_BODY="$(bash .github/scripts/fetch_article.sh "$ART_BODY" 2>/dev/null | head -c 2500)"
fi
export ART_BODY

# 컨텍스트(참고 기사 스탠스·재생성 지시 · 운영자 260721 v2 — env CTX = {art:{t,m,b,u},note,redo} JSON · 없으면 빈 블록)
CTX_TXT="$(python3 - <<'PY'
import json, os
try:
    c = json.loads(os.environ.get('CTX') or '{}')
except Exception:
    c = {}
seg = []
a = c.get('art') or {}
body = str(a.get('b') or '') or os.environ.get('ART_BODY', '')   # 빈약 본문 = fetch_article.sh 직접 읽기 결과로 대체(수집 기사 축)
if a.get('t') or body:
    seg.append('## 참고 기사(번역 스탠스 근거)\n아래 기사의 관점·용어·톤에 맞춰 강조 선정과 번역 문구의 스탠스를 잡아라.\n제목: %s\n매체: %s\n요약: %s' % (a.get('t',''), a.get('m',''), body))
if c.get('redo'):
    seg.append('## 재생성 요청\n이전 결과가 반려됐다. 선별·번역을 새로 하되 아래 운영자 지시가 있으면 그걸 최우선으로 반영해라.')
if c.get('note'):
    seg.append('## 운영자 지시(최우선 반영)\n%s' % c['note'])
print('\n\n'.join(seg))
PY
)"

prompt="$(cat "$PROMPT_FILE")
${NUM_LINES}

${CTX_TXT}"

# 순수 텍스트 작업 = 도구 전부 불허(헤드리스 무중단 · kmake와 동일 축, 지침 Read조차 불요)
inline_delay=15
_to_tried=0
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=tr METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT="$TR_EFFORT" claude_meter 600 \
        --model "$MODEL" \
        --effort "$TR_EFFORT" \
        --disallowedTools "Read,Glob,Grep,WebFetch,WebSearch,Write,Edit,NotebookEdit,Bash,Task" \
        --max-turns 8 \
        2> "${OUTDIR}/stderr.log")"
  rc=$?
  if { [ $rc -eq 0 ] && grep -qm1 '"chips"' <<<"$out"; } || grep -qm1 '^TRAUTO_FAILED' <<<"$out"; then
    break
  fi
  if [ $rc -eq 124 ] && [ "$_to_tried" = "0" ] && claude_failover_force; then _to_tried=1; continue; fi
  if claude_failover "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then continue; fi
  if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then
    echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
    sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
  fi
  break
done

if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^TRAUTO_FAILED' <<<"$out"; then
  { echo "exit_code: $rc"; echo "---- stderr ----"; cat "${OUTDIR}/stderr.log" 2>/dev/null
    echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 20; } > "${OUTDIR}/error.log"
  echo "::error::tr 플랜 생성 실패 (rc=$rc)"; exit 1
fi

# JSON 추출({ 첫 등장부터) + 스키마 검증 후에만 저장(깨진 plan 커밋 = 폴링 폼 오동작 차단)
printf '%s\n' "$out" | sed -n '/^{/,$p' > "${OUTDIR}/plan.raw"
python3 - "$OUTDIR" <<'PY' || { echo "::error::plan JSON 검증 실패"; cp "${OUTDIR}/plan.raw" "${OUTDIR}/error.log"; exit 1; }
import json, sys, os
d = sys.argv[1]
plan = json.load(open(os.path.join(d, 'plan.raw'), encoding='utf-8'))
assert isinstance(plan.get('hl'), list) and plan['hl'] and all(isinstance(i, int) for i in plan['hl']), 'hl 불량'
assert isinstance(plan.get('chips'), list) and plan['chips'], 'chips 불량'
for c in plan['chips']:
    assert isinstance(c.get('a'), int) and str(c.get('t', '')).strip(), 'chip 불량'
b = plan.get('band')   # 밴드 문구(운영자 260721 v2 · 옵션 — 구 plan 하위호환)
if b is not None:
    assert isinstance(b, str) and len(b) <= 400, 'band 불량'
plan['v'] = 1
json.dump(plan, open(os.path.join(d, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False)
PY
rm -f "${OUTDIR}/plan.raw" "${OUTDIR}/stderr.log"
echo "성공 → ${OUTDIR}/plan.json ($(wc -c < "${OUTDIR}/plan.json") bytes)"
