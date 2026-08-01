@echo off
REM nomute - Google Drive auto-move installer (operator 260801)
REM Double-click once. It copies the watcher to %LOCALAPPDATA%\nomute\,
REM drops nomute_drive_move.bat into the Startup folder, and starts watching now.
REM   watches : C:\Users\Hwang\Google Drive ...\Shared
REM   moves to: G:\...\Shared
REM Uninstall: run drive_move_watch_uninstall.cmd
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0drive_move_watch.ps1" -InstallStartup
echo.
echo Startup entry: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\nomute_drive_move.bat
echo Log file     : %LOCALAPPDATA%\nomute\drive_move.log
pause
