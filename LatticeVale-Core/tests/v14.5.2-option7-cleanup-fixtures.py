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

# TRIM is root-filesystem-only and nonfatal if unsupported; VHDX mutation is explicitly out of scope.
assert 'fstrim -v /' in cleanup
assert 'TRIM/discard report:' in cleanup
assert 'logical unused filesystem extent space' in cleanup
assert 'it is NOT the amount of Windows host-partition space reclaimed' in cleanup
assert 'deliberately does not resize, move, mount, or compact the VHDX itself.' in cleanup.replace('\n', ' ')


# Successful cleanup now proves the safety promise with a before/after protected-identity
# snapshot. The verification intentionally checks preservation of pre-existing identities,
# not mutable database/log contents.
for needle in (
    'snapshot_protected_state "$SAFETY_DIR/before"',
    'snapshot_protected_state "$SAFETY_DIR/after"',
    'POST-CLEANUP PROTECTED-STATE VERIFICATION',
    'installer/config identity preserved',
    'persistent LatticeVale roots preserved',
    'user/unverified backup identities preserved',
    'pre-existing Ollama model manifests preserved',
    'Docker container identities preserved',
    'Docker volumes preserved',
    'Docker networks preserved',
    'tagged Docker image identities preserved',
    'Cleanup safety verification: PASS',
    'LATTICEVALE_CLEANUP_INTEGRITY_FAILED',
):
    assert needle in cleanup, needle

# ext-family statfs naming is normalized for display without weakening the Linux-native
# filesystem admission check.
assert "function Format-LinuxNativeFilesystemLabel" in ps
assert "if ($FsType -eq 'ext2/ext3') { return 'ext-family (Linux-native; statfs reports ext2/ext3)' }" in ps
assert 'Linux home filesystem: $linuxHomeFsDisplay - OK' in ps

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
        assert 'POST-CLEANUP PROTECTED-STATE VERIFICATION' in result.stdout, result.stdout
        assert 'Cleanup safety verification: PASS' in result.stdout, result.stdout
        assert not good.exists(), result.stdout
        assert unverified.is_dir(), result.stdout
        assert (unverified / 'keep-me').read_text(encoding='utf-8') == 'preserve'

    # Negative regression: mutate a protected file between the helper's AFTER display and
    # its protected-state resnapshot. The production helper must detect the changed identity
    # and return nonzero instead of printing a successful cleanup result. This is done by
    # instrumenting a temporary copy of the helper; production source has no test-only hook.
    with tempfile.TemporaryDirectory(prefix='latticevale-option7-integrity-fixture-') as td:
        td = Path(td)
        stack = td / 'hermes-stack'
        stack.mkdir()
        (stack / 'install-options.json').write_text(json.dumps({'installerVersion': '14.5.2'}), encoding='utf-8')
        (stack / '.installer-state.json').write_text(json.dumps({'installerVersion': '14.5.2'}), encoding='utf-8')
        (stack / 'compose.yaml').write_text('services: {}\n', encoding='utf-8')
        instrumented = td / 'cleanup-storage-mutated.sh'
        instrumented_text = cleanup.replace(
            "echo '--- AFTER ---'\nshow_state\nsnapshot_protected_state \"$SAFETY_DIR/after\"",
            "echo '--- AFTER ---'\nshow_state\nprintf '# fixture mutation\n' >> compose.yaml\nsnapshot_protected_state \"$SAFETY_DIR/after\"",
            1,
        )
        assert instrumented_text != cleanup
        instrumented.write_text(instrumented_text, encoding='utf-8')
        instrumented.chmod(0o755)
        result = subprocess.run(
            [str(instrumented), str(stack), 'preupdate-backups'],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
        assert result.returncode != 0, result.stdout
        assert 'FAIL  installer/config identity preserved' in result.stdout, result.stdout
        assert 'LATTICEVALE_CLEANUP_INTEGRITY_FAILED' in result.stdout, result.stdout
        assert 'Cleanup safety verification: PASS' not in result.stdout, result.stdout

print('v14.5.2 OPTION 7 CLEANUP FIXTURES: PASS')
