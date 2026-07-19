#!/data/data/com.termux/files/usr/bin/sh
# media-handler 알림 래퍼 (260719 신설 · 실물 정본 — 원본 다운로더 = ~/bin/media-handler.real)
# 설치(폰 한 줄): [ -f ~/bin/media-handler.real ] || mv ~/bin/media-handler ~/bin/media-handler.real; curl -fsSL https://raw.githubusercontent.com/muteno/nomute-editor/main/docs/media-notify.sh -o ~/bin/media-handler && chmod +x ~/bin/media-handler
# 동작: 다운로드 전후 갤러리 폴더 diff → 새 파일 있으면 "다운로드 완료 · 파일명" 알림(운영자 260719 스펙 — 완료만).
#       stdin을 닫아 원본의 'Enter로 종료' 대기도 소멸(Tasker 백그라운드 경로 안전).
D="$HOME/storage/dcim/nomute_image"
B="$HOME/.mediadl.before"
ls "$D" 2>/dev/null > "$B"
"$HOME/bin/media-handler.real" "$@" </dev/null
NEWLIST=$(ls "$D" 2>/dev/null | grep -vxF -f "$B" 2>/dev/null)
C=$(printf '%s' "$NEWLIST" | grep -c .)
if [ "${C:-0}" -gt 0 ]; then
  F=$(printf '%s\n' "$NEWLIST" | head -1)
  M="$F"
  [ "$C" -gt 1 ] && M="$F 외 $((C-1))건"
  termux-notification --id mediadl -t "다운로드 완료" -c "$M" 2>/dev/null || true
fi
exit 0
