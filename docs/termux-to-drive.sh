#!/data/data/com.termux/files/usr/bin/bash
# 노뮤트 — 폰 클립보드/캡쳐 → 공유드라이브 업로드 (드라이브싱크의 역방향 = 폰 → PC)
# 정본 문서 = docs/드라이브싱크_갤러리_폰파이프라인_v1.0.md §9
#
# 배경: 지금 폰은 rclone gdrive:Shared 를 '받기'만 한다(drive-gallery-sync.sh).
#       이 스크립트는 같은 리모트에 '올려서' PC(내 드라이브/Shared)가 받게 한다 = 반대 방향.
#
# ⚠️ 전제 1 — rclone 쓰기 권한: 드라이브싱크를 scope=drive.readonly 로 잡았으면 업로드가 막힌다.
#       한 번만  rclone config reconnect gdrive:  → 브라우저에서 scope 'drive'(전체)로 다시 동의.
# 전제 2 — Termux:API 설치:  pkg install rclone termux-api
#
# 설치(1회):
#   1) 이 파일을 ~/bin/to-drive 로 복사 → chmod +x ~/bin/to-drive
#   2-a) [클립보드]  Termux:Widget 바로가기:  ln -s ~/bin/to-drive ~/.shortcuts/클립보드→드라이브
#   2-b) [최근 캡쳐] Termux:Widget 바로가기:  printf '#!/data/data/com.termux/files/usr/bin/bash\n~/bin/to-drive shot\n' > ~/.shortcuts/최근캡쳐→드라이브 && chmod +x ~/.shortcuts/*
#   2-c) [공유시트]  텍스트/URL 공유 → Termux:  cp ~/bin/to-drive ~/bin/termux-url-opener  (공유분이 stdin 으로 들어옴)
# 사용:
#   to-drive            → 클립보드(텍스트)를 .txt 로 업로드
#   to-drive shot       → Screenshots 폴더의 '가장 최근' 캡쳐 1장 업로드
#   to-drive <파일경로> → 그 파일 업로드
#   echo "글" | to-drive→ stdin 내용을 .txt 로 업로드(공유시트 경로)

set -u
REMOTE="gdrive:Shared"                    # 드라이브싱크와 동일 리모트(내 드라이브/Shared)
STAMP="$(date +%y%m%d-%H%M%S)"
LOG="$HOME/.to-drive.log"
notify(){ termux-notification -t "$1" -c "$2" 2>/dev/null || true; }
logline(){ echo "$(date '+%y-%m-%d %H:%M:%S') | $1" >> "$LOG"; }

# 캡쳐가 쌓이는 후보 폴더(기기마다 조금 다름 — 존재하는 곳에서 최신 파일을 고름)
SHOTDIRS=(/sdcard/Pictures/Screenshots /sdcard/DCIM/Screenshots /sdcard/Pictures/Screenshot)

upload(){   # $1 = 올릴 로컬 파일
  local f="$1"
  [ -f "$f" ] || { notify "드라이브 업로드 실패" "파일 없음: $f"; logline "NO_FILE:$f"; return 1; }
  if rclone copy "$f" "$REMOTE" --no-traverse --log-file "$LOG" --log-level INFO; then
    notify "드라이브로 보냄 ✅" "$(basename "$f") → 내 드라이브/Shared"; logline "OK:$(basename "$f")"
  else
    notify "드라이브 업로드 실패 ⏳" "네트워크·권한(readonly?) 확인 — $(basename "$f")"; logline "FAIL:$(basename "$f")"; return 1
  fi
}

case "${1:-clip}" in
  shot)   # 최근 캡쳐 1장
    newest=""
    for d in "${SHOTDIRS[@]}"; do
      [ -d "$d" ] || continue
      c="$(ls -t "$d"/*.{png,jpg,jpeg} 2>/dev/null | head -1)"
      [ -n "$c" ] && { newest="$c"; break; }
    done
    [ -z "$newest" ] && { notify "드라이브 업로드 실패" "캡쳐 폴더에서 이미지 못 찾음"; logline "NO_SHOT"; exit 1; }
    upload "$newest" ;;
  clip)   # 클립보드(또는 공유시트 stdin) 텍스트
    if [ ! -t 0 ]; then CONTENT="$(cat)"; else CONTENT="$(termux-clipboard-get 2>/dev/null)"; fi
    [ -z "${CONTENT//[$' \t\r\n']/}" ] && { notify "드라이브 업로드 실패" "클립보드/입력이 비었음"; logline "EMPTY_CLIP"; exit 1; }
    TMP="$HOME/.to-drive-$STAMP.txt"; printf '%s\n' "$CONTENT" > "$TMP"
    upload "$TMP" && rm -f "$TMP" ;;
  *)      # 파일 경로 직접
    upload "$1" ;;
esac
