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


# V14.6.7: effective Compose/live HostConfig drift after a running-container repair.
assert module._compose_memory_bytes('1124073472') == 1124073472
assert module._compose_memory_bytes('1072MiB') == 1124073472
assert module._compose_cpu_nanos('0.15') == 150000000
for invalid in ('-1', '0', 'invalid', '1.1b'):
    try:
        module._compose_memory_bytes(invalid)
    except RuntimeError:
        pass
    else:
        raise AssertionError(('invalid memory accepted', invalid))


def fixture(running=True, owner='hermesstack', *, dynamic=False, pending=False, initial=1073741824,
            expected=1124073472, second_old=1_200_000_000, second_expected=1_200_000_000,
            break_after=None, low_headroom=False, old_cpu=150000000, target_cpu=150000000):
    with tempfile.TemporaryDirectory(prefix='lv-resource-wsl-') as temp:
        root = Path(temp)
        desired = {'hermes': {'name': 'hermes-agent', 'memory': expected, 'cpu': target_cpu},
                   'qmd': {'name': 'hermes-qmd', 'memory': second_expected, 'cpu': 250000000}}
        live = {'hermes': {'id': 'container-id-hermes', 'memory': initial, 'cpu': old_cpu, 'swap': 2_500_000_000},
                'qmd': {'id': 'container-id-qmd', 'memory': second_old, 'cpu': 250000000, 'swap': 3_000_000_000}}
        updates = []
        failures = [0]
        def fake_run(args, cwd, timeout=12):
            assert cwd == root
            if args[:3] == ['docker', 'compose', 'config']:
                return json.dumps({'services': {k: {'mem_limit': e['memory'], 'cpus': e['cpu'] / 1e9} for k,e in desired.items()}})
            if args[:2] == ['docker', 'inspect']:
                return json.dumps([{
                    'Name': '/' + e['name'], 'Id': live[k]['id'],
                    'State': {'Running': running, 'Pid': 400},
                    'Config': {'Labels': {'com.docker.compose.project': owner,
                                          'com.docker.compose.service': k}},
                    'HostConfig': {'Memory': live[k]['memory'], 'NanoCpus': live[k]['cpu'],
                                   'MemorySwap': live[k]['swap']}}
                    for k,e in desired.items()])
            if args[:2] == ['docker', 'update']:
                name = args[-1]
                key = next(k for k,e in desired.items() if e['name'] == name)
                metric = 'memory' if args[2] == '--memory' else 'cpu'
                if break_after is not None and len(updates) == break_after and failures[0] == 0:
                    failures[0] += 1
                    raise RuntimeError('injected docker update failure')
                old = live[key][metric]
                value = int(args[3][:-1]) if metric == 'memory' else int(round(float(args[3])*1e9))
                live[key][metric] = value
                updates.append((key, metric, old, value))
                return name
            raise AssertionError(args)
        canonical = {k: {'name': e['name']} for k,e in desired.items()}
        snapshot = {'policyFingerprint': 'demo', 'pending': {'hermes': {}} if pending else None}
        (root / 'data/latticevale').mkdir(parents=True, exist_ok=True)
        (root / 'data/latticevale/resource-burst-state.json').write_text(json.dumps(snapshot))
        with (patch.object(module, 'load_expected', return_value=(canonical, {'POLICY_FINGERPRINT':'demo'})),
              patch.object(module, 'run', side_effect=fake_run),
              patch.object(module, 'verify_snapshot', side_effect=(None if dynamic else RuntimeError('no lease'))),
              patch.object(module, 'cgroup_event_counters', return_value={'memory_current_mib': 1000 if not low_headroom else 2000})):
            error = None
            try:
                module.reconcile_static_limits(root)
            except RuntimeError as exc:
                error = str(exc)
        return error, live, updates, desired

error, live, updates, desired = fixture()
assert error is None, error
assert updates == [('hermes', 'memory', 1073741824, 1124073472)]
assert live['hermes']['memory'] == desired['hermes']['memory']
assert fixture(initial=1124073472)[2] == []  # already converged, idempotent
assert fixture(dynamic=True)[2] == []  # controller lease wins
error,live,updates,_ = fixture(initial=1124073472, old_cpu=100000000, target_cpu=150000000)
assert error is None and updates == [('hermes', 'cpu', 100000000, 150000000)]
assert live['hermes']['cpu'] == 150000000
error,_,updates,_ = fixture(owner='unrelated-project')
assert 'unverified Docker ownership' in error and not updates
error,_,updates,_ = fixture(running=False)
assert 'not running' in error and not updates
error,_,updates,_ = fixture(pending=True)
assert 'incomplete burst-controller transaction' in error and not updates
error,_,updates,_ = fixture(initial=1400000000, expected=1073741824, low_headroom=True)
assert 'adequate measured cgroup headroom' in error and not updates
error,live,updates,_ = fixture(initial=1073741824, second_old=1200000000, second_expected=1400000000,
                               break_after=1)
assert 'injected docker update failure' in error
assert live['hermes']['memory'] == 1073741824  # rollback after second change failed
assert updates[-1][3] == 1073741824
print('V14.6.7 DOCKER STATIC RESOURCE RECOVERY FIXTURES: PASS')


# V14.6.7: reproduce the 2026-11-08 12-container live audit.  Eleven
# identities and allocations agree with the saved lease, while the recreated
# SearXNG container is at the exact canonical Compose ceiling.  Two loaded
# services cannot safely tolerate a wholesale static memory reduction.
from copy import deepcopy
import time

