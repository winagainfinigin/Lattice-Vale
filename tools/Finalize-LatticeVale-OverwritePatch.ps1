#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter()][string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$rootFull = [IO.Path]::GetFullPath($Root)
$deleteList = Join-Path $rootFull 'installer\PATCH-DELETE.txt'
if (-not (Test-Path -LiteralPath $deleteList -PathType Leaf)) {
    throw "Patch deletion list not found: $deleteList"
}

$removed = 0
$missing = 0
Get-Content -LiteralPath $deleteList | ForEach-Object {
    $rel = $_.Trim()
    if (-not $rel -or $rel.StartsWith('#')) { return }
    if ([IO.Path]::IsPathRooted($rel) -or $rel -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "Unsafe PATCH-DELETE path: $rel"
    }
    $candidate = [IO.Path]::GetFullPath((Join-Path $rootFull ($rel -replace '/', [IO.Path]::DirectorySeparatorChar)))
    $prefix = $rootFull.TrimEnd([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) {
        throw "PATCH-DELETE path escapes repository root: $rel"
    }
    if (Test-Path -LiteralPath $candidate) {
        Remove-Item -LiteralPath $candidate -Force -Recurse
        Write-Host "REMOVED obsolete source path: $rel"
        $script:removed++
    } else {
        $script:missing++
    }
}
Write-Host "Overwrite-patch cleanup complete: removed=$removed already-absent=$missing"
