#!/usr/bin/env python3
"""v14.6.1 same-version runtime-policy/DirectML repair regression coverage."""
from pathlib import Path
import hashlib
import importlib.util
import sys
import tempfile
import subprocess
import threading
import time
import urllib.request

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version == '14.6.1', version
sys.path.insert(0, str(ROOT / 'stack'))
from latticevale_arch import (  # noqa:E402
    directml_context_recommendation,
    directml_cpu_thread_plan,
    directml_generation_limit,
    fingerprint,
    host_memory_budget,
    parse_compatibility,
    validate_runtime_policy_state,
)

compat = parse_compatibility(ROOT / 'compatibility.conf')
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
arch = (ROOT / 'stack/latticevale_arch.py').read_text(encoding='utf-8')
dml = (ROOT / 'stack/directml-gateway.sh').read_text(encoding='utf-8')
dml_py = (ROOT / 'stack/directml-gateway.py').read_text(encoding='utf-8')
readme = (REPO / 'README.md').read_text(encoding='utf-8')

# README contract: same-version repair is preservation-first and derived state follows
# options -> hardware -> backend -> policy -> generated runtime configuration.
assert 'options → hardware → backend capability/health → resource policy → generated runtime configuration' in readme
assert 'Resume / repair installation' in readme
assert 'patch ZIP remains for source checkouts only' in readme

# Exact observed topology: 3 WSL CPUs, 9946 MiB WSL RAM, RX 6700 XT-class bounded
# DirectML admission, no Linux-native Ollama GPU, DirectML text + managed CPU Ollama.
mem = 9946
cpus = 3
admission = 12242
hardware = {
    'schema': int(compat['HARDWARE_CAPABILITIES_SCHEMA']),
    'wsl': {'cpuCount': cpus, 'memoryMiB': mem},
}
hardware['hardwareFingerprint'] = fingerprint(hardware)
backends = {
    'schema': int(compat['BACKEND_CAPABILITIES_SCHEMA']),
    'backendFingerprint': 'b' * 64,
    'adapterSelection': {'selected': {'directmlAdmission': {
        'capacityMiB': admission,
        'source': 'windows-dxdiag+registry-qword-conservative',
        'confidence': 'high',
    }}},
    'selection': {'textBackend': 'directml', 'ollamaAcceleration': 'cpu'},
}
budget = host_memory_budget(mem, 'cpu', True, True)
state = {
    'POLICY_VERSION': compat['RUNTIME_POLICY_SCHEMA'],
    'MEM_MIB': str(mem),
    'CPUS': str(cpus),
    'OLLAMA_ACCELERATION': 'cpu',
    'MANAGED_OLLAMA_SELECTED': 'true',
    'DIRECTML_SELECTED': 'true',
    'RESERVE_MIB': str(budget['reserveMiB']),
    'DIRECTML_HOST_RESERVE_MIB': str(budget['directmlHostReserveMiB']),
    'BUDGET_MIB': str(budget['containerBudgetMiB']),
    'RESOURCE_POLICY_MODE': 'adaptive',
    'HARDWARE_FINGERPRINT': hardware['hardwareFingerprint'],
    'DIRECTML_ADMISSION_MIB': str(admission),
    'DIRECTML_ADMISSION_SOURCE': 'windows-dxdiag+registry-qword-conservative',
    'DIRECTML_ADMISSION_CONFIDENCE': 'high',
    'DIRECTML_CONTEXT_LENGTH': str(directml_context_recommendation(mem, admission)),
    'DIRECTML_CPU_THREADS': str(directml_cpu_thread_plan(cpus)),
}
state['DIRECTML_MAX_NEW_TOKENS'] = str(directml_generation_limit(int(state['DIRECTML_CONTEXT_LENGTH'])))
material = '\n'.join(f'{k}={v}' for k, v in sorted(state.items())) + '\n'
state['POLICY_FINGERPRINT'] = hashlib.sha256(material.encode()).hexdigest()
validated = validate_runtime_policy_state(state, compat, hardware=hardware, backends=backends)
assert validated['cpuCount'] == cpus
assert validated['memory']['containerBudgetMiB'] == budget['containerBudgetMiB']
assert validated['directmlRuntime']['admissionMiB'] == admission

# Stale canonical hardware cannot be accepted by the same freshly generated state.
stale = dict(hardware)
stale['hardwareFingerprint'] = 'c' * 64
try:
    validate_runtime_policy_state(state, compat, hardware=stale, backends=backends)
except ValueError as exc:
    assert 'HARDWARE_FINGERPRINT_MISMATCH' in str(exc)
