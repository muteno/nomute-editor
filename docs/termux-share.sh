#!/data/data/com.termux/files/usr/bin/bash
# 노뮤트 뉴스 큐 — Termux 공유 스크립트 (참고용 · 실전판은 폰재구축플레이북 §5)
# 설치:
#   1) Termux + Termux:API 설치, `pkg install git termux-api`
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
git reset -q --hard origin/main

mkdir -p pending
echo "$URL" > "pending/$(date +%y%m%d-%H%M%S).txt"
git add pending
git -c user.name=muteno-phone -c user.email=phone@nomute commit -qm "queue: $URL"

if git push -q origin HEAD:main; then
  notify "큐 등록됨 ✅" "$URL"; log "OK"
else
  notify "큐 등록 실패 ❌" "Termux 열어 git push 확인"; log "PUSH_FAIL"
fi
