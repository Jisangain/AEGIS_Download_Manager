@echo off
setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set MANIFEST_PATH=%SCRIPT_DIR%com.aegis.downloadmanager.json
set EDGE_MANIFEST_PATH=%SCRIPT_DIR%com.aegis.downloadmanager.edge.json

:: Check if Python is available to run full 2-stage setup engine
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    if exist "%SCRIPT_DIR%setup_host.py" (
        python "%SCRIPT_DIR%setup_host.py"
        goto :END
    )
)

echo ========================================================
echo STAGE 1: Native Messaging Host Installation
echo ========================================================

:: 1. Verify Native Host Executable
if exist "%SCRIPT_DIR%aegis_host.exe" (
    set HOST_TARGET=%SCRIPT_DIR%aegis_host.exe
    echo [OK] Found native host executable: !HOST_TARGET!
) else if exist "%SCRIPT_DIR%aegis_host.bat" (
    set HOST_TARGET=%SCRIPT_DIR%aegis_host.bat
    echo [WARN] Native host executable missing; using batch launcher: !HOST_TARGET!
) else (
    echo [ERROR] Native host executable not found in %SCRIPT_DIR%!
    echo Stage 1 FAILED.
    goto :END
)

set ESCAPED_TARGET=%HOST_TARGET:\=\\%

:: 2. Write Chrome / Chromium Native Host Manifest
(
echo {
echo   "name": "com.aegis.downloadmanager",
echo   "description": "Aegis Download Manager Native Messaging Host",
echo   "path": "%ESCAPED_TARGET%",
echo   "type": "stdio",
echo   "allowed_origins": [
echo     "chrome-extension://olhghfhliadcobalbkamekmbdgcgmhee/",
echo     "chrome-extension://icdicciedmiojchchcagghmpkbenkccj/"
echo   ]
echo }
) > "%MANIFEST_PATH%"

if not exist "%MANIFEST_PATH%" (
    echo [ERROR] Failed to generate Chrome host manifest!
    goto :END
)
echo [OK] Generated Chrome manifest: %MANIFEST_PATH%

:: 3. Write Microsoft Edge Native Host Manifest
(
echo {
echo   "name": "com.aegis.downloadmanager",
echo   "description": "Aegis Download Manager Native Messaging Host",
echo   "path": "%ESCAPED_TARGET%",
echo   "type": "stdio",
echo   "allowed_origins": [
echo     "chrome-extension://olhghfhliadcobalbkamekmbdgcgmhee/",
echo     "chrome-extension://icdicciedmiojchchcagghmpkbenkccj/",
echo     "edge-extension://olhghfhliadcobalbkamekmbdgcgmhee/",
echo     "edge-extension://icdicciedmiojchchcagghmpkbenkccj/"
echo   ]
echo }
) > "%EDGE_MANIFEST_PATH%"

if not exist "%EDGE_MANIFEST_PATH%" (
    echo [ERROR] Failed to generate Edge host manifest!
    goto :END
)
echo [OK] Generated Edge manifest: %EDGE_MANIFEST_PATH%

:: 4. Register Registry Keys (64-bit and 32-bit WoW64)
echo.
echo Registering Native Messaging Host keys in HKCU:
set REG_FAIL=0

reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul || set REG_FAIL=1
reg add "HKCU\Software\Wow6432Node\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul || set REG_FAIL=1

reg add "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul || set REG_FAIL=1
reg add "HKCU\Software\Wow6432Node\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul || set REG_FAIL=1

reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%EDGE_MANIFEST_PATH%" /f >nul || set REG_FAIL=1
reg add "HKCU\Software\Wow6432Node\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%EDGE_MANIFEST_PATH%" /f >nul || set REG_FAIL=1

if %REG_FAIL% neq 0 (
    echo [ERROR] One or more registry operations failed.
    goto :END
)

:: 5. Verify Registry Keys
echo.
echo Verifying registry registration:
reg query "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /ve >nul 2>&1
if %ERRORLEVEL% equ 0 (echo   - Google Chrome: [VERIFIED]) else (echo   - Google Chrome: [FAILED])

reg query "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager" /ve >nul 2>&1
if %ERRORLEVEL% equ 0 (echo   - Brave Browser: [VERIFIED]) else (echo   - Brave Browser: [FAILED])

reg query "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /ve >nul 2>&1
if %ERRORLEVEL% equ 0 (echo   - Microsoft Edge: [VERIFIED]) else (echo   - Microsoft Edge: [FAILED])

echo.
echo ========================================================
echo STAGE 2: Browser Extension Status
echo ========================================================
echo.
echo Chromium security policies require unpacked extensions to be
echo loaded into your browser using Developer Mode.
echo.
echo Steps to complete browser extension integration:
echo   1. Open your browser's extensions manager:
echo      - Chrome: chrome://extensions
echo      - Brave:  brave://extensions
echo      - Edge:   edge://extensions
echo   2. Enable the 'Developer mode' toggle (top right).
echo   3. Click 'Load unpacked' and select this directory:
echo      "%SCRIPT_DIR%"
echo.
echo ========================================================
echo INSTALLATION SUMMARY
echo ========================================================
echo Native Host:       [INSTALLED ^& VERIFIED]
echo Browser Extension: [REQUIRES MANUAL LOADING VIA DEVELOPER MODE]
echo ========================================================

:END
pause
