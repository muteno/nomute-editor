@echo off
chcp 949 >nul
setlocal enabledelayedexpansion

REM === 인자 모드 (v5.1): 단축키 등으로 URL을 넘기면 그 URL을 첫 입력으로 자동 처리 ===
REM     처리 후 종료하지 않고 계속 다음 URL 입력 대기 (q로 종료)
REM === v5.3: [자동] 괄호 이스케이프(파서 픽스) + CP949 저장(깨진문자 커맨드 픽스) + 자막=영상제목 폴더 ===
REM === v5.5: ESC 2번 = 창 닫기 (안정판: 키 감지는 단일키 게이트만, URL 입력은 원본 set /p 유지) ===
REM === v5.6: 구글드라이브 자동 탐지(아무 드라이브 문자/한·영 UI/폴더·미러 마운트) - 계정 무관 Shared 복사 ===
REM === v5.7: 라이브 마운트 우선+앱 구동 체크(잔재 폴더 오탐 픽스) + 자막 Shared 바닥 평평 복사 ===
REM === v5.8: 끝 화면에 GDRIVE 전송 결과 상시 표시(도착 개수 실측 / 미전송 사유) ===
REM === v5.9: 클라우드 경로 고정 - 유저프로필\Google Drive 스트리밍\내 드라이브\Shared (자동탐지 폐기 · Q226) ===
REM === v5.9.1: 스트리밍 폴더 실존 게이트(유령 로컬 폴더 차단) + 끝화면 robocopy 실패 오보 봉합 - 오퍼스 3인 검증 반영 ===
REM === v5.9.2: 낙오자 재송 스위프 - 시작 시 지난 7일 미전송분 자동 재송(날짜 = 파일명 앞 8자리 · 아이데이션 Q229 반영) ===
REM === v5.9.3: 클라우드 = G:\내 드라이브\Shared 문자 마운트 고정(스트리밍 폴더 경로 폐기 · 운영자 260721) ===
REM === v6.0: 클라우드 = 드라이브 문자 자동 감지 복원(계정 동일 · G:/I: 등 문자 가변 PC 대응 - 볼륨 라벨 우선 + 문자 스캔 폴백 · 운영자 260723) ===
REM === v6.1: 최고화질 강제 + 최고화질이 1080p 초과(가로영상)면 최고화질 + 1080p mp4 동반본 다운로드 · 화질 1회 선행조회 · 쿠키 인자 통합(운영자 260723) ===
REM === v6.2: [최고화질 실패 봉합] YouTube에 쿠키를 넘기지 않는다 + 화질 영수증 상시 출력 + deno 감지 + 자막 후처리 복원(운영자 260728) ===
REM     ▶ v6.1까지 유튜브가 최고화질로 안 받아진 진짜 이유(yt-dlp 2026.07 소스 실측):
REM       --cookies가 붙으면 yt-dlp가 '인증 세션'으로 판단해 유튜브 플레이어 클라이언트를
REM       기본값 android_vr 에서 tv_downgraded + web_safari 로 통째로 갈아끼운다.
REM         · android_vr    = JS런타임 불필요 · PO토큰 불필요  -^> 고화질 포맷 전부 나옴
REM         · tv_downgraded = JS런타임(deno) 필요
REM         · web_safari    = JS런타임 + PO토큰 필요 -^> 없으면 URL 누락(SABR)으로 포맷이 통째 스킵
REM       게다가 인증 상태에선 android_vr가 "쿠키 미지원"이라 강제 제거되고,
REM       "JS런타임 없음" 경고조차 인증 경로에선 안 뜬다 = 조용히 저화질로 떨어진다.
REM       -^> 그래서 -f "bv*+ba/b/best"(포맷 문자열 자체는 정상)여도 고화질이 안 잡혔다.
REM       -^> v6.2는 YT에 한해 쿠키를 빼고 받는다. 공개영상은 쿠키가 필요 없다.
REM          연령제한·멤버십 등으로 실패하면 그때만 쿠키를 붙여 1회 재시도한다.
REM === v6.3: [프레임 축 분리] 해상도 최고 1개 + 프레임 최고 1개를 각각 받는다(운영자 260728) ===
REM     지시 = "해상도랑 프레임별로 가장 높은 거 하나씩 뽑게 해. 그게 같으면 하나만".
REM     이유 = yt-dlp 기본 정렬은 res(해상도)가 fps(프레임)보다 우선이라,
REM       4K가 30fps뿐이고 1440p가 60fps인 영상에서 4K30만 받고 1440p60을 버렸다.
REM       실측(셀렉터 오프라인 대입):
REM         · 4K에 60fps 있음   -> 해상도본 = 프레임본 = format 315 (같음 = 1개만)
REM         · 4K는 30뿐/1440p60 -> 해상도본 313(2160p30) · 프레임본 308(1440p60) (다름 = 2개)
REM         · 전부 30fps        -> 둘 다 format 313 (같음 = 1개만)
REM     구현 = 선행조회를 2축으로(기본정렬 / -S "fps,res,br") 돌려 format_id 비교.
REM       같으면 본편 1개만. 다르면 본편(해상도) + maxfps_ 표식 파일(프레임) 2개.
REM     파일 표식 = 본편(표식 없음) · maxfps_(프레임 최고) · 1080p_(호환용, v6.1 유지)
REM === v6.4: [화질 3축 + 다운로드 범위 고정] (운영자 260728) ===
REM     지시 = "1) 최고해상도 1개  2) 최고프레임 1개  (1==2면 1만)
REM             3) 세로 1080p 1개  (1==3이면 1만)
REM             영상 링크(또는 재생목록)에 해당하는 영상만 다운로드"
REM     축3 = 세로 1080p = 짧은 변이 1080인 호환본. v6.1은 가로영상에만 줬는데 세로영상
REM       (쇼츠·릴스)도 받게 확장했다. 가로영상 = height^<=1080(1920x1080) · 세로영상 =
REM       width^<=1080(1080x1920). 세로영상에 height 필터를 쓰면 1080x1920의 height가
REM       1920이라 매치가 아예 없다(오프라인 실측) - v6.1이 세로를 제외했던 이유가 이것.
REM     '같으면 1개' 판정 = 화면 크기 비교가 아니라 format_id 비교. 축마다 다운로드와
REM       같은 순서의 셀렉터로 1회 선행조회(--print = 다운로드 안 함) -^> 앞 축과 format_id가
REM       겹치면 그 축은 안 받는다. 4K30+1080p60 영상처럼 축2와 축3이 겹치는 경우도 걸러진다.
REM     범위 고정 = watch?v=..^&list=.. 링크는 재생목록이 통째로 딸려오므로 --no-playlist,
REM       /playlist 링크만 --yes-playlist(재생목록 전체). 채널 URL엔 영향 없다.
REM       ※ 재생목록이면 선행조회는 첫 영상 기준(--playlist-items 1)이라 축 판정도 첫 영상 기준.
REM     파일 표식 = 본편(표식 없음) · maxfps_(프레임 최고) · 1080p_(짧은변 1080 호환본)
REM === 주의: 이 파일은 CP949/ANSI로만 저장할 것 - UTF-8 재저장 시 한글 고정경로가 깨져 유령 폴더 생성 ===
set "ARGURL=%~1"

