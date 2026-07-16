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
source "$ROOT/shared/summary_repair.sh"    # 분량 가드 SSOT — IG/Thread 과소 시 1회 보강(기본 OFF·SUMMARY_LEN_GUARD='1' · 260705)
INLINE_TRIES=4   # 인라인 재시도 = 4계정 폴오버 체인 깊이(서브3까지 실호출) + 일시 과부하(529/5xx)·타임아웃(rc=124)·버스트 ✨요약요청 유실 차단(analyze와 동일·260622·4계정 3→4)
EFFORT="${PIPE_SEARCH_EFFORT:-high}"   # 검색·요약 추론깊이 — '메이저 기사 찾기'는 도구 왕복이 본질이라 max 는 매 검색 사이 헛사고로 타임아웃만 유발(누락방지 실익≈0) → high 기본(효율·품질 균형 · 운영자 260704). 워크플로 env PIPE_SEARCH_EFFORT 로 카나리아/롤백(max).
ASK_TIMEOUT="${ASK_TIMEOUT:-600}"      # claude -p 타임아웃(초) — 요약요청은 요약만이라 10분이면 충분(검색완화 후). 초과 시 계정 1회 전환 후 격리(운영자 260704 "10분 넘으면 다른 계정" · 옛 900s는 배치 timeout 시 45분→워크플로 초과라 하향).
ASK_JOB_DEADLINE="${ASK_JOB_DEADLINE:-2200}"   # 스크립트 SECONDS 이 초 넘으면 새 요약요청 처리 시작 안 함(잔여 잔류→다음 런) — 과부하 다건 타임아웃이 잡 timeout(60분) 초과해 처리 중 기사까지 잘리는 것 방지(평의회 260704 A · 여유 = 60분 - 셋업 - 다음기사 최악 2×600s).
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
  if [ "$SECONDS" -gt "$ASK_JOB_DEADLINE" ]; then echo "⏱ 잡 시간 예산 임박(${SECONDS}s>${ASK_JOB_DEADLINE}s) — 잔여 요약요청은 다음 런에(잔류)"; break; fi   # 배치 다건 타임아웃이 잡 timeout(60분) 넘겨 처리 중 기사까지 잘리는 것 방지(평의회 260704 A)
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
 1) ⭐ **요청문에 이미 기사 본문급 전문(수백 자 이상)이 들어 있으면 = 그 전문이 곧 원문이다 → WebSearch 로 다른 기사를 찾지 말고 그 전문만으로 바로 큐레이션하라**(검색은 시간만 먹고 15분 타임아웃을 유발한다 — 운영자가 이미 본문을 줬으면 검색은 불필요·운영자 260704). ⚠️ **단 관련이미지 소스(image_sources)만은 이 생략의 예외다**: 전문이 있어도 frontmatter \`image_sources\`는 위 문서의 image_sources 규칙(전문 = 소스 URL 2~3개까지만 best-effort)대로 WebSearch 해 채워라 — 뷰어 '검색 이미지'가 이 URL들의 대표사진(og:image)을 가져오는 유일한 원료다(비우면 관련 이미지 0장 · 운영자 260710 '검색 이미지는 유지, AI 썸네일 생성만 스킵'). 몇 번에 안 나오면 있는 만큼만 넣고 빈 값도 허용 — 요약 완성이 항상 우선(검색어 바꿔가며 여러 번 검색 = 금지 불변 · 예외는 image_sources 한 필드뿐이라 원문 \`url:\` 은 아래 4) 그대로 빈 값 유지). 전문 없이 본문에 URL만 있으면 그 기사를(운영자가 직접 고른 URL은 오래됐어도 존중), URL·전문 없이 토픽/캡처만 있으면 WebSearch 로 '제일 메이저' 기사 1건(여럿이면 합쳐서 핵심)을 찾는다. ⚠️ **토픽/캡처 검색 시 = 최신 우선(18시간 내)**: 같은 사안이면 **최근 18시간 내 보도 중 가장 메이저한 것**을 골라라(며칠·몇 주 지난 옛 기사가 뉴스요약 피드 상단 채우는 문제 방지 — 운영자 260702). 18시간 내 보도가 없으면 그중 가장 최근 것으로(억지 최신화·날짜 조작 금지), *최신 보도가 있는데 옛 기사를 고르지는 마라*. ⚠️ **검색은 최대 2~3회로 제한** — 몇 번 찾아 안 나오면(막힌 매체·지역뉴스 등) 있는 정보로 best-effort 요약하고 넘어가라(무한 검색으로 타임아웃 나면 아예 요약이 0이 된다).
 2) 첨부 캡처 파일이 있으면 Read 로 열어 단서로 활용한다.
 3) 찾은 기사로 위 지침·출력 포맷 그대로 큐레이션 다이제스트를 생성한다.
 4) ⭐ 찾은 '제일 메이저' 기사의 **원본 URL(WebFetch/WebSearch로 실제 접근·확인한 것만)을 frontmatter \`url:\` 에 넣어라**(뷰어 상단 '원문' 링크로 노출된다). ⚠️ 스니펫에서 본 듯한 URL을 추측·조립하지 마라(사실 무결성) — 실제 확인한 기사 URL이 하나도 없을 때만 url: "". 그리고 **그 기사에서 기자(reporter)·게시일시(date·time)·매체(media)를 추출해 frontmatter + 본문 '출처:' 줄 양쪽에 정확히 반영**하라(토픽/캡처 요청이라도 네가 찾아 확인한 그 기사가 곧 원문이다). ⚠️ **요청문에 전문이 이미 있으면 url 은 빈 값**(전문이 곧 원문 — *원문 URL 확보용* 검색은 여전히 생략·억지로 찾지 마라. 1)의 image_sources 예외 검색과는 별개 — 그 검색 중 원문 URL을 우연히 확인해도 url 은 빈 값 유지). 매체·기자·일시는 전문 안에 적힌 것을 그대로 추출해 반영하라(전문에 없으면 비워둠). 전문 없이 토픽/URL로 찾은 경우에만 그 기사 URL을 넣는다.
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
  claude_reset_force_swap 2>/dev/null || true   # 앞 기사가 타임아웃으로 강제전환(force)한 계정을 쿼터 확정 위치로 복원 → 쿼터 4계정 체인 예산 보존(평의회 260704 Q5)
  claude_preflight "$MODEL" 2>/dev/null || true # 본선(≤600s) 직전 60s 핑으로 산 계정 선탑승 — 죽은 활성계정 침묵 행이 본선 timeout을 통째로 태우던 공회전 소거(preflight SSOT 본선 확장 배선 260717 · fail-soft)
  _to_tried=0                                   # 이 기사에서 타임아웃 계정전환을 이미 1회 했는지(무한 전환 차단)
  for attempt in $(seq 1 "$INLINE_TRIES"); do
    out="$(printf '%s' "$prompt" | METER_SRC=ask METER_REF="$base" METER_MODEL="$MODEL" METER_EFFORT="$EFFORT" claude_meter "$ASK_TIMEOUT" \
          --model "$MODEL" \
          --effort "$EFFORT" \
          --allowedTools "WebFetch,WebSearch,Read,Glob,Grep" \
          --disallowedTools "Write,Edit,NotebookEdit,Bash,Task" \
          --max-turns 50 \
          2> "/tmp/${base}.err")"
    rc=$?
    if { [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '^---' <<<"$out"; } || grep -qm1 '^ANALYSIS_FAILED' <<<"$out"; then
      break
    fi
    if claude_failover "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 1단계씩 전환·재시도(서브1→서브2→서브3 · SSOT)
    # 타임아웃(rc=124 = claude_meter ASK_TIMEOUT 초과) = 출력이 비어 is_quota/is_transient 가 못 잡는 사각지대였다(이번 '중국인 렌터카' 실패의 원인).
    #   서버 과부하 응답지연이면 다른 계정(부하 편차)에서 회복될 수 있으므로 *딱 1회* 강제 계정 전환 후 재시도(운영자 260704 "10분 넘으면 다른 계정").
    #   ⚠️ 1회 제한 = 타임아웃은 대개 입력바운드(계정 바꿔도 반복)라 무한 전환은 워크플로 시간·쿼터만 소진(평의회 260704). 그 1회 전환도 claude_reset_force_swap 이 다음 기사서 되돌림.
    if [ $rc -eq 124 ] && [ "$_to_tried" = "0" ] && claude_failover_force; then _to_tried=1; continue; fi
    # 일시 과부하(5xx)면 백오프 후 재시도(마지막 시도면 탈출→격리). ⚠️ 타임아웃(rc=124)은 여기서 재시도 안 함(force 1회로 끝) — `[ $rc -ne 124 ]` 명시 가드 = 과부하성 타임아웃 stderr(Overloaded)가 is_transient 에 매칭돼 3회로 새는 것 봉인(2회 상한 airtight · 평의회 260704 B).
    if [ "$attempt" -lt "$INLINE_TRIES" ] && [ $rc -ne 124 ] && is_transient "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then
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
    if grep -qm1 '^ANALYSIS_FAILED' <<<"$out"; then _fk=source; elif [ $rc -eq 124 ]; then _fk=timeout; elif is_transient "$out$(cat "/tmp/${base}.err" 2>/dev/null)"; then _fk=congest; else _fk=source; fi
    if [ "$_fk" = timeout ]; then
      _fbody="$(printf '⚠️ 요약 요청이 시간 초과로 실패했어.\n사유: 원문 검색·요약이 제한 시간을 넘겨 중단됨(과부하 또는 검색 지연).\n\n→ 대기열에서 “재시도”를 누르면 그 내용이 채워져 다시 요청할 수 있어(캡처는 재첨부).')"
    elif [ "$_fk" = congest ]; then
      _fbody="$(printf '⚠️ 요약 요청이 분석 과정에서 실패했어.\n사유: 분석 도구 혼잡(일시 과부하 — 재시도 소진).\n\n→ 대기열에서 “재시도”를 누르면 그 내용이 채워져 다시 요청할 수 있어.')"
    else
      _fbody="$(printf '⚠️ 요약 요청이 분석 과정에서 실패했어.\n사유: 내용 분석 결함(입력이 비었거나 불충분).\n\n→ 대기열에서 “재시도”를 누르거나 입력을 확인하고 다시 요청해줘.')"
    fi
    # 관련 기사 링크 무조건 동봉(운영자 260712 "실패 시 관련 기사 무조건 링크 + 알림") — 직접 요약요청은 공유 링크가 안 잡힐 수 있음 → 입력이 URL이면 원문 · 텍스트뿐이면 첫 조각 구글뉴스 유추 검색(비-LLM·토큰 0 · 실패 시 무동봉 fail-soft)
    _ref="$(NM_T="${text}" python3 -c '
import os, re, urllib.parse
t = (os.environ.get("NM_T") or "").strip()
m = re.search(r"https?://\S{8,}", t)
if m: print(m.group(0)[:400])
else:
    q = re.sub(r"\s+", " ", t)[:60].strip()
    print("https://news.google.com/search?q=" + urllib.parse.quote(q) + "&hl=ko&gl=KR&ceid=KR:ko" if q else "")
' 2>/dev/null || true)"
    [ -n "${_ref// }" ] && _fbody="${_fbody}"$'\n\n'"[관련 기사 — 어떤 기사인지 확인]"$'\n'"${_ref}"
    python3 shared/msg.py set "fail-${base}" "$_fbody" warn 2>/dev/null || true
    printf '%s\n' "$base" >> /tmp/analyzed_fail_msgs.txt
    echo "실패 → asks/failed/${base}"; echo "::endgroup::"; continue
  fi

  # frontmatter 앞 사족 제거 + 이중 여는 '---' 접기 + 지침버전 도장(스크립트가 박음) — analyze와 동일.
  #   (이중 --- = 모델이 여는 표식 두 번 뱉으면 첫 블록 조기 폐합 → title 본문行 → 피드 파일명 노출 · 260703 실측 가드)
  out="$(printf '%s\n' "$out" | sed -n '/^---[[:space:]]*$/,$p')"
  out="$(printf '%s\n' "$out" | awk 'NR==1{print;next} !s && (/^---[[:space:]]*$/ || /^[[:space:]]*$/){next} {s=1;print}')"
  out="$(printf '%s\n' "$out" | awk -v v="$GVER" '!d && /^---[[:space:]]*$/{print; print "guidelines_version: \"" v "\""; d=1; next} {print}')"
  # 뷰어 '이미지' 토글 OFF → queue frontmatter에 no_thumb: "1" 주입 → thumb_gen이 제미나이 썸네일 skip(검색 og:image는 항상·운영자 260702)
  if [ -n "$nothumb" ]; then
    out="$(printf '%s\n' "$out" | awk '!nt && /^---[[:space:]]*$/{print; print "no_thumb: \"1\""; nt=1; next} {print}')"
  fi
  # 닫는 '---' 보증(260704 실측 '중국인 렌터카' — LLM이 frontmatter 닫는 표식을 생략 → 뷰어가 여닫이 매치 실패 →
  #   메타데이터 통째 본문 노출). 여는 '---' 이후 key: value 필드 줄이 끝나는 지점(닫는 '---' 없이 빈 줄·본문行이 오면)
  #   그 앞에 '---'를 삽입한다. 이미 닫는 '---'가 있는 정상 출력은 무변형(그 줄에서 cl=1로 멈춤). build-viewer 관용 파싱과 한 쌍.
  out="$(printf '%s\n' "$out" | awk '
    NR==1 && /^---[[:space:]]*$/{print; op=1; next}
    op && !cl {
      if(/^---[[:space:]]*$/){print; cl=1; next}
      if(/^[A-Za-z_][A-Za-z0-9_]*:[[:space:]]/){print; next}
      print "---"; cl=1; print; next
    }
    {print}')"

  id="ask-$(printf '%s' "$base" | tr -cd 'A-Za-z0-9' | cut -c1-18)"
  outfile="queue/${stamp}-${id}.md"
  n=2; while [ -e "$outfile" ]; do outfile="queue/${stamp}-${id}-${n}.md"; n=$((n+1)); done
  printf '%s\n' "$out" > "$outfile"
  # 분량 가드(기본 OFF · SUMMARY_LEN_GUARD='1' 카나리아) — IG/Thread 과소 시 자유요약에서 1회 보강(잡 예산 내 · fail-soft · 260705 · repair ≤+480s는 다음-기사 헤드룸(2×600s) 내 = 잡 최악 무변·평의회8)
  if [ "$SECONDS" -le "$ASK_JOB_DEADLINE" ]; then summary_repair "$outfile" ask-repair; fi
  # 규격·자수 기계 린트(비차단 · analyze.sh 미러 · 분신술② NEW-1 · 260703) — ask 경로 다이제스트 사각지대 해소(검증4). 가드 뒤 = 최종본 실측.
  python3 shared/digest_guard.py "$outfile" 2>/dev/null | sed 's/^/  /' || true
  rm -f "$f"
  title="$(grep -m1 '^title:' <<<"$out" | sed -E 's/^title:[[:space:]]*//; s/^"//; s/"$//')"
  title_ko="$(grep -m1 '^title_ko:' <<<"$out" | sed -E 's/^title_ko:[[:space:]]*//; s/^"//; s/"$//')"   # 외신 한국어 번역 제목(완료 푸시 우선 · analyze.sh 미러 · 260703)
  echo "${title_ko:-${title:-$id}}" >> /tmp/analyzed_titles.txt
  basename "$outfile" >> /tmp/analyzed_files.txt   # 완료 푸시 딥링크용(요약 창 ?a=)
  echo "성공 → $outfile (${title:-$id})"
  echo "::endgroup::"
done
