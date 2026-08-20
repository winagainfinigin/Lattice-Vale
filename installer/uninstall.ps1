#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$DistroName = '',
    [string]$LinuxUser = '',
    [switch]$SkipSourceVerification
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleaseRoot = Split-Path -Parent $Here
$CoreUninstaller = Join-Path $ReleaseRoot 'LatticeVale-Core\Uninstall-LatticeVale.ps1'
$Manifest = Join-Path $Here 'SOURCE-SHA256SUMS.txt'
$VersionFile = Join-Path $ReleaseRoot 'LatticeVale-Core\VERSION.txt'
$Verifier = Join-Path $ReleaseRoot 'tools\ReleaseManifest.ps1'

if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) { throw "Release verifier module not found: $Verifier" }
. $Verifier
if (-not (Test-Path -LiteralPath $CoreUninstaller -PathType Leaf)) { throw "Core uninstaller not found: $CoreUninstaller" }
if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) { throw "Version file not found: $VersionFile" }
$ReleaseVersion = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
Write-Host "LatticeVale v$ReleaseVersion uninstaller" -ForegroundColor Cyan
Write-Host "Core uninstaller: $CoreUninstaller"
Write-Host 'The uninstaller source is plain text and can be inspected before execution.'

if (-not $SkipSourceVerification) {
    $checked = Test-LatticeValeSourceManifest -ReleaseRoot $ReleaseRoot -ManifestPath $Manifest
    Write-Host "Verified $checked release source/config files with exact manifest coverage." -ForegroundColor Green
} else { Write-Warning 'Source-manifest verification was explicitly skipped.' }

$invoke = @{}
if (-not [string]::IsNullOrWhiteSpace($DistroName)) { $invoke.DistroName = $DistroName }
if (-not [string]::IsNullOrWhiteSpace($LinuxUser)) { $invoke.LinuxUser = $LinuxUser }
& $CoreUninstaller @invoke
if (-not $?) { exit 1 }
exit 0
