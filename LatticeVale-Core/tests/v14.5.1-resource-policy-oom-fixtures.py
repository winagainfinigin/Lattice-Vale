#!/usr/bin/env python3
"""v14.5.1 resource-policy v9 CPU/RAM and running-container OOM regression fixtures."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / "VERSION.txt").read_text(encoding="ascii").strip()
assert version in {"14.5.1","14.5.2"}, version

cfg = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
manage = (ROOT / "stack/manage.sh").read_text(encoding="utf-8")
boot = (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8")
audit = (ROOT / "stack/state-audit.py").read_text(encoding="utf-8")
features = (REPO / "docs/FEATURES.md").read_text(encoding="utf-8")

# v4 was proven to starve the central Hermes cgroup on a real ~9.7 GiB full stack.
assert "POLICY_VERSION=9" in cfg
assert 'saved_version" == 9' in cfg
assert './configure-stack.sh --refresh-resource-policy' in manage
assert './configure-stack.sh --refresh-resource-policy' in boot
assert 'values.get("POLICY_VERSION") != "9"' in audit

# Preserve the conservative <=6 GiB reserve. Policy v9 gives CPU-backed managed
# Ollama extra hard-limit headroom on >6-12 GiB WSL VMs while retaining a bounded
# host reserve; non-CPU Ollama and other >6-24 GiB shapes keep the 20% reserve.
assert 'mem_mib <= 6144 )); then' in cfg and 'reserve_pct=30' in cfg
assert 'mem_mib <= 12288 )) && [[ "$accel" == cpu ]] && managed_ollama_enabled' in cfg
assert 'reserve_pct=10' in cfg
assert 'mem_mib <= 24576 )); then' in cfg and 'reserve_pct=20' in cfg
assert "specs=[('hermes',8,hermes_floor,hermes_cap)]" in cfg
assert 'resource_hermes_floor_mib() {' in cfg
assert "('honcho-api',4,512,3072)" in cfg
assert 'requested_ollama_floor' in cfg
assert 'resource_ollama_model_metrics() {' in cfg
assert 'OLLAMA_MODEL_FLOOR_MIB=%s' in cfg

# Clean installs persist the exact generated service ceilings, while repair verification
# compares those desired values with Docker HostConfig.Memory so a current YAML file
# cannot hide an old live cgroup from a pre-v7 container.
for marker in (
    "LIMIT_%s_MIB=%s",
    "verify_live_resource_policy_limits() {",
    "{{.HostConfig.Memory}}",
    "docker compose config --format json",
    "live Docker CPU/RAM ceilings do not match the current adaptive resource policy",
    "Reconcile completed but the live Docker CPU/RAM ceilings still do not match policy v9",
):
    assert marker in cfg, marker

# Execute the embedded allocator with the exact budget produced by the audited host:
# 9946 MiB visible with CPU-backed managed Ollama: policy v9 uses a 10% reserve,
# giving 1491 MiB host headroom and an 8455 MiB managed-container budget.
start = cfg.index("import sys\nbudget=int(sys.argv[1])", cfg.index("<<'PY_RESOURCE_PLAN'"))
end = cfg.index("\nPY_RESOURCE_PLAN", start)
planner = cfg[start:end]

def plan_result(budget: int, matrix=True, searxng=True, qmd=True, ollama=True, honcho=True, accel='cpu', hermes_floor=1024, ollama_floor=5120):
    args = [str(budget)] + [('true' if x else 'false') for x in (matrix,searxng,qmd,ollama,honcho)] + [accel, str(hermes_floor), str(ollama_floor)]
    return subprocess.run([sys.executable, "-c", planner, *args], text=True, capture_output=True, timeout=10)

def plan(budget: int, matrix=True, searxng=True, qmd=True, ollama=True, honcho=True, accel='cpu', hermes_floor=1024, ollama_floor=5120):
    r = plan_result(budget, matrix, searxng, qmd, ollama, honcho, accel, hermes_floor, ollama_floor)
    assert r.returncode == 0, r.stderr
    out = {}
    for line in r.stdout.splitlines():
        k,v=line.split('=',1); out[k]=int(v)
    return out

full = plan(8952)
assert sum(full.values()) <= 8952, full
assert full["hermes"] >= 1024, full
assert full["ollama"] >= 5120, full
assert full["honcho-api"] >= 512, full
assert full["honcho-deriver"] >= 384, full
# Lock the audited ~9.7 GiB CPU-backed full-stack shape so future allocator changes
# cannot regress into memory.max pressure again. Policy v6 produced only 4128 MiB
# Ollama and the live cgroup recorded >15k max-pressure events at ~98% usage.
assert full["hermes"] == 1040, full
assert full["honcho-api"] == 528, full
assert full["honcho-deriver"] == 400, full
assert full["ollama"] == 5152, full
# Regression target: v4 generated 544 MiB for Hermes; v6 left CPU Ollama too tight.
assert full["hermes"] > 544 and full["ollama"] > 4128, full

# Policy v9 makes the CPU-backed Ollama 4608 MiB floor a viability requirement.
# A full selected stack therefore needs >=8320 MiB managed container budget.
for budget in (768, 1280, 2868, 5735, 7958, 8831):
    r = plan_result(budget)
    assert r.returncode == 3, (budget, r.returncode, r.stdout, r.stderr)
    assert "cannot safely fit the selected services" in r.stderr, (budget, r.stderr)

# Lighter selections remain adaptive. Core Hermes alone still fits 1280 MiB.
# Hermes + CPU-backed managed Ollama requires >=5632 MiB, while GPU-backed managed
# Ollama keeps the older best-effort floor and can fit smaller selected-service sets.
core = plan(1280, matrix=False, searxng=False, qmd=False, ollama=False, honcho=False)
assert core["hermes"] >= 1024 and sum(core.values()) <= 1280, core
assert plan_result(6143, matrix=False, searxng=False, qmd=False, ollama=True, honcho=False).returncode == 3
core_ollama = plan(6144, matrix=False, searxng=False, qmd=False, ollama=True, honcho=False)
assert core_ollama["hermes"] >= 1024 and core_ollama["ollama"] >= 5120, core_ollama
gpu_small = plan(3584, matrix=False, searxng=False, qmd=False, ollama=True, honcho=False, accel='nvidia', ollama_floor=2304)
assert gpu_small["hermes"] >= 1024 and gpu_small["ollama"] >= 2048, gpu_small

# Once CPU full-stack minima fit, larger budgets remain bounded and positive.
for budget in (8832, 8952, 9831, 13108, 28672, 61440):
    alloc = plan(budget)
    assert alloc and all(v > 0 for v in alloc.values()), (budget, alloc)
    assert sum(alloc.values()) <= budget, (budget, sum(alloc.values()), alloc)

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
# 544 MiB live Hermes cgroup must fail even when the desired v9 state says 1040 MiB;
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
    (td / '.latticevale-resource-state').write_text('POLICY_VERSION=9\nMATRIX_PROFILE_GATEWAYS=0\nKANBAN_CONCURRENCY=1\nHERMES_MIN_MIB=1024\nLIMIT_HERMES_MIB=1040\nCPU_HERMES_MILLI=3000\n', encoding='utf-8')
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

assert "policy v9" in features.lower()
print("v14.5.1 RESOURCE POLICY / OOM FIXTURES: PASS")
