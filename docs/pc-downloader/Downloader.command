#!/bin/bash
# =====================================================================
#  만능 다운로더 v5.9.3-mac  (Downloader.bat v5.9.3 맥 이식)
#  YT/IG/X/TT/FB/Threads - 비디오 + 이미지 + 자막
#
#  동작 동일:
#   - 인자/클립보드=첫 URL 자동 / 이후 계속 입력 (q 종료)
#   - 아무 키 = URL 입력 / Q = 종료 / ESC 2번 = 창 닫기
#   - yt-dlp 비디오+자막(srt→txt 변환), gallery-dl 이미지
#   - 구글드라이브 Shared 바닥 평평 복사 (폰 파이프라인용)
#
#  맥 치환 내역:
#   - 도구: .exe 대신 PATH 자동 탐색 (brew → uv(~/.local/bin) → 전사 venv 순)
#     yt-dlp·ffmpeg = ~/.claude/skills/whisper/.venv/bin (전사 스택과 공용)
#     gallery-dl    = ~/.local/bin (uv tool install gallery-dl)
#   - 쿠키: 스크립트 옆 yt-dlp/cookies.txt 그대로 (OneDrive로 윈도와 공유)
#   - 클라우드 고정 경로(Q226 유지): CloudStorage/GoogleDrive-계정/내 드라이브/Shared
#     ※ 구글 계정 바뀌면 아래 GD_ROOT 한 줄만 수정
#   - robocopy→cp / 클립보드→pbpaste / 창 닫기→AppleScript(Terminal)
#   - --windows-filenames 유지: 윈도PC·폰과 파일명 규칙 통일(동기화 안전)
#   - 이 파일은 UTF-8 저장 (맥 표준. CP949 금지)
#   - v5.9.2 낙오자 재송 스위프 이식: 지난 7일 미전송분 시작 시 재송(동명 존재 = 스킵)
#   - v5.9.3(윈도 G: 문자 마운트 고정)은 윈도 전용 - 맥은 CloudStorage 경로 그대로(변경 무관)
# =====================================================================

VENV_BIN="$HOME/.claude/skills/whisper/.venv/bin"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH:$VENV_BIN"

ESCCH=$'\033'

# --- 창 닫기 (맥판: 이 스크립트가 떠 있는 Terminal 창만 닫음) ---
close_terminal_window() {
    MYTTY=$(tty 2>/dev/null)
    if [ "$TERM_PROGRAM" = "Apple_Terminal" ] && [ -n "$MYTTY" ]; then
        nohup osascript \
            -e 'on run argv' \
            -e 'tell application "Terminal"' \
            -e 'repeat with w in windows' \
            -e 'repeat with t in tabs of w' \
            -e 'if (tty of t) is (item 1 of argv) then' \
            -e 'close w saving no' \
            -e 'return' \
            -e 'end if' \
            -e 'end repeat' \
            -e 'end repeat' \
            -e 'end tell' \
            -e 'end run' \
            "$MYTTY" >/dev/null 2>&1 &
    fi
    exit 0
}

esc_exit() {
    echo
    echo "[ESC 2번] 창을 닫습니다."
    close_terminal_window
}

end_exit() {
    echo
    echo "종료합니다."
    read -r -p "엔터를 누르면 창이 닫힙니다... " _
    close_terminal_window
}

ARGURL="$1"
printf '\033]0;만능 다운로더 v5.9.3-mac\007'

echo "==============================================="
echo "  만능 다운로더 v5.9.3-mac"
echo "  YT/IG/X/TT/FB/Threads - 비디오 + 이미지 + 자막"
echo "  인자/클립보드=첫 URL 자동 / 이후 계속 입력 가능 (q 종료)"
echo "  ESC 2번 연속 = 창 닫기"
echo "==============================================="
echo

