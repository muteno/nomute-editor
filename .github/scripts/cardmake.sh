#!/usr/bin/env bash
# 카드뉴스 일괄 제작: 대상 queue/*.md → Claude 헤드리스 Step 4(카드 MD) → cards/<기사>/cards.md
# → (GDRIVE_SA_JSON 있으면) Drive 발사(기존 Apps Script→Gemini→Cloud Run 자동화) + _final_*.jpg 회수
# → 기사별 즉시 커밋·push(분석물 보존 최우선 — Pages가 그때그때 뷰어 갱신).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PROMPT_FILE="prompts/card-make.md"
MODEL="claude-opus-4-8"
TARGET="${1:-all}"

# 지침 SSOT 강제 주입 — 요약과 동일한 단일 헬퍼(주입 로직 갈라짐 방지). card 프로필.
source "$ROOT/shared/inject_guidelines.sh"
GVER="$(guidelines_version card)"
GBLOCK="$(guidelines_block card)"
echo "지침 버전(card): ${GVER}"

git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

push_main() {
  # news-analyze와 동일 전략: -X theirs(이 run의 산출물 우선), 충돌 시 abort 후 재시도
  for i in 0 1 2 3 4; do
    [ "$i" -gt 0 ] && sleep $((2**i))
    git pull --rebase -X theirs origin main && git push origin HEAD:main && return 0
    git rebase --abort 2>/dev/null || true
  done
  return 1
}

commit_push() {
  git add cards
  git diff --cached --quiet && return 0
  git commit -m "$1"
  push_main || { echo "::error::push 실패: $1"; return 1; }
}

status_json() {  # $1=dir $2=state
  printf '{"state":"%s","updated":"%s","guidelines_version":"%s"}\n' \
    "$2" "$(date -u +%FT%TZ)" "$GVER" > "$1/status.json"
}

# 대상 결정: all = cards/ 미존재(미제작) 큐 전체 / 그 외 = queue 파일명 1개
shopt -s nullglob
targets=()
if [ "$TARGET" = "all" ]; then
  for q in queue/*.md; do
    stem="$(basename "$q" .md)"
    if [ ! -d "cards/$stem" ]; then targets+=("$q"); continue; fi
    # 지침 게이트 — 카드의 지침 버전이 현재와 다르면(갱신됨) 재생성 대상에 포함.
    cv="$(grep -o '"guidelines_version":"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
    [ "$cv" = "$GVER" ] || { echo "지침 변경 — 카드 재생성 대상: $stem (${cv:-없음}→${GVER})"; targets+=("$q"); }
  done
else
  base="$(basename "$TARGET")"
  if [[ ! "$base" =~ ^[A-Za-z0-9._-]+\.md$ ]] || [ ! -f "queue/$base" ]; then
    echo "::error::잘못된 대상: $TARGET"; exit 1
  fi
  targets=("queue/$base")
fi
if [ ${#targets[@]} -eq 0 ]; then
  echo "대상 없음(전부 제작됨)"; exit 0
fi

# 시작 상태 일괄 커밋 → 뷰어에 ⏳
for q in "${targets[@]}"; do
  stem="$(basename "$q" .md)"
  mkdir -p "cards/$stem"
  status_json "cards/$stem" "generating"
done
commit_push "cards: 제작 시작 ⏳ ${#targets[@]}건"

fail=0
for q in "${targets[@]}"; do
  stem="$(basename "$q" .md)"
  echo "::group::카드 제작: $stem"

  # 고정부(프롬프트 + 강제 주입 지침) → 가변부(다이제스트) 순서 = 캐시 prefix 안정화.
  # --disallowedTools + --max-turns = 헤드리스 무중단(파일쓰기/권한대기/툴 무한루프 차단, analyze.sh와 동일).
  out="$(timeout 1500 claude -p "$(cat "$PROMPT_FILE")

${GBLOCK}

[큐레이션 다이제스트 — 이 기사로 카드뉴스 MD를 만든다]
$(cat "$q")" \
        --model "$MODEL" \
        --allowedTools "WebFetch,WebSearch" \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,Read,Glob,Grep" \
        --max-turns 40 \
        2> "/tmp/${stem}.err")"
  rc=$?

  # 실패 판정: 비정상 종료 / 빈 출력 / 실패 신호 / parsePrompts 필수 헤더 부재
  if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^CARDS_FAILED' <<<"$out" \
     || ! grep -qm1 '^### \[카드 1\]' <<<"$out" || ! grep -qm1 '^\*\*이미지 프롬프트\*\*' <<<"$out"; then
    {
      echo "exit_code: $rc"
      echo "---- stderr ----"; cat "/tmp/${stem}.err" 2>/dev/null
      echo "---- stdout(head) ----"; printf '%s\n' "$out" | head -n 30
    } > "cards/$stem/error.log"
    status_json "cards/$stem" "failed"
    commit_push "cards: $stem 제작 실패"
    fail=$((fail+1)); echo "::endgroup::"; continue
  fi

  # 모델 사족 방어 — 첫 '#' 줄(제목)부터 저장
  printf '%s\n' "$out" | sed -n '/^#/,$p' > "cards/$stem/cards.md"

  state="text_done"
  if [ -n "${GDRIVE_SA_JSON:-}" ]; then
    # Drive 폴더 주제명: 제목에서 문자 단위 16자(바이트 절단 금지 — run#2 교훈)
    topic="$(grep -m1 '^title:' "$q" | python3 -c "
import re, sys
t = re.sub(r'^title:\s*\"?|\"\s*$', '', sys.stdin.read().strip())
t = re.sub(r'[^0-9A-Za-z가-힣]+', '_', t)[:16].strip('_')
print(t or 'news')")"
    if python3 .github/scripts/drive_cards.py --md "cards/$stem/cards.md" --topic "$topic" --out "cards/$stem"; then
      state="done"
    else
      state="fired_partial"   # 발사됐으나 대기시간 내 미완/일부 — Drive에서 마저 생성될 수 있음
    fi
  fi
  status_json "cards/$stem" "$state"
  commit_push "cards: $stem ($state)"
  echo "::endgroup::"
done

# 전건 실패만 잡 실패로
[ $fail -eq ${#targets[@]} ] && exit 1 || exit 0
