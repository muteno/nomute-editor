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
set "ARGURL=%~1"

echo ===============================================
echo   만능 다운로더 v5.8
echo   YT/IG/X/TT/FB/Threads - 비디오 + 이미지 + 자막
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
REM === 클라우드 저장 = 고정 경로 (v5.9 · 운영자 260719 Q226) - 유저명만 %USERPROFILE%로 범용 ===
REM     자동 탐지 폐기 → 항상 %USERPROFILE%\Google Drive 스트리밍\내 드라이브\Shared 로 복사
REM     GDFS_ON(앱 실행 체크)은 유지: 앱 꺼짐 시 로컬만(죽은 잔재 폴더 생성 방지) · 다른 PC = 한글 UI·같은 스트리밍 마운트 가정
set "GDFS_ON=0"
tasklist /fi "imagename eq GoogleDriveFS.exe" 2>nul | find /i "GoogleDriveFS.exe" >nul && set "GDFS_ON=1"
REM 클라우드 = 고정 경로(유저명만 %USERPROFILE%로 범용 · 운영자 260719 Q226)
set "CLOUD=%USERPROFILE%\Google Drive 스트리밍\내 드라이브\Shared"
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

REM === ffmpeg 체크 (v4.8) ===
if not exist "%YTDLP%\ffmpeg.exe" (
    echo [경고] ffmpeg.exe 없음. 영상 병합^(mp4^) 및 자막 srt 변환이 실패할 수 있음.
)

REM === gallery-dl 체크 ===
set "HAS_GDL=0"
if exist "%GDL%" set "HAS_GDL=1"
if "!HAS_GDL!"=="1" echo [확인] gallery-dl 사용 가능
if "!HAS_GDL!"=="0" echo [경고] gallery-dl.exe 없음. 이미지 다운로드 비활성화.

REM === 쿠키 파일 체크 ===
set "HAS_COOKIES=0"
if exist "%COOKIES%" set "HAS_COOKIES=1"
if "!HAS_COOKIES!"=="1" echo [확인] 쿠키 파일 있음 (IG/X 이미지 가능)
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
echo [확인] 클라우드(고정): %CLOUD%
set "GD_WHY=Shared 폴더 생성/쓰기 실패"
if not exist "%CLOUD%" mkdir "%CLOUD%" 2>nul
if not exist "%CLOUD%" goto cloud_done
echo test_%RANDOM% > "%CLOUD%\_write_test.tmp" 2>nul
if not exist "%CLOUD%\_write_test.tmp" goto cloud_done
del "%CLOUD%\_write_test.tmp" >nul 2>&1
set "DUAL=1"
set "GD_WHY="
echo [확인] 클라우드 쓰기 가능

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

REM === [1/2] yt-dlp 비디오 + 자막 시도 ===
echo.
echo [1/2] yt-dlp 비디오 + 자막 시도...
if "!HAS_COOKIES!"=="1" (
    "%YTDLP%\yt-dlp.exe" --no-cache-dir --ffmpeg-location "%YTDLP%" --cookies "%COOKIES%" --trim-filenames 120 --windows-filenames -P "%LOCAL%" -P "temp:%TEMP%" -o "!TS!_!PLAT!_%%(uploader_id)s_%%(title)s.%%(ext)s" -o "subtitle:%%(title)s/!TS!_!PLAT!_%%(uploader_id)s.%%(ext)s" --write-subs --write-auto-subs --sub-langs "!SUBLANG!" --convert-subs srt -f "bv*+ba/b/best" --merge-output-format mp4 -N 4 "!URL!"
) else (
    "%YTDLP%\yt-dlp.exe" --no-cache-dir --ffmpeg-location "%YTDLP%" --trim-filenames 120 --windows-filenames -P "%LOCAL%" -P "temp:%TEMP%" -o "!TS!_!PLAT!_%%(uploader_id)s_%%(title)s.%%(ext)s" -o "subtitle:%%(title)s/!TS!_!PLAT!_%%(uploader_id)s.%%(ext)s" --write-subs --write-auto-subs --sub-langs "!SUBLANG!" --convert-subs srt -f "bv*+ba/b/best" --merge-output-format mp4 -N 4 "!URL!"
)
set "YT_RC=!errorlevel!"
if !YT_RC! neq 0 echo [yt-dlp] 비디오 못 받음. 이미지 게시물일 가능성.

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
echo   로컬:    %LOCAL%
if "!DUAL!"=="1" echo   GDRIVE : 전송 완료 !GD_CNT!개 - %CLOUD%
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
