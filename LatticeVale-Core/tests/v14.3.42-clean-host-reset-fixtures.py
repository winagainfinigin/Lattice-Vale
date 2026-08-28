#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT.parent
reset=(REL/'tools/Reset-LatticeVale-CleanHost.ps1').read_text(encoding='ascii')
install=(REL/'installer/Install-LatticeVale.ps1').read_text(encoding='ascii')+(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
uninstall=(REL/'installer/Uninstall-LatticeVale.ps1').read_text(encoding='ascii')+(ROOT/'Uninstall-LatticeVale.ps1').read_text(encoding='ascii')
version=(ROOT/'VERSION.txt').read_text().strip()
assert version in {'14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}
assert '[switch]$Execute' in reset and "Type CLEAN-RESET to continue" in reset
assert '[switch]$RemoveWslRuntime' in reset and "@('--unregister',$d)" in reset
assert "'.wslconfig*'" in reset and "Microsoft.WSL" in reset
assert '[switch]$RemoveLegacyHermesFoundry' in reset
assert '[switch]$DeleteLatticeValeSource' in reset and 'Refusing to delete a filesystem root' in reset
assert r'LatticeVale-Core\VERSION.txt' in reset and r"'installer\Install-LatticeVale.ps1'" in reset
assert 'tailscale serve reset' not in reset.lower()
assert "@('serve',\"--https=$($pair.Https)\",'off')" in reset
assert "Win32_LogicalDisk -Filter 'DriveType=3'" in reset and "Get-ChildItem -LiteralPath $driveRoot -Filter '*.lnk'" in reset
assert 'Remove-HnsNetwork' not in reset
assert 'Disable-WindowsOptionalFeature' not in reset and 'dism.exe /online /disable-feature' not in reset.lower()
assert 'VirtualMachinePlatform' in reset and 'does NOT remove Tailscale' in reset
assert r'%USERPROFILE%\.hermes' in reset and 'standalone' in reset
assert 'Reset-LatticeVale-CleanHost.ps1' not in install
assert 'Reset-LatticeVale-CleanHost.ps1' not in uninstall
inst=(REL/'docs/Instructions.txt').read_text(encoding='utf-8')
desc=(REL/'docs/Installer Description.txt').read_text(encoding='utf-8')
assert 'INTENTIONAL FRESH WSL + LATTICEVALE BASELINE' in inst
assert 'ALL WSL distributions registered to the current Windows user' in inst
assert 'NORMAL UNINSTALL VS. CLEAN-HOST RESET' in desc
print('v14.3.42 clean-host reset fixtures: PASS')
