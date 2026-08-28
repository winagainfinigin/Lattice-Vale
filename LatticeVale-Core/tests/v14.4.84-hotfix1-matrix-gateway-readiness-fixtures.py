#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
version=(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()
assert version == '14.4.84', 'Hotfix 1 intentionally keeps the public 14.4.84 version number'

# The observed regression was: Synapse unavailable/Docker DNS not ready, gateway process
# stays alive, audit reports RUNNING, Element loses communication. Probe from the actual
# Hermes container, not merely localhost on WSL.
for token in (
    'matrix_backend_ready_from_hermes_manage',
    'wait_matrix_backend_from_hermes_manage',
    '/_matrix/client/versions',
    'socket.getaddrinfo("synapse", 8008)',
    'ensure_matrix_server_online_manage',
    'ensure_matrix_runtime_online_manage',
):
    assert token in manage, token

case_root=manage.index('case "$cmd" in')
case_start=manage.index('  start)', case_root)
case_end=manage.index('  stop)', case_start)
start=manage[case_start:case_end]
assert start.index('ensure_matrix_server_online_manage') < start.index('docker compose up -d --pull never --no-build') < start.index('start_selected_matrix_profile_gateways')

# A gateway that is already UP must be recycled after backend readiness; merely seeing
# an s6 process is no longer treated as connectivity.
reconcile=manage[manage.index('reconcile_profile_gateway_exact_manage()'):manage.index('stop_profile_gateway_exact_manage()')]
assert 'up) action=restart' in reconcile
assert 'down) action=start' in reconcile
assert 'gateway "$action"' in reconcile
assert '/command/s6-svc -r "$service"' in reconcile
assert '/command/s6-svc -U "$service"' in reconcile

default=manage[manage.index('reconcile_default_gateway_manage()'):manage.index('reconcile_profile_gateway_exact_manage()')]
assert 'up) action=restart' in default
assert 'hermes gateway "$action"' in default
assert '/run/service/gateway-default' in default

selected=manage[manage.index('start_selected_matrix_profile_gateways()'):manage.index('refresh_adaptive_resource_policy()')]
assert selected.index('ensure_matrix_runtime_online_manage') < selected.index('reconcile_default_gateway_manage')
assert 'reconcile_profile_gateway_exact_manage "$name"' in selected
assert 'Profile gateway running with Matrix backend verified' in selected

# Fresh install + repair final reconciliation both use configure-stack.sh. It must start
# Synapse first, then prove in-container reachability and recycle the default gateway.
stage=cfg[cfg.index('stage_reconcile()'):cfg.index('stage_kanban_gateway()')]
assert stage.index('ensure_matrix_online 60') < stage.index('docker compose up -d --pull never --no-build --remove-orphans')
assert stage.index('wait_matrix_backend_from_hermes 60') < stage.index('hermes gateway restart')
kanban=cfg[cfg.index('stage_kanban_gateway()'):cfg.index('stage_finalize()')]
assert 'ensure_matrix_online 60' in kanban
assert 'wait_matrix_backend_from_hermes 60' in kanban
checkpoint=cfg[cfg.index('checkpoint_revision()'):cfg.index('matrix_profile_activation_pending()')]
assert "kanban_gateway) printf '3'" in checkpoint
assert "reconcile) printf '2'" in checkpoint

# Audit must stop claiming RUNNING when only the gateway process is alive.
assert 'matrix_backend_reachable_from_hermes' in audit
assert "Synapse is not reachable from inside hermes-agent" in audit
assert 'gateway process is running but Synapse is unreachable from inside hermes-agent' in audit
assert 'gateway_running and matrix_internal_ready' in audit
assert 'matrix_status == "STARTING" or is_settling(hermes_state)' in audit
assert '"${2:-}" == synapse || "${2:-}" == synapse-db' in manage

for script in (ROOT/'stack/manage.sh', ROOT/'stack/configure-stack.sh'):
    r=subprocess.run(['bash','-n',str(script)],capture_output=True,text=True)
    assert r.returncode == 0, r.stderr
compile((ROOT/'stack/state-audit.py').read_text(encoding='utf-8'), str(ROOT/'stack/state-audit.py'), 'exec')
print('v14.4.84 HOTFIX 1 MATRIX GATEWAY READINESS FIXTURES: PASS')
