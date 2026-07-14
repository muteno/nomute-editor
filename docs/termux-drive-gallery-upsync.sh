#!/data/data/com.termux/files/usr/bin/sh
# ============================================================================
# drive-gallery-upsync.sh — 갤러리 → gdrive:Shared 역방향 자동 업로드
# drive-gallery-sync.sh(내려받기)의 쌍. 정본 문서 = docs/드라이브싱크_갤러리_폰파이프라인_v1.0.md §1-2
# 폰 설치 위치 = ~/.termux/tasker/drive-gallery-upsync.sh (Tasker가 3분+잠금해제마다 실행)
#
# 핵심 룰: "오고간 적 있는 파일은 패스"
#   · 풀러가 내려받은 것 = Pictures/DriveSync 제외 + ~/.drivesync.seen 이름 대조로 안 올림
#   · 드라이브에 같은 이름이 이미 있으면 안 올림(등록만)
#   · 업로드 성공분은 ~/.drivesync.seen 에 선등록 → 풀러가 도로 안 내려받음(루프 차단)
# 첫 실행 = 베이스라인: 현재 갤러리 전량을 '본 것'으로 등록만(업로드 0) → 이후 새 파일만 올라감.
# ============================================================================
REMOTE="gdrive:Shared"                    # 풀러와 같은 공간(내 드라이브/Shared)
UP_SUB="FromPhone"                        # 업로드 착지 하위 폴더(빈값 = Shared 루트)
SRC_DIRS="/sdcard/DCIM /sdcard/Pictures"  # 갤러리 스캔 대상(공백 구분)
EXCLUDES="/sdcard/Pictures/DriveSync"     # 풀러 착지점 = 재업로드 금지(공백 구분 복수 가능)
EXTS='jpg|jpeg|png|gif|webp|heic|heif|dng|mp4|mov|webm|mkv|3gp|m4v'
MAX_MB=0                                  # 0=무제한 · N=N MB 초과 파일 스킵(로그 남김)
WIFI_ONLY=0                               # 1=와이파이에서만 업로드(termux-api 필요)
UPSEEN="$HOME/.upsync.seen"               # 업로드축 원장(로컬 경로)
PULLSEEN="$HOME/.drivesync.seen"          # 풀러 원장(원격 경로) = 양방향 공용 열쇠
LOG="$HOME/.upsync.log"
STAMP="$HOME/.upsync.last"
LIST="$HOME/.upsync.scan"; NEWL="$HOME/.upsync.new"; RNOW="$HOME/.upsync.rnow"; TRAV="$HOME/.upsync.trav"
[ -f "$HOME/.upsync.conf" ] && . "$HOME/.upsync.conf"   # 값 덮어쓰기용(선택)

# 0) 120초 디바운스(풀러와 동일 관례) + 로그 로테이션
T=$(date +%s)
if [ -f "$STAMP" ] && [ $((T - $(cat "$STAMP"))) -lt 120 ]; then exit 0; fi
echo "$T" > "$STAMP"
[ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 2000 ] && { tail -n 1000 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"; }

# 1) 스캔(로컬만·네트워크 0): 대상 확장자, 숨김(.trashed-* 등 닷파일) 제외, EXCLUDES 제외
{ for d in $SRC_DIRS; do [ -d "$d" ] && find "$d" -type f -not -path '*/.*' 2>/dev/null; done; } \
  | grep -iE "\.($EXTS)\$" > "$LIST" || true
for ex in $EXCLUDES; do grep -vF "$ex/" "$LIST" > "$LIST.t"; mv "$LIST.t" "$LIST"; done

# 2) 첫 실행 베이스라인: 전량 등록만·업로드 0 (기존 사진첩 통째 업로드 폭탄 방지)
touch "$UPSEEN"
if [ ! -s "$UPSEEN" ]; then
  { echo "__init__"; cat "$LIST"; } > "$UPSEEN"
  echo "$(date '+%F %T') baseline: $(wc -l < "$LIST") files registered, no upload" >> "$LOG"
  exit 0
fi

# 3) 새 파일만 추출(풀러와 같은 awk diff — UPSEEN에 없는 로컬 경로)
awk 'FNR==NR{s[$0]=1;next} !($0 in s)' "$UPSEEN" "$LIST" > "$NEWL"
[ -s "$NEWL" ] || exit 0

# 4) 와이파이 게이트(옵션) — 원장 소비 전에 빠져나가야 나중에 다시 시도됨
if [ "$WIFI_ONLY" = "1" ] && command -v termux-wifi-connectioninfo >/dev/null 2>&1; then
  termux-wifi-connectioninfo 2>/dev/null | grep -q '"supplicant_state": *"COMPLETED"' \
    || { echo "$(date '+%F %T') skip: wifi only" >> "$LOG"; exit 0; }
fi

# 5) 원격 현황 1회 조회 → '오고간 이름' 집합 = 원격 목록 + 풀러 원장
rclone lsf -R --files-only "$REMOTE" > "$RNOW" 2>>"$LOG" || exit 1
touch "$PULLSEEN"
cat "$RNOW" "$PULLSEEN" > "$TRAV"

# 6) 새 파일 처리: 오고간 이름 = 패스(원장 등록만) / 아니면 업로드
while IFS= read -r f; do
  [ -f "$f" ] || { echo "$f" >> "$UPSEEN"; continue; }   # 스캔 후 삭제된 파일 = 등록만
  b=$(basename "$f")
  if [ -n "$UP_SUB" ]; then rpath="$UP_SUB/$b"; else rpath="$b"; fi
  # 오고간 적 있는 이름(원격 존재 or 풀러가 내려준 것) → 패스
  if grep -qxF "$b" "$TRAV" || grep -qF "/$b" "$TRAV"; then
    echo "$f" >> "$UPSEEN"
    grep -qxF "$rpath" "$PULLSEEN" || echo "$rpath" >> "$PULLSEEN"
    echo "$(date '+%F %T') PASS(traveled) $b" >> "$LOG"
    continue
  fi
  # 크기 상한(옵션)
  if [ "$MAX_MB" -gt 0 ]; then
    sz=$(wc -c < "$f" 2>/dev/null || echo 0)
    if [ "$sz" -gt $((MAX_MB*1048576)) ]; then
      echo "$(date '+%F %T') SKIP big(${sz}B) $f" >> "$LOG"; echo "$f" >> "$UPSEEN"; continue
    fi
  fi
  # 풀러 원장에 '선등록' → 업로드 완료 직후 풀러 lsf에 떠도 재다운 안 함(루프 차단)
  echo "$rpath" >> "$PULLSEEN"
  if rclone copyto "$f" "$REMOTE/$rpath" --inplace --log-file "$LOG" --log-level INFO; then
    echo "$f" >> "$UPSEEN"
    echo "$b" >> "$TRAV"                                  # 같은 런 내 동명 중복 차단
    echo "$(date '+%F %T') UP $b" >> "$LOG"
  else
    grep -vxF "$rpath" "$PULLSEEN" > "$PULLSEEN.t"; mv "$PULLSEEN.t" "$PULLSEEN"   # 선등록 롤백
    echo "$(date '+%F %T') FAIL $b (다음 런 재시도)" >> "$LOG"
  fi
done < "$NEWL"
