@echo off
setlocal
echo ========================================================
echo Installing Aegis Native Messaging Host for Chrome & Edge
echo ========================================================

set SCRIPT_DIR=%~dp0
set MANIFEST_PATH=%SCRIPT_DIR%com.aegis.downloadmanager.json
set HOST_BAT=%SCRIPT_DIR%aegis_host.bat

:: Replace backslashes with escaped backslashes for JSON
set ESCAPED_BAT=%HOST_BAT:\=\\%

:: Write resolved manifest with absolute path to bat
(
echo {
echo   "name": "com.aegis.downloadmanager",
echo   "description": "Aegis Download Manager Native Messaging Host",
echo   "path": "%ESCAPED_BAT%",
echo   "type": "stdio",
echo   "allowed_origins": [
echo     "chrome-extension://*/",
echo     "edge-extension://*/"
echo   ]
echo }
) > "%MANIFEST_PATH%"

echo Registering for Google Chrome...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul

echo Registering for Microsoft Edge...
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul

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
