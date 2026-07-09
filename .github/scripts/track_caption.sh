#!/usr/bin/env bash
# 트래킹 카드 캡션 + 동일인 병합 힌트 — opus 4.8 · effort max (운영자 260710 승인 = 트래킹 LLM 0콜 기틀 해제 · 분석 보조 1콜)
#   tracks.json + crops/*.jpg → claude -p(--safe-mode·Read만)가 {카드별 한 줄 묘사, *확실한* 동일인 pid 쌍} JSON 출력
#   → tracks.json에 people[].cap · subjects[].cap · meta.same_hint 병합(additive — 렌더·모자이크/핀셋/키잉 소비 계약 불변).
# 불변(치명 주의):
#   - **전면 fail-soft = 어떤 실패도 exit 0 · error.log 절대 금지** — error.log는 뷰어 분석 폴의 치명 신호(즉시 실패 표시)라
#     캡션 실패가 정상 분석 산출을 죽이면 안 됨. 실패 = ::warning + 캡션 없이 진행.
#   - 묘사만(옷·색·위치·특징) · 실명/신원/유명인 추정 절대 금지(정책·초상권). 병합 힌트(same)는 확실할 때만 —
#     모델이 얼굴 비교를 거부/애매 판정하면 빈 배열 = 정직(뷰어는 없으면 그냥 안 그림).
#   - --safe-mode 근거: 프롬프트 자기완결(크롭 경로+규칙) = CLAUDE.md·skills·MCP 의존 0 · Read는 내장 도구라 정상 동작
#     (§📰 d '생성 경로 safe-mode 신중'의 정밀분석 요건 = 이 주석 + 카나리아 실측으로 이행).
#   - 게이트 = TRACK_CAP=1일 때만(§📰 e 카나리아 절차: 기본 OFF 머지 → dispatch 카나리아 → 실측 후 승격).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
[ "${TRACK_CAP:-}" = "1" ] || { echo "TRACK_CAP OFF — 캡션 스킵"; exit 0; }
ID="${1:-}"
[ -n "$ID" ] || { echo "::warning::id 없음 — 캡션 스킵"; exit 0; }   # ${1:?} 비영종료 대신 fail-soft 일관(평의회2 F4)
case "$ID" in *[!0-9a-f-]*) echo "::warning::잘못된 id — 캡션 스킵"; exit 0;; esac   # 자기완결 가드(워크플로 가드에만 위임 안 함 · 평의회3)
OUTDIR="viewer/track_out/${ID}"
TJ="$OUTDIR/tracks.json"
[ -s "$TJ" ] || { echo "::warning::tracks.json 없음 — 캡션 스킵"; exit 0; }
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL = claude-opus-4-8 · 260702 SYS-08)
MODEL="$PIPE_MODEL"
source "$ROOT/shared/claude_transient.sh"   # is_quota()/claude_failover()/is_transient() SSOT — 4계정 로테이션(§📰 f)
source "$ROOT/shared/claude_meter.sh"       # claude_meter() SSOT — 토큰 계측
INLINE_TRIES="${INLINE_TRIES:-4}"

# 카드 목록(크롭 실존만) — Read 도구가 열 절대경로 제시
LIST="$(python3 - "$TJ" "$OUTDIR" <<'PY'
import json, os, sys
tj, out = sys.argv[1], sys.argv[2]
d = json.load(open(tj, encoding="utf-8"))
rows = []
for p in d.get("people", []):
    c = p.get("crop") or ""
    fp = os.path.join(out, c)
    if c and os.path.isfile(fp):
        rows.append("p%s: %s" % (p.get("pid"), os.path.abspath(fp)))
for s in d.get("subjects", []):
    c = s.get("crop") or ""
    fp = os.path.join(out, c)
    if c and os.path.isfile(fp):
        rows.append("s%s: %s" % (s.get("sid"), os.path.abspath(fp)))
print("\n".join(rows))
PY
)" || { echo "::warning::카드 목록 실패 — 캡션 스킵"; exit 0; }
[ -n "$LIST" ] || { echo "캡션 대상 크롭 0 — 스킵"; exit 0; }

