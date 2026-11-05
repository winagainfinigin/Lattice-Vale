#!/usr/bin/env python3
"""v14.6.6 policy-v14 bounded borrowing and failure-path regressions."""
from __future__ import annotations
import importlib.util
import random
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / 'stack'
sys.path.insert(0, str(STACK))
from latticevale_arch import host_memory_budget, resource_burst_metadata, service_memory_plan  # noqa:E402

spec = importlib.util.spec_from_file_location('lv_resource_burst', STACK / 'resource-burst-controller.py')
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Conservative +2pp WSL host-headroom relaxation, while preserving floors.
for managed in (False, True):
    for directml in (False, True):
        last = -1
        for mem in range(3072, 25000, 501):
            plan = host_memory_budget(mem, 'cpu', managed, directml)
            assert plan['containerBudgetMiB'] + plan['reserveMiB'] == mem
            assert plan['containerBudgetMiB'] > last
            last = plan['containerBudgetMiB']
            if directml:
                assert plan['reserveMiB'] >= plan['directmlHostReserveMiB'] >= 0

meta = resource_burst_metadata(10123, matrix=True, searxng=True, qmd=True,
                               ollama=True, honcho=True, hermes_floor=1024, ollama_floor=2048)
limits = service_memory_plan(10123, matrix=True, searxng=True, qmd=True,
                             ollama=True, honcho=True, hermes_floor=1024, ollama_floor=2048)
assert set(meta) == set(limits)
assert all(0 < entry['memoryFloorMiB'] <= limits[k] for k, entry in meta.items())
assert all(entry['cpuShares'] > 0 for entry in meta.values())
assert meta['hermes']['cpuShares'] > meta['qmd-indexer']['cpuShares']
assert meta['qmd']['memoryFloorMiB'] == 1024
assert meta['qmd-indexer']['memoryFloorMiB'] == 1024

services = {
    'hermes': {'name': 'hermes-agent', 'cpu': 1600, 'mem': 2048, 'floor': 1024},
    'qmd-indexer': {'name': 'hermes-qmd-indexer', 'cpu': 1300, 'mem': 2048, 'floor': 1024},
    'ollama': {'name': 'hermes-ollama', 'cpu': 1300, 'mem': 1024, 'floor': 768},
}
base = {k: {'cpu': v['cpu'], 'mem': v['mem'], 'oom': False} for k, v in services.items()}
usage = {
    'hermes': {'cpu_pct': 155, 'mem': 1920},
    'qmd-indexer': {'cpu_pct': 3.5, 'mem': 220},
    'ollama': {'cpu_pct': 2.5, 'mem': 270},
}
record = {'lastUpdate': 0, 'services': {
    'hermes': {'up': 1, 'idle': 0},
    'qmd-indexer': {'up': 0, 'idle': 2},
    'ollama': {'up': 0, 'idle': 2},
}}

def decide(cur=base, work=usage, old=record, *, avail=4096, mpsi=0.05, cpsi=0.2,
           iopsi=0.0, fresh=False, directml=False, active=True, now=500):
    return module.plan(services, cur, work, old,
                       available_mib=avail, memory_psi=mpsi, cpu_psi=cpsi,
                       io_psi=iopsi, fresh_oom=fresh, cpus=8,
                       directml_selected=directml, directml_active=active,
                       cpu_envelope=4200, directml_reserve=2000 if directml else 0,
                       budget=5120, now=now)

goal, counters = decide()
assert goal['hermes']['cpu'] > base['hermes']['cpu']
assert goal['hermes']['mem'] > base['hermes']['mem']
assert goal['qmd-indexer']['cpu'] < base['qmd-indexer']['cpu']
assert goal['qmd-indexer']['mem'] < base['qmd-indexer']['mem']
assert sum(x['cpu'] for x in goal.values()) <= 4200
assert sum(x['mem'] for x in goal.values()) <= 5120
assert module.plan(services, base, {**usage, 'hermes': {'cpu_pct': 151, 'mem': 100}}, record, available_mib=4096, memory_psi=0.1, cpu_psi=0.5, cpus=8, cpu_envelope=4200, budget=5120, now=500)[0]['hermes']['cpu'] > 1600
assert counters['hermes']['up'] == 2 and counters['qmd-indexer']['idle'] == 3
assert all(goal[k]['mem'] >= services[k]['floor'] for k in services)

# No borrowing under reported memory pressure, CPU pressure, I/O pressure, OOM,
# missing telemetry, or insufficient available WSL RAM.
for kw in ({'mpsi': 5}, {'cpsi': 40}, {'iopsi': 15}, {'fresh': True},
           {'avail': None}, {'avail': 350}):
    constrained, _ = decide(**kw)
    assert constrained == {k: {'cpu': v['cpu'], 'mem': v['mem']} for k, v in base.items()}, kw