# value tuple: canonical MiB, live MiB, canonical CPU m, live CPU m
observed = {
    'hermes': (1072, 1024, 850, 850),
    'honcho-api': (400, 416, 150, 150),
    'honcho-db': (208, 192, 150, 150),
    'honcho-deriver': (272, 272, 150, 150),
    'honcho-redis': (80, 80, 100, 100),
    'ollama': (5728, 5808, 1350, 1350),
    'qmd': (1040, 1024, 150, 150),
    'qmd-indexer': (1040, 1024, 150, 100),
    'searxng': (208, 208, 150, 150),
    'searxng-valkey': (80, 80, 100, 100),
    'synapse': (208, 208, 150, 150),
    'synapse-db': (176, 176, 150, 150),
}
assert sum(v[1] for v in observed.values()) == 10512
assert sum(v[3] for v in observed.values()) == 3550


def snapshot_case(*, edits=None, active_override=False, pending=None, bad_fingerprint=False,
                  changing_identity=False, timer=False):
    with tempfile.TemporaryDirectory(prefix='lv-snapshot-rebind-') as tmp:
        root = Path(tmp)
        store = root / 'data/latticevale/resource-burst-state.json'
        store.parent.mkdir(parents=True)
        expected = {k: {'name': module.PAIRS[k], 'mem': x[0], 'cpu': x[2],
                        'floor': min(x[0], x[1])} for k, x in observed.items()}
        state = {'POLICY_FINGERPRINT': 'audited-fingerprint', 'BUDGET_MIB':'10512',
                 'CPU_DOCKER_ENVELOPE_MILLI':'3600', 'DIRECTML_SELECTED':'false',
                 'CPU_DIRECTML_RESERVE_MILLI':'0', 'CPUS':'4'}
        live = {k: {'id': f'current-{k}', 'mem': x[1], 'cpu': x[3],
                    'memory_current_mib': 5696 if k=='ollama' else 358 if k=='honcho-api' else 50}
                for k,x in observed.items()}
        saved = deepcopy(live)
        saved['searxng']['id'] = 'previous-searxng'
        saved['searxng']['up'] = 2
        saved['searxng']['idle'] = 1
        saved['ollama']['up'] = 3
        saved['ollama']['idle'] = 0
        snapshot = {'policyFingerprint': 'WRONG' if bad_fingerprint else 'audited-fingerprint',
                    'services': saved, 'pending': pending,
                    'lastUpdate':time.time(), 'lastSample':time.time(),
                    'directmlCpuTelemetry':{'busy':True,'idle':0}}
        if edits:
            edits(live, saved, expected, snapshot, state)
        store.write_text(json.dumps(snapshot))
        before = store.read_bytes()
        updates = []
        inspects = [0]
        def fake_run(args, cwd, timeout=12):
            assert cwd == root
            if args[:3] == ['docker','compose','config']:
                return json.dumps({'services': {k: {
                    'mem_limit':str(e['mem'] * module.MIB), 'cpus':e['cpu']/1000}
                    for k,e in expected.items()}})
            if args[:2] == ['docker','inspect']:
                inspects[0] += 1
                if changing_identity and inspects[0] >= 4:
                    live['searxng']['id'] = 'changed-midflight'
                return json.dumps([{
                    'Name':'/'+expected[k]['name'], 'Id':v['id'],
                    'State':{'Running':True,'Pid':901},
                    'Config':{'Labels':{'com.docker.compose.project':
                                         'badproject' if active_override and k=='searxng' else 'hermesstack',
                                         'com.docker.compose.service': k}},
                    'HostConfig':{'Memory':v['mem']*module.MIB,
                                  'NanoCpus':v['cpu']*10**6,
                                  'MemorySwap':max(1, 2*v['mem']*module.MIB)}
                } for k,v in live.items()])
            if args[:2] == ['docker','update']:
                updates.append(args)
                raise AssertionError('Resource limits MUST NOT change during this test')
            raise AssertionError(args)
        err = None
        simulated_usage = {k:{'mem':100, 'cpu_pct':1.0, 'charged_mem':50} for k in expected}
        with (patch.object(module,'load_expected',return_value=(expected,state)),
              patch.object(module,'run',side_effect=fake_run),
              patch.object(module,'cgroup_event_counters',return_value={'memory_current_mib':5696}),
              patch.object(module,'read_usage',return_value=simulated_usage),
              patch.object(module,'pressure',return_value=0.01),
              patch.object(module,'host_available_mib',return_value=4096),
              patch.object(module,'host_cpu_load1',return_value=0.1)):
            try:
                assert not module.verify_snapshot(root), 'prior snapshot must not validate'
            except RuntimeError:
                pass
            try:
                result=(module.run_once(root,restore=False) if timer else
                        module.reconcile_static_limits(root))
                assert result==0
            except Exception as exc:
                err=str(exc)
            new = json.loads(store.read_text())
            success = err is None
            if success:
                assert module.verify_snapshot(root)
                assert module.reconcile_static_limits(root)==0
            changed = store.read_bytes()!=before
        return success,err,updates,before,new,changed,live,snapshot,inspects[0]

ok,err,updates,before,after,changed,live,prior,count=snapshot_case()
assert ok,err
assert changed and not updates
assert after['services']['searxng']['id']=='current-searxng'
assert after['services']['searxng']['up']==after['services']['searxng']['idle']==0
assert after['services']['ollama']==prior['services']['ollama']
assert after['pending'] is None and after['lastUpdate']==prior['lastUpdate']
assert len(after['services']) == 12
assert count >= 3
# The recurring controller also automatically rebinds under its own lock.
ok,err,updates,before,after,changed,live,prior,count=snapshot_case(timer=True)
assert ok and changed and not updates, err
assert after['services']['searxng']['id']=='current-searxng'
assert after['pending'] is None

