#!/usr/bin/env bash
# 폰 수집 크론 진단·복구 1발(운영자 260805 "폰에서 어떻게 확인하는지 명령어 주셈").
#
# 왜 따로 만드나 = wd-phone 경보가 뜨면 운영자가 확인해야 할 게 7곳으로 흩어져 있다
#   (crond 서비스 · crontab 등록 · 로그 · 산출 파일 나이 · Termux:API 웨이크락 · git 착지 · 실제 1회 실행).
#   각각을 손으로 치면 명령 6줄 + 결과 해석까지 운영자 몫 → [9] 「눌러서 되는 것」 위반.
#   이 파일 = 그 6축을 한 번에 재고, 마지막에 **수집을 실제로 1회 돌려 복구까지 끝낸다**.
#
# 쓰는 법(폰 Termux 또는 맥 · 한 줄):
#   cd ~/nomute-editor && git pull -q --rebase origin main && bash scripts/phone_check.sh
#
# 진단만 하고 수집은 안 돌리고 싶으면:  bash scripts/phone_check.sh --no-run
# 로그 위치 = ~/phone_subs.log (크론이 여기에 append · 이 스크립트도 실행분을 같이 남긴다)
# 끄는 법  = crontab -e 에서 phone_subs 줄 앞에 # 를 붙이면 크론 정지(되살리기 = # 제거)
set -u
cd "$(dirname "$0")/.."
RUN=1; [ "${1:-}" = "--no-run" ] && RUN=0
ok(){ printf '  ✅ %s\n' "$*"; }
no(){ printf '  ❌ %s\n' "$*"; }
hm(){ printf '  ⚠  %s\n' "$*"; }

echo "▶ 폰 수집 진단 — $(date '+%Y-%m-%d %H:%M:%S')"
echo
echo "① 산출 파일 나이(= 워치독이 보는 그 값 · 임계 90분)"
python3 - <<'PY'
import json, os, datetime
p = os.path.join('viewer', 'sns_subs_phone.json')
try:
    d = json.load(open(p, encoding='utf-8'))
    u = d.get('updated') or ''
    t = datetime.datetime.fromisoformat(u)
    age = (datetime.datetime.now(t.tzinfo) - t).total_seconds() / 60
    mark = '✅' if age <= 90 else '❌'
    print(f'  {mark} updated={u} · {int(age//60)}시간 {int(age%60)}분 전 (임계 90분)')
    for k in ('x', 'insta', 'threads', 'tiktok', 'reddit', 'disaster'):
        v = d.get(k)
        if isinstance(v, list):
            print(f'      {k}: {len(v)}건')
except FileNotFoundError:
    print('  ❌ viewer/sns_subs_phone.json 없음 — 폰이 아직 한 번도 수집 못 했다(첫 설치면 정상)')
except Exception as e:
    print(f'  ❌ 읽기 실패({type(e).__name__}: {e})')
PY

echo
echo "② crond 서비스(폰 Termux)"
if command -v sv >/dev/null 2>&1; then
  st="$(sv status crond 2>&1)"
  case "$st" in
    run:*) ok "$st" ;;
    *)     no "$st  → 되살리기:  sv-enable crond && sv up crond" ;;
  esac
else
  hm "sv 없음 = 맥이거나 termux-services 미설치. 맥은 cron이 상시라 정상 · 폰이면:  pkg install cronie termux-services && sv-enable crond"
fi

echo
echo "③ crontab 등록"
cl="$(crontab -l 2>/dev/null | grep -n 'phone_subs' || true)"
if [ -n "$cl" ]; then
  ok "등록됨 — $cl"
  case "$cl" in \#*|*$'\n'\#*) hm "줄 앞에 # 가 있으면 꺼진 상태다(crontab -e 로 # 제거)" ;; esac
else
  no "phone_subs 줄 없음 → crontab -e 후 아래 1줄 추가:"
  echo "        */30 * * * * bash ~/nomute-editor/scripts/phone_subs.sh >> ~/phone_subs.log 2>&1"
fi

