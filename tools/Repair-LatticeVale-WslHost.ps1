#Requires -Version 5.1
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$DistroName = '',
    [switch]$ApplyNatFallback,
    [switch]$SkipComponentStoreRepair
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Text) {
    Write-Host "`n== $Text ==" -ForegroundColor Cyan
}

function Get-FeatureState([string]$FeatureName) {
    try {
        return [string](Get-WindowsOptionalFeature -Online -FeatureName $FeatureName -ErrorAction Stop).State
    } catch {
        return ''
    }
}

function Test-RebootPending {
    if (Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') { return $true }
    if (Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') { return $true }
    try {
        $pending = (Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction Stop).PendingFileRenameOperations
        if ($null -ne $pending -and @($pending).Count -gt 0) { return $true }
    } catch {}
    return $false
}

function Invoke-WslLaunchProbe([string]$Name) {
    $lines = @()
    $exitCode = -1
    try {
        $lines = @(& wsl.exe -d $Name -u root -- true 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    } catch {
        $lines += [string]$_.Exception.Message
    }
    $text = ($lines -join "`n").Trim()
    return [pscustomobject]@{
        Success = ($exitCode -eq 0)
        ExitCode = $exitCode
        Text = $text
        Unexpected = ($text -match '(?i)(Wsl/Service(?:/CreateInstance(?:/CreateVm)?)?/E_UNEXPECTED|Wsl/Service/E_UNEXPECTED|Catastrophic failure)')
    }
}

function Test-ModernStoreWsl {
    try {
        $versionLines = @(& wsl.exe --version 2>&1)
        return ($LASTEXITCODE -eq 0 -and $versionLines.Count -ge 0)
    } catch {
        return $false
    }
}

function Get-RegisteredWslDistroNames {
    try {
        $raw = (& wsl.exe --list --quiet 2>$null | Out-String)
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) { return @() }
        $normalized = ($raw -replace "`0", '').Trim([char]0xFEFF,[char]0x200B,[char]0x20,[char]0x0D,[char]0x0A,[char]0x09)
        if ([string]::IsNullOrWhiteSpace($normalized)) { return @() }
        return @($normalized -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    } catch {
        return @()
    }
}

function Get-WslNetworkingModeFromConfig {
    $configPath = Join-Path $env:USERPROFILE '.wslconfig'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { return '' }
    $raw = [IO.File]::ReadAllText($configPath)
    $section = [regex]::Match($raw, '(?ims)^\s*\[wsl2\]\s*\r?\n(?<body>.*?)(?=^\s*\[|\z)')
    if (-not $section.Success) { return '' }
    $mode = [regex]::Match($section.Groups['body'].Value, '(?im)^\s*networkingMode\s*=\s*(?<value>[^\s#;]+)')
    if (-not $mode.Success) { return '' }
    return $mode.Groups['value'].Value.Trim().ToLowerInvariant()
}

function Set-WslNetworkingModeNat {
    $configPath = Join-Path $env:USERPROFILE '.wslconfig'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupPath = "$configPath.latticevale-auditpatch-$stamp.bak"
    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
        $sourceLines = @(Get-Content -LiteralPath $configPath)
    } else {
        $sourceLines = @()
    }

    $output = New-Object System.Collections.Generic.List[string]
    $inWsl2 = $false
    $sawWsl2 = $false
    $wroteMode = $false

    foreach ($line in $sourceLines) {
        $sectionMatch = [regex]::Match($line, '^\s*\[(?<name>[^\]]+)\]\s*$')
        if ($sectionMatch.Success) {
            if ($inWsl2 -and -not $wroteMode) {
                $output.Add('networkingMode=nat')
                $wroteMode = $true
            }
            $inWsl2 = ($sectionMatch.Groups['name'].Value.Trim() -ieq 'wsl2')
            if ($inWsl2) { $sawWsl2 = $true }
            $output.Add($line)
            continue
        }
        if ($inWsl2 -and $line -match '^\s*networkingMode\s*=') {
            if (-not $wroteMode) {
                $output.Add('networkingMode=nat')
                $wroteMode = $true
            }
            continue
        }
        $output.Add($line)
    }

    if ($sawWsl2) {
        if ($inWsl2 -and -not $wroteMode) { $output.Add('networkingMode=nat') }
    } else {
        if ($output.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($output[$output.Count - 1])) { $output.Add('') }
        $output.Add('[wsl2]')
        $output.Add('networkingMode=nat')
    }

    $text = (($output.ToArray() -join "`r`n") + "`r`n")
    [IO.File]::WriteAllText($configPath, $text, (New-Object Text.UTF8Encoding($false)))
    return $backupPath
}

Write-Host 'LatticeVale WSL host repair helper (compatibility patch)' -ForegroundColor Green
Write-Host 'This helper never unregisters, imports, moves, converts, or deletes a WSL distribution or VHDX.'

if ([string]::IsNullOrWhiteSpace($DistroName)) {
    $registeredDistros = @(Get-RegisteredWslDistroNames)
    if ($registeredDistros.Count -eq 1) {
        $DistroName = [string]$registeredDistros[0]
        Write-Host "Auto-selected the only registered WSL distro: $DistroName"
    } elseif ($registeredDistros.Count -gt 1) {
        Write-Host 'Registered WSL distros:' -ForegroundColor Yellow
        foreach ($item in $registeredDistros) { Write-Host "  - $item" }
        throw 'More than one WSL distro is registered. Rerun this helper with -DistroName <exact-name> so it cannot repair/test the wrong distro.'
    } else {
        throw 'No WSL distro could be auto-selected. If WSL enumeration itself is broken, rerun this helper with -DistroName <exact-existing-distro-name>.'
    }
}
Write-Host "Target distro: $DistroName"

Write-Step 'Inspecting Windows WSL prerequisites'
$wslFeatureState = Get-FeatureState 'Microsoft-Windows-Subsystem-Linux'
$vmPlatformState = Get-FeatureState 'VirtualMachinePlatform'
$modernWsl = Test-ModernStoreWsl
Write-Host "Microsoft-Windows-Subsystem-Linux: $wslFeatureState"
Write-Host "VirtualMachinePlatform: $vmPlatformState"
Write-Host "Modern Store/MSI WSL detected: $modernWsl"

# Functional-first safety rule: if the existing WSL2 distro launches, do not repair
# Windows components merely because optional-feature metadata looks unusual. This
# avoids changing a healthy Store/MSI WSL installation such as one where the legacy
# WSL1/inbox optional component is intentionally disabled.
Write-Step 'Testing current WSL state before host mutation'
$initialProbe = Invoke-WslLaunchProbe $DistroName
if ($initialProbe.Success) {
    if ($wslFeatureState -and $wslFeatureState -ne 'Enabled' -and $modernWsl) {
        Write-Host "The legacy/inbox Windows Subsystem for Linux optional feature is '$wslFeatureState', but modern Store/MSI WSL successfully launched '$DistroName'. No feature repair is needed." -ForegroundColor Yellow
    }
    Write-Host "WSL launch test passed for '$DistroName'. No host repair was performed; you can rerun installer\install.ps1." -ForegroundColor Green
    exit 0
}

# v14.3.41 safe-first recovery: when the launch failure is E_UNEXPECTED and the
# global WSL configuration explicitly selects mirrored networking, test the narrow,
# reversible networking correction before DISM or Windows feature mutation. Mirrored
# mode is global to every WSL2 distro and can fail only after a cold restart, so host
# configuration recovery belongs ahead of component-store repair.
$initialNetworkingMode = Get-WslNetworkingModeFromConfig
if ($initialProbe.Unexpected -and $initialNetworkingMode -eq 'mirrored') {
    Write-Step 'Detected E_UNEXPECTED with global mirrored WSL networking'
    if (-not $ApplyNatFallback) {
        Write-Warning 'The registered distro cannot launch while .wslconfig explicitly selects networkingMode=mirrored. LatticeVale no longer creates or requires mirrored networking because host-build regressions can make a previously working configuration fail after WSL or Windows restarts.'
        Write-Host "No Windows component or distro mutation has been performed. To back up .wslconfig, change only networkingMode to NAT, and retest the same registered distro, rerun:`n  .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName '$DistroName' -SkipComponentStoreRepair -ApplyNatFallback" -ForegroundColor Yellow
        exit 20
    }

    Write-Step 'Applying backed-up NAT compatibility recovery before component repair'
    $backupPath = Set-WslNetworkingModeNat
    Write-Host "Backed up the previous .wslconfig to: $backupPath"
    Write-Host 'Changed only [wsl2] networkingMode to nat; processor, memory, [general], and unrelated settings are preserved.'
    & wsl.exe --shutdown 2>$null | Out-Null
    Start-Sleep -Seconds 2
    $natProbe = Invoke-WslLaunchProbe $DistroName
    if ($natProbe.Success) {
        Write-Host "WSL launch test passed after the NAT recovery. LatticeVale did not modify distro registration or the VHDX. You can rerun installer\install.ps1." -ForegroundColor Green
        exit 0
    }
    Write-Warning 'WSL still fails after changing only networkingMode to NAT. The .wslconfig backup was preserved; continuing with the remaining host diagnostics instead of assuming networking was the only cause.'
    if ($natProbe.Text) { Write-Host $natProbe.Text }
    $initialProbe = $natProbe
}

$systemChanged = $false

if (-not $SkipComponentStoreRepair) {
    Write-Step 'Repairing the Windows component store'
    Write-Host 'The supplied audit reported that the component store is repairable, so this modified build runs Microsoft DISM RestoreHealth before changing WSL feature state.'
    & dism.exe /Online /Cleanup-Image /RestoreHealth
    $dismExit = $LASTEXITCODE
    if ($dismExit -ne 0 -and $dismExit -ne 3010) {
        throw "DISM RestoreHealth failed with exit code $dismExit. Stop here rather than changing WSL feature state on an unrepaired component store."
    }
    if ($dismExit -eq 3010) { $systemChanged = $true }
}

$wslFeatureState = Get-FeatureState 'Microsoft-Windows-Subsystem-Linux'
if ($wslFeatureState -ne 'Enabled') {
    if ($modernWsl) {
        Write-Warning "Microsoft-Windows-Subsystem-Linux is '$wslFeatureState', but modern Store/MSI WSL is installed. LatticeVale will not automatically enable the legacy/inbox WSL1 component; the functional launch result remains authoritative."
    } else {
        Write-Step 'Enabling legacy/inbox Windows Subsystem for Linux optional feature'
        $result = Enable-WindowsOptionalFeature -Online -FeatureName 'Microsoft-Windows-Subsystem-Linux' -All -NoRestart -ErrorAction Stop
        $systemChanged = $true
        Write-Host "Feature state after request: $($result.State)"
    }
}

$vmPlatformState = Get-FeatureState 'VirtualMachinePlatform'
if ($vmPlatformState -ne 'Enabled') {
    Write-Step 'Enabling Virtual Machine Platform optional feature'
    $result = Enable-WindowsOptionalFeature -Online -FeatureName 'VirtualMachinePlatform' -All -NoRestart -ErrorAction Stop
    $systemChanged = $true
    Write-Host "Feature state after request: $($result.State)"
}

if ($systemChanged -or (Test-RebootPending)) {
    Write-Step 'Restart required before reliable WSL validation'
    Write-Host 'Restart Windows, then run this helper again. It will test the existing distro without recreating it.' -ForegroundColor Yellow
    Write-Host "Do not unregister '$DistroName' and do not delete or replace its distro VHDX." -ForegroundColor Yellow
    exit 10
}

Write-Step 'Testing the existing WSL distro'
$probe = Invoke-WslLaunchProbe $DistroName
if ($probe.Success) {
    Write-Host "WSL launch test passed for '$DistroName'. You can rerun installer\install.ps1." -ForegroundColor Green
    exit 0
}

Write-Warning "WSL launch test failed with exit code $($probe.ExitCode)."
if ($probe.Text) { Write-Host $probe.Text }

if ($probe.Unexpected) {
    Write-Step 'Retrying after a clean WSL shutdown'
    & wsl.exe --shutdown | Out-Null
    Start-Sleep -Seconds 2
    $probe = Invoke-WslLaunchProbe $DistroName
    if ($probe.Success) {
        Write-Host "WSL launch recovered after wsl --shutdown. You can rerun installer\install.ps1." -ForegroundColor Green
        exit 0
    }

    $wslMode = Get-WslNetworkingModeFromConfig
    Write-Host "Configured WSL networkingMode: $wslMode"
    if ($wslMode -eq 'mirrored') {
        if (-not $ApplyNatFallback) {
            Write-Warning 'E_UNEXPECTED persists while .wslconfig uses mirrored networking.'
            Write-Host 'A Microsoft WSL issue documents internal/E_UNEXPECTED failures with mirrored networking on Windows 11. LatticeVale v14.3.41 treats NAT/default networking as the compatibility-safe recovery path and no longer creates mirrored mode.'
            Write-Host "To apply a reversible NAT fallback, rerun:`n  .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName '$DistroName' -SkipComponentStoreRepair -ApplyNatFallback"
            exit 20
        }

        Write-Step 'Applying backed-up NAT compatibility fallback'
        $backupPath = Set-WslNetworkingModeNat
        Write-Host "Backed up the previous .wslconfig to: $backupPath"
        Write-Host 'Changed only [wsl2] networkingMode to nat; processor, memory, and [general] settings are preserved.'
        & wsl.exe --shutdown | Out-Null
        Start-Sleep -Seconds 2
        $probe = Invoke-WslLaunchProbe $DistroName
        if ($probe.Success) {
            Write-Host "WSL launch test passed in NAT mode. You can rerun installer\install.ps1." -ForegroundColor Green
            exit 0
        }
        Write-Warning 'WSL still fails after the NAT fallback. The .wslconfig backup was preserved for rollback.'
        if ($probe.Text) { Write-Host $probe.Text }
        exit 21
    }
}

Write-Warning 'The existing distro is still not launchable. Stop here; do not unregister or recreate it as a first repair step.'
Write-Host 'The patched installer will not touch the distro VHDX. Collect fresh WSL logs after this point because the remaining failure may be a Windows/WSL build regression rather than a LatticeVale issue.'
exit 30
