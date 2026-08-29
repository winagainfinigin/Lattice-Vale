#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
version=(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()
assert version == '14.4.85', version

stage=cfg[cfg.index('stage_reconcile()'):cfg.index('stage_kanban_gateway()')]
restart=stage.index('start_or_restart_default_gateway_exact')
post=stage.rindex("wait_hermes_gateway_surfaces 'reconcile gateway restart' 60")
assert restart < post
assert stage.index('wait_http Hermes-API') < restart < post
assert stage.index('wait_http Dashboard') < restart < post
assert post > stage.index('wait_http Honcho')

kanban=cfg[cfg.index('stage_kanban_gateway()'):cfg.index('stage_finalize()')]
assert 'start_or_restart_default_gateway_exact' in kanban
assert kanban.index('start_or_restart_default_gateway_exact') < kanban.index("wait_hermes_gateway_surfaces 'Kanban/final gateway reload' 60")
verify=cfg[cfg.index('verify_kanban_gateway()'):cfg.index('verify_finalize()')]
assert 'HERMES_API_HOST_PORT' in verify
assert 'DASHBOARD_HOST_PORT' in verify
assert 'matrix_backend_ready_from_hermes' in verify

checkpoint=cfg[cfg.index('checkpoint_revision()'):cfg.index('matrix_profile_activation_pending()')]
assert "reconcile) printf '4'" in checkpoint
assert "kanban_gateway) printf '4'" in checkpoint

for marker in (
    "wait_hermes_gateway_surfaces_manage 'stack start/gateway reconciliation'",
    "wait_hermes_gateway_surfaces_manage 'stack restart/gateway reconciliation'",
    "wait_hermes_gateway_surfaces_manage 'stack update/gateway reconciliation'",
):
    assert marker in manage, marker

# Execute only the waiter with mocked runtime state. The API is unavailable for two
# polls after a simulated gateway restart, then returns; the waiter must tolerate it.
start=cfg.index('wait_hermes_gateway_surfaces() {')
end=cfg.index('\nverify_prepare_config() {', start)
func=cfg[start:end]
mock = r'''set -e
countfile=$(mktemp)
echo 0 > "$countfile"
opt_bool() { [ "$1" = dashboard ] && echo true || echo false; }
http_status_ok() {
  case "$1" in
    *:8642/health)
      n=$(cat "$countfile"); n=$((n+1)); echo "$n" > "$countfile"
      [ "$n" -ge 3 ]
      ;;
    *:9119/) return 0 ;;
    *) return 0 ;;
  esac
}
docker() { return 0; }
timeout() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --foreground) shift ;;
      --kill-after=*) shift ;;
      [0-9]*s) shift; break ;;
      *) break ;;
    esac
  done
  "$@"
}
sleep() { :; }
''' + func + r'''
wait_hermes_gateway_surfaces test 5
rm -f "$countfile"
'''
r=subprocess.run(['bash','-c',mock],capture_output=True,text=True)
assert r.returncode == 0, r.stderr

for f in ('configure-stack.sh','manage.sh'):
    r=subprocess.run(['bash','-n',str(ROOT/'stack'/f)],capture_output=True,text=True)
    assert r.returncode == 0, r.stderr
print('v14.4.85 POST-GATEWAY READINESS FIXTURES: PASS')
