@echo off
REM nomute - Google Drive auto-move uninstaller (operator 260801)
setlocal
set "PS1=%~dp0drive_move_watch.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Uninstall
pause
