#!/usr/bin/env bash
# 폰 수집 크론 자가부활 설치 1발(운영자 260805 "폰 안죽게하려면 어떻게 해야해").
#
# ▷ 왜 = 감지는 이미 다 돼 있는데 **복구만 사람 손**이었다.
#   실측(260805): 폰 정지 22시간 44분. 그동안 watchdog은 제 일을 다 했다 —
#   임계 90분에 감지(WD_PHONE_MIN) → `push_send`로 기기 푸시까지 발사(쿨다운 6h = 3~4회 도착)
#   → 뷰어 메시지함 wd-phone 점등. **알림을 더 세게 만드는 건 답이 아니다**(이미 갔다).
#   진짜 공백은 「그 알림을 본 사람이 폰을 열어 termux를 손으로 되살리기 전까지 아무 일도 안 일어난다」는 것.
#   → 이 파일은 감지를 늘리지 않는다. **사람 손 없이 되살아나는 두 층**만 깐다.
#
# ▷ 두 층(안드로이드 축 — 셸 스크립트로는 못 막는 자리들)
#   ① 재부팅 복구 = Termux:Boot 훅. crond는 안드로이드 재부팅에서 **자동으로 안 돌아온다** →
#      OS 업데이트·배터리 방전·강제 재시작 한 번이면 그날부터 영구 정지(사람이 열기 전까지).
#      대책 = ~/.termux/boot/ 훅이 부팅 직후 wake-lock + crond를 다시 세운다.
#   ② 도즈 복구 = termux-job-scheduler 감시자. 안드 도즈가 crond를 재우면 crond 자신은
#      스스로 못 깨어난다(자기 부활을 자기 cron에 넣는 건 논리적으로 불가). JobScheduler는
#      **OS가 깨우는 축**이라 도즈 안에서도 산다 → 주기적으로 crond 생존만 확인해 죽었으면 되살린다.
#
# ⚠ 감시자는 **수집을 직접 돌리지 않는다**(crond 재시작만) — `scripts/phone_subs.sh`에 동시실행 보호가
#   없어서(실측: flock·락파일 0) 감시자와 크론이 겹쳐 쏘면 같은 레포에서 git index.lock·rebase가 충돌한다.
#   생존 확인·재시작만 = 겹칠 일 자체가 0. 수집 주기는 종전 crontab(*/30) 그대로 = 동작 변경 0.
#
# ▷ 쓰는 법(폰 Termux에서 한 줄 · 1회면 끝):
#     cd ~/nomute-editor && git pull -q --rebase origin main && bash scripts/phone_guard.sh
#
# ▷ 끄는 법:  bash scripts/phone_guard.sh --off   (부팅 훅 삭제 + 감시자 등록 해제 · 크론은 무접촉)
# ▷ 로그   :  ~/phone_guard.log (감시자가 여기에 append · 크론 로그 ~/phone_subs.log 와 별도)
# ▷ 상태만 보기: bash scripts/phone_guard.sh --status
#
# ⚠ 이게 못 막는 것(정직) = 폰 전원 off · 기내모드·회선 사망 · Termux 앱을 사용자가 직접 강제종료.
#   그 세 가지는 OS 위의 어떤 스크립트로도 못 되살린다 → 그때는 종전대로 watchdog 푸시가 사람을 부른다.
#   그리고 아래 ①②는 **Termux:Boot / Termux:API 앱이 깔려 있어야** 동작한다(CLI 패키지만으론 무동작 ·
#   미설치면 이 스크립트가 그 자리에서 설치 안내를 띄우고 나머지 층만 깐다 = fail-soft).
set -u
cd "$(dirname "$0")/.."
REPO="$(pwd)"
LOG="$HOME/phone_guard.log"
BOOTDIR="$HOME/.termux/boot"
BOOTHOOK="$BOOTDIR/nomute-boot.sh"
WATCHER="$HOME/.nomute_phone_watch.sh"
JOB_ID=7311                       # 고정 id = 재실행해도 중복 등록 0(같은 id면 OS가 덮어쓴다)
JOB_MIN="${NOMUTE_GUARD_MIN:-15}" # 감시 주기(분) — 크론 30분의 절반 = 한 주기 놓치기 전에 되살린다

