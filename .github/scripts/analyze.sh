#!/usr/bin/env bash
# pending/*.txt 를 순회하며 각 URL을 Claude Code 헤드리스(claude -p)로 큐레이션 분석 →
# 결과 md를 queue/ 에 저장, 처리한 pending 삭제, 실패는 pending/failed/ 로 격리.
# 큐 전체가 한 건 실패로 죽지 않게 per-file로 처리한다.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PROMPT_FILE="prompts/news-analysis.md"
MODEL="claude-opus-4-8"
: > /tmp/analyzed_titles.txt
: > /tmp/analyzed_failures.txt   # 실패 URL 적재 → 워크플로가 잡을 빨갛게(조용한 실패 차단)

# 지침 SSOT 강제 주입 — live 에디터 지침을 프롬프트 고정부에 떠먹인다(읽기 의존 X = 강제).
# GVER(지침 버전 도장)는 산출물 frontmatter에 박혀, 지침이 바뀌면 같은 기사 재공유 시 재생성된다.
source "$ROOT/shared/inject_guidelines.sh"
GVER="$(guidelines_version summary)"
GBLOCK="$(guidelines_block summary)"
echo "지침 버전(summary): ${GVER}"

shopt -s nullglob
files=(pending/*.txt)
if [ ${#files[@]} -eq 0 ]; then
  echo "pending 비어있음 — 종료"
  exit 0
fi

# 파일명 = ASCII-safe 한정 (타임스탬프 + URL 유래 기사ID). 한글 제목은 frontmatter title에만.
# (구 슬러그 방식은 cut -c 바이트 절단이 UTF-8 멀티바이트를 깨뜨려 폐지 — run#2 ENOENT 원인)
article_id() {
  local u="$1" id
  id=$(printf '%s' "$u" | sed -E 's/[?#].*$//; s:/+$::; s:.*/::' | tr -cd 'A-Za-z0-9._-' | cut -c1-24)
  [ -n "$id" ] || id=$(printf '%s' "$u" | sha1sum | cut -c1-8)
  printf '%s' "$id"
}

for f in "${files[@]}"; do
  base="$(basename "$f" .txt)"        # YYMMDD-HHMMSS
  stamp="${base:0:11}"                # YYMMDD-HHMM
  url="$(head -n1 "$f" | tr -d '\r\n')"
  echo "::group::분석: $url"

  if [ -z "$url" ]; then
    mkdir -p pending/failed
    echo "빈 URL" > "pending/failed/${base}.log"
    git mv "$f" "pending/failed/${base}.txt" 2>/dev/null || mv "$f" "pending/failed/${base}.txt"
    echo "::endgroup::"; continue
  fi

  # 중복 방지 + 지침 게이트 — 같은 기사(article_id)가 이미 queue/ 에 있으면:
  #   · 그 카드의 지침 버전 == 현재 == 진짜 중복 → 분석 생략(토큰 절약, 카드 2장 버그 차단).
  #   · 다르면(지침이 그새 갱신됨) → 재생성(덮어쓰기). 잘못된 1개보다 제대로 된 1개를 2× 비용으로.
  id="$(article_id "$url")"
  REGEN_TARGET=""
  existing="$(compgen -G "queue/*-${id}.md" 2>/dev/null | head -n1 || true)"
  if [ -n "$existing" ]; then
    ev="$(grep -m1 '^guidelines_version:' "$existing" | sed -E 's/^guidelines_version:[[:space:]]*"?([^"]*)"?.*/\1/')"
    if [ "$ev" = "$GVER" ]; then
      echo "중복 — 같은 지침 버전 카드 있음(${id} / ${GVER}) → 분석 생략"
      rm -f "$f"
      echo "::endgroup::"; continue
    fi
    echo "지침 변경 감지(${ev:-없음}→${GVER}) — 재생성(덮어쓰기): $existing"
    REGEN_TARGET="$existing"
  fi

  # 인코딩 정규화 사전 추출 — 네이트(news.nate.com) 등 EUC-KR 매체를 모델 WebFetch 가
  # UTF-8 로 오독해 본문이 깨지는(���) 문제를 입구에서 차단. 빈약/실패면 빈 문자열 → 모델 WebFetch 폴백.
  extracted="$(bash .github/scripts/fetch_article.sh "$url" 2>/dev/null || true)"
  # 고정부(프롬프트 + 강제 주입 지침) → 가변부(기사) 순서 = 캐시 prefix 안정화.
  prompt="$(cat "$PROMPT_FILE")

