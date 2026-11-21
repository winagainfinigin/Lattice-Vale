#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$version = (Get-Content -LiteralPath (Join-Path $root 'LatticeVale-Core\VERSION.txt') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid release version: $version" }
$manifestPath = Join-Path $root 'installer\SOURCE-SHA256SUMS.txt'
$manifest = @()
foreach ($manifestLine in Get-Content -LiteralPath $manifestPath) {
    if ([string]::IsNullOrWhiteSpace($manifestLine) -or $manifestLine.TrimStart().StartsWith('#')) { continue }
    if ($manifestLine -notmatch '^([0-9a-fA-F]{64})  (.+)$') { throw "Malformed source manifest row: $manifestLine" }
    $manifest += $manifestLine
}
if ($manifest.Count -lt 1) { throw 'Source manifest is empty or malformed.' }

$out = [IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($out) | Out-Null
$work = Join-Path ([IO.Path]::GetTempPath()) ('LatticeVale-release-' + [guid]::NewGuid().ToString('N'))
$packageRoot = Join-Path $work 'Lattice-Vale'
$zipPath = Join-Path $out "LatticeVale-v$version-release.zip"
$hashPath = $zipPath + '.sha256'
$provenancePath = Join-Path $out "LatticeVale-v$version-release.provenance.json"

try {
    [IO.Directory]::CreateDirectory($packageRoot) | Out-Null
foreach ($line in $manifest) {
    if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') { throw "Malformed source manifest row: $line" }
    $expectedHash = $Matches[1]
    $manifestRelative = $Matches[2]
    $relative = $manifestRelative.Replace('/', [IO.Path]::DirectorySeparatorChar)
        if ([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)') { throw "Unsafe manifest path: $relative" }
        $source = [IO.Path]::GetFullPath((Join-Path $root $relative))
        $sourcePrefix = $root.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
        if (-not $source.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Manifest path escapes repository: $relative" }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Manifest source is missing: $relative" }
        $actual = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    if ($actual -ne $expectedHash) { throw "Manifest hash mismatch: $relative" }
        $target = Join-Path $packageRoot $relative
        [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target
    }
    Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $packageRoot 'installer\SOURCE-SHA256SUMS.txt')

    & (Join-Path $packageRoot 'installer\verify-release.ps1')

    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    [IO.Compression.ZipFile]::CreateFromDirectory($work, $zipPath, [IO.Compression.CompressionLevel]::Optimal, $false)
    $archive = [IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entries = @($archive.Entries | Where-Object { -not $_.FullName.EndsWith('/') })
        if ($entries.Count -ne ($manifest.Count + 1)) { throw "Unexpected package entry count: $($entries.Count)" }
        foreach ($entry in $entries) {
            if (-not $entry.FullName.StartsWith('Lattice-Vale/', [StringComparison]::Ordinal)) { throw "Unexpected archive root: $($entry.FullName)" }
            if ($entry.FullName -match '(^|/)\.git(/|$)|(^|/)__pycache__(/|$)|\.(pyc|pyo)$') { throw "Forbidden release artifact: $($entry.FullName)" }
        }
    } finally { $archive.Dispose() }

    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText($hashPath, "$hash  $(Split-Path -Leaf $zipPath)`n", [Text.UTF8Encoding]::new($false))
    $commit = (& git -C $root rev-parse HEAD 2>$null).Trim()
    if ($LASTEXITCODE -ne 0) { $commit = 'unavailable' }
    $provenance = [ordered]@{ version=$version; sourceCommit=$commit; archive=(Split-Path -Leaf $zipPath); sha256=$hash; createdUtc=[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ') }
    [IO.File]::WriteAllText($provenancePath, ($provenance | ConvertTo-Json -Depth 4) + "`n", [Text.UTF8Encoding]::new($false))
    Write-Output "Release archive: $zipPath"
    Write-Output "SHA-256: $hash"
    Write-Output "Source commit: $commit"
} finally {
    if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
}
