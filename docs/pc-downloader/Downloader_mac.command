#!/bin/bash
# ===============================================
#  만능 다운로더 맥판 v1.0 (Downloader_mac.command)
#  윈도우 Downloader.bat v5.7 대응 - YT/IG/X/TT/FB/Threads 비디오+이미지+자막
#  - 로컬: ~/Downloads/yt-dlp (없으면 생성)
#  - 클라우드: 구글드라이브 자동 탐지(앱 실행 중일 때만) → <내 드라이브>/Shared 바닥 평평 복사
#  - 자막: 플랫폼 자막(en,ko) 우선 → 없으면 Whisper large-v3 자동 추출(설치돼 있을 때)
#         srt + 타임코드 제거 txt 변환 + Shared 바닥에 제목 포함 이름으로 복사 = 윈도우판과 동일
#
#  설치(최초 1회, 터미널에 한 줄씩):
#    brew install yt-dlp ffmpeg gallery-dl
#    pip3 install mlx-whisper          # 애플실리콘 · large-v3 자막용(선택)
#  첫 실행: 파인더에서 이 파일 우클릭 → 열기 (보안 확인 1회)
#  실행 권한이 없다고 하면: chmod +x <이 파일 경로>
# ===============================================

SUBLANG="en,ko"
MAKE_SUBTXT=1

LOCAL="$HOME/Downloads/yt-dlp"
GTEMP="$LOCAL/_gallery_temp"
mkdir -p "$LOCAL"

echo "==============================================="
echo "  만능 다운로더 맥판 v1.0"
echo "  YT/IG/X/TT/FB/Threads - 비디오 + 이미지 + 자막"
echo "  인자/클립보드=첫 URL 자동 / 이후 계속 입력 가능 (q 종료)"
echo "==============================================="
echo

# === 도구 체크 ===
if ! command -v yt-dlp >/dev/null 2>&1; then
    echo "[오류] yt-dlp 없음. 터미널에서: brew install yt-dlp ffmpeg"
    read -r -p "엔터를 누르면 종료: " _
    exit 1
fi
command -v ffmpeg >/dev/null 2>&1 || echo "[경고] ffmpeg 없음(brew install ffmpeg). 영상 병합(mp4)/자막 srt 변환 실패 가능."

HAS_GDL=0
command -v gallery-dl >/dev/null 2>&1 && HAS_GDL=1
[ "$HAS_GDL" = "1" ] && echo "[확인] gallery-dl 사용 가능" || echo "[알림] gallery-dl 없음(brew install gallery-dl) - 이미지 다운로드 비활성화"

WHISPER=""
command -v mlx_whisper >/dev/null 2>&1 && WHISPER="mlx"
[ -z "$WHISPER" ] && command -v whisper >/dev/null 2>&1 && WHISPER="oai"
if [ -n "$WHISPER" ]; then
    echo "[확인] Whisper large-v3 사용 가능($WHISPER) - 플랫폼 자막 없으면 자동 추출"
else
    echo "[알림] Whisper 없음(pip3 install mlx-whisper) - 플랫폼 자막만 시도"
fi

# === 쿠키(선택): IG/X 이미지용 ===
COOKIES=""
[ -f "$HOME/.config/nomute/cookies.txt" ] && COOKIES="$HOME/.config/nomute/cookies.txt"
if [ -n "$COOKIES" ]; then echo "[확인] 쿠키 파일 있음 (IG/X 이미지 가능)"
else echo "[알림] 쿠키 없음(~/.config/nomute/cookies.txt) - IG/X 이미지는 쿠키 필요"; fi

echo "[확인] 자막 언어: $SUBLANG / txt 변환: $MAKE_SUBTXT"

# === 구글드라이브 자동 탐지 (v5.7 원칙: 앱 실행 중일 때만 = 죽은 잔재 폴더 오탐 차단) ===
echo
echo "[검증] 클라우드 쓰기 테스트..."
DUAL=0
GDRIVE=""
if pgrep -f "Google Drive" >/dev/null 2>&1 || pgrep -f "GoogleDrive" >/dev/null 2>&1; then
    for d in "$HOME/Library/CloudStorage"/GoogleDrive-*/"내 드라이브" \
             "$HOME/Library/CloudStorage"/GoogleDrive-*/"My Drive" \
             /Volumes/GoogleDrive*/"내 드라이브" \
             /Volumes/GoogleDrive*/"My Drive"; do
        if [ -d "$d" ]; then GDRIVE="$d"; break; fi
    done
    [ -z "$GDRIVE" ] && echo "[알림] 드라이브 앱은 켜져 있는데 '내 드라이브' 위치를 못 찾음 - 이번엔 로컬에만 저장"
else
    echo "[알림] 구글드라이브 앱이 실행 중이 아님 - 미설치/꺼짐/로그인 전. 이번엔 로컬에만 저장"