${GBLOCK}

분석할 기사 URL: ${url}"
  if [ -n "${extracted// }" ]; then
    prompt="${prompt}

[사전 추출 본문 — 페이지 인코딩 정규화 완료(EUC-KR 등 → UTF-8). 이 텍스트를 1차 사실 출처로 삼아라. 부족하거나 검증이 필요하면 WebFetch/WebSearch 로 보강·교차확인하되, 추출이 충분하면 그대로 써도 된다]:
${extracted}"
  fi

  # 900s — 큐레이션 다이제스트 + 콘텐츠 초안(자유요약·IG·Thread·썸네일·시사점)까지 생성(260612 확장)
  # 허용 도구 = WebFetch·WebSearch(사실 확보) + Read·Glob·Grep(품질기준 §7 지침 읽기 — 읽기전용).
  # ⚠️ Write·Edit·Bash 류는 일절 불허(모델이 파일 쓰기·커밋을 시도하다 권한 대기로 멈춰
  # 다이제스트 대신 '승인 요청' 텍스트를 뱉어 failed 격리된 사건 대응 — 프롬프트 §⛔와 한 쌍).
  # --disallowedTools = 미허용 도구를 '권한 대기'가 아니라 '즉시 거부'로 만들어 헤드리스가
  #   절대 멈추지 않게(오늘 [D] 근인 = 허용목록만으론 Write/Bash 시도가 900s 행이 됨).
  # --max-turns = 도구 무한루프(레포 탐색 등) 차단. 둘 다 "제약없이=막힘없이"의 핵심.
  out="$(timeout 900 claude -p "$prompt" \
        --model "$MODEL" \
        --allowedTools "WebFetch,WebSearch,Read,Glob,Grep" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task" \
        --max-turns 40 \
        2> "/tmp/${base}.err")"
  rc=$?

  # 실패 판정: 비정상 종료 / 빈 출력 / 모델이 실패 신호 / frontmatter 없음
  if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^ANALYSIS_FAILED' <<<"$out" || ! grep -qm1 '^---' <<<"$out"; then
    mkdir -p pending/failed
    {
      echo "url: $url"
      echo "exit_code: $rc"
      echo "---- stderr ----"; cat "/tmp/${base}.err" 2>/dev/null
      echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 20
    } > "pending/failed/${base}.log"
    git mv "$f" "pending/failed/${base}.txt" 2>/dev/null || mv "$f" "pending/failed/${base}.txt"
    echo "$url" >> /tmp/analyzed_failures.txt
    echo "실패 → pending/failed/${base}"
    echo "::endgroup::"; continue
  fi

  # 모델이 frontmatter 앞에 사족(인사·진행 멘트)을 붙이는 드리프트 방어 — 첫 '---' 줄부터만 저장
  out="$(printf '%s\n' "$out" | sed -n '/^---[[:space:]]*$/,$p')"

  # 지침 버전 도장 — 첫 '---' 바로 뒤에 삽입(모델이 쓰는 게 아니라 스크립트가 박는다 = 정확).
  out="$(printf '%s\n' "$out" | awk -v v="$GVER" \
        '!done && /^---[[:space:]]*$/{print; print "guidelines_version: \"" v "\""; done=1; next} {print}')"

  # 성공: 재생성이면 기존 파일 덮어쓰기(스템·카드 연결 유지), 아니면 새 ASCII 파일명.
  title="$(grep -m1 '^title:' <<<"$out" | sed -E 's/^title:[[:space:]]*//; s/^"//; s/"$//')"
  if [ -n "$REGEN_TARGET" ]; then
    outfile="$REGEN_TARGET"
  else
    outfile="queue/${stamp}-${id}.md"
    n=2; while [ -e "$outfile" ]; do outfile="queue/${stamp}-${id}-${n}.md"; n=$((n+1)); done
  fi
  printf '%s\n' "$out" > "$outfile"
  rm -f "$f"
  echo "${title:-$id}" >> /tmp/analyzed_titles.txt
  echo "성공 → $outfile (지침 ${GVER})"
  echo "::endgroup::"
done
