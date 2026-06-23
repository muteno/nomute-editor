#!/data/data/com.termux/files/usr/bin/bash
# 노뮤트 뉴스 큐 — Termux 공유 스크립트 (참고용 · 실전판은 폰재구축플레이북 §5)
# 설치:
#   1) Termux + Termux:API 설치, `pkg install git termux-api`
#      (전문 붙여넣기 경로는 추가 패키지 0개. URL 공유→폰 선-fetch 를 쓰려면 `python libiconv` 추가)
#   2) git clone <레포> ~/nomute-editor (또는 이미 있으면 생략)
#   3) 이 파일을 ~/bin/queue-news 로 복사하고 chmod +x
#   4) Termux:Tasker/공유 시트에 "queue-news"를 등록(공유 → Termux)
# 사용: 폰에서 기사 '공유 → Termux(queue-news)' → URL이 pending/ 에 push됨
# 로그: 매 시도가 ~/nomute-queue.log 에 남는다(알람 꺼도 성공/실패 확인 가능).
#
# ⚠️ 증거보존(260620 분신술 ⓐ①): 공유분은 *먼저* 레포 밖 ~/nomute-pending-failed/ 에 저장한 뒤 push 한다.
#    push 가 5회 실패해도 그 백업은 git reset --hard 에 *증발하지 않고* 남아, 다음 공유 때 자동 재시도로 합류한다.
#    (옛 버전은 실패 시 미푸시 로컬커밋만 남았다가 다음 공유의 reset 에 통째 사라지는 silent-drop 이 있었음.)

INPUT="$*"               # 공유된 전체(URL 또는 기사 '전체선택→공유' 전문)
notify(){ termux-notification -t "$1" -c "$2" 2>/dev/null || true; }
URL="$(printf '%s' "$INPUT" | grep -oE 'https?://[^ "'"'"'<>]+' | head -1)"
# 한글 음절(가-힣)의 UTF-8 lead 바이트(0xEA~0xED) 수 ≈ 글자수 — LC_ALL=C 라 로케일 무관(폰 바이트모드여도 일관).
HANGUL=$(printf '%s' "$INPUT" | LC_ALL=C grep -oE $'[\xea-\xed]' | wc -l)   # 200자+ = 전문 붙여넣기 판정
logline(){ echo "$(date '+%y-%m-%d %H:%M:%S') | $1 | ${LINE1:-$URL}" >> ~/nomute-queue.log; }

cd ~/nomute-editor || { notify "큐 실패" "리포 폴더 없음"; logline "NO_REPO"; exit 1; }

FAILDIR="$HOME/nomute-pending-failed"   # 레포 밖 = git reset --hard 면역(미전송분 보존·다음 공유 때 자동 재시도)
mkdir -p "$FAILDIR"

# 백업파일 1건을 최신 origin/main 위에 올려 5회 백오프 push. 0=성공 / 1=네트워크·push 실패 / 2=commit 실패.
push_file(){   # $1=백업파일 · $2=최대시도(기본5) → 0=성공 / 1=네트워크·push / 2=commit
  local src="$1" maxtry="${2:-5}" name; name="$(basename "$src")"
  local try
  for try in $(seq 1 "$maxtry"); do
    git fetch -q origin main || return 1
    git reset -q --hard origin/main          # 최신 원격에 맞춤(레포 안만 영향 — FAILDIR 백업은 무사)
    mkdir -p pending
    cp "$src" "pending/$name"
    git add pending
    git diff --cached --quiet && return 0     # 이미 main에 동일내용(부분성공) = 반영됨 → 성공처리(rc2 무한 DEFERRED 차단·분신술1·10)
    git -c user.name=muteno-phone -c user.email=phone@nomute commit -qm "queue: $(head -n1 "$src")" 2>/dev/null || return 2
    if git push -q origin HEAD:main; then return 0; fi
    [ "$try" = "$maxtry" ] || sleep $((try * 2))   # 마지막 시도 뒤엔 sleep 생략(off-by-one·분신술2)
  done
  return 1
}

# ── 본문 준비(URL 선-fetch / 전문 붙여넣기) ──
if [ "$HANGUL" -ge 200 ]; then
  # 전문 붙여넣기(전체선택→공유) — 403·JS·페이월 *전부* 우회, fetch 안 함. 안의 링크는 무시.
  LINE1="paste:$(printf '%s' "$INPUT" | sha1sum | cut -c1-12)"   # 합성 id(원문 URL 없음·dedup용)
  BODY="$(printf '%s' "$INPUT" | head -c 20000)"   # iconv 불필요 — 분석기가 iconv -c 로 정리
else
  # URL 경로 — 폰 선-fetch(403 우회). repo의 fetch_article.sh로 폰(200)에서 본문 선취득.
  [ -z "$URL" ] && { notify "큐 실패" "URL/전문 못 찾음"; logline "NO_URL"; exit 1; }
  LINE1="$URL"
  git fetch -q origin main && git reset -q --hard origin/main   # fetch_article.sh 최신화(아직 백업 전 = 잃을 것 없음)
  BODY="$(timeout 20 bash .github/scripts/fetch_article.sh "$URL" 2>/dev/null || true)"
fi

# ── 새 공유분을 *먼저* 백업파일로 저장(레포 밖 = 절대 안 잃음) ──
NEWF="$FAILDIR/$(date +%y%m%d-%H%M%S)-$RANDOM.txt"
if [ -n "${BODY//[$' \t\r\n']/}" ]; then
  printf '%s\n# body:\n%s\n' "$LINE1" "$BODY" > "$NEWF"
else
  echo "$LINE1" > "$NEWF"                # 본문 없음(JS렌더·페이월) → line1만(클라우드 폴백)
fi

# ── 백업디렉터리 전체(이전 미전송분 + 방금 것)를 오래된 순으로 push → 성공분만 삭제 ──
shopt -s nullglob
new_ok=0; left=0
for src in "$FAILDIR"/*.txt; do            # glob = 파일명 사전순(YYMMDD 접두) = 오래된 순(FIFO)
  if [ "$src" = "$NEWF" ]; then push_file "$src" 5; else push_file "$src" 1; fi   # 방금 것=풀재시도 / 백로그=1회(전경 행 방지·분신술2 M1)
  rc=$?
  if [ "$rc" = 0 ]; then
    rm -f "$src"; [ "$src" = "$NEWF" ] && new_ok=1
  else
    left=$((left + 1))
  fi
done
shopt -u nullglob

if [ "$new_ok" = 1 ] && [ "$left" = 0 ]; then
  notify "큐 등록됨 ✅" "$LINE1"; logline "OK"
elif [ "$new_ok" = 1 ]; then
  notify "큐 등록됨 ✅ (이전 ${left}건 보류)" "$LINE1"; logline "OK_LEFT:$left"
else
  notify "큐 보류 ⏳ ${left}건" "네트워크 실패 — 보존됨, 다음 공유 때 자동 재시도(데이터 안 잃음)"; logline "DEFERRED:$left"
fi
