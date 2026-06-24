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
source "$ROOT/shared/claude_transient.sh"  # is_transient() SSOT — 일시 과부하(5xx/Overloaded) 인라인 재시도용(analyze와 공용)
INLINE_TRIES=3   # claude -p 일시 과부하(529/5xx) 인라인 재시도(15s·30s 백오프) — 버스트 ✨요약요청 유실 차단(analyze와 동일·260622)
GVER="$(guidelines_version summary)"
GBLOCK="$(guidelines_block summary)"
echo "지침 버전(summary): ${GVER}"

# 이번 런에서 *새로* 실패한 base만 기록(누적 asks/failed 전체 아님) → Surface 스텝이 이것만 보고 빨강 판정.
# (옛 실패가 asks/failed/에 남아도 매 런 빨강 뜨던 stale-red 차단 · 옛 실패는 뷰어 대기열이 24h 표면화. 운영자 260620.)
ASK_FAIL_RUN="${RUNNER_TEMP:-/tmp}/ask_fail_run"; : > "$ASK_FAIL_RUN"
: > /tmp/analyzed_titles.txt   # 완료 푸시용 — 생성된 요약 제목(analyze.sh와 같은 경로 = 워크플로 푸시 스텝 공용)
: > /tmp/analyzed_files.txt    # 완료 푸시용 — 생성된 queue 파일명(베이스) → ?a=<파일> 딥링크(titles와 같은 순서)

shopt -s nullglob
files=(asks/*.json)
if [ ${#files[@]} -eq 0 ]; then
  echo "asks 비어있음 — 종료"
  exit 0
fi

for f in "${files[@]}"; do
  base="$(basename "$f" .json)"          # YYYYMMDD-HHMMSS-xxxxx (ts=submit.js toISOString·UTC)
  # 스크랩(IN) 시각 = 운영자가 '요청을 전송한 시점' = 파일명 ts(UTC) → KST 변환해 큐 파일명 YYMMDD-HHMM 으로.
  # ⚠️ 처리 시점 runner date(UTC)를 쓰면 9h 틀어져 feedAgeH(KST 가정) 정렬·대기열 '몇분 전'이 어긋남(운영자 260621 "스크랩=내가 요청한 시점, 안 박히니 못 찾음").
  bts="${base:0:15}"; stamp=""           # YYYYMMDD-HHMMSS (UTC)
  if [[ "$bts" =~ ^([0-9]{4})([0-9]{2})([0-9]{2})-([0-9]{2})([0-9]{2})([0-9]{2})$ ]]; then
    stamp="$(TZ=Asia/Seoul date -d "${BASH_REMATCH[1]}-${BASH_REMATCH[2]}-${BASH_REMATCH[3]}T${BASH_REMATCH[4]}:${BASH_REMATCH[5]}:${BASH_REMATCH[6]}Z" +%y%m%d-%H%M 2>/dev/null)" || stamp=""
  fi
  [ -z "$stamp" ] && stamp="$(TZ=Asia/Seoul date +%y%m%d-%H%M)"   # 폴백: 파싱 실패 시 현재 KST
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
 4) ⭐ 찾은 '제일 메이저' 기사의 **원본 URL(WebFetch/WebSearch로 실제 접근·확인한 것만)을 frontmatter `url:` 에 넣어라**(뷰어 상단 '원문' 링크로 노출된다). ⚠️ 스니펫에서 본 듯한 URL을 추측·조립하지 마라(사실 무결성) — 실제 확인한 기사 URL이 하나도 없을 때만 url: "". 그리고 **그 기사에서 기자(reporter)·게시일시(date·time)·매체(media)를 추출해 frontmatter + 본문 '출처:' 줄 양쪽에 정확히 반영**하라(토픽/캡처 요청이라도 네가 찾아 확인한 그 기사가 곧 원문이다). ⚠️ §입력 처리 0의 'URL 없으면 url:""' 규칙은 **운영자 전문 붙여넣기**(전문이 곧 원문) 경우에만 적용 — 요약 요청 모드에선 네가 찾아 확인한 기사 URL을 넣는다.
 5) 내용이 모호해도 절대 실패(ANALYSIS_FAILED)하지 말고 best-effort 로 큐레이션한다 — 이 건은 운영자가 직접 고른 것이다.
 ⛔ Write/Edit/Bash 금지(스크립트가 저장한다). frontmatter '---' 로 시작하는 다이제스트만 출력.]

사용자 요청(자연어):
${text:-(없음 — 캡처만)}

첨부 캡처 파일(있으면 Read 로 확인):
$(printf '%b' "${imglist:-- (없음)\n}")"

  # 허용 도구 = WebFetch·WebSearch(기사 찾기·사실확보) + Read(캡처 판독·지침 읽기) + Glob·Grep.
  # Write/Edit/Bash 불허 → 헤드리스가 권한대기로 멈추지 않음(analyze와 동일 방어).
  # 인라인 재시도 — Anthropic API 일시 과부하(529 Overloaded/5xx)면 짧은 백오프로 즉시 재시도(analyze와 동일·260622).
  #   성공·ANALYSIS_FAILED(막다른길)는 즉시 탈출(쿼터 낭비 0). 과부하 신호일 때만 재시도(is_transient).
  inline_delay=15
  for attempt in $(seq 1 "$INLINE_TRIES"); do
    out="$(printf '%s' "$prompt" | timeout 900 claude -p \
          --model "$MODEL" \
          --effort max \
          --allowedTools "WebFetch,WebSearch,Read,Glob,Grep" \
          --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task" \
          --max-turns 50 \
          2> "/tmp/${base}.err")"
    rc=$?
    if { [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '^---' <<<"$out"; } || grep -qm1 '^ANALYSIS_FAILED' <<<"$out"; then
      break
    fi
    if claude_failover "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 1회 전환·재시도(account failover · SSOT)
    if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then
      echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
      sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
    fi
    break
  done
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
  echo "${title:-$id}" >> /tmp/analyzed_titles.txt
  basename "$outfile" >> /tmp/analyzed_files.txt   # 완료 푸시 딥링크용(요약 창 ?a=)
  echo "성공 → $outfile (${title:-$id})"
  echo "::endgroup::"
done
