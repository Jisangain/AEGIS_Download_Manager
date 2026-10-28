@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0" || goto :failed

set "AEGIS_ROOT=%~dp0"
set "SETUP_TMP=%TEMP%\AegisDownloadManager-Setup"
set "PYTHON_EXE="
set "VENV_DIR=.venv"

if not exist "%SETUP_TMP%" mkdir "%SETUP_TMP%"
if errorlevel 1 goto :failed

echo Checking for Python 3.10 or newer...
call :find_python
if errorlevel 1 call :install_python
if errorlevel 1 goto :failed

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if errorlevel 1 set "VENV_DIR=.venv-aegis"
)
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating the Aegis virtual environment...
    "%PYTHON_EXE%" -m venv "%VENV_DIR%"
    if errorlevel 1 goto :failed
)
set "PYTHON_EXE=%CD%\%VENV_DIR%\Scripts\python.exe"

if not exist "tools\ffmpeg.exe" goto :install_ffmpeg
"tools\ffmpeg.exe" -version >nul 2>&1
if errorlevel 1 goto :install_ffmpeg
echo FFmpeg is ready.
goto :install_requirements

:find_python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
    call :validate_python
    if not errorlevel 1 exit /b 0
    set "PYTHON_EXE="
)

where py.exe >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('powershell -NoProfile -Command "$p=Get-Command python.exe -ErrorAction SilentlyContinue ^| Where-Object { $_.Source -notmatch '\\WindowsApps\\' } ^| Select-Object -First 1 -ExpandProperty Source; if($p){$p}" 2^>nul') do set "PYTHON_EXE=%%P"
)

if defined PYTHON_EXE (
    call :validate_python
    if not errorlevel 1 exit /b 0
    set "PYTHON_EXE="
)
exit /b 1

:validate_python
if not defined PYTHON_EXE exit /b 1
"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
exit /b %errorlevel%

:install_python
echo Python 3.10+ was not found. Downloading the official Python 3.13.17 installer...
set "PYTHON_INSTALLER=%SETUP_TMP%\python-3.13.17-amd64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-amd64.exe' -OutFile '%PYTHON_INSTALLER%'; $h=(Get-FileHash -LiteralPath '%PYTHON_INSTALLER%' -Algorithm SHA256).Hash; if ($h -ne '5da012101ba2e17113a9a1cd901e9ce1441086f2b7ecb5de06ec94163899a190') { throw 'Python installer SHA-256 mismatch' } } catch { Write-Error $_; exit 1 }"
if errorlevel 1 exit /b 1

start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 TargetDir="%LOCALAPPDATA%\Programs\Python\Python313" PrependPath=0 Include_pip=1 Include_launcher=0 Include_test=0 Include_doc=0 Shortcuts=0
if errorlevel 1 exit /b 1
set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :validate_python
if errorlevel 1 exit /b 1
exit /b 0

:install_ffmpeg
echo FFmpeg was not found. Downloading the Windows essentials build for high-resolution video and audio merging...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; $tmp='%SETUP_TMP%'; $root=$env:AEGIS_ROOT; $zip=Join-Path $tmp 'ffmpeg-release-essentials.zip'; $hashFile=Join-Path $tmp 'ffmpeg-release-essentials.zip.sha256'; $extract=Join-Path $tmp 'ffmpeg-extracted'; try { Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256' -OutFile $hashFile; $expected=[regex]::Match((Get-Content -LiteralPath $hashFile -Raw),'[0-9a-fA-F]{64}').Value.ToUpperInvariant(); $actual=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToUpperInvariant(); if (-not $expected -or $actual -ne $expected) { throw 'FFmpeg archive SHA-256 check failed' }; Expand-Archive -LiteralPath $zip -DestinationPath $extract -Force; $ffmpeg=Get-ChildItem -LiteralPath $extract -Filter ffmpeg.exe -File -Recurse | Select-Object -First 1; if (-not $ffmpeg) { throw 'ffmpeg.exe was not found in the downloaded archive' }; $tools=Join-Path $root 'tools'; New-Item -ItemType Directory -Path $tools -Force | Out-Null; Copy-Item -LiteralPath $ffmpeg.FullName -Destination (Join-Path $tools 'ffmpeg.exe') -Force; & (Join-Path $tools 'ffmpeg.exe') -version | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'Downloaded ffmpeg.exe did not start' }; Remove-Item -LiteralPath $zip,$hashFile,$extract -Recurse -Force; Write-Host 'FFmpeg installed in the project tools folder.' } catch { Write-Error $_; exit 1 }"
if errorlevel 1 exit /b 1

:install_requirements
echo Installing Python packages from requirements.txt...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Setup complete. Launching Aegis with:
echo %PYTHON_EXE%
"%PYTHON_EXE%" main.py
if errorlevel 1 goto :failed
goto :done

:failed
echo.
echo Aegis setup or launch failed. Check the error above and confirm this PC has internet access.
pause
exit /b 1

:done
endlocal