echo ===============================================
echo   만능 다운로더 v6.5
echo   YT/IG/X/TT/FB/Threads - 비디오 + 이미지 + 자막
echo   해상도 최고 + 프레임 최고 + 짧은변 1080p 각 1개(겹치면 생략)
echo   링크가 가리키는 영상(또는 재생목록)만 다운로드
echo   ffmpeg 자동확보 = 360p 폴백 차단
echo   인자/클립보드=첫 URL 자동 / 이후 계속 입력 가능 (q 종료)
echo   ESC 2번 연속 = 창 닫기
echo ===============================================
echo.

REM === 클립보드 모드 (v5.2): 인자 없이 실행하면(더블클릭·단축키 등) 클립보드가 URL일 때 첫 입력으로 자동 사용 ===
set "ARGSRC=인자로 받은"
if defined ARGURL goto argsrc_done
for /f "usebackq delims=" %%a in (`powershell -noprofile -c "$l=@(Get-Clipboard -ErrorAction SilentlyContinue)[0]; if($l){$l=$l.Trim(); $t=$l.ToLower(); foreach($p in 'https://','http://','ttps://','ttp://'){ if($t.StartsWith($p)){ Write-Output $l; break } } }"`) do set "ARGURL=%%a"
if defined ARGURL set "ARGSRC=클립보드에서 감지한"
:argsrc_done

REM === 경로 설정 ===
set "YTDLP=%OneDriveCommercial%\황세웅\6.  Nomute\창고\05. Utility\yt-dlp"
set "GDL=%YTDLP%\gallery-dl.exe"
set "COOKIES=%YTDLP%\cookies.txt"
REM === 클라우드 저장 = 드라이브 문자 자동 감지 (v6.0 · 운영자 260723) - 문자:\내 드라이브\Shared ===
REM     PC마다 마운트 문자가 G:/I: 등 달라도(구글 계정 동일) 같은 '내 드라이브\Shared'를 찾아 복사
REM     감지 = 아래 [검증] 단계에서 1)Google Drive 볼륨 라벨 문자 2)문자 전수 스캔(Shared 있는 마운트 우선) 순
REM     GDFS_ON(앱 실행 체크)은 유지: 앱 꺼짐 시 로컬만(죽은 잔재 폴더 오탐 방지 · v5.7 계승)
set "GDFS_ON=0"
tasklist /fi "imagename eq GoogleDriveFS.exe" 2>nul | find /i "GoogleDriveFS.exe" >nul && set "GDFS_ON=1"
REM 클라우드 경로 = 아래 [검증]에서 자동 감지로 확정 (미감지 = 이번 실행 로컬만)
set "CLOUD="
set "LOCAL=%USERPROFILE%\Downloads\yt-dlp"
set "GTEMP=%LOCAL%\_gallery_temp"

REM === 자막 설정 (v4.9) ===
REM   SUBLANG    : 받을 자막 언어. "en,ko" / "en" / "ko" / "all" 등. -로 제외 가능("all,-live_chat")
REM   MAKE_SUBTXT: 1=srt를 타임코드 제거한 txt로도 변환, 0=srt만 유지
set "SUBLANG=en,ko"
set "MAKE_SUBTXT=1"

REM === OneDriveCommercial 환경변수 체크 (v4.8) ===
if "%OneDriveCommercial%"=="" (
    echo [오류] OneDriveCommercial 환경변수 없음.
    echo        OneDrive 회사/학교 계정 동기화 상태 확인.
    pause
    goto end
)

REM === yt-dlp 체크 ===
if not exist "%YTDLP%\yt-dlp.exe" (
    echo [오류] yt-dlp.exe 없음. OneDrive 동기화 확인.
    pause
    goto end
)

REM === yt-dlp 버전 표시 (v6.2) - 화질 문제의 흔한 원인이 '구버전'이라 항상 보이게 ===
set "YTV="
for /f "usebackq delims=" %%v in (`"%YTDLP%\yt-dlp.exe" --version 2^>nul`) do set "YTV=%%v"
if defined YTV echo [확인] yt-dlp 버전: !YTV!
if not defined YTV echo [경고] yt-dlp 버전 확인 실패.

