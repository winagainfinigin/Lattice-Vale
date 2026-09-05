#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Manifest = Join-Path $Root 'installer\SOURCE-SHA256SUMS.txt'

. (Join-Path $PSScriptRoot 'ReleaseManifest.ps1')
$allReleaseItems = @(Get-ChildItem -LiteralPath $Root -Force -Recurse | Where-Object {
    $_.FullName -ne $Manifest -and
    $_.FullName -notmatch '[\\/]\.git(?:[\\/]|$)'
})
foreach ($item in $allReleaseItems) {
    $relativeCheck = $item.FullName.Substring($Root.Length).TrimStart('\','/').Replace('\','/')
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing to manifest reparse-point release item: $relativeCheck" }
    Assert-LatticeValePortableReleaseRelativePath $relativeCheck
}

$files = @($allReleaseItems | Where-Object { -not $_.PSIsContainer } | Sort-Object { $_.FullName.Substring($Root.Length).Replace('\','/').ToLowerInvariant() })
$seen = @{}
foreach ($file in $files) {
    $relativeCheck = $file.FullName.Substring($Root.Length).TrimStart('\','/').Replace('\','/')
    $key = $relativeCheck.ToLowerInvariant()
    if ($seen.ContainsKey($key)) { throw "Case-colliding release paths are not portable to Windows: $relativeCheck" }
    $seen[$key] = $true
}

$lines = @(
    '# LatticeVale release file manifest (SHA-256)'
    '# Regenerate only after reviewing every intended release change.'
)
foreach ($file in $files) {
    $relative = $file.FullName.Substring($Root.Length).TrimStart('\','/').Replace('\','/')
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $lines += "$hash  $relative"
}
[IO.File]::WriteAllText($Manifest, (($lines -join "`n") + "`n"), [Text.Encoding]::ASCII)
Write-Host "Wrote $($files.Count) entries to $Manifest" -ForegroundColor Green
