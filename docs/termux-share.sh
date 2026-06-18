#!/data/data/com.termux/files/usr/bin/bash
# 노뮤트 뉴스 큐 — Termux 공유 스크립트 (참고용 · 실전판은 폰재구축플레이북 §5)
# 설치:
#   1) Termux + Termux:API 설치, `pkg install git termux-api`
#      (전문 붙여넣기 경로는 추가 패키지 0개. URL 공유→폰 선-fetch 를 쓰려면 `python libiconv` 추가)
#   2) git clone <레포> ~/nomute-editor (또는 이미 있으면 생략)
#   3) 이 파일을 ~/bin/queue-news 로 복사하고 chmod +x
#   4) Termux:Tasker/공유 시트에 "queue-news"를 등록(공유 → Termux)
# 사용: 폰에서 기사 '공유 → Termux(queue-news)' → URL이 pending/ 에 push됨
# 로그: 매 시도가 ~/nomute-queue.log 에 남는다(알람 꺼도 성공/실패 확인 가능).

INPUT="$*"               # 공유된 전체(URL 또는 기사 '전체선택→공유' 전문)
notify(){ termux-notification -t "$1" -c "$2" 2>/dev/null || true; }
URL="$(printf '%s' "$INPUT" | grep -oE 'https?://[^ "'"'"'<>]+' | head -1)"
# 한글 음절(가-힣)의 UTF-8 lead 바이트(0xEA~0xED) 수 ≈ 글자수 — LC_ALL=C 라 로케일 무관(폰 바이트모드여도 일관).
HANGUL=$(printf '%s' "$INPUT" | LC_ALL=C grep -oE $'[\xea-\xed]' | wc -l)   # 200자+ = 전문 붙여넣기 판정
logline(){ echo "$(date '+%y-%m-%d %H:%M:%S') | $1 | ${LINE1:-$URL}" >> ~/nomute-queue.log; }

cd ~/nomute-editor || { notify "큐 실패" "리포 폴더 없음"; logline "NO_REPO"; exit 1; }

if [ "$HANGUL" -ge 200 ]; then
  # ── 전문 붙여넣기(전체선택→공유) — 403·JS·페이월 *전부* 우회, fetch 안 함. 안의 링크는 무시 ──
  LINE1="paste:$(printf '%s' "$INPUT" | sha1sum | cut -c1-12)"   # 합성 id(원문 URL 없음·dedup용)
  BODY="$(printf '%s' "$INPUT" | head -c 20000)"   # iconv 불필요 — 분석기가 iconv -c 로 정리(전문경로 = libiconv 의존 0)
else
  # ── URL 경로 — 폰 선-fetch(403 우회). repo의 fetch_article.sh로 폰(200)에서 본문 선취득 ──
  [ -z "$URL" ] && { notify "큐 실패" "URL/전문 못 찾음"; logline "NO_URL"; exit 1; }
  LINE1="$URL"
  # ⚠️ 전제: `pkg install python libiconv`(없으면 추출 빈값 → 클라우드 폴백).
  git fetch -q origin main && git reset -q --hard origin/main   # repo의 fetch_article.sh 최신화
  BODY="$(timeout 20 bash .github/scripts/fetch_article.sh "$URL" 2>/dev/null || true)"
fi
# main은 자동 파이프라인(분 단위 커밋)으로 분주 → push non-ff 거부가 실패 1순위. 매 시도 reset 후
# pending 새로 찍어 push 재시도(2·4·6·8s 백오프, 5회)로 흡수.
mkdir -p pending
FNAME="pending/$(date +%y%m%d-%H%M%S)-$RANDOM.txt"
OK=0
for try in 1 2 3 4 5; do
  if ! git fetch -q origin main; then
    notify "큐 실패 ❌" "git fetch 실패 — 네트워크/PAT 확인"; logline "FETCH_FAIL"; exit 1
  fi
  git reset -q --hard origin/main          # 최신 원격에 맞춤(이때 FNAME도 지워짐)
  # reset 후 재기록 — 본문(URL경로=선-fetch / 전문경로=붙여넣은 텍스트)이 있으면 '# body:' 동봉.
  if [ -n "${BODY//[$' \t\r\n']/}" ]; then
    printf '%s\n# body:\n%s\n' "$LINE1" "$BODY" > "$FNAME"
  else
    echo "$LINE1" > "$FNAME"                # 본문 없음(JS렌더·페이월) → line1만(클라우드 폴백)
  fi
  git add pending
  git -c user.name=muteno-phone -c user.email=phone@nomute commit -qm "queue: $LINE1" \
    || { notify "큐 실패 ❌" "commit 실패(중복/빈 변경?)"; logline "COMMIT_FAIL"; exit 1; }
  if git push -q origin HEAD:main; then OK=1; break; fi
  sleep $((try * 2))                        # 백오프 후 재동기화·재시도
done

if [ "$OK" = 1 ]; then
  notify "큐 등록됨 ✅" "$LINE1"; logline "OK"
else
  notify "큐 등록 실패 ❌" "5회 재시도 실패 — Termux 열어 git push 확인"; logline "PUSH_FAIL"
fi
