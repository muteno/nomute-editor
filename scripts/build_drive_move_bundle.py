#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# build_drive_move_bundle.py — drive_move_watch.ps1 을 '단일 설치 .bat' 하나로 묶는 생성기
#   (운영자 260801 "단일 bat파일 만들어서 주고, 한번 실행하면 신경 안 쓰게")
#
# 왜 base64로 싣냐 = cmd 는 .bat 파일을 OEM 코드페이지(한국어 949)로 읽는다. 감시기 본문에는
#   'C:\\...\\내 드라이브\\Shared' 같은 한글 경로가 들어 있어서 그대로 실으면 반드시 깨진다.
#   base64 는 A-Za-z0-9+/= 뿐이라 어떤 코드페이지에서도 바이트가 보존된다 → 복원 후 UTF-8 BOM 그대로.
#
# 산출물 = scripts/노뮤트_구글드라이브_자동이동_설치.bat  ← 기계산출물. 손편집 금지.
#   값을 바꾸려면 drive_move_watch.ps1 을 고치고 이 스크립트를 다시 돌린다.
#
# 사용:  python3 scripts/build_drive_move_bundle.py          (생성)
#        python3 scripts/build_drive_move_bundle.py --check  (레포 산출물이 최신인지 확인 · rc=1이면 낡음)
# ═══════════════════════════════════════════════════════════════════════════════
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "drive_move_watch.ps1"
OUT = ROOT / "scripts" / "노뮤트_구글드라이브_자동이동_설치.bat"

LINE = 76  # base64 한 줄 길이 — cmd 의 8191자 한 줄 한계에 한참 못 미치게 짧게 끊는다


def build() -> str:
    raw = SRC.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        sys.exit(f"FAIL: {SRC} 에 UTF-8 BOM 이 없다 — 한글 경로가 깨진다. 먼저 BOM 을 붙여라.")
    b64 = base64.b64encode(raw).decode("ascii")
    chunks = [b64[i:i + LINE] for i in range(0, len(b64), LINE)]

    head = r"""@echo off
REM ===========================================================================
REM  nomute - Google Drive auto-move : ONE-CLICK SETUP
REM
REM  Watches : C:\Users\Hwang\Google Drive (streaming)\My Drive\Shared
REM  Moves to: G:\My Drive\Shared
REM  (the real Korean paths live inside the embedded ps1, not in this file)
REM
REM  Run this file ONCE. It installs itself into the Startup folder and keeps
REM  running on every logon. To stop: delete
REM    %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\nomute_drive_move.bat
REM
REM  GENERATED FILE - do not edit by hand.
REM  Source of truth: scripts/drive_move_watch.ps1
REM  Regenerate     : python3 scripts/build_drive_move_bundle.py
REM ===========================================================================
setlocal
set "NM=%LOCALAPPDATA%\nomute"
if not exist "%NM%" mkdir "%NM%"
set "B64=%NM%\_setup.b64"
if exist "%B64%" del "%B64%"

echo [1/3] Unpacking watcher...
"""

    body = ['>> "%B64%" echo ' + c for c in chunks]

    tail = r"""
echo [2/3] Writing "%NM%\drive_move_watch.ps1" ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t=[IO.File]::ReadAllText($env:B64); [IO.File]::WriteAllBytes((Join-Path $env:NM 'drive_move_watch.ps1'), [Convert]::FromBase64String(($t -replace '\s','')))"
if errorlevel 1 goto :fail
del "%B64%" >nul 2>&1

echo [3/3] Registering startup entry and starting the watcher...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%NM%\drive_move_watch.ps1" -InstallStartup
if errorlevel 1 goto :fail

echo.
echo   DONE. It is running now, and will start again on every logon.
echo   Log: %NM%\drive_move.log
echo.
pause
exit /b 0

:fail
echo.
echo   SETUP FAILED - please send the red lines above.
echo.
pause
exit /b 1
"""
    return head + "\n".join(body) + tail


def main() -> int:
    text = build().replace("\r\n", "\n").replace("\n", "\r\n")
    data = text.encode("ascii")  # 비ASCII가 섞이면 여기서 터진다 = 코드페이지 사고 사전 차단

    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_bytes() != data:
            print(f"⚠️ 낡음 — {OUT.name} 재생성 필요: python3 scripts/build_drive_move_bundle.py")
            return 1
        print(f"✅ {OUT.name} = drive_move_watch.ps1 최신 반영")
        return 0

    OUT.write_bytes(data)
    print(f"✅ 생성 — {OUT.relative_to(ROOT)}  ({len(data):,} bytes · 원본 {SRC.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
