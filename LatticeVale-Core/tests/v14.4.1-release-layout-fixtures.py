#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CORE=ROOT/'LatticeVale-Core'
INSTALLER=ROOT/'installer'
DOCS=ROOT/'docs'
version=(CORE/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1'}, version

# Repository root stays conventional and uncluttered.
root_files={p.name for p in ROOT.iterdir() if p.is_file()}
assert root_files == {'.gitattributes','.gitignore','README.md','LICENSE'}, root_files
assert (ROOT/'.github').is_dir()
assert INSTALLER.is_dir() and DOCS.is_dir()

for name in ('Install-LatticeVale.ps1','Uninstall-LatticeVale.ps1','install.ps1','uninstall.ps1','verify-release.ps1','SOURCE-SHA256SUMS.txt'):
    assert (INSTALLER/name).is_file(), name
for name in ('README.md','Instructions.txt','Installer Description.txt','FEATURES.md','CHANGELOG.md','SECURITY.md','RELEASE.md','SUPPORT.md','SOURCES.md','THIRD-PARTY-NOTICES.md','CONTRIBUTING.md'):
    assert (DOCS/name).is_file(), name

install=(INSTALLER/'Install-LatticeVale.ps1').read_text(encoding='ascii')
uninstall=(INSTALLER/'Uninstall-LatticeVale.ps1').read_text(encoding='ascii')
compat_install=(INSTALLER/'install.ps1').read_text(encoding='ascii')
compat_uninstall=(INSTALLER/'uninstall.ps1').read_text(encoding='ascii')
verify=(INSTALLER/'verify-release.ps1').read_text(encoding='ascii')
for launcher in (install, uninstall, verify):
    assert '$ReleaseRoot = Split-Path -Parent $Here' in launcher or '$ReleaseRoot=Split-Path -Parent $Here' in launcher
    assert 'Test-LatticeValeSourceManifest -ReleaseRoot $ReleaseRoot' in launcher
assert "Join-Path $ReleaseRoot 'LatticeVale-Core\\Install-LatticeVale.ps1'" in install
assert "Join-Path $ReleaseRoot 'LatticeVale-Core\\Uninstall-LatticeVale.ps1'" in uninstall
assert compat_install == install
assert compat_uninstall == uninstall
assert "Join-Path $ReleaseRoot 'tools\\ReleaseManifest.ps1'" in verify

new_manifest=(ROOT/'tools/New-SourceManifest.ps1').read_text(encoding='ascii')
assert "installer\\SOURCE-SHA256SUMS.txt" in new_manifest
reset=(ROOT/'tools/Reset-LatticeVale-CleanHost.ps1').read_text(encoding='ascii')
assert "installer\\Install-LatticeVale.ps1" in reset

landing=(ROOT/'README.md').read_text(encoding='utf-8')
assert '.\\installer\\verify-release.ps1' in landing
assert '.\\installer\\Install-LatticeVale.ps1' in landing
assert '.\\installer\\Uninstall-LatticeVale.ps1' in landing
full=(DOCS/'README.md').read_text(encoding='utf-8')
assert 'Release layout (v14.4.1+)' in full
assert '.\\installer\\Install-LatticeVale.ps1' in full
assert 'single top-level folder is always named `Lattice-Vale`' in full
release=(DOCS/'RELEASE.md').read_text(encoding='utf-8')
assert 'exactly one top-level folder named `Lattice-Vale`' in release
print('v14.4.1 release layout fixtures: PASS')
