#!/usr/bin/env python3
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')

# Option 2: preserve per-profile Matrix intent when the shared service is disabled.
assert '$matrixEnabled = if ($hasMatrixSetting) { [bool](Get-OptionValue $matrixExisting \'enabled\' $false) } else { $false }' in ps
assert '$GlobalMatrixEnabled -and -not $hasMatrixSetting -and $PromptOnMissing' in ps

# Option 2: turning off installer-owned local Ollama must force an actual provider choice.
for needle in (
    '$wasHermesLocalAI = $hermesLocalAI',
    'if ($wasHermesLocalAI -and -not $hermesLocalAI)',
    '$forceProviderSetup = $true',
    'provider/model wizard',
):
    assert needle in ps, needle

# Option 2: selected component changes normalize only now-impossible Tailscale dependencies.
assert 'if (-not $dashboard -and $tailscaleDashboard)' in ps
assert 'if (-not $matrix -and $tailscaleMatrix)' in ps
assert "No LatticeVale service remains selected for Tailscale exposure" in ps

# Runtime Matrix deactivation must remove live credentials from default + profile envs,
# while leaving protected profile secret stores/rooms intact.
assert 'matrix_runtime_enabled=false' in cfg
assert '[[ "$(opt_bool matrix)" == true ]] && matrix_runtime_enabled=true' in cfg
assert 'remove_env_keys "$f" MATRIX_HOMESERVER MATRIX_ACCESS_TOKEN MATRIX_USER_ID' in cfg
assert "if not enabled and (present & matrix_keys): raise SystemExit(1)" in cfg

# Final gateway reconciliation must stop installer-managed profiles which are no longer
# runtime-enabled and must not start profile Matrix gateways when global Matrix is off.
assert 'stop_profile_gateway_exact "$managed_profile"' in cfg
kanban=cfg[cfg.index('stage_kanban_gateway() {'):cfg.index('\nstage_finalize() {')]
assert 'if [[ "$(opt_bool matrix)" == true ]]; then' in kanban
assert "jq -r '.workers[]? | select(.matrix.enabled == true) | .name' install-options.json" in kanban
start_idx=kanban.index("jq -r '.workers[]? | select(.matrix.enabled == true) | .name' install-options.json")
guard_idx=kanban.rfind('if [[ "$(opt_bool matrix)" == true ]]; then',0,start_idx)
assert guard_idx >= 0 and guard_idx < start_idx

# Option 4 remains a provider/profile reconfiguration, and accurately explains that
# a saved local-Ollama policy is changed through option 2 rather than silently ignored.
assert "$installMode = 'reconfigure'" in ps
assert '$forceProviderSetup = $true' in ps and '$forceProfileSetup = $true' in ps
assert 'Use Change installed components -> Local AI / Honcho / Ollama' in ps

# Advanced recovery: Matrix identity replacement is invalid while shared Matrix is off.
assert 'Advanced Matrix identity rebuild requires the shared Matrix service to be enabled' in ps

# Advanced Matrix identity rebuild must be transactional. Preserve current identity +
# crypto store first; persist unique replacement bootstrap/device second; only then retire
# the old runtime identity/store. Successful completion removes the pending marker.
rebuild_start=cfg.index("rebuild_marker='.matrix-identity-rebuild-pending'")
rebuild_end=cfg.index('\nstage_provider_setup() {',rebuild_start)
rebuild=cfg[rebuild_start:rebuild_end]
backup_secret=rebuild.index('cp -a "$f" "$recovery_dir/"')
backup_store=rebuild.index('cp -a data/hermes/platforms/matrix/store "$recovery_dir/matrix-store"')
marker_write=rebuild.index("printf '%s\\n' \"$recovery_dir\" > \"$rebuild_marker\"")
unique_device=rebuild.index('matrix_bot_device_id="LATTICEVALE_RECOVERY_${recovery_suffix^^}"')
bootstrap_write=rebuild.index('MATRIX_BOT_DEVICE_ID=$matrix_bot_device_id')
retire_secret=rebuild.index('rm -f secrets/matrix-bot.env .matrix-info .matrix-configured')
retire_store=rebuild.index('rm -rf data/hermes/platforms/matrix/store')
cleanup_marker=rebuild.rindex('rm -f "$matrix_bootstrap" "$rebuild_marker"')
assert backup_secret < marker_write < bootstrap_write < retire_secret < cleanup_marker
assert backup_store < bootstrap_write < retire_store < cleanup_marker
assert unique_device < bootstrap_write
assert 'matrix_admin_default="$(read_env_file_value_optional .matrix-info MATRIX_ADMIN)"' in rebuild
assert 'matrix_admin_locked=true' in rebuild
assert "Only the installer-owned default bot/device/room will be replaced." in rebuild
assert 'MATRIX_RECOVERY_KEY MATRIX_RECOVERY_KEY_OUTPUT_FILE' in rebuild
assert '[[ ! -e .matrix-identity-rebuild-pending ]] || return 1' in cfg

# Normal recovery/reset paths must not delete Synapse persistent data.
advanced_menu=ps[ps.index("'Advanced recovery - reset checkpoints or explicitly rebuild installer-owned identities'"):ps.index("'Update / repair installer-managed software - force this bundle''s declared component versions/channels")]
assert 'docker volume rm' not in advanced_menu.lower()
assert 'data/synapse' not in advanced_menu.lower()

print('v14.4.85 EXISTING MENU OPTIONS: PASS')
print('- option 2 preserves profile Matrix intent while deactivating impossible runtime dependencies')
print('- local Ollama -> external provider transition forces the provider wizard')
print('- option 4 semantics remain explicit under saved Local AI policy')
print('- option 5 Matrix identity rebuild is gated, transactional, backed up, and resumable')
