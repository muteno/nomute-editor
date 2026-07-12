#!/usr/bin/env bash
# 폰(termux) 구독 수집 크론 진입점(운영자 260712 "ㄱ") — X·인스타만 수집해 main에 직푸시.
# 기존 기사 공유 경로(termux-share·queue-handler)와 완전 분리(산출 = viewer/sns_subs_phone.json 한 파일).
# 설치(폰에서 1회):
#   pkg install python cronie termux-services && sv-enable crond
#   crontab -e →  */30 * * * * bash ~/nomute-editor/scripts/phone_subs.sh >> ~/phone_subs.log 2>&1
#   (레포 클론 경로가 다르면 위 경로만 맞춰줘 · 안드로이드 설정 > 배터리 > Termux 제한 없음)
set -e
cd "$(dirname "$0")/.."
git fetch origin main -q 2>/dev/null || true
git pull -q --rebase origin main 2>/dev/null || true   # 최신 계정 목록(sns_accounts.json) 동기
python3 scripts/phone_subs.py || exit 0                # 수집 실패 = 조용히 종료(다음 주기 · fail-soft)
git add viewer/sns_subs_phone.json
git diff --cached --quiet && exit 0                    # 변동 없음 = 무커밋
git commit -q -m "phone-subs: X·인스타 폰 수집"
for i in 1 2 3 4; do
  git pull -q --rebase origin main 2>/dev/null || true
  git push -q origin HEAD:main && exit 0 || { echo "push 재시도 $i"; sleep $((2**i)); }
done
echo "push 실패(재시도 소진) — 다음 주기 재시도"   # 트렌드는 30분 뒤 재수집 = 유실 개념 없음