fi
if [ -n "$GDRIVE" ]; then
    CLOUD="$GDRIVE/Shared"
    echo "[확인] 구글드라이브 감지: $GDRIVE"
    mkdir -p "$CLOUD" 2>/dev/null
    if touch "$CLOUD/_write_test.tmp" 2>/dev/null; then
        rm -f "$CLOUD/_write_test.tmp"
        DUAL=1
        echo "[확인] 클라우드 쓰기 가능"
    else
        echo "[알림] 클라우드 쓰기 실패 - 이번엔 로컬에만 저장"
    fi
fi
echo "[확인] 로컬: $LOCAL"
[ "$DUAL" = "1" ] && echo "[확인] 클라우드: $CLOUD"
cd "$LOCAL" || exit 1

# === 첫 URL: 인자 → 클립보드 (윈도우 v5.2 대응) ===
ARGURL="${1:-}"
ARGSRC="인자로 받은"
if [ -z "$ARGURL" ] && command -v pbpaste >/dev/null 2>&1; then
    CB=$(pbpaste 2>/dev/null | head -1 | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    case "$(printf '%s' "$CB" | tr '[:upper:]' '[:lower:]')" in
        https://*|http://*|ttps://*|ttp://*) ARGURL="$CB"; ARGSRC="클립보드에서 감지한" ;;
    esac
fi

while :; do
    echo
    echo "-----------------------------------------------"
    if [ -n "$ARGURL" ]; then
        URL="$ARGURL"
        ARGURL=""
        echo "[자동] $ARGSRC 첫 URL 사용 (이후 계속 입력 가능)"
    else
        printf 'URL 붙여넣기 (q=종료): '
        IFS= read -r URL || break
    fi
    if [ "$URL" = "q" ] || [ "$URL" = "Q" ]; then break; fi
    [ -z "$URL" ] && continue

    # === URL 자동 정제 (윈도우 v4.7+ 대응: 앞 쓰레기 제거 + ttps 보정) ===
    URL=$(printf '%s' "$URL" | awk '{ p=index($0,"https://"); if(p==0)p=index($0,"http://"); if(p==0)p=index($0,"ttps://"); if(p==0)p=index($0,"ttp://"); if(p>0)$0=substr($0,p); sub(/^[ \t]+/,""); sub(/[ \t]+$/,""); if($0 ~ /^ttps:\/\// || $0 ~ /^ttp:\/\//) $0="h"$0; print }')
    case "$URL" in
        https://*|http://*) : ;;
        *) echo; echo "[오류] 유효한 URL이 아님: $URL"; echo "       https:// 로 시작하는 URL을 붙여넣어줘."; continue ;;
    esac
    echo "[URL] $URL"

    # === 플랫폼 감지 ===
    PLAT="ETC"
    case "$URL" in
        *youtube.com*|*youtu.be*) PLAT="YT" ;;
        *instagram.com*)          PLAT="IG" ;;
        *x.com*|*twitter.com*)    PLAT="X" ;;
        *tiktok.com*)             PLAT="TT" ;;
        *facebook.com*|*fb.watch*) PLAT="FB" ;;
        *threads.net*|*threads.com*) PLAT="TH" ;;
    esac
    TS=$(date +%Y%m%d_%H%M%S)
    echo "[감지] 플랫폼: $PLAT / 시각: $TS"
    [ "$PLAT" = "TH" ] && echo "[안내] Threads는 공식 지원이 불안정합니다. 일단 시도합니다."

    # === [1/3] yt-dlp 비디오 + 플랫폼 자막 ===
    echo
    echo "[1/3] yt-dlp 비디오 + 자막 시도..."
    CK=()
    [ -n "$COOKIES" ] && CK=(--cookies "$COOKIES")
    yt-dlp --no-cache-dir "${CK[@]}" --trim-filenames 120 --windows-filenames \
        -P "$LOCAL" -P "temp:${TMPDIR:-/tmp}" \
        -o "${TS}_${PLAT}_%(uploader_id)s_%(title)s.%(ext)s" \
        -o "subtitle:%(title)s/${TS}_${PLAT}_%(uploader_id)s.%(ext)s" \
        --write-subs --write-auto-subs --sub-langs "$SUBLANG" --convert-subs srt \
        -f "bv*+ba/b/best" --merge-output-format mp4 -N 4 "$URL" \
        || echo "[yt-dlp] 비디오 못 받음. 이미지 게시물일 가능성."

    # === [2/3] 자막 없으면 Whisper large-v3 자동 추출 ===
    echo
    if find "$LOCAL" -name "${TS}_${PLAT}_*.srt" 2>/dev/null | grep -q .; then
        echo "[2/3] 플랫폼 자막 확보 - Whisper 불필요"
    elif [ -n "$WHISPER" ]; then
        for f in "$LOCAL/${TS}_${PLAT}_"*.mp4 "$LOCAL/${TS}_${PLAT}_"*.m4a "$LOCAL/${TS}_${PLAT}_"*.webm "$LOCAL/${TS}_${PLAT}_"*.mp3 "$LOCAL/${TS}_${PLAT}_"*.mkv "$LOCAL/${TS}_${PLAT}_"*.mov; do
            [ -e "$f" ] || continue
            echo "[2/3] Whisper large-v3 자막 추출(길이에 따라 몇 분 걸릴 수 있음): $(basename "$f")"
            if [ "$WHISPER" = "mlx" ]; then
                mlx_whisper "$f" --model mlx-community/whisper-large-v3-mlx --output-dir "$LOCAL" --output-format srt
            else
                whisper "$f" --model large-v3 --output_format srt --output_dir "$LOCAL"
            fi
            stem=$(basename "$f")
            stem="${stem%.*}"
            if [ -f "$LOCAL/$stem.srt" ]; then
                mv -f "$LOCAL/$stem.srt" "$LOCAL/$stem.wlv3.srt"
                echo "  [srt] $stem.wlv3.srt"
            fi
        done
    else
        echo "[2/3] 플랫폼 자막 없음 + Whisper 미설치 - 자막 스킵"
    fi

    # === 자막 후처리: txt 변환 + Shared 바닥 평평 복사(제목 포함 이름) - 윈도우 v5.7 동일 ===
    while IFS= read -r s; do
        [ -n "$s" ] || continue
        t="${s%.srt}.txt"
        if [ "$MAKE_SUBTXT" = "1" ]; then
            awk '!/^[0-9]+[ \t\r]*$/ && !/-->/ { gsub(/<[^>]*>/,""); gsub(/\r$/,""); sub(/^[ \t]+/,""); sub(/[ \t]+$/,""); if($0!="" && $0!=prev){print; prev=$0} }' "$s" > "$t"
            if [ -s "$t" ]; then echo "  [txt] $(basename "$t")"; else rm -f "$t"; fi
        fi
        if [ "$DUAL" = "1" ]; then
            for x in "$s" "$t"; do
                [ -f "$x" ] || continue
                base=$(basename "$x")
                if [ "$(dirname "$x")" = "$LOCAL" ]; then
                    fn="$base"
                else
                    dir=$(basename "$(dirname "$x")")
                    fn="${base%%.*}_${dir}.${base#*.}"
                fi
                cp -f "$x" "$CLOUD/$fn" 2>/dev/null && echo "  [Shared 자막] $fn"
            done
        fi
    done < <(find "$LOCAL" -name "${TS}_${PLAT}_*.srt" 2>/dev/null)

    # === [3/3] gallery-dl 이미지 ===
    echo
    if [ "$PLAT" = "YT" ]; then
        echo "[3/3] YouTube - 이미지 없음, 스킵"
    elif [ "$HAS_GDL" = "0" ]; then
        echo "[3/3] gallery-dl 미설치 - 스킵"
    else
        echo "[3/3] gallery-dl 이미지 시도..."
        rm -rf "$GTEMP"
        mkdir -p "$GTEMP"
        gallery-dl -D "$GTEMP" --filter "extension not in ('mp4','m4v','webm','mov','m3u8','mp3','m4a','ts','aac','ogg')" "${CK[@]}" "$URL"
        GDL_RC=$?
        CNT=0
        while IFS= read -r f; do
            [ -n "$f" ] || continue
            mv -f "$f" "$LOCAL/${TS}_${PLAT}_gallery_$(basename "$f")" && CNT=$((CNT+1))
        done < <(find "$GTEMP" -type f 2>/dev/null)
        rm -rf "$GTEMP"
        if [ "$CNT" -gt 0 ]; then
            echo "[gallery-dl] ${CNT}개 이미지 받음"
        elif [ "$GDL_RC" -ne 0 ]; then
            echo "[gallery-dl] 실패(rc=$GDL_RC)"
            [ -z "$COOKIES" ] && echo "     쿠키 파일 없음. 확장프로그램으로 export 필요." || echo "     쿠키 만료 가능성. 재export 필요."
        else
            echo "[gallery-dl] 받은 이미지 없음"
        fi
    fi

    # === 클라우드 바닥 복사 (Shared는 항상 평평) ===
    echo
    if [ "$DUAL" = "1" ]; then
        N=0
        while IFS= read -r f; do
            [ -n "$f" ] || continue
            cp -f "$f" "$CLOUD/" 2>/dev/null && N=$((N+1))
        done < <(find "$LOCAL" -maxdepth 1 -type f -name "${TS}_${PLAT}_*")
        echo "[복사] Shared 바닥 복사: ${N}개"
    else
        echo "[복사] 클라우드 비활성화 - 로컬만 저장"
    fi

    echo
    echo "==============================================="
    echo "  다운로드 완료"
    echo "  로컬:    $LOCAL"
    [ "$DUAL" = "1" ] && echo "  클라우드: $CLOUD"
    echo "==============================================="
done

echo
echo "종료합니다."