echo
echo "④ 야간 정지 방지 3층(폰 전용 · 셋 다 있어야 새벽에 안 끊긴다)"
if command -v termux-wake-lock >/dev/null 2>&1; then
  ok "③층 termux-wake-lock CLI 있음"
  if command -v termux-battery-status >/dev/null 2>&1 && timeout 8 termux-battery-status >/dev/null 2>&1; then
    ok "①층 Termux:API 앱 응답함(웨이크락 실동작)"
  else
    no "①층 Termux:API 앱 무응답 — F-Droid에서 'Termux:API' **앱**을 깔아야 한다(pkg install termux-api 는 CLI만)"
  fi
  hm "②층 안드 설정 > 배터리 > Termux = '제한 없음' 은 화면에서 직접 확인(도즈가 앱을 죽이면 웨이크락으로 못 막는다)"
else
  hm "termux-wake-lock 없음 = 맥이면 해당 없음 · 폰이면:  pkg install termux-api"
fi

echo
echo "⑤ 최근 로그(~/phone_subs.log 마지막 15줄)"
if [ -f "$HOME/phone_subs.log" ]; then
  echo "      마지막 기록: $(date -r "$HOME/phone_subs.log" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || stat -f %Sm "$HOME/phone_subs.log" 2>/dev/null || echo '시각 불명')"
  tail -15 "$HOME/phone_subs.log" | sed 's/^/      /'
else
  hm "로그 파일 없음 — 크론이 한 번도 안 돌았거나 리다이렉트(>> ~/phone_subs.log)가 빠졌다"
fi

echo
echo "⑥ git 착지(= 걷은 걸 main에 올리는 축 · 260806 실사고 봉합)"
# ⚠ 신설 사유 — 260806 폰 실측: crond ✅(pid 생존) · 손으로 돌리니 수집도 ✅(insta 23·threads 18·tiktok 24)
#   인데 산출 파일은 **31시간 정지**였다. 즉 고장 지점이 크론도 수집도 아닌 **그 사이의 git 착지**인데,
#   ①~⑤ 어디에도 그 축이 없어서 진단서가 "크론 살아있음 + 수집 됨"만 보여주고 원인 자리를 비워 뒀다.
#   phone_subs.sh는 `set -e` + `git pull --rebase` 라 리베이스가 충돌로 중단되면 그 자리에 상태가 눌어붙고,
#   이후 매 회차가 같은 자리에서 죽는다(로그도 안 남는 조용한 정지) · push 인증 만료도 같은 증상을 낸다.
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  no "리베이스가 중단된 채 멈춰 있다 = 매 회차가 여기서 죽는다 → 풀기:  git rebase --abort"
elif [ -f .git/MERGE_HEAD ]; then
  no "머지가 중단된 채 멈춰 있다 → 풀기:  git merge --abort"
else
  ok "리베이스·머지 중단 없음"
fi
_un="$(git log --oneline origin/main..HEAD 2>/dev/null | wc -l | tr -d ' ')"
if [ "${_un:-0}" -gt 0 ]; then
  no "안 올라간 커밋 ${_un}개 = 걷어놓고 못 부친 상태 → 올리기:  git push origin HEAD:main"
  git log --oneline origin/main..HEAD 2>/dev/null | head -3 | sed 's/^/        /'
else
  ok "미푸시 커밋 0"
fi
if timeout 20 git ls-remote origin -h refs/heads/main >/dev/null 2>&1; then
  ok "원격 접속·인증 정상"
else
  no "원격 접속·인증 실패 = 토큰 만료·네트워크 → 확인:  git ls-remote origin"
fi

echo
if [ "$RUN" = "1" ]; then
  echo "⑦ 지금 1회 수집 실행(= 복구 · 성공하면 30분 안에 화면이 채워진다)"
  echo "   ↓ 아래 출력이 곧 원인 진단이다(쿠키 만료·429·네트워크 등)"
  bash scripts/phone_subs.sh 2>&1 | tee -a "$HOME/phone_subs.log" | sed 's/^/      /'
  echo "   실행 종료(rc=$?) — 다시 ① 을 보려면:  bash scripts/phone_check.sh --no-run"
else
  echo "⑦ 수집 실행 건너뜀(--no-run) — 돌리려면 인자 없이 다시:  bash scripts/phone_check.sh"
fi
echo
echo "▶ 끝 · 로그 = ~/phone_subs.log · 끄기 = crontab -e 에서 phone_subs 줄 앞에 #"