# === 클립보드 모드: 인자 없이 실행하면(더블클릭 등) 클립보드가 URL일 때 첫 입력으로 자동 사용 ===
ARGSRC="인자로 받은"
if [ -z "$ARGURL" ]; then
    CLIP=$(pbpaste 2>/dev/null | head -n 1 | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    CLIPLC=$(printf '%s' "$CLIP" | tr '[:upper:]' '[:lower:]')
    case "$CLIPLC" in
        https://*|http://*|ttps://*|ttp://*) ARGURL="$CLIP"; ARGSRC="클립보드에서 감지한" ;;
    esac
fi

# === 경로 설정 ===
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# 쿠키: 스크립트 옆 yt-dlp/cookies.txt 우선(OneDrive 공유) — 다른 곳에서 실행 시 고정 경로
COOKIES="$SCRIPT_DIR/yt-dlp/cookies.txt"
[ -f "$COOKIES" ] || COOKIES="$HOME/Library/CloudStorage/OneDrive-GS칼텍스예울마루/황세웅/6.  Nomute/창고/05. Utility/yt-dlp/cookies.txt"

# 클라우드 = 고정 경로 (v5.9 Q226 · 계정 바뀌면 이 줄 수정)
GD_ROOT="$HOME/Library/CloudStorage/GoogleDrive-ems1130g@gmail.com/내 드라이브"
CLOUD="$GD_ROOT/Shared"
LOCAL="$HOME/Downloads/yt-dlp"
GTEMP="$LOCAL/_gallery_temp"

# === 자막 설정 ===
#   SUBLANG    : 받을 자막 언어. "en,ko" / "en" / "ko" / "all" 등. -로 제외 가능("all,-live_chat")
#   MAKE_SUBTXT: 1=srt를 타임코드 제거한 txt로도 변환, 0=srt만 유지
SUBLANG="en,ko"
MAKE_SUBTXT=1

# === yt-dlp 체크 ===
YTDLP_BIN=$(command -v yt-dlp)
if [ -z "$YTDLP_BIN" ]; then
    echo "[오류] yt-dlp 없음."
    echo "       기본 위치(전사 스택): $VENV_BIN"
    echo "       재설치: brew install yt-dlp 또는 uv tool install yt-dlp"
    read -r -p "엔터로 종료... " _
    close_terminal_window
fi

# === ffmpeg 체크 ===
FFMPEG_BIN=$(command -v ffmpeg)
if [ -n "$FFMPEG_BIN" ]; then
    FFLOC=(--ffmpeg-location "$(dirname "$FFMPEG_BIN")")
else
    FFLOC=()
    echo "[경고] ffmpeg 없음. 영상 병합(mp4) 및 자막 srt 변환이 실패할 수 있음."
fi

# === JS 런타임 (유튜브 고화질 포맷용) ===
#     yt-dlp가 기본으론 deno만 찾음. deno 없고 node 있으면 node 사용 (없으면 240p로 떨어짐)
JSRT=()
if ! command -v deno >/dev/null 2>&1 && command -v node >/dev/null 2>&1; then
    JSRT=(--js-runtimes node)
fi

# === gallery-dl 체크 ===
HAS_GDL=0
command -v gallery-dl >/dev/null 2>&1 && HAS_GDL=1
[ "$HAS_GDL" = "1" ] && echo "[확인] gallery-dl 사용 가능"
[ "$HAS_GDL" = "0" ] && echo "[경고] gallery-dl 없음(uv tool install gallery-dl). 이미지 다운로드 비활성화."

# === 쿠키 파일 체크 ===
HAS_COOKIES=0
[ -f "$COOKIES" ] && HAS_COOKIES=1
[ "$HAS_COOKIES" = "1" ] && echo "[확인] 쿠키 파일 있음 (IG/X 이미지 가능)"
[ "$HAS_COOKIES" = "0" ] && echo "[알림] 쿠키 파일 없음. IG/X 이미지는 쿠키 필요."

# === 자막 설정 표시 ===
echo "[확인] 자막 언어: $SUBLANG / txt 변환: $MAKE_SUBTXT"

# === 로컬 폴더 ===
mkdir -p "$LOCAL"

# === 클라우드 사전 검증 ===
echo
echo "[검증] 클라우드 쓰기 테스트..."
DUAL=0
GD_WHY=""
GDFS_ON=0
pgrep -xq "Google Drive" && GDFS_ON=1
if [ "$GDFS_ON" = "0" ]; then
    echo "[알림] 구글드라이브 앱이 실행 중이 아님 - 미설치/꺼짐/로그인 전"
    echo "       앱 켜고 로그인하면 클라우드 복사 활성화. 이번엔 로컬에만 저장"
    GD_WHY="드라이브 앱 꺼짐/미로그인 - 응용 프로그램에서 Google Drive 실행"
elif [ ! -d "$GD_ROOT" ]; then
    echo "[알림] CloudStorage 마운트 없음 - 로그인 계정이 다르거나 스트리밍 미설정. 이번엔 로컬에만 저장"
    GD_WHY="CloudStorage 마운트 없음 - 드라이브 계정(ems1130g)/스트리밍 설정 확인"
else
    echo "[확인] 클라우드(고정): $CLOUD"
    GD_WHY="Shared 폴더 생성/쓰기 실패"
    mkdir -p "$CLOUD" 2>/dev/null
    if [ -d "$CLOUD" ] && echo "test_$$" > "$CLOUD/_write_test.tmp" 2>/dev/null && [ -f "$CLOUD/_write_test.tmp" ]; then
        rm -f "$CLOUD/_write_test.tmp"
        DUAL=1
        GD_WHY=""
        echo "[확인] 클라우드 쓰기 가능"
    fi
fi

# === v5.9.2 이식: 낙오자 재송 스위프 - 지난 실행에서 클라우드에 못 간 파일(앱 꺼짐·복사 실패) 자동 재송 ===
#     날짜 필터 = 파일명 TS 앞 8자리(mtime 금지 - yt-dlp가 mtime을 업로드일로 바꿈) · 동명 존재 = 스킵(재복사 0)
if [ "$DUAL" = "1" ]; then
    echo "[스위프] 지난 7일 미전송분 재송 확인..."
    SW_N=0
    for i in 0 1 2 3 4 5 6 7; do
        day=$(date -v -${i}d +%Y%m%d 2>/dev/null)
        [ -n "$day" ] || continue
        for f in "$LOCAL/${day}"_*; do
            [ -f "$f" ] || continue
            [ -f "$CLOUD/$(basename "$f")" ] && continue
            cp -f "$f" "$CLOUD/" 2>/dev/null && SW_N=$((SW_N+1))
        done
    done
    if [ "$SW_N" -gt 0 ]; then echo "[스위프] ${SW_N}개 재송"; else echo "[스위프] 재송분 없음"; fi
fi

# 검증 결과 사유 보존(매 URL마다 초기화용 — 이전 URL의 복사 실패 사유가 다음 결과에 남지 않게)
GD_WHY0="$GD_WHY"

echo "[확인] 로컬: $LOCAL"
[ "$DUAL" = "1" ] && echo "[확인] 클라우드: $CLOUD"
cd "$LOCAL" || true

# ===================== 메인 루프 =====================
while true; do
    echo
    echo "-----------------------------------------------"
    GD_WHY="$GD_WHY0"

    # === 인자/클립보드로 URL 받았으면 그걸 첫 입력으로, 아니면 직접 입력 ===
    if [ -n "$ARGURL" ]; then
        URL="$ARGURL"
        ARGURL=""
        echo "[자동] $ARGSRC 첫 URL 사용 (이후 계속 입력 가능)"
    else
        # === 단일키 게이트 - ESC 2번=창닫기 / Q=종료 / 그 외 아무 키=URL 입력 ===
        echo "[아무 키 = URL 입력 / Q = 종료 / ESC 2번 = 창 닫기]"
        esc=0
        GATE="go"
        while true; do
            IFS= read -r -s -n 1 key
            if [ "$key" = "$ESCCH" ]; then
                esc=$((esc+1))
                if [ "$esc" -ge 2 ]; then GATE="esc"; break; fi
            elif [ "$key" = "q" ] || [ "$key" = "Q" ]; then
                GATE="quit"; break
            else
                break
            fi
        done
        [ "$GATE" = "esc" ] && esc_exit
        [ "$GATE" = "quit" ] && end_exit
        URL=""
        read -r -p "URL 붙여넣기 (q=종료): " URL
    fi

    [ "$URL" = "q" ] || [ "$URL" = "Q" ] && end_exit
    [ -z "$URL" ] && continue

    # ===================================================
    #  URL 자동 정제 v4.7+
    #  - 앞에 붙은 쓰레기 텍스트 제거
    #  - ttps:// ttp:// -> https:// http:// 보정 (게이트가 첫 글자 먹은 경우)
    #  - 유효성 검증
    # ===================================================
    for p in "https://" "http://" "ttps://" "ttp://"; do
        case "$URL" in
            *"$p"*) URL="$p${URL#*"$p"}"; break ;;
        esac
    done
    URL=$(printf '%s' "$URL" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    URLLC=$(printf '%s' "$URL" | tr '[:upper:]' '[:lower:]')
    case "$URLLC" in
        ttps://*|ttp://*) URL="h$URL"; URLLC="h$URLLC" ;;
    esac

    case "$URLLC" in
        https://*|http://*) : ;;
        *)
            echo
            echo "[오류] 유효한 URL이 아님: $URL"
            echo "       https:// 로 시작하는 URL을 붙여넣어줘."
            echo
            continue
            ;;
    esac

    echo "[URL] $URL"

    # === 플랫폼 감지 ===
    PLAT="ETC"
    case "$URLLC" in
        *youtube.com*|*youtu.be*)      PLAT="YT" ;;
        *instagram.com*)               PLAT="IG" ;;
        *x.com*|*twitter.com*)         PLAT="X"  ;;
        *tiktok.com*)                  PLAT="TT" ;;
        *facebook.com*|*fb.watch*)     PLAT="FB" ;;
        *threads.net*|*threads.com*)   PLAT="TH" ;;
    esac

    TS=$(date +%Y%m%d_%H%M%S)
    echo "[감지] 플랫폼: $PLAT / 시각: $TS"

    # === Threads 안내 ===
    if [ "$PLAT" = "TH" ]; then
        echo "[안내] Threads는 yt-dlp/gallery-dl 공식 지원이 불안정합니다."
        echo "       다운로드 실패 가능성이 높습니다. 일단 시도합니다."
    fi

    # === 자막 안내 ===
    if [ "$PLAT" != "YT" ]; then
        echo "[안내] 자막 추출은 YouTube에서 가장 안정적입니다."
        echo "       IG/X/TT/FB/Threads는 자막 트랙이 드물어 .srt/.txt가 안 생길 수 있습니다."
    fi

    # === [1/2] yt-dlp 비디오 + 자막 시도 ===
    echo
    echo "[1/2] yt-dlp 비디오 + 자막 시도..."
    if [ "$HAS_COOKIES" = "1" ]; then
        yt-dlp --no-cache-dir "${FFLOC[@]}" "${JSRT[@]}" --cookies "$COOKIES" \
            --trim-filenames 120 --windows-filenames \
            -P "$LOCAL" -P "temp:${TMPDIR:-/tmp}" \
            -o "${TS}_${PLAT}_%(uploader_id)s_%(title)s.%(ext)s" \
            -o "subtitle:%(title)s/${TS}_${PLAT}_%(uploader_id)s.%(ext)s" \
            --write-subs --write-auto-subs --sub-langs "$SUBLANG" --convert-subs srt \
            -f "bv*+ba/b/best" --merge-output-format mp4 -N 4 "$URL"
    else
        yt-dlp --no-cache-dir "${FFLOC[@]}" "${JSRT[@]}" \
            --trim-filenames 120 --windows-filenames \
            -P "$LOCAL" -P "temp:${TMPDIR:-/tmp}" \
            -o "${TS}_${PLAT}_%(uploader_id)s_%(title)s.%(ext)s" \
            -o "subtitle:%(title)s/${TS}_${PLAT}_%(uploader_id)s.%(ext)s" \
            --write-subs --write-auto-subs --sub-langs "$SUBLANG" --convert-subs srt \
            -f "bv*+ba/b/best" --merge-output-format mp4 -N 4 "$URL"
    fi
    YT_RC=$?
    [ "$YT_RC" -ne 0 ] && echo "[yt-dlp] 비디오 못 받음. 이미지 게시물일 가능성."

    # === 자막 후처리 (txt 변환 + Shared 바닥 평평 복사) ===
    #     폰 파이프라인은 Shared 바닥만 훑으므로 자막을 '시각_플랫폼_업로더_제목.언어.확장자'로 바닥에 복사(로컬은 제목 폴더 유지)
    echo
    echo "[자막] 후처리: txt 변환=$MAKE_SUBTXT / Shared 평평 복사=$DUAL..."
    find "$LOCAL" -type f -name "${TS}_${PLAT}_*.srt" 2>/dev/null | while IFS= read -r f; do
        t="${f%.srt}.txt"
        if [ "$MAKE_SUBTXT" = "1" ]; then
            awk '
                /^[0-9]+[[:space:]]*$/ { next }
                /-->/ { next }
                {
                    gsub(/<[^>]*>/, "")
                    gsub(/^[[:space:]]+/, ""); gsub(/[[:space:]]+$/, "")
                    if ($0 == "") next
                    if ($0 != prev) { print; prev = $0 }
                }
            ' "$f" > "$t" 2>/dev/null
            if [ -s "$t" ]; then
                echo "  [txt] $(basename "$t")"
            else
                rm -f "$t"
            fi
        fi
        if [ "$DUAL" = "1" ]; then
            fn=$(basename "$f")
            d=$(dirname "$f")
            if [ "$d" != "$LOCAL" ]; then
                fn="${fn%%.*}_$(basename "$d").${fn#*.}"
            fi
            cp -f "$f" "$CLOUD/$fn" 2>/dev/null
            [ -f "$t" ] && cp -f "$t" "$CLOUD/${fn%.srt}.txt" 2>/dev/null
            echo "  [Shared 자막] $fn"
        fi
    done

    # === [2/2] gallery-dl 이미지 시도 ===
    echo
    if [ "$PLAT" = "YT" ]; then
        echo "[2/2] YouTube - 이미지 없음, 스킵"
    elif [ "$HAS_GDL" = "0" ]; then
        echo "[2/2] gallery-dl 미설치 - 스킵"
    else
        echo "[2/2] gallery-dl 이미지 시도..."
        rm -rf "$GTEMP" 2>/dev/null
        mkdir -p "$GTEMP" 2>/dev/null
        GDLFILTER="extension not in ('mp4','m4v','webm','mov','m3u8','mp3','m4a','ts','aac','ogg')"
        if [ "$HAS_COOKIES" = "1" ]; then
            gallery-dl -D "$GTEMP" --filter "$GDLFILTER" --cookies "$COOKIES" "$URL"
        else
            gallery-dl -D "$GTEMP" --filter "$GDLFILTER" "$URL"
        fi
        GDL_RC=$?
        GDL_CNT=0
        while IFS= read -r f; do
            if mv -f "$f" "$LOCAL/${TS}_${PLAT}_gallery_$(basename "$f")" 2>/dev/null; then
                GDL_CNT=$((GDL_CNT+1))
            fi
        done < <(find "$GTEMP" -type f 2>/dev/null)
        rm -rf "$GTEMP" 2>/dev/null
        if [ "$GDL_CNT" -gt 0 ]; then
            echo "[gallery-dl] ${GDL_CNT}개 이미지 받음"
        elif [ "$GDL_RC" -ne 0 ]; then
            echo "[gallery-dl] 실패 (exit=$GDL_RC)"
            [ "$HAS_COOKIES" = "0" ] && echo "     쿠키 파일 없음. 확장프로그램으로 export 필요."
            [ "$HAS_COOKIES" = "1" ] && echo "     쿠키 만료 가능성. 재export 필요."
        else
            echo "[gallery-dl] 받은 이미지 없음"
        fi
    fi

    # === 클라우드 복사 (robocopy → cp, 바닥 평평 유지) ===
    echo
    if [ "$DUAL" = "0" ]; then
        echo "[복사] 클라우드 비활성화 - 로컬만 저장"
    else
        echo "[복사] 클라우드 동기화..."
        CP_N=0
        CP_ERR=0
        for f in "$LOCAL"/${TS}_${PLAT}_*; do
            [ -f "$f" ] || continue
            if cp -f "$f" "$CLOUD/" 2>/dev/null; then
                CP_N=$((CP_N+1))
            else
                CP_ERR=1
            fi
        done
        if [ "$CP_ERR" = "1" ]; then
            echo "[복사 실패] 일부 파일 복사 오류"
            echo "     로컬 파일은 안전: $LOCAL"
            GD_WHY="cp 복사 오류"
        elif [ "$CP_N" -gt 0 ]; then
            echo "[복사] 완료 (${CP_N}개)"
        else
            echo "[복사] 새 파일 없음"
        fi
    fi

    # === 끝 화면: GDRIVE 전송 결과 상시 표시 (도착 개수 실측 / 미전송 사유) ===
    GD_CNT=0
    if [ "$DUAL" = "1" ]; then
        GD_CNT=$(ls -1 "$CLOUD"/${TS}_${PLAT}_* 2>/dev/null | wc -l | tr -d '[:space:]')
    fi
    echo
    echo "==============================================="
    echo "  다운로드 완료"
    echo "  로컬:    $LOCAL"
    if [ "$DUAL" = "1" ] && [ -z "$GD_WHY" ]; then
        echo "  GDRIVE : 전송 완료 ${GD_CNT}개 - $CLOUD"
    elif [ "$DUAL" = "1" ]; then
        echo "  GDRIVE : 전송 이상 - 도착 ${GD_CNT}개 / $GD_WHY"
    else
        echo "  GDRIVE : 미전송 - $GD_WHY"
    fi
    echo "==============================================="
    echo
done
