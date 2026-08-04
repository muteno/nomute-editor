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
EFFORT="${PIPE_SEARCH_EFFORT:-medium}"   # 검색·요약 추론깊이 — opus5 는 medium 도 구세대 high급 품질에 지연·토큰 대폭 절감(요약 단축 축 · 운영자 260727 일괄 하향, 구 high=260704). 워크플로 env PIPE_SEARCH_EFFORT 로 카나리아/롤백(high).
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

# ── 처리 대상 선정(병렬 안전 스코프 · 운영자 260720 "여러 개 동시에" ) ──
# ASK_ONLY(개행 구분 경로 목록)가 있으면 = push 트리거 런: '이 푸시가 추가한 파일만' 처리.
#   → 런들이 concurrency 그룹 없이 병렬로 떠도 각자 자기 몫만 집어 중복 소비·이중 과금이 없다.
#   목록 파일이 작업트리(ref:main 최신)에 없으면 = 이미 다른 경로가 처리(삭제/격리)한 것 → 스킵.
#   (구 런 re-run 도 같은 원리로 전건 스킵 = 안전 no-op.)
# ASK_ONLY 비면 = workflow_dispatch(수동 구출·pending-sweep 백스톱): 잔류 전건 스윕(종전 동작).
#   스윕이 인플라이트 파일과 겹치는 극단 코너에서도 산출 파일명이 결정적(스탬프+base유래 id)이라
#   자기-덮어쓰기로 수렴(피드 중복 0 · 토큰만 소모) — 스윕 쪽은 45분 나이 임계가 1차로 배제.
shopt -s nullglob
if [ -n "${ASK_ONLY:-}" ]; then
  files=()
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    case "$p" in asks/*/*) echo "· 하위 디렉터리(failed 격리본 등) — 스킵: $p"; continue;; esac   # pathspec 월경 이중 방어(적대검증 C5ⓒ)
    if [ ! -f "$p" ]; then echo "· 스코프 파일 부재(이미 처리/격리) — 스킵: $p"; continue; fi
    files+=("$p")
  done <<< "$ASK_ONLY"
  echo "스코프 모드: 이 푸시가 추가한 ${#files[@]}건만 처리(병렬 런 각자 자기 몫)"
else
  # 스윕(dispatch) — ASK_MIN_AGE_MIN 분 미만 신선 건은 스킵(자기 스코프 런이 처리 중일 개연성 — 겹침 이중과금 배제 ·
  #   적대검증 A5③/C3). 0(수동 기본) = 전건. 무타임스탬프 = 나이 미상 → 처리(유실 0 우선).
  files=()
  _now="$(date +%s)"
  for p in asks/*.json; do
    if [ "${ASK_MIN_AGE_MIN:-0}" != "0" ]; then
      _b="$(basename "$p" .json)"
      if [[ "$_b" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})-([0-9]{2})([0-9]{2}) ]]; then
        _ts=$(date -u -d "${BASH_REMATCH[1]}-${BASH_REMATCH[2]}-${BASH_REMATCH[3]}T${BASH_REMATCH[4]}:${BASH_REMATCH[5]}:00Z" +%s 2>/dev/null || echo 0)
        if [ "${_ts:-0}" -gt 0 ] && [ $(( (_now - _ts) / 60 )) -lt "${ASK_MIN_AGE_MIN}" ]; then
          echo "· 신선 ask($(( (_now - _ts) / 60 ))분<${ASK_MIN_AGE_MIN}분) — 스킵(자기 런 처리 중 추정): $p"; continue
        fi
      fi
    fi
    files+=("$p")
  done
  echo "스윕 모드: 잔류 ${#files[@]}건 처리(dispatch 구출·백스톱 · MIN_AGE=${ASK_MIN_AGE_MIN:-0}분)"
fi
if [ ${#files[@]} -eq 0 ]; then
  echo "처리할 요약요청 없음 — 종료"
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
  # 수집 프리셋(운영자 260723 — 뷰어 요약요청 스트립: h24=24시간 이내 · fp=외신 기반[260803 외신⇄국내 단일 토글 = 뷰어 mj 상시 1 전송·fp가 축만 선택] · mj=주요 언론 기반[다매체 종합 · 뷰어 칩은 260803 철거·값은 상시 도착] · og=원본 한정[260727·기본 소등]) → 프롬프트 조건 블록.
  #   ⚠ 같은 스트립의 noai(AI 미제작·260727)는 여기 목록에 일부러 없다 = 수집 조건이 아니라 산출 조건 → 위 nothumb(frontmatter no_thumb) 축으로 흐른다(프롬프트 무접촉).
  #   미지정·전OFF(구 asks 포함) = 빈 블록 = 종전 동작 그대로. 블록 위치 = 고정부([★] 모드) 뒤·가변부(요청) 앞 = 캐시 prefix 불변.
  pres="$(python3 -c "
import json
p = (json.load(open('$f')).get('preset') or {})
print(''.join(k for k in ('h24','fp','mj','og') if p.get(k) in (1,'1',True)))
" 2>/dev/null || true)"
  PRESET_BLOCK=""
  if [ -n "$pres" ]; then
    PRESET_BLOCK="[⚙ 수집 프리셋 — 운영자가 요청 창에서 켠 수집 조건(ON만 나열). ⚠️ 위 1)의 기본 보강 모드와 **함께** 적용된다(260803 — 구 '전문 있으면 프리셋 무시' 폐지·역전 동기화): 전문이 있어도 프리셋은 보강 검색의 조건·취향으로 그대로 유효하다. 유일 예외 = 「원본 한정」(켜져 있으면 보강·프리셋 검색 전부 생략 · 아래 블록이 항상 우선):
"
    case "$pres" in *og*) PRESET_BLOCK="${PRESET_BLOCK} - 🔒 원본 한정(운영자 260727 · 이 항목이 켜져 있으면 아래 다른 수집 조건보다 **항상 우선**): **운영자가 이 요청문에 직접 준 원본 안에서만 큐레이션하라** — 원본 = 요청문에 붙여넣은 전문 + 요청문에 적힌 URL + 첨부 캡처, 그게 전부다. 다른 기사·자료를 WebSearch로 찾지 마라(URL이 적혀 있으면 그 URL만 WebFetch로 열어 원문으로 삼고, 거기서 더 뻗어나가지 않는다). 원본에 없는 사실·수치·인용·배경은 **지어내지 말고 쓰지 마라** — 정보가 얇으면 얇은 대로 원본 범위 안에서 best-effort로 완성한다(분량을 채우려고 외부 지식·추측으로 늘리는 것 금지 · 그래도 실패(ANALYSIS_FAILED) 금지 원칙은 불변). 아래 24시간 이내·외신·주요 언론 조건이 함께 켜져 있어도 **그 조건들이 요구하는 추가 검색은 수행하지 마라**(원본 한정이 이긴다 — 그 조건들은 원본을 고르는 취향이지 원본을 넘어설 권한이 아니다). 예외는 frontmatter image_sources 한 필드뿐 — 위 1)의 image_sources 규칙 그대로 소스 URL 2~3개까지 best-effort 검색해 채운다(뷰어 '검색 이미지'의 유일한 원료라 비우면 관련 이미지 0장 · 본문 내용은 여전히 원본에서만 온다).
";; esac
    case "$pres" in *h24*) PRESET_BLOCK="${PRESET_BLOCK} - ⏱ 24시간 이내: 검색 수집·인용 후보 = 게시 24시간 이내 기사만(위 '18시간 우선' 규칙을 이 24시간 하드 창으로 대체 — 24시간 밖 기사는 소스로 쓰지 마라). 24시간 내 보도가 전무할 때만 가장 최근 보도로 best-effort(억지 최신화·날짜 조작 금지 · 실패 금지 원칙 유지). 운영자가 직접 준 URL은 오래됐어도 존중(종전 규칙).
";; esac
    case "$pres" in *fp*) PRESET_BLOCK="${PRESET_BLOCK} - 🌐 외신 기사: '외신만'이 아니라 **외신을 먼저·주로 탐색하라** — 주제 핵심을 영문 키워드로 옮겨 영어 WebSearch부터 시작한다(Reuters·AP·AFP·BBC·CNN·NYT·Bloomberg·Guardian 등 국제 통신사·주요 외신 우선). 외신에서 사실이 충분히 확보되면 그걸 축으로 삼고, 국내 보도는 교차확인·국내 맥락 보조로만 쓴다. 아래 「주요 언론 기반」이 함께 켜져 있으면 그 종합의 매체 풀도 이 외신 축을 따른다(외신 주요 매체 2~4곳이 축 · 국내는 교차확인 보조 — 종합의 구조·분량·frontmatter url 규칙은 그대로).
";; esac
    case "$pres" in *mj*) PRESET_BLOCK="${PRESET_BLOCK} - 📰 주요 언론 기반: 단일 기사 요약이 아니라 **주요 언론 2~4곳의 보도를 수집·교차 검증해**, 먼저 2,000자 가까운 보도형 종합 자료를 내부적으로 구성하라 — 기·승 = 사실을 기반으로 한 사건의 발단·전개 / 전 = 사건의 결말(현재 상태) / 결 = 시사점이 확실한 구조. 그 종합 자료를 이 요약의 원문 소스로 삼아 위 출력 포맷 그대로 큐레이션한다(출력 포맷·분량 규칙 불변 — 종합 자료 자체를 그대로 출력하지 마라 · frontmatter url = 수집 매체 중 실제 확인한 가장 메이저한 기사 URL). 운영자가 URL을 준 요청이면 그 기사가 축(url 그대로)이고 타 매체는 교차확인용.
";; esac
    # 검색 상한 완화 = 검색을 *하는* 프리셋(h24·fp·mj)이 켜졌을 때만. 원본 한정만 켜진 요청은 검색 자체가 금지라 이 줄이 모순 → 블록을 바로 닫는다(운영자 260727).
    case "$pres" in
      *h24*|*fp*|*mj*) PRESET_BLOCK="${PRESET_BLOCK} - 검색 상한 확인: 프리셋 검색(외신 영문 + 국내 교차)도 기본 보강 상한과 같은 총 6회 예산 안에서 수행한다(260803 — 기본이 6회로 상향돼 구 '프리셋 완화'는 상한 명시로 대체). 그래도 타임아웃 방지가 항상 우선 — 상한 내 확보된 것만으로 best-effort 완성하라(무한 검색 금지 불변).]
" ;;
      *) PRESET_BLOCK="${PRESET_BLOCK}]
" ;;
    esac
  fi
  # ── 링크 레일(운영자 260731 "우측 사진 아래에 링크도 · 원문이면 원문 활용 · 미디어면 large v3 전사해서 그 내용 활용") ──
  #   기사(article) = URL 블록으로 프롬프트에 실어 Claude 가 WebFetch 로 원문을 연다(종전 'URL만 있으면 그 기사' 규칙에 그대로 물림).
  #   미디어(media) = ask_link_stt.sh(자막 우선 → Whisper large-v3)로 전사문을 확보해 **전문(원문)으로** 주입 = 검색 없이 그 내용만으로 큐레이션.
  #   전사는 워크플로 선처리(ASK_LINK_DIR/<base>.txt)를 우선 쓰고, 없으면 여기서 인라인 전사(수동 dispatch·구 런 호환). 실패 = fail-soft(링크는 URL로라도 전달).
  link="$(python3 -c "import json; print((json.load(open('$f')).get('link') or '').strip())" 2>/dev/null || true)"
  LINK_BLOCK=""
  if [ -n "${link// }" ]; then
    lkind="$(python3 .github/scripts/ask_link.py --classify "$link" 2>/dev/null || true)"
    if [ "$lkind" = "media" ]; then
      trfile="${ASK_LINK_DIR:-/tmp/asklink}/${base}.txt"
      if [ ! -s "$trfile" ]; then
        mkdir -p "$(dirname "$trfile")"
        # 전사 강행(운영자 260731 "자막없으면 영상길이 제한, 단 강제 활성화 가능") — 링크칸에서 켠 건만 상한을 FORCE 값으로 올린다.
        lforce="$(python3 -c "import json; print('1' if json.load(open('$f')).get('linkForce') in (1,'1',True) else '')" 2>/dev/null || true)"
        _cap="${ASK_LINK_STT_MAX_SEC:-1800}"
        [ -n "$lforce" ] && _cap="${ASK_LINK_STT_FORCE_SEC:-3300}" && echo "· 전사 강행 ON — 길이 상한 ${_cap}s"
        echo "· 미디어 링크 전사(자막 우선 → Whisper large-v3): $link"
        ASK_LINK_STT_MAX_SEC="$_cap" timeout "${ASK_LINK_STT_TIMEOUT:-4800}" bash .github/scripts/ask_link_stt.sh "$link" "$trfile" || { echo "::warning::링크 전사 실패 — URL만 전달(fail-soft): $link"; rm -f "$trfile"; }
      fi
      if [ -s "$trfile" ]; then
        LINK_BLOCK="[🎧 운영자가 준 미디어 링크(${link})를 전사한 전문 — **이 전사문이 곧 원문이다**. 다른 기사를 WebSearch 로 찾지 말고 이 전사 내용만으로 위 출력 포맷대로 큐레이션하라(전사에 없는 사실·수치·인용은 지어내지 마라 · 타임코드 [mm:ss]는 위치 표시일 뿐이니 본문에 옮기지 마라 · frontmatter url = 이 미디어 링크 · media/reporter/date 는 전사 메타에 있는 만큼만). image_sources 만 위 1)의 예외 규칙대로 best-effort 검색:
$(head -c 60000 "$trfile")
]
"
      else
        LINK_BLOCK="[🔗 운영자가 준 미디어 링크(${link}) — 전사에 실패했다. WebFetch 로 열어 제목·설명 등 확보 가능한 정보로 best-effort 큐레이션하고, 부족하면 그 주제를 WebSearch 로 보완하라(frontmatter url = 이 링크).]
"
      fi
    elif [ "$lkind" = "article" ]; then
      LINK_BLOCK="[🔗 운영자가 준 원문 링크: ${link} — **이 링크가 원문이다**. WebFetch 로 열어 그 기사 본문으로 큐레이션하라(다른 기사 탐색은 이 원문이 안 열릴 때만 · frontmatter url = 이 링크 · 매체·기자·게시일시는 이 원문에서 추출). 요청문 텍스트는 이 원문을 어떻게 다룰지에 대한 운영자 지시로 읽어라.]
"
    fi
  fi
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

  # ── 출처 글 본문 이미지 수확(운영자 260804 · 사고 fail-2026-08-04-0239-297it 봉합) ──
  #   SNS 카드 「전송」은 {제목 + 글 주소 + RSS 요약}만 보낸다(viewer socBindSend · images 0장).
  #   그런데 커뮤니티 글은 **본문 자체가 이미지**인 경우가 흔하다 → 텍스트가 0이라 Claude 가 페이지를
  #   정상으로 열고도(WebFetch 성공) 읽을 게 없어 ANALYSIS_FAILED 로 끝났다(실측: 제목 "이런걸 재능이라고
  #   하는구나"는 검색 키워드가 0이라 프롬프트 1-2 기사 유추 폴백도 공회전).
  #   ⚠️ 사고의 정체 = '못 읽음'도 '뜻 모름'도 아닌 **읽을 글이 그림뿐**. 그런데 파이프엔 이미 멀티모달
  #   레일이 있었다(위 images[] → img-*.jpg → 프롬프트 '첨부 캡처') — 그 레일에 본문 그림이 안 실렸을 뿐.
  #   → 여기서 출처 URL 의 본문 이미지를 내려받아 같은 레일에 태운다(신규 분석 로직 0 · 실측 = 그 글의
  #   이미지 2장을 읽으니 '보험 직업분류: 남성은 전업주부 선택 불가' 화제가 그대로 드러났다).
  #   스코프 = 출처 URL 축 전용(srcUrl 우선 → 없으면 요청문 첫 URL) · link 레일이 잡은 요청은 무접촉
  #   (그쪽은 이미 원문·전사문을 확보한다) · 실패는 전부 fail-soft(수확이 요약을 죽이지 않는다).
  srcurl="$(python3 -c "import json; print((json.load(open('$f')).get('srcUrl') or '').strip())" 2>/dev/null || true)"
  SRCIMG_BLOCK=""
  if [ -z "$LINK_BLOCK" ] && [ "${ASK_SRCIMG:-1}" != "0" ]; then   # ASK_SRCIMG=0 = 롤백 킬스위치
    _su="${srcurl}"
    [ -z "${_su// }" ] && _su="$(NM_T="${text}" python3 -c '
import os, re
m = re.search(r"https?://\S{8,}", (os.environ.get("NM_T") or ""))
print(m.group(0)[:400] if m else "")
' 2>/dev/null || true)"
    if [ -n "${_su// }" ]; then
      _sj="$(timeout "${ASK_SRCIMG_TIMEOUT:-150}" python3 .github/scripts/ask_srcimg.py "$_su" "$workdir" --max "${ASK_SRCIMG_MAX:-4}" 2>/dev/null || true)"
      [ -n "${_sj// }" ] || _sj='{}'   # ⚠ 기본값을 ${_sj:-{}} 로 쓰면 안 된다 — 브레이스가 먼저 닫혀 파싱이 깨진다(실측: 수확 성공인데 로그만 '판독 실패')
      echo "· 출처 본문 이미지 수확: $(printf '%s' "$_sj" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("why") or "산출 없음")' 2>/dev/null || echo '판독 실패(fail-soft)')"
      srcimglist=""
      for im in "$workdir"/src-*; do [ -e "$im" ] && srcimglist="${srcimglist}- ${im}\n"; done
      if [ -n "$srcimglist" ]; then
        SRCIMG_BLOCK="[🖼 출처 글의 본문 이미지 — 운영자가 보낸 글(${_su})의 **본문에 실려 있던 그림을 스크립트가 내려받아 붙였다**. ⭐ **Read 로 반드시 전부 열어라** — 커뮤니티 글은 본문이 그림뿐인 경우가 많아, 이 그림이 사실상 원문이다(실제로 이 경로의 요약 실패는 전부 '그림을 못 봐서'였다).
 - 그림 안의 글·대화·자막·화면캡처·표를 읽어 **무슨 화제인지 확정**하고, 그걸 사실의 축으로 삼아 위 출력 포맷대로 큐레이션하라.
 - 그림에서 사건·인물·기관·제품 같은 고유명사나 쟁점을 뽑았으면 **그 키워드로 WebSearch** 해 관련 보도로 보강하라(상한은 위 6회 규칙 그대로). 제목만으로는 검색어가 안 나오던 글도 그림을 읽으면 검색어가 나온다.
 - 관련 보도가 없는 유머·일상·후기·화면캡처성 화제면 **기사를 억지로 찾지 마라** — 그 게시물 자체가 소재다. 그림에서 읽은 내용으로 완성하라(frontmatter url = 이 글 주소).
 - ⚠️ 장식·광고·추천 배너가 섞여 올 수 있다(수확은 기계적이다) — 본문과 무관해 보이는 그림은 그냥 무시하고, 남은 것으로 판단하라.
 - ⚠️ 그림까지 읽었는데도 불확실하면 **확인된 것만 좁게** 쓰되 ANALYSIS_FAILED 는 내지 마라(위 5) 불변).
파일:
$(printf '%b' "$srcimglist")]
"
      fi
    fi
  fi

  if [ -z "${text// }" ] && [ -z "$imglist" ] && [ -z "$LINK_BLOCK" ]; then   # 링크만 넣은 요청도 유효(운영자 260731)
    mkdir -p asks/failed; echo "빈 요청" > "asks/failed/${base}.log"
    git mv "$f" "asks/failed/${base}.json" 2>/dev/null || mv "$f" "asks/failed/${base}.json"
    echo "$base" >> "$ASK_FAIL_RUN"   # 이번 런 실패 기록(stale-red 차단)
    echo "::endgroup::"; continue
  fi

  # 고정부(프롬프트 + 주입 지침) → 가변부(요청) 순서 = 캐시 prefix 안정화.
  prompt="$(cat "$PROMPT_FILE")

${GBLOCK}

[★ 요약 요청 모드 — 운영자가 자연어 + 캡처로 큐레이션을 직접 요청했다.
 1) ⭐ **기본값 = 보강 모드(운영자 260803 「보강이 기본값」 — 구 260704 '전문만으로 바로 큐레이션' 폐지·역전)**: 요청문에 기사 본문급 전문(수백 자 이상)이 들어 있으면 그 전문은 '사실의 축'(원문)이다 — 축만 되풀이해 요약하고 끝내지 말고, WebSearch(아래 상한 내)로 **원문에 빠진 축을 찾아 채워 교차확인한 보강 다이제스트**를 내라. 보강 우선순위 = ① 덩어리 숫자의 내역 분해(총액→구성) ② 반대편·상대 당사자의 주장(원문이 한쪽 입장만 담았으면 필수) ③ 사건 경위·이전 보도 맥락(타임라인 재료) ④ 핵심 실체의 정체(등장 회사·기관·인물이 어떤 곳/누구인지) ⑤ 예정된 다음 단계. 원문과 보강 사실이 충돌하면 다수·최신 보도를 우선하되 단정 대신 병기하고, 결과가 아직 안 나온 사안은 「미확정」으로 정직하게 표기하라(없는 사실 날조 금지 불변). ⚠️ 유일한 예외 = 아래 프리셋에 「원본 한정」이 있으면 이 보강 검색 전부를 생략한다(그 블록이 항상 우선). ⚠️ **관련이미지 소스(image_sources)는 별도 규칙이다**: 전문이 있어도 frontmatter \`image_sources\`는 위 문서의 image_sources 규칙(전문 = 소스 URL 2~3개까지만 best-effort)대로 WebSearch 해 채워라 — 뷰어 '검색 이미지'가 이 URL들의 대표사진(og:image)을 가져오는 유일한 원료다(비우면 관련 이미지 0장 · 운영자 260710 '검색 이미지는 유지, AI 썸네일 생성만 스킵'). 몇 번에 안 나오면 있는 만큼만 넣고 빈 값도 허용 — 요약 완성이 항상 우선(검색어 바꿔가며 여러 번 검색 = 금지 불변 · 예외는 image_sources 한 필드뿐이라 원문 \`url:\` 은 아래 4) 그대로 빈 값 유지). 전문 없이 본문에 URL만 있으면 그 기사를(운영자가 직접 고른 URL은 오래됐어도 존중), URL·전문 없이 토픽/캡처만 있으면 WebSearch 로 '제일 메이저' 기사 1건(여럿이면 합쳐서 핵심)을 찾는다. ⚠️ **토픽/캡처 검색 시 = 최신 우선(18시간 내)**: 같은 사안이면 **최근 18시간 내 보도 중 가장 메이저한 것**을 골라라(며칠·몇 주 지난 옛 기사가 뉴스요약 피드 상단 채우는 문제 방지 — 운영자 260702). 18시간 내 보도가 없으면 그중 가장 최근 것으로(억지 최신화·날짜 조작 금지), *최신 보도가 있는데 옛 기사를 고르지는 마라*. ⚠️ **검색 상한 = 총 6회(보강 검색 포함 · 260803 — 구 2~3회에서 보강 기본값 전환과 함께 상향)** — 상한 안에서 안 나오는 축은 비워두고 있는 정보로 best-effort 완성하라(무한 검색으로 타임아웃 나면 아예 요약이 0이 된다 — 요약 완성이 보강보다 항상 우선).
 1-2) ⭐ **요청문이 국내 커뮤니티 게시글이면(제목 + 커뮤니티 URL[fmkorea·theqoo·dcinside·mlbpark·clien·보배드림·인스티즈 등], 본문 없음·짧은 스니펫만) = 커뮤니티 원문은 봇 차단으로 못 열릴 수 있으니 제목의 핵심 키워드로 WebSearch 해 같은 화제를 다룬 메이저 기사를 찾아 요약하라**(대상 = 게시글이 아니라 그 화제 · 커뮤니티 제목 특유 표현 .jpg·ㅋㅋ·밈·축약은 핵심 키워드로 정제해 검색). 이 폴백은 자동이다 — 원문 fetch 성공 여부와 무관하게 화제의 메이저 보도를 우선한다(운영자 260729). 검색 상한(총 6회)·최신 우선(18시간)은 위와 동일.
 1-3) ⭐ **그 커뮤니티 글의 본문이 '그림뿐'일 때(260804 실측 사고 봉합)**: 커뮤니티 글은 본문 텍스트가 0이고 이미지 몇 장이 전부인 경우가 흔하다 — 이때 **제목은 검색어가 되지 못한다**(실패 사례 제목 = "이런걸 재능이라고 하는구나" = 사건·인물·고유명사 0). 제목만 붙들고 검색을 반복하지 마라, 안 나온다. 순서는 이렇다: ① 위 🖼 블록으로 **본문 이미지가 첨부돼 있으면 그것부터 Read** 해 화제를 확정한다(그림 안의 글·화면캡처가 곧 원문이다) → ② 거기서 나온 고유명사·쟁점으로 WebSearch 해 보도를 보강한다 → ③ 보도가 없으면 **그 게시물 자체를 소재로** 완성한다(기사가 없는 화제도 큐레이션 대상이다 — 억지 기사 매칭 금지). 이미지 블록이 없고 제목도 검색어가 안 되면 ③으로 바로 간다. **어느 경로든 ANALYSIS_FAILED 는 답이 아니다**(아래 5)).
 2) 첨부 캡처 파일이 있으면 Read 로 열어 단서로 활용한다.
 3) 찾은 기사로 위 지침·출력 포맷 그대로 큐레이션 다이제스트를 생성한다.
 4) ⭐ 찾은 '제일 메이저' 기사의 **원본 URL(WebFetch/WebSearch로 실제 접근·확인한 것만)을 frontmatter \`url:\` 에 넣어라**(뷰어 상단 '원문' 링크로 노출된다). ⚠️ 스니펫에서 본 듯한 URL을 추측·조립하지 마라(사실 무결성) — 실제 확인한 기사 URL이 하나도 없을 때만 url 을 빈 값으로. 그리고 **그 기사에서 기자(reporter)·게시일시(date·time)·매체(media)를 추출해 frontmatter + 본문 '출처:' 줄 양쪽에 정확히 반영**하라(토픽/캡처 요청이라도 네가 찾아 확인한 그 기사가 곧 원문이다). ⚠️ **요청문에 전문이 이미 있으면** = url 전용 추가 검색은 하지 마라(1)의 보강 검색 상한 안에서 부수적으로만) — 보강 검색 도중 **같은 기사**(제목·기자·매체가 전문과 일치)의 URL을 실제 접근으로 확인한 경우에만 url 에 넣고(뷰어 '원문' 링크 활성 · 260803 — 구 '우연히 확인해도 빈 값 유지' 폐지), 확인 못 했으면 종전대로 url 은 빈 값(추측 조립 금지 불변). 매체·기자·일시는 전문 안에 적힌 것을 1순위로 추출하고, 전문에 없는 항목만 확인된 같은 기사에서 보충하라(둘 다 없으면 비워둠). 전문 없이 토픽/URL로 찾은 경우에만 그 기사 URL을 넣는다.
 5) 내용이 모호해도 절대 실패(ANALYSIS_FAILED)하지 말고 best-effort 로 큐레이션한다 — 이 건은 운영자가 직접 고른 것이다.
 ⛔ Write/Edit/Bash 금지(스크립트가 저장한다). frontmatter '---' 로 시작하는 다이제스트만 출력.]

${PRESET_BLOCK}
${LINK_BLOCK}
${SRCIMG_BLOCK}
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

  # 출처괄호 백스톱(운영자 260723) — 초안(```text) 본문 괄호 매체표기 기계 제거(analyze.sh 동일 백스톱과 한 쌍 ·
  #   정본 표기 = 01_지침 [⚡ 출처 분기] B/B-간소 · fail-soft = 오류·빈 출력 시 원문 유지).
  _nc="$(printf '%s\n' "$out" | python3 .github/scripts/strip_cites.py 2>/tmp/_sc_note || true)"
  if [ -n "${_nc// }" ] && [ "$_nc" != "$out" ]; then
    echo "  출처괄호 백스톱 — 초안 본문 괄호 매체표기 제거(⚡ 줄 일원화): $(tr '\n' '·' < /tmp/_sc_note 2>/dev/null)"
    out="$_nc"
  elif [ -s /tmp/_sc_note ]; then
    echo "  출처괄호 백스톱 — $(tr '\n' '·' < /tmp/_sc_note)"   # 계측(평의회1 한 수): 전무 가드 발동 등 무변경 사유도 로그
  fi

  id="ask-$(printf '%s' "$base" | tr -cd 'A-Za-z0-9' | cut -c1-18)"
  outfile="queue/${stamp}-${id}.md"
  n=2; while [ -e "$outfile" ]; do outfile="queue/${stamp}-${id}-${n}.md"; n=$((n+1)); done
  printf '%s\n' "$out" > "$outfile"
  # 분량 가드(기본 OFF · SUMMARY_LEN_GUARD='1' 카나리아) — IG/Thread 과소 시 자유요약에서 1회 보강(잡 예산 내 · fail-soft · 260705 · repair ≤+480s는 다음-기사 헤드룸(2×600s) 내 = 잡 최악 무변·평의회8)
  if [ "$SECONDS" -le "$ASK_JOB_DEADLINE" ]; then summary_repair "$outfile" ask-repair; fi
  # 규격·자수 기계 린트(비차단 · analyze.sh 미러 · 분신술② NEW-1 · 260703) — ask 경로 다이제스트 사각지대 해소(검증4). 가드 뒤 = 최종본 실측.
  python3 shared/digest_guard.py "$outfile" 2>/dev/null | sed 's/^/  /' || true
  rm -f "$f"
  rm -f "asks/failed/${base}.json" "asks/failed/${base}.log"   # 성공이 격리를 이긴다 — 병렬 중복 런의 성공/실패 발산 시 '피드 성공+대기열 FAIL' 공존 차단(적대검증 B1 · git add asks 가 삭제도 스테이지)
  title="$(grep -m1 '^title:' <<<"$out" | sed -E 's/^title:[[:space:]]*//; s/^"//; s/"$//')"
  title_ko="$(grep -m1 '^title_ko:' <<<"$out" | sed -E 's/^title_ko:[[:space:]]*//; s/^"//; s/"$//')"   # 외신 한국어 번역 제목(완료 푸시 우선 · analyze.sh 미러 · 260703)
  echo "${title_ko:-${title:-$id}}" >> /tmp/analyzed_titles.txt
  basename "$outfile" >> /tmp/analyzed_files.txt   # 완료 푸시 딥링크용(요약 창 ?a=)
  echo "성공 → $outfile (${title:-$id})"
  # ── 건별 조기 착지(운영자 260728 "원천 해결") — 레퍼런스 = ly-make.yml 조기 커밋 + Commit 스텝 pull 관용구 그대로.
  #   유실의 뿌리 = 산출물 보존이 런 끝 단일 커밋 1점(260727 실측: 요약 완성 4초 뒤 커밋 거부 = 완성본 통째 유실 →
  #   pending-sweep 크론 실측 62~140분 지연에 물려 회수까지 126분). 성공한 그 자리에서 {다이제스트 + 소비한 ask 삭제 +
  #   failed 격리 정리}를 즉시 커밋·푸시하면 유실 창이 런 전체(수십 분) → 건당 수 초로 봉인 = 뒤 스텝·타 기사 실패·
  #   러너 증발·push 전패 어느 방아쇠에도 완료분은 무사, 회수 크론 지연은 무해화.
  #   ⓐ fail-soft — 미착지여도 런은 계속, 최종 Commit 스텝이 종전대로 줍는다(2중 방어 · 악화 경로 0).
  #   ⓑ 이 푸시의 asks/** 변경 = 소비 삭제뿐 → news-ask 재트리거는 ASK_ONLY diff-filter=AM no-op 분기가 즉시 종료(기설계 계승).
  #   ⓒ git_land.sh 미사용 사유 = reset --hard 재적층이 런 중간의 미커밋 상태(앞 기사 failed git mv 등)를 파괴 —
  #      유일 기록자 전제도 asks 공유 경로라 미충족. 조기 커밋+rebase 관용구(ly-make 정본)가 상태 보존형이라 적합.
  if [ -n "${GITHUB_ACTIONS:-}" ]; then
    git config user.name  "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git add "$outfile" asks
    if git commit -q -m "ask: 요약 요청 큐레이션(조기 착지) ${base}"; then
      _landed=0
      for _i in 1 2 3; do
        if git pull --rebase --autostash -X theirs origin main && git push origin HEAD:main; then _landed=1; break; fi
        git rebase --abort 2>/dev/null || true
        sleep $((_i * 2))
      done
      if [ "$_landed" = 1 ]; then echo "  조기 착지 완료 → $outfile"
      else echo "::warning::조기 착지 push 미완(${base}) — 로컬 커밋은 보존, 최종 Commit 스텝이 줍는다"; fi
    fi
  fi
  echo "::endgroup::"
done
