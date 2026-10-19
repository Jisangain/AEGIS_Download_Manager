@echo off
echo ========================================================
echo Unregistering Aegis Native Messaging Host
echo ========================================================

reg delete "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /f >nul 2>&1
reg delete "HKCU\Software\Wow6432Node\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager" /f >nul 2>&1
reg delete "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager" /f >nul 2>&1
reg delete "HKCU\Software\Wow6432Node\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /f >nul 2>&1
reg delete "HKCU\Software\Wow6432Node\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager" /f >nul 2>&1

echo Native messaging host removed from Chrome and Edge.
pause
