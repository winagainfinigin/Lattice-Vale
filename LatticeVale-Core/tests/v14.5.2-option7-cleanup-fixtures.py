#!/usr/bin/env python3
from pathlib import Path
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
cleanup = (ROOT / 'linux/cleanup-storage.sh').read_text(encoding='utf-8')

# The existing six modes remain in the same order/wording; Cleanup is additive #7.
existing = [
    'Resume / repair installation - recommended; reuse previous choices and repair failed/incomplete/stale stages (targeted managed software also refreshes when the periodic window is due)',
    'Change installed components - reuse the stack but choose options again',
    'Verify installation only - read-only audit; make no changes',
    'Reconfigure providers/profiles - keep services/data but rerun Hermes provider setup',
    'Advanced recovery - reset checkpoints or explicitly rebuild installer-owned identities',
    "Update / repair installer-managed software - force this bundle''s declared component versions/channels and managed package/image/source layer now, then run normal repair",
    'Cleanup / reclaim disk space - choose safe cleanup categories without changing the current LatticeVale runtime/data configuration',
]
pos = [ps.index(x) for x in existing]
assert pos == sorted(pos)
assert "$installMode = 'cleanup'" in ps
assert 'linux\\cleanup-storage.sh' in ps

# Cleanup is terminal/isolated and does not join mutating repair mode lists.
cleanup_case = ps[ps.index("            7 {\n                $installMode = 'cleanup'"):ps.index("    'absent' { }")]
assert 'Invoke-LatticeValeCleanupMaintenance' in cleanup_case
assert 'exit 0' in cleanup_case
assert "$repairMaintenance = ($stackState -eq 'managed' -and $installMode -in @('resume','change','reconfigure','advanced','update'))" in ps
assert "@('resume','change','reconfigure','advanced','update')) -and $null -ne $existingOptions" in ps
assert "'cleanup'" not in ps[ps.index('$repairMaintenance = ($stackState'):ps.index('$dockerConflicts =')]

# Low-space managed installs may reach only verify/cleanup; ordinary fresh/unrecognized
# storage policy is reasserted after the Linux user/stack owner is known.
for needle in (
    'ManagedCleanupEligible = $false',
    "$storageCleanupBlockers = @('STORAGE_FREE_LOW','STORAGE_TOTAL_LOW')",
    "$result.StorageStatus = 'CLEANUP ONLY'",
    'Verify and Cleanup remain available',
    "if ($stackState -ne 'managed')",
    'cleanup-only storage exception does not apply',
    'Rerun the installer and choose Cleanup / reclaim disk space (Option 7)',
):
    assert needle in ps, needle

# The helper validates active managed intent before deleting any recovery backup.
for needle in (
    "for required in install-options.json .installer-state.json compose.yaml",
    "[[ -f \"$required\" && ! -L \"$required\" ]]",
    "^pre-update-[0-9]{8}T[0-9]{6}Z-[0-9]+$",
    "LatticeVale pre-update safety backup",
    'grep -Fxq -- "stack=$STACK" "$info"',
    "find backups -mindepth 1 -maxdepth 1 -type d -name 'pre-update-*'",
):
    assert needle in cleanup, needle

# Every cleanup category is non-runtime/non-persistent. In particular, image cleanup is
# dangling-only and build cache prune deliberately omits --all/-a.
assert 'docker image prune -f' in cleanup
assert 'docker builder prune -f' in cleanup
for forbidden in (
    'docker image prune -a',
    'docker image prune --all',
    'docker builder prune -a',
    'docker builder prune --all',
    'docker system prune',
    'docker container prune',
    'docker network prune',
    'docker volume prune',
    'docker compose down',
    'docker compose rm',
    'rm -rf data/',
    'rm -rf -- data/',
    'rm -rf vault',
    'rm -rf workspace',
    'ollama rm',
    'Optimize-VHD',
    'compact vdisk',
    'wsl --manage',
):
    assert forbidden not in cleanup, forbidden

# Linux-native filesystem status remains normalized through the compatibility formatter.
assert "function Format-LinuxNativeFilesystemLabel" in ps
assert "Format-LinuxNativeFilesystemLabel $linuxHomeFs" in ps

# TRIM is root-filesystem-only and nonfatal if unsupported; VHDX mutation is explicitly out of scope.
assert 'fstrim -v /' in cleanup
# The safety contract is behavioral rather than tied to a specific explanatory sentence.
# VHDX resize/move/compact tooling is already rejected above; root fstrim remains required.

# Staging deletion is narrowly named, root-owned and aged; APT only cleans downloaded cache.
assert "-mmin +60 -print0" in cleanup
assert '[[ "$uid" == 0 ]]' in cleanup
assert 'apt-get clean' in cleanup
assert 'apt-get autoremove' not in cleanup


# Dynamic ownership-gating regression: a proven pre-update backup is removed, while a
# backup-like directory lacking exact ownership metadata is preserved. This exercises the
# actual cleanup helper rather than only its source text. Run only where the fixture has
# root privileges because the production helper intentionally requires WSL root.
if hasattr(os, 'geteuid') and os.geteuid() == 0:
    with tempfile.TemporaryDirectory(prefix='latticevale-option7-fixture-') as td:
        stack = Path(td) / 'hermes-stack'
        backups = stack / 'backups'
        backups.mkdir(parents=True)
        (stack / 'install-options.json').write_text(json.dumps({'installerVersion': '14.5.2'}), encoding='utf-8')
        (stack / '.installer-state.json').write_text(json.dumps({'installerVersion': '14.5.2'}), encoding='utf-8')
        (stack / 'compose.yaml').write_text('services: {}\n', encoding='utf-8')

        good = backups / 'pre-update-20260829T010203Z-1234'
        good.mkdir()
        (good / 'BACKUP-INFO.txt').write_text(
            'LatticeVale pre-update safety backup\n'
            f'created_utc=20260829T010203Z\nstack={stack}\n',
            encoding='utf-8',
        )
        (good / 'files.tar.gz').write_bytes(b'fixture')

        unverified = backups / 'pre-update-20260829T010204Z-1235'
        unverified.mkdir()
        (unverified / 'BACKUP-INFO.txt').write_text(
            'user-created backup\n'
            f'stack={stack}\n',
            encoding='utf-8',
        )
        (unverified / 'keep-me').write_text('preserve', encoding='utf-8')

        result = subprocess.run(
            [str(ROOT / 'linux/cleanup-storage.sh'), str(stack), 'preupdate-backups'],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stdout
        assert not good.exists(), result.stdout
        assert unverified.is_dir(), result.stdout
        assert (unverified / 'keep-me').read_text(encoding='utf-8') == 'preserve'

print('v14.5.2 OPTION 7 CLEANUP FIXTURES: PASS')