else:
    raise AssertionError('stale hardware fingerprint was accepted')

# The production writer consumes canonical CPU/RAM, never independent nproc/meminfo.
start = cfg.index('write_latticevale_compose_overlay() {')
end = cfg.index('\nverify_adaptive_runtime_policy() {', start)
overlay_fn = cfg[start:end]
assert "jq -r '.wsl.cpuCount // 0' data/latticevale/hardware-capabilities.json" in overlay_fn
assert "jq -r '.wsl.memoryMiB // 0' data/latticevale/hardware-capabilities.json" in overlay_fn
assert 'cpus="$(nproc' not in overlay_fn
assert "awk '/^MemTotal:/'" not in overlay_fn

# Resume/repair refreshes canonical architecture before even deciding whether adaptive
# policy is enabled/current. This specifically protects a completed prepare_config checkpoint.
reconcile_start = cfg.index('repair_runtime_policy_reconcile() {')
reconcile_end = cfg.index('\nchoose_ollama_context_length()', reconcile_start)
reconcile = cfg[reconcile_start:reconcile_end]
assert reconcile.index('refresh_canonical_architecture_state') < reconcile.index('containerResourceLimits')
assert 'hardware-capabilities.py --stack .' in cfg[cfg.index('refresh_canonical_architecture_state() {'):reconcile_start]
assert 'backend-capabilities.py --stack .' in cfg[cfg.index('refresh_canonical_architecture_state() {'):reconcile_start]

# Every formerly-silent post-write invariant now has a stable classified diagnostic.
for code in (
    'WSL_CPU_MISMATCH', 'WSL_MEMORY_MISMATCH', 'CANONICAL_POLICY_INVALID',
    'RESOURCE_REPORT_POLICY_FINGERPRINT_MISMATCH',
    'RESOURCE_REPORT_HARDWARE_FINGERPRINT_MISMATCH',
    'COMPOSE_OVERLAY_MALLOC_TUNING_MISSING', 'COMPOSE_SELECTOR_MISSING_OVERLAY',
):
    assert code in cfg, code
for code in ('WSL_CPU_MISMATCH', 'WSL_MEMORY_MISMATCH', 'HARDWARE_FINGERPRINT_MISMATCH', 'HARDWARE_STATE_INVALID'):
    assert code in arch, code