# An idle DirectML host worker can lend only bounded CPU headroom; once active,
# its reserve is immediately reclaimed even during cooldown.
idle, _ = decide(directml=True, active=False)
assert sum(x['cpu'] for x in idle.values()) <= 4200 + min(2000//3, 800)
assert sum(x['cpu'] for x in idle.values()) <= 7200
active_limits = {k: {**base[k], **idle[k]} for k in services}
active_record = {'lastUpdate': 498, 'services': {
    k: {'up': 2, 'idle': 0} for k in services}}
active, _ = decide(cur=active_limits, old=active_record, directml=True, active=True, now=500)
assert sum(v['cpu'] for v in active.values()) <= 4200

# Reset borrowed resources to baseline when contention subsides.
quiet = {k: {'cpu_pct': 5, 'mem': min(250, v['mem']//4)} for k, v in services.items()}
settled_record = {'lastUpdate': 200, 'services': {
    k: {'up': 0, 'idle': 3} for k in services}}
settled, _ = decide(cur={k: {**base[k], **goal[k]} for k in services},
                    work=quiet, old=settled_record)
assert all(settled[k]['cpu'] <= goal[k]['cpu'] or settled[k]['cpu'] <= services[k]['cpu'] for k in services)
assert sum(v['cpu'] for v in settled.values()) <= 4200
assert sum(v['mem'] for v in settled.values()) <= 5120

# Borrowing is preemptible: if an idle donor awakens, recover baseline
# CPU immediately despite the 75s cooldown; return RAM only from safe headroom.
borrowed = {k: {**base[k], **goal[k]} for k in services}
awakened_work = {**usage, 'qmd-indexer': {'cpu_pct': max(50, borrowed['qmd-indexer']['cpu'] / 10),
                                         'mem': int(borrowed['qmd-indexer']['mem'] * 0.84)}}
restored, _ = decide(cur=borrowed, work=awakened_work,
                     old={'lastUpdate': 498, 'services': {k: {'up': 0, 'idle': 0} for k in services}},
                     now=500)
assert restored['qmd-indexer']['cpu'] >= borrowed['qmd-indexer']['cpu']
assert restored['qmd-indexer']['mem'] >= borrowed['qmd-indexer']['mem']
assert sum(v['cpu'] for v in restored.values()) <= 4200
assert sum(v['mem'] for v in restored.values()) <= 5120

# Host DirectML CPU measurement: first sighting is conservative; two idle
# samples permit bounded borrowing, and renewed activity immediately reclaims.
with patch.object(module, 'directml_sample', side_effect=[{'41': 1000}, {'41': 1001}, {'41': 1002}, {'41': 5000}, None, {}]):
    telem = {}
    assert module.directml_workload(telem, 100) is True
    assert module.directml_workload(telem, 145) is True
    assert module.directml_workload(telem, 190) is False
    assert module.directml_workload(telem, 235) is True
    assert module.directml_workload(telem, 280) is True
    assert module.directml_workload(telem, 325) is False

# Parse both decimal and binary Docker memory units and absolute byte sizes.
assert module.mem_from_stats('1.5GiB / 2GiB') == 1536
assert module.mem_from_stats('1GB / 2GB') == 954
assert module.mem_from_stats('512MiB / 1GiB') == 512

# Test transactional Docker update rollback without touching Docker/WSL.
updates = []
def fake_run(args, cwd, timeout=12):
    updates.append(args)
    return 'ok'
with patch.object(module, 'run', fake_run):
    changed = module.perform(Path('/not-used'), services, base, goal)
assert changed
assert all(cmd[:2] == ['docker', 'update'] for cmd in updates)

updates.clear()
def fail_second(args, cwd, timeout=12):
    updates.append(args)
    if len(updates) == 2:
        raise RuntimeError('simulated Docker failure')
    return 'ok'
with patch.object(module, 'run', fail_second):
    try:
        module.perform(Path('/not-used'), services, base, goal)
    except RuntimeError as exc:
        assert 'rollback attempted' in str(exc)
    else:
        raise AssertionError('must propagate transaction failure')
assert len(updates) >= 3 and updates[-1][:2] == ['docker', 'update']

# Deterministic property sweeps: arbitrary pressures, uneven memory usage,
# changing DirectML states, and differing live limits cannot manufacture CPU/RAM.
rng = random.Random(1466)
for i in range(600):
    work = {}
    for k, cap in services.items():
        work[k] = {'mem': rng.randint(0, cap['mem']),
                   'cpu_pct': rng.uniform(0, cap['cpu'] / 10)}
    trial, _ = decide(work=work, avail=rng.randint(256, 10000),
                      mpsi=rng.uniform(0, 4), cpsi=rng.uniform(0, 40),
                      iopsi=rng.uniform(0, 20),
                      directml=(i%2 == 0), active=(i%4 != 0))
    assert sum(v['mem'] for v in trial.values()) <= 5120
    assert sum(v['cpu'] for v in trial.values()) <= 4200 + (min(2000//3, 800) if i%4 == 0 else 0)
    assert all(trial[k]['mem'] >= services[k]['floor'] and trial[k]['cpu'] >= 50 for k in services)

cfg = (STACK / 'configure-stack.sh').read_text()
boot = (ROOT / 'linux/bootstrap.sh').read_text()
uninst = (ROOT / 'Uninstall-LatticeVale.ps1').read_text()
audit = (STACK / 'state-audit.py').read_text()
assert 'resource-burst-controller.py --verify' in cfg
assert 'resource_policy["FLOOR_${resource_state_key}_MIB"]' in cfg
assert 'resource_policy["SHARES_${resource_state_key}"]' in cfg
assert 'mem_reservation: "%sm"' in cfg and 'cpu_shares: %s' in cfg
ps1 = (ROOT / 'Install-LatticeVale.ps1').read_text()
assert "'stack\\resource-burst-controller.py'" in ps1
assert "'runtime-policy.py','resource-burst-controller.py','diagnostics.py'" in ps1
assert 'latticevale-resource-burst.timer' in boot
assert 'resource-burst-controller.py" "$stack_dir/resource-burst-controller.py"' in boot
assert 'latticevale-resource-burst.timer' in uninst
assert 'burst_valid = (burst_rc == 0)' in audit
print('v14.6.6 bounded-burst resource controller / orchestration fixtures: PASS')
