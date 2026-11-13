# LatticeVale 14.6.7 optional Element / Adlice detection triage.
# Strictly read-only. Never disables protection, quarantines, restores,
# downloads software, or creates broad exclusions.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Continue'
Write-Host '=== LatticeVale | Element / Adlice read-only security triage ==='
Write-Host 'LatticeVale runs Matrix Synapse in Docker; Element Desktop is a separate Windows application.'
Write-Host 'An Adlice detection cannot be called a false positive without its exact detection name, target, and verification.'

$paths = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($p in @(
    (Join-Path $env:LOCALAPPDATA 'Programs\element-desktop\Element.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Element\Element.exe'),
    (Join-Path $env:LOCALAPPDATA 'Element\Element.exe'),
    (Join-Path $env:ProgramFiles 'Element\Element.exe'),
    $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} 'Element\Element.exe' })
)) {
    if (-not [string]::IsNullOrWhiteSpace($p) -and (Test-Path -LiteralPath $p -PathType Leaf)) {
        [void]$paths.Add($p)
    }
}

# Inspect executable paths for running instances; never trust process names
# as proof of authenticity, because malware can also call itself Element.exe.
try {
    $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'Element.exe'" -ErrorAction Stop)
    foreach ($process in $processes) {
        if ($process.ExecutablePath -and (Test-Path -LiteralPath $process.ExecutablePath -PathType Leaf)) {
            [void]$paths.Add([string]$process.ExecutablePath)
        }
    }
    Write-Host ("Running Element.exe instances: {0}" -f $processes.Count)
} catch {
    Write-Warning ('Could not inspect process paths: ' + $_.Exception.Message)
}

if ($paths.Count -eq 0) {
    Write-Host 'No Element Desktop executable found in common locations or the running process list.'
    Write-Host 'If Adlice flagged a different path, inspect THAT exact path in its scan report.'
}
foreach ($path in $paths) {
    Write-Host "`nExecutable: $path"
    try {
        $file = Get-Item -LiteralPath $path -ErrorAction Stop
        $signature = Get-AuthenticodeSignature -LiteralPath $path -ErrorAction Stop
        $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop
        $publisher = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { '(none)' }
        Write-Host ('File version: ' + $file.VersionInfo.FileVersion)
        Write-Host ('Product name: ' + $file.VersionInfo.ProductName)
        Write-Host ('Signature status: ' + [string]$signature.Status)
        Write-Host ('Signer subject: ' + $publisher)
        Write-Host ('SHA256: ' + $hash.Hash)
        if ($signature.Status -ne 'Valid') {
            Write-Warning 'Signature not verified. Do NOT make antivirus exclusions. Investigate the detected file first.'
        } else {
            Write-Host 'Valid signature is supporting evidence, not proof that Adlice detection is erroneous.'
        }
    } catch {
        Write-Warning ('Element file audit failed: ' + $_.Exception.Message)
    }
}
Write-Host "`n=== Follow-up for an Adlice alert ==="
Write-Host 'In Adlice Protect (RogueKiller): open History > Reporting or the scan Results > Report.'
Write-Host 'Export the detection category/name, EXACT file/registry path, SHA256, and engine/signature version.'
Write-Host 'Check that the flagged file is the verified installed Element executable, not an unrelated file with a similar name.'
Write-Host 'Update Adlice signatures and Element from its official distribution channel; report suspected false positives to Adlice.'
Write-Host 'Never disable Adlice or automatically whitelist a directory; exclusions hide real threats.'
Write-Host 'If Element Desktop cannot be trusted or is quarantined, use https://app.element.io/ temporarily.'
Write-Host 'No scanner settings, files, registries, or services were modified.'
