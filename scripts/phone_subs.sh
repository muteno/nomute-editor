#!/usr/bin/env bash
# 폰(termux)/맥 구독 수집 크론 진입점(운영자 260712 "ㄱ") — X·인스타·스레드를 수집해 main에 직푸시.
# 기존 기사 공유 경로(termux-share·queue-handler)와 완전 분리(산출 = viewer/sns_subs_phone.json 한 파일).
# 설치(폰에서 1회):
#   pkg install python cronie termux-services termux-api && sv-enable crond
#   crontab -e →  */30 * * * * bash ~/nomute-editor/scripts/phone_subs.sh >> ~/phone_subs.log 2>&1
#   (레포 클론 경로가 다르면 위 경로만 맞춰줘 · 안드로이드 설정 > 배터리 > Termux 제한 없음)
#   ⚠ 야간 정지 방지 3층(운영자 260727) — 아래 termux-wake-lock은 ③층이고, ①②는 폰에서 1회 손으로 해야 한다:
#     ① Termux:API 앱 설치(F-Droid · `pkg install termux-api`는 CLI만 깔린다 = 앱이 없으면 웨이크락 무동작)
#     ② 안드 설정 > 배터리 > Termux = '제한 없음'(도즈가 앱 자체를 죽이는 축 · 웨이크락으로 못 막는다)
#     ③ 이 스크립트의 termux-wake-lock(아래) = CPU 재우기 방지 · 셋 다 있어야 새벽에 안 끊긴다
# 맥 설치(1회 · 운영자 260712 "맥에서 크롬 통해 접근" — 스레드는 가정 IP가 유일 공급원):
#   레포 클론 후  crontab -e →  */30 * * * * bash ~/nomute-editor/scripts/phone_subs.sh >> ~/phone_subs.log 2>&1
#   (macOS 기본 python3·git으로 동작 = 추가 패키지 0 · 크롬 로그인과 무관한 게스트 HTML 파싱이라 브라우저 불요)
set -e
cd "$(dirname "$0")/.."
# 절전 방지(운영자 260727 "폰 안 쓰는 시간대에도 살아있게 해야되겠는데") — 안드로이드 도즈가 crond를 재우면
# 이 스크립트는 **아예 실행되지 않는다**(260727 판례: 00:32~02:25 2시간 공백 = 스레드·인스타가 그동안 굶음).
# termux-wake-lock = CPU 웨이크락 획득 후 **의도적으로 해제 안 함**(다음 30분 주기까지 crond 생존 = 야간 연속성).
#   해제하면 즉시 도즈로 복귀 = 같은 공백 재발이라 trap 해제를 안 건다. 배터리 소모 증가는 감수(운영자 선택).
#   ⚠ 요구: `pkg install termux-api` + Termux:API 앱. 미설치·맥 = 조용히 건너뜀(fail-soft = 종전 동작 불변).
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock >/dev/null 2>&1 || true
# 폰 로컬 시크릿(git 밖 · cron은 .bashrc 미로드라 여기서 source) — 재난문자 등 키 필요 소스용.
# 1회 설정(폰):  echo "export SAFETY_KEY='발급받은_재난문자_서비스키'" > ~/.nomute_phone_env
# 부계 세션쿠키(선택 · Meta 로그인월 우회 — 무인증은 러너·컨테이너·폰 전부 429 실측 260726):
#   echo 'export THREADS_COOKIE="sessionid=…; ds_user_id=…"' >> ~/.nomute_phone_env
#   echo 'export INSTA_COOKIE="sessionid=…; ds_user_id=…; csrftoken=…"' >> ~/.nomute_phone_env   # 운영자 260726 · 미설정 = 게스트(종전 동작)
#   echo 'export INSTA_UA="chrome://version 의 사용자 에이전트 전체 문자열"' >> ~/.nomute_phone_env   # 쿠키 발급 브라우저 UA 고정(260729 「useragent mismatch」 — 메타가 세션을 발급 UA에 묶는다 · 쿠키와 짝 필수)
#   echo 'export THREADS_UA="위와 같은 UA 문자열"' >> ~/.nomute_phone_env   # ⚠ 스레드도 **같은 메타 정책** — 260729 봉합이 인스타에만 이식돼 스레드는 쿠키가 매번 무소득이었다(260805 실측 5계정 전건) · THREADS_COOKIE와 **한 쌍**으로 넣어라(하나만 갈면 또 어긋난다 · 쿠키·UA는 같은 브라우저에서 같이 뽑는다)
#   ⚠ 반드시 부계로(자동화 감지 밴 리스크 = 본계 금지) · 이 파일은 git 밖 = 레포 커밋 0
#   ▶ 잘 들어오는지 폰에서 바로 확인:  bash scripts/insta_check.sh   (쿠키·쿨다운 상태 + 실제 1콜 진단 · 운영자 260731)
# 보안 가드(평의회 260723 #6) — env(쿠키·키 평문 집결)가 600 아니면 강제(termux -c / Mac -f 분기) · 전체 쿠키jar 유출 사고 재발 봉인
[ -f "$HOME/.nomute_phone_env" ] && { [ "$(stat -c %a "$HOME/.nomute_phone_env" 2>/dev/null || stat -f %A "$HOME/.nomute_phone_env" 2>/dev/null)" = 600 ] || chmod 600 "$HOME/.nomute_phone_env"; . "$HOME/.nomute_phone_env"; }
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
