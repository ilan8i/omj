@echo off
cd /d "%~dp0"
if not exist "toolkit\python.exe" (
  echo [OMJ] toolkit\python.exe not found. Run omj-install.bat first.
  pause
  exit /b 1
)
if exist "toolkit\.omj_runtime" (
  set "PYTHONPATH=%~dp0"
) else (
  set "PYTHONHOME=%~dp0toolkit"
  set "PYTHONPATH=%~dp0toolkit\python310.zip;%~dp0toolkit;%~dp0toolkit\Lib\site-packages;%~dp0"
)
set "PATH=%~dp0toolkit\Git\mingw64\bin;%PATH%"
set "PADDLE_PDX_CACHE_HOME=%~dp0models"
set "HF_HOME=%~dp0models\huggingface"
set "MODELSCOPE_CACHE=%~dp0models\modelscope"
"toolkit\python.exe" server.py
pause
