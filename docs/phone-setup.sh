#!/data/data/com.termux/files/usr/bin/bash
# 노뮤트 뉴스 큐 — 폰 입구 원클릭 복구·설치 (멱등: 몇 번 돌려도 안전)
#
# 실행(폰 Termux 한 줄):
#   bash <(curl -fsSL https://raw.githubusercontent.com/muteno/nomute-editor/main/docs/phone-setup.sh)
#
# 무엇을 고치나:
#   ① allow-external-apps=true (Tasker가 Termux 실행하려면 필수 — 주석 처리 함정 제거)
#   ② queue-handler 최신 자가치유본 설치(git fetch+reset --hard → push, 로그파일)
#   ③ 모든 진입점(공유시트·Termux:Tasker·위젯/클립보드)을 핸들러로 일괄 연결
#   ④ git 연결 자가점검(센티넬 푸시 없이 — 큐 오염 방지)
# 이후 폰 GUI에서 한 번만 설정하면 끝(말미 안내).
set -u

say(){  printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok(){   printf '  \342\234\205 %s\n' "$1"; }
warn(){ printf '  \342\232\240\357\270\217  %s\n' "$1"; }

# ── 0) 리포 확인(없으면 클론) ──────────────────────────────
REPO="$HOME/nomute-editor"
if [ ! -d "$REPO/.git" ]; then
  warn "리포 없음 → 클론 시도(~/nomute-editor). 첫 push 때 Username=깃아이디 / Password=PAT."
  git clone -q https://github.com/muteno/nomute-editor "$REPO" \
    || { warn "클론 실패 — git 설치·네트워크·PAT 확인 후 재실행"; exit 1; }
fi
ok "리포: $REPO"

# ── 1) Termux 외부앱 허용(주석 함정 제거) ──────────────────
say "1) allow-external-apps"
mkdir -p "$HOME/.termux"
PROP="$HOME/.termux/termux.properties"; touch "$PROP"
sed -i '/allow-external-apps/d' "$PROP"          # 주석·중복 줄 싹 제거
echo "allow-external-apps = true" >> "$PROP"     # 주석 아닌 명시 1줄
termux-reload-settings 2>/dev/null || true
ok "allow-external-apps = true (주석 아님)"

# ── 2) 핸들러(자가치유 최신본) ─────────────────────────────
say "2) ~/bin/queue-handler"
mkdir -p "$HOME/bin"
cat > "$HOME/bin/queue-handler" << 'H'
#!/data/data/com.termux/files/usr/bin/bash
INPUT="$*"
[ -f "$INPUT" ] && INPUT="$(cat "$INPUT")"
URL=$(echo "$INPUT" | grep -oE 'https?://[^ "'"'"'<>]+' | head -1)
notify(){ termux-notification -t "$1" -c "$2" 2>/dev/null || true; }
log(){ echo "$(date '+%y-%m-%d %H:%M:%S') | $1 | $URL" >> ~/nomute-queue.log; }
if [ -z "$URL" ]; then notify "큐 실패" "URL 못 찾음"; log "NO_URL"; exit 1; fi
case "$URL" in
  *x.com*|*twitter.com*|*instagram.com*|*youtube.com*|*youtu.be*|*tiktok.com*)
    [ -x ~/bin/media-handler ] && exec ~/bin/media-handler "$URL" ;;
esac
cd ~/nomute-editor || { notify "큐 실패" "리포 폴더 없음"; log "NO_REPO"; exit 1; }
if ! git fetch -q origin main; then
  notify "큐 실패 ❌" "git fetch 실패 — 네트워크/PAT 확인"; log "FETCH_FAIL"; exit 1
fi
git reset -q --hard origin/main
mkdir -p pending
echo "$URL" > "pending/$(date +%y%m%d-%H%M%S)-$RANDOM.txt"
git add pending
git -c user.name=muteno-phone -c user.email=phone@nomute commit -qm "queue: $URL" \
  || { notify "큐 실패 ❌" "commit 실패(중복/빈 변경?)"; log "COMMIT_FAIL"; exit 1; }
if git push -q origin HEAD:main; then
  notify "큐 등록됨 ✅" "$URL"; log "OK"
else
  notify "큐 등록 실패 ❌" "Termux 열어 git push 확인"; log "PUSH_FAIL"
fi
H
chmod +x "$HOME/bin/queue-handler"
ok "queue-handler 설치(자가치유본)"

# ── 3) 진입점 일괄 연결 → 핸들러 ───────────────────────────
say "3) 진입점 연결"
# 3a) Termux 공유시트(URL/텍스트 파일)
for f in termux-url-opener termux-file-editor; do
  printf '#!/data/data/com.termux/files/usr/bin/bash\nexec ~/bin/queue-handler "$*"\n' > "$HOME/bin/$f"
  chmod +x "$HOME/bin/$f"
done
ok "공유시트: ~/bin/termux-url-opener · termux-file-editor"
# 3b) Termux:Tasker 플러그인(Tasker가 부르는 자리)
mkdir -p "$HOME/.termux/tasker"
printf '#!/data/data/com.termux/files/usr/bin/bash\n~/bin/queue-handler "$*"\n' > "$HOME/.termux/tasker/queue-from-tasker"
chmod +x "$HOME/.termux/tasker/queue-from-tasker"
ok "Tasker: ~/.termux/tasker/queue-from-tasker"
# 3c) 위젯/클립보드
mkdir -p "$HOME/.shortcuts"
printf '#!/data/data/com.termux/files/usr/bin/bash\n~/bin/queue-handler "$(termux-clipboard-get)"\n' > "$HOME/.shortcuts/큐등록"
chmod +x "$HOME/.shortcuts/큐등록"
ok "위젯/클립보드: ~/.shortcuts/큐등록"

# ── 4) git 연결 자가점검(큐 오염 없이) ─────────────────────
say "4) git 연결 점검"
cd "$REPO"
if git fetch -q origin main; then
  ok "git fetch OK — 인증·네트워크 정상(=손으로 공유하면 push까지 됨)"
else
  warn "git fetch 실패 — PAT 만료/네트워크 의심. 'cd ~/nomute-editor && git fetch origin main' 수동 확인"
fi

# ── 5) 남은 1회 GUI 설정 안내 ──────────────────────────────
say "끝! 폰 GUI에서 둘 중 '하나만' 골라 1회 설정"
cat <<'GUIDE'
  [권장·간단] 공유시트로 Termux 직접 쓰기 (Tasker 불필요):
    기사 → 공유 → 목록에서 "Termux" 선택.
    "Termux"가 안 보이면 Termux:Widget/Tasker 앱이 설치돼 있나 확인(플레이북 §2).

  [Tasker 쓸 경우] Tasker 앱에서:
    프로파일 = 공유 인텐트(ACTION_SEND) 캐치 → 공유 텍스트를 변수(예: %share)로.
    태스크 액션 = 플러그인 ▸ Termux:Tasker
        · Executable = queue-from-tasker   (디렉토리 칸 비움)
        · Arguments  = %share  (또는 잡은 URL 변수)
        · "Terminal session" 체크 해제
    ※ 자주 막히는 곳: 위 ① allow-external-apps. 이 스크립트가 이미 켰음.

  확인: 기사 공유 → 폰 알림 ✅/❌, 또는 Termux에서
        tail -1 ~/nomute-queue.log
  (네이트는 이제 분석단에서 자동 디코딩되니 원문/네이트 아무거나 OK.)
GUIDE
