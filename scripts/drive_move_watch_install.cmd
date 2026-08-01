@echo off
REM nomute - Google Drive auto-move installer (operator 260801)
REM Double-click this file once. It registers a logon task that watches
REM   C:\Users\Hwang\Google Drive ...\Shared  and moves new files to  G:\...\Shared
REM Uninstall: run  drive_move_watch_uninstall.cmd
setlocal
set "PS1=%~dp0drive_move_watch.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Install
echo.
echo Log file: %LOCALAPPDATA%\nomute\drive_move.log
pause
