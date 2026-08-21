#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}, version
un=(ROOT/'Uninstall-LatticeVale.ps1').read_text(encoding='ascii')

# Discovery must match the installer's resumable-stack policy, not only final markers.
for marker in ('install-options.json','.installer-state.json','.install-info','.configured'):
    assert marker in un
for core in ('compose.yaml','configure-stack.sh','manage.sh'):
    assert core in un
assert 'backup-metadata' in un
assert 'managed-recovery' in un
assert 'partial-runtime' in un
assert 'Get-HermesStackDiagnostics' in un
assert 'Detected candidate paths:' in un

# Account discovery remains bounded to interactive, non-nobody users; v14.3.29
# performs the checks in PowerShell from direct `getent passwd` output rather than a
# serialized multiline bash probe.
if version in {'14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}:
    assert 'function Get-WslPasswdEntries' in un
    assert "Invoke-Wsl $Name 'root' 'getent' @('passwd')" in un
    assert "$user -eq 'nobody'" in un
    assert "$uid -lt 1000 -or $uid -gt 65534" in un
    assert "$shell -match '(?:nologin|/false)$'" in un
else:
    assert '[ "$uid" -ge 1000 ]' in un and '[ "$uid" -le 65534 ]' in un
    assert '[ "$gid" -ge 1000 ]' in un and '[ "$gid" -le 65534 ]' in un
    assert '[ "$u" != nobody ]' in un
    assert '*nologin|*/false' in un

# Path safety is exact to the selected account, not a broad /home wildcard.
assert 'function Assert-SelectedStackTarget' in un
assert 'expected="${home%/}/hermes-stack"' in un
assert 'Assert-SelectedStackTarget $DistroName $LinuxUser $stack' in un
assert 'expected="${HOME%/}/hermes-stack"' in un
assert 'case "$stack" in /home/*/hermes-stack)' not in un
assert 'Refusing to purge symlink stack' in un
assert 'Refusing to purge mountpoint stack' in un
assert 'Refusing to purge stack containing nested mountpoint' in un

# Other partial stacks protect shared installer-owned Linux policy from removal.
assert '[ -f "$candidate/.installer-state.json" ]' in un
assert '[ -f "$candidate/compose.yaml" ] && [ -f "$candidate/configure-stack.sh" ] && [ -f "$candidate/manage.sh" ]' in un

# The exact old failure should be gone.
assert 'No installer-shaped ~/hermes-stack was found for a normal user' not in un

print('v14.3.28 uninstaller recovery discovery fixtures: PASS')