REM === ffmpeg 확보 (v6.5) = 저화질의 진범 ===
REM     yt-dlp는 고화질을 "영상 따로 + 음성 따로"로 받아 ffmpeg으로 합친다.
REM     ffmpeg이 없으면 그 조합(bv*+ba)을 아예 못 고르고 "이미 합쳐진 파일"로 떨어지는데,
REM     유튜브가 주는 합본은 format 18 = 640x360 하나뿐이다. 그래서 360p가 받아졌다.
REM     -^> 없으면 경고만 하고 넘어가지 않는다. 자동으로 받아 설치하고, 그래도 없으면 멈춘다.
set "FFOK=0"
if exist "%YTDLP%\ffmpeg.exe" set "FFOK=1"
if "!FFOK!"=="1" echo [확인] ffmpeg 있음 - 고화질 병합 가능
if "!FFOK!"=="0" (
    echo.
    echo [중요] ffmpeg.exe 가 없다. 이게 없으면 무조건 360p만 받아진다.
    echo [설치] 자동 다운로드 시작 ^(약 80MB · 1~3분 · 한 번만 하면 된다^)...
    powershell -noprofile -c "$ErrorActionPreference='Stop'; $t='%YTDLP%'; $u='https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'; $z=Join-Path $env:TEMP 'nmff.zip'; $x=Join-Path $env:TEMP 'nmffx'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri $u -OutFile $z -UseBasicParsing; if(Test-Path $x){Remove-Item $x -Recurse -Force}; Expand-Archive -Path $z -DestinationPath $x -Force; Get-ChildItem -Path $x -Recurse -Include ffmpeg.exe,ffprobe.exe | ForEach-Object { Copy-Item $_.FullName -Destination $t -Force }; Remove-Item $z -Force; Remove-Item $x -Recurse -Force; Write-Output '  [설치] ffmpeg 배치 완료'"
    if exist "%YTDLP%\ffmpeg.exe" set "FFOK=1"
)
if "!FFOK!"=="0" (
    echo.
    echo ===============================================
    echo   [중단] ffmpeg 을 못 구했다.
    echo   이 상태로 받으면 360p 만 나오므로 받지 않는다.
    echo.
    echo   해결 = 아래 둘 중 하나
    echo    1^) 인터넷/방화벽 확인 후 이 창을 다시 실행 ^(자동설치 재시도^)
    echo    2^) https://www.gyan.dev/ffmpeg/builds/ 에서 essentials 압축을 받아
    echo       bin 안의 ffmpeg.exe ffprobe.exe 를 아래 폴더에 복사
    echo       %YTDLP%
    echo ===============================================
    pause
    goto end
)

REM === JS 런타임(deno) 감지 (v6.2) ===
REM     쿠키를 쓰는 경로(연령제한 재시도·다른 플랫폼)에서 yt-dlp가 서명 해독에 JS 런타임을 요구한다.
REM     YT 기본 경로는 쿠키를 안 쓰므로(android_vr) deno가 없어도 최고화질에 지장 없다.
set "JSRT="
if exist "%YTDLP%\deno.exe" set "JSRT=--js-runtimes deno:"%YTDLP%\deno.exe""
if defined JSRT goto jsrt_done
where deno >nul 2>&1 && set "JSRT=--js-runtimes deno"
:jsrt_done
if defined JSRT echo [확인] JS 런타임: deno 감지
if not defined JSRT echo [알림] JS 런타임^(deno^) 없음 - YT 기본 경로는 무관. 연령제한 영상만 영향.

REM === gallery-dl 체크 ===
set "HAS_GDL=0"
if exist "%GDL%" set "HAS_GDL=1"
if "!HAS_GDL!"=="1" echo [확인] gallery-dl 사용 가능
if "!HAS_GDL!"=="0" echo [경고] gallery-dl.exe 없음. 이미지 다운로드 비활성화.

REM === 쿠키 파일 체크 ===
set "HAS_COOKIES=0"
if exist "%COOKIES%" set "HAS_COOKIES=1"
if "!HAS_COOKIES!"=="1" echo [확인] 쿠키 파일 있음 ^(IG/X 이미지 가능 · YT는 v6.2부터 미사용^)
if "!HAS_COOKIES!"=="0" echo [알림] 쿠키 파일 없음. IG/X 이미지는 쿠키 필요.

REM === 자막 설정 표시 (v4.9) ===
echo [확인] 자막 언어: !SUBLANG! / txt 변환: !MAKE_SUBTXT!

REM === 로컬 폴더 ===
if not exist "%LOCAL%" mkdir "%LOCAL%"

