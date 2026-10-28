param(
    [string]$WebsitePath = (Join-Path $PSScriptRoot 'Werbsite')
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'dist\Aegis Download Manager.exe'
$downloadDirectory = Join-Path $WebsitePath 'downloads'
$destination = Join-Path $downloadDirectory 'Aegis-Download-Manager.exe'
$metadataPath = Join-Path $downloadDirectory 'release.json'

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Packaged executable not found: $source. Build the app first."
}

New-Item -ItemType Directory -Path $downloadDirectory -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $destination -Force
$file = Get-Item -LiteralPath $destination
$size = if ($file.Length -ge 1GB) { '{0:N2} GB' -f ($file.Length / 1GB) } else { '{0:N0} MB' -f ($file.Length / 1MB) }
$metadata = [ordered]@{
    name = 'Aegis Download Manager'
    platform = 'Windows · 64-bit'
    size = $size
    file = 'Aegis-Download-Manager.exe'
    updated = $file.LastWriteTimeUtc.ToString('yyyy-MM-ddTHH:mm:ssZ')
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8
Write-Host "Website download updated: $destination ($size)"
