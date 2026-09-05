#!/usr/bin/env python3
"""v14.5.1-origin CPU/RAM adaptation regressions against the 14.6 canonical engine."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
sys.path.insert(0, str(ROOT / 'stack'))
from latticevale_arch import cpu_quota_plan, host_memory_budget, service_memory_plan  # noqa:E402

assert '[POLICY_VERSION]=12' in cfg
assert '[RESOURCE_POLICY_MODE]=adaptive' in cfg
assert 'runtime-policy.py host-budget' in cfg
assert 'runtime-policy.py cpu-plan' in cfg
assert 'runtime-policy.py service-plan' in cfg
assert 'PY_RESOURCE_PLAN' not in cfg
assert 'LOW_MEMORY_PROFILE' not in cfg
assert 'mem_mib <= 12288' not in cfg

# Host resource policy is continuous/adaptive: arbitrary RAM inputs must remain
# bounded and larger allocations may never reduce the container budget.
for accel in ('cpu','vulkan','nvidia','amd'):
    for managed in (False, True):
        for directml in (False, True):
            previous = -1
            for mem in (2053, 3187, 4771, 7039, 9587, 13711, 22103, 38917, 73129):
                state = host_memory_budget(mem, accel, managed, directml)
                assert state['reserveMiB'] >= 0
                assert state['directmlHostReserveMiB'] >= 0
                assert state['reserveMiB'] + state['containerBudgetMiB'] == mem
                assert state['containerBudgetMiB'] >= 384
                assert state['containerBudgetMiB'] >= previous
                previous = state['containerBudgetMiB']
                if directml:
                    assert state['reserveMiB'] >= state['directmlHostReserveMiB'] > 0
                else:
                    assert state['directmlHostReserveMiB'] == 0

# CPU quotas derive from CPUs visible to WSL and workload pressure, not host tiers.
for accel in ('cpu','vulkan','nvidia','amd'):
    prev = 0
    for cpus in (1,2,3,5,7,11,19,37):
        q = cpu_quota_plan(cpus, 1, 3, accel)
        cap = cpus * 1000
        assert all(250 <= value <= cap for value in q.values())
        assert q['hermes'] >= prev
        prev = q['hermes']
        busy = cpu_quota_plan(cpus, 8, 8, accel)
        assert busy['hermes'] >= q['hermes']
        assert all(250 <= value <= cap for value in busy.values())

# Enabled services are planned from the current container budget.  Find the minimum
# viable budget dynamically rather than freezing a machine-specific threshold.
def full_plan(budget: int):
    return service_memory_plan(budget, matrix=True, searxng=True, qmd=True, ollama=True,
                               honcho=True, hermes_floor=1024, ollama_floor=3072)

lo, hi = 384, 65536
while lo < hi:
    mid = (lo + hi) // 2
    try:
        full_plan(mid); hi = mid
    except ValueError:
        lo = mid + 1
threshold = lo
assert threshold > 384
assert sum(full_plan(threshold).values()) <= threshold
try:
    full_plan(threshold - 1)
except ValueError as exc:
    assert 'cannot safely fit selected services' in str(exc)
else:
    raise AssertionError('planner admitted a budget below its own adaptive service minima')

# Larger arbitrary budgets preserve enabled-service identity and never shrink service limits.
previous = None
for budget in (threshold, threshold + 337, threshold + 1291, threshold + 4703, threshold + 15317):
    alloc = full_plan(budget)
    assert sum(alloc.values()) <= budget
    assert set(alloc) == {'hermes','synapse-db','synapse','searxng-valkey','searxng','qmd','qmd-indexer','ollama','honcho-db','honcho-redis','honcho-api','honcho-deriver'}
    if previous:
        for name in alloc:
            assert alloc[name] >= previous[name], (name, budget, previous[name], alloc[name])
    previous = alloc

# A lighter service selection remains viable at a correspondingly smaller envelope.
core = service_memory_plan(1103, matrix=False, searxng=False, qmd=False, ollama=False,
                           honcho=False, hermes_floor=1024, ollama_floor=0)
assert core['hermes'] >= 1024 and sum(core.values()) <= 1103

print('v14.5.1 ADAPTIVE HARDWARE MATRIX FIXTURES: PASS')