REM === 클라우드 사전 검증 ===
echo.
echo [검증] 클라우드 쓰기 테스트...
set "DUAL=0"
set "GD_WHY="
if "%GDFS_ON%"=="0" (
    echo [알림] 구글드라이브 앱이 실행 중이 아님 - 미설치/꺼짐/로그인 전
    echo        앱 켜고 로그인하면 클라우드 복사 활성화. 이번엔 로컬에만 저장
    set "GD_WHY=드라이브 앱 꺼짐/미로그인 - 시작메뉴에서 Google Drive 실행"
    goto cloud_done
)
REM v6.0: 드라이브 문자 자동 감지 - 계정 동일 전제, 마운트 문자(G:/I: 등)는 PC마다 달라도 됨
REM       1순위 = Google Drive 볼륨 라벨의 문자(앱이 어디 마운트했든 정확) · 2순위 = 문자 전수 스캔(C: 제외)
REM       각 단계 = Shared 이미 있는 마운트 우선(오탐 최소화) · 한/영 로케일(내 드라이브/My Drive) 모두 지원
REM       실존 폴더만 채택 = 유령 로컬 폴더 차단(v5.9.1 계승) · Shared 생성은 감지된 마운트 안에서만
set "GLET="
for /f "usebackq delims=" %%a in (`powershell -noprofile -c "foreach($d in [IO.DriveInfo]::GetDrives()){ try{ if($d.IsReady -and $d.VolumeLabel -like 'Google Drive*'){ $d.Name.Substring(0,1); break } }catch{} }"`) do set "GLET=%%a"
set "GROOT="
for %%d in (!GLET! G H I J K L M N O P Q R S T U V W X Y Z D E F) do if not defined GROOT if exist "%%d:\내 드라이브\Shared\" set "GROOT=%%d:\내 드라이브"
for %%d in (!GLET! G H I J K L M N O P Q R S T U V W X Y Z D E F) do if not defined GROOT if exist "%%d:\My Drive\Shared\" set "GROOT=%%d:\My Drive"
for %%d in (!GLET! G H I J K L M N O P Q R S T U V W X Y Z D E F) do if not defined GROOT if exist "%%d:\내 드라이브\" set "GROOT=%%d:\내 드라이브"
for %%d in (!GLET! G H I J K L M N O P Q R S T U V W X Y Z D E F) do if not defined GROOT if exist "%%d:\My Drive\" set "GROOT=%%d:\My Drive"
if not defined GROOT (
    echo [알림] 어느 드라이브에서도 '내 드라이브' 마운트를 못 찾음. 이번엔 로컬에만 저장
    set "GD_WHY=내 드라이브 마운트 미발견 - 드라이브 앱 설정에서 문자 마운트 확인"
    goto cloud_done
)
set "CLOUD=!GROOT!\Shared"
echo [확인] 클라우드(자동감지): !CLOUD!
set "GD_WHY=Shared 폴더 생성/쓰기 실패"
if not exist "%CLOUD%" mkdir "%CLOUD%" 2>nul
if not exist "%CLOUD%" goto cloud_done
echo test_%RANDOM% > "%CLOUD%\_write_test.tmp" 2>nul
if not exist "%CLOUD%\_write_test.tmp" goto cloud_done
del "%CLOUD%\_write_test.tmp" >nul 2>&1
set "DUAL=1"
set "GD_WHY="
echo [확인] 클라우드 쓰기 가능
REM v5.9.2: 낙오자 재송 스위프 - 지난 실행에서 클라우드에 못 간 파일(앱 꺼짐·robocopy 실패) 자동 재송
REM         날짜 필터 = 파일명 TS 앞 8자리. mtime /MAXAGE 금지 - yt-dlp가 mtime을 영상 업로드일로 바꿔 최신 파일도 옛날로 보임
REM         동명·동크기·동시각 = robocopy 자동 스킵(이미 간 파일 재복사 0) · 자막 제목폴더 = 무 /S라 비대상 · PS 실패 시 = 스위프 건너뜀
set "SWEEP_PATS="
for /f "usebackq delims=" %%d in (`powershell -noprofile -c "foreach($i in 0..7){ (Get-Date).AddDays(-$i).ToString('yyyyMMdd')+'_*' }"`) do set "SWEEP_PATS=!SWEEP_PATS! %%d"
if defined SWEEP_PATS echo [스위프] 지난 7일 미전송분 재송 확인...
if defined SWEEP_PATS robocopy "%LOCAL%" "%CLOUD%" !SWEEP_PATS! /R:2 /W:2 /NJH /NJS /NDL /NC /NS /NP

:cloud_done
echo [확인] 로컬: %LOCAL%
if "!DUAL!"=="1" echo [확인] 클라우드: %CLOUD%
cd /d "%LOCAL%"

:loop
echo.
echo -----------------------------------------------
REM === v5.2: 인자/클립보드로 URL 받았으면 그걸 첫 입력으로, 아니면 직접 입력 ===
if defined ARGURL (
    set "URL=!ARGURL!"
    set "ARGURL="
    echo [자동] !ARGSRC! 첫 URL 사용 ^(이후 계속 입력 가능^)
    goto url_have
)
REM === v5.5: 단일키 게이트 - ESC 2번=창닫기 / Q=종료 / 그 외 아무 키=URL 입력 ===
REM     powershell 실행 실패 시(errorlevel 9009 등) 그냥 URL 입력으로 진행됨 = 안전
echo [아무 키 = URL 입력 / Q = 종료 / ESC 2번 = 창 닫기]
powershell -noprofile -c "$e=0;while($true){$k=[Console]::ReadKey($true);if($k.Key -eq 'Escape'){$e=$e+1;if($e -ge 2){exit 27}}elseif($k.KeyChar -eq 'q' -or $k.KeyChar -eq 'Q'){exit 113}else{exit 0}}"
if !errorlevel! equ 27 goto esc_exit
if !errorlevel! equ 113 goto end
set "URL="
set /p URL=URL 붙여넣기 ^(q=종료^):

:url_have
if /i "!URL!"=="q" goto end
if "!URL!"=="" goto loop

REM ===================================================
REM  URL 자동 정제 v4.7+
REM  - 앞에 붙은 쓰레기 텍스트 제거
REM  - ttps:// ttp:// -^> https:// http:// 보정
REM  - 유효성 검증
REM ===================================================

REM --- 원본 백업 (PowerShell 실패 대비) ---
set "URL_BACKUP=!URL!"

REM --- 쓰레기 제거 + scheme 보정 (PowerShell 한 줄) ---
for /f "usebackq delims=" %%a in (`powershell -noprofile -c "$u='!URL!'; foreach($p in 'https://','http://','ttps://','ttp://'){$i=$u.IndexOf($p); if($i -ge 0){$u=$u.Substring($i); break}}; if($u.StartsWith('ttps://')){$u='h'+$u}elseif($u.StartsWith('ttp://')){$u='h'+$u}; Write-Output $u.Trim()"`) do set "URL=%%a"

