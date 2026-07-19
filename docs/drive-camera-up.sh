#!/data/data/com.termux/files/usr/bin/sh
# 갤러리 → 드라이브 역방향 업로드 (v1.2.5 · 정본 실물 — 문서 미러 = 드라이브싱크 플레이북 §1-b)
# 설치(폰 한 줄): curl -fsSL https://raw.githubusercontent.com/muteno/nomute-editor/main/docs/drive-camera-up.sh -o ~/.termux/tasker/drive-camera-up.sh && chmod +x ~/.termux/tasker/drive-camera-up.sh
# ── 알림 문구 칸(운영자 조정 — 타이틀은 이 두 변수 · 내용 문구는 아래 -c 줄) ──
T_BASE="갤러리 업로드 기준선 설정 ✅"
T_UPFAIL="업로드 실패"
REMOTE_BASE="gdrive:Shared"
SRCS="/sdcard/DCIM/Camera /sdcard/DCIM/Screenshots /sdcard/Pictures/Screenshots"
WIFI_ONLY=0
UPSEEN="$HOME/.driveup.seen"
DSEEN="$HOME/.drivesync.seen"
UNOW="$HOME/.driveup.now"
UNEW="$HOME/.driveup.new"
LOG="$HOME/.driveup.log"
STAMP="$HOME/.driveup.last"
LOCK="$HOME/.driveup.lock"
T=$(date +%s)
if [ -f "$STAMP" ] && [ $((T - $(cat "$STAMP"))) -lt 120 ]; then exit 0; fi
echo "$T" > "$STAMP"
if ! mkdir "$LOCK" 2>/dev/null; then
  A=$((T - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0)))
  [ "$A" -lt 7200 ] && exit 0
  rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" 2>/dev/null || exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
: > "$UNOW"
for SRC in $SRCS; do
  [ -d "$SRC" ] || continue
  ls "$SRC" | while IFS= read -r f; do
    [ -f "$SRC/$f" ] && printf '%s\n' "$SRC/$f"
  done >> "$UNOW"
done
[ -s "$UNOW" ] || exit 0
if [ ! -s "$UPSEEN" ]; then
  cp "$UNOW" "$UPSEEN"
  termux-notification --id driveup -t "$T_BASE" \
    -c "지금부터 새로 생기는 사진·영상만 드라이브로 올라감" 2>/dev/null || true
  exit 0
fi
awk 'FNR==NR{s[$0]=1;next} !($0 in s)' "$UPSEEN" "$UNOW" > "$UNEW"
[ -s "$UNEW" ] || exit 0
if [ "$WIFI_ONLY" = 1 ]; then
  termux-wifi-connectioninfo 2>/dev/null | grep -q '"supplicant_state": "COMPLETED"' || exit 0
fi
FAIL=0
FAILN=0
FAILF=""
for SRC in $SRCS; do
  [ -d "$SRC" ] || continue
  grep "^$SRC/" "$UNEW" | sed "s|^$SRC/||" > "$UNEW.d"
  [ -s "$UNEW.d" ] || continue
  cat "$UNEW.d" >> "$DSEEN"
  if rclone copy "$SRC" "$REMOTE_BASE" --files-from "$UNEW.d" --inplace \
      --transfers 2 --log-file "$LOG" --log-level INFO; then
    sed "s|^|$SRC/|" "$UNEW.d" >> "$UPSEEN"
  else
    FAIL=1
    FAILN=$((FAILN + $(wc -l < "$UNEW.d")))
    [ -z "$FAILF" ] && FAILF=$(head -1 "$UNEW.d")
  fi
done
if [ "$FAIL" = 1 ]; then
  FM="$FAILF"
  [ "$FAILN" -gt 1 ] && FM="$FAILF 외 $((FAILN-1))건"
  termux-notification --id driveup-fail -t "$T_UPFAIL" \
    -c "$(TZ='Asia/Seoul' date '+[%H-%M]') $FM — 다음 실행 때 자동 재시도" 2>/dev/null || true
fi
exit 0
