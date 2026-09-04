#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT.parent
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}, version
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
helper = (RELEASE / 'tools' / 'Repair-LatticeVale-WslHost.ps1').read_text(encoding='ascii')
audit = (ROOT / 'stack' / 'state-audit.py').read_text(encoding='utf-8')

# Normal configuration/runtime must never own/change the host-global networkingMode directly.
for forbidden in (
    'function Resolve-LatticeValeNativeOllamaMirroredFallback',
    'function Set-WslGlobalNetworkingModeValue',
    'function Restart-LatticeValeWslForNativeOllamaNetworking',
    'Switch global WSL2 networkingMode to mirrored',
    'Use mirrored WSL networking as the shared mode',
    'Configured [wsl2] networkingMode=mirrored',
):
    assert forbidden not in ps, forbidden
assert 'v14.3.41 host-safety rule: never change global WSL networking' in ps
assert 'will not create, reapply, or require mirrored mode' in ps
assert "user-existing-mirrored" in ps
assert "Configure native Windows Ollama for direct WSL access as a final fallback?" in ps

# Existing mirrored topology remains consumable if the host/user configured it and it works.
assert "if ($activeWslNetworkingMode -eq 'mirrored')" in ps
assert "wslNetworkingModeOwner = $wslNetworkingModeOwner" in ps
assert "Shared WSL networking policy: existing mirrored mode (externally/user configured)." in ps
assert 'without taking ownership of or rewriting .wslconfig' in ps

# Safe host recovery remains implemented in the explicit helper. v14.4.81 may invoke
# that helper in bounded launch-recovery mode, but core still has no networking writer.
# NAT is backed up and limited to persistent E_UNEXPECTED + mirrored before deeper repair.
assert '[switch]$ApplyNatFallback' in helper
assert 'function Set-WslNetworkingModeNat' in helper
assert '$backupPath = "$configPath.latticevale-auditpatch-$stamp.bak"' in helper
assert "networkingMode=nat" in helper
safe = helper.index("$initialNetworkingMode = Get-WslNetworkingModeFromConfig")
dism = helper.index("dism.exe /Online /Cleanup-Image /RestoreHealth")
assert safe < dism
assert "if ($initialProbe.Unexpected -and $initialNetworkingMode -eq 'mirrored')" in helper
assert 'Applying backed-up NAT compatibility recovery' in helper
assert '[switch]$LaunchRecoveryOnly' in helper
assert "'-LaunchRecoveryOnly'" in ps
assert 'Set-WslNetworkingModeNat' not in ps
assert helper.index('if ($LaunchRecoveryOnly)') < dism
for forbidden in ('--unregister', '--import', '--set-version', 'Optimize-VHD', 'Mount-VHD', 'Dismount-VHD'):
    assert forbidden.lower() not in helper.lower(), forbidden

# Runtime audit distinguishes a user-owned existing mirrored topology from the managed
# shared NAT/VirtioProxy policy rather than pretending LatticeVale owns .wslconfig.
assert 'user-existing-mirrored' in audit
assert 'shared native-Ollama/Tailscale networking policy must record a verified non-mirrored topology' in audit

print('v14.3.41 WSL host-safety fixtures: PASS')
