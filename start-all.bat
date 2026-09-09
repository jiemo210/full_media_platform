@echo off
cd /d "%~dp0"
echo Starting Full Media Platform (backend 8012 + frontend 5174)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" start
echo.
pause
