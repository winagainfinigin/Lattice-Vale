#!/usr/bin/env python3
"""v14.6.6 policy-v14 bounded borrowing and failure-path regressions."""
from __future__ import annotations
import importlib.util
import json
import tempfile
import random
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / 'stack'
sys.path.insert(0, str(STACK))
from latticevale_arch import (host_memory_budget, resource_burst_metadata, service_memory_plan,
                              cpu_quota_plan, cpu_envelope_plan)  # noqa:E402

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
    'hermes': {'cpu_pct': 155, 'mem': 1920, 'charged_mem': 1940},
    'qmd-indexer': {'cpu_pct': 3.5, 'mem': 220, 'charged_mem': 320},
    'ollama': {'cpu_pct': 2.5, 'mem': 270, 'charged_mem': 340},
}
record = {'lastUpdate': 0, 'services': {
    'hermes': {'up': 1, 'idle': 0},
    'qmd-indexer': {'up': 0, 'idle': 2},
    'ollama': {'up': 0, 'idle': 2},
}}

def decide(cur=base, work=usage, old=record, *, avail=4096, mpsi=0.05, cpsi=0.2,
           load1=0.3, iopsi=0.0, fresh=False, directml=False, active=True, now=500):
    return module.plan(services, cur, work, old,
                       available_mib=avail, memory_psi=mpsi, cpu_psi=cpsi,
                       cpu_load1=load1, io_psi=iopsi, fresh_oom=fresh, cpus=8,
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

# Memory pressure, I/O pressure, OOM, or missing essential telemetry retains
# canonical caps. CPU PSI alone cannot veto safe within-envelope CPU transfers:
# hard per-container CFS quotas can create CPU PSI >85% at tiny host load.
for kw in ({'mpsi': 5}, {'iopsi': 15}, {'fresh': True},
           {'avail': None}, {'avail': 350}):
    constrained, _ = decide(**kw)
    assert constrained == {k: {'cpu': v['cpu'], 'mem': v['mem']} for k, v in base.items()}, kw
for host_load in (0.31, 8.0):
    high_cpu_psi, _ = decide(cpsi=88, load1=host_load)
    assert high_cpu_psi['hermes']['cpu'] > base['hermes']['cpu']
    assert sum(k['cpu'] for k in high_cpu_psi.values()) <= 4200
# Genuinely busy host CPU prevents additional *DirectML-reserved* loans, but
# still permits redistribution *inside* the canonical Docker envelope.
true_host_pressure, _ = decide(cpsi=88, load1=8.0, directml=True, active=False)
assert sum(k['cpu'] for k in true_host_pressure.values()) <= 4200
false_host_pressure, _ = decide(cpsi=88, load1=0.31, directml=True, active=False)
assert sum(k['cpu'] for k in false_host_pressure.values()) <= 4200 + min(2000//3, 800)

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
quiet = {k: {'cpu_pct': 5, 'mem': min(250, v['mem']//4),
             'charged_mem': min(300, v['mem']//3)} for k, v in services.items()}
settled_record = {'lastUpdate': 200, 'services': {
    k: {'up': 0, 'idle': 3} for k in services}}
settled, _ = decide(cur={k: {**base[k], **goal[k]} for k in services},
                    work=quiet, old=settled_record)
assert all(settled[k]['cpu'] <= goal[k]['cpu'] or settled[k]['cpu'] <= services[k]['cpu'] for k in services)
assert sum(v['cpu'] for v in settled.values()) <= 4200
assert sum(v['mem'] for v in settled.values()) <= 5120

# Borrowing is preemptible: if an idle donor awakens, recover baseline
# CPU immediately despite the 45s cooldown; return RAM only from safe headroom.
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


# Demand-matched CPU: a saturated receiver already at its legal cap cannot
# cause a background donor to lose CPU quota needlessly.
at_cpu_cap = {k: v.copy() for k, v in base.items()}
at_cpu_cap['hermes']['cpu'] = 3000  # 75% of four logical CPUs.
at_cpu_cap['qmd-indexer']['cpu'] = 700
at_cpu_cap['ollama']['cpu'] = 500
no_room_work = {
    'hermes': {'cpu_pct': 295, 'mem': 100, 'charged_mem': 120},
    'qmd-indexer': {'cpu_pct': 1, 'mem': 100, 'charged_mem': 120},
    'ollama': {'cpu_pct': 1, 'mem': 100, 'charged_mem': 120},
}
no_cpu_donation, _ = decide(cur=at_cpu_cap, work=no_room_work,
                            old={'lastUpdate': 0, 'services': {
                                k: {'up': 1 if k == 'hermes' else 0,
                                    'idle': 2 if k != 'hermes' else 0}
                                for k in services}}, now=500)
assert all(no_cpu_donation[k]['cpu'] == at_cpu_cap[k]['cpu'] for k in services)

# The same rule applies to memory: a capped receiver must not cause unused
# donor reductions, even when its working set is near the limit.
at_mem_cap = {k: v.copy() for k, v in base.items()}
at_mem_cap['hermes']['mem'] = 3584  # 1.75 x 2048-MiB canonical baseline.
at_mem_cap['qmd-indexer']['mem'] = 1024
at_mem_cap['ollama']['mem'] = 768
no_mem_room = {
    'hermes': {'cpu_pct': 2, 'mem': 3500, 'charged_mem': 3550},
    'qmd-indexer': {'cpu_pct': 1, 'mem': 150, 'charged_mem': 200},
    'ollama': {'cpu_pct': 1, 'mem': 150, 'charged_mem': 200},
}
no_mem_donation, _ = module.plan(
    services, at_mem_cap, no_mem_room,
    {'lastUpdate': 0, 'services': {k: {'up': 1 if k == 'hermes' else 0,
                                    'idle': 2 if k != 'hermes' else 0}
                                  for k in services}},
    available_mib=6000, memory_psi=0.1, cpu_psi=0.1, cpus=8,
    cpu_envelope=6000, budget=6400, now=500)
assert all(no_mem_donation[k]['mem'] == at_mem_cap[k]['mem'] for k in services)

# Only sustained, fresh throttling is an urgent CPU signal. Short-lived
# background wake-ups, missing records, and reset counters stay inconclusive.
assert module.sustained_quota_throttle(152, 152, 0, 0)
assert module.sustained_quota_throttle(120, 16, 0, 0)
assert not module.sustained_quota_throttle(3, 1, 0, 0)
assert not module.sustained_quota_throttle(150, 3, 0, 0)
assert not module.sustained_quota_throttle(150, 150, 200, 200)
assert not module.sustained_quota_throttle(150, 150, None, None)
assert not module.sustained_quota_throttle(150, 151, 0, 0)

# A freshly observed cgroup CPU quota bottleneck must be addressed during the
# ordinary 45-second cooldown, without simultaneously moving RAM ceilings.
throttle_work = {k: v.copy() for k, v in usage.items()}
throttle_work['hermes']['throttled'] = True
throttled, _ = decide(work=throttle_work,
                      old={'lastUpdate': 490, 'services': {
                          k: {'up': 0, 'idle': 2 if k != 'hermes' else 0}
                          for k in services}}, now=500)
assert throttled['hermes']['cpu'] > base['hermes']['cpu']
assert all(throttled[k]['mem'] == base[k]['mem'] for k in services)

# Missing cgroup memory.current disables memory donation, not CPU borrowing.
unknown_charge = {k: {'cpu_pct': v['cpu_pct'], 'mem': v['mem']}
                  for k, v in usage.items()}
missing_memory, _ = decide(work=unknown_charge)
assert missing_memory['hermes']['cpu'] > base['hermes']['cpu']
assert all(missing_memory[k]['mem'] == base[k]['mem'] for k in services)

# Priority-aware floors preserve background borrowing while avoiding the old
# 55% minimum for critical interactive services.
assert module.cpu_donor_floor('qmd-indexer', 300) == 200
assert module.cpu_donor_floor('hermes', 600) == 550
assert module.memory_donor_floor('qmd-indexer', 2048, 1024, 1200) >= 1504
assert module.memory_donor_floor('qmd-indexer', 2048, 1024, None) == 2048

# A user-owned override is allowed to coexist with burst borrowing only when
# the complete effective Compose model differs in Hermes image/pull policy alone.
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for file in ('compose.yaml', 'compose.latticevale.yaml', 'compose.override.yaml'):
        (root / file).write_text('services: {}\n')
    canonical = {'name': 'hermesstack', 'services': {
        'hermes': {'image': 'original:version', 'cpus': 0.5, 'mem_limit': '800m'},
        'ollama': {'image': 'ollama:version', 'cpus': 1.5, 'mem_limit': '2g'}}}
    customized = json.loads(json.dumps(canonical))
    customized['services']['hermes']['image'] = 'custom:version'
    customized['services']['hermes']['pull_policy'] = 'never'
    def fake_compose(args, cwd, timeout=12):
        assert args[:2] == ['docker', 'compose']
        assert args[-3:] == ['config', '--format', 'json']
        return json.dumps(customized if 'compose.override.yaml' in args else canonical)
    with patch.object(module, 'run', fake_compose):
        assert module.image_only_compose_override(root)
        customized['services']['hermes']['cpus'] = 0.7
        assert not module.image_only_compose_override(root)
        customized['services']['hermes']['cpus'] = 0.5
        customized['services']['ollama']['mem_limit'] = '3g'
        assert not module.image_only_compose_override(root)
        customized['services']['ollama']['mem_limit'] = '2g'
        customized['services']['hermes']['environment'] = ['UNVERIFIED=1']
        assert not module.image_only_compose_override(root)

# CPU baselines follow enabled services, WSL vCPU count, CPU inference vs.
# accelerated Ollama, and DirectML host reservation. These are portable
# constraints rather than a special case for the reporter's 4-core system.
for cores in (1, 2, 4, 8, 16, 32, 64):
    for accelerated in ('cpu', 'vulkan', 'nvidia', 'amd'):
        for directml_mode in (False, True):
            quota = cpu_quota_plan(
                cores, matrix_gateways=1, kanban_concurrency=3,
                accel=accelerated, directml_selected=directml_mode)
            envelope = cpu_envelope_plan(cores, directml_mode)
            assert sum(quota.values()) <= envelope['dockerEnvelopeMilli']
            assert max(quota.values()) < cores * 1000
            assert all(q >= 50 and q % 50 == 0 for q in quota.values())
            assert quota['hermes'] >= quota['qmd-indexer']
            if cores >= 2:
                assert quota['hermes'] > quota['qmd-indexer']
            if accelerated in ('cpu', 'vulkan'):
                assert quota['ollama'] >= quota['qmd-indexer']
            no_local_ollama = cpu_quota_plan(
                cores, 1, 3, accelerated, ollama=False,
                directml_selected=directml_mode)
            assert 'ollama' not in no_local_ollama
            assert sum(no_local_ollama.values()) <= envelope['dockerEnvelopeMilli']
# Performance-oriented reference case, without coding a hardware-specific
# allocation path: reserve 10% of four vCPUs for WSL/system scheduling.
reference = cpu_quota_plan(4, 1, 3, 'cpu')
assert reference['ollama'] >= 1200
assert reference['hermes'] >= 750
assert sum(reference.values()) <= 3600

# Bootstrap must call the same read-only resolved-Compose override check as
# the runtime controller when deciding whether to install a systemd timer.
boot_source = (ROOT / 'linux/bootstrap.sh').read_text()
assert '--check-override --stack "$stack_dir"' in boot_source
assert 'runuser -u "$linux_user" -- /usr/bin/python3' in boot_source
assert 'OnUnitInactiveSec=25s' in boot_source
assert 'OnBootSec=1min' in boot_source

# Portability sweep: derive everything from exposed WSL CPUs/RAM, selected
# services and backend, not machine-specific CPU/RAM tiers. Infeasible tiny
# configurations must reject impossible service floors without overcommitting.
qualified = 0
for ncpu in (1, 2, 4, 8, 16, 32, 64):
    for ram in (2048, 4096, 8192, 12288, 16384, 32768, 65536, 131072):
        for dml in (False, True):
            mem = host_memory_budget(ram, 'cpu', True, dml)
            envelope = cpu_envelope_plan(ncpu, dml)['dockerEnvelopeMilli']
            try:
                quotas = cpu_quota_plan(ncpu, 1, 3, 'cpu',
                    matrix=True, searxng=True, qmd=True, ollama=True, honcho=True,
                    directml_selected=dml)
                caps = service_memory_plan(mem['containerBudgetMiB'],
                    matrix=True, searxng=True, qmd=True, ollama=True, honcho=True,
                    hermes_floor=1024, ollama_floor=2048)
                floors = resource_burst_metadata(mem['containerBudgetMiB'],
                    matrix=True, searxng=True, qmd=True, ollama=True, honcho=True,
                    hermes_floor=1024, ollama_floor=2048)
            except ValueError:
                continue  # Explicit unsupported topology; never invent RAM.
            exp = {name: {'cpu': quotas[name], 'mem': caps[name],
                          'floor': floors[name]['memoryFloorMiB']}
                   for name in quotas}
            cur = {name: {'cpu': item['cpu'], 'mem': item['mem']}
                   for name, item in exp.items()}
            work = {name: {
                'cpu_pct': item['cpu'] * (0.09 if name == 'hermes' else 0.005),
                'mem': int(item['mem'] * (0.89 if name == 'hermes' else 0.10)),
                'charged_mem': int(item['mem'] * (0.91 if name == 'hermes' else 0.20))}
                for name, item in exp.items()}
            rec = {'lastUpdate': 0, 'services': {name: {
                'up': 1 if name == 'hermes' else 0,
                'idle': 2 if name != 'hermes' else 0}
                for name in exp}}
            goal, _ = module.plan(exp, cur, work, rec,
                available_mib=max(1024, mem['reserveMiB'] + 512),
                memory_psi=.01, cpu_psi=.02, io_psi=0.,
                cpus=ncpu, cpu_envelope=envelope,
                directml_selected=dml, directml_active=True,
                budget=mem['containerBudgetMiB'], now=500)
            assert sum(x['cpu'] for x in goal.values()) <= envelope
            assert sum(x['mem'] for x in goal.values()) <= mem['containerBudgetMiB']
            assert all(goal[k]['mem'] >= exp[k]['floor'] and goal[k]['cpu'] >= 50
                       for k in goal)
            qualified += 1
assert qualified >= 55

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
        displayed = rng.randint(0, cap['mem'])
        work[k] = {'mem': displayed,
                   'charged_mem': min(cap['mem'], displayed + rng.randint(0, 64)),
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
