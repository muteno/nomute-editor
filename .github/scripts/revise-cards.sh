#!/usr/bin/env bash
# 뷰어 🃏카드 수정 요청 — cards/<FILE>/cards.md(카드 프롬프트 전체)를 운영자 지시(INSTRUCTION)대로 재기획·재작성.
# ⛔ 재요약·재수집 금지: 기존 요약(queue/<FILE>.md)을 *맥락*으로만 받고, 카드 플랜(텍스트·이미지프롬프트)만 다시 쓴다.
# ⛔ 제미나이 0(재슛 안 함): 이미지 파일은 손대지 않는다 — 프롬프트(텍스트)만 갱신. 운영자가 원하면 '슛'으로 별도 재촬영.
# 흐름: cards.md+요약 추출 → 프롬프트(카드 지침 주입) → claude -p(구독 OAuth) 재작성 → 스크립트가 cards.md 치환 + status.json updated 갱신 후 커밋.
# 인증·디스패치·계측 = revise.sh 미러(구독·무료·per-run 과금 0). Claude 는 Write/Edit/Bash 불허 — 파일 저장은 스크립트가 한다.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL · 260702 SYS-08)
MODEL="$PIPE_MODEL"
source "$ROOT/shared/claude_transient.sh"   # is_quota/claude_failover — 계정 한도 시 대체 계정 1단계씩 전환(서브1→서브2)
source "$ROOT/shared/claude_meter.sh"       # claude_meter() SSOT — 토큰 사용량 계측

FILE="${FILE:-}"                 # 큐 항목 id(확장자 없이) — 워크플로 input
INSTRUCTION="${INSTRUCTION:-}"   # 재기획 지시(자연어)
FILE="${FILE%.md}"

# 안전 검증 — file 패턴(경로주입 차단) · 빈 지시 컷.
if ! printf '%s' "$FILE" | grep -qE '^[0-9]{6}-[0-9]{4}-[A-Za-z0-9._-]{1,80}$'; then
  echo "::error::잘못된 file: '$FILE'"; exit 1
fi
CARDS="cards/${FILE}/cards.md"
STATUS="cards/${FILE}/status.json"
QFILE="queue/${FILE}.md"
if [ ! -f "$CARDS" ]; then echo "::error::카드 없음: $CARDS"; exit 1; fi
if [ -z "${INSTRUCTION// }" ]; then echo "::error::빈 지시"; exit 1; fi

# 지침 SSOT 강제 주입(카드 세트 = cardmake와 동일 'card') — 카드 포맷·머리표·이미지프롬프트 규칙 일치.
source "$ROOT/shared/inject_guidelines.sh"
GBLOCK="$(guidelines_block card)"

CARDS_OLD="$(cat "$CARDS")"
# 요약 본문(맥락) — 있으면 프론트매터 제거하고 본문만(재작성 근거·사실 고정용). 없어도 진행(카드만으로).
SUMMARY_CTX=""
if [ -f "$QFILE" ]; then
  SUMMARY_CTX="$(python3 - "$QFILE" <<'PY'
import sys, re
txt = open(sys.argv[1], encoding='utf-8').read()
m = re.match(r'^---\s*\n.*?\n---\s*\n(.*)$', txt, re.S)
sys.stdout.write((m.group(1) if m else txt).strip())
PY
)"
fi

# 프롬프트 = 카드 지침(고정부) → 지시·요약맥락·원본 카드(가변부). 출력 = 센티넬로 감싼 재작성 cards.md 전체.
prompt="${GBLOCK}

