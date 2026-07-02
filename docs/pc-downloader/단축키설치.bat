@echo off
chcp 949 >nul
setlocal

REM ===============================================
REM  NoMute 다운로더 단축키 설치기 (v5.2)
REM  - 더블클릭 한 번이면 끝. PC당 1회만 실행.
REM  - Ctrl+Shift+D 를 누르면 Downloader.bat이 바로 실행되게
REM    시작 메뉴에 바로가기(NoMute Downloader.lnk)를 등록한다.
REM  - 같은 단축키를 쓰던 옛 바로가기(구버전 ps1 방식 등)는 자동 해제.
REM  - 단축키를 바꾸려면 아래 HOTKEY 줄만 고치고 다시 더블클릭.
REM ===============================================
set "HOTKEY=Ctrl+Shift+D"
set "BATPATH=%OneDriveCommercial%\황세웅\6.  Nomute\창고\05. Utility\Downloader.bat"
set "LNKPATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\NoMute Downloader.lnk"

echo ===============================================
echo   NoMute 다운로더 단축키 설치 (%HOTKEY%)
echo ===============================================
echo.

REM === OneDrive 확인 ===
if "%OneDriveCommercial%"=="" (
    echo [오류] OneDriveCommercial 환경변수 없음.
    echo        OneDrive 회사/학교 계정 동기화 상태 확인.
    echo.
    pause
    exit /b 1
)

REM === 다운로더 본체 확인 ===
if not exist "%BATPATH%" (
    echo [오류] Downloader.bat 없음. 먼저 아래 위치에 넣어줘:
    echo        %BATPATH%
    echo.
    pause
    exit /b 1
)
echo [확인] 다운로더: %BATPATH%

REM === [1/2] 같은 단축키를 쓰는 기존 바로가기 해제 (충돌 방지) ===
echo [1/2] 기존 %HOTKEY% 바로가기 정리...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $dirs=@([Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('Desktop')); foreach($d in $dirs){ Get-ChildItem -LiteralPath $d -Filter *.lnk -Recurse -ErrorAction SilentlyContinue | ForEach-Object { try{ $s=$ws.CreateShortcut($_.FullName); if($s.Hotkey -and (($s.Hotkey -replace ' ','') -ieq ($env:HOTKEY -replace ' ',''))){ $s.Hotkey=''; $s.Save(); Write-Output ('  [OFF] ' + $_.FullName) } }catch{} } }"

REM === [2/2] 새 바로가기 등록 (시작 메뉴 = 단축키가 먹는 위치) ===
echo [2/2] 새 단축키 등록...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut($env:LNKPATH); $s.TargetPath=$env:BATPATH; $s.WorkingDirectory=(Split-Path $env:BATPATH); $s.Hotkey=$env:HOTKEY; $s.Description='NoMute downloader hotkey'; $s.Save(); Write-Output ('  [SET] ' + $env:LNKPATH)"

REM === 결과 검증 (바로가기 실존 확인) ===
if not exist "%LNKPATH%" (
    echo.
    echo [오류] 바로가기 생성 실패. 위 메시지 확인.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] 설치 완료.
echo      이제 URL 복사하고 %HOTKEY% 만 누르면
echo      다운로더가 뜨면서 그 URL부터 자동 다운로드된다.
echo.
echo      - 단축키가 바로 안 먹으면: 로그아웃 후 재로그인 한 번.
echo      - 옛 방식 흔적인 USERPROFILE\nomute 폴더는 이제 안 쓰니 지워도 됨.
echo.
pause
exit /b 0
