#!/data/data/com.termux/files/usr/bin/sh
# 드라이브 → 갤러리 다운싱크 (v1.3 · 정본 실물 — 문서 미러 = 드라이브싱크 플레이북 §1)
# 설치(폰 한 줄): curl -fsSL https://raw.githubusercontent.com/muteno/nomute-editor/main/docs/drive-gallery-sync.sh -o ~/.termux/tasker/drive-gallery-sync.sh && chmod +x ~/.termux/tasker/drive-gallery-sync.sh
REMOTE="gdrive:Shared"
LOCAL="/sdcard/Pictures/DriveSync"
SEEN="$HOME/.drivesync.seen"
NOW="$HOME/.drivesync.now"
NEW="$HOME/.drivesync.new"
LOG="$HOME/.drivesync.log"
STAMP="$HOME/.drivesync.last"
T=$(date +%s)
if [ -f "$STAMP" ] && [ $((T - $(cat "$STAMP"))) -lt 120 ]; then exit 0; fi
echo "$T" > "$STAMP"
mkdir -p "$LOCAL"; touch "$SEEN"
[ -s "$SEEN" ] || echo "__init__" > "$SEEN"
rclone lsf -R --files-only "$REMOTE" > "$NOW" 2>>"$LOG" || exit 1
awk 'FNR==NR{s[$0]=1;next} !($0 in s)' "$SEEN" "$NOW" > "$NEW"
if [ -s "$NEW" ]; then
  if rclone copy "$REMOTE" "$LOCAL" --files-from "$NEW" --inplace \
      --transfers 4 --log-file "$LOG" --log-level INFO; then
    cat "$NEW" >> "$SEEN"
  else
    DF=$(head -1 "$NEW"); DN=$(wc -l < "$NEW")
    DM="$DF"
    [ "$DN" -gt 1 ] && DM="$DF 외 $((DN-1))건"
    termux-notification --id drivesync-fail -t "드라이브싱크 실패 ⚠️" \
      -c "$(TZ='Asia/Seoul' date '+[%I:%M %p]') $DM" 2>/dev/null || true
  fi
  termux-media-scan -r "$LOCAL"
fi
[ -x "$HOME/.termux/tasker/drive-camera-up.sh" ] && sh "$HOME/.termux/tasker/drive-camera-up.sh"
exit 0
