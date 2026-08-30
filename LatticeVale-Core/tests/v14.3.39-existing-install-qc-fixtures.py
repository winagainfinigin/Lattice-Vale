#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.40', '14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'}, version
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')

# Six existing-managed-stack modes remain distinct.
for text in (
    'Resume / repair installation - recommended',
    'Change installed components - reuse the stack but choose options again',
    'Verify installation only - read-only audit; make no changes',
    'Reconfigure providers/profiles - keep services/data but rerun Hermes provider setup',
    'Advanced recovery - reset checkpoints or explicitly rebuild installer-owned identities',
    'Update / repair installer-managed software - force this bundle',
): assert text in ps
for mode in ("$installMode = 'resume'", "$installMode = 'change'", "$installMode = 'verify'", "$installMode = 'reconfigure'", "$installMode = 'advanced'", "$installMode = 'update'"):
    assert mode in ps

# Verify-only exits before repair staging/bootstrap and is excluded from mutating maintenance.
verify_idx=ps.index("$installMode = 'verify'")
verify_exit=ps.index('exit 0', verify_idx)
bootstrap_idx=ps.index("Write-Step 'Final existing-distro verification'")
assert verify_idx < verify_exit < bootstrap_idx
assert "$installMode -in @('resume','change','reconfigure','advanced','update')" in ps

# Scoped change mode preserves unselected settings and persistent data.
assert 'Only these categories will be changed:' in ps
assert 'Everything else remains exactly as saved.' in ps
assert 'existing cards are not deleted' in ps
assert 'existing Synapse data is not deliberately deleted' in ps
assert 'existing notes/vault data are preserved' in ps

# Reconfigure and advanced controls are explicit and transient, not checkpoint identity.
assert "$installMode = 'reconfigure'" in ps
assert '$forceProviderSetup = $true' in ps and '$forceProfileSetup = $true' in ps
assert '$rebuildMatrixIdentity = $true' in ps and '$resetCheckpoints = $true' in ps
for key in ('installerMode','resetCheckpoints','forceProviderSetup','forceProfileSetup','rebuildMatrixIdentity','repairMaintenance','forceManagedUpdate'):
    assert repr(key) in cfg or f"'{key}'" in cfg

# Matrix identity rebuild makes a targeted backup before removing installer routing metadata.
backup=cfg.index('recovery_dir="backups/matrix-identity-')
copy=cfg.index('cp -a "$f" "$recovery_dir/"', backup)
bootstrap=cfg.index('MATRIX_BOT_DEVICE_ID=$matrix_bot_device_id', copy)
remove=cfg.index('rm -f secrets/matrix-bot.env .matrix-info .matrix-configured', bootstrap)
assert backup < copy < bootstrap < remove
assert "Only the installer-owned default bot/device/room will be replaced." in cfg
assert 'cp -a data/hermes/platforms/matrix/store "$recovery_dir/matrix-store"' in cfg
assert '[[ ! -e .matrix-identity-rebuild-pending ]] || return 1' in cfg

# Update/repair must back up before the Linux staging/bootstrap path begins.
backup_idx=ps.index("Write-Step 'Creating pre-update managed-stack safety backup'")
stage_idx=ps.index('$stageLinux = "/tmp/$stageName"', backup_idx)
assert backup_idx < stage_idx
backup_block=ps[backup_idx:stage_idx]
assert 'pre-update-safety-backup.sh' in backup_block
assert './manage.sh backup' not in backup_block
assert 'No installer-managed software refresh was started' in backup_block

# Component removal may remove only selected LatticeVale containers; persistent data stays.
assert 'If a previously selected optional service is now disabled, stop/remove only its containers. Persistent data is retained.' in cfg
for forbidden in ('rm -rf data/synapse', 'rm -rf data/synapse-db', 'rm -rf data/honcho', 'docker compose down -v', 'docker volume prune'):
    assert forbidden not in cfg
# Advanced explicit Matrix identity rebuild may replace only its default crypto-store subtree;
# broad Hermes persistent-data deletion remains forbidden.
assert not any(line.strip() in {'rm -rf data/hermes','rm -rf data/hermes/'} for line in cfg.splitlines())

# Automatic repair must not mutate Docker Engine-global cache belonging to other projects.
for forbidden in ('docker image prune -f', 'docker builder prune', 'docker system prune', 'docker container prune', 'docker network prune', 'docker volume prune'):
    assert forbidden not in cfg
assert 'engine-global Docker images and build cache untouched' in cfg

# Safe owner-specific repair remains present.
assert 'prune_old_installer_config_backups' in cfg
assert 'cap_installer_event_log' in cfg
assert 'APT cache and stale LatticeVale staging' in boot or 'stale LatticeVale staging' in boot

print('v14.3.40 existing-install QC fixtures: PASS')
