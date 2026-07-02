#!/usr/bin/env bash
# asks/*.json (뷰어 ✨요약 요청 = 자연어 text + base64 캡처 images[]) 를 순회하며
# Claude Code 헤드리스(claude -p)로 해석 → 제일 메이저 기사를 WebSearch로 찾아(또는 본문 URL) 큐레이션
# 다이제스트 생성 → queue/ 저장, 처리한 ask 삭제, 실패는 asks/failed/ 격리. (analyze.sh 미러 — 입력만 멀티모달)
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PROMPT_FILE="prompts/news-analysis.md"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL · 260702 SYS-08)
MODEL="$PIPE_MODEL"

# 지침 SSOT 강제 주입(analyze와 동일 summary 세트) — 출력 포맷·품질기준 일치, GVER 도장.
source "$ROOT/shared/inject_guidelines.sh"
source "$ROOT/shared/claude_transient.sh"  # is_transient() SSOT — 일시 과부하(5xx/Overloaded) 인라인 재시도용(analyze와 공용)
source "$ROOT/shared/claude_meter.sh"      # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard · 옛 동작 호환)
INLINE_TRIES=3   # claude -p 일시 과부하(529/5xx) 인라인 재시도(15s·30s 백오프) — 버스트 ✨요약요청 유실 차단(analyze와 동일·260622)
GVER="$(guidelines_version summary)"
GBLOCK="$(guidelines_block summary)"
echo "지침 버전(summary): ${GVER}"

# 이번 런에서 *새로* 실패한 base만 기록(누적 asks/failed 전체 아님) → Surface 스텝이 이것만 보고 빨강 판정.
# (옛 실패가 asks/failed/에 남아도 매 런 빨강 뜨던 stale-red 차단 · 옛 실패는 뷰어 대기열이 24h 표면화. 운영자 260620.)
ASK_FAIL_RUN="${RUNNER_TEMP:-/tmp}/ask_fail_run"; : > "$ASK_FAIL_RUN"
: > /tmp/analyzed_titles.txt   # 완료 푸시용 — 생성된 요약 제목(analyze.sh와 같은 경로 = 워크플로 푸시 스텝 공용)
: > /tmp/analyzed_fail_msgs.txt   # 실패 푸시용 — 실패 base 적재 → notify_fail.sh 웹푸시(analyze.sh 미러 · 운영자 260629 ask 경로 푸시 통일)
: > /tmp/analyzed_files.txt    # 완료 푸시용 — 생성된 queue 파일명(베이스) → ?a=<파일> 딥링크(titles와 같은 순서)

