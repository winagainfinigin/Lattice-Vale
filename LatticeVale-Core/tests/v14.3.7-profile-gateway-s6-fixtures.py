#!/usr/bin/env python3
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
assert version in {'14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}

# The failure that produced v14.3.7 was caused by trusting Hermes' profile CLI
# status after profile creation. Current Docker Hermes exposes one s6 slot per
# profile, so lifecycle safety must key off that exact slot.
for token in (
    'profile_gateway_s6_state()',
    'profile_gateway_is_running_exact()',
    'quiesce_profile_gateway_for_credential_write()',
    'service="/run/service/gateway-$name"',
    '/command/s6-svstat "$service"',
    '/command/s6-svc -d "$service"',
    '/command/s6-svc -U "/run/service/gateway-$name"',
    'quiesce_profile_gateway_for_credential_write "$name"',
):
    assert token in cfg, token

create=cfg.index('hermes profile create "$name" --description "$desc"')
quiesce=cfg.index('quiesce_profile_gateway_for_credential_write "$name"', create)
clone=cfg.index("PY_PROFILE_SAFE_CLONE", quiesce)
assert create < quiesce < clone

# Do not use profile-blind/process-wide kill patterns. The bounded fallback may
# TERM/KILL only the PID freshly reported by this exact profile's s6 service.
assert "killall" not in cfg
assert "pkill" not in cfg
assert "kill -TERM \"$1\"" in cfg
assert "kill -KILL \"$1\"" in cfg
assert 'current="$(sed -n' in cfg
assert 'if [[ "$current" == "$pid" ]]' in cfg

# Later Matrix verification must use the same exact s6 truth, not a human text
# status line that can be satisfied by another profile gateway.
if version in {'14.3.7','14.3.8'}:
    assert 'profile_gateway_is_running_exact "$name" || return 1' in cfg
    assert "Profile '$name' exact s6 gateway service is not running after Matrix provisioning." in cfg
else:
    assert 'quiesce_profile_gateway_for_credential_write "$name"' in cfg
    assert 'pending-manual' in cfg
assert re.search(r'gateway status[^\n]*grep -qi [\'\"]running', cfg) is None

r=subprocess.run(['bash','-n',str(ROOT/'stack/configure-stack.sh')],capture_output=True,text=True)
assert r.returncode == 0, r.stderr

# Execute the helper against a fake Docker CLI. This covers both the normal
# stop path and the upstream dynamic-s6 race where normal stop/down requests
# report success but the exact service remains up until its exact service PID
# receives TERM. `sleep` is stubbed so the bounded wait loops run instantly.
helper=cfg[cfg.index('profile_gateway_s6_state() {'):cfg.index('verify_profiles() {')]
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    state=td/'state'; log=td/'docker.log'; bindir=td/'bin'; bindir.mkdir()
    (bindir/'sleep').write_text('#!/bin/sh\nexit 0\n',encoding='utf-8')
    (bindir/'docker').write_text(r'''#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_DOCKER_LOG"
args="$*"
case "$args" in
  *s6-svstat*)
    if [ "$(cat "$FAKE_DOCKER_STATE")" = up ]; then
      printf 'up (pid 4242) 1 seconds\n'
    else
      printf 'down (exitcode 0) 1 seconds, normally down\n'
    fi
    exit 0
    ;;
  *"gateway stop"*)
    [ "$FAKE_DOCKER_MODE" = normal ] && printf 'down\n' > "$FAKE_DOCKER_STATE"
    exit 0
    ;;
  *"s6-svc -d"*)
    [ "$FAKE_DOCKER_MODE" = normal ] && printf 'down\n' > "$FAKE_DOCKER_STATE"
    exit 0
    ;;
  *"kill -TERM"*)
    printf 'down\n' > "$FAKE_DOCKER_STATE"
    exit 0
    ;;
  *"kill -KILL"*)
    printf 'down\n' > "$FAKE_DOCKER_STATE"
    exit 0
    ;;
esac
exit 99
''',encoding='utf-8')
    os.chmod(bindir/'docker',0o755); os.chmod(bindir/'sleep',0o755)
    env=os.environ.copy(); env.update({
        'PATH':str(bindir)+os.pathsep+env['PATH'],
        'FAKE_DOCKER_STATE':str(state),
        'FAKE_DOCKER_LOG':str(log),
    })
    script='set -Eeuo pipefail\n'+helper+'\nquiesce_profile_gateway_for_credential_write assistant\n'

    state.write_text('up\n'); log.write_text(''); env['FAKE_DOCKER_MODE']='normal'
    r=subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True,timeout=20)
    assert r.returncode == 0, r.stdout+r.stderr
    assert 'kill -TERM' not in log.read_text()

    state.write_text('up\n'); log.write_text(''); env['FAKE_DOCKER_MODE']='stuck'
    r=subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True,timeout=20)
    assert r.returncode == 0, r.stdout+r.stderr
    calls=log.read_text()
    assert '/run/service/gateway-assistant' in calls
    assert 'kill -TERM' in calls and '4242' in calls
    assert 'kill -KILL' not in calls

print('v14.3.7 exact-profile s6 gateway fixtures: PASS')
