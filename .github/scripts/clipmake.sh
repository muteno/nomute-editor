#!/usr/bin/env bash
# 쇼츠 클리퍼 v0(운영자 260711 승인) — 입력(env SUBS = 타임코드 전사) → claude -p(prompts/clip-make.md 구간픽)
#   → viewer/ly_out/<id>/clips.json. 하이라이트 *후보 제안*만 — 자동 발행 없음(선택·렌더 = 운영자 · 뷰어 2단 = track 분석→확정 미러).
#   인증 = 구독 OAuth · 폴오버 SSOT(claude_transient) 경유 = lymake와 동일 계약. 실패 = error.log + exit 1(뷰어 폴 표면화).
#   후보 0개 = 정상 산출(clips.json 빈 목록 · exit 0 — 억지 후보 금지). env: EDIT_DUR(초·선택) · SRC_URL(원 URL 소스 = 재렌더용 승계·선택).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/clip-make.md"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL — 생성/판단 = opus 유지 · §모델)
MODEL="$PIPE_MODEL"
source "$ROOT/shared/claude_transient.sh"  # is_quota()/claude_failover()/is_transient() SSOT — 4계정 로테이션(§📰)
source "$ROOT/shared/claude_meter.sh"      # claude_meter() SSOT — 토큰 계측
INLINE_TRIES="${INLINE_TRIES:-4}"   # 쿼터 폴오버 체인 깊이(4계정)와 동수 — lymake 동일
ID="${1:?usage: clipmake.sh <id> (SUBS=env)}"
OUTDIR="viewer/ly_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${SUBS:-}" ] || { echo "::error::SUBS(전사) 비어있음"; echo "클립 스캔 실패 — 전사가 비었어(소리 없는 영상?)" > "$OUTDIR/error.log"; exit 1; }

prompt="$(cat "$PROMPT_FILE")"
prompt="$prompt

[전사 — 영상 길이 ${EDIT_DUR:-미상}초]
${SUBS}"

# 인라인 재시도 — 쿼터 한도 = 대체 계정 전환 · 일시 과부하 = 백오프(lymake 문법 그대로)
inline_delay=15
rc=1   # set -u 방어(INLINE_TRIES 이상값으로 루프 미진입 시 미정의 참조 차단 · 검증⑥ L1)
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=clip METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 600 \
        --model "$MODEL" \
        --effort max \
        --disallowedTools "Read,Glob,Grep,Write,Edit,NotebookEdit,Bash,Task,WebFetch,WebSearch" \
        --max-turns 1 \
        2> "${OUTDIR}/stderr.log")"
  rc=$?
  if [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '"clips"' <<<"$out"; then
    break
  fi
  if claude_failover "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 서브1→서브2→서브3(SSOT)
  if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then
    echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
    sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
  fi
  break
done

if [ $rc -ne 0 ] || [ -z "${out// }" ] || ! grep -qm1 '"clips"' <<<"$out"; then
  {
    echo "exit_code: $rc"
    echo "---- stderr ----"; cat "${OUTDIR}/stderr.log" 2>/dev/null
    echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 10
  } > "${OUTDIR}/error.log"
  rm -f "${OUTDIR}/stderr.log"   # 실패 잔존 시 커밋 유입 차단(내용은 error.log에 이미 수용 · 검증⑥ L2)
  echo "::error::클립 구간픽 실패 (rc=$rc)"
  exit 1
fi

# LLM 출력 → clips.json — 3층 관용 파싱(§📰 LLM 형식 보증: 펜스 관용 → raw JSON → 미검출 = 실패 표면화) + 스팬 실측 검증
#   길이 가드 6~90초 = 프롬프트 지시(15~60초)의 *보수 여유 하드넷*(지시 위반 후보도 운영자 확정 단계가 거름 · 검증⑥ L6/⑩ P4 — 숫자 불일치는 의도)
CLIP_OUT="$out" python3 - "$OUTDIR" <<'PY' || { echo "클립 후보 파싱 실패 — 다시 시도해줘" > "$OUTDIR/error.log"; rm -f "$OUTDIR/stderr.log"; echo "::error::clips.json 파싱 실패"; exit 1; }
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from math import isfinite

d = sys.argv[1]
raw = os.environ.get("CLIP_OUT") or ""
j = None
m = re.search(r"```[ \t]*(?:json)?\s*(\{[\s\S]*?)(?:```|\Z)", raw, re.I)   # ① 펜스 관용(태그 생략·닫는 펜스 누락)
if m and '"clips"' in m.group(1):
    try:
        j = json.loads(m.group(1).strip())
    except Exception:
        j = None
if j is None:   # ② 펜스 없는 raw JSON — 앞에서부터 raw_decode(출력 = JSON 단독 계약이라 첫 '{'가 정본)
    dec = json.JSONDecoder()
    for mm in re.finditer(r"\{", raw):
        try:
            obj, _end = dec.raw_decode(raw, mm.start())
        except Exception:
            continue
        if isinstance(obj, dict) and "clips" in obj:
            j = obj
            break
assert isinstance(j, dict), "JSON 미검출"   # ③ 미검출 = 소리나는 실패(상위가 error.log)
try:
    dur = float(os.environ.get("EDIT_DUR") or 0)
except Exception:
    dur = 0.0
cl = j.get("clips")
if not isinstance(cl, list):
    cl = []   # clips 비배열(모델 형식 이탈) = 0후보로 우아한 강등(TypeError 크래시 방지 · 검증⑥ L4)
clips = []
for c in cl[:8]:
    try:
        s, e = float(c.get("s")), float(c.get("e"))
    except Exception:
        continue
    if not (isfinite(s) and isfinite(e)) or s < 0 or e <= s:
        continue
    if dur > 0:   # 전사 범위 실측 클램프 — LLM 환각 스팬 방어
        if s >= dur:
            continue
        e = min(e, dur)
    if e - s < 6:
        continue   # 6초 미만 = 쇼츠 불성립(문장 반쪽 위험)
    e = min(e, s + 90)   # 90초 캡 = 쇼츠 상한(운영자 확정 전 보수)
    clips.append({"s": round(s, 1), "e": round(e, 1),
                  "title": str(c.get("title") or "").strip()[:40],
                  "why": str(c.get("why") or "").strip()[:80]})
clips = clips[:5]
try:
    from zoneinfo import ZoneInfo
    ts = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")   # KST(§표기표준)
except Exception:
    ts = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
doc = {"v": 1, "ts": ts, "dur": round(dur, 1), "clips": clips}
src_url = (os.environ.get("SRC_URL") or "").strip()
if src_url.startswith(("http://", "https://")):
    doc["src"] = src_url   # URL 소스 = 그대로 승계(재렌더 소스 · 파일 업로드는 후속 R2 보관 스텝이 채움)
p = os.path.join(d, "clips.json")
tmp = p + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
os.replace(tmp, p)   # 원자 교체 = 레포 표준(truncate-쓰기 금지 · 검증⑤)
print("clips.json: 후보 {}개".format(len(clips)))
PY
rm -f "${OUTDIR}/stderr.log"
echo "성공 → ${OUTDIR}/clips.json"