prompt="영상 트래킹 카드 보조 작업. 아래 각 이미지(인물 얼굴 p* · 피사체 s* 크롭)를 Read 도구로 열어 보고 JSON 하나만 출력해.
규칙:
- 키 = 목록의 번호 그대로: people 키 = p번호(\`p5:\` 이미지 → \"5\") · subjects 키 = s번호 · same도 p번호 쌍. 번호는 비연속일 수 있음 — 순번으로 다시 매기지 마라.
- cap = 카드 구분용 한 줄 묘사(한국어 14자 이내 · 옷/색/위치/특징만). 신원 추정·실명·유명인 이름 절대 금지.
- same = 서로 다른 p 카드가 *확실히* 같은 사람일 때만 p번호 쌍 나열(예 [[5,7]]). 다른 사람을 같다고 하는 오류가 놓치는 것보다 훨씬 나쁘다(모자이크 오배정 위험) — 조금이라도 애매하거나 판단이 곤란하면 빈 배열 [].
- 열리지 않거나 식별 곤란한 이미지 = 해당 키 생략(추측 금지).
- 출력 = JSON 한 덩어리만(설명·코드펜스 금지): {\"people\":{\"5\":\"남색 정장, 마이크 앞\",\"7\":\"회색 후드\"},\"subjects\":{\"1\":\"흰색 승합차\"},\"same\":[]}
이미지 목록:
$LIST"
NCARD="$(printf '%s\n' "$LIST" | wc -l | tr -d ' ')"
MAXTURNS=$((2 * NCARD + 10))   # 카드 수 비례(이미지 Read 왕복 여유 · 평의회8 F5)

inline_delay=15; rc=1; out=""
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=track-cap METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 600 \
        --model "$MODEL" \
        --effort max \
        --safe-mode \
        --allowedTools "Read" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Glob,Grep" \
        --max-turns "$MAXTURNS" \
        2> /tmp/track_cap_stderr.log)"
  rc=$?
  if [ $rc -eq 0 ] && grep -qm1 '{' <<<"$out"; then break; fi
  if claude_failover "$out$(cat /tmp/track_cap_stderr.log 2>/dev/null)"; then continue; fi   # 쿼터 한도 = 대체 계정 전환(SSOT)
  if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat /tmp/track_cap_stderr.log 2>/dev/null)"; then
    echo "  ⏳ 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
    sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
  fi
  break
done
{ [ $rc -eq 0 ] && grep -qm1 '{' <<<"$out"; } || { echo "::warning::캡션 생성 실패(rc=$rc) — 캡션 없이 진행(fail-soft)"; exit 0; }

CAP_OUT="$out" python3 - "$TJ" <<'PY' || echo "::warning::캡션 병합 실패 — 캡션 없이 진행(fail-soft)"
import json, os, re, sys
tj = sys.argv[1]
raw = os.environ.get("CAP_OUT", "")
m = re.search(r'\{.*\}', raw, re.S)   # 관용 추출 — 앞뒤 산문·펜스 잔여 허용(§📰 c 관용 파싱 정신)
if not m:
    sys.exit(1)
try:
    j = json.loads(m.group(0))
except Exception:
    sys.exit(1)
d = json.load(open(tj, encoding="utf-8"))
clean = lambda s: str(s).strip().replace("\n", " ")[:20]   # 프롬프트는 14자 지시 · 파서는 20자 하드캡(이중띠 · 평의회7)
pc = j.get("people") or {}
sc = j.get("subjects") or {}
for p in d.get("people", []):
    v = pc.get(str(p.get("pid")))
    if v:
        p["cap"] = clean(v)
for s in d.get("subjects", []):
    v = sc.get(str(s.get("sid")))
    if v:
        s["cap"] = clean(v)
pids = {p.get("pid") for p in d.get("people", [])}
same = []
for pair in (j.get("same") or []):
    try:
        a, b = int(pair[0]), int(pair[1])
    except Exception:
        continue
    if a in pids and b in pids and a != b and sorted((a, b)) not in same:
        same.append(sorted((a, b)))
d.setdefault("meta", {})["same_hint"] = same
tmp = tj + ".captmp"
with open(tmp, "w", encoding="utf-8") as f:   # 원자 교체 — 타임아웃 하드킬이 dump 도중 걸려도 원본 tracks.json 절단 0(평의회2 F3)
    json.dump(d, f, ensure_ascii=False, separators=(",", ":"))   # analyze 저장 포맷 정합(compact · 평의회7)
os.replace(tmp, tj)
print("캡션 병합: people %d · subjects %d · same %d" % (
    sum(1 for p in d.get("people", []) if p.get("cap")),
    sum(1 for s in d.get("subjects", []) if s.get("cap")), len(same)))
PY
rm -f /tmp/track_cap_stderr.log   # 러너 잔존면 정리(평의회3 방어심화)
exit 0
