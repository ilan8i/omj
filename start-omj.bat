@echo off
cd /d "%~dp0"
if not exist "toolkit\python.exe" (
  echo [OMJ] toolkit\python.exe not found. Run omj-install.bat first.
  pause
  exit /b 1
)
set "PADDLE_PDX_CACHE_HOME=%~dp0models"
set "HF_HOME=%~dp0models\huggingface"
set "MODELSCOPE_CACHE=%~dp0models\modelscope"
"toolkit\python.exe" server.py
pause
