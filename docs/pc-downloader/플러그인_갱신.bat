@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title 스레드 플러그인 갱신 (nomute_threads.py)

REM ============================================================
REM  PC 다운로더용 스레드 플러그인 1클릭 갱신기 (운영자 260803)
REM
REM  왜 필요한가:
REM    Downloader.bat 이 쓰는 yt-dlp 는 OneDrive 폴더 옆의 플러그인을 자동으로 읽는다.
REM    그런데 그 사본이 구판(1.0.0)이면 threads.com/share/<코드> 공유 링크를 통째로 못 받는다.
REM    구판·신판이 둘 다 __version__ 1.0.0 이던 시절이 있어(260803 실사고) 눈으로 구분도 안 됐다.
REM    -> 이 파일을 더블클릭하면 깃허브 정본을 받아 그 자리에 덮어쓴다. 옛 파일은 .bak 으로 남긴다.
REM
REM  끄는 법: 그냥 안 돌리면 된다(이 파일은 아무것도 상주시키지 않는다).
REM  로그: 이 창에 그대로 보인다. 창은 아무 키나 누를 때까지 안 닫힌다.
REM ============================================================

set "RAW=https://raw.githubusercontent.com/muteno/nomute-editor/main/apps/vidl/plugins/yt_dlp_plugins/extractor/nomute_threads.py"

echo.
echo   [스레드 플러그인 갱신]
echo.

REM --- yt-dlp 폴더 찾기 (Downloader.bat 과 같은 경로 규칙) ---
set "YTDLP="
if defined OneDriveCommercial if exist "%OneDriveCommercial%\황도현\6.  Nomute\창고\05. Utility\yt-dlp" set "YTDLP=%OneDriveCommercial%\황도현\6.  Nomute\창고\05. Utility\yt-dlp"
if not defined YTDLP if defined OneDrive if exist "%OneDrive%\황도현\6.  Nomute\창고\05. Utility\yt-dlp" set "YTDLP=%OneDrive%\황도현\6.  Nomute\창고\05. Utility\yt-dlp"
if not defined YTDLP if exist "%USERPROFILE%\Downloads\yt-dlp" set "YTDLP=%USERPROFILE%\Downloads\yt-dlp"

if not defined YTDLP (
    echo   [실패] yt-dlp 폴더를 못 찾았어요.
    echo          OneDrive 동기화가 켜져 있는지 확인하고 다시 실행해 주세요.
    goto :end
)
echo   yt-dlp 폴더: %YTDLP%

REM --- 기존 플러그인 위치 찾기(하위 어디에 있든) ---
set "TARGET="
for /f "delims=" %%f in ('dir /b /s "%YTDLP%\nomute_threads.py" 2^>nul') do set "TARGET=%%f"

if defined TARGET (
    echo   기존 파일: !TARGET!
    for /f "usebackq tokens=* delims=" %%v in (`powershell -noprofile -c "$m=Select-String -Path '!TARGET!' -Pattern \"__version__\s*=\s*'([^']+)'\" -AllMatches | Select-Object -First 1; if($m){$m.Matches[0].Groups[1].Value}else{'(버전 표기 없음)'}"`) do echo   현재 버전: %%v
) else (
    REM 없으면 yt-dlp 표준 플러그인 경로에 새로 놓는다
    set "TARGET=%YTDLP%\yt-dlp-plugins\nomute\yt_dlp_plugins\extractor\nomute_threads.py"
    echo   기존 파일이 없어 새로 설치합니다: !TARGET!
)

for %%d in ("!TARGET!") do set "TDIR=%%~dpd"
if not exist "!TDIR!" mkdir "!TDIR!" 2>nul

REM --- 정본 내려받기 (임시파일로 받아 검증 후 교체 = 실패해도 기존 파일 무손상) ---
set "TMPF=%TEMP%\nomute_threads.new.py"
echo   깃허브 정본 받는 중...
powershell -noprofile -c "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%RAW%' -OutFile '%TMPF%' -UseBasicParsing" 2>nul
if errorlevel 1 (
    echo   [실패] 내려받기 실패 - 인터넷 연결을 확인해 주세요. 기존 파일은 그대로입니다.
    goto :end
)

REM 받은 파일이 진짜 플러그인인지 검증(빈 파일·오류 페이지 덮어쓰기 차단)
find /i "NomuteThreadsIE" "%TMPF%" >nul 2>&1
if errorlevel 1 (
    echo   [실패] 받은 파일이 플러그인이 아닙니다. 기존 파일은 그대로입니다.
    del "%TMPF%" 2>nul
    goto :end
)

if exist "!TARGET!" copy /y "!TARGET!" "!TARGET!.bak" >nul 2>&1
copy /y "%TMPF%" "!TARGET!" >nul
del "%TMPF%" 2>nul

for /f "usebackq tokens=* delims=" %%v in (`powershell -noprofile -c "$m=Select-String -Path '!TARGET!' -Pattern \"__version__\s*=\s*'([^']+)'\" -AllMatches | Select-Object -First 1; if($m){$m.Matches[0].Groups[1].Value}"`) do set "NEWV=%%v"
echo.
echo   [완료] 갱신됨 - 새 버전: !NEWV!
echo          옛 파일은 같은 폴더에 .bak 으로 남겨뒀어요.
echo.
echo   이제 Downloader.bat 에 threads.com/share/... 주소를 넣어도 받아집니다.

:end
echo.
pause
endlocal
