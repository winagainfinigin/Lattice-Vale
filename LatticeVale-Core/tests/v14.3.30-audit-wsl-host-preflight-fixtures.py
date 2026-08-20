#!/usr/bin/env python3
"""Regression fixtures for the audit-driven WSL host prerequisite patch."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT.parent
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
helper = (RELEASE_ROOT / 'tools' / 'Repair-LatticeVale-WslHost.ps1').read_text(encoding='ascii')

feature_probe = "Get-WindowsOptionalFeatureStateSafe 'Microsoft-Windows-Subsystem-Linux'"
list_probe = "Invoke-NativeProcessCapture 'wsl.exe' @('--list', '--quiet')"
version_probe = "Invoke-NativeProcessCapture 'wsl.exe' @('--version')"
assert feature_probe in ps
assert version_probe in ps and ps.index(version_probe) < ps.index(list_probe), 'modern WSL detection must precede distro enumeration'
assert "legacy/inbox feature state is advisory for WSL2" in ps
assert "Continuing to functional WSL/distro checks" in ps
assert "throw \"Windows Subsystem for Linux optional feature is" not in ps
assert 'WindowsSubsystemForLinuxState = $wslFeatureState' in ps
assert 'tools\\Repair-LatticeVale-WslHost.ps1' in ps
assert 'WSL_HOST_E_UNEXPECTED' in ps
assert 'Catastrophic failure' in ps

# The core installer remains prerequisite-only. Host mutation is isolated in an explicit helper.
for forbidden in ('Enable-WindowsOptionalFeature', 'dism.exe /Online /Cleanup-Image /RestoreHealth'):
    assert forbidden.lower() not in ps.lower(), forbidden

assert "Enable-WindowsOptionalFeature -Online -FeatureName 'Microsoft-Windows-Subsystem-Linux' -All -NoRestart" in helper
assert "Enable-WindowsOptionalFeature -Online -FeatureName 'VirtualMachinePlatform' -All -NoRestart" in helper
assert 'dism.exe /Online /Cleanup-Image /RestoreHealth' in helper
assert 'Set-WslNetworkingModeNat' in helper
assert 'networkingMode=nat' in helper
assert 'latticevale-auditpatch-' in helper
assert 'wsl.exe --shutdown' in helper
assert 'ApplyNatFallback' in helper
assert 'Testing current WSL state before host mutation' in helper
assert 'No host repair was performed' in helper
assert 'Test-ModernStoreWsl' in helper
assert 'will not automatically enable the legacy/inbox WSL1 component' in helper

# Preservation boundary: this helper must not manipulate distro registration or VHD files.
for forbidden in ('--unregister', '--import', '--set-version', 'Remove-Item', 'Optimize-VHD', 'Mount-VHD', 'Dismount-VHD'):
    assert forbidden.lower() not in helper.lower(), forbidden
assert 'never unregisters, imports, moves, converts, or deletes a WSL distribution or VHDX' in helper

print('v14.3.30 AUDIT WSL HOST PREFLIGHT FIXTURES: PASS')
