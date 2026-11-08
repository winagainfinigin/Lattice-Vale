#!/usr/bin/env python3
"""LatticeVale policy-v14 burst controller (canonical v13 state compatible).

Runs as the stack's unprivileged Docker user from a systemd timer. It may only
rebalance the existing aggregate CPU and memory envelopes of LatticeVale-owned
containers. Any uncertain state or user Compose override falls back to static
Compose quotas; existing services are never restarted by this controller.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
from latticevale_arch import SERVICE_ORDER, parse_env_state

MIB = 1024**2
PAIRS = {
    'hermes': 'hermes-agent', 'synapse-db': 'hermes-synapse-db',
    'synapse': 'hermes-synapse', 'searxng-valkey': 'hermes-searxng-valkey',
    'searxng': 'hermes-searxng', 'qmd': 'hermes-qmd',
    'qmd-indexer': 'hermes-qmd-indexer', 'ollama': 'hermes-ollama',
    'honcho-db': 'hermes-honcho-db', 'honcho-redis': 'hermes-honcho-redis',
    'honcho-api': 'hermes-honcho-api', 'honcho-deriver': 'hermes-honcho-deriver',
}
# Priority-sensitive donor floors: background capacity is available for real
# bottlenecks, while interactive services retain larger burst margins.
# These ratios scale with canonical service quotas, not any PC/WSL hardware SKU.
CPU_DONOR_FLOOR_BACKGROUND = 0.65
CPU_DONOR_FLOOR_STANDARD = 0.80
CPU_DONOR_FLOOR_INTERACTIVE = 0.90
MEM_DONOR_FLOOR_BACKGROUND = 0.85
MEM_DONOR_FLOOR_INTERACTIVE = 0.90
CPU_QUANTUM_MILLI = 50
MEM_QUANTUM_MIB = 16

PRIORITY = {
    'hermes': 11, 'synapse': 8, 'synapse-db': 7,
    'honcho-api': 7, 'honcho-db': 6, 'qmd': 6, 'ollama': 10,
    'searxng': 4, 'searxng-valkey': 3, 'honcho-redis': 4,
    'qmd-indexer': 3, 'honcho-deriver': 3,
}


def cpu_donor_floor(service, baseline):
    """Keep enough quota for a fast wake-up without hard-coding host sizes."""
    priority = PRIORITY[service]
    ratio = (CPU_DONOR_FLOOR_BACKGROUND if priority <= 4 else
             CPU_DONOR_FLOOR_INTERACTIVE if priority >= 8 else
             CPU_DONOR_FLOOR_STANDARD)
    return max(CPU_QUANTUM_MILLI,
               math.ceil(baseline * ratio / CPU_QUANTUM_MILLI) * CPU_QUANTUM_MILLI)


def memory_donor_floor(service, baseline, configured_floor, charged_mib):
    """Preserve cgroup-charged pages, hard model floors, and burst headroom."""
    if charged_mib is None:
        return baseline  # Missing cgroup telemetry must never shrink a hard limit.
    ratio = (MEM_DONOR_FLOOR_BACKGROUND if PRIORITY[service] <= 4
             else MEM_DONOR_FLOOR_INTERACTIVE)
    return max(configured_floor, math.ceil(baseline * ratio),
               math.ceil(charged_mib * 1.20) + 64)


def run(args, cwd, timeout=12):
    env = os.environ.copy()
    for key in ('DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_TLS',
                'DOCKER_CERT_PATH', 'DOCKER_API_VERSION'):
        env.pop(key, None)
    env['DOCKER_HOST'] = 'unix:///var/run/docker.sock'
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if r.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed: {r.stderr.strip()[:220]}")
    return r.stdout


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def pressure(path, kind='some'):
    try:
        line = next(x for x in Path(path).read_text().splitlines() if x.startswith(kind + ' '))
        return float(re.search(r'\bavg10=([0-9.]+)', line).group(1))
    except (OSError, ValueError, AttributeError, StopIteration):
        return None


def sustained_quota_throttle(periods, throttled, old_periods, old_throttled):
    """Detect recent sustained CFS throttling, excluding sporadic wake-ups."""
    if any(v is None for v in (periods, throttled, old_periods, old_throttled)):
        return False
    try:
        delta_periods = int(periods) - int(old_periods)
        delta_throttled = int(throttled) - int(old_throttled)
    except (TypeError, ValueError):
        return False
    return (delta_periods >= 20 and 4 <= delta_throttled <= delta_periods and
            delta_throttled / delta_periods >= .12)


def host_cpu_load1():
    """1-minute Linux runqueue load; combine with CPU PSI to avoid quota false alarms.

    A cgroup hard quota can produce ~90% CPU PSI even if the 4-vCPU WSL host
    has a load average far below one. Borrowing idle *quota* helps that case.
    A missing or invalid load measurement remains a conservative guard.
    """
    try:
        load = float(os.getloadavg()[0])
        return load if math.isfinite(load) and load >= 0 else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def override_eligible(root):
    """Use exactly the same full Compose-model check at bootstrap and runtime."""
    return not (root / 'compose.override.yaml').exists() or image_only_compose_override(root)


def host_available_mib():
    try:
        text = Path('/proc/meminfo').read_text()
        return int(re.search(r'^MemAvailable:\s*(\d+)\s*kB', text, re.M).group(1)) // 1024
    except (OSError, AttributeError):
        return None


def directml_sample():
    """Read host DirectML process CPU time, keeping its reserve if unreadable."""
    result = {}
    try:
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                cmdline = (proc / 'cmdline').read_bytes().replace(b'\0', b' ')
            except (OSError, PermissionError):
                continue
            if b'directml-gateway.py' not in cmdline or b'resource-burst-controller' in cmdline:
                continue
            try:
                # /proc/<pid>/stat fields 14-15, after the variable-width (comm).
                fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
                result[proc.name] = int(fields[11]) + int(fields[12])
            except (OSError, ValueError, IndexError, PermissionError):
                return None
    except (OSError, PermissionError):
        return None
    return result


def directml_workload(snapshot, now):
    """Return busy/unknown status and update consecutive idle samples.

    Two low-CPU samples are required before lending any host CPU reserve;
    a new process or new activity immediately reclaims the borrowed fraction.
    """
    running = directml_sample()
    previous = snapshot.get('directmlCpuTelemetry', {})
    if running is None:
        snapshot['directmlCpuTelemetry'] = {'busy': True, 'idle': 0}
        return True
    if not running:
        snapshot['directmlCpuTelemetry'] = {'busy': False, 'idle': 2}
        return False
    old = previous.get('ticks', {})
    elapsed = now - previous.get('time', now)
    stable = set(old) == set(running) and 5 <= elapsed <= 240
    if stable:
        rate = sum(max(0, running[p] - old[p]) for p in running) / (
            elapsed * max(1, os.sysconf('SC_CLK_TCK')))
        idle = min(5, int(previous.get('idle', 0)) + 1) if rate < 0.05 else 0
    else:
        idle = 0
    snapshot['directmlCpuTelemetry'] = {
        'ticks': running, 'time': now, 'idle': idle, 'busy': idle < 2,
    }
    return idle < 2


def mem_from_stats(value):
    text = str(value).split('/')[0].strip().replace(',', '')
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*([kmgti]?i?b)', text, re.I)
    if not match:
        raise ValueError(f'cannot read Docker memory usage {value!r}')
    amount, unit = float(match.group(1)), match.group(2).lower()
    scale = {'b': 1, 'kb': 1000, 'mb': 1000**2, 'gb': 1000**3,
             'tb': 1000**4, 'kib': 1024, 'mib': MIB, 'gib': 1024**3,
             'tib': 1024**4}.get(unit)
    if scale is None:
        raise ValueError(f'invalid Docker stats unit {unit}')
    return math.ceil(amount * scale / MIB)


def image_only_compose_override(root):
    """Admit only a verified image-only Hermes override, preserving opaque overrides.

    Docker Compose resolves interpolation and merge semantics; comparing the
    entire effective models avoids attempting to parse user YAML ourselves.
    Any other effective mutation, Compose error, or unsupported tool falls back
    to static allocations. Neither model is written to disk or logged.
    """
    files = ['compose.yaml']
    if (root / 'compose.latticevale.yaml').is_file() and (root / 'compose.latticevale.yaml').stat().st_size:
        files.append('compose.latticevale.yaml')
    if not (root / 'compose.override.yaml').is_file():
        return False

    def resolved_model(paths):
        cmd = ['docker', 'compose']
        for path in paths:
            cmd.extend(['-f', path])
        cmd.extend(['config', '--format', 'json'])
        model = json.loads(run(cmd, root, timeout=25))
        if not isinstance(model, dict) or not isinstance(model.get('services'), dict):
            raise RuntimeError('Compose effective model is malformed')
        return model

    plain = resolved_model(files)
    custom = resolved_model(files + ['compose.override.yaml'])
    plain_hermes = plain['services'].get('hermes')
    custom_hermes = custom['services'].get('hermes')
    if not isinstance(plain_hermes, dict) or not isinstance(custom_hermes, dict):
        return False
    if not isinstance(custom_hermes.get('image'), str) or not custom_hermes['image'].strip():
        return False
    # Only Hermes's image/pull selection may differ; all other settings and
    # every other service, volume, network, resource value, and profile must
    # remain exactly as LatticeVale generates them.
    for model in (plain, custom):
        hermes = model['services']['hermes']
        hermes.pop('image', None)
        hermes.pop('pull_policy', None)
    return plain == custom


def load_expected(root, *, allow_override=False):
    opts = read_json(root / 'install-options.json', {})
    state = parse_env_state(root / '.latticevale-resource-state')
    policy = read_json(root / 'data/latticevale/runtime-policy.json', {})
    if not isinstance(opts, dict) or opts.get('containerResourceLimits') is not True:
        raise RuntimeError('resource limits disabled; static policy remains authoritative')
    if not state or policy.get('policyFingerprint') != state.get('POLICY_FINGERPRINT'):
        raise RuntimeError('resource-policy fingerprint mismatch; static fallback')
    if state.get('RESOURCE_BURST_STRATEGY') != 'bounded-v14':
        raise RuntimeError('burst policy not installed; static fallback')
    if (root / 'compose.override.yaml').exists() and not allow_override:
        if not image_only_compose_override(root):
            raise RuntimeError('unverified or resource-affecting Compose override; static fallback')
    names = [x for x in SERVICE_ORDER if f'LIMIT_{x.upper().replace("-", "_")}_MIB' in state]
    expected = {}
    for name in names:
        key = name.upper().replace('-', '_')
        expected[name] = {
            'name': PAIRS[name],
            'mem': int(state[f'LIMIT_{key}_MIB']),
            'cpu': int(state[f'CPU_{key}_MILLI']),
            'floor': int(state[f'FLOOR_{key}_MIB']),
        }
        if not (expected[name]['mem'] >= expected[name]['floor'] >= 1 and expected[name]['cpu'] >= 50):
            raise RuntimeError('invalid canonical service limits')
    if not expected or sum(v['mem'] for v in expected.values()) > int(state['BUDGET_MIB']):
        raise RuntimeError('canonical memory envelope exceeded')
    if sum(v['cpu'] for v in expected.values()) > int(state['CPU_DOCKER_ENVELOPE_MILLI']):
        raise RuntimeError('canonical CPU envelope exceeded')
    return expected, state



def cgroup_event_counters(pid):
    """Read Linux cgroup v2 counters for actual Docker throttling/new OOMs."""
    try:
        lines = Path(f'/proc/{pid}/cgroup').read_text().splitlines()
        rel = next(x.split('::', 1)[1] for x in lines if x.startswith('0::/'))
        group = (Path('/sys/fs/cgroup') / rel.lstrip('/')).resolve()
        if not group.is_relative_to(Path('/sys/fs/cgroup')):
            return {}
        output = {}
        for filename, fields in (('cpu.stat', ('nr_throttled', 'nr_periods')),
                                 ('memory.events', ('oom_kill',))):
            try:
                data = dict(line.split()[:2] for line in (group / filename).read_text().splitlines())
            except (OSError, ValueError):
                continue
            for field in fields:
                if field in data:
                    output[field] = int(data[field])
        try:
            charged = int((group / 'memory.current').read_text().strip())
            if charged >= 0:
                output['memory_current_mib'] = math.ceil(charged / MIB)
        except (OSError, ValueError, PermissionError):
            pass
        return output
    except (OSError, ValueError, StopIteration, PermissionError):
        return {}


def inspect_containers(root, expected):
    args = ['docker', 'inspect'] + [e['name'] for e in expected.values()]
    raw = json.loads(run(args, root, timeout=18))
    byname = {x.get('Name', '').lstrip('/'): x for x in raw}
    result = {}
    for service, e in expected.items():
        obj = byname.get(e['name'])
        if not isinstance(obj, dict) or obj.get('State', {}).get('Running') is not True:
            raise RuntimeError(f'{service} not running; static fallback')
        labels = obj.get('Config', {}).get('Labels') or {}
        if labels.get('com.docker.compose.project') != 'hermesstack' or labels.get('com.docker.compose.service') != service:
            raise RuntimeError(f'{service} ownership does not match the LatticeVale Compose stack')
        hc = obj['HostConfig']
        mem, nano = int(hc.get('Memory') or 0), int(hc.get('NanoCpus') or 0)
        if mem <= 0 or nano <= 0:
            raise RuntimeError(f'{service} has missing Docker resource ceilings')
        pid = int(obj.get('State', {}).get('Pid') or 0)
        counters = cgroup_event_counters(pid) if pid > 0 else {}
        result[service] = {'id': obj['Id'], 'mem': mem // MIB, 'cpu': nano // 10**6,
                           'oom': bool(obj['State'].get('OOMKilled', False)), **counters}
    return result


def read_usage(root, expected):
    raw = run(['docker', 'stats', '--no-stream', '--no-trunc', '--format', '{{json .}}'] +
              [v['name'] for v in expected.values()], root, timeout=28)
    data = {}
    for line in raw.splitlines():
        d = json.loads(line)
        n = str(d.get('Name', ''))
        p = str(d.get('CPUPerc', '')).strip().rstrip('%').replace(',', '')
        data[n] = {'mem': mem_from_stats(d.get('MemUsage', '')),
                   'cpu_pct': float(p)}
    if set(data) != {v['name'] for v in expected.values()}:
        raise RuntimeError('Docker stats omitted selected containers')
    return {k: data[v['name']] for k, v in expected.items()}


def safe_state(root, expected, state, actual):
    record = read_json(root / 'data/latticevale/resource-burst-state.json', {})
    if not isinstance(record, dict):
        record = {}
    matching = (record.get('policyFingerprint') == state['POLICY_FINGERPRINT'] and
                set(record.get('services', {})) == set(expected))
    if matching:
        for name, item in expected.items():
            saved = record['services'][name]
            if (saved.get('id') != actual[name]['id'] or
                saved.get('mem') != actual[name]['mem'] or saved.get('cpu') != actual[name]['cpu']):
                matching = False
                break
    if record.get('pending') and record.get('policyFingerprint') == state['POLICY_FINGERPRINT']:
        planned = record['pending']
        previous = record.get('services', {})
        if set(planned) != set(expected) or set(previous) != set(expected):
            raise RuntimeError('incomplete controller transaction has mismatched topology')
        for k in expected:
            if actual[k]['id'] != previous[k].get('id'):
                raise RuntimeError('container was replaced during controller transaction')
            for metric in ('mem', 'cpu'):
                if actual[k][metric] not in (previous[k].get(metric), planned[k].get(metric)):
                    raise RuntimeError('live limits changed independently during controller transaction')
        # Resume from a crash only by returning to canonical safe limits.
        # restore_pending is performed in run_once after this has been validated.
        record['_requires_restore'] = True
        return record
    if not matching:
        # Only a verified Compose baseline can initialize a new controller state.
        if any(actual[k]['mem'] != e['mem'] or actual[k]['cpu'] != e['cpu']
               for k, e in expected.items()):
            raise RuntimeError('live Docker limits differ from both verified baseline and controller snapshot')
        return {'policyFingerprint': state['POLICY_FINGERPRINT'], 'services': {
            k: {**actual[k], 'up': 0, 'idle': 0} for k in expected},
            'lastUpdate': 0, 'lastSample': 0}
    return record


def plan(expected, current, usage, record, *, available_mib, memory_psi, cpu_psi,
         cpu_load1=None, io_psi=None, fresh_oom=False,
         directml_selected=False, directml_active=True, cpus=1, cpu_envelope=0,
         directml_reserve=0, budget=0, now=None):
    """Pure, reproducible planner; never raises per-service cap outside group budget."""
    now = time.time() if now is None else now
    old = {k: {'mem': current[k]['mem'], 'cpu': current[k]['cpu']} for k in expected}
    goal = {k: v.copy() for k, v in old.items()}
    counters = {}
    # WSL-wide CPU PSI includes time that *cgroup-quota-throttled* tasks
    # cannot run. A high PSI number alone therefore does not prove physical
    # cores are exhausted (observed: 88% PSI with load1=0.31 on 4 vCPUs).
    # Hard per-container quotas can create high CPU PSI on an otherwise idle
    # WSL host. The CPU quota transfers stay strictly within the configured
    # aggregate Docker envelope, so CPU PSI alone must not suppress them.
    # Corroborating high runqueue load does, however, disable any additional
    # lending from a separately reserved DirectML slice.
    cpu_host_busy = (cpu_psi >= 25.0 and
                     (cpu_load1 is None or not math.isfinite(cpu_load1) or
                      cpu_load1 >= cpus * 0.85)) if cpu_psi is not None else True
    high_pressure = (available_mib is None or memory_psi is None or cpu_psi is None or
                     memory_psi >= 2.0 or
                     (io_psi is not None and io_psi >= 12.0) or
                     available_mib < max(512, int(budget * 0.10)))
    for k in expected:
        cap_m, cap_c, u = current[k]['mem'], current[k]['cpu'], usage[k]
        saturated = (u['mem'] >= max(1, int(cap_m * 0.82)) or
                     u['cpu_pct'] >= (cap_c / 10) * 0.82 or u.get('throttled', False))
        idle = (u['mem'] < cap_m * 0.50 and u['cpu_pct'] < (cap_c / 10) * 0.35)
        prev = record['services'][k]
        counters[k] = {
            'up': min(5, int(prev.get('up', 0)) + 1) if saturated else 0,
            'idle': min(5, int(prev.get('idle', 0)) + 1) if idle else 0,
        }
    # Reserve against sudden host/DirectML pressure. On a verified inactive
    # DirectML worker, temporarily lend at most a third of its CPU reservation.
    extra = (min(int(directml_reserve / 3), int(cpus * 100))
             if directml_selected and not directml_active and
             not high_pressure and not cpu_host_busy else 0)
    usable_cpu = cpu_envelope + extra
    if usable_cpu > cpus * 1000 - max(50, int(cpus * 100)):
        usable_cpu = cpus * 1000 - max(50, int(cpus * 100))
    def ensure_cpu_envelope():
        # An inactive DirectML worker can become active between timer ticks.
        # Return the borrowed portion of its reservation immediately instead
        # of allowing prior burst leases to continue after the next sample.
        excess = sum(x['cpu'] for x in goal.values()) - usable_cpu
        if excess <= 0:
            return
        for k in sorted(expected, key=lambda n: (PRIORITY[n], n)):
            if excess <= 0:
                break
            reducible = max(0, goal[k]['cpu'] - 50)
            give = min(reducible, ((excess + 49) // 50) * 50)
            goal[k]['cpu'] -= give
            excess -= give
        if excess > 0:
            raise RuntimeError('insufficient CPU safety capacity')

    # CPU donations are preemptible: restore an awakened donor's canonical
    # allocation before expanding other services. This also bypasses the
    # ordinary cooldown so a previously idle interactive worker can wake up.
    for awakened in sorted(expected, key=lambda k: (-PRIORITY[k], k)):
        missing = expected[awakened]['cpu'] - goal[awakened]['cpu']
        if missing <= 0 or not (usage[awakened]['cpu_pct'] >= current[awakened]['cpu'] * .06 or
                                usage[awakened].get('throttled', False)):
            continue
        spare = max(0, usable_cpu - sum(x['cpu'] for x in goal.values()))
        for borrowed in sorted(expected, key=lambda k: (PRIORITY[k], k)):
            if spare >= missing:
                break
            take = min(missing - spare, max(0, goal[borrowed]['cpu'] - expected[borrowed]['cpu']))
            goal[borrowed]['cpu'] -= take
            spare += take
        goal[awakened]['cpu'] += min(missing, spare)

    # Memory leases are harder to preempt: reclaim only unused headroom and
    # never lower a working-set hard limit during an active allocation.
    for awakened in sorted(expected, key=lambda k: (-PRIORITY[k], k)):
        missing = expected[awakened]['mem'] - goal[awakened]['mem']
        if missing <= 0 or usage[awakened]['mem'] < current[awakened]['mem'] * .70:
            continue
        spare = max(0, budget - sum(x['mem'] for x in goal.values()))
        for borrowed in sorted(expected, key=lambda k: (PRIORITY[k], k)):
            if spare >= missing:
                break
            charged = usage[borrowed].get('charged_mem')
            if charged is None:
                continue
            remain = max(expected[borrowed]['mem'],
                         math.ceil(charged * 1.20) + 64)
            take = min(missing - spare, max(0, goal[borrowed]['mem'] - remain))
            take = (take // 16) * 16
            goal[borrowed]['mem'] -= take
            spare += take
        goal[awakened]['mem'] += min(missing, spare)

    if high_pressure or fresh_oom:
        # When memory pressure or prior OOM is indicated, give resources back to
        # the canonical safe profile gradually, leaving busy memory untouched.
        for k, e in expected.items():
            charged = usage[k].get('charged_mem')
            candidate = max(e['mem'], current[k]['mem'] - 64)
            if (current[k]['mem'] > e['mem'] and charged is not None and
                    candidate >= math.ceil(charged * 1.20) + 64 and
                    usage[k]['mem'] < e['mem'] * .8):
                goal[k]['mem'] = candidate
            if current[k]['cpu'] > e['cpu']:
                goal[k]['cpu'] = max(e['cpu'], current[k]['cpu'] - 100)
        ensure_cpu_envelope()
        return goal, counters
    # A measured, fresh quota-throttling signal can bypass cooldown for CPU
    # only. Ordinary quota increases still require two demand samples.
    urgent_throttle = any(usage[k].get('throttled', False) for k in expected)
    in_cooldown = now - record.get('lastUpdate', 0) < 45
    if in_cooldown and not urgent_throttle:
        ensure_cpu_envelope()
        return goal, counters

    # Rebalance CPU from idle services to busy services while conserving the
    # aggregate Docker envelope. Never reduce the stable minimum for a service.
    cpu_receivers = [k for k in expected if
                     (counters[k]['up'] >= 2 or usage[k].get('throttled', False)) and
                     (usage[k]['cpu_pct'] >= (current[k]['cpu'] / 10) * .82 or
                      usage[k].get('throttled', False))]
    cpu_receivers.sort(key=lambda k: (-PRIORITY[k], -usage[k]['cpu_pct'], k))
    cpu_donors = [k for k in expected if counters[k]['idle'] >= 3 and k not in cpu_receivers]
    cpu_donors.sort(key=lambda k: (PRIORITY[k], k))
    available_cpu = max(0, usable_cpu - sum(x['cpu'] for x in goal.values()))
    if cpu_receivers:
        # Allocate only what recipients can accept. Previously every idle donor
        # was reduced even if no receiver had sufficient burst ceiling.
        for target in cpu_receivers:
            base, cur = expected[target]['cpu'], goal[target]['cpu']
            ceiling = min(int(cpus * 1000 * .75), max(base * 3, base + 500))
            requested = (min(400, max(0, ceiling - cur)) // CPU_QUANTUM_MILLI
                         ) * CPU_QUANTUM_MILLI
            for donor in cpu_donors:
                shortage = requested - available_cpu
                if shortage <= 0:
                    break
                donor_cur = goal[donor]['cpu']
                floor = cpu_donor_floor(donor, expected[donor]['cpu'])
                reclaim = (min(200, shortage, max(0, donor_cur - floor))
                           // CPU_QUANTUM_MILLI) * CPU_QUANTUM_MILLI
                goal[donor]['cpu'] -= reclaim
                available_cpu += reclaim
            added = min(requested, available_cpu)
            goal[target]['cpu'] += added
            available_cpu -= added
    else:
        # Return toward original weights once workloads quiet down.
        # Restore normal allocations when borrowing has ended. A service
        # reawakening from an earlier donation has priority over spare quotas.
        for k, e in expected.items():
            if counters[k]['idle'] >= 3 and goal[k]['cpu'] > e['cpu']:
                goal[k]['cpu'] = max(e['cpu'], goal[k]['cpu'] - 200)
        spare_cpu = max(0, usable_cpu - sum(x['cpu'] for x in goal.values()))
        for k in sorted(expected, key=lambda k: (-PRIORITY[k], k)):
            if goal[k]['cpu'] < expected[k]['cpu']:
                add = min(200, expected[k]['cpu'] - goal[k]['cpu'], spare_cpu)
                add = (add // 50) * 50
                goal[k]['cpu'] += add
                spare_cpu -= add

    if in_cooldown:
        ensure_cpu_envelope()
        assert sum(x['cpu'] for x in goal.values()) <= usable_cpu
        assert sum(x['mem'] for x in goal.values()) <= budget
        return goal, counters

    # Redistribute caps only by taking safely unused headroom from idle donors.
    # The sum of all hard limits stays <= the original container budget.
    memory_receivers = [k for k in expected if counters[k]['up'] >= 2 and
                        usage[k]['mem'] >= current[k]['mem'] * .82]
    memory_receivers.sort(key=lambda k: (-PRIORITY[k], -usage[k]['mem'], k))
    # The cgroup charge (memory.current), including file cache, is required
    # before reducing anyone's hard memory limit. Docker stats alone is not.
    memory_donors = [k for k in expected if counters[k]['idle'] >= 3 and
                     isinstance(usage[k].get('charged_mem'), (int, float)) and
                     usage[k]['charged_mem'] >= 0 and k not in memory_receivers]
    memory_donors.sort(key=lambda k: (PRIORITY[k], k))
    spare = max(0, budget - sum(x['mem'] for x in goal.values()))
    if memory_receivers:
        for target in memory_receivers:
            cur, base = goal[target]['mem'], expected[target]['mem']
            max_burst = min(budget, max(base + 256, int(base * 1.75)))
            requested = (min(128, max(0, max_burst - cur),
                             max(0, available_mib - 512)) // MEM_QUANTUM_MIB
                         ) * MEM_QUANTUM_MIB
            for donor in memory_donors:
                shortage = requested - spare
                if shortage <= 0:
                    break
                donor_cur = goal[donor]['mem']
                floor = memory_donor_floor(
                    donor, expected[donor]['mem'], expected[donor]['floor'],
                    usage[donor]['charged_mem'])
                reclaim = (min(128, shortage, max(0, donor_cur - floor))
                           // MEM_QUANTUM_MIB) * MEM_QUANTUM_MIB
                goal[donor]['mem'] -= reclaim
                spare += reclaim
            added = min(requested, spare)
            goal[target]['mem'] += added
            spare -= added
    else:
        for k, e in expected.items():
            charged = usage[k].get('charged_mem')
            candidate = max(e['mem'], goal[k]['mem'] - 64)
            if (counters[k]['idle'] >= 3 and goal[k]['mem'] > e['mem'] and
                    charged is not None and
                    candidate >= math.ceil(charged * 1.20) + 64 and
                    usage[k]['mem'] < e['mem'] * .8):
                goal[k]['mem'] = candidate
        spare_mib = max(0, budget - sum(x['mem'] for x in goal.values()))
        for k in sorted(expected, key=lambda k: (-PRIORITY[k], k)):
            if goal[k]['mem'] < expected[k]['mem']:
                add = min(64, expected[k]['mem'] - goal[k]['mem'], spare_mib)
                add = (add // 16) * 16
                goal[k]['mem'] += add
                spare_mib -= add

    ensure_cpu_envelope()
    assert sum(x['cpu'] for x in goal.values()) <= usable_cpu
    assert sum(x['mem'] for x in goal.values()) <= budget
    assert all(goal[k]['mem'] >= expected[k]['floor'] and goal[k]['cpu'] >= 50 for k in expected)
    return goal, counters


def perform(root, expected, before, target):
    # Decreases first, increases second: aggregate caps never transiently exceed
    # the conserved envelope. Save a rollback journal in the caller afterward.
    changes = []
    try:
        for metric in ('mem', 'cpu'):
            for direction in (-1, 1):
                for service in sorted(expected):
                    old, new = before[service][metric], target[service][metric]
                    if (new - old) * direction <= 0:
                        continue
                    arg = f'{new}m' if metric == 'mem' else f'{new / 1000:.3f}'
                    flag = '--memory' if metric == 'mem' else '--cpus'
                    run(['docker', 'update', flag, arg, expected[service]['name']], root, timeout=18)
                    changes.append((service, metric, old))
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        for service, metric, old in reversed(changes):
            arg = f'{old}m' if metric == 'mem' else f'{old / 1000:.3f}'
            try:
                run(['docker', 'update', '--memory' if metric == 'mem' else '--cpus', arg,
                     expected[service]['name']], root, timeout=18)
            except Exception:
                pass
        raise RuntimeError(f'borrow/rebalance failed; rollback attempted: {exc}') from exc
    return bool(changes)


def verify_snapshot(root):
    expected, state = load_expected(root)
    actual = inspect_containers(root, expected)
    snapshot = safe_state(root, expected, state, actual)
    if snapshot.get('pending') or snapshot.get('_requires_restore'):
        raise RuntimeError('controller transaction has not converged')
    return True


def run_once(root, restore=False):
    # A lock prevents timer/repair runs from racing the policy snapshot or Docker.
    lockpath = root / 'data/latticevale/resource-burst.lock'
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    with lockpath.open('a+') as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('burst controller already running; next scheduled check will retry')
            return 0
        expected, state = load_expected(root, allow_override=restore)
        actual = inspect_containers(root, expected)
        snapshot = safe_state(root, expected, state, actual)
        if snapshot.pop('_requires_restore', False):
            safe_baseline = {k: {'mem': expected[k]['mem'], 'cpu': expected[k]['cpu']} for k in expected}
            write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
            perform(root, expected, actual, safe_baseline)
            actual = inspect_containers(root, expected)
            snapshot['pending'] = None
            snapshot['services'] = {k: {**actual[k], 'up': 0, 'idle': 0} for k in expected}
            snapshot['lastUpdate'] = time.time()
            write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
        if restore:
            target = {k: {'mem': e['mem'], 'cpu': e['cpu']} for k, e in expected.items()}
            snapshot['pending'] = target
            write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
            if perform(root, expected, actual, target):
                print('Restored canonical Compose resource limits before repair')
            snapshot['pending'] = None
            snapshot['services'] = {k: {**actual[k], **target[k], 'up': 0, 'idle': 0} for k in expected}
            snapshot['lastUpdate'] = time.time()
        else:
            usage = read_usage(root, expected)
            psi_m = pressure('/proc/pressure/memory', 'some')
            psi_c = pressure('/proc/pressure/cpu', 'some')
            psi_io = pressure('/proc/pressure/io', 'some')
            available = host_available_mib()
            host_load1 = host_cpu_load1()
            fresh_oom = False
            for k in expected:
                # Include charged cache and current cgroup usage when assessing
                # safety of reducing memory.max, not just Docker stats usage.
                usage[k]['charged_mem'] = actual[k].get('memory_current_mib')
                previous = snapshot['services'].get(k, {})
                now_oom = actual[k].get('oom_kill')
                prior_oom = previous.get('oom_kill')
                fresh_oom |= (now_oom is not None and prior_oom is not None and now_oom > prior_oom)
                periods = actual[k].get('nr_periods')
                throttle = actual[k].get('nr_throttled')
                if periods is not None and throttle is not None:
                    usage[k]['throttled'] = sustained_quota_throttle(
                        periods, throttle, previous.get('nr_periods'),
                        previous.get('nr_throttled'))
            sampled_at = time.time()
            directml_busy = directml_workload(snapshot, sampled_at) if state.get('DIRECTML_SELECTED') == 'true' else True
            target, counters = plan(expected, actual, usage, snapshot,
                                    available_mib=available, memory_psi=psi_m, cpu_psi=psi_c,
                                    cpu_load1=host_load1, io_psi=psi_io, fresh_oom=fresh_oom,
                                    directml_selected=state.get('DIRECTML_SELECTED') == 'true',
                                    directml_active=directml_busy, cpus=int(state['CPUS']),
                                    cpu_envelope=int(state['CPU_DOCKER_ENVELOPE_MILLI']),
                                    directml_reserve=int(state['CPU_DIRECTML_RESERVE_MILLI']),
                                    budget=int(state['BUDGET_MIB']))
            snapshot['pending'] = target
            write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
            changes = perform(root, expected, actual, target)
            snapshot['pending'] = None
            snapshot['services'] = {k: {**actual[k], **target[k], **counters[k]} for k in expected}
            if changes:
                snapshot['lastUpdate'] = time.time()
                print(f'Adjusted bounded resource pool; RAM={sum(x["mem"] for x in target.values())}MiB; CPU={sum(x["cpu"] for x in target.values())}m')
            else:
                print('Resource burst envelope stable')
        snapshot['lastSample'] = time.time()
        write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
        return 0



# Resume/repair: Compose sometimes reports an already-running container as
# unchanged even when its live HostConfig CPU/RAM limits no longer agree with
# the effective model. Reconcile only limits, only on exact owned containers,
# without recreating services or overriding an authenticated burst lease.
def _compose_memory_bytes(value):
    from decimal import Decimal, InvalidOperation
    if isinstance(value, bool):
        raise RuntimeError('boolean Compose mem_limit is invalid')
    match = re.fullmatch(r'\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b?)\s*', str(value or ''), re.I)
    if not match:
        raise RuntimeError(f'invalid effective Compose mem_limit: {value!r}')
    multipliers = {'': 1, 'b': 1, 'k': 1024, 'kb': 1024, 'ki': 1024, 'kib': 1024,
                   'm': 1024**2, 'mb': 1024**2, 'mi': 1024**2, 'mib': 1024**2,
                   'g': 1024**3, 'gb': 1024**3, 'gi': 1024**3, 'gib': 1024**3,
                   't': 1024**4, 'tb': 1024**4, 'ti': 1024**4, 'tib': 1024**4}
    unit = match.group(2).lower()
    if unit not in multipliers:
        raise RuntimeError(f'unsupported Compose memory unit {unit!r}')
    exact = Decimal(match.group(1)) * multipliers[unit]
    if exact != exact.to_integral_value() or not (6 * MIB <= exact < 1024**5):
        raise RuntimeError('invalid Docker memory limit or fractional byte count')
    return int(exact)


def _compose_cpu_nanos(value):
    from decimal import Decimal, InvalidOperation
    try:
        d = Decimal(str(value))
        n = d * 1_000_000_000
        if not d.is_finite() or not (0 < n <= 256 * 1_000_000_000) or n != n.to_integral_value():
            raise ValueError('not a positive exact NanoCPU value')
        return int(n)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise RuntimeError(f'invalid effective Compose CPU limit: {value!r}') from exc


def _static_compose_limits(root, managed):
    config = json.loads(run(['docker', 'compose', 'config', '--format', 'json'], root, timeout=25))
    services = config.get('services') if isinstance(config, dict) else None
    if not isinstance(services, dict):
        raise RuntimeError('effective Compose services are missing')
    result = {}
    for service, expected in managed.items():
        item = services.get(service)
        if not isinstance(item, dict):
            raise RuntimeError(f'missing managed service in effective Compose config: {service}')
        result[service] = {'name': expected['name'],
                           'memory': _compose_memory_bytes(item.get('mem_limit')),
                           'cpu': _compose_cpu_nanos(item.get('cpus'))}
    return result


def _static_live_limits(root, desired):
    raw = json.loads(run(['docker', 'inspect'] + [v['name'] for v in desired.values()], root, timeout=18))
    by_name = {str(obj.get('Name', '')).lstrip('/'): obj for obj in raw}
    result = {}
    for service, expected in desired.items():
        obj = by_name.get(expected['name'])
        if not isinstance(obj, dict) or not obj.get('State', {}).get('Running'):
            raise RuntimeError(f'managed container not running: {expected["name"]}')
        labels = obj.get('Config', {}).get('Labels') or {}
        if labels.get('com.docker.compose.project') != 'hermesstack' or labels.get('com.docker.compose.service') != service:
            raise RuntimeError(f'unverified Docker ownership: {expected["name"]}')
        hc = obj.get('HostConfig') or {}
        memory, cpu = int(hc.get('Memory') or 0), int(hc.get('NanoCpus') or 0)
        if memory <= 0 or cpu <= 0:
            raise RuntimeError(f'unbounded Docker resource settings: {expected["name"]}')
        result[service] = {'id': obj['Id'], 'memory': memory, 'cpu': cpu,
                           'swap': int(hc.get('MemorySwap') or 0),
                           'pid': int(obj['State'].get('Pid') or 0)}
    return result


def _static_update_limit(root, name, metric, value):
    from decimal import Decimal
    option, argument = ('--memory', f'{value}b') if metric == 'memory' else (
        '--cpus', format(Decimal(value) / Decimal(1_000_000_000), 'f'))
    run(['docker', 'update', option, argument, name], root, timeout=20)


def reconcile_static_limits(root):
    # The systemd policy timer and installer must never independently mutate
    # the same Docker resources. Do not try to break a busy ownership lock.
    lockpath = root / 'data/latticevale/resource-burst.lock'
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    with lockpath.open('a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('resource controller currently owns the live Docker limits; retry repair later') from exc
        managed, state = load_expected(root, allow_override=True)
        # A verified runtime snapshot represents a legitimate controller lease.
        # Never overwrite its intentionally different allocation with static caps.
        try:
            verify_snapshot(root)
        except (RuntimeError, OSError, ValueError):
            pass
        else:
            print('Verified bounded resource-controller allocation; preserving live leases')
            return 0
        snapshot = read_json(root / 'data/latticevale/resource-burst-state.json', {})
        if isinstance(snapshot, dict) and snapshot.get('policyFingerprint') == state['POLICY_FINGERPRINT'] and snapshot.get('pending'):
            raise RuntimeError('incomplete burst-controller transaction; refusing to overwrite pending changes')
        desired = _static_compose_limits(root, managed)
        current = _static_live_limits(root, desired)
        target_changes = [(k, metric, current[k][metric], desired[k][metric])
                          for metric in ('memory', 'cpu') for k in desired
                          if current[k][metric] != desired[k][metric]]
        if not target_changes:
            print('Effective Compose resource limits already match all selected managed containers')
            return 0
        # Decrease before increase to avoid transiently exceeding the total
        # canonical envelope. A memory reduction requires cgroup charge data;
        # uncertainty is not permission to risk an OOM in a live service.
        for service, metric, old, new in target_changes:
            if metric == 'memory':
                if current[service]['swap'] > 0 and current[service]['swap'] < new:
                    raise RuntimeError(f'{service}: existing Docker memory+swap limit is below the new memory ceiling')
                if new < old:
                    pid = current[service]['pid']
                    charged = cgroup_event_counters(pid).get('memory_current_mib') if pid > 0 else None
                    if charged is None or new <= (charged + 64) * MIB:
                        raise RuntimeError(f'{service}: cannot safely lower live memory ceiling without adequate measured cgroup headroom')
        # Stable deterministic ordering supports exact rollback if a later
        # update or verification fails. Revalidate ownership and container IDs
        # before every mutation, including rollback.
        ordered = sorted(target_changes, key=lambda x: (0 if x[3] < x[2] else 1,
                                                        0 if x[1] == 'memory' else 1, x[0]))
        applied = []
        try:
            for service, metric, old, new in ordered:
                before = _static_live_limits(root, desired)[service]
                if before['id'] != current[service]['id'] or before[metric] != old:
                    raise RuntimeError(f'{service}: concurrent container or resource change detected')
                _static_update_limit(root, desired[service]['name'], metric, new)
                applied.append((service, metric, old, new))
                after = _static_live_limits(root, desired)[service]
                if after['id'] != current[service]['id'] or after[metric] != new:
                    raise RuntimeError(f'{service}: Docker did not apply expected {metric} limit')
            final = _static_live_limits(root, desired)
            if any(final[k][metric] != desired[k][metric] for k in desired for metric in ('memory', 'cpu')):
                raise RuntimeError('one or more selected managed Docker resource limits still differ from effective Compose')
        except Exception as exc:
            failed_undos = []
            for service, metric, old, new in reversed(applied):
                try:
                    before = _static_live_limits(root, desired)[service]
                    if before['id'] != current[service]['id'] or before[metric] != new:
                        failed_undos.append(f'{service}/{metric}: concurrent change')
                        continue
                    _static_update_limit(root, desired[service]['name'], metric, old)
                    after = _static_live_limits(root, desired)[service]
                    if after[metric] != old:
                        failed_undos.append(f'{service}/{metric}: rollback not applied')
                except Exception as rollback_exc:
                    failed_undos.append(f'{service}/{metric}: {rollback_exc}')
            detail = f'; rollback incomplete: {failed_undos}' if failed_undos else '; prior limits restored where changed'
            raise RuntimeError(f'static Compose resource repair failed: {exc}{detail}') from exc
        print(f'Reconciled {len(applied)} effective Compose hard-resource settings in place; managed containers were not restarted')
        return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stack', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--restore', action='store_true')
    p.add_argument('--reconcile-static', action='store_true',
                   help='Safely reconcile owned live CPU/RAM limits to effective Compose during repair')
    p.add_argument('--verify', action='store_true')
    p.add_argument('--check-override', action='store_true',
                   help='Read-only check of an image-only Compose override')
    a = p.parse_args()
    root = a.stack.resolve()
    if root != Path(__file__).resolve().parent:
        raise SystemExit('resource controller must run from its own installed stack')
    try:
        if a.reconcile_static:
            return reconcile_static_limits(root)
        if a.check_override:
            if not override_eligible(root):
                raise RuntimeError('Compose override modifies managed policy beyond Hermes image selection')
            return 0
        if a.verify:
            verify_snapshot(root)
            return 0
        return run_once(root, restore=a.restore)
    except Exception as exc:
        if a.reconcile_static:
            print(f'Static Docker resource reconciliation failed: {exc}', file=sys.stderr)
            return 2
        print(f'Resource burst controller inactive (canonical or last verified bounded limits retained): {exc}', file=sys.stderr)
        return 2 if (a.restore or a.verify or a.check_override) else 0  # Keep optional timer fail-safe.


if __name__ == '__main__':
    raise SystemExit(main())
