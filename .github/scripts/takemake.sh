#!/usr/bin/env bash
# 테이크 감지(운영자 260727 ④) — 입력(env SUBS = 타임코드 전사) → claude -p(prompts/take-make.md)
#   → viewer/ly_out/<id>/takes.json{drop:[{s,e,why}]} = **버릴 반복 테이크 구간 제안**.
#   소비 = ly_burn.load_take_spans(렌더 시 차감) · cut_scan(컷 미리보기 목록에 kind=take로 합류).
#   골격 = clipmake.sh 100% 미러(인증·폴오버·계측·3층 관용 파싱) — 다른 건 프롬프트·출력 키(drop)·검증 규칙뿐.
#   실패 = 비치명으로 설계(호출측 워크플로가 `|| true` — 테이크 감지 실패가 컷·자막 잡을 죽이면 안 됨).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/take-make.md"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL · §모델)
MODEL="${TAKE_MODEL:-claude-fable-5}"   # 클리퍼(구간선정)와 같은 티어 = 판단형 · 폴백 = Opus
source "$ROOT/shared/claude_transient.sh"  # is_quota()/claude_failover()/is_transient() SSOT
source "$ROOT/shared/claude_meter.sh"      # claude_meter() SSOT — 토큰 계측
INLINE_TRIES="${INLINE_TRIES:-4}"
ID="${1:?usage: takemake.sh <id> (SUBS=env)}"
OUTDIR="viewer/ly_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${SUBS:-}" ] || { echo "::warning::SUBS(전사) 비어있음 — 테이크 감지 스킵"; exit 1; }

prompt="$(cat "$PROMPT_FILE")"
prompt="$prompt

[전사 — 영상 길이 ${EDIT_DUR:-미상}초]
${SUBS}"

inline_delay=15
rc=1
TAKE_MODEL_FB="${TAKE_MODEL_FB:-claude-opus-5}"; _mfb_tried=0; _eff=high
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=take METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT="$_eff" claude_meter 600 \
        --model "$MODEL" \
        --effort "$_eff" \
        --disallowedTools "Read,Glob,Grep,Write,Edit,NotebookEdit,Bash,Task,WebFetch,WebSearch" \
        --max-turns 1 \
        2> "${OUTDIR}/take_stderr.log")"
  rc=$?
  if [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '"drop"' <<<"$out"; then
    break
  fi
  if claude_failover "$out$(cat "${OUTDIR}/take_stderr.log" 2>/dev/null)"; then continue; fi
  if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "${OUTDIR}/take_stderr.log" 2>/dev/null)"; then
    echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
    sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
  fi
  if [ "$_mfb_tried" = 0 ] && [ "$MODEL" != "$TAKE_MODEL_FB" ] && [ "$attempt" -lt "$INLINE_TRIES" ]; then
    _mfb_tried=1; MODEL="$TAKE_MODEL_FB"; _eff=high; echo "  ⏳ 모델 폴백 → ${MODEL} high (1회 한정)"; continue
  fi
  break
done
rm -f "${OUTDIR}/take_stderr.log"

if [ $rc -ne 0 ] || [ -z "${out// }" ] || ! grep -qm1 '"drop"' <<<"$out"; then
  echo "::warning::테이크 감지 실패(rc=$rc) — 테이크 컷 없이 진행"
  exit 1
fi

# LLM 출력 → takes.json — 3층 관용 파싱(clipmake 문법 그대로) + 스팬 실측 검증.
#   하드넷: 전사 범위 클램프 · 0.3초 미만 드롭 · 총 제거 ≤ 영상의 50%(초과분은 뒤에서부터 버림 = 프롬프트 지시의 보수 여유)
TAKE_OUT="$out" python3 - "$OUTDIR" <<'PY' || { echo "::warning::takes.json 파싱 실패 — 테이크 컷 없이 진행"; exit 1; }
import json
import os
import re
import sys
from math import isfinite

sys.path.insert(0, ".github/scripts")
import ly_burn as lb   # kst_now(KST 표기 SSOT · §표기표준)

d = sys.argv[1]
raw = os.environ.get("TAKE_OUT") or ""
j = None
m = re.search(r"```[ \t]*(?:json)?\s*(\{[\s\S]*?)(?:```|\Z)", raw, re.I)   # ① 펜스 관용
if m and '"drop"' in m.group(1):
    try:
        j = json.loads(m.group(1).strip())
    except Exception:
        j = None
if j is None:   # ② 펜스 없는 raw JSON
    dec = json.JSONDecoder()
    for mm in re.finditer(r"\{", raw):
        try:
            obj, _end = dec.raw_decode(raw, mm.start())
        except Exception:
            continue
        if isinstance(obj, dict) and "drop" in obj:
            j = obj
            break
assert isinstance(j, dict), "JSON 미검출"   # ③ 미검출 = 소리나는 실패(상위가 warning + 스킵)
try:
    dur = float(os.environ.get("EDIT_DUR") or 0)
except Exception:
    dur = 0.0
dl = j.get("drop")
if not isinstance(dl, list):
    dl = []   # 비배열(형식 이탈) = 0개로 우아한 강등
drop, tot = [], 0.0
for c in sorted([x for x in dl[:60] if isinstance(x, dict)], key=lambda x: x.get("s") or 0):
    try:
        s, e = float(c.get("s")), float(c.get("e"))
    except Exception:
        continue
    if not (isfinite(s) and isfinite(e)) or s < 0 or e <= s:
        continue
    if dur > 0:
        if s >= dur:
            continue
        e = min(e, dur)
    if e - s < 0.3:
        continue
    if dur > 0 and tot + (e - s) > dur * 0.5:
        continue   # 절반 초과 = 그 후보부터 버림(과잉 삭제 방어 — 침묵 클램프 아님·아래 note로 표면화)
    tot += e - s
    drop.append({"s": round(s, 1), "e": round(e, 1), "why": str(c.get("why") or "").strip()[:60]})
doc = {"v": 1, "ts": lb.kst_now(), "dur": round(dur, 1), "drop": drop}
if len(drop) < len([x for x in dl if isinstance(x, dict)]):
    doc["note"] = "일부 후보 제외(범위·길이·총량 하드넷)"
p = os.path.join(d, "takes.json")
tmp = p + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
os.replace(tmp, p)   # 원자 교체 = 레포 표준
print("takes.json: 버릴 테이크 {}개 ({:.1f}초)".format(len(drop), tot))
PY
echo "성공 → ${OUTDIR}/takes.json"
