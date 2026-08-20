#Requires -Version 5.1
[CmdletBinding()]
param([string]$ZipPath='')
$ErrorActionPreference='Stop'
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleaseRoot=Split-Path -Parent $Here
$Manifest=Join-Path $Here 'SOURCE-SHA256SUMS.txt'
$Verifier=Join-Path $ReleaseRoot 'tools\ReleaseManifest.ps1'
if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) { throw "Release verifier module not found: $Verifier" }
. $Verifier
$checked=Test-LatticeValeSourceManifest -ReleaseRoot $ReleaseRoot -ManifestPath $Manifest -WriteEachFile
Write-Host "`nVerified $checked release source/config files with exact manifest coverage." -ForegroundColor Green
if (-not [string]::IsNullOrWhiteSpace($ZipPath)) {
    $resolved=(Resolve-Path -LiteralPath $ZipPath).Path
    $zipHash=Get-FileHash -LiteralPath $resolved -Algorithm SHA256
    Write-Host "`nZIP SHA-256:" -ForegroundColor Cyan
    Write-Host $zipHash.Hash
    Write-Host $resolved
}
