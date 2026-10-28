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
$programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
$chromeUserData = Join-Path $localAppData 'Google\Chrome\User Data'
$braveUserData = Join-Path $localAppData 'BraveSoftware\Brave-Browser\User Data'
$edgeUserData = Join-Path $localAppData 'Microsoft\Edge\User Data'
$chromeIds = Get-LoadedAegisExtensionIds @($chromeUserData, $braveUserData)
$edgeIds = Get-LoadedAegisExtensionIds @($edgeUserData)

if ($chromeIds.Count -eq 0 -and $edgeIds.Count -eq 0) {
    Write-Host 'Aegis browser setup' -ForegroundColor Cyan
    Write-Host '1. In the browser page that opens, turn on Developer mode.'
    Write-Host '2. Choose Load unpacked and select this folder:' -ForegroundColor Yellow
    Write-Host 'Keep this window open. The extension ID will be detected and registered automatically.'

    $browserChoices = @(
        @{ Name = 'Chrome'; UserData = $chromeUserData; Executable = (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'); Url = 'chrome://extensions' },
        @{ Name = 'Chrome'; UserData = $chromeUserData; Executable = (Join-Path $programFilesX86 'Google\Chrome\Application\chrome.exe'); Url = 'chrome://extensions' },
        @{ Name = 'Chrome'; UserData = $chromeUserData; Executable = (Join-Path $localAppData 'Google\Chrome\Application\chrome.exe'); Url = 'chrome://extensions' },
        @{ Name = 'Brave'; UserData = $braveUserData; Executable = (Join-Path $env:ProgramFiles 'BraveSoftware\Brave-Browser\Application\brave.exe'); Url = 'brave://extensions' },
        @{ Name = 'Brave'; UserData = $braveUserData; Executable = (Join-Path $programFilesX86 'BraveSoftware\Brave-Browser\Application\brave.exe'); Url = 'brave://extensions' },
        @{ Name = 'Edge'; UserData = $edgeUserData; Executable = (Join-Path $programFilesX86 'Microsoft\Edge\Application\msedge.exe'); Url = 'edge://extensions' },
        @{ Name = 'Edge'; UserData = $edgeUserData; Executable = (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'); Url = 'edge://extensions' }
    )
    $browser = $browserChoices | Where-Object { Test-Path -LiteralPath $_.Executable -PathType Leaf } | Select-Object -First 1
    if ($browser) {
        Write-Host "Opening $($browser.Name) extensions..."
        Start-Process -FilePath $browser.Executable -ArgumentList $browser.Url
    } else {
        Write-Host 'No supported browser executable was found. Open chrome://extensions, brave://extensions, or edge://extensions manually.' -ForegroundColor Yellow
    }

    $deadline = [DateTime]::UtcNow.AddMinutes(5)
    do {
        Start-Sleep -Seconds 2
        $chromeIds = Get-LoadedAegisExtensionIds @($chromeUserData, $braveUserData)
        $edgeIds = Get-LoadedAegisExtensionIds @($edgeUserData)
        if ($chromeIds.Count -gt 0 -or $edgeIds.Count -gt 0) { break }
        Write-Host 'Waiting for Aegis to be loaded...' -NoNewline
        Write-Host "`r" -NoNewline
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($chromeIds.Count -eq 0 -and $edgeIds.Count -eq 0) {
        throw 'Setup timed out before the Aegis extension was detected. Leave the extension page open and run install_host.bat again after loading this folder.'
    }
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
Write-Host 'After restarting, click the Aegis extension to see its automatic connection check.'
