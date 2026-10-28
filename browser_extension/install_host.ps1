$ErrorActionPreference = 'Stop'

$extensionDir = [IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$hostPath = Join-Path $extensionDir 'aegis_host.exe'
$hostName = 'com.aegis.downloadmanager'
$chromeManifestPath = Join-Path $extensionDir "$hostName.json"
$edgeManifestPath = Join-Path $extensionDir "$hostName.edge.json"

if (-not (Test-Path -LiteralPath $hostPath -PathType Leaf)) {
    throw "Native host executable is missing: $hostPath`nUse the Aegis Browser Extension ZIP release asset, not the GitHub source ZIP."
}

function Get-LoadedAegisExtensionIds([string[]]$UserDataRoots) {
    $ids = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($userDataRoot in $UserDataRoots) {
        if (-not (Test-Path -LiteralPath $userDataRoot -PathType Container)) { continue }
        foreach ($profile in Get-ChildItem -LiteralPath $userDataRoot -Directory -ErrorAction SilentlyContinue) {
            foreach ($preferenceName in @('Secure Preferences', 'Preferences')) {
                $preferencesPath = Join-Path $profile.FullName $preferenceName
                if (-not (Test-Path -LiteralPath $preferencesPath -PathType Leaf)) { continue }
                try {
                    $preferences = Get-Content -LiteralPath $preferencesPath -Raw | ConvertFrom-Json
                    $settings = $preferences.extensions.settings
                    if ($null -eq $settings) { continue }
                    foreach ($entry in $settings.PSObject.Properties) {
                        $extension = $entry.Value
                        $loadedPath = [string]$extension.path
                        if ([string]::IsNullOrWhiteSpace($loadedPath)) { continue }
                        try { $loadedPath = [IO.Path]::GetFullPath($loadedPath) } catch { continue }
                        if ($loadedPath.Equals($extensionDir, [StringComparison]::OrdinalIgnoreCase) -and
                            $entry.Name -match '^[a-p]{32}$') {
                            [void]$ids.Add($entry.Name)
                        }
                    }
                } catch {
                    # A profile may be locked, incomplete, or use an unsupported preference format.
                }
            }
        }
    }
    return @($ids)
}

$localAppData = [Environment]::GetFolderPath('LocalApplicationData')
$chromeIds = Get-LoadedAegisExtensionIds @(
    (Join-Path $localAppData 'Google\Chrome\User Data'),
    (Join-Path $localAppData 'BraveSoftware\Brave-Browser\User Data')
)
$edgeIds = Get-LoadedAegisExtensionIds @(
    (Join-Path $localAppData 'Microsoft\Edge\User Data')
)

if ($chromeIds.Count -eq 0 -and $edgeIds.Count -eq 0) {
    Write-Host 'Aegis extension was not found in Chrome, Brave, or Edge.' -ForegroundColor Yellow
    Write-Host 'First extract this ZIP to a permanent folder, open the browser extensions page, enable Developer mode, and choose Load unpacked.'
    Write-Host "Select this exact folder: $extensionDir"
    Write-Host 'Then run install_host.bat again. You will not need to copy or type an extension ID.'
    exit 1
}

$nativeManifestBase = [ordered]@{
    name = $hostName
    description = 'Aegis Download Manager Native Messaging Host'
    path = [IO.Path]::GetFullPath($hostPath)
    type = 'stdio'
}
$registrations = @()

if ($chromeIds.Count -gt 0) {
    $chromeManifest = [ordered]@{}
    foreach ($key in $nativeManifestBase.Keys) { $chromeManifest[$key] = $nativeManifestBase[$key] }
    $chromeManifest.allowed_origins = @($chromeIds | ForEach-Object { "chrome-extension://$_/" })
    $chromeJson = $chromeManifest | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($chromeManifestPath, $chromeJson, [Text.UTF8Encoding]::new($false))
    foreach ($registration in @(
        @{ Browser = 'Chrome'; Key = "Software\Google\Chrome\NativeMessagingHosts\$hostName" },
        @{ Browser = 'Chrome (32-bit registry view)'; Key = "Software\Wow6432Node\Google\Chrome\NativeMessagingHosts\$hostName" },
        @{ Browser = 'Brave'; Key = "Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\$hostName" },
        @{ Browser = 'Brave (32-bit registry view)'; Key = "Software\Wow6432Node\BraveSoftware\Brave-Browser\NativeMessagingHosts\$hostName" }
    )) {
        $registrations += @{ Browser = $registration.Browser; Key = $registration.Key; Manifest = $chromeManifestPath }
    }
}

if ($edgeIds.Count -gt 0) {
    $edgeManifest = [ordered]@{}
    foreach ($key in $nativeManifestBase.Keys) { $edgeManifest[$key] = $nativeManifestBase[$key] }
    $edgeManifest.allowed_origins = @($edgeIds | ForEach-Object { "edge-extension://$_/" })
    $edgeJson = $edgeManifest | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($edgeManifestPath, $edgeJson, [Text.UTF8Encoding]::new($false))
    $registrations += @{ Browser = 'Microsoft Edge'; Key = "Software\Microsoft\Edge\NativeMessagingHosts\$hostName"; Manifest = $edgeManifestPath }
    $registrations += @{ Browser = 'Microsoft Edge (32-bit registry view)'; Key = "Software\Wow6432Node\Microsoft\Edge\NativeMessagingHosts\$hostName"; Manifest = $edgeManifestPath }
}

$registry = [Microsoft.Win32.Registry]::CurrentUser
foreach ($registration in $registrations) {
    $key = $registry.CreateSubKey($registration.Key)
    if ($null -eq $key) { throw "Could not register the native host for $($registration.Browser)." }
    try {
        $key.SetValue('', $registration.Manifest, [Microsoft.Win32.RegistryValueKind]::String)
    } finally {
        $key.Dispose()
    }
}

foreach ($registration in $registrations) {
    $key = $registry.OpenSubKey($registration.Key)
    if ($null -eq $key) { throw "Could not verify the native host registration for $($registration.Browser)." }
    try {
        $registeredPath = [string]$key.GetValue('')
        if (-not $registeredPath.Equals($registration.Manifest, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $registeredPath -PathType Leaf)) {
            throw "Native host registration verification failed for $($registration.Browser)."
        }
    } finally {
        $key.Dispose()
    }
}

Write-Host 'Aegis browser integration installed and verified:' -ForegroundColor Green
foreach ($registration in $registrations) { Write-Host "  $($registration.Browser)" }
Write-Host 'Restart the browser. The extension ID was detected automatically; no ID entry was needed.'
