@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0omj-install.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed. Press any key to exit.
  pause >nul
)
endlocal