ok(){ printf '  ✅ %s\n' "$*"; }
no(){ printf '  ❌ %s\n' "$*"; }
hm(){ printf '  ⚠  %s\n' "$*"; }
has(){ command -v "$1" >/dev/null 2>&1; }

# ── crond 생존 판정 = 프로세스 실존(termux-services sv 유무와 무관하게 성립하는 유일한 축) ──
crond_alive(){ pgrep -x crond >/dev/null 2>&1 || pgrep -f 'bin/crond' >/dev/null 2>&1; }

crond_start(){
  has sv-enable && sv-enable crond >/dev/null 2>&1 || true
  has sv && sv up crond >/dev/null 2>&1 || true
  crond_alive || { has crond && crond >/dev/null 2>&1 || true; }   # 서비스 관리자 없는 환경 폴백
  crond_alive
}

# ── --off ─────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--off" ]; then
  echo "▶ 자가부활 해제(크론 자체는 안 건드림 — 수집은 종전대로 계속 돈다)"
  rm -f "$BOOTHOOK" && ok "부팅 훅 삭제: $BOOTHOOK" || hm "부팅 훅 없음"
  if has termux-job-scheduler; then
    termux-job-scheduler --cancel --job-id "$JOB_ID" >/dev/null 2>&1 && ok "감시자 등록 해제(job $JOB_ID)" || hm "감시자 등록 없음"
  fi
  rm -f "$WATCHER" 2>/dev/null || true
  echo; echo "해제 완료. 되살리기 = bash scripts/phone_guard.sh"
  exit 0
fi

# ── --status ──────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--status" ]; then
  echo "▶ 자가부활 상태 — $(date '+%Y-%m-%d %H:%M:%S')"
  crond_alive && ok "crond 살아있음" || no "crond 죽어있음 (되살리기 = bash scripts/phone_guard.sh)"
  [ -f "$BOOTHOOK" ] && ok "① 재부팅 복구 훅 설치됨" || no "① 재부팅 복구 훅 없음"
  if has termux-job-scheduler; then
    if termux-job-scheduler --pending 2>/dev/null | grep -q "$JOB_ID"; then ok "② 도즈 감시자 등록됨(job $JOB_ID · ${JOB_MIN}분)"; else no "② 도즈 감시자 미등록"; fi
  else
    hm "② termux-job-scheduler 없음 = Termux:API 앱 미설치(F-Droid)"
  fi
  [ -f "$LOG" ] && { echo; echo "  최근 감시 로그 3줄:"; tail -3 "$LOG" | sed 's/^/    /'; }
  exit 0
fi

echo "▶ 폰 수집 자가부활 설치 — $(date '+%Y-%m-%d %H:%M:%S')"
echo "  레포: $REPO"
echo

# ── 0. 지금 당장 크론부터 살린다(설치 전에 현 상태 복구 = 이 실행 1회가 곧 복구) ───────────
echo "0) 지금 crond 상태"
if crond_alive; then ok "이미 살아있음"
else
  hm "죽어있음 → 되살리는 중…"
  crond_start && ok "crond 기동됨" || no "crond 기동 실패 — 'pkg install cronie termux-services' 후 다시 실행해 줘"
fi
has termux-wake-lock && { termux-wake-lock >/dev/null 2>&1 && ok "웨이크락 획득" || hm "웨이크락 실패(Termux:API 앱 미설치?)"; } \
  || hm "termux-wake-lock 없음 = 'pkg install termux-api' + F-Droid Termux:API 앱 필요"
echo

