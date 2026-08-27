#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$DistroName = '',
    [switch]$ApplyNatFallback,
    [switch]$SkipComponentStoreRepair,
    [switch]$LaunchRecoveryOnly
)

$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

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

function ConvertTo-WindowsProcessArgument([string]$Value) {
    if ($null -eq $Value) { return '""' }
    if ($Value -notmatch '[\s"]') { return $Value }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ($ch -eq '\') { $slashes++; continue }
        if ($ch -eq '"') {
            [void]$builder.Append(('\' * (($slashes * 2) + 1)))
            [void]$builder.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) { [void]$builder.Append(('\' * $slashes)); $slashes = 0 }
        [void]$builder.Append($ch)
    }
    if ($slashes -gt 0) { [void]$builder.Append(('\' * ($slashes * 2))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Invoke-NativeProcessCapture([string]$FilePath, [string[]]$Arguments, [int]$TimeoutSeconds = 30) {
    $process = $null
    try {
        $argumentLine = (($Arguments | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $FilePath
        $startInfo.Arguments = $argumentLine
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw "Could not start native process: $FilePath" }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch {}
            try { $process.WaitForExit(2000) | Out-Null } catch {}
            $stdout = if ($stdoutTask.IsCompleted) { [string]$stdoutTask.Result } else { '' }
            $stderr = if ($stderrTask.IsCompleted) { [string]$stderrTask.Result } else { '' }
            $text = (($stdout + "`n" + $stderr) -replace "`0", '').Trim()
            return [pscustomobject]@{ Success=$false; ExitCode=-1; TimedOut=$true; Text=$text; StdOut=(($stdout -replace "`0", '').Trim()); StdErr=(($stderr -replace "`0", '').Trim()) }
        }
        $process.WaitForExit()
        $stdout = [string]$stdoutTask.Result
        $stderr = [string]$stderrTask.Result
        $text = (($stdout + "`n" + $stderr) -replace "`0", '').Trim()
        $exitCode = [int]$process.ExitCode
        return [pscustomobject]@{ Success=($exitCode -eq 0); ExitCode=$exitCode; TimedOut=$false; Text=$text; StdOut=(($stdout -replace "`0", '').Trim()); StdErr=(($stderr -replace "`0", '').Trim()) }
    } catch {
        return [pscustomobject]@{ Success=$false; ExitCode=-1; TimedOut=$false; Text=[string]$_.Exception.Message; StdOut=''; StdErr=[string]$_.Exception.Message }
    } finally {
        if ($process) { try { $process.Dispose() } catch {} }
    }
}

function Invoke-WslLaunchProbe([string]$Name) {
    $probe = Invoke-NativeProcessCapture 'wsl.exe' @('-d', $Name, '-u', 'root', '--', 'true') 30
    $text = ([string]$probe.Text).Trim()
    return [pscustomobject]@{
        Success = [bool]$probe.Success
        ExitCode = [int]$probe.ExitCode
        TimedOut = [bool]$probe.TimedOut
        Text = $text
        Unexpected = ($text -match '(?i)(Wsl/Service(?:/CreateInstance(?:/CreateVm)?)?/E_UNEXPECTED|Wsl/Service/E_UNEXPECTED|Catastrophic failure)')
    }
}

function Invoke-WslShutdownRecovery {
    $shutdown = Invoke-NativeProcessCapture 'wsl.exe' @('--shutdown') 30
    if (-not $shutdown.Success) {
        $detail = if ($shutdown.TimedOut) { 'wsl --shutdown timed out after 30 seconds' } elseif ($shutdown.Text) { $shutdown.Text } else { "wsl.exe exit code $($shutdown.ExitCode)" }
        Write-Warning "The clean WSL shutdown recovery could not complete: $detail"
        return $false
    }
    # Microsoft documents wsl --shutdown as the fast path for fully restarting WSL.
    # Give the host VM/networking state time to settle before probing the same distro.
    Start-Sleep -Seconds 8
    return $true
}

function Test-ModernStoreWsl {
    $probe = Invoke-NativeProcessCapture 'wsl.exe' @('--version') 15
    return [bool]$probe.Success
}

function Get-RegisteredWslDistroNames {
    $probe = Invoke-NativeProcessCapture 'wsl.exe' @('--list', '--quiet') 15
    if (-not $probe.Success) { return @() }
    $normalized = ([string]$probe.StdOut).Trim([char]0xFEFF,[char]0x200B,[char]0x20,[char]0x0D,[char]0x0A,[char]0x09)
    if ([string]::IsNullOrWhiteSpace($normalized)) { return @() }
    return @($normalized -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
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
    Write-Host "WSL launch test passed for '$DistroName'. No host repair was performed." -ForegroundColor Green
    exit 0
}

# v14.4.81 safe-first recovery: Microsoft documents wsl --shutdown as an
# initial recovery for catastrophic/unexpected WSL failures. Try that non-destructive
# restart first. Only if E_UNEXPECTED persists and the user explicitly configured
# mirrored networking may the helper offer the existing backed-up NAT correction.
if ($initialProbe.Unexpected) {
    Write-Step 'Retrying E_UNEXPECTED after a clean WSL shutdown'
    if (Invoke-WslShutdownRecovery) {
        $restartProbe = Invoke-WslLaunchProbe $DistroName
        if ($restartProbe.Success) {
            Write-Host "WSL launch recovered after wsl --shutdown. The distro registration, VHDX, and .wslconfig were not changed." -ForegroundColor Green
            exit 0
        }
        $initialProbe = $restartProbe
        if ($restartProbe.Text) { Write-Host $restartProbe.Text }
    }
}

$initialNetworkingMode = Get-WslNetworkingModeFromConfig
if ($initialProbe.Unexpected -and $initialNetworkingMode -eq 'mirrored') {
    Write-Step 'Detected persistent E_UNEXPECTED with global mirrored WSL networking'
    if (-not $ApplyNatFallback) {
        Write-Warning 'The registered distro still cannot launch after a clean WSL restart while .wslconfig explicitly selects networkingMode=mirrored. NAT is the WSL default and is the narrow compatibility fallback LatticeVale can offer without touching the distro or VHDX.'
        Write-Host "No Windows component or distro mutation has been performed. To back up .wslconfig, change only networkingMode to NAT, and retest the same registered distro, rerun:`n  .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName '$DistroName' -LaunchRecoveryOnly -ApplyNatFallback" -ForegroundColor Yellow
        exit 20
    }

    Write-Step 'Applying backed-up NAT compatibility recovery'
    $backupPath = Set-WslNetworkingModeNat
    Write-Host "Backed up the previous .wslconfig to: $backupPath"
    Write-Host 'Changed only [wsl2] networkingMode to nat; processor, memory, [general], and unrelated settings are preserved.'
    if (Invoke-WslShutdownRecovery) {
        $natProbe = Invoke-WslLaunchProbe $DistroName
        if ($natProbe.Success) {
            Write-Host "WSL launch test passed after the NAT recovery. LatticeVale did not modify distro registration or the VHDX." -ForegroundColor Green
            exit 0
        }
        Write-Warning 'WSL still fails after changing only networkingMode to NAT. The .wslconfig backup was preserved.'
        if ($natProbe.Text) { Write-Host $natProbe.Text }
        $initialProbe = $natProbe
    }
}

if ($LaunchRecoveryOnly) {
    Write-Warning 'Bounded launch recovery did not restore the existing distro. No DISM, Windows-feature mutation, distro registration change, or VHDX change was performed.'
    Write-Host "For deeper Windows/WSL host repair, rerun without -LaunchRecoveryOnly from an elevated PowerShell window:`n  .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName '$DistroName'" -ForegroundColor Yellow
    exit 30
}

if (-not (Test-IsAdministrator)) {
    Write-Warning 'The bounded WSL launch recovery is safe to run without elevation, but deeper DISM/Windows-feature repair requires Administrator rights.'
    Write-Host "Open PowerShell as Administrator and rerun:`n  .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName '$DistroName'" -ForegroundColor Yellow
    exit 40
}

$systemChanged = $false

if (-not $SkipComponentStoreRepair) {
    Write-Step 'Repairing the Windows component store'
    Write-Host 'Running Microsoft DISM RestoreHealth before any deeper WSL feature-state repair.'
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
    Write-Host "WSL launch test passed for '$DistroName'." -ForegroundColor Green
    exit 0
}

Write-Warning "WSL launch test failed with exit code $($probe.ExitCode)."
if ($probe.Text) { Write-Host $probe.Text }

if ($probe.Unexpected) {
    $wslMode = Get-WslNetworkingModeFromConfig
    Write-Host "Configured WSL networkingMode: $wslMode"
    if ($wslMode -eq 'mirrored') {
        if (-not $ApplyNatFallback) {
            Write-Warning 'E_UNEXPECTED persists while .wslconfig uses mirrored networking.'
            Write-Host 'Current WSL issue reports show E_UNEXPECTED on affected Windows 11 builds, while mirrored-networking regressions are also documented separately. LatticeVale therefore treats NAT/default networking only as a conditional compatibility fallback here, not as proof of the root cause.'
            Write-Host "To apply a reversible NAT fallback, rerun:`n  .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName '$DistroName' -SkipComponentStoreRepair -ApplyNatFallback"
            exit 20
        }

        Write-Step 'Applying backed-up NAT compatibility fallback'
        $backupPath = Set-WslNetworkingModeNat
        Write-Host "Backed up the previous .wslconfig to: $backupPath"
        Write-Host 'Changed only [wsl2] networkingMode to nat; processor, memory, and [general] settings are preserved.'
        [void](Invoke-WslShutdownRecovery)
        $probe = Invoke-WslLaunchProbe $DistroName
        if ($probe.Success) {
            Write-Host "WSL launch test passed in NAT mode. You can rerun installer\Install-LatticeVale.ps1." -ForegroundColor Green
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
