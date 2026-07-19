#!/data/data/com.termux/files/usr/bin/sh
# media-handler 알림 래퍼 v5 (260719 · 실물 정본 — 원본 다운로더 = ~/bin/media-handler.real)
# v5: 게시자 = 표시명(닉네임) 확정(운영자) + 이모지·기호 자동 제거(유니코드 정제 · 통째 이모지 닉 = 시간 폴백 · 파이썬 불가 = 원문 유지)
# 설치(폰 한 줄): [ -f ~/bin/media-handler.real ] || mv ~/bin/media-handler ~/bin/media-handler.real; curl -fsSL https://raw.githubusercontent.com/muteno/nomute-editor/main/docs/media-notify.sh -o ~/bin/media-handler && chmod +x ~/bin/media-handler
# 동작: 다운로드 전후 갤러리 폴더 diff → 성공 = "다운로드 완료 · [게시자] 파일명"(v4 — 게시자 = yt-dlp uploader 조회 · 실패/이미지 전용 = [hh:mm AM/PM] 폴백) / 실패(새 파일 0) = "다운로드 실패 · [hh:mm AM/PM] 링크".
#       stdin을 닫아 원본의 'Enter로 종료' 대기도 소멸(Tasker 백그라운드 경로 안전).
# ── 알림 문구 칸(운영자 조정 — 타이틀은 이 두 변수만 고치면 됨 · 내용 문구는 아래 -c 줄) ──
T_OK="다운로드 완료"
T_FAIL="다운로드 실패"
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
  WHO=$(timeout 15 yt-dlp --no-warnings --print "%(uploader)s" "$1" 2>/dev/null | head -1)
  if CLEAN=$(printf '%s' "$WHO" | python3 -c 'import sys,unicodedata as u;s=sys.stdin.read();print("".join(ch for ch in s if not(u.category(ch) in ("So","Sk","Cs","Co") or 0x1F000<=ord(ch)<=0x1FAFF or 0x2600<=ord(ch)<=0x27BF or ord(ch) in (0xFE0F,0x200D,0x20E3))).strip())' 2>/dev/null); then
    WHO=$(printf '%s' "$CLEAN" | tr -s ' ')
  fi
  case "$WHO" in ""|" "|NA|null) PRE=$(TZ='Asia/Seoul' date '+[%I:%M %p]') ;; *) PRE="[$WHO]" ;; esac
  termux-notification --id mediadl -t "$T_OK" \
    -c "$PRE $M" 2>/dev/null || true
else
  termux-notification --id mediadl-fail -t "$T_FAIL" \
    -c "$(TZ='Asia/Seoul' date '+[%I:%M %p]') ${1:-링크 미상}" 2>/dev/null || true
fi
exit 0
