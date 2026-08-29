#!/usr/bin/env python3
from pathlib import Path
import re, subprocess, tempfile, textwrap

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()
assert version in {'14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}, version
cfg = (ROOT / 'stack' / 'configure-stack.sh').read_text(encoding='utf-8')

# Fixed installer-owned Matrix room policy.
assert 'LATTICEVALE_MATRIX_ROOM_VERSION=10' in cfg
assert "cfg['default_room_version']='10'" in cfg
assert 'matrix_require_room_v10()' in cfg
assert '/_matrix/client/v3/capabilities' in cfg
assert '.capabilities["m.room_versions"].available[$v]' in cfg

# Matrix must be brought online and its Client-Server API proven healthy before
# default/profile room work. A Docker container merely existing is insufficient.
assert 'matrix_client_api_ready()' in cfg
assert '/_matrix/client/versions' in cfg
assert 'ensure_matrix_online()' in cfg
assert 'docker compose up -d --pull never --no-build synapse-db synapse' in cfg
for stage, terminator in (('stage_matrix_bootstrap()', '\n}\n'), ('stage_matrix_profiles()', '\n)\n')):
    start = cfg.index(stage)
    end = cfg.find(terminator, start)
    body = cfg[start:end if end != -1 else len(cfg)]
    assert 'ensure_matrix_online' in body, stage

# Both the default managed room and per-profile managed rooms must explicitly
# request v10; never inherit Synapse's ambient default.
assert cfg.count('room_version:$rv') >= 3, cfg.count('room_version:$rv')
assert cfg.count('created_room_version="$(matrix_room_version') >= 1
assert 'replacement_version="$(matrix_room_version' in cfg

# Existing installer-managed non-v10 rooms are preserved, backed up, and replaced;
# identity/token recreation is not required for a room-version migration.
assert 'MATRIX_PREVIOUS_ROOM' in cfg
assert 'backups/matrix-room-v10-' in cfg
assert 'backups/matrix-profile-room-v10-' in cfg
assert 'Matrix rooms cannot be downgraded in place.' in cfg
assert 'Do not recreate users or rotate tokens.' in cfg

# v14.3.8 used installer-blocking auto-join verification. Current hotfix behavior keeps
# resumable pending state but automatically runs the bounded profile finisher so a
# selected installer-created Matrix room is not left with a stopped profile gateway.
assert '/_matrix/client/v3/join/$encoded_room' not in cfg
assert '/_matrix/client/v3/joined_rooms' in cfg
if version == '14.3.8':
    assert 'wait_matrix_room_join()' in cfg
    assert 'failures >= 3' in cfg
    assert 'stop_profile_gateway_after_matrix_failure "$name"' in cfg
    assert 'retry this profile once automatically' in cfg
else:
    assert 'LATTICEVALE_PROVISIONING_STATE pending-manual' in cfg
    assert './manage.sh matrix-profile-finish "$name"' in cfg
    assert 'Activating Matrix communication for Hermes profile' in cfg
    assert 'start_or_restart_profile_gateway_exact "$name"' in cfg

print('v14.3.8 Matrix v10/online-order fixtures: PASS')
