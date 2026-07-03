#!/usr/bin/env bash
# 뷰어 ✏️요약 수정 요청 — queue/<FILE>.md 의 IG·Thread 초안만 운영자 지시(INSTRUCTION)대로 재작성.
# ⛔ 재요약 금지: 기사 재수집·재분석 안 함. 기존 요약(이 파일)을 입력으로 받아 그 두 블록만 다시 쓴다(구독 쿼터 절약).
# 흐름: 블록 추출 → 프롬프트(지침 주입) → claude -p(구독 OAuth) 재작성 → 스크립트가 in-place 치환 후 커밋.
# 인증·디스패치 패턴은 ask.sh 미러(구독·무료). Claude 는 Write/Edit/Bash 불허 — 파일 저장은 스크립트가 한다.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
MODEL="claude-opus-4-8"
source "$ROOT/shared/claude_transient.sh"   # is_quota/claude_failover — 계정 사용량 한도 시 대체 계정 1단계씩 전환(서브1→서브2 · 3계정 체인)
source "$ROOT/shared/claude_meter.sh"       # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard · 옛 동작 호환)

FILE="${FILE:-}"                 # 큐 항목 id(확장자 없이) — 워크플로 input
INSTRUCTION="${INSTRUCTION:-}"   # 재작성 지시(자연어)
FILE="${FILE%.md}"

# 안전 검증 — file 패턴(경로주입 차단) · 빈 지시 컷.
if ! printf '%s' "$FILE" | grep -qE '^[0-9]{6}-[0-9]{4}-[A-Za-z0-9._-]{1,80}$'; then
  echo "::error::잘못된 file: '$FILE'"; exit 1
fi
TARGET="queue/${FILE}.md"
if [ ! -f "$TARGET" ]; then echo "::error::대상 없음: $TARGET"; exit 1; fi
if [ -z "${INSTRUCTION// }" ]; then echo "::error::빈 지시"; exit 1; fi

# 지침 SSOT 강제 주입(요약과 동일 summary 세트) — 톤·포맷 기준 일치.
source "$ROOT/shared/inject_guidelines.sh"
GBLOCK="$(guidelines_block summary)"

# 기존 IG·Thread 섹션 추출(헤더 '### [IG'/'### [Thread' 부터 다음 '### ' 직전까지).
IG_OLD="$(python3 - "$TARGET" IG <<'PY'
import sys, re
txt = open(sys.argv[1], encoding='utf-8').read()
lines = txt.splitlines(keepends=True)
key = sys.argv[2]
out, grab = [], False
for ln in lines:
    if re.match(r'^###\s', ln):
        if grab: break
        grab = ln.lstrip('#').strip().startswith('[' + key)
    if grab: out.append(ln)
sys.stdout.write(''.join(out))
PY
)"
TH_OLD="$(python3 - "$TARGET" Thread <<'PY'
import sys, re
txt = open(sys.argv[1], encoding='utf-8').read()
lines = txt.splitlines(keepends=True)
key = sys.argv[2]
out, grab = [], False
for ln in lines:
    if re.match(r'^###\s', ln):
        if grab: break
        grab = ln.lstrip('#').strip().startswith('[' + key)
    if grab: out.append(ln)
sys.stdout.write(''.join(out))
PY
)"

if [ -z "${IG_OLD// }" ] || [ -z "${TH_OLD// }" ]; then
  echo "::error::IG/Thread 블록을 못 찾음 — 포맷 불일치($TARGET)"; exit 1
fi

# 프롬프트 = 지침(고정부) → 지시·원본 블록(가변부). 출력 = 센티넬로 감싼 재작성 두 블록만.
prompt="${GBLOCK}

