#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (ROOT / 'stack/manage.sh').read_text(encoding='utf-8')
readonly = (ROOT / 'stack/latticevale_readonly.py').read_text(encoding='utf-8')
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()
assert version in {'14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}, version

# Live repair evidence showed the exact default gateway could need longer than the
# former 20-second readiness window, while the bounded stack verifier later became
# healthy. Keep readiness bounded, tolerate transient probe failures, and require
# stable consecutive up observations.
for text in (cfg, manage):
    assert 'wait_seconds="${2:-60}"' in text
    assert 'consecutive_up' in text
    assert 'observed_state' in text

assert 'requesting the same exact service slot up and retrying readiness' in cfg
assert '/command/s6-svc -U "$service"' in cfg
assert "printf '%s\\n' \"--- exact Hermes gateway log: $name ---\"" in cfg
assert "printf '%s\\n' \"--- exact Hermes gateway log: $name ---\"" in manage
assert 'v14.5.0 does not parse, normalize, or rewrite this file' not in readonly
assert 'the read-only planner does not parse, normalize, or rewrite this file' in readonly

# Execute the installer waiter with transient inspection failures, then down, then
# two consecutive up observations. A single failed s6-svstat must not abort.
start = cfg.index('wait_profile_gateway_up_exact() {')
end = cfg.index('\nprofile_gateway_log_tail_exact() {', start)
wait_func = cfg[start:end]
mock = r'''set -e
countfile=$(mktemp)
echo 0 > "$countfile"
profile_gateway_s6_state() {
  n=$(cat "$countfile"); n=$((n+1)); echo "$n" > "$countfile"
  case "$n" in
    1|2) return 1 ;;
    3|4) printf 'down\n' ;;
    *) printf 'up\n' ;;
  esac
}
sleep() { :; }
''' + wait_func + r'''
wait_profile_gateway_up_exact default 10
rm -f "$countfile"
'''
r = subprocess.run(['bash', '-c', mock], capture_output=True, text=True)
assert r.returncode == 0, (r.stdout, r.stderr)

# If Hermes says restart succeeded but the first bounded readiness window expires,
# the default helper must reassert only the exact proven s6 slot with -U and accept
# a subsequent stable window instead of immediately breaking reconcile.
start = cfg.index('start_or_restart_default_gateway_exact() {')
end = cfg.index('\nwait_profile_gateway_down_exact() {', start)
default_func = cfg[start:end]
mock = r'''set -e
wait_calls=0
calls=$(mktemp)
profile_gateway_s6_state() { printf 'up\n'; }
wait_profile_gateway_up_exact() {
  wait_calls=$((wait_calls+1))
  [ "$wait_calls" -ge 2 ]
}
profile_gateway_log_tail_exact() { :; }
docker() { printf '%s\n' "$*" >> "$calls"; return 0; }
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
''' + default_func + r'''
start_or_restart_default_gateway_exact
grep -q '/command/s6-svc -U /run/service/gateway-default' "$calls"
rm -f "$calls"
'''
r = subprocess.run(['bash', '-c', mock], capture_output=True, text=True)
assert r.returncode == 0, (r.stdout, r.stderr)

for f in ('configure-stack.sh', 'manage.sh'):
    r = subprocess.run(['bash', '-n', str(ROOT / 'stack' / f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

print('v14.5.1 DELAYED GATEWAY RECONCILE FIXTURES: PASS')
