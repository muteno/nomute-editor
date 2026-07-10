#!/usr/bin/env bash
# 입력(env SUBS = SRT/STT 텍스트) → claude -p(헤드리스, /ly 지침 런타임 Read) → 릴스 자막 md
#   → viewer/ly_out/<id>/subs.md. 인증 = CLAUDE_CODE_OAUTH_TOKEN(구독 OAuth·무료).
# 워크플로가 커밋·push(thumb-make 가드 패턴). 실패 = error.log + exit 1.
# 이 스크립트는 SUBS(텍스트/SRT 또는 Whisper STT 결과)만 처리. 영상 URL/파일→Whisper STT는 워크플로(ly-make.yml) 상위 스텝에서.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PROMPT_FILE="prompts/ly-make.md"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL · 260702 SYS-08)
MODEL="$PIPE_MODEL"
source "$ROOT/shared/claude_transient.sh"  # is_quota()/claude_failover()/is_transient() SSOT — 쿼터 한도 시 4계정 자동 로테이션·일시 과부하 재시도(analyze·ask·card와 통일·§📰)
source "$ROOT/shared/claude_meter.sh"   # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard · 옛 동작 호환)
INLINE_TRIES="${INLINE_TRIES:-4}"   # 쿼터 폴오버(서브1→서브2→서브3 = 4계정 체인 깊이·서브3 실호출)·일시 과부하(5xx/Overloaded) 인라인 재시도(15s·30s 백오프) — analyze·ask·card와 동일
ID="${1:?usage: lymake.sh <id> (SUBS=env)}"
OUTDIR="viewer/ly_out/${ID}"; mkdir -p "$OUTDIR"

[ -n "${SUBS:-}" ] || { echo "::error::SUBS(자막/SRT 입력) 비어있음"; echo "exit: 빈 입력" > "$OUTDIR/error.log"; exit 1; }

# 뷰어 버튼 설정(OPTS JSON) → [옵션] 지시줄 — 프롬프트 마커 __LY_OPTS__ 치환(버튼 = 프롬프팅 대체 · 260707)
OPTS_LINES="$(OPTS="${OPTS:-}" python3 - <<'PY'
import json, os, sys
raw = (os.environ.get("OPTS") or "").strip()
if not raw:
    print("- 기본값(지침 그대로).")   # opts 미전달(구 클라·수동 디스패치) = 종전 프롬프트와 실질 동일(회귀 0)
    sys.exit(0)
try:
    o = json.loads(raw)
except Exception:
    o = {}
L = []
lang = o.get("lang") or "auto"
if lang == "ko":
    L.append("- 번역만 출력: 원문 블록 생략, 한글 자막만.")   # 지침 예약어(통합 모드) 재사용 금지 — 용어 역전 혼란 차단(평의회)
elif lang == "dual":
    L.append("- 조각마다 원문 블록 + 한글 블록 병기. 단 소스가 한국어면 이 옵션은 무시하고 지침 한국어 원본 방식 그대로(거부·안내문 출력 금지 — 항상 # 제목부터).")
elif lang == "src":
    L.append("- 의역 금지: 받아쓴 원문 그대로(오탈자·띄어쓰기만 교정) — 번역 블록 생략.")
if (o.get("tone") or "sns") == "plain":
    L.append("- 톤: SNS 감성 의역 최소화 — 담백한 직역체.")
if o.get("filler", True):
    L.append("- 군더더기(음·어 같은 무의미 감탄사 낱말)만 자막에서 뺀다 — 의미 있는 말은 삭제 금지(지침 원칙 유지).")
if o.get("keyword", True):
    L.append("- 키워드 강조: 맨 끝 타이밍 JSON의 ko 필드에만 핵심 단어 1개(최대 2개)를 *별표*로 감싼다 — ① 표·② 복사 블록 본문엔 별표 금지(순수 자막 유지).")
print("\n".join(L) if L else "- 기본값(지침 그대로).")
PY
)"
prompt="$(cat "$PROMPT_FILE")"
prompt="${prompt/__LY_OPTS__/$OPTS_LINES}"
prompt="$prompt
${SUBS}"