# Execute the ordering of repair_runtime_policy_reconcile with stubs: refresh must happen
# before the stale-policy check and before overlay generation; a changed policy marks both
# runtime-owning stages pending.
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    func = reconcile
    harness = f'''set -Eeuo pipefail
refresh_done=false
verify_calls=0
opt_bool() {{ [[ "$1" == containerResourceLimits ]] && printf true || printf false; }}
refresh_canonical_architecture_state() {{ refresh_done=true; }}
verify_adaptive_runtime_policy() {{ verify_calls=$((verify_calls+1)); [[ "$refresh_done" == true ]] || return 9; (( verify_calls >= 2 )); }}
managed_ollama_enabled() {{ return 0; }}
resolve_ollama_acceleration() {{ printf cpu; }}
write_latticevale_compose_overlay() {{ [[ "$refresh_done" == true && "$1" == cpu && "$2" == true ]]; }}
state_mark() {{ printf 'STATE:%s:%s\\n' "$1" "$2"; }}
{func}
repair_runtime_policy_reconcile
'''
    proc = subprocess.run(['bash', '-c', harness], cwd=td, text=True, capture_output=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert 'STATE:infrastructure:pending' in proc.stdout
    assert 'STATE:reconcile:pending' in proc.stdout

# DirectML-only failure is isolated from Docker local-repair eligibility. The local path
# first verifies containers without the host gateway, then runs targeted DirectML repair;
# broad pull/build repair is entered only when Docker/service infrastructure itself fails.
local_start = cfg.index('start_existing_infrastructure_for_repair() {')
local_end = cfg.index('\nreconcile_model_aware_ollama_resources()', local_start)
local_repair = cfg[local_start:local_end]
assert 'verify_infrastructure false' in local_repair
assert './directml-gateway.sh' not in local_repair
stage_start = cfg.index('stage_infrastructure() {')
stage_end = cfg.index('\ninfra_services=()', stage_start)
stage = cfg[stage_start:stage_end]
local_success = stage.index('if start_existing_infrastructure_for_repair; then')
broad_pull = stage.index('docker compose pull --ignore-buildable')
assert local_success < stage.index('repair_directml_gateway || return 1', local_success) < broad_pull
assert 'Existing Docker/service infrastructure did not become healthy' in stage

# Missing Hermes s6 gateway slots are ephemeral supervisor state, not persistent
# profile identity. Resume/repair must reconstruct the exact slot via upstream
# S6ServiceManager.register_profile_gateway() and then continue normal lifecycle.
manage_text = (ROOT / 'stack/manage.sh').read_text(encoding='utf-8')
for source in (cfg, manage_text):
    assert 'register_profile_gateway(name)' in source
    assert 'Repairing missing exact Hermes s6 gateway slot' in source
assert 'Default gateway has no registered s6 service slot; refusing to guess or recreate it automatically.' not in cfg
checkpoint = cfg[cfg.index('checkpoint_revision() {'):cfg.index('matrix_profile_activation_pending()')]
assert "reconcile) printf '5'" in checkpoint
assert "kanban_gateway) printf '5'" in checkpoint

# Behavioral proof of the default repair branch: an absent slot is registered from
# preserved state, re-read as down, and then started through Hermes' normal lifecycle.
default_start = cfg.index('start_or_restart_default_gateway_exact() {')
default_end = cfg.index('\nwait_profile_gateway_down_exact() {', default_start)
default_fn = cfg[default_start:default_end]
harness = r'''set -Eeuo pipefail
gateway_state=absent
calls=$(mktemp)
profile_gateway_s6_state() { printf '%s\n' "$gateway_state"; }
register_missing_gateway_slot_exact() { gateway_state=down; printf 'register:%s\n' "$1" >> "$calls"; }
wait_profile_gateway_up_exact() { return 0; }
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
''' + default_fn + r'''
start_or_restart_default_gateway_exact
grep -q '^register:default$' "$calls"
grep -q 'hermes gateway start' "$calls"
rm -f "$calls"
'''
proc = subprocess.run(['bash', '-c', harness], text=True, capture_output=True, timeout=15)
assert proc.returncode == 0, (proc.stdout, proc.stderr)

# fallback=none remains fail-closed at marker creation and self-test failure.
assert 'refusing forced Ollama fallback marker because directmlFallbackPolicy=none' in dml
assert 'fail-closed fallback policy' in dml
assert 'text_fallback_enabled && return 0 || return 1' in dml

# DirectML readiness regression from the RX 6700 XT repair audit: first-load inference
# can hold MODEL_LOCK longer than the supervisor health timeout. /health therefore must
# not take MODEL_LOCK; a live worker gets a confirmation miss before replacement; and
# installer repair waits for bounded readiness after self-test rather than a one-shot curl.
health_start = dml_py.index('    def do_GET(self) -> None:')
health_end = dml_py.index('    def do_POST(self) -> None:', health_start)
health_handler = dml_py[health_start:health_end]
assert 'with STATE_LOCK, MODEL_LOCK:' not in health_handler
assert 'with STATE_LOCK:' in health_handler
assert 'health_misses=0' in dml
assert 'health probe missed once while worker is still alive' in dml
assert 'health probe missed twice while worker remained alive' in dml
assert 'wait-ready) wait_ready ;;' in dml
repair_start = cfg.index('repair_directml_gateway() {')
repair_end = cfg.index('\nstage_infrastructure() {', repair_start)
repair_fn = cfg[repair_start:repair_end]
assert './directml-gateway.sh wait-ready' in repair_fn
assert './directml-gateway.sh health >/dev/null' not in repair_fn
assert 'server_version = f"LatticeValeDirectML/{VERSION}"' in dml_py

# Behavioral proof: a held MODEL_LOCK (representing first model load/generation) must not
# delay /health. The old implementation timed out here and caused the supervisor restart.
spec = importlib.util.spec_from_file_location('lv_dml_health_regression', ROOT / 'stack/directml-gateway.py')
dml_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(dml_mod)
dml_mod.DEPENDENCY_PROBE = {'ready': True, 'detail': 'fixture'}
dml_mod.fallback_ready = lambda: (False, 'disabled')
server = dml_mod.ThreadingHTTPServer(('127.0.0.1', 0), dml_mod.GatewayHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
locked = threading.Event()
release = threading.Event()
def hold_model_lock():
    with dml_mod.MODEL_LOCK:
        locked.set()
        release.wait(3)
holder = threading.Thread(target=hold_model_lock)
holder.start()
assert locked.wait(1)
started = time.monotonic()
with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/health', timeout=1) as response:
    assert response.status == 200
elapsed = time.monotonic() - started
release.set()
holder.join(timeout=2)
server.shutdown()
server.server_close()
assert elapsed < 0.5, elapsed

print('v14.6.1 runtime-policy/DirectML repair fixtures: PASS')
