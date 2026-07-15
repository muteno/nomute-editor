#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# 역방향 동기화 — 폰 갤러리 사진 + 클립보드 → GDRIVE 공유폴더
#   내려받기(GDRIVE→폰)의 "짝". rclone copy 라서:
#     · 이미 올린 사진 = 자동 스킵(중복 안 쌓임)
#     · 폰에서 사진 지워도 드라이브 원본은 유지(삭제 전파 안 함 = 안전)
#     · 클립보드는 "직전과 다를 때만" 시각 파일명으로 올림(3분마다 같은 내용 재업로드 방지)
#
#   설치:  cp ~/nomute-editor/sync/gdrive-up.sh ~/bin/gdrive-up && chmod +x ~/bin/gdrive-up
#   실행:  ~/bin/gdrive-up      (기존 '내려받기' Tasker 트리거에 이 줄만 추가)
#   로그:  tail ~/gdrive-up.log
# ─────────────────────────────────────────────────────────────────────────
export TZ='Asia/Seoul'                 # 폰·러너 무관 KST 강제 (CLAUDE.md [12])

# ── 채울 값 3개 (딱 한 번, nano ~/bin/gdrive-up 로 수정) ───────────────────
REMOTE="gdrive"                        # rclone listremotes 결과에서 콜론(:) 뺀 이름
GDRIVE_DIR="__여기_채워__"             # 내려받기가 바라보는 그 GDRIVE 폴더와 '똑같이'
# 올릴 갤러리 폴더들 — 캡처·카메라 등 여러 개 OK. 여기 담긴 게 폰↔PC '공용 창고'가 됨.
PHONE_DIRS=(
  "/storage/emulated/0/DCIM/Screenshots"   # 캡처(스크린샷)
  "/storage/emulated/0/DCIM/Camera"        # 카메라 사진
)
# ─────────────────────────────────────────────────────────────────────────

MODE="${1:-all}"                       # all=사진+클립(3분 트리거) · clip=클립만 즉시(홈 위젯 탭)
CLIP_STATE="$HOME/.gdrive_clip_last"   # 직전 클립보드 기억(중복 업로드 차단)
LOG="$HOME/gdrive-up.log"

notify(){ termux-notification -t "$1" -c "$2" 2>/dev/null || true; }
log(){ echo "$(date '+%y-%m-%d %H:%M:%S') | $1" >> "$LOG"; }

# 값 미기입 방어 — 플레이스홀더 남아 있으면 실행 거부(엉뚱한 곳에 안 꽂히게)
case "$GDRIVE_DIR" in
  *__여기_채워__*) notify "설정 미완료 ⚙️" "gdrive-up 상단 REMOTE·GDRIVE_DIR 채워"; log "SETUP_INCOMPLETE"; exit 1;;
esac
command -v rclone >/dev/null 2>&1 || { notify "업로드 실패 ❌" "rclone 없음"; log "NO_RCLONE"; exit 1; }

# 1) 갤러리(사진·캡처): 여러 폴더 → GDRIVE (copy = 이미 있으면 스킵 · 삭제 전파 안 함) — clip 모드면 건너뜀
if [ "$MODE" != "clip" ]; then
  for d in "${PHONE_DIRS[@]}"; do
    [ -d "$d" ] || { log "SKIP_NODIR $d"; continue; }
    if rclone copy "$d" "$REMOTE:$GDRIVE_DIR" \
          --exclude "clip_*.txt" \
          --transfers 4 --checkers 8 --min-age 10s \
          --log-file "$LOG" --log-level INFO; then
      log "PHOTO_OK $d"
    else
      notify "사진 업로드 실패 ❌" "tail ~/gdrive-up.log"; log "PHOTO_FAIL $d"
    fi
  done
fi

# 2) 클립보드: 텍스트가 있고 & 직전과 다를 때만 파일로 올림 (텍스트 전용 — 이미지 복사는 미지원)
CLIP="$(termux-clipboard-get 2>/dev/null)"
if [ -n "$CLIP" ] && [ "$CLIP" != "$(cat "$CLIP_STATE" 2>/dev/null)" ]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  TMP="$HOME/clip_$TS.txt"
  printf '%s\n' "$CLIP" > "$TMP"
  if rclone copy "$TMP" "$REMOTE:$GDRIVE_DIR" --log-file "$LOG" --log-level INFO; then
    printf '%s' "$CLIP" > "$CLIP_STATE"
    notify "클립보드 올림 ✅" "clip_$TS.txt"; log "CLIP_OK clip_$TS.txt"
  else
    notify "클립보드 업로드 실패 ❌" "tail ~/gdrive-up.log"; log "CLIP_FAIL"
  fi
  rm -f "$TMP"
fi