# 인라인 재시도 — 쿼터 한도면 대체 계정 전환(claude_failover·서브1→서브2→서브3), 일시 과부하(5xx/Overloaded)면 백오프 재시도. 성공·LYMAKE_FAILED(막다른길)는 즉시 탈출(쿼터 낭비 0).
inline_delay=15
for attempt in $(seq 1 "$INLINE_TRIES"); do
  out="$(printf '%s' "$prompt" | METER_SRC=ly METER_REF="$ID" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
        --model "$MODEL" \
        --effort max \
        --allowedTools "Read,Glob,Grep" \
        --disallowedTools "Write,Edit,NotebookEdit,Bash,Task,WebFetch,WebSearch" \
        --max-turns 40 \
        2> "${OUTDIR}/stderr.log")"
  rc=$?
  if { [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '^#' <<<"$out"; } || grep -qm1 '^LYMAKE_FAILED' <<<"$out"; then
    break
  fi
  if claude_failover "$out$(cat "${OUTDIR}/stderr.log" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 1단계씩 전환·재시도(서브1→서브2→서브3 · SSOT)
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
# 꼬리 타이밍 JSON 블록 → subs.json 분리(번인·SRT용 기계 데이터 · 폼 표시 전 제거) — 없거나 깨져도 무해(번인이 segments.json 폴백)
#   평의회 반영(260707): 매치되면 파싱 실패여도 블록은 표시본에서 제거(원시 JSON 노출 차단) · 본문 잔여 *별표* 클린(복붙 오염 2중 방어)
#   3층 방어(CLAUDE.md §📰 LLM 형식 보증 · 평의회4 260709): LLM 출력의 펜스 변형은 확률적 = 관용 파싱 —
#     ①펜스 관용(json 태그 생략·대문자·닫는 펜스 누락·펜스 뒤 산문 소량) ②펜스 없는 꼬리 raw JSON(raw_decode)
#     ③미검출 = ::warning:: 카나리아(Actions 로그 조기발견 · segments.json 폴백 = 외국어 원문 번인 열화라 침묵 금지)
OPTS="${OPTS:-}" python3 - "$OUTDIR" <<'PY' || echo "타이밍 JSON 분리 실패(무해 · segments.json 폴백)"
import json, re, sys, os
d = sys.argv[1]; p = os.path.join(d, "subs.md")
md = open(p, encoding="utf-8").read()
j, strip_at = None, -1
# ① '"segs"' 담은 *마지막* 펜스 블록만 채택(재평의회4: 파싱 실패 시 앞쪽 본문 예시로 후진하면 오채택+과제거 → 꼬리 한정)
#    ```json/```JSON/무태그·태그 앞 공백·닫는 펜스 누락(\Z) 관용. ```python 등 딴 태그 펜스는 정규식 구조상 불매치 = 본문 보호.
fences = [m for m in re.finditer(r"```[ \t]*(?:json)?\s*(\{[\s\S]*?)(?:```|\Z)", md, re.I) if '"segs"' in m.group(1)]
if fences:
    m = fences[-1]
    strip_at = m.start()   # 파싱 실패여도 꼬리 기계 블록 표시 노출은 차단(제거 = 꼬리 한정)
    try:
        j = json.loads(m.group(1).strip())
    except Exception:
        print("::warning::타이밍 JSON 파싱 실패(꼬리 블록 형식 이탈) — segments.json 폴백")
# ② 펜스 없는 꼬리 raw JSON — 코드펜스 *밖*(``` 짝수 패리티) + 줄머리(들여쓰기 허용) '{'를 뒤에서부터 raw_decode(재평의회4)
if j is None and strip_at < 0:
    dec = json.JSONDecoder()
    for m in reversed(list(re.finditer(r"^[ \t]*\{", md, re.M))):
        if md[:m.start()].count("```") % 2:
            continue   # 열린 코드펜스 안 = 표시용 본문(오채택·여는 펜스 잔존 방지)
        try:
            obj, end = dec.raw_decode(md, m.end() - 1)   # '{' 위치부터 = 들여쓴 꼬리 JSON도 검출
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("segs") and len(md[end:].strip()) <= 240:
            j, strip_at = obj, m.start()
            break
if isinstance(j, dict):
    segs = [s for s in (j.get("segs") or [])
            if isinstance(s.get("s"), (int, float)) and isinstance(s.get("e"), (int, float))
            and (s.get("ko") or s.get("src"))]
    if segs:
        with open(os.path.join(d, "subs.json"), "w", encoding="utf-8") as f:
            json.dump({"v": 1, "segs": segs}, f, ensure_ascii=False, separators=(",", ":"))
        print("subs.json 분리: {}조각".format(len(segs)))
    else:
        print("::warning::타이밍 JSON 유효 조각 0(형식 이탈) — segments.json 폴백")   # 파싱 성공·조각 0 침묵 봉합(재평의회4)
elif strip_at < 0:
    print("::warning::타이밍 JSON 미검출 — 모델 형식 이탈 가능(segments.json 폴백·번인은 원문 타이밍)")   # ③ 카나리아
if strip_at >= 0:
    md = md[:strip_at].rstrip() + "\n"   # 파싱 성공 여부와 무관 — 기계 블록은 표시본에서 항상 제거
    md = re.sub(r"\n#{2,3}[^\n]*타이밍[^\n]*\n$", "\n", md)   # 블록 직전 안내 소머리 잔재 정리(있을 때만)
try:
    o = json.loads(os.environ.get("OPTS") or "{}")
except Exception:
    o = {}
if o.get("keyword", True) and (os.environ.get("OPTS") or "").strip():
    md = re.sub(r"(?<!\*)\*([^*\n]{1,24})\*(?!\*)", r"\1", md)   # 표시·복사 텍스트의 잔여 단일 *별표*만 제거(subs.json 전용 — 모델 변동성 방어) · 경계 가드 = **볼드**·표 헤더 오매칭 차단(재검 3인)
open(p, "w", encoding="utf-8").write(md)
PY
rm -f "${OUTDIR}/stderr.log"
echo "성공 → ${OUTDIR}/subs.md ($(wc -c < "${OUTDIR}/subs.md") bytes)"
