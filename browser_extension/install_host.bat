@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_host.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo Native messaging setup failed. Read the message above, correct it, and run this file again.
) else (
  echo Setup complete. Restart your browser and keep Aegis Download Manager running.
)
pause
exit /b %RESULT%