# ── 감시자 본체(두 층이 공유) ─────────────────────────────────────────────────
cat > "$WATCHER" <<WEOF
#!/usr/bin/env bash
# nomute 폰 크론 감시자 — 자동 생성물(수정은 scripts/phone_guard.sh 쪽에서). 하는 일 = crond 생존 확인·재기동뿐.
# ⚠ 수집(phone_subs.sh)은 절대 직접 안 돌린다 — 크론과 겹쳐 쏘면 같은 레포에서 git이 충돌한다.
set -u
LOG="\$HOME/phone_guard.log"
alive(){ pgrep -x crond >/dev/null 2>&1 || pgrep -f 'bin/crond' >/dev/null 2>&1; }
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock >/dev/null 2>&1 || true
if alive; then
  echo "\$(date '+%F %T') ok crond 생존" >> "\$LOG"
else
  command -v sv-enable >/dev/null 2>&1 && sv-enable crond >/dev/null 2>&1 || true
  command -v sv >/dev/null 2>&1 && sv up crond >/dev/null 2>&1 || true
  alive || { command -v crond >/dev/null 2>&1 && crond >/dev/null 2>&1 || true; }
  if alive; then echo "\$(date '+%F %T') REVIVED crond 재기동 성공" >> "\$LOG"
  else echo "\$(date '+%F %T') FAIL crond 재기동 실패" >> "\$LOG"; fi
fi
# 로그 무한증식 차단 = 최근 500줄만 유지
[ -f "\$LOG" ] && tail -500 "\$LOG" > "\$LOG.tmp" 2>/dev/null && mv "\$LOG.tmp" "\$LOG" || true
WEOF
chmod 700 "$WATCHER"
ok "감시자 설치: $WATCHER"
echo

# ── ① 재부팅 복구(Termux:Boot) ────────────────────────────────────────────────
echo "1) 재부팅 복구 훅"
mkdir -p "$BOOTDIR"
cat > "$BOOTHOOK" <<BEOF
#!/usr/bin/env bash
# nomute — 부팅 직후 폰 수집 크론 복구(자동 생성물 · 정본 = scripts/phone_guard.sh)
# 이게 없으면 재부팅 한 번에 crond가 영영 안 돌아온다(안드로이드는 crond를 자동 복구하지 않는다).
sleep 20                                   # 부팅 직후 스토리지·네트워크 준비 대기
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock >/dev/null 2>&1 || true
bash "$WATCHER" || true
BEOF
chmod 700 "$BOOTHOOK"
ok "설치: $BOOTHOOK"
if [ -d "$HOME/.termux/boot" ]; then
  hm "⚠ Termux:Boot **앱**이 깔려 있어야 이 훅이 실행된다(F-Droid에서 'Termux:Boot' 설치 후 한 번 열어주기)"
fi
echo

# ── ② 도즈 복구(termux-job-scheduler) ────────────────────────────────────────
echo "2) 도즈 감시자(OS가 깨우는 축)"
if has termux-job-scheduler; then
  if termux-job-scheduler --script "$WATCHER" --job-id "$JOB_ID" \
       --period-ms $((JOB_MIN * 60000)) --persisted true --network any >/dev/null 2>&1; then
    ok "등록됨 — ${JOB_MIN}분마다 crond 생존 확인(재부팅 후에도 유지 = --persisted)"
  else
    no "등록 실패 — Termux:API 앱(F-Droid)이 깔려 있는지 확인해 줘"
  fi
else
  no "termux-job-scheduler 없음 → 'pkg install termux-api' + F-Droid에서 Termux:API 앱 설치 후 이 스크립트 재실행"
fi
echo

# ── 검증 ──────────────────────────────────────────────────────────────────────
echo "3) 검증"
bash "$WATCHER" && ok "감시자 1회 실행 정상(로그: $LOG)" || no "감시자 실행 실패"
crond_alive && ok "crond 살아있음" || no "crond 죽어있음"
if crontab -l 2>/dev/null | grep -q phone_subs; then ok "crontab에 phone_subs 등록됨"
else no "crontab에 phone_subs 없음 → crontab -e 에 다음 한 줄:
     */30 * * * * bash $REPO/scripts/phone_subs.sh >> \$HOME/phone_subs.log 2>&1"; fi
echo
echo "설치 끝. 상태 확인 = bash scripts/phone_guard.sh --status · 끄기 = --off"
echo "수집이 실제로 도는지(산출 나이·계정별 결과) = bash scripts/phone_check.sh"
