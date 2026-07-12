#!/usr/bin/env bash
# X 국가별 트렌드 번역·주제 배치(운영자 260712 draft) — xtrends 원문 단어를 {ko(한국어 표기)·tp(주제)} 사전으로 만들어
# 사이드카 viewer/sns_xtr_ko.json에 누적(뷰어가 조인 = 한글 위·영문 아래 이중 표기 · 사전 없으면 원문 폴백).
# 게이트 3중: ① SNS_XTR=1(§📰-e 카나리아 — draft = 기본 OFF·dispatch 실측 후 승격) ② 신규 단어 0 = LLM 스킵(기존 사전 재사용 = 토큰 0 · 단어는 런 간 대부분 지속 = 증분 번역)
# ③ 실패 = fail-soft(직전 사전 유지 · rc 0 — 수집 커밋 비차단).
# 모델 = claude-sonnet-5 기본(짧은 룰북 단발 분류 = gate/breaking judge 동축 · turns=1·도구 0·effort 미사용 §🤖-b).
# ⚠ §🤖-b sonnet 예외 등재는 gate_judge·breaking_judge 2종뿐 — 이 스크립트로의 확대 = 운영자 확인 필수(draft PR 승인 = 그 절차 · 머지 전 미확정).
# --safe-mode(stdin 자기완결 · --bare 절대 금지 = OAuth 즉사 §📰-d) · 폴오버 SSOT 경유(§📰-f).
set -u
[ "${SNS_XTR:-0}" = "1" ] || { echo "xtr_judge: OFF(SNS_XTR!=1) — 스킵"; exit 0; }
cd "$(git rev-parse --show-toplevel)"
. shared/claude_transient.sh
MODEL="${SNS_XTR_MODEL:-claude-sonnet-5}"
OUT_JSON="viewer/sns_xtr_ko.json"

# ── 1단: 현재 단어 수집 + 기존 사전 대조 → 신규 단어만 추출(증분 · 재진입 재번역은 드묾 = 허용) ──
NEED="$(python3 - <<'PY'
import json, hashlib
try:
    xt = (json.load(open('viewer/sns_trends.json')).get('xtrends') or {})
except Exception:
    print(''); raise SystemExit
words, seen = [], set()
for k in ('ww', 'kr', 'us', 'jp', 'br', 'uk', 'in'):
    for it in (xt.get(k) or []):
        t = (it.get('t') or '').strip()
        if t and t.lower() not in seen:
            seen.add(t.lower()); words.append(t)
prev = {}
try:
    prev = json.load(open('viewer/sns_xtr_ko.json')).get('map') or {}
except Exception:
    pass
need = [w for w in words if w not in prev]
print(hashlib.sha256('\n'.join(sorted(words)).encode()).hexdigest()[:16])
for w in need:
    print(w)
PY
)" || { echo "::warning::xtr_judge 단어 수집 실패 — 직전 사전 유지"; exit 0; }
SHA="$(printf '%s\n' "$NEED" | head -1)"
NEWW="$(printf '%s\n' "$NEED" | tail -n +2 | sed '/^$/d')"
[ -z "$SHA" ] && { echo "xtr_judge: xtrends 없음 — 스킵"; exit 0; }

out=""
if [ -n "$NEWW" ]; then
  NW_CNT="$(printf '%s\n' "$NEWW" | wc -l | tr -d ' ')"
  echo "xtr_judge: 신규 단어 ${NW_CNT}건 번역·분류"
  PROMPT="너는 X(트위터) 실시간 트렌드 단어의 한국어 표기·주제 분류기다. 아래 각 단어에 대해 JSON 객체 하나만 출력하라.
형식: {\"<원문 그대로>\": {\"ko\": \"<한국어 번역·통용 표기>\", \"tp\": \"<주제>\"}, ...} — 모든 입력 단어를 키로 포함.
규칙: ko = 자연스러운 한국어(고유명사 = 국내 통용 한글 표기 · 해시태그 = # 유지한 채 의미 번역 · 이미 한국어거나 의미 불명확 = 원문 그대로) · tp = {스포츠, 연예, 음악, 게임, 정치사회, 경제테크, 기타} 중 정확히 하나 · JSON 외 다른 텍스트·코드펜스·설명 절대 출력 금지.

$NEWW"
  for _try in 1 2 3 4; do
    out="$(printf '%s' "$PROMPT" | timeout 240 claude -p --model "$MODEL" --safe-mode --max-turns 1 \
      --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,WebSearch,WebFetch,Task,NotebookEdit,TodoWrite" 2>/tmp/xtr.err)"; rc=$?
    if [ $rc -ne 0 ] || [ -z "$out" ]; then
      if claude_failover "$out$(cat /tmp/xtr.err 2>/dev/null)"; then continue; fi   # 쿼터 = 4계정 체인 1단씩(§📰-f)
      echo "::warning::xtr_judge 번역 실패(rc=$rc) — 직전 사전 유지(fail-soft)"; exit 0
    fi
    break
  done
else
  echo "xtr_judge: 신규 단어 0 — LLM 스킵(기존 사전 프룬만 · 토큰 0)"
fi

# ── 2단: 병합·프룬(현재 단어만 유지 = 자동 캡) · 내용 동일 = 미기록(커밋 노이즈 0) ──
XTR_OUT="$out" XTR_SHA="$SHA" python3 - <<'PY'
import json, os, re, datetime
KST = datetime.timezone(datetime.timedelta(hours=9))
TOPICS = {'스포츠', '연예', '음악', '게임', '정치사회', '경제테크', '기타'}
xt = (json.load(open('viewer/sns_trends.json')).get('xtrends') or {})
words, seen = [], set()
for k in ('ww', 'kr', 'us', 'jp', 'br', 'uk', 'in'):
    for it in (xt.get(k) or []):
        t = (it.get('t') or '').strip()
        if t and t.lower() not in seen:
            seen.add(t.lower()); words.append(t)
prev_map, prev_doc = {}, {}
try:
    prev_doc = json.load(open('viewer/sns_xtr_ko.json'))
    prev_map = prev_doc.get('map') or {}
except Exception:
    pass
new = {}
raw = (os.environ.get('XTR_OUT') or '').strip()
if raw:
    m = re.search(r'\{.*\}', raw, re.S)   # 코드펜스·서두 잡음 방어(첫 { ~ 끝 })
    try:
        for w, e in (json.loads(m.group(0)) if m else {}).items():
            if not isinstance(e, dict):
                continue
            ko = str(e.get('ko') or '').strip()[:80]
            tp = str(e.get('tp') or '').strip()
            if ko:
                new[w] = {'ko': ko, 'tp': tp if tp in TOPICS else '기타'}
    except Exception as ex:
        print('::warning::xtr_judge JSON 파싱 실패 — 신규분 미반영(기존 사전만 프룬):', ex)
merged = {}
for w in words:   # 프룬 = 현재 트렌드 단어만 유지(자동 캡 · 이탈 단어 재진입 = 재번역 허용 비용)
    e = new.get(w) or prev_map.get(w)
    if e:
        merged[w] = e
if merged == prev_map and (prev_doc.get('src_hash') or '') == (os.environ.get('XTR_SHA') or ''):
    print('xtr_judge: 사전 변동 없음 — 미기록')
else:
    json.dump({'updated': datetime.datetime.now(KST).isoformat(timespec='seconds'),
               'src_hash': os.environ.get('XTR_SHA') or '', 'map': merged},
              open('viewer/sns_xtr_ko.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print('xtr_judge: 사전 저장 — %d단어(신규 %d)' % (len(merged), len(new)))
PY
exit 0
