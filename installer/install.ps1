#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$DistroName = '',
    [switch]$SkipSourceVerification
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleaseRoot = Split-Path -Parent $Here
$CoreInstaller = Join-Path $ReleaseRoot 'LatticeVale-Core\Install-LatticeVale.ps1'
$Manifest = Join-Path $Here 'SOURCE-SHA256SUMS.txt'
$VersionFile = Join-Path $ReleaseRoot 'LatticeVale-Core\VERSION.txt'
$Verifier = Join-Path $ReleaseRoot 'tools\ReleaseManifest.ps1'

if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) { throw "Release verifier module not found: $Verifier" }
. $Verifier
if (-not (Test-Path -LiteralPath $CoreInstaller -PathType Leaf)) { throw "Core installer not found: $CoreInstaller" }
if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) { throw "Version file not found: $VersionFile" }
$ReleaseVersion = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
Write-Host "LatticeVale v$ReleaseVersion" -ForegroundColor Cyan
Write-Host "Core installer: $CoreInstaller"
Write-Host 'The installer source is plain text and can be inspected before execution.'

if (-not $SkipSourceVerification) {
    $checked = Test-LatticeValeSourceManifest -ReleaseRoot $ReleaseRoot -ManifestPath $Manifest
    Write-Host "Verified $checked release source/config files with exact manifest coverage." -ForegroundColor Green
} else { Write-Warning 'Source-manifest verification was explicitly skipped.' }

$invoke=@{}
if (-not [string]::IsNullOrWhiteSpace($DistroName)) { $invoke.DistroName=$DistroName }
& $CoreInstaller @invoke
if (-not $?) { exit 1 }
exit 0