[★ 카드 수정 요청 모드 — 운영자가 이미 만들어진 '카드뉴스 프롬프트(cards.md)'의 진행 방식·맥락이 마음에 안 든다며 재기획을 요청했다.
 ⛔ 기사 재수집·재요약·새 사실 추가 금지. 아래 '요약 맥락'과 '원본 카드'에 이미 있는 내용만으로 재기획한다(WebSearch·Read로 기사 다시 안 봄).
 ✅ 운영자 지시대로 카드 플랜 전체를 다시 써라 — 카드 순서·장수·흐름(起承轉結)·각 카드의 텍스트와 이미지 프롬프트를 맥락에 맞게 재구성. 지시가 특정 방향(예: 더 차분하게·시사점 강조·도입 강화)을 주면 전체를 그 방향으로.
 ✅ 위 카드 지침의 출력 포맷을 100% 그대로 유지: 최상단 '# 제목' 한 줄 → 각 카드 '### [카드 N]' → '**텍스트**' + \`\`\`text 코드펜스 + '**이미지 프롬프트**' + \`\`\`text 코드펜스 (+ 있으면 '**검색어**' 코드펜스). 머리표·라벨·코드펜스 구조 어김없이.
 ✅ 강조는 의미 완결 단위 통째('\`*매번 그 자리였다*\`' — 어절 중간·서술어 분리 금지).
 ⚠️ 이미지 프롬프트의 언어·스타일(영문 manhwa 등)·구도 어휘는 원본 카드의 관례를 계승(같은 화풍 일관). 텍스트는 한국어.
 출력 형식 — 아래 센티넬을 정확히 그대로, 그 사이에 재작성된 cards.md '전체'를 넣는다. 사족·설명·코드펜스 밖 잡담 금지.]

운영자 지시:
${INSTRUCTION}

요약 맥락(사실 고정 — 재수집 금지):
${SUMMARY_CTX:-（요약 없음 — 원본 카드 내용만으로 재기획）}

원본 카드(cards.md 전체):
${CARDS_OLD}

출력(아래 센티넬 정확히 사용):
<<<NOMUTE_CARDS_START>>>
(재작성된 cards.md 전체 — '# 제목'부터 마지막 카드까지)
<<<NOMUTE_CARDS_END>>>"

# 헤드리스 — 읽기 도구만 허용(파일 저장은 스크립트). 무중단. 쿼터 한도면 대체 계정 1단계씩 폴오버(서브1→서브2 · 3계정 체인).
for _try in 1 2 3; do
  out="$(printf '%s' "$prompt" | METER_SRC=revise-cards METER_REF="$FILE" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
        --model "$MODEL" \
        --effort max \
        --allowedTools "Read,Glob,Grep" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch" \
        --max-turns 12 \
        2> "/tmp/revise-cards-${FILE}.err")"
  rc=$?
  { [ $rc -eq 0 ] && [ -n "${out// }" ]; } && break
  claude_failover "$out$(cat "/tmp/revise-cards-${FILE}.err" 2>/dev/null)" && continue
  break
done

if [ $rc -ne 0 ] || [ -z "${out// }" ]; then
  echo "::error::claude 실패(rc=$rc)"; cat "/tmp/revise-cards-${FILE}.err" 2>/dev/null | head -40; exit 1
fi

# 센티넬에서 재작성 cards.md 추출 + 포맷 검증 → cards.md 치환 + status.json updated 갱신(KST).
python3 - "$CARDS" "$STATUS" "$out" <<'PY'
import sys, re, json, os
from datetime import datetime, timezone, timedelta

cards_path, status_path, out = sys.argv[1], sys.argv[2], sys.argv[3]

m = re.search(r'<<<NOMUTE_CARDS_START>>>\n?(.*?)\n?<<<NOMUTE_CARDS_END>>>', out, re.S)
if not m:
    sys.exit('::error::센티넬 누락 — 재작성 출력 파싱 실패')
newmd = m.group(1).strip('\n') + '\n'

# 포맷 검증: 최소 카드 1장 + 코드펜스 짝 맞음(viewer 파서 깨짐 방지).
ncards = len(re.findall(r'(?m)^###\s+\[카드', newmd))
nfence = newmd.count('```')
if ncards < 1:
    sys.exit('::error::재작성본에 카드(### [카드 N]) 없음 — 포맷 깨짐(원본 미변경)')
if nfence % 2 != 0:
    sys.exit('::error::코드펜스(```) 홀수 = 깨짐(원본 미변경)')

open(cards_path, 'w', encoding='utf-8').write(newmd)

# status.json updated 갱신(KST · §📐 시각표준) — viewer가 a.cards.updated 변화로 완료 감지 + ensureDetail ver 무효화(detail 재로드).
# crev(카드 수정 회차)도 증가 = 표시·디버그용. state/images 등 다른 필드는 보존.
KST = timezone(timedelta(hours=9))
try:
    st = json.load(open(status_path, encoding='utf-8')) if os.path.exists(status_path) else {}
except Exception:
    st = {}
st['updated'] = datetime.now(KST).isoformat(timespec='seconds')
st['crev'] = int(st.get('crev', 0) or 0) + 1
json.dump(st, open(status_path, 'w', encoding='utf-8'), ensure_ascii=False)
print('카드 재작성 완료:', cards_path, '· 카드', ncards, '장 · crev =>', st['crev'])
PY
prc=$?
if [ $prc -ne 0 ]; then echo "::error::치환/status 실패(원본 미변경)"; exit 1; fi

echo "카드 수정 반영 → $CARDS"
