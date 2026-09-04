#!/usr/bin/env python3
"""Regression assertions for v14.4.81 bounded WSL E_UNEXPECTED recovery."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT.parent
VERSION = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert VERSION in {'14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}, VERSION
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
helper = (RELEASE / 'tools' / 'Repair-LatticeVale-WslHost.ps1').read_text(encoding='ascii')
compat = (ROOT / 'compatibility.conf').read_text(encoding='ascii')

# The installer may orchestrate the explicit helper, but does not directly implement
# host-global .wslconfig mutation or distro/VHDX mutation.
assert 'function Try-RecoverLatticeValeWslHostLaunch' in ps
assert 'function Invoke-LatticeValeWslHostLaunchRecoveryHelper' in ps
assert "'-LaunchRecoveryOnly'" in ps
assert "if ($exitCode -eq 20)" in ps
assert 'Apply the backed-up NAT compatibility recovery now?' in ps
assert "@('--list','--running','--quiet') 15" in ps
assert 'Proceed with the global WSL shutdown/restart recovery anyway?' in ps
assert 'LatticeVale cannot prove whether unrelated distros are active during this host-service failure.' in ps
assert 'Rechecking Ubuntu WSL2 eligibility after host recovery' in ps
assert '$requestedUnexpected' in ps
assert 'if ($eligible.Count -eq 0 -or $null -ne $requestedUnexpected)' in ps
assert 'Try-RecoverLatticeValeWslHostLaunch ([string]$recoveryTarget.Name)' in ps
assert 'foreach ($name in $InstalledNames) { $infos += Get-UbuntuDistroInfo ([string]$name) }' in ps
assert 'MIN_HOST_PARTITION_FREE_GIB=50' in compat
assert 'MIN_MANAGED_REPAIR_FREE_GIB=10' in compat
assert "$_ .BlockerCodes" not in ps  # guard against a common malformed member-access typo
assert 'Set-WslNetworkingModeNat' not in ps
for forbidden in ('--unregister', '--import', '--set-version', 'Optimize-VHD', 'Mount-VHD', 'Dismount-VHD'):
    assert forbidden.lower() not in ps.lower(), forbidden

# The helper first performs Microsoft's non-destructive WSL restart recovery, then
# offers NAT only for persistent E_UNEXPECTED + explicit mirrored mode.
assert '[switch]$LaunchRecoveryOnly' in helper
assert '#Requires -RunAsAdministrator' not in helper
assert 'function Test-IsAdministrator' in helper
assert "Write-Step 'Retrying E_UNEXPECTED after a clean WSL shutdown'" in helper
assert "Invoke-NativeProcessCapture 'wsl.exe' @('--shutdown') 30" in helper
assert 'Start-Sleep -Seconds 8' in helper
shutdown_first = helper.index("Write-Step 'Retrying E_UNEXPECTED after a clean WSL shutdown'")
mode_check = helper.index('$initialNetworkingMode = Get-WslNetworkingModeFromConfig')
assert shutdown_first < mode_check
assert "if ($initialProbe.Unexpected -and $initialNetworkingMode -eq 'mirrored')" in helper
assert 'Applying backed-up NAT compatibility recovery' in helper
assert 'networkingMode=nat' in helper
assert 'No DISM, Windows-feature mutation, distro registration change, or VHDX change was performed.' in helper
launch_only = helper.index('if ($LaunchRecoveryOnly)')
admin_guard = helper.index('if (-not (Test-IsAdministrator))')
dism = helper.index('dism.exe /Online /Cleanup-Image /RestoreHealth')
assert launch_only < admin_guard < dism
assert 'deeper DISM/Windows-feature repair requires Administrator rights' in helper

# Bounded helper probes must not wait forever on a broken WSL service.
assert 'function Invoke-NativeProcessCapture' in helper
assert 'WaitForExit($TimeoutSeconds * 1000)' in helper
assert "Invoke-NativeProcessCapture 'wsl.exe' @('-d', $Name, '-u', 'root', '--', 'true') 30" in helper
assert "Invoke-NativeProcessCapture 'wsl.exe' @('--list', '--quiet') 15" in helper

# Preservation boundary remains strict.
for forbidden in ('--unregister', '--import', '--set-version', 'Remove-Item', 'Optimize-VHD', 'Mount-VHD', 'Dismount-VHD'):
    assert forbidden.lower() not in helper.lower(), forbidden

print('v14.4.81+ WSL launch-recovery fixtures: PASS')
