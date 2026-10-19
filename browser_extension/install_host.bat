@echo off
setlocal
echo ========================================================
echo Installing Aegis Native Messaging Host for Chrome & Edge
echo ========================================================

set SCRIPT_DIR=%~dp0
set MANIFEST_PATH=%SCRIPT_DIR%com.aegis.downloadmanager.json
set EDGE_MANIFEST_PATH=%SCRIPT_DIR%com.aegis.downloadmanager.edge.json

if exist "%SCRIPT_DIR%aegis_host.exe" (
    set HOST_TARGET=%SCRIPT_DIR%aegis_host.exe
) else (
    set HOST_TARGET=%SCRIPT_DIR%aegis_host.bat
)

:: Replace backslashes with escaped backslashes for JSON
set ESCAPED_TARGET=%HOST_TARGET:\=\\%

:: Write Chrome/Chromium manifest (Chrome strictly enforces chrome-extension:// origins)
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

:: Write Edge manifest
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

echo Registering for Google Chrome...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul
reg add "HKCU\Software\Wow6432Node\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul

echo Registering for Brave Browser...
reg add "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul
reg add "HKCU\Software\Wow6432Node\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul

echo Registering for Microsoft Edge...
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%EDGE_MANIFEST_PATH%" /f >nul
reg add "HKCU\Software\Wow6432Node\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%EDGE_MANIFEST_PATH%" /f >nul

echo.
echo ========================================================
echo Installation complete! 
echo Native messaging host registered successfully.
echo To install the extension:
echo 1. Open chrome://extensions or edge://extensions
echo 2. Enable 'Developer Mode'
echo 3. Click 'Load unpacked' and select this 'browser_extension' folder.
echo ========================================================
pause