shopt -s nullglob
files=(asks/*.json)
if [ ${#files[@]} -eq 0 ]; then
  echo "asks 비어있음 — 종료"
  exit 0
fi

for f in "${files[@]}"; do
  base="$(basename "$f" .json)"          # YYYY-MM-DD-HHMM-xxxxx (ts=submit.js toISOString→[:.]제거→T치환→slice15·UTC·초없음)
  # 스크랩(IN) 시각 = 운영자가 '요청을 전송한 시점' = 파일명 ts(UTC) → KST 변환해 큐 파일명 YYMMDD-HHMM 으로.
  # ⚠️ 처리 시점 runner date(UTC)를 쓰면 9h 틀어져 feedAgeH(KST 가정) 정렬·대기열 '몇분 전'이 어긋남(운영자 260621 "스크랩=내가 요청한 시점, 안 박히니 못 찾음").
  # ⚠️ 정규식은 submit.js 실제 형식 YYYY-MM-DD-HHMM(대시 3개·초 없음)에 맞춤 — 옛 YYYYMMDD-HHMMSS 기대는 항상 unmatch→폴백(처리시각) 상시발동이라 의도 안 먹었음(260701 픽스).
  bts="${base:0:15}"; stamp=""           # YYYY-MM-DD-HHMM (UTC·초없음)
  if [[ "$bts" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})-([0-9]{2})([0-9]{2})$ ]]; then
    stamp="$(TZ=Asia/Seoul date -d "${BASH_REMATCH[1]}-${BASH_REMATCH[2]}-${BASH_REMATCH[3]}T${BASH_REMATCH[4]}:${BASH_REMATCH[5]}:00Z" +%y%m%d-%H%M 2>/dev/null)" || stamp=""
  fi
  [ -z "$stamp" ] && stamp="$(TZ=Asia/Seoul date +%y%m%d-%H%M)"   # 폴백: 파싱 실패 시 현재 KST
  echo "::group::요약 요청: $base"

  # JSON 파싱: 텍스트 추출 + 이미지(data URL) → 파일 디코드(Claude Read 가 볼 수 있게)
  workdir="$(mktemp -d)"
  text="$(python3 -c "import json; print(json.load(open('$f')).get('text',''))" 2>/dev/null || true)"
  nothumb="$(python3 -c "import json; print('1' if json.load(open('$f')).get('nothumb') in (1,'1',True) else '')" 2>/dev/null || true)"   # 뷰어 '이미지' 토글 OFF → 제미나이 썸네일 생성 skip(검색 og:image는 항상·운영자 260702)
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
 1) 본문에 URL이 있으면 그 기사를(운영자가 직접 고른 URL은 오래됐어도 존중), 토픽/캡처만 있으면 WebSearch 로 '제일 메이저' 기사 1건(여럿이면 합쳐서 핵심)을 찾는다. ⚠️ **토픽/캡처 검색 시 = 최신 우선(18시간 내)**: 같은 사안이면 **최근 18시간 내 보도 중 가장 메이저한 것**을 골라라(며칠·몇 주 지난 옛 기사가 뉴스요약 피드 상단 채우는 문제 방지 — 운영자 260702). 18시간 내 보도가 없으면 그중 가장 최근 것으로(억지 최신화·날짜 조작 금지), *최신 보도가 있는데 옛 기사를 고르지는 마라*.
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
    out="$(printf '%s' "$prompt" | METER_SRC=ask METER_REF="$base" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
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
    if claude_failover "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 1단계씩 전환·재시도(서브1→서브2 · SSOT)
    if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then
      echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
      sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
    fi
    break
  done
  if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^ANALYSIS_FAILED' <<<"$out" || ! grep -qm1 '^---' <<<"$out"; then
    mkdir -p asks/failed
    { echo "exit_code: $rc"; echo "---- stderr ----"; cat "/tmp/${base}.err" 2>/dev/null; echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 20; } > "asks/failed/${base}.log"
    git mv "$f" "asks/failed/${base}.json" 2>/dev/null || mv "$f" "asks/failed/${base}.json"
    echo "$base" >> "$ASK_FAIL_RUN"   # 이번 런 실패 기록(stale-red 차단)
    # 실패 메시지함 + 웹푸시 트리거(analyze.sh emit_fail_msg 미러 · 운영자 260629 ask 경로 푸시 통일) — fail-<base> = notify_fail.sh 딥링크(/?msg=fail-<base>)
    # 사유 분류(analyze.sh 패턴 미러 · 평의회 260629): 일시 과부하=혼잡(재시도 소진) / ANALYSIS_FAILED·기타=내용 결함 — "자동 복구" 단정 금지(콘텐츠 실패엔 거짓).
    if grep -qm1 '^ANALYSIS_FAILED' <<<"$out"; then _fk=source; elif is_transient "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then _fk=congest; else _fk=source; fi
    if [ "$_fk" = congest ]; then
      _fbody="$(printf '⚠️ 요약 요청이 분석 과정에서 실패했어.\n사유: 분석 도구 혼잡(일시 과부하 — 재시도 소진).\n\n→ 잠시 후 그 요약을 다시 요청해줘.')"
    else
      _fbody="$(printf '⚠️ 요약 요청이 분석 과정에서 실패했어.\n사유: 내용 분석 결함(입력이 비었거나 불충분).\n\n→ 입력을 확인하고 다시 요청해줘.')"
    fi
    python3 shared/msg.py set "fail-${base}" "$_fbody" warn 2>/dev/null || true
    printf '%s\n' "$base" >> /tmp/analyzed_fail_msgs.txt
    echo "실패 → asks/failed/${base}"; echo "::endgroup::"; continue
  fi

  # frontmatter 앞 사족 제거 + 지침버전 도장(스크립트가 박음) — analyze와 동일.
  out="$(printf '%s\n' "$out" | sed -n '/^---[[:space:]]*$/,$p')"
  out="$(printf '%s\n' "$out" | awk -v v="$GVER" '!d && /^---[[:space:]]*$/{print; print "guidelines_version: \"" v "\""; d=1; next} {print}')"
  # 뷰어 '이미지' 토글 OFF → queue frontmatter에 no_thumb: "1" 주입 → thumb_gen이 제미나이 썸네일 skip(검색 og:image는 항상·운영자 260702)
  if [ -n "$nothumb" ]; then
    out="$(printf '%s\n' "$out" | awk '!nt && /^---[[:space:]]*$/{print; print "no_thumb: \"1\""; nt=1; next} {print}')"
  fi

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
