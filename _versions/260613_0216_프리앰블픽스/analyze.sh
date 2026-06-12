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

  out="$(timeout 600 claude -p "$(cat "$PROMPT_FILE")

분석할 기사 URL: ${url}" \
        --model "$MODEL" \
        --allowedTools "WebFetch,WebSearch" \
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
    echo "실패 → pending/failed/${base}"
    echo "::endgroup::"; continue
  fi

  # 성공: ASCII 파일명(타임스탬프+기사ID) — 충돌 시 -2, -3 …
  id="$(article_id "$url")"
  title="$(grep -m1 '^title:' <<<"$out" | sed -E 's/^title:[[:space:]]*//; s/^"//; s/"$//')"

  outfile="queue/${stamp}-${id}.md"
  n=2; while [ -e "$outfile" ]; do outfile="queue/${stamp}-${id}-${n}.md"; n=$((n+1)); done
  printf '%s\n' "$out" > "$outfile"
  rm -f "$f"
  echo "${title:-$id}" >> /tmp/analyzed_titles.txt
  echo "성공 → $outfile"
  echo "::endgroup::"
done
