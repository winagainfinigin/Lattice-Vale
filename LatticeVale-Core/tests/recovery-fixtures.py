#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text()
cfg=(ROOT/'stack/configure-stack.sh').read_text()
boot=(ROOT/'linux/bootstrap.sh').read_text()
manage=(ROOT/'stack/manage.sh').read_text()

# PowerShell front-end modes.
for text in ('Resume / repair installation','Change installed components','Verify installation only','Reconfigure providers/profiles','Advanced recovery'):
    assert text in ps, text
assert "$installMode = 'resume'" in ps
assert 'Get-ExistingInstallOptions' in ps
assert 'Invoke-BundledStackAudit' in ps
assert 'Show-WindowsRecoveryAudit' in ps
assert 'Get-WindowsTailscaleServePortState' in ps[ps.index('function Show-WindowsRecoveryAudit'):]
assert "exit 0" in ps[ps.index("$installMode = 'verify'"):ps.index("$installMode = 'reconfigure'")]

# State/checkpoint design: marker AND live verifier are required to skip.
assert 'trap on_interrupt INT TERM' in cfg
assert 'installer interrupted by user/system signal' in cfg
assert 'STATE_FILE=".installer-state.json"' in cfg
assert 'state_stage_current "$stage" && "$verifier"' in cfg
assert 'post-stage verification failed' in cfg
assert "d['status']='failed'" in cfg
assert "d['status']='complete'" in cfg
# Transient recovery controls must not change the stable options hash.
hash_block=cfg[cfg.index("for k in ('installerVersion'"):cfg.index('payload=json.dumps')]
for key in ('installerVersion','installerMode','resetCheckpoints','forceProviderSetup','forceProfileSetup','rebuildMatrixIdentity'):
    assert key in hash_block

# Canonical stage sequence.
stages=['prepare_config','infrastructure','matrix_bootstrap','provider_setup','profiles','integrations','reconcile','kanban_gateway','finalize']
pos=[cfg.index(f'run_stage {x} ') for x in stages]
assert pos==sorted(pos)
# Every stage action must explicitly return success after optional false conditions; otherwise
# a trailing `[[ option == true ]] && ...` can make a healthy stage fail with status 1.
for i,stage in enumerate(stages):
    start=cfg.index(f'stage_{stage}() {{')
    end=cfg.index(f'stage_{stages[i+1]}() {{',start) if i+1<len(stages) else cfg.index('# Canonical resumable sequence',start)
    assert '\nreturn 0\n}' in cfg[start:end], stage
assert cfg.index('run_stage matrix_bootstrap ') < cfg.index('run_stage provider_setup ')

# Advanced Matrix recovery is explicit and backups identity metadata first.
assert 'rebuildMatrixIdentity' in ps and 'rebuildMatrixIdentity' in cfg
assert 'backups/matrix-identity-' in cfg
assert 'hermes_recovery_' in cfg
assert 'Automatic identity replacement is unsafe.' in cfg

# Pre-change backup + audit commands.
assert 'installer-config.tar.gz' in boot
assert 'state-audit.py' in boot
assert 'audit) python3 ./state-audit.py --stack . ;;' in manage
assert 'repair-info)' in manage
assert 'logs/installer-events.jsonl' in cfg

# Verifiers must fail closed: an earlier selected service failure cannot be masked by a later disabled service.
for line in (
    'wait_http SearXNG http://127.0.0.1:${SEARXNG_HOST_PORT}/ 1 || return 1',
    'qmd_health_ok || return 1',
    'wait_http Honcho http://127.0.0.1:${HONCHO_HOST_PORT}/health 1 || return 1',
    'matrix_client_api_ready || return 1',
    'matrix_backend_ready_from_hermes || return 1',
):
    assert line in cfg, line

# Docker recovery skips package surgery only when all official Docker Ubuntu packages are present.
assert 'docker_required_packages=(docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin)' in boot
assert 'for pkg in "${docker_required_packages[@]}"' in boot
assert 'docker_packages_ready=false' in boot

# Windows stages are persisted as recovery hints after live reconciliation.
assert 'Set-InstallerWindowsState' in ps
for key in ('windowsApps','tailscale','autoStart'):
    assert f'{key} = @{{ status =' in ps

# Explicit Matrix identity rebuild creates a new admin name as well as a new bot, preserving old users.
assert 'matrix_admin_default="${recovery_owner}_recovery_$recovery_suffix"' in cfg

# No distro creation/conversion is reintroduced.
low=ps.lower()
for forbidden in ('wsl --install','wsl.exe --install','wsl --import','wsl.exe --import','--unregister','--set-version'):
    assert forbidden not in low, forbidden

print('RECOVERY FIXTURES: PASS')
print('- five startup modes present')
print('- checkpoints require live verification')
print('- canonical resumable stage order enforced')
print('- explicit Matrix identity recovery is backup-first')
