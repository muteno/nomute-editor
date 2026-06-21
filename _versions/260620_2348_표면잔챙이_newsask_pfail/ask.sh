#!/usr/bin/env bash
# asks/*.json (뷰어 ✨요약 요청 = 자연어 text + base64 캡처 images[]) 를 순회하며
# Claude Code 헤드리스(claude -p)로 해석 → 제일 메이저 기사를 WebSearch로 찾아(또는 본문 URL) 큐레이션
# 다이제스트 생성 → queue/ 저장, 처리한 ask 삭제, 실패는 asks/failed/ 격리. (analyze.sh 미러 — 입력만 멀티모달)
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PROMPT_FILE="prompts/news-analysis.md"
MODEL="claude-opus-4-8"

# 지침 SSOT 강제 주입(analyze와 동일 summary 세트) — 출력 포맷·품질기준 일치, GVER 도장.
source "$ROOT/shared/inject_guidelines.sh"
source "$ROOT/shared/claude_health.sh"   # 시스템성(인증·쿼터) 실패 → 사용자 메시지(프로필 점등)
GVER="$(guidelines_version summary)"
GBLOCK="$(guidelines_block summary)"
echo "지침 버전(summary): ${GVER}"

# 이번 런에서 *새로* 실패한 base만 기록(누적 asks/failed 전체 아님) → Surface 스텝이 이것만 보고 빨강 판정.
# (옛 실패가 asks/failed/에 남아도 매 런 빨강 뜨던 stale-red 차단 · 옛 실패는 뷰어 대기열이 24h 표면화. 운영자 260620.)
ASK_FAIL_RUN="${RUNNER_TEMP:-/tmp}/ask_fail_run"; : > "$ASK_FAIL_RUN"

shopt -s nullglob
files=(asks/*.json)
if [ ${#files[@]} -eq 0 ]; then
  echo "asks 비어있음 — 종료"
  exit 0
fi

for f in "${files[@]}"; do
  base="$(basename "$f" .json)"          # YYYYMMDD-HHMMSS-xxxxx
  stamp="$(date +%y%m%d-%H%M)"
  echo "::group::요약 요청: $base"

  # JSON 파싱: 텍스트 추출 + 이미지(data URL) → 파일 디코드(Claude Read 가 볼 수 있게)
  workdir="$(mktemp -d)"
  text="$(python3 -c "import json; print(json.load(open('$f')).get('text',''))" 2>/dev/null || true)"
  python3 - "$f" "$workdir" <<'PY' 2>/dev/null || true
import json, sys, base64, re
d = json.load(open(sys.argv[1])); wd = sys.argv[2]
for i, u in enumerate((d.get('images') or [])[:8]):
    m = re.match(r'data:image/\w+;base64,(.*)', u or '')
    if not m:
        continue
    open(f"{wd}/img-{i+1}.jpg", "wb").write(base64.b64decode(m.group(1)))
PY
  imglist=""
  for im in "$workdir"/img-*.jpg; do [ -e "$im" ] && imglist="${imglist}- ${im}\n"; done

  if [ -z "${text// }" ] && [ -z "$imglist" ]; then
    mkdir -p asks/failed; echo "빈 요청" > "asks/failed/${base}.log"
    git mv "$f" "asks/failed/${base}.json" 2>/dev/null || mv "$f" "asks/failed/${base}.json"
    echo "$base" >> "$ASK_FAIL_RUN"   # 이번 런 실패 기록(stale-red 차단)
    echo "::endgroup::"; continue
  fi

  # 고정부(프롬프트 + 주입 지침) → 가변부(요청) 순서 = 캐시 prefix 안정화.
  prompt="$(cat "$PROMPT_FILE")

${GBLOCK}

[★ 요약 요청 모드 — 운영자가 자연어 + 캡처로 큐레이션을 직접 요청했다.
 1) 본문에 URL이 있으면 그 기사를, 토픽/캡처만 있으면 WebSearch 로 '제일 메이저' 기사 1건(여럿이면 합쳐서 핵심)을 찾는다.
 2) 첨부 캡처 파일이 있으면 Read 로 열어 단서로 활용한다.
 3) 찾은 기사로 위 지침·출력 포맷 그대로 큐레이션 다이제스트를 생성한다.
 4) 내용이 모호해도 절대 실패(ANALYSIS_FAILED)하지 말고 best-effort 로 큐레이션한다 — 이 건은 운영자가 직접 고른 것이다.
 ⛔ Write/Edit/Bash 금지(스크립트가 저장한다). frontmatter '---' 로 시작하는 다이제스트만 출력.]

사용자 요청(자연어):
${text:-(없음 — 캡처만)}

첨부 캡처 파일(있으면 Read 로 확인):
$(printf '%b' "${imglist:-- (없음)\n}")"

  # 허용 도구 = WebFetch·WebSearch(기사 찾기·사실확보) + Read(캡처 판독·지침 읽기) + Glob·Grep.
  # Write/Edit/Bash 불허 → 헤드리스가 권한대기로 멈추지 않음(analyze와 동일 방어).
  out="$(printf '%s' "$prompt" | timeout 900 claude -p \
        --model "$MODEL" \
        --effort max \
        --allowedTools "WebFetch,WebSearch,Read,Glob,Grep" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task" \
        --max-turns 50 \
        2> "/tmp/${base}.err")"
  rc=$?
  claude_health_update "$out" "/tmp/${base}.err"   # 응답O=정상(경고해제) / 빈응답+인증·쿼터=경고(프로필 점등)

  if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^ANALYSIS_FAILED' <<<"$out" || ! grep -qm1 '^---' <<<"$out"; then
    mkdir -p asks/failed
    { echo "exit_code: $rc"; echo "---- stderr ----"; cat "/tmp/${base}.err" 2>/dev/null; echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 20; } > "asks/failed/${base}.log"
    git mv "$f" "asks/failed/${base}.json" 2>/dev/null || mv "$f" "asks/failed/${base}.json"
    echo "$base" >> "$ASK_FAIL_RUN"   # 이번 런 실패 기록(stale-red 차단)
    echo "실패 → asks/failed/${base}"; echo "::endgroup::"; continue
  fi

  # frontmatter 앞 사족 제거 + 지침버전 도장(스크립트가 박음) — analyze와 동일.
  out="$(printf '%s\n' "$out" | sed -n '/^---[[:space:]]*$/,$p')"
  out="$(printf '%s\n' "$out" | awk -v v="$GVER" '!d && /^---[[:space:]]*$/{print; print "guidelines_version: \"" v "\""; d=1; next} {print}')"

  id="ask-$(printf '%s' "$base" | tr -cd 'A-Za-z0-9' | cut -c1-18)"
  outfile="queue/${stamp}-${id}.md"
  n=2; while [ -e "$outfile" ]; do outfile="queue/${stamp}-${id}-${n}.md"; n=$((n+1)); done
  printf '%s\n' "$out" > "$outfile"
  rm -f "$f"
  title="$(grep -m1 '^title:' <<<"$out" | sed -E 's/^title:[[:space:]]*//; s/^"//; s/"$//')"
  echo "성공 → $outfile (${title:-$id})"
  echo "::endgroup::"
done
