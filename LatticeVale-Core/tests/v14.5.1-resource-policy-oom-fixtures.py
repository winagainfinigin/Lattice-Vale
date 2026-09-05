#!/usr/bin/env python3
"""v14.5.1 resource-policy v11 CPU/RAM and running-container OOM regression fixtures."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / "VERSION.txt").read_text(encoding="ascii").strip()
assert version in {"14.5.1","14.5.2","14.5.3","14.5.4","14.5.42","14.5.43","14.5.44",'14.5.45','14.5.46','14.5.47','14.6.0'}, version

cfg = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
manage = (ROOT / "stack/manage.sh").read_text(encoding="utf-8")
boot = (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8")
audit = (ROOT / "stack/state-audit.py").read_text(encoding="utf-8")
features = (REPO / "docs/FEATURES.md").read_text(encoding="utf-8")
sys.path.insert(0,str(ROOT/'stack'))
from latticevale_arch import host_memory_budget, service_memory_plan  # noqa:E402

# Current policy is schema 12 and formula verification is delegated to the canonical
# runtime-policy engine. Older starvation/OOM regressions remain protected behaviorally.
assert '[POLICY_VERSION]=12' in cfg
assert 'runtime-policy.py verify --stack . --compat compatibility.conf' in cfg
assert './configure-stack.sh --refresh-resource-policy' in manage
assert './configure-stack.sh --refresh-resource-policy' in boot
assert 'validate_runtime_policy_state' in audit and 'validate_runtime_policy_document' in audit

# Host budgeting must be adaptive across arbitrary WSL allocations and backend shapes.
for accel in ("cpu", "vulkan", "nvidia", "amd"):
    for managed in (False, True):
        for directml in (False, True):
            previous_budget = -1
            for mem in (2137, 3923, 6179, 9053, 12791, 18437, 27611, 49157):
                state = host_memory_budget(mem, accel, managed, directml)
                assert state["reserveMiB"] + state["containerBudgetMiB"] == mem
                assert state["containerBudgetMiB"] >= 384
                assert state["containerBudgetMiB"] >= previous_budget
                previous_budget = state["containerBudgetMiB"]
                if directml:
                    assert 0 < state["directmlHostReserveMiB"] <= state["reserveMiB"]
                else:
                    assert state["directmlHostReserveMiB"] == 0
assert 'runtime-policy.py service-plan' in cfg
assert 'resource_hermes_floor_mib() {' in cfg
assert 'resource_ollama_model_metrics() {' in cfg
assert '[OLLAMA_MODEL_FLOOR_MIB]="$ollama_floor_mib"' in cfg
assert 'PY_RESOURCE_PLAN' not in cfg
assert 'LOW_MEMORY_PROFILE' not in cfg

# Clean installs persist exact generated ceilings and live repair verifies Docker consumes them.
for marker in (
    'resource_policy["LIMIT_${resource_state_key}_MIB"]="${mem_limits[$resource_state_svc]}"',
    "verify_live_resource_policy_limits() {",
    "{{.HostConfig.Memory}}",
    "docker compose config --format json",
    "live Docker CPU/RAM ceilings do not match the current adaptive resource policy",
    "Reconcile completed but the live Docker CPU/RAM ceilings still do not match policy v12",
):
    assert marker in cfg, marker

class PlanResult:
    def __init__(self, returncode:int, stderr:str=''):
        self.returncode=returncode; self.stderr=stderr; self.stdout=''

def plan_result(budget: int, matrix=True, searxng=True, qmd=True, ollama=True, honcho=True, hermes_floor=1024, ollama_floor=3072):
    try:
        alloc=service_memory_plan(budget,matrix=matrix,searxng=searxng,qmd=qmd,ollama=ollama,honcho=honcho,hermes_floor=hermes_floor,ollama_floor=ollama_floor)
        r=PlanResult(0); r.alloc=alloc; return r
    except ValueError as exc:
        r=PlanResult(3,str(exc)); r.alloc={}; return r

def first_fit(**kwargs):
    lo,hi=384,131072
    while lo<hi:
        mid=(lo+hi)//2
        if plan_result(mid,**kwargs).returncode==0: hi=mid
        else: lo=mid+1
    return lo

# Full and light selections compute their viability threshold from enabled-service minima.
full_threshold=first_fit()
assert plan_result(full_threshold).returncode==0
assert plan_result(full_threshold-1).returncode==3
full=plan_result(full_threshold+977).alloc
assert sum(full.values())<=full_threshold+977
assert full['hermes']>=1024 and full['ollama']>=3072
assert full['honcho-api']>=384 and full['honcho-deriver']>=256

core_threshold=first_fit(matrix=False,searxng=False,qmd=False,ollama=False,honcho=False,ollama_floor=0)
assert core_threshold==1024
core=plan_result(core_threshold+191,matrix=False,searxng=False,qmd=False,ollama=False,honcho=False,ollama_floor=0).alloc
assert core['hermes']>=1024 and sum(core.values())<=core_threshold+191

ollama_threshold=first_fit(matrix=False,searxng=False,qmd=False,ollama=True,honcho=False,ollama_floor=2304)
assert plan_result(ollama_threshold-1,matrix=False,searxng=False,qmd=False,ollama=True,honcho=False,ollama_floor=2304).returncode==3
small_gpu=plan_result(ollama_threshold+257,matrix=False,searxng=False,qmd=False,ollama=True,honcho=False,ollama_floor=2304).alloc
assert small_gpu['hermes']>=1024 and small_gpu['ollama']>=2304

# Water-fill is monotonic for arbitrary larger budgets until a service reaches its safety cap.
prev=None
for budget in (full_threshold, full_threshold+431, full_threshold+1907, full_threshold+7123, full_threshold+22109):
    alloc=plan_result(budget).alloc
    assert alloc and sum(alloc.values())<=budget
    if prev:
        for name in alloc: assert alloc[name]>=prev[name], (name,budget,prev[name],alloc[name])
    prev=alloc

# The audit must not report HEALTHY when Docker says a currently-running selected
# container has recorded an OOM kill or is still using a stale live hard ceiling.
for marker in (
    'oom_candidates = [("Hermes", "hermes-agent")]',
    'live_state.get("running") and live_state.get("oomKilled")',
    'container recorded an OOM kill in its current lifecycle',
    'Resume / repair will recalculate/reconcile the adaptive resource policy',
    'memoryLimitBytes',
    'live memory ceiling is',
    'effective_compose_resource_limits(root)',
    'cpuLimitNanoCpus',
    'live CPU ceiling is',
    'effective Compose requires',
):
    assert marker in audit, marker

# Execute the exact live-limit verifier with a fake Docker inspect. A v14.5.0-era
# 544 MiB live Hermes cgroup must fail even when the desired v11 state says 1040 MiB;
# after Compose recreation to 1040 MiB it must pass. This is the repair-path regression
# that the first v14.5.1 candidate did not cover.
def between(text: str, start: str, end: str) -> str:
    a = text.index(start)
    b = text.index(end, a)
    return text[a:b]

live_verify = between(cfg, 'verify_live_resource_policy_limits() {', 'repair_runtime_policy_reconcile() {')
with tempfile.TemporaryDirectory(prefix='lv151-live-limit-') as td_raw:
    td = Path(td_raw)
    fakebin = td / 'bin'; fakebin.mkdir()
    docker = fakebin / 'docker'
    docker.write_text(
        '#!/usr/bin/env bash\n'
        'set -e\n'
        'if [[ "$1" == compose && "$2" == config ]]; then\n'
        '  printf "{\\"services\\":{\\"hermes\\":{\\"mem_limit\\":\\"%s\\",\\"cpus\\":\\"%s\\"}}}\\n" "${FAKE_COMPOSE_LIMIT:-1040m}" "${FAKE_COMPOSE_CPUS:-3}"\n'
        '  exit 0\n'
        'fi\n'
        'if [[ "$1" == inspect ]]; then\n'
        '  printf "%s:%s\\n" "${FAKE_MEMORY_BYTES:-0}" "${FAKE_NANO_CPUS:-3000000000}"\n'
        '  exit 0\n'
        'fi\n'
        'exit 2\n',
        encoding='utf-8',
    )
    docker.chmod(0o755)
    (td / '.latticevale-resource-state').write_text('POLICY_VERSION=12\nMATRIX_PROFILE_GATEWAYS=0\nKANBAN_CONCURRENCY=1\nHERMES_MIN_MIB=1024\nLIMIT_HERMES_MIB=1040\nCPU_HERMES_MILLI=3000\n', encoding='utf-8')
    harness = td / 'harness.sh'
    harness.write_text(
        '#!/usr/bin/env bash\n'
        'set -euo pipefail\n'
        'opt_bool() { [[ "$1" == containerResourceLimits ]] && printf true || printf false; }\n'
        'managed_ollama_enabled() { return 1; }\n'
        + live_verify
        + '\nverify_live_resource_policy_limits\n',
        encoding='utf-8',
    )
    env = dict(os.environ)
    env['PATH'] = str(fakebin) + os.pathsep + env.get('PATH','')
    env['FAKE_MEMORY_BYTES'] = str(544 * 1024 * 1024)
    stale = subprocess.run(['bash', str(harness)], cwd=td, env=env, text=True, capture_output=True, timeout=10)
    assert stale.returncode != 0, stale.stdout + stale.stderr
    assert 'Compose reconciliation is required' in stale.stderr, stale.stderr
    env['FAKE_MEMORY_BYTES'] = str(1040 * 1024 * 1024)
    current = subprocess.run(['bash', str(harness)], cwd=td, env=env, text=True, capture_output=True, timeout=10)
    assert current.returncode == 0, current.stdout + current.stderr
    # CPU convergence is equally mandatory: a stale 2-CPU live quota must fail when
    # effective Compose requires 3 CPUs, then pass after Docker reports 3 NanoCPUs.
    env['FAKE_NANO_CPUS'] = '2000000000'
    stale_cpu = subprocess.run(['bash', str(harness)], cwd=td, env=env, text=True, capture_output=True, timeout=10)
    assert stale_cpu.returncode != 0, stale_cpu.stdout + stale_cpu.stderr
    assert 'NanoCPUs' in stale_cpu.stderr and 'Compose reconciliation is required' in stale_cpu.stderr, stale_cpu.stderr
    env['FAKE_NANO_CPUS'] = '3000000000'
    current_cpu = subprocess.run(['bash', str(harness)], cwd=td, env=env, text=True, capture_output=True, timeout=10)
    assert current_cpu.returncode == 0, current_cpu.stdout + current_cpu.stderr
    # User override remains authoritative: if effective Compose raises Hermes to 1536 MiB,
    # live verification accepts that value rather than insisting on the generated 1040 MiB.
    env['FAKE_COMPOSE_LIMIT'] = '1536m'
    env['FAKE_COMPOSE_CPUS'] = '1.5'
    env['FAKE_MEMORY_BYTES'] = str(1536 * 1024 * 1024)
    env['FAKE_NANO_CPUS'] = '1500000000'
    overridden = subprocess.run(['bash', str(harness)], cwd=td, env=env, text=True, capture_output=True, timeout=10)
    assert overridden.returncode == 0, overridden.stdout + overridden.stderr

assert "policy v12" in features.lower()
print("v14.5.1 RESOURCE POLICY / OOM FIXTURES: PASS")
