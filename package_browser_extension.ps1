$ErrorActionPreference = 'Stop'

$repoRoot = $PSScriptRoot
$extensionDir = Join-Path $repoRoot 'browser_extension'
$outputDir = Join-Path $repoRoot 'dist'
$zipPath = Join-Path $outputDir 'Aegis-Browser-Extension.zip'

$requiredFiles = @(
    'manifest.json',
    'background.js',
    'content.js',
    'content.css',
    'popup.html',
    'popup.js',
    'aegis_host.exe',
    'install_host.bat',
    'install_host.ps1',
    'uninstall_host.bat',
    'INSTALL_WINDOWS.txt'
)

foreach ($name in $requiredFiles) {
    $path = Join-Path $extensionDir $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Cannot package extension: required file missing: $path"
    }
}

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Add-Type -AssemblyName System.IO.Compression
$stream = [IO.File]::Open($zipPath, [IO.FileMode]::CreateNew)
$archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($name in $requiredFiles) {
        $sourcePath = Join-Path $extensionDir $name
        $entry = $archive.CreateEntry($name, [System.IO.Compression.CompressionLevel]::Optimal)
        $input = [IO.File]::OpenRead($sourcePath)
        $entryStream = $entry.Open()
        try {
            $input.CopyTo($entryStream)
        } finally {
            $entryStream.Dispose()
            $input.Dispose()
        }
    }
} finally {
    $archive.Dispose()
    $stream.Dispose()
}

Write-Host "Created: $zipPath"
