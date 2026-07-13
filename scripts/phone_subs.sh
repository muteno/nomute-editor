#!/usr/bin/env bash
# 폰(termux)/맥 구독 수집 크론 진입점(운영자 260712 "ㄱ") — X·인스타·스레드를 수집해 main에 직푸시.
# 기존 기사 공유 경로(termux-share·queue-handler)와 완전 분리(산출 = viewer/sns_subs_phone.json 한 파일).
# 설치(폰에서 1회):
#   pkg install python cronie termux-services && sv-enable crond
#   crontab -e →  */30 * * * * bash ~/nomute-editor/scripts/phone_subs.sh >> ~/phone_subs.log 2>&1
#   (레포 클론 경로가 다르면 위 경로만 맞춰줘 · 안드로이드 설정 > 배터리 > Termux 제한 없음)
# 맥 설치(1회 · 운영자 260712 "맥에서 크롬 통해 접근" — 스레드는 가정 IP가 유일 공급원):
#   레포 클론 후  crontab -e →  */30 * * * * bash ~/nomute-editor/scripts/phone_subs.sh >> ~/phone_subs.log 2>&1
#   (macOS 기본 python3·git으로 동작 = 추가 패키지 0 · 크롬 로그인과 무관한 게스트 HTML 파싱이라 브라우저 불요)
set -e
cd "$(dirname "$0")/.."
# 폰 로컬 시크릿(git 밖 · cron은 .bashrc 미로드라 여기서 source) — 재난문자 등 키 필요 소스용.
# 1회 설정(폰):  echo "export SAFETY_KEY='발급받은_재난문자_서비스키'" > ~/.nomute_phone_env
[ -f "$HOME/.nomute_phone_env" ] && . "$HOME/.nomute_phone_env"
git fetch origin main -q 2>/dev/null || true
git pull -q --rebase origin main 2>/dev/null || true   # 최신 계정 목록(sns_accounts.json) 동기
python3 scripts/phone_subs.py || exit 0                # 수집 실패 = 조용히 종료(다음 주기 · fail-soft)
git add viewer/sns_subs_phone.json
git diff --cached --quiet && exit 0                    # 변동 없음 = 무커밋
git commit -q -m "phone-subs: 구독·레딧·재난문자 폰 수집"
for i in 1 2 3 4; do
  git pull -q --rebase origin main 2>/dev/null || true
  git push -q origin HEAD:main && exit 0 || { echo "push 재시도 $i"; sleep $((2**i)); }
done
echo "push 실패(재시도 소진) — 다음 주기 재시도"   # 트렌드는 30분 뒤 재수집 = 유실 개념 없음
