@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_server.ps1"
echo.
echo ===================================================
echo  [OK] RemoteCoder is running in background!
echo  Press any key to close this window.
echo ===================================================
echo.
pause
