#!/data/data/com.termux/files/usr/bin/bash
# 노뮤트 뉴스 큐 — Termux 공유 스크립트 (참고용)
# 설치:
#   1) Termux + Termux:API 설치, `pkg install git termux-api`
#   2) git clone <레포> ~/nomute-editor (또는 이미 있으면 생략)
#   3) 이 파일을 ~/bin/queue-news 로 복사하고 chmod +x
#   4) Termux:Tasker/공유 시트에 "queue-news"를 등록(공유 → Termux)
# 사용: 폰에서 기사 '공유 → Termux(queue-news)' → URL이 pending/ 에 push됨
set -e
cd ~/nomute-editor
git pull -q
mkdir -p pending
echo "$1" > "pending/$(date +%y%m%d-%H%M%S).txt"
git add pending && git commit -qm "queue: $1" && git push -q
termux-notification -t "큐 등록됨" -c "$1" 2>/dev/null || true
