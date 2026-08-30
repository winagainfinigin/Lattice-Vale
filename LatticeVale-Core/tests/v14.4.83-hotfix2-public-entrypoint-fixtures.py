#!/usr/bin/env python3
from pathlib import Path

CORE=Path(__file__).resolve().parents[1]
ROOT=CORE.parent
INSTALLER=ROOT/'installer'

assert (CORE/'VERSION.txt').read_text(encoding='ascii').strip() in {'14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'}

primary_install=INSTALLER/'Install-LatticeVale.ps1'
primary_uninstall=INSTALLER/'Uninstall-LatticeVale.ps1'
compat_install=INSTALLER/'install.ps1'
compat_uninstall=INSTALLER/'uninstall.ps1'
verify=INSTALLER/'verify-release.ps1'
for p in (primary_install,primary_uninstall,compat_install,compat_uninstall,verify):
    assert p.is_file(), p

# Primary launchers preserve the proven v14.4.83 wrapper behavior.
pi=primary_install.read_text(encoding='ascii')
pu=primary_uninstall.read_text(encoding='ascii')
assert "Join-Path $ReleaseRoot 'LatticeVale-Core\\Install-LatticeVale.ps1'" in pi
assert "Join-Path $ReleaseRoot 'LatticeVale-Core\\Uninstall-LatticeVale.ps1'" in pu
for text in (pi,pu):
    assert 'SOURCE-SHA256SUMS.txt' in text
    assert 'Test-LatticeValeSourceManifest -ReleaseRoot $ReleaseRoot' in text
    assert "Join-Path $ReleaseRoot 'tools\\ReleaseManifest.ps1'" in text

# Compatibility launchers remain behavior-identical so old automation is not broken.
assert primary_install.read_bytes() == compat_install.read_bytes()
assert primary_uninstall.read_bytes() == compat_uninstall.read_bytes()

readme=(ROOT/'README.md').read_text(encoding='utf-8')
for cmd in (
    r'powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\Install-LatticeVale.ps1',
    r'powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\Uninstall-LatticeVale.ps1',
):
    assert cmd in readme, cmd

# Current operational docs use the canonical names, not the compatibility names.
for rel in ('docs/README.md','docs/Instructions.txt','docs/SECURITY.md','docs/FEATURES.md','docs/SUPPORT.md','docs/Installer Description.txt','docs/SOURCES.md'):
    text=(ROOT/rel).read_text(encoding='utf-8')
    assert 'installer\\install.ps1' not in text and 'installer/install.ps1' not in text, rel
    assert 'installer\\uninstall.ps1' not in text and 'installer/uninstall.ps1' not in text, rel

reset=(ROOT/'tools/Reset-LatticeVale-CleanHost.ps1').read_text(encoding='ascii')
repair=(ROOT/'tools/Repair-LatticeVale-WslHost.ps1').read_text(encoding='ascii')
assert r"'installer\Install-LatticeVale.ps1'" in reset
assert 'installer\\Uninstall-LatticeVale.ps1' in reset
assert 'installer\\Install-LatticeVale.ps1' in repair

print('v14.4.83 Hotfix 2 public entrypoint fixtures: PASS')
