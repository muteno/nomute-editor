@echo off
REM nomute - Google Drive auto-move uninstaller (operator 260801)
REM Removes the Startup entry and stops the running watcher.
REM Also unregisters the Scheduled Task variant if it was ever used.
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0drive_move_watch.ps1" -UninstallStartup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0drive_move_watch.ps1" -Uninstall
pause
