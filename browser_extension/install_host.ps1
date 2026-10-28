$ErrorActionPreference = 'Stop'

$extensionDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$hostPath = Join-Path $extensionDir 'aegis_host.exe'
$hostName = 'com.aegis.downloadmanager'
$chromeManifestPath = Join-Path $extensionDir "$hostName.json"
$edgeManifestPath = Join-Path $extensionDir "$hostName.edge.json"

if (-not (Test-Path -LiteralPath $hostPath -PathType Leaf)) {
    throw "Native host executable is missing: $hostPath`nUse the Aegis Browser Extension ZIP release package. The GitHub source ZIP does not contain this executable."
}

Write-Host 'Load the Aegis extension in your browser first:' -ForegroundColor Cyan
Write-Host '  Chrome: chrome://extensions'
Write-Host '  Brave:  brave://extensions'
Write-Host '  Edge:   edge://extensions'
$extensionId = (Read-Host 'Copy and enter the extension ID shown on its card').Trim()
if ($extensionId -notmatch '^[a-p]{32}$') {
    throw 'Invalid extension ID. It must be exactly 32 letters from a through p.'
}

$extensionOrigin = "chrome-extension://$extensionId/"
$nativeManifest = [ordered]@{
    name = $hostName
    description = 'Aegis Download Manager Native Messaging Host'
    path = [IO.Path]::GetFullPath($hostPath)
    type = 'stdio'
    allowed_origins = @($extensionOrigin)
}
$json = $nativeManifest | ConvertTo-Json -Depth 4
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($chromeManifestPath, $json, $utf8NoBom)
[IO.File]::WriteAllText($edgeManifestPath, $json, $utf8NoBom)

$registrations = @(
    @{ Browser = 'Chrome'; Key = "Software\Google\Chrome\NativeMessagingHosts\$hostName"; Manifest = $chromeManifestPath },
    @{ Browser = 'Chrome (32-bit registry view)'; Key = "Software\Wow6432Node\Google\Chrome\NativeMessagingHosts\$hostName"; Manifest = $chromeManifestPath },
    @{ Browser = 'Brave'; Key = "Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\$hostName"; Manifest = $chromeManifestPath },
    @{ Browser = 'Brave (32-bit registry view)'; Key = "Software\Wow6432Node\BraveSoftware\Brave-Browser\NativeMessagingHosts\$hostName"; Manifest = $chromeManifestPath },
    @{ Browser = 'Edge'; Key = "Software\Microsoft\Edge\NativeMessagingHosts\$hostName"; Manifest = $edgeManifestPath },
    @{ Browser = 'Edge (32-bit registry view)'; Key = "Software\Wow6432Node\Microsoft\Edge\NativeMessagingHosts\$hostName"; Manifest = $edgeManifestPath }
)

$registry = [Microsoft.Win32.Registry]::CurrentUser
foreach ($registration in $registrations) {
    $key = $registry.CreateSubKey($registration.Key)
    if ($null -eq $key) {
        throw "Could not create the per-user registry key for $($registration.Browser)."
    }
    try {
        $key.SetValue('', $registration.Manifest, [Microsoft.Win32.RegistryValueKind]::String)
    } finally {
        $key.Dispose()
    }
}

foreach ($registration in $registrations) {
    $key = $registry.OpenSubKey($registration.Key)
    if ($null -eq $key) {
        throw "Could not verify the native host registration for $($registration.Browser)."
    }
    try {
        $registeredPath = $key.GetValue('')
        if ($registeredPath -ne $registration.Manifest -or -not (Test-Path -LiteralPath $registeredPath -PathType Leaf)) {
            throw "Native host registration verification failed for $($registration.Browser)."
        }
    } finally {
        $key.Dispose()
    }
}

Write-Host "`nNative host registered for extension $extensionId." -ForegroundColor Green
Write-Host 'Restart the browser. The extension can now start Aegis when you send it a download.'
