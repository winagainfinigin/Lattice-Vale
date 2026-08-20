#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
cfg = (ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (ROOT/'stack/manage.sh').read_text(encoding='utf-8')
audit = (ROOT/'stack/state-audit.py').read_text(encoding='utf-8')

# The exact regression: stage action says activation failure is non-fatal, therefore its
# verifier must accept the protected pending-manual transaction rather than returning 1.
verify = cfg[cfg.index('verify_matrix_profiles() {'):cfg.index('verify_matrix_profile_cross_signing() {')]
pstart = verify.index('if [[ "$provisioning_state" == pending-manual ]]')
pend = verify.index('    fi', pstart) + len('    fi')
pending = verify[pstart:pend]
assert 'continue' in pending
assert 'return 1' not in pending
assert '[[ "$setup_status" == "$provisioning_state" ]] || return 1' in verify
assert '[[ "$runtime_user" == "$expected_user" ]] || return 1' in verify
# Pending profiles must not perform a live room-version lookup before joining; the
# protected recorded marker is sufficient until activation succeeds.
pending_pos = verify.index('if [[ "$provisioning_state" == pending-manual ]]')
live_room_pos = verify.index('room_version="$(matrix_room_version')
assert pending_pos < live_room_pos

# The installer itself invokes matrix-profile-finish before .configured exists. That
# exact recovery command must therefore be dispatched before the global completion gate.
dispatch_pos = manage.index('if [[ "$cmd" == matrix-profile-finish ]]')
configured_gate_pos = manage.index('\nneed_configured\ncase "$cmd" in')
assert dispatch_pos < configured_gate_pos
assert 'Matrix profile recovery is not staged far enough to run safely' in manage

# Pending must still be retried on every repair despite a valid/done resource checkpoint.
checkpoint = cfg[cfg.index('checkpoint_revision()'):cfg.index('resume_adoption_allowed()')]
assert "matrix_profiles|matrix_profile_cross_signing) printf '3'" in checkpoint
assert 'matrix_profile_activation_pending()' in checkpoint
assert 'matrix_profiles) matrix_profile_activation_pending ;;' in checkpoint
assert 'matrix_profile_cross_signing_pending()' in checkpoint
assert 'matrix_profile_cross_signing) matrix_profile_cross_signing_pending ;;' in checkpoint

# Handoff/final status must say pending, not the transient word "activating".
stage = cfg[cfg.index('stage_matrix_profiles() ('):cfg.index('stage_matrix_profile_cross_signing()')]
assert 'Status: pending-manual' in stage
assert 'Status: activating' not in stage
assert 'automatic Hermes activation is still pending' in stage
assert 'Continuing LatticeVale without failing the core stack' in stage
finalize = cfg[cfg.index('stage_finalize()'):cfg.index('# Lightweight runtime refresh')]
assert "grep -q '^Status: pending-manual$'" in finalize

# Named-profile CLI lifecycle failures get an exact-service fallback only after the slot
# exists. -U intentionally clears a stale persistent down marker left by a prior stop.
helper = cfg[cfg.index('start_or_restart_profile_gateway_exact()'):cfg.index('wait_profile_gateway_down_exact()')]
assert 'gateway "$action"' in helper
assert '/command/s6-svc -U "/run/service/gateway-$name"' in helper
assert '/command/s6-svc -r "/run/service/gateway-$name"' in helper
mhelper = manage[manage.index('start_profile_gateway_exact_manage()'):manage.index('stop_profile_gateway_exact_manage()')]
assert 'profile_gateway_s6_state_exact "$name"' in mhelper
assert '/command/s6-svc -U "$service"' in mhelper

# Secondary cross-signing warnings are also truly non-fatal: explicit pending state is
# accepted by the verifier and forces a future repair retry instead of breaking the install.
xs = cfg[cfg.index('stage_matrix_profile_cross_signing()'):cfg.index('stage_integrations()')]
xv = cfg[cfg.index('verify_matrix_profile_cross_signing()'):cfg.index('verify_integrations()')]
assert 'LATTICEVALE_CROSS_SIGNING_STATE pending' in xs
assert 'LATTICEVALE_CROSS_SIGNING_STATE complete' in xs
assert 'if [[ "$cross_state" == pending ]]' in xv and 'continue' in xv
assert 'LATTICEVALE_CROSS_SIGNING_STATE=pending' in finalize

# Audit must classify retryable security/activation state as configured rather than broken.
assert 'cross_signing_state = env_value(secret, "LATTICEVALE_CROSS_SIGNING_STATE")' in audit
assert 'E2EE cross-signing persistence pending' in audit

for script in (ROOT/'stack/configure-stack.sh', ROOT/'stack/manage.sh'):
    r = subprocess.run(['bash','-n',str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

print('v14.3.30 Matrix profile soft-pending regression fixtures: PASS')

# Execute the Matrix resource verifier against a minimal synthetic profile. A protected
# pending-manual transaction must pass; a supposedly-complete profile that has not joined
# must fail; once joined it must pass even if no gateway-runtime probe is available here.
import json, os, tempfile, shutil
with tempfile.TemporaryDirectory() as td_raw:
    td = Path(td_raw)
    (td/'data/hermes/profiles/assistant').mkdir(parents=True)
    (td/'secrets/matrix-profiles').mkdir(parents=True)
    (td/'secrets').mkdir(exist_ok=True)
    (td/'.matrix-profiles').mkdir()
    (td/'bin').mkdir()
    (td/'install-options.json').write_text(json.dumps({'matrix': True, 'workers':[{'name':'assistant','matrix':{'enabled':True,'localpart':'assistant'}}]}))
    (td/'data/hermes/profiles/assistant/config.yaml').write_text('model:\n  default: test-model\n')
    (td/'data/hermes/profiles/assistant/.env').write_text(
        'MATRIX_ACCESS_TOKEN=profile-token\nMATRIX_USER_ID=@assistant:hermes.local\n'
        'MATRIX_ALLOWED_ROOMS=!room:hermes.local\nMATRIX_HOME_ROOM=!room:hermes.local\n')
    secret = td/'secrets/matrix-profiles/assistant.env'
    info = td/'.matrix-profiles/assistant.info'
    secret.write_text(
        'MATRIX_ACCESS_TOKEN=profile-token\nMATRIX_USER_ID=@assistant:hermes.local\n'
        'MATRIX_ALLOWED_ROOMS=!room:hermes.local\nMATRIX_HOME_ROOM=!room:hermes.local\n'
        'MATRIX_ROOM_MODE=create\nMATRIX_ROOM_VERSION=10\nLATTICEVALE_PROVISIONING_STATE=pending-manual\n')
    info.write_text('HERMES_MODEL=test-model\nMATRIX_SETUP_STATUS=pending-manual\n')
    (td/'bin/curl').write_text(r'''#!/bin/sh
case "$*" in
  *account/whoami*) printf '%s\n' '{"user_id":"@assistant:hermes.local"}' ;;
  *joined_rooms*)
    if [ "${FAKE_JOINED:-false}" = true ]; then printf '%s\n' '{"joined_rooms":["!room:hermes.local"]}'
    else printf '%s\n' '{"joined_rooms":[]}'
    fi ;;
  *) printf '%s\n' '{}' ;;
esac
''')
    os.chmod(td/'bin/curl',0o755)
    verifier = cfg[cfg.index('verify_matrix_profiles() {'):cfg.index('\nverify_matrix_profile_cross_signing() {')]
    harness = r'''opt_bool(){ [ "$1" = matrix ] && printf 'true\n' || printf 'false\n'; }
read_env_file_value_optional(){ [ -f "$1" ] || return 0; sed -n "s/^$2=//p" "$1" | head -n1; }
matrix_client_api_ready(){ return 0; }
hermes_model_configured(){ return 0; }
matrix_room_version(){ [ "${FAKE_JOINED:-false}" = true ] && printf '10\n' || return 1; }
MATRIX_HOST_PORT=18008
LATTICEVALE_MATRIX_ROOM_VERSION=10
''' + verifier + '\nverify_matrix_profiles\n'
    env = os.environ.copy(); env['PATH']=str(td/'bin')+os.pathsep+env['PATH']
    r = subprocess.run(['bash','-c',harness], cwd=td, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout+r.stderr
    secret.write_text(secret.read_text().replace('pending-manual','complete'))
    info.write_text(info.read_text().replace('pending-manual','complete'))
    r = subprocess.run(['bash','-c',harness], cwd=td, env=env, capture_output=True, text=True)
    assert r.returncode != 0, 'complete profile without joined room must remain invalid'
    env['FAKE_JOINED']='true'
    r = subprocess.run(['bash','-c',harness], cwd=td, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout+r.stderr

# Execute the manage.sh start helper with an upstream-style named-profile CLI failure.
# The fallback must touch only /run/service/gateway-assistant and clear a stale down marker.
with tempfile.TemporaryDirectory() as td_raw:
    td=Path(td_raw); (td/'bin').mkdir(); state=td/'state'; log=td/'docker.log'
    state.write_text('down\n'); log.write_text('')
    (td/'bin/sleep').write_text('#!/bin/sh\nexit 0\n'); os.chmod(td/'bin/sleep',0o755)
    (td/'bin/docker').write_text(r'''#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_DOCKER_LOG"
case "$*" in
  *s6-svstat*)
    if [ "$(cat "$FAKE_DOCKER_STATE")" = up ]; then printf 'up (pid 4242) 1 seconds\n'; else printf 'down (exitcode 0) 1 seconds, normally down\n'; fi
    exit 0 ;;
  *"gateway start"*) exit 1 ;;
  *"s6-svc -U /run/service/gateway-assistant"*) printf 'up\n' > "$FAKE_DOCKER_STATE"; exit 0 ;;
  *) exit 0 ;;
esac
'''); os.chmod(td/'bin/docker',0o755)
    start=manage.index('profile_gateway_s6_state_exact() {')
    end=manage.index('\nstop_profile_gateway_exact_manage() {', start)
    helpers=manage[start:end]
    env=os.environ.copy(); env.update({'PATH':str(td/'bin')+os.pathsep+env['PATH'],'FAKE_DOCKER_LOG':str(log),'FAKE_DOCKER_STATE':str(state)})
    r=subprocess.run(['bash','-c','set -u\n'+helpers+'\nstart_profile_gateway_exact_manage assistant\n'],env=env,capture_output=True,text=True,timeout=30)
    assert r.returncode == 0, r.stdout+r.stderr
    calls=log.read_text()
    assert 'gateway start' in calls
    assert 's6-svc -U /run/service/gateway-assistant' in calls
    assert '/run/service/gateway-default' not in calls


# The real installer invokes manage.sh matrix-profile-finish while .configured is still
# absent. Execute a structurally reduced copy of the dispatch contract and ensure the
# recovery command is allowed while an ordinary command would still require completion.
manage_tail = manage[manage.index('cmd="${1:-status}"'):]
assert manage_tail.index('if [[ "$cmd" == matrix-profile-finish ]]') < manage_tail.index('\nneed_configured\ncase "$cmd" in')

# Execute the full manage.sh dispatch with no .configured marker. A fully staged Matrix
# recovery command must be reachable during configure-stack.sh, while ordinary status
# remains protected by the final-completion gate.
with tempfile.TemporaryDirectory() as td_raw:
    td=Path(td_raw)
    shutil.copy2(ROOT/'stack/manage.sh', td/'manage.sh')
    (td/'bin').mkdir()
    (td/'bin/docker').write_text('#!/bin/sh\nexit 0\n'); os.chmod(td/'bin/docker',0o755)
    (td/'install-options.json').write_text(json.dumps({'matrix':True,'workers':[{'name':'assistant','matrix':{'enabled':True}}]}))
    (td/'.env').write_text('MATRIX_HOST_PORT=8008\n')
    (td/'compose.yaml').write_text('services: {}\n')
    (td/'secrets/matrix-profiles').mkdir(parents=True)
    (td/'.matrix-profiles').mkdir()
    (td/'data/hermes/profiles/assistant').mkdir(parents=True)
    (td/'secrets/matrix-profiles/assistant.env').write_text(
        'LATTICEVALE_PROVISIONING_STATE=complete\nMATRIX_ACCESS_TOKEN=x\n'
        'MATRIX_USER_ID=@assistant:hermes.local\nMATRIX_ALLOWED_ROOMS=!r:hermes.local\n')
    (td/'.matrix-profiles/assistant.info').write_text('MATRIX_SETUP_STATUS=complete\n')
    (td/'data/hermes/profiles/assistant/.env').write_text('x=1\n')
    env=os.environ.copy(); env['PATH']=str(td/'bin')+os.pathsep+env['PATH']
    r=subprocess.run(['bash','manage.sh','matrix-profile-finish','assistant'],cwd=td,env=env,capture_output=True,text=True)
    assert r.returncode == 0, r.stdout+r.stderr
    assert "already marked complete" in r.stdout
    r=subprocess.run(['bash','manage.sh','status'],cwd=td,env=env,capture_output=True,text=True)
    assert r.returncode != 0 and 'has not finished configuration' in (r.stdout+r.stderr)

print('v14.3.30 Matrix profile executable pending/fallback fixtures: PASS')

# The pre-existing default-bot legacy pending marker must also match its stated semantics:
# preserved legacy identity => verifier passes but repair bypass remains active; a fresh
# installer-managed identity is never allowed to use the soft-pending exemption.
default_verify = cfg[cfg.index('verify_matrix_cross_signing() {'):cfg.index('\nstage_matrix_cross_signing() {')]
with tempfile.TemporaryDirectory() as td_raw:
    td=Path(td_raw); (td/'secrets').mkdir(); (td/'data/hermes').mkdir(parents=True)
    (td/'secrets/matrix-bot.env').write_text('MATRIX_USER_ID=@hermes:hermes.local\n')
    (td/'data/hermes/.env').write_text('MATRIX_E2EE_MODE=required\n')
    (td/'.matrix-info').write_text('MATRIX_USER_ID=@hermes:hermes.local\n')
    (td/'.matrix-cross-signing-pending').write_text('')
    harness="opt_bool(){ printf 'true\\n'; }\n"+default_verify+'\nverify_matrix_cross_signing\n'
    r=subprocess.run(['bash','-c',harness],cwd=td,capture_output=True,text=True)
    assert r.returncode == 0, r.stdout+r.stderr
    (td/'.matrix-info').write_text('MATRIX_CROSS_SIGNING=installer-managed\n')
    r=subprocess.run(['bash','-c',harness],cwd=td,capture_output=True,text=True)
    assert r.returncode != 0, 'fresh installer-managed default identity must remain strict'

assert 'matrix_cross_signing) [[ -e .matrix-cross-signing-pending ]] ;;' in cfg
print('v14.3.30 default Matrix legacy-pending semantics fixtures: PASS')
