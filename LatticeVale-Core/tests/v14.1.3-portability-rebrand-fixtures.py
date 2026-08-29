#!/usr/bin/env python3
from pathlib import Path
import re

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent

assert (CORE / 'VERSION.txt').read_text(encoding='utf-8').strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}

# Current public-facing source layout is fully LatticeVale-branded.
for rel in (
    'README.md', 'docs/README.md', 'docs/CHANGELOG.md', 'docs/RELEASE.md', 'docs/SECURITY.md', 'docs/SOURCES.md',
    'docs/SUPPORT.md', 'docs/CONTRIBUTING.md', 'docs/Installer Description.txt', 'docs/Instructions.txt',
    'LatticeVale-Core/README.md', 'LatticeVale-Core/AUDIT.md',
):
    text = (ROOT / rel).read_text(encoding='utf-8')
    assert 'LatticeVale' in text, f'{rel} does not identify the current project name'
    assert ('Hermes' + ' Foundry') not in text, f'{rel} contains stale project branding'
    assert ('Hermes' + ' WSL Foundry') not in text, f'{rel} contains stale project branding'

for rel in (
    'LatticeVale-Core/Install-LatticeVale.ps1',
    'LatticeVale-Core/windows/LatticeVale-WslNativeRelay.ps1',
    'LatticeVale-Core/windows/LatticeVale-Shortcut.ps1',
):
    assert (ROOT / rel).is_file(), f'missing renamed source: {rel}'

installer = (CORE / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
configure = (CORE / 'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (CORE / 'stack/manage.sh').read_text(encoding='utf-8')
install = (ROOT / 'installer/Install-LatticeVale.ps1').read_text(encoding='utf-8')
verify = (ROOT / 'installer/verify-release.ps1').read_text(encoding='utf-8')
manifest_module = (ROOT / 'tools/ReleaseManifest.ps1').read_text(encoding='utf-8')

# New project-owned Windows artifacts use neutral current identifiers.
assert "Join-Path $env:LOCALAPPDATA 'LatticeVale'" in installer
assert 'LatticeVale Stack - $safe-$suffix' in installer
assert 'LatticeVale Tailscale Relay -' in installer
assert 'Start LatticeVale -' in installer
assert 'Shut Down LatticeVale -' in installer

# Legacy project strings may remain in the main installer as migration inputs and in the
# explicitly archival, verbatim v13 patch-note directory. Current project-facing docs/code
# must remain LatticeVale-branded.
old_brand_patterns = ('Hermes' + ' Foundry', 'Hermes' + ' WSL Foundry', 'Hermes' + '-Foundry')
legacy_patch_root = ROOT / 'docs' / 'legacy-patch-notes' / 'hermes-wsl-foundry-v13'
for p in ROOT.rglob('*'):
    if not p.is_file() or p.name == 'SOURCE-SHA256SUMS.txt' or '.git' in p.parts or 'tests' in p.parts:
        continue
    if p.suffix.lower() not in {'.ps1', '.sh', '.py', '.md', '.txt', '.yml', '.yaml', '.conf'}:
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    if any(x in text for x in old_brand_patterns):
        if p in {CORE / 'Install-LatticeVale.ps1', ROOT / 'tools' / 'Reset-LatticeVale-CleanHost.ps1'}:
            # Retained old-brand references in executable code must be visibly scoped as
            # legacy/migration compatibility. The clean-host reset intentionally recognizes
            # exact legacy Foundry names so it can remove only proven old integration state.
            for i, line in enumerate(text.splitlines()):
                if any(x in line for x in old_brand_patterns):
                    context='\n'.join(text.splitlines()[max(0,i-24):i+25])
                    assert re.search(r'(?i)legacy|migration|backward|compatib|cleanup|clean-host', context), \
                        f'old brand not scoped as migration compatibility near line {i+1}'
            continue
        try:
            p.relative_to(legacy_patch_root)
        except ValueError:
            raise AssertionError(f'stale brand outside migration code/archive: {p.relative_to(ROOT)}')

# Obsidian Windows-path handling must not assume /mnt and must verify a Windows-backed mount.
assert "'wslpath' @('-a', '-u', $driveRootWindows)" in installer or "'wslpath' @('-a','-u',$driveRootWindows)" in installer
assert 'findmnt' in installer
assert 'findmnt' in configure
assert not re.search(r"StartsWith\(['\"]?/mnt", installer), 'installer still hard-requires /mnt'
assert 'obsidianVaultWslPath' in configure

# Generated project-facing service labels use LatticeVale; repair migrates only the exact historical default.
assert "'instance_name':'LatticeVale Search'" in configure
assert "general.get('instance_name') == 'Hermes Search'" in configure
assert "general['instance_name']='LatticeVale Search'" in configure

# Tailscale inspection checks the effective service configuration as well as status fallback.
assert "@('serve', 'status', '--json')" in installer or "@('serve','status','--json')" in installer
assert "@('serve', 'get-config', '--all')" in installer or "@('serve','get-config','--all')" in installer
assert '$serveArgs' in installer
assert 'foreach ($args' not in installer

# Windows relay control must follow the distro's actual Windows-drive translation rather than assume /mnt/c.
manage = (CORE / 'stack/manage.sh').read_text(encoding='utf-8')
assert r"wslpath -u 'C:\Windows\System32\schtasks.exe'" in manage
assert '/mnt/c/Windows/System32/schtasks.exe' not in manage

# Global .wslconfig changes must not silently stop unrelated running WSL distros.
assert 'function Confirm-LatticeValeGlobalWslRestart' in installer
assert "@('--list','--running','--quiet')" in installer or "@('--list', '--running', '--quiet')" in installer
assert 'Other running distros:' in installer
assert "Read-YesNo 'Continue and temporarily stop all currently running WSL distros" in installer
assert installer.index('Confirm-LatticeValeGlobalWslRestart $DistroName') < installer.index('Set-WslGlobalInstanceIdleTimeoutDisabled $wslLifetime.Path')

# New state uses LatticeVale markers while still reading old marker names for migration.
assert 'LATTICEVALE_PROVISIONING_STATE' in configure
assert 'FOUNDRY_PROVISIONING_STATE' in configure
assert 'LATTICEVALE_OLLAMA_CONTEXT_AUTO' in configure
assert 'FOUNDRY_OLLAMA_CONTEXT_AUTO' in configure
assert 'LATTICEVALE_PROVISIONING_STATE' in manage

# Release entry points are bound to the renamed core source and exact manifest coverage logic.
assert 'LatticeVale-Core\\Install-LatticeVale.ps1' in install
for text in (install, verify):
    assert 'SOURCE-SHA256SUMS.txt' in text
    assert 'tools\\ReleaseManifest.ps1' in text or 'tools/ReleaseManifest.ps1' in text
assert 'duplicate' in manifest_module.lower()
assert 'unexpected' in manifest_module.lower() or 'unmanifested' in manifest_module.lower()

# Stale active source filenames must not exist.
for stale in (
    'LatticeVale-Core/Install-HermesStack.ps1',
    'LatticeVale-Core/windows/Hermes-WslNativeRelay.ps1',
    'LatticeVale-Core/windows/Hermes-Shortcut.ps1',
    'LatticeVale-Core/AUDIT-v14.0.md',
):
    assert not (ROOT / stale).exists(), f'stale active file remains: {stale}'

print('V14.3.0 PORTABILITY/REBRAND FIXTURES: PASS')
