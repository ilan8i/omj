@echo off
cd /d "%~dp0"
if not exist "toolkit\python.exe" (
  echo [OMJ] toolkit\python.exe not found. Run omj-install.bat first.
  pause
  exit /b 1
)
"toolkit\python.exe" server.py
pause