REM --- PowerShell 실패 시 원본 복원 ---
if "!URL!"=="" set "URL=!URL_BACKUP!"

REM --- ttps/ttp 이중 안전장치 (PowerShell 우회 시 대비) ---
if /i "!URL:~0,7!"=="ttps://" set "URL=h!URL!"
if /i "!URL:~0,6!"=="ttp://" set "URL=h!URL!"

REM --- 유효성 검증 ---
set "URL_VALID=0"
if /i "!URL:~0,8!"=="https://" set "URL_VALID=1"
if /i "!URL:~0,7!"=="http://" set "URL_VALID=1"
if "!URL_VALID!"=="0" (
    echo.
    echo [오류] 유효한 URL이 아님: !URL!
    echo        https:// 로 시작하는 URL을 붙여넣어줘.
    echo.
    goto loop
)

REM --- 정제 완료 ---
echo [URL] !URL!

REM ===================================================

REM 플랫폼 감지
set "PLAT=ETC"
echo "!URL!" | find /i "youtube.com" >nul && set "PLAT=YT"
echo "!URL!" | find /i "youtu.be" >nul && set "PLAT=YT"
echo "!URL!" | find /i "instagram.com" >nul && set "PLAT=IG"
echo "!URL!" | find /i "x.com" >nul && set "PLAT=X"
echo "!URL!" | find /i "twitter.com" >nul && set "PLAT=X"
echo "!URL!" | find /i "tiktok.com" >nul && set "PLAT=TT"
echo "!URL!" | find /i "facebook.com" >nul && set "PLAT=FB"
echo "!URL!" | find /i "fb.watch" >nul && set "PLAT=FB"
echo "!URL!" | find /i "threads.net" >nul && set "PLAT=TH"
echo "!URL!" | find /i "threads.com" >nul && set "PLAT=TH"

