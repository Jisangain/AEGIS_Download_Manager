@echo off
echo ========================================================
echo Building Aegis Download Manager Standalone Executable
echo ========================================================

where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing pyinstaller...
    pip install pyinstaller
)

if not exist "tools\qjs.exe" (
    echo Required YouTube JavaScript runtime is missing: tools\qjs.exe
    echo Place the supported QuickJS-NG Windows executable in tools\qjs.exe, then rebuild.
    pause
    exit /b 1
)

python -c "import yt_dlp_ejs" >nul 2>nul
if %errorlevel% neq 0 (
    echo Installing yt-dlp with its default YouTube challenge components...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Could not install the yt-dlp dependencies. Check the build environment's network access.
        pause
        exit /b 1
    )
)

echo Packaging application with PyInstaller...
pyinstaller --noconfirm --clean --noconsole --onefile ^
    --name "Aegis Download Manager" ^
    --icon "icon.ico" ^
    --add-data "database.py;." ^
    --add-data "engine.py;." ^
    --add-data "ui.py;." ^
    --add-data "ipc_server.py;." ^
    --add-data "icon.ico;." ^
    --add-data "icon.png;." ^
    --add-data "tools\qjs.exe;tools" ^
    --add-data "tools\QUICKJS-NG-LICENSE.txt;licenses" ^
    --hidden-import "PyQt6" ^
    --hidden-import "sqlite3" ^
    --collect-all "yt_dlp" ^
    --collect-all "yt_dlp_ejs" ^
    --copy-metadata "yt-dlp" ^
    --copy-metadata "yt-dlp-ejs" ^
    main.py

if %errorlevel% neq 0 (
    echo Application packaging failed.
    pause
    exit /b 1
)

echo.
echo Build finished! The executable is located in: dist\Aegis Download Manager.exe
echo Building the Python-free browser native messaging host...
pyinstaller --noconfirm --clean --onefile --name aegis_host ^
    --distpath "browser_extension" ^
    --workpath "build\native-host" ^
    --specpath "build\native-host" ^
    aegis_host.py
if %errorlevel% neq 0 (
    echo Native messaging host build failed.
    pause
    exit /b 1
)
echo Creating the browser extension release package...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0package_browser_extension.ps1"
if %errorlevel% neq 0 (
    echo Browser extension package creation failed.
    pause
    exit /b 1
)
echo Updating the website download copy...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_website_release.ps1"
if %errorlevel% neq 0 (
    echo Website download sync failed. Check the error above.
    pause
    exit /b 1
)
pause
