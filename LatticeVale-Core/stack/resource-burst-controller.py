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


def cpu_service_ceiling(service, baseline_milli, visible_cpus):
    """Bound a *container's aggregate* CPU quota below detected WSL capacity.

    Interactive Hermes and CPU-heavy inference receive larger independent
    ceilings than background services. Preserve a validated canonical floor,
    since this overlay is not authorized to rewrite the static installer plan.
    The canonical planner distributes the Docker envelope across active roles;
    this cap prevents the dynamic lender from concentrating most cores into a
    single process group. This is CPU-time quota, not pinned CPU affinity.
    """
    if visible_cpus < 1 or baseline_milli < CPU_QUANTUM_MILLI:
        raise ValueError('invalid canonical CPU baseline or visible CPU count')
    ratio = (0.60 if service == 'ollama' else
             0.45 if service == 'hermes' else 0.30)
    # Leave at least 10% CPU for the host regardless of backend/role.
    host_max = int(visible_cpus * 1000 * 0.90)
    bounded = int(visible_cpus * 1000 * ratio)
    bounded = max(CPU_QUANTUM_MILLI, (bounded // CPU_QUANTUM_MILLI) * CPU_QUANTUM_MILLI)
    return max(baseline_milli, min(host_max, bounded))


def memory_service_ceiling(service, baseline_mib, host_memory_mib, budget_mib):
    """Bound dynamic *container* memory by detected WSL RAM and service role.

    No arbitrary percentage may invalidate the model/context-aware canonical
    baseline. Hard ceilings are admission limits, not forced memory usage.
    This only limits optional burst *above* that baseline; active cgroup pages
    are never reclaimed to enforce it. Docker memory.max applies to an entire
    container including its child processes and charged file cache.
    """
    if min(baseline_mib, host_memory_mib, budget_mib) <= 0:
        raise ValueError('invalid memory baseline, detected host RAM or budget')
    # Keep non-inference roles from accumulating a dominant portion of RAM.
    ratio = (0.55 if service == 'ollama' else
             0.15 if service == 'hermes' else 0.12)
    by_host = (int(host_memory_mib * ratio) // MEM_QUANTUM_MIB) * MEM_QUANTUM_MIB
    # Never increase a service above the independently conserved Docker pool.
    return max(baseline_mib, min(budget_mib, by_host))


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
                                 ('memory.events', ('oom_kill', 'max'))):
            try:
                data = dict(line.split()[:2] for line in (group / filename).read_text().splitlines())
            except (OSError, ValueError):
                continue
            for field in fields:
                if field in data:
                    output['memory_max_events' if field == 'max' else field] = int(data[field])
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
    if record.get('pending') is not None and record.get('policyFingerprint') == state['POLICY_FINGERPRINT']:
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
         directml_reserve=0, budget=0, host_memory_mib=None, now=None):
    """Pure, reproducible planner; never raises per-service cap outside group budget."""
    now = time.time() if now is None else now
    old = {k: {'mem': current[k]['mem'], 'cpu': current[k]['cpu']} for k in expected}
    goal = {k: v.copy() for k, v in old.items()}
    # Canonical installer state supplies the WSL-visible RAM total; tests and
    # older call sites without that optional field retain the Docker budget.
    bound_ram = host_memory_mib is not None
    if host_memory_mib is None:
        host_memory_mib = budget
    if host_memory_mib < budget:
        raise ValueError('WSL memory must cover Docker budget')
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
        saturated = (u.get('memory_limit_hit', False) or
                     u['mem'] >= max(1, int(cap_m * 0.82)) or
                     u['cpu_pct'] >= (cap_c / 10) * 0.82 or u.get('throttled', False))
        idle = (not u.get('memory_limit_hit', False) and
                u['mem'] < cap_m * 0.50 and u['cpu_pct'] < (cap_c / 10) * 0.35)
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
    # Converge legacy leases that exceed the new independently bounded
    # per-service ceilings, even during cooldown or memory pressure. No
    # canonical baseline is reduced and no container memory cap is touched.
    for service in expected:
        ceiling = cpu_service_ceiling(service, expected[service]['cpu'], cpus)
        if goal[service]['cpu'] > ceiling:
            goal[service]['cpu'] = ceiling

    # Reclaim excess legacy *burst* memory only when safely possible. A cap
    # change never shrinks the canonical baseline, and missing cgroup charge
    # telemetry leaves the current ceiling untouched until it is safe.
    for service in expected if bound_ram else ():
        ceiling = memory_service_ceiling(
            service, expected[service]['mem'], host_memory_mib, budget)
        if goal[service]['mem'] > ceiling:
            charged = usage[service].get('charged_mem')
            if isinstance(charged, (int, float)) and charged >= 0 and not usage[service].get('memory_limit_hit', False):
                safe_floor = math.ceil(charged * 1.20) + 64
                if ceiling >= safe_floor:
                    goal[service]['mem'] = ceiling

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

    def transfer_cpu_to_throttled_receivers():
        # Within-envelope CPU-time transfers remain safe during memory/I/O PSI.
        # Do not shrink a busy receiver's CPU quota just because RAM is pressured.
        donors = [k for k in expected if counters[k]['idle'] >= 3 and
                  not usage[k].get('throttled', False)]
        donors.sort(key=lambda k: (PRIORITY[k], k))
        receivers = [k for k in expected if usage[k].get('throttled', False)]
        receivers.sort(key=lambda k: (-PRIORITY[k], k))
        spare = max(0, usable_cpu - sum(x['cpu'] for x in goal.values()))
        for receiver in receivers:
            base, cur = expected[receiver]['cpu'], goal[receiver]['cpu']
            ceiling = cpu_service_ceiling(receiver, base, cpus)
            request = (min(400, max(0, ceiling - cur)) // CPU_QUANTUM_MILLI) * CPU_QUANTUM_MILLI
            for donor in donors:
                if spare >= request:
                    break
                floor = cpu_donor_floor(donor, expected[donor]['cpu'])
                reclaim = (min(200, request - spare, max(0, goal[donor]['cpu'] - floor))
                           // CPU_QUANTUM_MILLI) * CPU_QUANTUM_MILLI
                goal[donor]['cpu'] -= reclaim
                spare += reclaim
            given = min(request, spare)
            goal[receiver]['cpu'] += given
            spare -= given

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
            if current[k]['cpu'] > e['cpu'] and (fresh_oom or not usage[k].get('throttled', False)):
                goal[k]['cpu'] = max(e['cpu'], current[k]['cpu'] - 100)
        if not fresh_oom:
            transfer_cpu_to_throttled_receivers()
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
            ceiling = cpu_service_ceiling(target, base, cpus)
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
                        (usage[k]['mem'] >= current[k]['mem'] * .82 or
                         usage[k].get('memory_limit_hit', False))]
    memory_receivers.sort(key=lambda k: (-PRIORITY[k], -usage[k]['mem'], k))
    # The cgroup charge (memory.current), including file cache, is required
    # before reducing anyone's hard memory limit. Docker stats alone is not.
    memory_donors = [k for k in expected if counters[k]['idle'] >= 3 and
                     not usage[k].get('memory_limit_hit', False) and
                     isinstance(usage[k].get('charged_mem'), (int, float)) and
                     usage[k]['charged_mem'] >= 0 and k not in memory_receivers]
    memory_donors.sort(key=lambda k: (PRIORITY[k], k))
    spare = max(0, budget - sum(x['mem'] for x in goal.values()))
    if memory_receivers:
        for target in memory_receivers:
            cur, base = goal[target]['mem'], expected[target]['mem']
            max_burst = min(max(base + 256, int(base * 1.75)),
                            (memory_service_ceiling(target, base, host_memory_mib, budget)
                             if bound_ram else budget))
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


def decision_report(expected, actual, usage, target, *, policy_fingerprint,
                    sampled_at, host_metrics):
    """Build a credential-free, bounded explanation of one scheduler sample."""
    services = {}
    for name in expected:
        old = actual[name]
        new = target[name]
        sample = usage[name]
        cpu_delta = int(new['cpu']) - int(old['cpu'])
        mem_delta = int(new['mem']) - int(old['mem'])
        if cpu_delta > 0:
            cpu_reason = ('measured-quota-throttling' if sample.get('throttled') else
                          'priority-envelope-rebalance')
        elif cpu_delta < 0:
            cpu_reason = 'conserved-envelope-rebalance'
        else:
            cpu_reason = 'no-change'
        if mem_delta > 0:
            mem_reason = ('recent-memory-limit-event' if sample.get('memory_limit_hit') else
                          'bounded-memory-demand')
        elif mem_delta < 0:
            mem_reason = 'verified-idle-donor-or-ceiling-convergence'
        else:
            mem_reason = 'no-change'
        services[name] = {
            'cpuMilli': {'before': int(old['cpu']), 'after': int(new['cpu']), 'reason': cpu_reason},
            'memoryMiB': {'before': int(old['mem']), 'after': int(new['mem']), 'reason': mem_reason},
            'usage': {
                'cpuPercent': round(float(sample.get('cpu_pct', 0.0)), 2),
                'dockerMemoryMiB': int(sample.get('mem', 0)),
                'chargedMemoryMiB': (int(sample['charged_mem'])
                                     if isinstance(sample.get('charged_mem'), (int, float)) else None),
                'quotaThrottled': bool(sample.get('throttled', False)),
                'memoryLimitEvent': bool(sample.get('memory_limit_hit', False)),
            },
        }
    metrics = {}
    for key in ('availableMiB', 'memoryPsiSomeAvg10', 'cpuPsiSomeAvg10',
                'ioPsiSomeAvg10', 'hostLoad1', 'directmlBusy', 'freshOom'):
        value = host_metrics.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[key] = round(float(value), 3)
        elif isinstance(value, (bool, str)) or value is None:
            metrics[key] = value
    return {
        'sampledAt': int(sampled_at),
        'policyFingerprint': str(policy_fingerprint)[:64],
        'host': metrics,
        'services': services,
    }


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




def _replacement_budget_plan(expected, state, actual, saved, replacements):
    """Plan only the capacity needed after verified canonical replacements.

    Never shrink a loaded model merely because it is over the static quota.
    Reclaim from unchanged, verified donors whose cgroup charge (including
    cache), 20% safety margin, 64-MiB cushion and per-service floor all fit.
    """
    budget = int(state['BUDGET_MIB'])
    current_total = sum(actual[k]['mem'] for k in expected)
    if current_total <= budget:
        return None
    if sum(saved[k]['mem'] for k in expected) > budget:
        raise RuntimeError('previous snapshot exceeds canonical memory envelope; refusing to legitimize it')
    expansion = sum(actual[k]['mem'] - saved[k]['mem'] for k in replacements)
    excess = current_total - budget
    if expansion < excess:
        raise RuntimeError('memory envelope excess is not explained by verified replacements')

    # A donor must retain its independently verified ID and allocation. Use
    # whole controller memory quanta to avoid fractional/hard-limit drift.
    choices = []
    for name, cfg in expected.items():
        charge = actual[name].get('memory_current_mib')
        if type(charge) is not int or charge < 0:
            continue
        safe_floor = max(cfg['floor'], math.ceil(charge * 1.20) + 64)
        available = max(0, (actual[name]['mem'] - safe_floor) // MEM_QUANTUM_MIB * MEM_QUANTUM_MIB)
        if name in replacements:
            # Compose recreated this verified managed container at its canonical
            # ceiling. It may safely return capacity it had donated previously,
            # but must never be reduced below its saved, verified lease.
            previously_donated = actual[name]['mem'] - saved[name]['mem']
            available = min(available, max(0, previously_donated))
        if available:
            # Recover the newly restored donation before touching an unchanged
            # service. The original saved allocations already fit the budget.
            choices.append((0 if name in replacements else 1, -available, name))
    choices.sort()
    # Do not silently over-recover or under-recover. Runtime quotas are
    # integral MiB, but the controller borrows in 16-MiB increments.
    needed = math.ceil(excess / MEM_QUANTUM_MIB) * MEM_QUANTUM_MIB
    target = {k: {'mem': actual[k]['mem'], 'cpu': actual[k]['cpu']} for k in expected}
    for _, negative_available, name in choices:
        amount = min(-negative_available, needed)
        target[name]['mem'] -= amount
        needed -= amount
        if needed == 0:
            break
    if needed:
        raise RuntimeError(f'replacement allocation exceeds canonical memory envelope by {excess} MiB; '
                           f'no verified donor has {needed} MiB of safe reclaimable cgroup headroom')
    if sum(v['mem'] for v in target.values()) > budget:
        raise RuntimeError('proposed recovery still exceeds canonical memory envelope')
    return target


def _replacement_cpu_envelope(state, record):
    """Honor ONLY a previously verified, still-fresh idle DirectML CPU loan.

    This matches the pre-hotfix admission rule; new recovery may not silently
    consume a host-reserved CPU slice if its idle proof has expired.
    """
    ceiling = int(state['CPU_DOCKER_ENVELOPE_MILLI'])
    if state.get('DIRECTML_SELECTED') != 'true':
        return ceiling
    idle = record.get('directmlCpuTelemetry') or {}
    last_sample = record.get('lastSample')
    if (isinstance(idle, dict) and idle.get('busy') is False and
            type(last_sample) in (int, float) and
            0 <= time.time() - last_sample <= 90):
        ceiling += min(int(state['CPU_DIRECTML_RESERVE_MILLI']) // 3,
                       int(state['CPUS']) * 100)
        ceiling = min(ceiling, int(state['CPUS']) * 900)
    return ceiling


def _replacement_cpu_plan(expected, state, actual, saved, replacements, envelope):
    """Return only the CPU quota restored by authenticated Compose recreation.

    CPU is not an OOM hard limit. A restored 50m loan must still be returned
    before an over-enveloped snapshot is rebound. Prefer the very service that
    recreated the donated quota, and preserve its prior verified limit and
    service-priority floor. Never use this as authority to bless foreign drift.
    """
    total = sum(actual[k]['cpu'] for k in expected)
    if total <= envelope:
        return None
    if sum(saved[k]['cpu'] for k in expected) > envelope:
        raise RuntimeError('previous CPU envelope snapshot exceeds canonical envelope; refusing rebind')
    expansion = sum(actual[k]['cpu'] - saved[k]['cpu'] for k in replacements)
    excess = total - envelope
    if expansion < excess:
        raise RuntimeError('CPU envelope excess is not explained by verified replacements')
    # These are quotas in 50-milliCPU quanta. A verified replacement can return
    # only its own restored prior donation; unchanged services can return only
    # safely preemptible quota above their priority-dependent donor floor.
    choices = []
    for name, cfg in expected.items():
        floor = cpu_donor_floor(name, cfg['cpu'])
        if name in replacements:
            floor = max(floor, saved[name]['cpu'])
        available = max(0, (actual[name]['cpu'] - floor) // CPU_QUANTUM_MILLI * CPU_QUANTUM_MILLI)
        if name in replacements:
            available = min(available, max(0, actual[name]['cpu'] - saved[name]['cpu']))
        if available:
            choices.append((0 if name in replacements else 1, -available, name))
    choices.sort()
    needed = math.ceil(excess / CPU_QUANTUM_MILLI) * CPU_QUANTUM_MILLI
    targets = {k: actual[k]['cpu'] for k in expected}
    for _, neg_available, name in choices:
        amount = min(-neg_available, needed)
        targets[name] -= amount
        needed -= amount
        if needed == 0:
            break
    if needed:
        raise RuntimeError(f'replacement allocation exceeds CPU envelope by {excess}m; '
                           f'no verified donor can return remaining {needed}m safely')
    if sum(targets.values()) > envelope:
        raise RuntimeError('CPU recovery plan still exceeds canonical CPU envelope')
    return targets


def _finish_replacement_budget_recovery(root, expected, state, actual, record):
    """Finish or resume an identity-verified CPU+RAM transaction, with rollback.

    All planned changes are reductions. Every independent Docker update has a
    prior durable journal, and is checked using freshly inspected owner/ID and
    limits. A timeout might follow a successful update, so rollback inspects
    every donor, not only changes that returned success to Python.
    """
    info = record.get('rebindBudgetRecovery')
    target = record.get('pending')
    if not isinstance(info, dict) or not isinstance(target, dict):
        raise RuntimeError('invalid replacement budget recovery journal')
    old_ids = info.get('previousIds')
    if (record.get('policyFingerprint') != state['POLICY_FINGERPRINT'] or
            not isinstance(old_ids, dict) or set(target) != set(expected) or
            set(record.get('services', {})) != set(expected) or
            set(actual) != set(expected)):
        raise RuntimeError('replacement budget recovery has invalid fingerprint or topology')
    donors = []
    for name, cfg in expected.items():
        prev = record['services'][name]
        goal = target[name]
        live = actual[name]
        if (live['id'] != prev.get('id') or
            any(type(goal.get(m)) is not int or type(prev.get(m)) is not int for m in ('mem', 'cpu')) or
            any(live[m] not in (prev[m], goal[m]) for m in ('mem', 'cpu')) or
            goal['mem'] < cfg['floor'] or goal['cpu'] < 50 or
            any(goal[m] > prev[m] for m in ('mem', 'cpu'))):
            raise RuntimeError(f'{name}: live identity/resource drift during recovery')
        if any(goal[m] < prev[m] for m in ('mem', 'cpu')):
            if name in old_ids and any(goal[m] < old_ids[name][m] for m in ('mem', 'cpu')):
                raise RuntimeError('replacement recovery would exceed its verified prior donation')
            if goal['cpu'] < cpu_donor_floor(name, cfg['cpu']):
                raise RuntimeError(f'{name}: recovery CPU quota below priority donor floor')
            donors.append(name)
    if not donors or sum(target[k]['mem'] for k in expected) > int(state['BUDGET_MIB']):
        raise RuntimeError('recovery journal violates canonical memory envelope')
    if sum(target[k]['cpu'] for k in expected) > _replacement_cpu_envelope(state, record):
        raise RuntimeError('recovery journal violates verified CPU envelope')

    before_limits = {name: {m: record['services'][name][m] for m in ('mem', 'cpu')}
                     for name in donors}
    # A service can have BOTH an independent memory and CPU reduction. Journal
    # each metric with identical interrupted-run and rollback guarantees.
    operations = [(name, metric) for metric in ('mem', 'cpu') for name in donors
                  if target[name][metric] < before_limits[name][metric]]
    try:
        for name, metric in operations:
            now = inspect_containers(root, expected)
            if any(now[k]['id'] != actual[k]['id'] or
                   any(now[k][m] not in (record['services'][k][m], target[k][m])
                       for m in ('mem', 'cpu')) for k in expected):
                raise RuntimeError('concurrent Docker replacement/resource change during recovery')
            if now[name][metric] == target[name][metric]:
                continue
            if metric == 'mem':
                charge = now[name].get('memory_current_mib')
                safe_floor = (max(expected[name]['floor'], math.ceil(charge * 1.20) + 64)
                              if type(charge) is int and charge >= 0 else None)
                if safe_floor is None or target[name]['mem'] < safe_floor:
                    raise RuntimeError(f'{name}: insufficient measured cgroup headroom for safe recovery')
            unit = 'memory' if metric == 'mem' else 'cpu'
            scale = MIB if metric == 'mem' else 1_000_000
            _static_update_limit(root, expected[name]['name'], unit, target[name][metric] * scale)
            verified = inspect_containers(root, expected)
            if verified[name]['id'] != actual[name]['id'] or verified[name][metric] != target[name][metric]:
                raise RuntimeError(f'{name}: Docker failed to apply expected {metric} limit')
        final = inspect_containers(root, expected)
        if any(final[k]['id'] != actual[k]['id'] or
               any(final[k][m] != target[k][m] for m in ('mem', 'cpu')) for k in expected):
            raise RuntimeError('recovery did not converge to journaled resource limits')
        if (sum(final[k]['mem'] for k in expected) > int(state['BUDGET_MIB']) or
            sum(final[k]['cpu'] for k in expected) > _replacement_cpu_envelope(state, record)):
            raise RuntimeError('recovery did not satisfy canonical resource envelopes')
        for name in expected:
            record['services'][name].update({k: final[name][k] for k in ('id', 'mem', 'cpu')})
        record['pending'] = None
        record.pop('rebindBudgetRecovery', None)
        record['lastUpdate'] = time.time()
        write_json(root / 'data/latticevale/resource-burst-state.json', record)
        return donors
    except Exception:
        rollback_ok = True
        for name, metric in reversed(operations):
            try:
                now = inspect_containers(root, expected)
                if now[name]['id'] != actual[name]['id']:
                    rollback_ok = False
                    continue
                if now[name][metric] == before_limits[name][metric]:
                    continue
                if now[name][metric] != target[name][metric]:
                    rollback_ok = False
                    continue
                unit = 'memory' if metric == 'mem' else 'cpu'
                scale = MIB if metric == 'mem' else 1_000_000
                _static_update_limit(root, expected[name]['name'], unit, before_limits[name][metric] * scale)
                check = inspect_containers(root, expected)
                if check[name]['id'] != actual[name]['id'] or check[name][metric] != before_limits[name][metric]:
                    rollback_ok = False
            except Exception:
                rollback_ok = False
        if rollback_ok:
            try:
                now = inspect_containers(root, expected)
                if any(now[k]['id'] != actual[k]['id'] or
                       any(now[k][metric] != actual[k][metric] for metric in ('mem', 'cpu'))
                       for k in expected):
                    rollback_ok = False
            except Exception:
                rollback_ok = False
        if rollback_ok:
            for name, old in old_ids.items():
                record['services'][name] = old
            for name in donors:
                if name not in old_ids:
                    record['services'][name].update(before_limits[name])
            record['pending'] = None
            record.pop('rebindBudgetRecovery', None)
            write_json(root / 'data/latticevale/resource-burst-state.json', record)
        # Preserve pending journal if ANY rollback failed or live state changed.
        raise


def reconcile_verified_replacements(root, expected, state, actual):
    """Rebind only independently verified canonical replacements, under the caller's lock.

    A container recreated by Compose gets a new ID, which invalidated the
    entire previously verified burst lease.  Never use this path to legitimize
    resource drift of an unchanged container, a pending transaction, or a
    replacement whose effective Compose limits are not canonical.
    """
    path = root / 'data/latticevale/resource-burst-state.json'
    record = read_json(path, {})
    if not isinstance(record, dict) or record.get('policyFingerprint') != state['POLICY_FINGERPRINT']:
        return []
    saved_services = record.get('services')
    if not isinstance(saved_services, dict) or set(saved_services) != set(expected):
        return []
    if record.get('rebindBudgetRecovery') is not None:
        if record.get('pending') is None:
            raise RuntimeError('replacement recovery marker without pending transaction')
        return _finish_replacement_budget_recovery(root, expected, state, actual, record)
    if record.get('pending') is not None:
        # Even an empty/malformed pending journal must not be reinterpreted.
        raise RuntimeError('pending controller transaction forbids replacement rebind')
    if set(actual) != set(expected):
        raise RuntimeError('managed container topology changed during replacement verification')

    replacements = []
    for name, baseline in expected.items():
        old = saved_services.get(name)
        live = actual[name]
        if not isinstance(old, dict) or not isinstance(old.get('id'), str) or not old['id']:
            return []
        if not isinstance(live.get('id'), str) or not live['id']:
            raise RuntimeError(f'{name}: live Docker container identity unavailable')
        for metric in ('mem', 'cpu'):
            if (type(old.get(metric)) is not int or old[metric] <= 0 or
                    type(live.get(metric)) is not int or live[metric] <= 0):
                raise RuntimeError(f'{name}: malformed live or saved {metric} limit')
        if live['id'] == old['id']:
            if any(live[metric] != old[metric] for metric in ('mem', 'cpu')):
                raise RuntimeError(f'{name}: unchanged container has unexplained resource drift')
        else:
            if live['mem'] != baseline['mem'] or live['cpu'] != baseline['cpu']:
                raise RuntimeError(f'{name}: replaced container is not at verified canonical limits')
            replacements.append(name)
        if live['mem'] < baseline['floor'] or live['cpu'] < 50:
            raise RuntimeError(f'{name}: live allocation violates service minimum')

    if not replacements:
        return []
    # Effective Compose must agree with the canonical baseline. In particular,
    # never bypass the user-override gate to accept a noncanonical replacement.
    desired = _static_compose_limits(root, expected)
    for name, baseline in expected.items():
        if (desired[name]['memory'] != baseline['mem'] * MIB or
                desired[name]['cpu'] != baseline['cpu'] * 1_000_000):
            raise RuntimeError(f'{name}: effective Compose limits differ from canonical policy; replacement rebind refused')
    if len({actual[k]['id'] for k in expected}) != len(expected):
        raise RuntimeError('duplicate Docker identities in managed topology')
    memory_target = _replacement_budget_plan(expected, state, actual, saved_services, replacements)
    cpu_target = _replacement_cpu_plan(expected, state, actual, saved_services, replacements,
                                       _replacement_cpu_envelope(state, record))
    recovery_target = None
    if memory_target is not None or cpu_target is not None:
        recovery_target = {k: {'mem': (memory_target[k]['mem'] if memory_target else actual[k]['mem']),
                               'cpu': (cpu_target[k] if cpu_target else actual[k]['cpu'])}
                           for k in expected}

    # Docker ownership/Running/IDs have already been checked by
    # inspect_containers. Reinspect under the same exclusive controller lock
    # immediately before persisting, so a Compose replacement cannot race us.
    confirmed = inspect_containers(root, expected)
    if any(confirmed[k]['id'] != actual[k]['id'] or
           confirmed[k]['mem'] != actual[k]['mem'] or
           confirmed[k]['cpu'] != actual[k]['cpu'] for k in expected):
        raise RuntimeError('concurrent Docker identity/resource change during replacement rebind')
    # Retain existing leases/counters; fresh containers reset their history.
    # When a replacement restored previously donated capacity, publish a
    # pending journal BEFORE any Docker update so interruption is recoverable.
    if recovery_target is not None:
        previous_ids = {name: dict(record['services'][name]) for name in replacements}
        for name in replacements:
            record['services'][name] = {**actual[name], 'up': 0, 'idle': 0}
        record['rebindBudgetRecovery'] = {'previousIds': previous_ids, 'startedAt': time.time()}
        record['pending'] = recovery_target
        write_json(path, record)
        donors = _finish_replacement_budget_recovery(root, expected, state, actual, record)
        print('Rebalanced over-budget CPU/RAM replacement safely using donor(s): ' + ', '.join(donors))
        return replacements
    for name in replacements:
        record['services'][name] = {**actual[name], 'up': 0, 'idle': 0}
    write_json(path, record)
    return replacements


def verify_snapshot(root):
    expected, state = load_expected(root)
    actual = inspect_containers(root, expected)
    snapshot = safe_state(root, expected, state, actual)
    if snapshot.get('pending') is not None or snapshot.get('_requires_restore'):
        raise RuntimeError('controller transaction has not converged')
    return True



def assert_safe_memory_reductions(actual, target):
    """Reject a hard-limit reduction that cannot retain measured cgroup headroom."""
    for name, goal in target.items():
        if goal['mem'] >= actual[name]['mem']:
            continue
        charge = actual[name].get('memory_current_mib')
        if type(charge) is not int or goal['mem'] <= charge + 64:
            raise RuntimeError(f'{name}: cannot safely restore lower memory ceiling without cgroup headroom')


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
        if not restore or read_json(root / 'data/latticevale/resource-burst-state.json', {}).get('rebindBudgetRecovery') is not None:
            # A verified replacement must not invalidate other active leases.
            # --restore intentionally has different, canonical-reset semantics.
            replacements = reconcile_verified_replacements(root, expected, state, actual)
            if replacements:
                # Recovery may have reduced verified container memory limits.
                # Never pass an outdated pre-recovery inspection to safe_state.
                actual = inspect_containers(root, expected)
                print('Rebound canonical replacement(s): ' + ', '.join(replacements))
        snapshot = safe_state(root, expected, state, actual)
        if snapshot.pop('_requires_restore', False):
            safe_baseline = {k: {'mem': expected[k]['mem'], 'cpu': expected[k]['cpu']} for k in expected}
            assert_safe_memory_reductions(actual, safe_baseline)
            write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
            perform(root, expected, actual, safe_baseline)
            actual = inspect_containers(root, expected)
            snapshot['pending'] = None
            snapshot['services'] = {k: {**actual[k], 'up': 0, 'idle': 0} for k in expected}
            snapshot['lastUpdate'] = time.time()
            write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
        if restore:
            target = {k: {'mem': e['mem'], 'cpu': e['cpu']} for k, e in expected.items()}
            assert_safe_memory_reductions(actual, target)
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
                current_max = actual[k].get('memory_max_events')
                previous_max = previous.get('memory_max_events')
                usage[k]['memory_limit_hit'] = (
                    isinstance(current_max, int) and isinstance(previous_max, int)
                    and current_max > previous_max)
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
                                    budget=int(state['BUDGET_MIB']),
                                    host_memory_mib=int(state.get('MEM_MIB', state['BUDGET_MIB'])))
            sample_report = decision_report(
                expected, actual, usage, target,
                policy_fingerprint=state['POLICY_FINGERPRINT'],
                sampled_at=sampled_at,
                host_metrics={
                    'availableMiB': available,
                    'memoryPsiSomeAvg10': psi_m,
                    'cpuPsiSomeAvg10': psi_c,
                    'ioPsiSomeAvg10': psi_io,
                    'hostLoad1': host_load1,
                    'directmlBusy': directml_busy,
                    'freshOom': fresh_oom,
                })
            history = snapshot.get('decisionHistory')
            if not isinstance(history, list):
                history = []
            history.append(sample_report)
            snapshot['decisionHistory'] = history[-24:]
            snapshot['pending'] = target
            write_json(root / 'data/latticevale/resource-burst-state.json', snapshot)
            changes = perform(root, expected, actual, target)
            snapshot['pending'] = None
            snapshot['services'] = {k: {**actual[k], **target[k], **counters[k]} for k in expected}
            if changes:
                snapshot['lastUpdate'] = time.time()
                print(f'Adjusted bounded resource pool; RAM={sum(x["mem"] for x in target.values())}MiB; CPU={sum(x["cpu"] for x in target.values())}m')
                for name, item in sample_report['services'].items():
                    cpu = item['cpuMilli']
                    mem = item['memoryMiB']
                    if cpu['before'] != cpu['after'] or mem['before'] != mem['after']:
                        print(f"  {name}: CPU {cpu['before']}->{cpu['after']}m ({cpu['reason']}); "
                              f"RAM {mem['before']}->{mem['after']}MiB ({mem['reason']})")
            else:
                print('Resource burst envelope stable; measured decision recorded')
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
        # Resolve only authenticated canonical Compose replacements before
        # considering a potentially unsafe global reduction to static limits.
        # load_expected without allow_override enforces the user-override gate.
        # Do not mask a rejected/unsafe replacement as a successful repair.
        saved = read_json(root / 'data/latticevale/resource-burst-state.json', {})
        rebind_candidate = (isinstance(saved, dict) and
                            saved.get('policyFingerprint') == state['POLICY_FINGERPRINT'] and
                            isinstance(saved.get('services'), dict) and
                            set(saved['services']) == set(managed) and
                            saved.get('pending') is None)
        if (isinstance(saved, dict) and saved.get('rebindBudgetRecovery') is not None):
            if not override_eligible(root):
                raise RuntimeError('Compose override prevents replacement budget recovery')
            validated, validated_state = load_expected(root)
            live = inspect_containers(root, validated)
            reconcile_verified_replacements(root, validated, validated_state, live)
            verify_snapshot(root)
            print('Completed interrupted replacement budget recovery safely')
            return 0
        if rebind_candidate and (not (root / 'compose.override.yaml').exists() or
                                 image_only_compose_override(root)):
            validated, validated_state = load_expected(root)
            live = inspect_containers(root, validated)
            replacements = reconcile_verified_replacements(root, validated, validated_state, live)
            if replacements:
                verify_snapshot(root)
                print('Preserved verified dynamic leases; rebound canonical replacement(s): ' + ', '.join(replacements))
                return 0
        snapshot = read_json(root / 'data/latticevale/resource-burst-state.json', {})
        if isinstance(snapshot, dict) and snapshot.get('policyFingerprint') == state['POLICY_FINGERPRINT'] and snapshot.get('pending') is not None:
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
    p.add_argument('--prepare-repair', action='store_true',
                   help='Preserve verified burst leases during repair; safely restore only invalid state')
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
        if a.prepare_repair:
            try:
                verify_snapshot(root)
            except (RuntimeError, ValueError, OSError):
                return run_once(root, restore=True)
            print('Existing verified bounded resource leases preserved during repair')
            return 0
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
        return 2 if (a.restore or a.prepare_repair or a.verify or a.check_override) else 0  # Keep optional timer fail-safe.


if __name__ == '__main__':
    raise SystemExit(main())