# Unchanged container drift cannot be relabeled as an innocent replacement.
# Replacement must be at canonical limit, within budget, and have true ownership.
negative_cases = [
    ('unchanged drift', lambda l,s,e,r,t: l['ollama'].__setitem__('mem',5728),
     'unexplained resource drift'),
    ('noncanonical replacement',lambda l,s,e,r,t:l['searxng'].__setitem__('mem',224),
     'not at verified canonical limits'),
    ('excess aggregate RAM',lambda l,s,e,r,t:
     (l['hermes'].__setitem__('mem',1096),s['hermes'].__setitem__('mem',1096)),
     'memory envelope'),
    ('excess CPU envelope',lambda l,s,e,r,t:
     (l['hermes'].__setitem__('cpu',1000),s['hermes'].__setitem__('cpu',1000)),
     'CPU envelope'),
    ('saved fingerprint stale',lambda l,s,e,r,t:r.__setitem__('policyFingerprint','stale'),
     'adequate measured cgroup headroom'),
    ('malformed snapshot record',lambda l,s,e,r,t:s['ollama'].__setitem__('mem','invalid'),
     'malformed live or saved'),
]
for label,edit,expected_err in negative_cases:
    ok,err,updates,before,after,changed,*_=snapshot_case(edits=edit)
    assert not ok and expected_err in (err or ''), (label,err)
    assert not changed and not updates, (label,changed,updates)

ok,err,updates,before,after,changed,*_=snapshot_case(active_override=True)
assert not ok and 'ownership' in err and not changed and not updates
ok,err,updates,before,after,changed,*_=snapshot_case(pending={'ollama':{'mem':5728}})
assert not ok and 'pending' in err and not changed and not updates
ok,err,updates,before,after,changed,*_=snapshot_case(changing_identity=True)
assert not ok and 'concurrent Docker identity/resource change' in err and not changed and not updates, (ok,err,changed,updates)

# Explicit restores are also protected against shrinking a loaded Ollama model.
try:
    module.assert_safe_memory_reductions(
        {'ollama':{'mem':5808,'memory_current_mib':5696}},
        {'ollama':{'mem':5728}})
except RuntimeError as exc:
    assert 'cgroup headroom' in str(exc)
else:
    raise AssertionError('unsafe Ollama reduction was accepted')
module.assert_safe_memory_reductions(
    {'qmd':{'mem':1024,'memory_current_mib':150}},
    {'qmd':{'mem':992}})
try:
    module.assert_safe_memory_reductions(
        {'ollama':{'mem':5808}}, {'ollama':{'mem':5728}})
except RuntimeError:
    pass
else:
    raise AssertionError('missing cgroup charge incorrectly allowed reduction')

assert '--prepare-repair --stack "$stack_dir"' in (ROOT/'linux/bootstrap.sh').read_text()
print('V14.6.7 VERIFIED REPLACEMENT / 12-SERVICE SNAPSHOT REBIND FIXTURES: PASS')

# A zero-length pending journal is not equivalent to a completed transaction.
ok,err,updates,before,after,changed,*_=snapshot_case(pending={})
assert not ok and 'pending' in err and not changed and not updates

# A failed atomic persistence cannot mutate the original snapshot or Docker.
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    original = {'policyFingerprint':'x', 'services':{'hermes':{'id':'old','mem':1000,'cpu':100}},
                'pending':None, 'lastSample':time.time()}
    target = root/'data/latticevale/resource-burst-state.json'
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(original))
    expected = {'hermes':{'name':'hermes-agent','mem':1000,'cpu':100,'floor':800}}
    live = {'hermes':{'id':'new','mem':1000,'cpu':100}}
    state = {'POLICY_FINGERPRINT':'x','BUDGET_MIB':'1500',
             'CPU_DOCKER_ENVELOPE_MILLI':'150','DIRECTML_SELECTED':'false'}
    before = target.read_bytes()
    with (patch.object(module,'_static_compose_limits',return_value={'hermes':
               {'name':'hermes-agent','memory':1000*module.MIB,'cpu':100000000}}),
          patch.object(module,'inspect_containers',return_value=live),
          patch.object(module,'write_json',side_effect=PermissionError('injected disk write failure'))):
        try:module.reconcile_verified_replacements(root, expected, state, live)
        except PermissionError as exc:assert 'injected' in str(exc)
        else:raise AssertionError('atomic persistence failure ignored')
    assert target.read_bytes()==before

# Verification-only repair preparations must preserve a healthy lease.
with (patch.object(module,'verify_snapshot',return_value=True) as verify,
      patch.object(module,'run_once',side_effect=AssertionError('restore called on healthy lease'))):
    with patch.object(sys,'argv',['resource-burst-controller.py','--prepare-repair']):
        assert module.main()==0
    assert verify.called

print('V14.6.7 SNAPSHOT SAFETY / ATOMIC WRITE / REPAIR IDEMPOTENCE: PASS')

# Upgrade staging must not pass --prepare-repair to the *old* installed
# controller, which does not support that flag. It must use read-only --verify
# before the source copy and defer uncertain state to the new implementation.
_boot = (ROOT / 'linux/bootstrap.sh').read_text()
assert "--help 2>/dev/null | grep -q -- '--prepare-repair'" in _boot
assert 'resource-burst-controller.py" --verify --stack "$stack_dir"' in _boot
assert _boot.index('--prepare-repair --stack "$stack_dir"') < _boot.index('"$bundle_root/stack/resource-burst-controller.py" "$stack_dir/resource-burst-controller.py"')
print('V14.6.7 PRE-STAGING OLD-CONTROLLER COMPATIBILITY: PASS')


