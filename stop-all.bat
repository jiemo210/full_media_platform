@echo off
cd /d "%~dp0"
echo Stopping Full Media Platform...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" stop
echo.
pause
