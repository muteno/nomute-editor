#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# build_threads_plugin_bundle.py — threads_plugin_update.ps1 을 '더블클릭 .bat' 하나로 묶는 생성기
#   (운영자 260804 — 「2번은 로컬을 바꾸라는 거임?」에 대한 [9-1] 납품)
#
# 왜 base64로 싣냐 = cmd 는 .bat 을 OEM 코드페이지(한국어 949)로 읽는다. 안내문·경로에 한글이 있으면
#   반드시 깨진다 — 260804 실사고: 한글을 그대로 실은 .bat 이 운영자 화면에서 줄 단위로 쪼개져
#   "'fined'은(는) 내부 또는 외부 명령이 아닙니다" 가 줄줄이 떴다(파싱 자체가 무너진다).
#   base64 는 A-Za-z0-9+/= 뿐이라 어떤 코드페이지에서도 바이트가 보존된다 → 복원 후 UTF-8 BOM 그대로.
#   정본 = scripts/build_drive_move_bundle.py 의 같은 수법(그건 260801부터 운영자 PC에서 실제로 돈다).
#
# 산출물 = scripts/노뮤트_스레드플러그인_갱신.bat  ← 기계산출물. 손편집 금지.
#   값을 바꾸려면 threads_plugin_update.ps1 을 고치고 이 스크립트를 다시 돌린다.
#
# 사용:  python3 scripts/build_threads_plugin_bundle.py          (생성)
#        python3 scripts/build_threads_plugin_bundle.py --check  (레포 산출물이 최신인지 · rc=1이면 낡음)
# ═══════════════════════════════════════════════════════════════════════════════
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "threads_plugin_update.ps1"
OUT = ROOT / "scripts" / "노뮤트_스레드플러그인_갱신.bat"

LINE = 76  # base64 한 줄 길이 — cmd 의 8191자 한 줄 한계에 한참 못 미치게 짧게 끊는다


def build() -> str:
    raw = SRC.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        sys.exit(f"FAIL: {SRC} 에 UTF-8 BOM 이 없다 — 한글 안내문이 깨진다. 먼저 BOM 을 붙여라.")
    b64 = base64.b64encode(raw).decode("ascii")
    chunks = [b64[i:i + LINE] for i in range(0, len(b64), LINE)]

    head = r"""@echo off
REM ===========================================================================
REM  nomute - Threads yt-dlp plugin updater : ONE-CLICK
REM
REM  Replaces nomute_threads.py used by Downloader.bat with the repo version,
REM  so that threads.com/share/<code> links can be downloaded.
REM  (all Korean text lives inside the embedded ps1, never in this file -
REM   cmd reads .bat in codepage 949 and would corrupt it)
REM
REM  Run this file whenever the plugin looks outdated. Nothing stays resident.
REM  The old plugin is kept next to the new one as *.bak
REM
REM  GENERATED FILE - do not edit by hand.
REM  Source of truth: scripts/threads_plugin_update.ps1
REM  Regenerate     : python3 scripts/build_threads_plugin_bundle.py
REM ===========================================================================
setlocal
set "NM=%LOCALAPPDATA%\nomute"
if not exist "%NM%" mkdir "%NM%"
set "B64=%NM%\_thplug.b64"
if exist "%B64%" del "%B64%"

echo [1/2] Unpacking updater...
"""

    body = ['>> "%B64%" echo ' + c for c in chunks]

    tail = r"""
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t=[IO.File]::ReadAllText($env:B64); [IO.File]::WriteAllBytes((Join-Path $env:NM 'threads_plugin_update.ps1'), [Convert]::FromBase64String(($t -replace '\s','')))"
if errorlevel 1 goto :fail
del "%B64%" >nul 2>&1

echo [2/2] Updating plugin...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%NM%\threads_plugin_update.ps1"
if errorlevel 1 goto :fail

echo.
pause
exit /b 0

:fail
echo.
echo   UPDATE FAILED - please send the lines above.
echo.
pause
exit /b 1
"""
    return head + "\n".join(body) + tail


def main() -> int:
    text = build().replace("\r\n", "\n").replace("\n", "\r\n")
    if not text.isascii():
        bad = sorted({c for c in text if not c.isascii()})
        sys.exit(f"FAIL: 산출 .bat 에 비-ASCII 문자가 남았다 {bad} — cp949 에서 깨진다.")
    if "--check" in sys.argv:
        cur = OUT.read_bytes().decode("ascii") if OUT.exists() else ""
        if cur != text:
            print(f"낡음: {OUT.name} 이 ps1 정본과 다르다 — python3 {Path(__file__).name} 로 재생성해라.")
            return 1
        print(f"최신: {OUT.name} = ps1 정본과 일치.")
        return 0
    OUT.write_bytes(text.encode("ascii"))
    print(f"생성: {OUT}  ({len(text)}자 · 전량 ASCII)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
