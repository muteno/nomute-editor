#!/data/data/com.termux/files/usr/bin/sh
# ============================================================================
# drive-clipboard-upsync.sh — 클립보드 텍스트 → gdrive:Shared/FromPhone/clips 자동 업로드
# 갤러리 업싱크(drive-gallery-upsync.sh)의 텍스트판. 정본 문서 = docs/드라이브싱크_갤러리_폰파이프라인_v1.0.md §1-3
# 폰 설치 위치 = ~/.termux/tasker/drive-clipboard-upsync.sh
#
# 입구 2개(하나의 스크립트가 둘 다 처리):
#   ① Tasker "클립보드 변경" 이벤트 → Tasker가 %CLIP을 STAGE 파일로 저장 → 이 스크립트 실행 (자동 · 정본)
#   ② 포그라운드 실행(Termux 위젯/수동) → STAGE가 비어 있으면 termux-clipboard-get으로 직접 읽음 (폴백)
#      ※ 안드로이드 10+에서 "백그라운드" 클립보드 읽기는 OS가 막는다 — 그래서 ①은 Tasker(READ_LOGS)로 읽고,
#        ②의 직접 읽기는 포그라운드에서만 정상. 백그라운드 호출 시 빈 값 = 조용히 통과(정상).
#
# 패스 룰: 같은 내용(md5) 재복사 = 패스 · 공백뿐 = 패스 · CLIP_MAX_KB 초과 = 패스(로그).
# 오프라인 = OUTBOX에 대기 → 다음 실행(클립 이벤트·DriveSync 3분/잠금해제 액션)에서 재시도.
# 업로드 직전 하행 원장(.drivesync.seen)에 선등록 → 풀러가 도로 안 내려받음(갤러리판과 동일 · 실패 시 롤백).
# ============================================================================
REMOTE="gdrive:Shared"                                # 풀러와 같은 공간
UP_SUB="FromPhone/clips"                              # 착지 하위 폴더
STAGE="/sdcard/Documents/nomute_clips/staging.txt"    # Tasker가 %CLIP을 써두는 곳
OUTBOX="$HOME/.clipsync.outbox"                       # 업로드 대기(오프라인 재시도)
SEEN="$HOME/.clipsync.seen"                           # 내용 md5 원장 = 같은 텍스트 재업로드 패스
PULLSEEN="$HOME/.drivesync.seen"                      # 풀러 원장(재다운 루프 차단)
LOG="$HOME/.clipsync.log"
CLIP_MAX_KB=512                                       # 초과 = 스킵(사고성 초대형 복사 방지)
[ -f "$HOME/.clipsync.conf" ] && . "$HOME/.clipsync.conf"   # 값 덮어쓰기용(선택)

mkdir -p "$OUTBOX" "$(dirname "$STAGE")"
touch "$SEEN" "$PULLSEEN"
[ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 1000 ] && { tail -n 500 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"; }
TMP="$HOME/.clipsync.tmp"; : > "$TMP"

# 1) 수집: STAGE(Tasker 이벤트 경로) 우선 → 소비 후 비움 / 없으면 클립보드 직접(포그라운드 한정 유효)
if [ -s "$STAGE" ]; then
  cat "$STAGE" > "$TMP"; : > "$STAGE"
elif command -v termux-clipboard-get >/dev/null 2>&1; then
  termux-clipboard-get > "$TMP" 2>>"$LOG" || : > "$TMP"
fi

# 2) 적재: 공백뿐/중복(md5)/과대 = 패스 · 새 내용 = OUTBOX에 clip_{시각}_{md5앞4}.txt 로 확정
if grep -q '[^[:space:]]' "$TMP" 2>/dev/null; then
  KB=$(( $(wc -c < "$TMP") / 1024 ))
  if [ "$KB" -gt "$CLIP_MAX_KB" ]; then
    echo "$(date '+%F %T') SKIP big(${KB}KB > ${CLIP_MAX_KB}KB)" >> "$LOG"
  else
    H=$(md5sum "$TMP" | cut -d' ' -f1); H4=$(echo "$H" | cut -c1-4)
    if grep -qxF "$H" "$SEEN"; then
      echo "$(date '+%F %T') PASS(dup) $H4" >> "$LOG"
    else
      N="clip_$(date +%Y%m%d_%H%M%S)_${H4}.txt"
      cp "$TMP" "$OUTBOX/$N"
      echo "$H" >> "$SEEN"
      echo "$(date '+%F %T') QUEUE $N" >> "$LOG"
    fi
  fi
fi
rm -f "$TMP"

# 3) 아웃박스 플러시: 성공 = 삭제 · 실패 = 남겨서 다음 실행에 재시도 (비어 있으면 네트워크 0)
for f in "$OUTBOX"/*.txt; do
  [ -f "$f" ] || continue
  b=$(basename "$f"); rpath="$UP_SUB/$b"
  grep -qxF "$rpath" "$PULLSEEN" || echo "$rpath" >> "$PULLSEEN"      # 선등록(재다운 루프 차단)
  if rclone copyto "$f" "$REMOTE/$rpath" --inplace --log-file "$LOG" --log-level ERROR; then
    rm -f "$f"
    echo "$(date '+%F %T') UP $b" >> "$LOG"
  else
    grep -vxF "$rpath" "$PULLSEEN" > "$PULLSEEN.t"; mv "$PULLSEEN.t" "$PULLSEEN"   # 선등록 롤백
    echo "$(date '+%F %T') FAIL $b (아웃박스 대기)" >> "$LOG"
  fi
done