# Nov 13, 2026 12-service replacement-budget regression (added to the
# existing fixture, retaining the established 151-test shard contract).
#!/usr/bin/env python3
"""Regression: Nov 13, 2026 12-service, 3-replacement, +16-MiB budget drift.

Pure mocks: never interact with a running Docker engine or modify user state.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

STACK = Path(__file__).resolve().parents[1] / 'stack'
sys.path.insert(0, str(STACK))
spec = importlib.util.spec_from_file_location('budget_recovery', STACK / 'resource-burst-controller.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
MIB = mod.MIB

# (canonical memory, saved memory, live memory, cpu m, floor, charged memory)
OBSERVED = {
    'hermes': (1072, 1072, 1072, 850, 1024, 682),
    'synapse': (208, 208, 208, 150, 192, 204),
    'synapse-db': (176, 176, 176, 150, 160, 126),
    'searxng': (208, 208, 208, 150, 192, 205),
    'searxng-valkey': (80, 80, 80, 100, 64, 35),
    'qmd': (1040, 1024, 1024, 150, 1024, 171),
    'qmd-indexer': (1040, 1040, 1040, 150, 1024, 14),
    'ollama': (5728, 5760, 5760, 1350, 5632, 5648),
    'honcho-api': (400, 400, 400, 150, 384, 352),
    'honcho-db': (208, 192, 208, 150, 192, 114),
    'honcho-redis': (80, 80, 80, 100, 64, 73),
    'honcho-deriver': (272, 272, 272, 150, 256, 272),
}
assert sum(v[0] for v in OBSERVED.values()) == 10512
assert sum(v[1] for v in OBSERVED.values()) == 10512
assert sum(v[2] for v in OBSERVED.values()) == 10528
assert sum(v[3] for v in OBSERVED.values()) == 3600


def simulate(*, missing_charge=False, corrupt_owner=False, extra_drift=False,
             fail_update=False, crash_mid_update=False, fake_changed_id=False):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = root / 'data/latticevale/resource-burst-state.json'
        store.parent.mkdir(parents=True)
        expect = {k: {'name': mod.PAIRS[k], 'mem': v[0], 'cpu': v[3], 'floor': v[4]}
                  for k,v in OBSERVED.items()}
        state = {'POLICY_FINGERPRINT':'audit-2026-11-13', 'BUDGET_MIB':'10512',
                 'CPU_DOCKER_ENVELOPE_MILLI':'3600', 'DIRECTML_SELECTED':'false'}
        current = {k:{'id':'current-'+k, 'mem':v[2], 'cpu':v[3], 'memory_current_mib':v[5]}
                   for k,v in OBSERVED.items()}
        saved = {k:{**v,'id': ('prior-'+k if k in ('synapse-db','searxng','honcho-db') else v['id']),
                    'up':2, 'idle':1} for k,v in current.items()}
        for k,v in OBSERVED.items():
            saved[k]['mem'] = v[1]
        if missing_charge:
            current['hermes'].pop('memory_current_mib')
            current['qmd-indexer'].pop('memory_current_mib')
        if extra_drift:
            current['ollama']['mem'] += 16
        if fake_changed_id:
            saved['qmd']['id'] = 'old-qmd'
        initial = {'policyFingerprint':state['POLICY_FINGERPRINT'], 'services':saved,
                   'pending':None, 'lastSample':32, 'lastUpdate':34}
        store.write_text(json.dumps(initial))
        updates=[]
        failures=[0]
        def inspect(_root, _expected):
            assert _root == root
            assert set(_expected) == set(current)
            if corrupt_owner:
                raise RuntimeError('unverified Docker ownership')
            return copy.deepcopy(current)
        def fake_update(_root, container, metric, size):
            assert _root==root
            assert metric=='memory'
            k=next(x for x in expect if expect[x]['name']==container)
            size//=MIB
            old=current[k]['mem']
            updates.append((k,old,size))
            current[k]['mem']=size
            if fail_update and failures[0] == 0:
                failures[0] += 1
                raise RuntimeError('injected Docker update failure')
            if crash_mid_update:
                raise SystemExit('simulated process interruption after Docker update')
        def compose(_root, _expected):
            return {k: {'name':v['name'],'memory':v['mem']*MIB,'cpu':v['cpu']*1000000}
                    for k,v in expect.items()}
        err=None
        with (patch.object(mod,'load_expected',return_value=(expect,state)),
              patch.object(mod,'inspect_containers',side_effect=inspect),
              patch.object(mod,'_static_compose_limits',side_effect=compose),
              patch.object(mod,'_static_update_limit',side_effect=fake_update)):
            try:
                mod.reconcile_static_limits(root)
            except (RuntimeError, SystemExit) as ex:
                err=str(ex)
            if crash_mid_update and not missing_charge:
                assert err and 'simulated process' in err
                assert json.loads(store.read_text())['pending'] is not None
                # A normal next installer run must recover the pending journal.
                with patch.object(mod,'_static_update_limit',side_effect=lambda *a: None):
                    assert mod.reconcile_static_limits(root)==0
                err=None
            if err is None:
                assert mod.verify_snapshot(root)
                assert mod.reconcile_static_limits(root)==0
        return err, updates, copy.deepcopy(current), json.loads(store.read_text()), initial

err,updates,live,final,old=simulate()
assert err is None,err
assert updates==[('hermes',1072,1056)],updates
assert live['hermes']['mem']==1056
assert live['ollama']['mem']==5760  # Never lower a loaded model
assert live['honcho-db']['mem']==208
assert sum(x['mem'] for x in live.values())==10512
assert final['pending'] is None and final.get('rebindBudgetRecovery') is None
assert final['services']['honcho-db']['id']=='current-honcho-db'
assert final['services']['searxng']['id']=='current-searxng'
assert final['services']['synapse-db']['id']=='current-synapse-db'
assert final['services']['hermes']['mem']==1056
assert final['services']['ollama']['up']==old['services']['ollama']['up']
print('BUDGET REPAIR: exact +16MiB observed scenario PASS')

err,updates,live,final,old=simulate(missing_charge=True)
assert err and 'memory envelope' in err and not updates
assert final==old,err
print('BUDGET REPAIR: unavailable cgroup charge safely blocks donor PASS')

err,updates,live,final,old=simulate(corrupt_owner=True)
assert err and 'ownership' in err and not updates and final==old
print('BUDGET REPAIR: ownership gate PASS')

err,updates,live,final,old=simulate(extra_drift=True)
assert err and 'unchanged container has unexplained resource drift' in err and not updates and final==old
print('BUDGET REPAIR: independent drift gate PASS')

err,updates,live,final,old=simulate(fail_update=True)
assert err and 'injected Docker' in err and final['pending'] is None
assert live['hermes']['mem']==1072  # failed update simulated before succeeding, then rollback
print('BUDGET REPAIR: update failure rollback PASS')

err,updates,live,final,old=simulate(crash_mid_update=True)
assert err is None and live['hermes']['mem']==1056
assert final['pending'] is None and final.get('rebindBudgetRecovery') is None
print('BUDGET REPAIR: durable journal / interruption recovery PASS')
print('V14.6.7 REPLACEMENT MEMORY ENVELOPE RECOVERY FIXTURES: PASS')

# Nov 16 live WSL audit: +32 MiB and two newly canonical QMD containers.
# Previously the plan excluded EVERY replacement from donation even when it
# could safely return only its own restored 16-MiB allocation. That stranded
# two genuinely safe 16-MiB donors and made the installer leave the relay down.
AUDIT_32 = {
    'hermes': (1072,1072,1072,960,1024),
    'honcho-api': (400,432,432,386,384),
    'honcho-db': (208,192,192,97,192),
    'honcho-deriver': (272,288,288,255,256),
    'honcho-redis': (80,80,80,57,64),
    'ollama': (5728,5728,5728,4975,5632),
    'qmd': (1040,1024,1040,161,1024),
    'qmd-indexer': (1040,1024,1040,4,1024),
    'searxng': (208,208,208,142,192),
    'searxng-valkey': (80,80,80,28,64),
    'synapse': (208,208,208,191,192),
    'synapse-db': (176,176,176,110,160),
}
assert sum(v[1] for v in AUDIT_32.values()) == 10512
assert sum(v[2] for v in AUDIT_32.values()) == 10544


def recover_audit_32(*, unavailable_indexer=False, fail_second=False, interrupted=False):
    with tempfile.TemporaryDirectory(prefix='lv-nov16-recurrence-') as tmp:
        root = Path(tmp)
        store = root/'data/latticevale/resource-burst-state.json'
        store.parent.mkdir(parents=True)
        expected = {k:{'name':mod.PAIRS[k], 'mem':v[0], 'cpu':150, 'floor':v[4]}
                    for k,v in AUDIT_32.items()}
        state = {'POLICY_FINGERPRINT':'nov16-2026', 'BUDGET_MIB':'10512',
                 'CPU_DOCKER_ENVELOPE_MILLI':'3600', 'DIRECTML_SELECTED':'false'}
        live = {k:{'id':'new-'+k, 'mem':v[2], 'cpu':150,
                   'memory_current_mib':v[3]} for k,v in AUDIT_32.items()}
        original = {k:{**live[k], 'mem':v[1],
                       'id':('old-'+k if k in ('hermes','qmd','qmd-indexer','searxng') else 'new-'+k),
                       'up':3, 'idle':2} for k,v in AUDIT_32.items()}
        if unavailable_indexer:
            live['qmd-indexer'].pop('memory_current_mib')
        record = {'policyFingerprint':state['POLICY_FINGERPRINT'],
                  'services':copy.deepcopy(original), 'pending':None}
        store.write_text(json.dumps(record))
        updates=[]
        failures=[0]
        def inspect(_root,_expected):
            assert _root==root
            return copy.deepcopy(live)
        def desired(_root,_expected):
            return {k:{'name':v['name'],'memory':v['mem']*MIB,
                       'cpu':v['cpu']*1000000} for k,v in expected.items()}
        def update(_root,container,metric,value):
            assert metric=='memory'
            name=next(k for k in expected if expected[k]['name']==container)
            updates.append((name,live[name]['mem'],value//MIB))
            live[name]['mem']=value//MIB
            if fail_second and name=='qmd-indexer' and failures[0] == 0:
                failures[0] += 1
                raise RuntimeError('injected update failure')
            if interrupted and name=='qmd':
                raise SystemExit('injected interruption')
        error=None
        with (patch.object(mod,'load_expected',return_value=(expected,state)),
              patch.object(mod,'inspect_containers',side_effect=inspect),
              patch.object(mod,'_static_compose_limits',side_effect=desired),
              patch.object(mod,'_static_update_limit',side_effect=update)):
            try:
                mod.reconcile_static_limits(root)
            except (RuntimeError,SystemExit) as exc:
                error=str(exc)
            if interrupted:
                assert 'interruption' in error
                assert json.loads(store.read_text())['pending'] is not None
                # After interruption a second run completes the durable journal.
                with patch.object(mod,'_static_update_limit',side_effect=lambda _r,c,m,v: live[next(k for k in expected if expected[k]['name']==c)].update(mem=v//MIB)):
                    assert mod.reconcile_static_limits(root)==0
                error=None
            if error is None:
                assert mod.verify_snapshot(root)
        return error,updates,live,json.loads(store.read_text()),record

err,updates,live,final,original=recover_audit_32()
assert err is None,err
assert updates==[('qmd',1040,1024),('qmd-indexer',1040,1024)],updates
assert sum(item['mem'] for item in live.values())==10512
assert live['ollama']['mem']==5728
assert final['services']['qmd']['id']=='new-qmd'
assert final['services']['qmd-indexer']['id']=='new-qmd-indexer'
assert final['pending'] is None and final.get('rebindBudgetRecovery') is None
print('NOV16 +32MiB two-replaced-donor non-disruptive recovery: PASS')

err,updates,live,final,original=recover_audit_32(unavailable_indexer=True)
assert err and 'memory envelope' in err and not updates
assert final==original
print('NOV16 missing donor telemetry fails closed: PASS')

err,updates,live,final,original=recover_audit_32(fail_second=True)
assert err and 'injected update failure' in err
assert live['qmd']['mem']==1040 and live['qmd-indexer']['mem']==1040
assert final==original
print('NOV16 replacement-donor rollback restores old IDs/leases: PASS')

err,updates,live,final,original=recover_audit_32(interrupted=True)
assert err is None and live['qmd']['mem']==1024 and live['qmd-indexer']['mem']==1024
assert final['pending'] is None and final.get('rebindBudgetRecovery') is None
print('NOV16 replaced-donor interruption resume: PASS')

# Nov 16 post-memory-hotfix Option 1 reproduced a SECOND failure. The +32 MiB
# was recoverable, but a QMD Indexer replacement had also reinstated 50m of
# previously donated CPU. Ollama retained its verified 1400m burst (1350m
# canonical). The restored 50m made the live 3650m total exceed the 3600m
# envelope; the former controller rejected it before executing the RAM plan.
# Validate CPU-only, combined CPU+RAM, rollback, crash-resume and no-adoption.
AUDIT_CPU = {
    'hermes': (1072,1072,1024),
    'honcho-api': (400,432,384),
    'honcho-db': (208,192,192),
    'honcho-deriver': (272,288,256),
    'honcho-redis': (80,80,64),
    'ollama': (5728,5728,5632),
    'qmd': (1040,1024,1024),
    'qmd-indexer': (1040,1024,1024),
    'searxng': (208,208,192),
    'searxng-valkey': (80,80,64),
    'synapse': (208,208,192),
    'synapse-db': (176,176,160),
}
AUDIT_CPU_CANONICAL = {
    'hermes':850,'honcho-api':150,'honcho-db':150,'honcho-deriver':150,
    'honcho-redis':100,'ollama':1350,'qmd':150,'qmd-indexer':150,
    'searxng':150,'searxng-valkey':100,'synapse':150,'synapse-db':150,
}
assert sum(AUDIT_CPU_CANONICAL.values())==3600


def cpu_recurrence(*, memory_excess=True, fail_cpu=False, crash_cpu=False,
                   external_cpu_drift=False, corrupt_owner=False):
    with tempfile.TemporaryDirectory(prefix='lv-cpu-nov16-') as tmp:
        root=Path(tmp)
        store=root/'data/latticevale/resource-burst-state.json'
        store.parent.mkdir(parents=True)
        expect={k:{'name':module.PAIRS[k],'mem':v[0],
                   'cpu':AUDIT_CPU_CANONICAL[k], 'floor':v[2]}
                for k,v in AUDIT_CPU.items()}
        st={'POLICY_FINGERPRINT':'live-2026-11-16','BUDGET_MIB':'10512',
            'CPU_DOCKER_ENVELOPE_MILLI':'3600','DIRECTML_SELECTED':'false'}
        live={k:{'id':'current-'+k,'mem':v[1],
                 'cpu':AUDIT_CPU_CANONICAL[k],
                 'memory_current_mib':4 if k=='qmd-indexer' else
                   161 if k=='qmd' else 4975 if k=='ollama' else 100}
              for k,v in AUDIT_CPU.items()}
        # Other unchanged managed services retain the already verified leases.
        live['ollama']['cpu']=1400
        live['qmd-indexer']['cpu']=150
        if memory_excess:
            live['qmd']['mem']=1040
            live['qmd-indexer']['mem']=1040
        else:
            # Two canonical replacements, but a different unchanged lease has
            # already returned the 32 MiB, leaving only a CPU overage.
            live['qmd']['mem']=1040
            live['qmd-indexer']['mem']=1040
            live['honcho-api']['mem']=400
        saved=deepcopy(live)
        saved['qmd']['id']='previous-qmd'
        saved['qmd-indexer']['id']='previous-qmd-indexer'
        saved['qmd-indexer']['cpu']=100
        if memory_excess:
            saved['qmd']['mem']=1024
            saved['qmd-indexer']['mem']=1024
        if external_cpu_drift:
            live['ollama']['cpu']+=50  # Unchanged ID; NOT an innocent replacement.
        if corrupt_owner:
            saved['qmd-indexer']['id']=''  # Not a legitimate previous identity.
        assert sum(x['cpu'] for x in saved.values())==3600
        assert sum(x['cpu'] for x in live.values())==3650+(50 if external_cpu_drift else 0)
        if memory_excess:
            assert sum(x['mem'] for x in live.values())==10544
        record={'policyFingerprint':st['POLICY_FINGERPRINT'],
                'services':deepcopy(saved), 'pending':None,'lastSample':35}
        store.write_text(json.dumps(record))
        current=deepcopy(live)
        changes=[]
        tripped=[False]
        def inspect(_root,_expect):
            assert _root==root
            if corrupt_owner:
                raise RuntimeError('unverified Docker ownership')
            return deepcopy(current)
        def compose(_root,_expect):
            return {k:{'name':v['name'], 'memory':v['mem']*module.MIB,
                       'cpu':v['cpu']*1000000} for k,v in expect.items()}
        def update(_root,container,metric,value):
            k=next(k for k in expect if expect[k]['name']==container)
            m='mem' if metric=='memory' else 'cpu'
            val=value//(module.MIB if m=='mem' else 1000000)
            changes.append((k,m,current[k][m],val))
            current[k][m]=val
            if m=='cpu' and fail_cpu and not tripped[0]:
                tripped[0]=True
                raise RuntimeError('simulated CPU Docker update failure after apply')
            if m=='cpu' and crash_cpu and not tripped[0]:
                tripped[0]=True
                raise SystemExit('simulated interruption after CPU update')
        error=None
        with (patch.object(module,'load_expected',return_value=(expect,st)),
              patch.object(module,'inspect_containers',side_effect=inspect),
              patch.object(module,'_static_compose_limits',side_effect=compose),
              patch.object(module,'_static_update_limit',side_effect=update)):
            try:
                module.reconcile_static_limits(root)
            except (RuntimeError,SystemExit) as exc:
                error=str(exc)
            if crash_cpu and not external_cpu_drift:
                assert error and 'interruption' in error
                assert json.loads(store.read_text())['pending'] is not None
                assert module.reconcile_static_limits(root)==0
                error=None
            if error is None:
                assert module.verify_snapshot(root)
                assert module.reconcile_static_limits(root)==0
        return error,changes,current,json.loads(store.read_text()),record

err,ops,cur,final,original=cpu_recurrence()
assert err is None,err
assert ops==[('qmd','mem',1040,1024),('qmd-indexer','mem',1040,1024),
             ('qmd-indexer','cpu',150,100)],ops
assert sum(c['mem'] for c in cur.values())==10512
assert sum(c['cpu'] for c in cur.values())==3600
assert cur['ollama']['cpu']==1400 and cur['ollama']['mem']==5728
assert final['pending'] is None and final.get('rebindBudgetRecovery') is None
print('NOV16 COMBINED +32 MiB/+50m CPU replaced QMD recovery: PASS')

err,ops,cur,final,original=cpu_recurrence(memory_excess=False)
assert err is None and ops==[('qmd-indexer','cpu',150,100)],(err,ops)
print('NOV16 +50m CPU-only replacement recovery: PASS')

err,ops,cur,final,original=cpu_recurrence(fail_cpu=True)
assert err and 'simulated CPU Docker update failure' in err
assert cur['qmd']['mem']==1040 and cur['qmd-indexer']['mem']==1040
assert cur['qmd-indexer']['cpu']==150 and final==original
print('NOV16 CPU failure after apply rolls back both CPU and memory: PASS')

err,ops,cur,final,original=cpu_recurrence(crash_cpu=True)
assert err is None and cur['qmd-indexer']['cpu']==100
assert final['pending'] is None and final.get('rebindBudgetRecovery') is None
print('NOV16 interrupted combined CPU/RAM journal resumes: PASS')

err,ops,cur,final,original=cpu_recurrence(external_cpu_drift=True)
assert err and 'unexplained resource drift' in err and not ops and final==original
print('NOV16 independent unchanged-container CPU drift rejected: PASS')

err,ops,cur,final,original=cpu_recurrence(corrupt_owner=True)
assert err and 'ownership' in err and not ops and final==original
print('NOV16 unverified owner rejected: PASS')

# Preserve the previously permitted DirectML idle CPU loan, but only while
# its independently verified telemetry is fresh; never use a stale reserve.
now=time.time()
directml_state={'CPU_DOCKER_ENVELOPE_MILLI':'2800',
                'DIRECTML_SELECTED':'true','CPU_DIRECTML_RESERVE_MILLI':'900',
                'CPUS':'4'}
assert module._replacement_cpu_envelope(directml_state,
    {'lastSample':now,'directmlCpuTelemetry':{'busy':False}})==3100
assert module._replacement_cpu_envelope(directml_state,
    {'lastSample':now-180,'directmlCpuTelemetry':{'busy':False}})==2800
assert module._replacement_cpu_envelope(directml_state,
    {'lastSample':now,'directmlCpuTelemetry':{'busy':True}})==2800
print('VERIFIED DIRECTML IDLE CPU RESERVE COMPATIBILITY: PASS')

# v14.6.9 consolidation: CPU CFS quota pressure must not be suppressed by
# unrelated memory/IO PSI; actual OOM still blocks new lending.
load_usage = {k: dict(v) for k, v in usage.items()}
load_usage['hermes']['throttled'] = True
under_ram_psi, _ = decide(work=load_usage, mpsi=5, iopsi=15)
assert under_ram_psi['hermes']['cpu'] > base['hermes']['cpu']
assert sum(v['cpu'] for v in under_ram_psi.values()) <= 4200
assert sum(v['mem'] for v in under_ram_psi.values()) <= 5120
no_lending_after_oom, _ = decide(work=load_usage, mpsi=5, fresh=True)
assert no_lending_after_oom['hermes']['cpu'] == base['hermes']['cpu']
# Fresh memory.max is not an idle donor signal even when Docker stats is low.
limit_hit_usage = {k: dict(v) for k, v in usage.items()}
limit_hit_usage['qmd-indexer']['memory_limit_hit'] = True
limit_hit_goal, limit_hit_count = decide(work=limit_hit_usage)
assert limit_hit_count['qmd-indexer']['idle'] == 0
assert limit_hit_goal['qmd-indexer']['mem'] >= base['qmd-indexer']['mem']
print('v14.6.9 memory.max and PSI-independent bounded CPU borrowing: PASS')

# v14.6.9 follow-up: detected-core-scaled independent CPU ceilings.
# Container quota caps CPU time for the entire service, not per-thread affinity.
for visible in (1, 2, 4, 8, 16):
    for service, fraction in (('hermes', .45), ('ollama', .60),
                              ('honcho-api', .30), ('qmd-indexer', .30)):
        baseline = 50
        ceiling = module.cpu_service_ceiling(service, baseline, visible)
        assert ceiling % 50 == 0
        assert 50 <= ceiling <= visible * 900
        assert ceiling <= max(50, int(visible * 1000 * fraction // 50) * 50)
assert module.cpu_service_ceiling('hermes', 900, 2) == 900
assert module.cpu_service_ceiling('ollama', 1350, 4) == 2400
assert module.cpu_service_ceiling('hermes', 900, 4) == 1800

# Legacy v14 leases above the new cap converge before any fresh borrowing.
bounded_roles = {
    'hermes': {'cpu': 900, 'mem': 1800, 'floor': 1024},
    'ollama': {'cpu': 1350, 'mem': 6200, 'floor': 5632},
    'qmd': {'cpu': 150, 'mem': 1040, 'floor': 1024},
}
bounded_live = {
    'hermes': {'cpu': 900, 'mem': 1800},
    'ollama': {'cpu': 2550, 'mem': 6200},
    'qmd': {'cpu': 150, 'mem': 1040},
}
bounded_usage = {k: {'cpu_pct': 0.0, 'mem': 50, 'charged_mem': 50,
                     'throttled': False} for k in bounded_roles}
bounded_record = {'lastUpdate': 500, 'services': {
    k: {'up': 0, 'idle': 0} for k in bounded_roles}}
bounded_goal, _ = module.plan(
    bounded_roles, bounded_live, bounded_usage, bounded_record,
    available_mib=4096, memory_psi=0.1, cpu_psi=0.1,
    cpu_load1=0.3, io_psi=0.1, cpus=4, cpu_envelope=3600,
    budget=10512, now=510)
assert bounded_goal['hermes']['cpu'] == 900
assert bounded_goal['ollama']['cpu'] == 2400
assert bounded_goal['qmd']['cpu'] == 150
assert all(bounded_goal[k]['cpu'] >= bounded_roles[k]['cpu'] for k in bounded_roles)
assert all(bounded_goal[k]['mem'] == bounded_live[k]['mem'] for k in bounded_roles)
print('v14.6.9 detected-core CPU service ceiling + legacy lease convergence: PASS')

# v14.6.9 follow-up: detected WSL RAM bounds individual Docker containers.
# These are optional burst ceilings, never reductions of model-aware baselines.
for wsl_mem in (4096, 8192, 11680, 32768):
    budget_mib = int(wsl_mem * .9)
    for role, fraction in (('ollama', .55), ('hermes', .15),
                           ('qmd', .12), ('honcho-api', .12)):
        ceiling = module.memory_service_ceiling(role, 256, wsl_mem, budget_mib)
        assert 256 <= ceiling <= budget_mib
        assert ceiling <= max(256, int(wsl_mem * fraction / 16) * 16)
assert module.memory_service_ceiling('ollama', 5632, 11680, 10512) >= 5632
assert module.memory_service_ceiling('ollama', 8000, 11680, 10512) == 8000

ram_roles = {'ollama': {'cpu': 1350, 'mem': 5632, 'floor': 5632},
             'hermes': {'cpu': 900, 'mem': 1040, 'floor': 1024},
             'qmd': {'cpu': 150, 'mem': 1040, 'floor': 1024}}
ram_live = {'ollama': {'cpu': 1350, 'mem': 7000},
            'hermes': {'cpu': 900, 'mem': 2000},
            'qmd': {'cpu': 150, 'mem': 1040}}
ram_usage = {k: {'cpu_pct': 0, 'mem': 100, 'charged_mem': 100,
                 'throttled': False} for k in ram_roles}
ram_record = {'lastUpdate': 500, 'services': {k: {'up': 0, 'idle': 0}
                                            for k in ram_roles}}
ram_goal, _ = module.plan(ram_roles, ram_live, ram_usage, ram_record,
                          available_mib=4000, memory_psi=.1, cpu_psi=.1,
                          cpu_load1=.2, io_psi=.1, cpus=4, cpu_envelope=3600,
                          budget=10512, host_memory_mib=11680, now=510)
assert ram_goal['ollama']['mem'] == module.memory_service_ceiling('ollama', 5632, 11680, 10512)
assert ram_goal['hermes']['mem'] == module.memory_service_ceiling('hermes', 1040, 11680, 10512)
assert ram_goal['qmd']['mem'] == 1040
# Don't shrink a cgroup near its hard ceiling or with a fresh limit event.
ram_loaded = {k: dict(v) for k, v in ram_usage.items()}
ram_loaded['ollama']['charged_mem'] = 6500
ram_loaded['ollama']['memory_limit_hit'] = True
loaded_goal, _ = module.plan(ram_roles, ram_live, ram_loaded, ram_record,
                              available_mib=4000, memory_psi=.1, cpu_psi=.1,
                              cpu_load1=.2, io_psi=.1, cpus=4, cpu_envelope=3600,
                              budget=10512, host_memory_mib=11680, now=510)
assert loaded_goal['ollama']['mem'] == 7000
print('v14.6.9 WSL-RAM-scaled per-container ceilings + safe legacy lease recovery: PASS')
