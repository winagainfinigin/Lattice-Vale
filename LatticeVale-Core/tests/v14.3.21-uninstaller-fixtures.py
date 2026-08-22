#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT.parent
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82'}
entry=(RELEASE/'installer/uninstall.ps1').read_text(encoding='ascii')
un=(ROOT/'Uninstall-LatticeVale.ps1').read_text(encoding='ascii')
install=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')

# First-party entry point mirrors install.ps1 release verification and requires the
# administrator-only core implementation to be present in the exact source manifest.
assert 'Test-LatticeValeSourceManifest' in entry
assert "LatticeVale-Core\\Uninstall-LatticeVale.ps1" in entry
assert '#Requires -RunAsAdministrator' in un
assert "[string]$DistroName = ''" in un and "[string]$LinuxUser = ''" in un

# A one-item fallback distro list must remain an array. PowerShell otherwise unwraps
# the single string and `$shown[0]` becomes the first character of the distro name.
assert "if ($candidates.Count -gt 0) { $shown=@($candidates) } else { $shown=@($distros) }" in un
assert "return $shown[$choice-1]" in un
assert "$shown=if ($candidates.Count -gt 0) {@($candidates)} else {$distros}" not in un

# Existing WSL is a prerequisite/host, never something the uninstaller may destroy.
assert 'never unregisters the WSL distro' in un
assert '--unregister' not in un.lower()
assert 'wsl --unregister' not in un.lower()

# Default mode is data-preserving. Destructive deletion has an exact secondary
# confirmation and a narrow Linux-native path/symlink/mountpoint gate.
assert 'PRESERVE ~/hermes-stack data for reinstall/recovery' in un
assert "'FULL PURGE: remove LatticeVale runtime/integrations AND permanently delete ~/hermes-stack data'" in un
assert 'Type PURGE to permanently delete the LatticeVale stack data' in un
assert "if ($confirm -cne 'PURGE')" in un
assert ('expected="${HOME%/}/hermes-stack"' in un) if version in {'14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82'} else ('case "$stack" in /home/*/hermes-stack)' in un)
assert 'Refusing to purge symlink stack' in un
assert 'Refusing to purge mountpoint stack' in un
assert 'rm -rf --one-file-system -- "$stack"' in un

# Runtime cleanup is scoped to the selected Compose project and installer-owned
# Windows artifacts; unknown same-name tasks/shortcuts are preserved.
assert 'docker compose down --remove-orphans' in un
assert 'Stack data was preserved' in un
assert 'Refusing to purge stack containing nested mountpoint' in un
assert './native-ollama-relay.sh stop' in un
assert 'function Remove-TaskIfOwned' in un and 'not provably LatticeVale-owned; it was left untouched' in un
assert 'function Test-ShortcutOwned' in un
assert "Get-NetFirewallRule -Group 'LatticeVale'" in un
assert 'LatticeValeNativeBridge-HyperV-' in un
assert 'function Restore-DirectOllamaState' in un
assert "if ([string]$current -eq [string]$s.configuredHost)" in un
assert 'OLLAMA_HOST no longer matches the installer-owned value' in un

# Preserve-data mode deliberately clears stale Windows-integration metadata while
# retaining application/service data for a later reinstall/repair.
assert 'function Mark-PreservedStackUninstalled' in un
assert '.latticevale-uninstalled' in un
assert '.tailscale-info' in un and '.windows-native-info' in un

# Shared prerequisites/apps are never blindly removed. Global WSL config rollback is
# opt-in because later user edits cannot be proven installer-owned.
for forbidden in ('apt-get remove','apt-get purge','winget uninstall','Uninstall-Package'):
    assert forbidden.lower() not in un.lower()
assert 'Docker Engine/packages' in un and 'Windows Ollama/Tailscale/Obsidian apps' in un
assert 'Offer-WslConfigRestore' in un
assert 'could overwrite later manual changes' in un
assert "Read-YesNo \"Restore the newest pre-LatticeVale .wslconfig backup" in un and '$false' in un
assert 'external Windows-backed Obsidian vaults' in un

# The uninstaller remains additive. v14.3.41 intentionally removes the installer-side
# mirrored-network mutation while preserving every install/uninstall entry point.
if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82'}:
    assert 'Resolve-LatticeValeNativeOllamaMirroredFallback' not in install
    assert 'Set-WslGlobalNetworkingModeValue' not in install
else:
    assert 'Resolve-LatticeValeNativeOllamaMirroredFallback' in install
assert (RELEASE/'installer/install.ps1').is_file()

print('v14.3.21 uninstaller fixtures: PASS')
