#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()
assert version in {'14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}, version
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')

# Matrix-enabled secondary profiles preserve a valid provisioning transaction even when
# live Hermes activation is temporarily pending. Pending activation must be retryable,
# visible, and non-fatal to the core stack.
for token in (
    'LATTICEVALE_PROVISIONING_STATE pending-manual',
    'MATRIX_SETUP_STATUS=$provisioning_state',
    'MATRIX-SECONDARY-PROFILES.txt',
    './manage.sh matrix-profile-finish "$name"',
    'Activating Matrix communication for Hermes profile',
    "Profile '$name' Matrix communication is active.",
    'start_or_restart_profile_gateway_exact "$name"',
):
    assert token in cfg, token

mp=cfg[cfg.index('stage_matrix_profiles() ('):cfg.index('stage_matrix_profile_cross_signing()')]
assert 'automatic Hermes activation is still pending' in mp
assert 'continue' in mp[mp.index('automatic Hermes activation is still pending'):], 'retryable Matrix activation must not fail the core install'
assert 'Status: pending-manual' in mp

# The Matrix-profile stage verifies the protected resource transaction. Pending activation
# is accepted only after identity/model/room/token verification, while Resume / repair is
# explicitly forced back through the stage until the finisher succeeds.
verify=cfg[cfg.index('verify_matrix_profiles()'):cfg.index('verify_matrix_profile_cross_signing()')]
assert 'if [[ "$provisioning_state" == pending-manual ]]' in verify
pending_start=verify.index('if [[ "$provisioning_state" == pending-manual ]]')
pending_end=verify.index('    fi', pending_start) + len('    fi')
pending=verify[pending_start:pending_end]
assert 'continue' in pending and 'return 1' not in pending
# Live room-version and membership verification remain strict only after the pending
# branch has continued to the next profile.
assert pending_start < verify.index('room_version="$(matrix_room_version', pending_end)
assert '[[ "$setup_status" == "$provisioning_state" ]] || return 1' in verify
assert 'matrix_profile_activation_pending()' in cfg
assert 'matrix_profiles) matrix_profile_activation_pending ;;' in cfg
assert '[[ "$gateway_state" == up ]] || return 1' not in verify

# The exact manual finisher remains as the bounded recovery primitive and is now invoked
# automatically by the installer stage.
for token in (
    'matrix-profile-finish PROFILE',
    'finish_matrix_profile()',
    'ensure_matrix_online_manage',
    'wait_profile_gateway_up_exact',
    'LATTICEVALE_PROVISIONING_STATE complete',
    'refresh_matrix_profile_handoff',
):
    assert token in manage, token

for script in (ROOT/'stack/configure-stack.sh', ROOT/'stack/manage.sh'):
    r=subprocess.run(['bash','-n',str(script)],capture_output=True,text=True)
    assert r.returncode == 0, r.stderr

print('v14.3.9 secondary Matrix manual-handoff fixtures: PASS')
