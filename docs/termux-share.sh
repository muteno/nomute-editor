#!/data/data/com.termux/files/usr/bin/bash
# 노뮤트 뉴스 큐 — Termux 공유 스크립트 (참고용 · 실전판은 폰재구축플레이북 §5)
# 설치:
#   1) Termux + Termux:API 설치, `pkg install git termux-api python libiconv`
#      (python·libiconv = 폰 선-fetch 본문 추출용 — 없으면 본문 동봉이 조용히 빈값 됨)
#   2) git clone <레포> ~/nomute-editor (또는 이미 있으면 생략)
#   3) 이 파일을 ~/bin/queue-news 로 복사하고 chmod +x
#   4) Termux:Tasker/공유 시트에 "queue-news"를 등록(공유 → Termux)
# 사용: 폰에서 기사 '공유 → Termux(queue-news)' → URL이 pending/ 에 push됨
# 로그: 매 시도가 ~/nomute-queue.log 에 남는다(알람 꺼도 성공/실패 확인 가능).

URL="$*"                 # 공유 텍스트가 공백 분할될 수 있어 전체 재결합
notify(){ termux-notification -t "$1" -c "$2" 2>/dev/null || true; }
log(){ echo "$(date '+%y-%m-%d %H:%M:%S') | $1 | $URL" >> ~/nomute-queue.log; }

cd ~/nomute-editor || { notify "큐 실패" "리포 폴더 없음"; log "NO_REPO"; exit 1; }

# 진실원본 = origin/main. 폰 로컬은 '입구'일 뿐이라 갈리면 무조건 원격에 맞춘다(자가치유).
# (git pull 은 로컬 갈림·로컬 변경 때 조용히 실패 → push 깨짐의 1순위 원인이라 폐지)
if ! git fetch -q origin main; then
  notify "큐 실패 ❌" "git fetch 실패 — 네트워크/PAT 확인"; log "FETCH_FAIL"; exit 1
fi
# main은 자동 파이프라인(scrape·breaking·cards·social-scan…)이 분 단위로 커밋해 매우 분주하다.
# fetch~push 사이에 원격이 또 앞서가면 push가 non-fast-forward로 거부된다(시작 시점 reset만으론
# 못 막는 '경쟁' — 실패 빈번의 1순위 원인, 260618). 그래서 매 시도마다 최신 main에 다시 맞추고
# pending 파일을 새로 찍어 올린 뒤 push를 재시도한다(2·4·6·8s 백오프, 5회).
# 폰 선-fetch (근본 우회) — 클라우드 러너는 조선·동아·연합 등에 IP기반 403, 폰(가정용 IP)은 200.
# 본문을 폰에서 미리 긁어 '# body:'로 동봉하면 분석기가 클라우드 fetch 없이 그대로 쓴다(403 우회).
# repo의 fetch_article.sh 재사용(추출 단일 정본·6KB 캡). timeout·|| true 로 공유 UX 안 막음.
git reset -q --hard origin/main          # repo의 fetch_article.sh를 최신으로
FETCH_URL="$(printf '%s' "$URL" | grep -oE 'https?://[^ "'"'"'<>]+' | head -1)"
BODY="$(timeout 20 bash .github/scripts/fetch_article.sh "$FETCH_URL" 2>/dev/null || true)"
mkdir -p pending
FNAME="pending/$(date +%y%m%d-%H%M%S)-$RANDOM.txt"
OK=0
for try in 1 2 3 4 5; do
  if [ "$try" -gt 1 ] && ! git fetch -q origin main; then
    notify "큐 실패 ❌" "git fetch 실패 — 네트워크/PAT 확인"; log "FETCH_FAIL"; exit 1
  fi
  git reset -q --hard origin/main          # 최신 원격에 맞춤(이때 FNAME도 지워짐)
  # reset 후 재기록 — 선-fetch 본문(BODY, 루프 밖 1회)이 있으면 '# body:'로 끝에 동봉.
  if [ -n "${BODY//[$' \t\r\n']/}" ]; then
    printf '%s\n# body:\n%s\n' "$URL" "$BODY" > "$FNAME"
  else
    echo "$URL" > "$FNAME"                  # 본문 못 긁음 → URL만(클라우드 폴백)
  fi
  git add pending
  git -c user.name=muteno-phone -c user.email=phone@nomute commit -qm "queue: $URL" \
    || { notify "큐 실패 ❌" "commit 실패(중복/빈 변경?)"; log "COMMIT_FAIL"; exit 1; }
  if git push -q origin HEAD:main; then OK=1; break; fi
  sleep $((try * 2))                        # 백오프 후 재동기화·재시도
done

if [ "$OK" = 1 ]; then
  notify "큐 등록됨 ✅" "$URL"; log "OK"
else
  notify "큐 등록 실패 ❌" "5회 재시도 실패 — Termux 열어 git push 확인"; log "PUSH_FAIL"
fi