[★ 요약 수정 요청 모드 — 운영자가 이미 만들어진 요약의 IG·Thread 초안이 편향·오류라며 재작성을 요청했다.
 ⛔ 기사 재수집·재요약·새 사실 추가 금지. 아래 '원본 IG/Thread 블록'에 이미 있는 내용만으로 재작성한다(WebSearch·Read로 기사 다시 안 봄).
 ✅ 운영자 지시대로 두 블록을 다시 써라(방향 무관 — 편향 제거·중립화·톤다운, *또는 더 보수·우편향·비판 강화* 등 운영자가 요구한 방향 그대로). 위 지침의 포맷·구조·머리표(🔎/📍/⚡)·코드펜스(text 코드블록)·길이 감각은 그대로 유지.
 📊 **편향 게이지는 재작성 결과 기준으로 다시 채점한다(stale 금지·운영자 260625)**: 말미 '📊 편향:' 줄에서 — 원문 N값(있으면)은 그대로(기사 원문은 안 변함), **요약/큐레이션 M값·색 네모·라벨은 재작성된 텍스트의 실제 편향으로 갱신**(운영자가 우/좌 방향을 줬으면 그 방향으로 움직인 결과를 반영 — 예: 중립 5 → 우편향 주문이면 8/10 🟥 강우). 척도 = 위 지침 [📊 편향 게이지](1=강좌 ~ 10=강우 · 5~6 중립).
 ⚠️ 단 운영자 지시가 절대 우선 룰(사실 무결성·원문 왜곡·강도 증폭 금지)을 넘는 '말도 안 되는 범위'(없는 사실 날조·의미 왜곡)면 거기까진 따르지 말고 가능한 선까지만 반영(게이지도 실제 반영된 만큼만).
 ✅ 헤더 '### [IG …]' · '### [Thread …]' 줄도 포함해 섹션 통째로 출력(길이 토큰은 자연스럽게 갱신 가능).
 ⚠️ 길이 하드 상한 절대 준수(재작성·중립화·톤다운으로 *늘리지 마라*): **Thread 본문 500자 초과 절대 금지**(\`⚡\` 출처 포함·면책 줄 제외 — 플랫폼이 500자 초과를 게시 못 함 · 목표 400~470) · **IG 800자 초과 금지**. 길어지면 어미·조사를 깎지 말고 문장/📍 단위로 통째 덜어 상한 이내로 맞춰라(위 지침 [Thread 상한 압박]·[글자수 측정]·[본문 종결] 기준 그대로). 출력 전 Thread 글자수를 스스로 세어 500 이하인지 확인하라.
 출력 형식 — 아래 센티넬을 정확히 그대로, 그 사이에만 재작성된 블록을 넣는다. 사족·설명 금지.]

운영자 지시:
${INSTRUCTION}

원본 IG 블록:
${IG_OLD}

원본 Thread 블록:
${TH_OLD}

출력(아래 센티넬 정확히 사용):
<<<NOMUTE_IG_START>>>
(재작성된 ### [IG …] 섹션 전체)
<<<NOMUTE_IG_END>>>
<<<NOMUTE_THREAD_START>>>
(재작성된 ### [Thread …] 섹션 전체)
<<<NOMUTE_THREAD_END>>>
<<<NOMUTE_BIAS_START>>>
(재작성 결과의 최종 편향 = 프론트매터용 한 줄 'M/10 색네모 라벨' · 예: 8/10 🟥 강우 — 원문 아닌 *요약/큐레이션 M* 기준)
<<<NOMUTE_BIAS_END>>>"

# 헤드리스 — 읽기 도구만 허용(파일 저장은 스크립트). 무중단(권한대기 차단).
# 단발 호출이라 쿼터 한도면 대체 계정으로 1단계씩 전환 후 재시도(서브1→서브2 · 3계정 체인 · SSOT claude_transient.sh).
for _try in 1 2 3; do
  out="$(printf '%s' "$prompt" | METER_SRC=revise METER_REF="$FILE" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
        --model "$MODEL" \
        --effort max \
        --allowedTools "Read,Glob,Grep" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch" \
        --max-turns 12 \
        2> "/tmp/revise-${FILE}.err")"
  rc=$?
  { [ $rc -eq 0 ] && [ -n "${out// }" ]; } && break
  claude_failover "$out$(cat "/tmp/revise-${FILE}.err" 2>/dev/null)" && continue   # 쿼터 → 대체 계정 전환·재시도
  break
done

if [ $rc -ne 0 ] || [ -z "${out// }" ]; then
  echo "::error::claude 실패(rc=$rc)"; cat "/tmp/revise-${FILE}.err" 2>/dev/null | head -40; exit 1
fi

# 센티넬에서 재작성 블록 추출 + in-place 치환 → 같은 파일 저장(프론트매터·시사점·기타 섹션 무손상).
python3 - "$TARGET" "$out" <<'PY'
import sys, re
path, out = sys.argv[1], sys.argv[2]

def between(s, a, b):
    m = re.search(re.escape(a) + r'\n?(.*?)\n?' + re.escape(b), s, re.S)
    return m.group(1).strip('\n') if m else None

ig = between(out, '<<<NOMUTE_IG_START>>>', '<<<NOMUTE_IG_END>>>')
th = between(out, '<<<NOMUTE_THREAD_START>>>', '<<<NOMUTE_THREAD_END>>>')
bias_new = between(out, '<<<NOMUTE_BIAS_START>>>', '<<<NOMUTE_BIAS_END>>>')   # 재채점된 요약 M(프론트매터 형식) — 없거나 형식 깨지면 아래서 갱신 생략
if not ig or not th:
    sys.exit('::error::센티넬 누락 — 재작성 출력 파싱 실패')
if not ig.lstrip().startswith('### [IG') or not th.lstrip().startswith('### [Thread'):
    sys.exit('::error::재작성 블록 헤더 불일치(### [IG / ### [Thread 아님)')

txt = open(path, encoding='utf-8').read()
lines = txt.splitlines(keepends=True)

def replace_section(lines, key, newblock):
    start = end = None
    for i, ln in enumerate(lines):
        if re.match(r'^###\s', ln):
            if start is None and ln.lstrip('#').strip().startswith('[' + key):
                start = i
            elif start is not None:
                end = i; break
    if start is None:
        sys.exit('::error::원본 %s 섹션 없음' % key)
    if end is None:
        end = len(lines)
    block = newblock.rstrip('\n') + '\n\n'   # 다음 섹션과 한 줄 띄움(원본 포맷 유지)
    return lines[:start] + [block] + lines[end:]

lines = replace_section(lines, 'IG', ig)
lines = replace_section(lines, 'Thread', th)

# 회차(rev) 프론트매터 증가 — IG/Thread 치환과 '같은 단일 write'로 원자 반영.
# (분리 write면 치환만 성공·rev 실패 시 부분반영 → 완료감지 영영 실패. 한 write로 둘 다 or 둘 다 안 됨.)
txt2 = ''.join(lines)
fm_m = re.match(r'(.*?^---\s*\n)(.*?)(\n---\s*\n)(.*)$', txt2, re.S | re.M)
if not fm_m:
    sys.exit('::error::프론트매터 못 찾음 — rev 증가 실패(원본 미변경)')
fhead, fmeta, fsep, frest = fm_m.groups()
rev_m = re.search(r'^rev:\s*(\d+)\s*$', fmeta, re.M)
if rev_m:
    nrev = int(rev_m.group(1)) + 1
    fmeta = re.sub(r'^rev:\s*\d+\s*$', 'rev: %d' % nrev, fmeta, count=1, flags=re.M)
else:
    nrev = 1
    fmeta = fmeta.rstrip('\n') + '\nrev: 1'

# 편향 게이지 재채점 반영 — 재작성된 요약 M을 프론트매터 bias 로 갱신(stale 차단·운영자 260625).
# 원문 N(자유요약 줄)·자유요약 본문은 안 건드림 = 기사 원문 편향 고정. 센티넬 없거나 'N/10' 형식 아니면 갱신 생략(원본 bias 유지 = 하위호환·안전).
bset = ''
if bias_new and re.match(r'^\s*\d{1,2}\s*/\s*10\b', bias_new):
    bnew = re.sub(r'\s+', ' ', bias_new.strip().replace('"', '')).strip()
    if re.search(r'^bias:\s*.*$', fmeta, re.M):
        fmeta = re.sub(r'^bias:\s*.*$', 'bias: "%s"' % bnew, fmeta, count=1, flags=re.M)
    else:
        fmeta = fmeta.rstrip('\n') + '\nbias: "%s"' % bnew
    bset = ' · bias => ' + bnew
open(path, 'w', encoding='utf-8').write(fhead + fmeta + fsep + frest)   # 단일 write = 원자 반영(블록+rev+bias)
print('치환+rev 완료:', path, '· rev =>', nrev, bset)
PY
prc=$?
if [ $prc -ne 0 ]; then echo "::error::치환/rev 실패(원본 미변경)"; exit 1; fi

echo "수정 반영 → $TARGET"