for /f %%i in ('powershell -noprofile -c "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set "TS=%%i"
echo [감지] 플랫폼: !PLAT! / 시각: !TS!

REM === 다운로드 범위 고정 (v6.4) : 링크가 가리키는 것만 받는다 ===
REM     watch?v=..^&list=.. = 영상 링크에 재생목록이 얹힌 것 -^> 그 영상 1개만(--no-playlist)
REM     /playlist?list=..  = 재생목록 그 자체 -^> 재생목록 전체(--yes-playlist)
REM     채널·계정 URL엔 --no-playlist가 영향을 주지 않는다(비디오+목록 겸용 URL에만 작용).
set "PLOPT=--no-playlist"
set "PLSCOPE=이 영상 1개"
echo "!URL!" | find /i "/playlist" >nul && set "PLOPT=--yes-playlist" && set "PLSCOPE=이 재생목록 전체"
echo [범위] !PLSCOPE! 만 다운로드

REM === Threads 안내 (v4.8) ===
if "!PLAT!"=="TH" (
    echo [안내] Threads는 yt-dlp/gallery-dl 공식 지원이 불안정합니다.
    echo        다운로드 실패 가능성이 높습니다. 일단 시도합니다.
)

REM === 자막 안내 (v4.9) ===
if not "!PLAT!"=="YT" (
    echo [안내] 자막 추출은 YouTube에서 가장 안정적입니다.
    echo        IG/X/TT/FB/Threads는 자막 트랙이 드물어 .srt/.txt가 안 생길 수 있습니다.
)

REM === [1/2] yt-dlp 비디오 + 자막 시도 (v6.2: 최고화질 봉합) ===
echo.
echo [1/2] yt-dlp 비디오 + 자막 시도...

REM --- 쿠키 인자 (v6.1 통합 · v6.2에서 YT 분리) ---
REM     CK  = 원래 쿠키 인자(IG/X/TT/FB/TH용 · 거기선 쿠키가 있어야 받아진다)
REM     CKV = yt-dlp 비디오 경로에 실제로 넘길 인자. YT면 비운다(파일 머리말 v6.2 설명 참조).
set "CK="
if "!HAS_COOKIES!"=="1" set "CK=--cookies "%COOKIES%""
set "CKV=!CK!"
if "!PLAT!"=="YT" set "CKV="
if "!PLAT!"=="YT" if "!HAS_COOKIES!"=="1" echo [화질] YouTube = 쿠키 미사용으로 받는다 ^(쿠키를 붙이면 고화질 포맷이 조용히 누락됨^)

REM --- 화질 3축 선행조회(다운로드 없이 메타데이터만 · --print = quiet + simulate) ---
REM     [주의] 선행조회도 본편과 '같은 인자'(!CKV! !JSRT! !PLOPT!)를 써야 한다 - 인자가 다르면 보이는 포맷이 달라져 판단이 틀어진다.
REM     v6.4 = 축 3개. ① 해상도 = 기본정렬 · ② 프레임 = -S "fps,res,br" · ③ 짧은변 1080p.
REM     조회 셀렉터는 다운로드 셀렉터에서 오디오 병합만 뺀 같은 순서 = 같은 비디오 스트림이 잡힌다.
set "VW="
set "VH="
set "VFPS="
set "VFID="
set "VCOD="
set "FW="
set "FH="
set "FFPS="
set "FFID="
set "FCOD="
set "TW="
set "TH="
set "TFPS="
set "TFID="
set "TCOD="
REM --- 축① 해상도 = 기본 정렬 ---
for /f "usebackq tokens=1,2,3,4,5 delims= " %%a in (`"%YTDLP%\yt-dlp.exe" --no-warnings --no-cache-dir !CKV! !JSRT! !PLOPT! -f "bv*/b/best" --print "%%(width)s %%(height)s %%(fps)s %%(format_id)s %%(vcodec)s" --playlist-items 1 "!URL!" 2^>nul`) do (
    set "VW=%%a"
    set "VH=%%b"
    set "VFPS=%%c"
    set "VFID=%%d"
    set "VCOD=%%e"
)
REM --- 축② 프레임 = -S "fps,res,br"(fps 최우선 정렬) ---
for /f "usebackq tokens=1,2,3,4,5 delims= " %%a in (`"%YTDLP%\yt-dlp.exe" --no-warnings --no-cache-dir !CKV! !JSRT! !PLOPT! -f "bv*/b/best" -S "fps,res,br" --print "%%(width)s %%(height)s %%(fps)s %%(format_id)s %%(vcodec)s" --playlist-items 1 "!URL!" 2^>nul`) do (
    set "FW=%%a"
    set "FH=%%b"
    set "FFPS=%%c"
    set "FFID=%%d"
    set "FCOD=%%e"
)
REM --- 화질 영수증(v6.2): 뭘 최고화질로 판단했는지 항상 화면에 남긴다 = "안 받아졌다"를 눈으로 검증 ---
if defined VH echo [화질] 최고해상도 = !VW!x!VH! @!VFPS!fps / !VCOD! / format !VFID!
if defined FH echo [화질] 최고프레임 = !FW!x!FH! @!FFPS!fps / !FCOD! / format !FFID!
if not defined VH echo [화질] 조회 실패 - 그래도 최고화질로 진행. 계속 이상하면 yt-dlp 업데이트부터.
REM --- 축② 판정 : 해상도본과 format_id가 같으면 안 받는다(중복 0) ---
set "GETFPS=0"
if defined FFID if defined VFID if not "!FFID!"=="!VFID!" set "GETFPS=1"
if "!GETFPS!"=="1" echo [화질] 해상도축과 프레임축이 다름 - 프레임본도 받는다
if "!GETFPS!"=="0" if defined VH echo [화질] 해상도축 = 프레임축 - 프레임본 생략
REM --- 축③ 짧은변 1080p(v6.4) : 가로영상 = height^<=1080 / 세로영상 = width^<=1080 ---
REM     셀렉터를 변수에 담지 않고 가로/세로 리터럴로 나눠 쓴다 = for 백틱 재파싱 위험 제거.
set "DIMK="
echo !VH!| findstr /r "^[0-9][0-9]*$" >nul && echo !VW!| findstr /r "^[0-9][0-9]*$" >nul && set "DIMK=height"
if defined DIMK if !VW! lss !VH! set "DIMK=width"
REM     분기는 goto 라벨로 한다 = 이 파일이 이미 쓰는 방식(if + 여러 줄 for 블록보다 파싱이 단순).
if "!DIMK!"=="height" goto ax3_land
if "!DIMK!"=="width" goto ax3_port
goto ax3_done

:ax3_land
for /f "usebackq tokens=1,2,3,4,5 delims= " %%a in (`"%YTDLP%\yt-dlp.exe" --no-warnings --no-cache-dir !CKV! !JSRT! !PLOPT! -f "bv*[height<=1080][ext=mp4]/b[height<=1080][ext=mp4]/bv*[height<=1080]/b[height<=1080]" --print "%%(width)s %%(height)s %%(fps)s %%(format_id)s %%(vcodec)s" --playlist-items 1 "!URL!" 2^>nul`) do (
    set "TW=%%a"
    set "TH=%%b"
    set "TFPS=%%c"
    set "TFID=%%d"
    set "TCOD=%%e"
)
goto ax3_done

:ax3_port
for /f "usebackq tokens=1,2,3,4,5 delims= " %%a in (`"%YTDLP%\yt-dlp.exe" --no-warnings --no-cache-dir !CKV! !JSRT! !PLOPT! -f "bv*[width<=1080][ext=mp4]/b[width<=1080][ext=mp4]/bv*[width<=1080]/b[width<=1080]" --print "%%(width)s %%(height)s %%(fps)s %%(format_id)s %%(vcodec)s" --playlist-items 1 "!URL!" 2^>nul`) do (
    set "TW=%%a"
    set "TH=%%b"
    set "TFPS=%%c"
    set "TFID=%%d"
    set "TCOD=%%e"
)

:ax3_done
REM --- 축③ 판정 : 축①과 같으면 생략 · 축②를 실제로 받는 경우 그것과 같아도 생략 ---
set "GET1080=0"
if defined TFID if not "!TFID!"=="!VFID!" set "GET1080=1"
if "!GET1080!"=="1" if "!GETFPS!"=="1" if "!TFID!"=="!FFID!" set "GET1080=0"
if "!GET1080!"=="1" echo [화질] 1080p축 = !TW!x!TH! @!TFPS!fps / !TCOD! / format !TFID! - 호환본도 받는다
if "!GET1080!"=="0" if defined VH echo [화질] 1080p축이 위 축과 겹침 또는 1080p 없음 - 호환본 생략

REM --- 최고화질 본편 + 자막(항상 실행) ---
"%YTDLP%\yt-dlp.exe" --no-cache-dir --ffmpeg-location "%YTDLP%" !CKV! !JSRT! !PLOPT! --trim-filenames 120 --windows-filenames -P "%LOCAL%" -P "temp:%TEMP%" -o "!TS!_!PLAT!_%%(uploader_id)s_%%(title)s.%%(ext)s" -o "subtitle:%%(title)s/!TS!_!PLAT!_%%(uploader_id)s.%%(ext)s" --write-subs --write-auto-subs --sub-langs "!SUBLANG!" --convert-subs srt -f "bv*+ba[ext=m4a]/bv*+ba[ext=mp4]/bv*+ba/b/best" --merge-output-format mp4 -N 4 "!URL!"
set "YT_RC=!errorlevel!"

REM --- YT 쿠키 폴백(v6.2): 쿠키 없이 실패한 경우에만 쿠키를 붙여 1회 재시도(연령제한·멤버십·비공개) ---
if !YT_RC! neq 0 if "!PLAT!"=="YT" if "!HAS_COOKIES!"=="1" (
    echo [재시도] 쿠키 없이 실패 - 연령제한/멤버십 가능성. 쿠키 붙여 1회 재시도...
    echo          ^(이 경로는 화질이 낮게 잡힐 수 있다. deno 설치 시 개선^)
    "%YTDLP%\yt-dlp.exe" --no-cache-dir --ffmpeg-location "%YTDLP%" !CK! !JSRT! !PLOPT! --trim-filenames 120 --windows-filenames -P "%LOCAL%" -P "temp:%TEMP%" -o "!TS!_!PLAT!_%%(uploader_id)s_%%(title)s.%%(ext)s" -o "subtitle:%%(title)s/!TS!_!PLAT!_%%(uploader_id)s.%%(ext)s" --write-subs --write-auto-subs --sub-langs "!SUBLANG!" --convert-subs srt -f "bv*+ba[ext=m4a]/bv*+ba[ext=mp4]/bv*+ba/b/best" --merge-output-format mp4 -N 4 "!URL!"
    set "YT_RC=!errorlevel!"
)
if !YT_RC! neq 0 echo [yt-dlp] 비디오 못 받음. 이미지 게시물일 가능성.

REM --- 최고프레임본(v6.3) : 해상도본과 format_id가 다를 때만 · 자막 재다운로드 안 함 ---
REM     표식 maxfps_ 는 앞쪽 = --trim-filenames 120이 뒤(제목)를 자르므로 안 잘림 -^> 본편과 충돌 없음.
if "!GETFPS!"=="1" (
    echo.
    echo [프레임] 최고프레임본 !FW!x!FH! @!FFPS!fps 다운로드...
    "%YTDLP%\yt-dlp.exe" --no-cache-dir --ffmpeg-location "%YTDLP%" !CKV! !JSRT! !PLOPT! --trim-filenames 120 --windows-filenames -P "%LOCAL%" -P "temp:%TEMP%" -o "!TS!_!PLAT!_maxfps_%%(uploader_id)s_%%(title)s.%%(ext)s" --no-write-subs --no-write-auto-subs -S "fps,res,br" -f "bv*+ba[ext=m4a]/bv*+ba[ext=mp4]/bv*+ba/b/best" --merge-output-format mp4 -N 4 "!URL!"
    if errorlevel 1 echo [프레임] 최고프레임본 다운로드 실패 ^(해상도본은 정상^)
)

REM --- 짧은변 1080p 호환본(축③ · 위 축과 겹치지 않을 때만 · 자막 재다운로드 안 함) ---
REM     파일명 표식 '1080p_'을 앞쪽에 둠 = --trim-filenames 120은 뒤(제목)를 자르므로 앞표식은 안 잘림 -^> 본편과 충돌 없음.
REM     포맷 = 1080 이하 mp4 우선(h264 mp4 = 어디서나 재생) -^> 없으면 1080 이하 최선.
if "!GET1080!"=="1" (
    echo.
    echo [1080p] 호환용 1080p mp4 동반본 다운로드... 기준=!DIMK!
    if "!DIMK!"=="width" "%YTDLP%\yt-dlp.exe" --no-cache-dir --ffmpeg-location "%YTDLP%" !CKV! !JSRT! !PLOPT! --trim-filenames 120 --windows-filenames -P "%LOCAL%" -P "temp:%TEMP%" -o "!TS!_!PLAT!_1080p_%%(uploader_id)s_%%(title)s.%%(ext)s" --no-write-subs --no-write-auto-subs -f "bv*[width<=1080][ext=mp4]+ba[ext=m4a]/b[width<=1080][ext=mp4]/bv*[width<=1080]+ba[ext=m4a]/bv*[width<=1080]+ba/b[width<=1080]" --merge-output-format mp4 -N 4 "!URL!"
    if not "!DIMK!"=="width" "%YTDLP%\yt-dlp.exe" --no-cache-dir --ffmpeg-location "%YTDLP%" !CKV! !JSRT! !PLOPT! --trim-filenames 120 --windows-filenames -P "%LOCAL%" -P "temp:%TEMP%" -o "!TS!_!PLAT!_1080p_%%(uploader_id)s_%%(title)s.%%(ext)s" --no-write-subs --no-write-auto-subs -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 -N 4 "!URL!"
    if errorlevel 1 echo [1080p] 동반본 다운로드 실패 ^(본편은 정상^)
)

REM === 자막 후처리 (v4.9 txt 변환 + v5.7 Shared 바닥 평평 복사) ===
REM     폰 파이프라인은 Shared 바닥만 훑으므로 자막을 '시각_플랫폼_업로더_제목.언어.확장자'로 바닥에 복사(로컬은 제목 폴더 유지)
echo.
echo [자막] 후처리: txt 변환=!MAKE_SUBTXT! / Shared 평평 복사=!DUAL!...
powershell -noprofile -c "$mk='%MAKE_SUBTXT%'; $dual='!DUAL!'; $cloud='%CLOUD%'; $root='%LOCAL%'; Get-ChildItem -LiteralPath $root -Filter '!TS!_!PLAT!_*.srt' -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $t = $_.FullName -replace '\.srt$','.txt'; if($mk -eq '1'){ $ls = Get-Content -LiteralPath $_.FullName -Encoding UTF8 | Where-Object { $_ -notmatch '^\d+$' -and $_ -notmatch '-->' -and $_.Trim() -ne '' } | ForEach-Object { ($_ -replace '<[^>]+>','').Trim() }; $o = New-Object System.Collections.ArrayList; foreach($l in $ls){ if($o.Count -eq 0 -or $o[$o.Count-1] -ne $l){ [void]$o.Add($l) } }; if($o.Count -gt 0){ Set-Content -LiteralPath $t -Value $o -Encoding UTF8; Write-Output ('  [txt] ' + (Split-Path $t -Leaf)) } }; if($dual -eq '1'){ $fn=$_.Name; if($_.DirectoryName -ine $root){ $i=$fn.IndexOf('.'); $fn=$fn.Substring(0,$i)+'_'+$_.Directory.Name+$fn.Substring($i) }; Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $cloud $fn) -Force -ErrorAction SilentlyContinue; if(Test-Path -LiteralPath $t){ Copy-Item -LiteralPath $t -Destination (Join-Path $cloud ($fn -replace '\.srt$','.txt')) -Force -ErrorAction SilentlyContinue }; Write-Output ('  [Shared 자막] ' + $fn) } }"

REM === [2/2] gallery-dl 이미지 시도 ===
echo.
if "!PLAT!"=="YT" goto skip_gallery
if "!HAS_GDL!"=="0" goto skip_gallery_nogdl
goto do_gallery

:skip_gallery
echo [2/2] YouTube - 이미지 없음, 스킵
goto post_download

:skip_gallery_nogdl
echo [2/2] gallery-dl 미설치 - 스킵
goto post_download

:do_gallery
echo [2/2] gallery-dl 이미지 시도...
if exist "%GTEMP%" rmdir /s /q "%GTEMP%" 2>nul
mkdir "%GTEMP%" 2>nul

REM 쿠키 파일 있으면 사용, 없으면 쿠키 없이 시도
if "!HAS_COOKIES!"=="1" goto gdl_with_cookies
goto gdl_without_cookies

:gdl_with_cookies
"%GDL%" -D "%GTEMP%" --filter "extension not in ('mp4','m4v','webm','mov','m3u8','mp3','m4a','ts','aac','ogg')" --cookies "%COOKIES%" "!URL!"
set "GDL_RC=!errorlevel!"
goto gdl_done

:gdl_without_cookies
"%GDL%" -D "%GTEMP%" --filter "extension not in ('mp4','m4v','webm','mov','m3u8','mp3','m4a','ts','aac','ogg')" "!URL!"
set "GDL_RC=!errorlevel!"

:gdl_done
set /a GDL_CNT=0
for /r "%GTEMP%" %%f in (*) do (
    move /Y "%%f" "%LOCAL%\!TS!_!PLAT!_gallery_%%~nxf" >nul 2>&1
    if not errorlevel 1 set /a GDL_CNT+=1
)
rmdir /s /q "%GTEMP%" 2>nul
if !GDL_CNT! gtr 0 goto gallery_ok
if !GDL_RC! neq 0 goto gallery_fail
echo [gallery-dl] 받은 이미지 없음
goto post_download

:gallery_ok
echo [gallery-dl] !GDL_CNT!개 이미지 받음
goto post_download

:gallery_fail
echo [gallery-dl] 실패 (errorlevel=!GDL_RC!)
if "!HAS_COOKIES!"=="0" echo      쿠키 파일 없음. 확장프로그램으로 export 필요.
if "!HAS_COOKIES!"=="1" echo      쿠키 만료 가능성. 재export 필요.
goto post_download

:post_download
REM === 클라우드 복사 ===
echo.
if "!DUAL!"=="0" goto copy_skip
echo [복사] robocopy 동기화...
REM v5.7: /S 제거 = Shared는 바닥 평평 유지(자막은 자막 후처리가 제목 포함 이름으로 이미 바닥 복사)
robocopy "%LOCAL%" "%CLOUD%" "!TS!_!PLAT!_*.*" /R:5 /W:2 /NJH /NJS /NDL /NC /NS /NP /MT:4
set "RC_CODE=!errorlevel!"
if !RC_CODE! geq 8 goto copy_fail
if !RC_CODE! geq 1 goto copy_ok
echo [복사] 새 파일 없음
goto copy_done

:copy_ok
echo [복사] 완료 (rc=!RC_CODE!)
goto copy_done

:copy_fail
echo [복사 실패] robocopy errorlevel=!RC_CODE!
echo      로컬 파일은 안전: %LOCAL%
set "GD_WHY=robocopy 오류 rc=!RC_CODE!"
goto copy_done

:copy_skip
echo [복사] 클라우드 비활성화 - 로컬만 저장

:copy_done
set /a GD_CNT=0
if "!DUAL!"=="1" for /f %%c in ('dir /b "%CLOUD%\!TS!_!PLAT!_*" 2^>nul ^| find /c /v ""') do set "GD_CNT=%%c"
echo.
echo ===============================================
echo   다운로드 완료
if defined VH echo   해상도본: !VW!x!VH! @!VFPS!fps ^(!VCOD!^)
if "!GETFPS!"=="1" echo   프레임본: !FW!x!FH! @!FFPS!fps ^(!FCOD!^) - maxfps_ 파일
if "!GET1080!"=="1" echo   1080p본 : !TW!x!TH! @!TFPS!fps ^(!TCOD!^) - 1080p_ 파일
echo   로컬:    %LOCAL%
if "!DUAL!"=="1" if not defined GD_WHY echo   GDRIVE : 전송 완료 !GD_CNT!개 - %CLOUD%
if "!DUAL!"=="1" if defined GD_WHY echo   GDRIVE : 전송 이상 - 도착 !GD_CNT!개 / !GD_WHY!
if "!DUAL!"=="0" echo   GDRIVE : 미전송 - !GD_WHY!
echo ===============================================
echo.
goto loop

:esc_exit
echo.
echo [ESC 2번] 창을 닫습니다.
endlocal
exit

:end
echo.
echo 종료합니다.
endlocal
pause
exit /b
