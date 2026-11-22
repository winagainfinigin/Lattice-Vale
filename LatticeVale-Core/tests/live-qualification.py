#!/usr/bin/env python3
"""Opt-in disposable-stack qualification with bounded synthetic CPU pressure.

Never run on a production stack.  A marker with exact contents is required
before any Docker interaction, and reports are written even on failed checks.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

MARKER = '.latticevale-qualification-stack'
MARKER_TEXT = 'DISPOSABLE LATTICEVALE QUALIFICATION STACK'
LOAD_NAME = f'latticevale-qualification-cpu-{os.getpid()}'
KNOWN_SERVICES = {
    'hermes', 'synapse-db', 'synapse', 'searxng-valkey', 'searxng', 'qmd',
    'qmd-indexer', 'ollama', 'honcho-db', 'honcho-redis', 'honcho-api',
    'honcho-deriver',
}


def command(args: list[str], *, cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, check=False)


def parse_compose_ps(text: str) -> list[dict[str, object]]:
    try:
        value = json.loads(text)
        rows = value if isinstance(value, list) else [value]
        return [row for row in rows if isinstance(row, dict)]
    except ValueError:
        rows = []
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows


def compose_rows(root: Path) -> list[dict[str, object]]:
    proc = command(['docker', 'compose', 'ps', '--format', 'json'], cwd=root, timeout=30)
    if proc.returncode:
        raise RuntimeError('Compose service status could not be read')
    rows = parse_compose_ps(proc.stdout)
    if not rows:
        raise RuntimeError('No Compose services were returned for the marked stack')
    return rows


def compose_status(root: Path) -> tuple[int, int, int]:
    rows = compose_rows(root)
    unhealthy = 0
    known = 0
    for row in rows:
        name = str(row.get('Service') or '').lower()
        if name in KNOWN_SERVICES:
            known += 1
        state = str(row.get('State') or row.get('Status') or '').lower()
        health = str(row.get('Health') or '').lower()
        if any(bad in state for bad in ('exited', 'dead', 'paused', 'restarting')) or health in ('unhealthy', 'starting-failed'):
            unhealthy += 1
    return len(rows), unhealthy, known


def psi_avg10(path: str) -> float | None:
    try:
        line = next(x for x in Path(path).read_text().splitlines() if x.startswith('some '))
        match = re.search(r'\bavg10=([0-9.]+)', line)
        return float(match.group(1)) if match else None
    except (OSError, StopIteration, ValueError):
        return None


def stats_max_cpu(root: Path) -> float | None:
    # IDs come from *this* marked Compose project, never engine-wide stats.
    ids = [str(row.get('ID') or '') for row in compose_rows(root)]
    ids = [container_id for container_id in ids if container_id]
    if not ids:
        return None
    proc = command(['docker', 'stats', '--no-stream', '--format', '{{json .}}', *ids], cwd=root, timeout=30)
    if proc.returncode:
        return None
    values = []
    for line in proc.stdout.splitlines():
        try:
            row = json.loads(line)
            value = float(str(row.get('CPUPerc', '0')).rstrip('%').replace(',', ''))
            if math.isfinite(value):
                values.append(value)
        except (ValueError, TypeError):
            continue
    return max(values) if values else None


def recent_gateway_watchdog_signals(root: Path) -> int | None:
    services = {str(row.get('Service') or '') for row in compose_rows(root)}
    if 'hermes' not in services:
        return None
    proc = command(['docker', 'compose', 'logs', '--since', '10m', '--tail', '1000', '--no-color', 'hermes'], cwd=root, timeout=20)
    if proc.returncode:
        return None
    return sum(len(re.findall(pattern, proc.stdout + '\n' + proc.stderr, re.I))
               for pattern in (r'watchdog', r'missed liveness', r'event loop', r'slow callback'))


def write_report(output: Path, report: dict[str, object]) -> None:
    # Atomic replacement prevents leaving a partial JSON report on interruption.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + f'.{os.getpid()}.tmp')
    try:
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def resource_history(root: Path) -> dict[str, object]:
    """Read only controller sample metadata; do not convert lack of activity to PASS."""
    path = root / 'data/latticevale/resource-burst-state.json'
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        rows = payload.get('decisionHistory') or []
        valid = [r for r in rows if isinstance(r, dict) and
                 isinstance(r.get('sampledAt'), (int, float))]
        return {'available': True, 'sampleCount': len(valid),
                'lastSampleAt': valid[-1]['sampledAt'] if valid else None,
                'history': valid}
    except (OSError, ValueError, TypeError, AttributeError):
        return {'available': False, 'sampleCount': 0, 'history': []}


def observe_transfers(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    """Assess evidence of actual transfers and repayment, never assume a pass.

    A donor's initial reduction is not proof that a recipient later repaid a
    loan. Track increase, then subsequent reduction of that SAME resource.
    """
    old_at = before.get('lastSampleAt')
    rows = [x for x in after.get('history', [])
            if isinstance(x, dict) and isinstance(x.get('sampledAt'), (int, float))
            and (old_at is None or x['sampledAt'] > old_at)]
    rows.sort(key=lambda x: x['sampledAt'])
    changed = set()
    borrowed = set()
    repaid = set()
    for row in rows:
        for service, values in (row.get('services') or {}).items():
            if not isinstance(values, dict):
                continue
            for field in ('cpuMilli', 'memoryMiB'):
                pair = values.get(field) or {}
                old, new = pair.get('before'), pair.get('after')
                if type(old) is not int or type(new) is not int or old == new:
                    continue
                key = (service, field)
                changed.add(key)
                if new > old:
                    borrowed.add(key)
                elif key in borrowed:
                    repaid.add(key)
    return {
        'freshControllerSamples': len(rows),
        'changedServicesAndResources': [f'{name}:{field}' for name, field in sorted(changed)],
        'borrowedServicesAndResources': [f'{name}:{field}' for name, field in sorted(borrowed)],
        'repaidServicesAndResources': [f'{name}:{field}' for name, field in sorted(repaid)],
        'redistributionObserved': bool(changed),
        'borrowAndReturnObserved': bool(repaid),
        'qualification': ('borrow-and-return-observed' if repaid else
                          'transfer-observed-but-return-unproven' if changed else
                          'not-demonstrated'),
    }


def qualify(root: Path, duration: int, report: dict[str, object], *, exercise_hermes_cpu=False) -> None:
    # Deliberately perform NO docker command before the explicit marker check.
    report['failedStep'] = 'validate-duration'
    if not (60 <= duration <= 3600):
        raise ValueError('--duration-seconds must be between 60 and 3600')
    report['failedStep'] = 'disposable-stack-marker'
    marker = root / MARKER
    if not marker.is_file() or marker.read_text(encoding='utf-8').strip() != MARKER_TEXT:
        raise RuntimeError('Refusing live qualification: explicit disposable-stack marker missing or invalid')

    report['failedStep'] = 'inspect-preloaded-probe-image'
    image = command(['docker', 'image', 'inspect', 'alpine:3.21'], cwd=root, timeout=20)
    if image.returncode:
        raise RuntimeError('Bounded probe image alpine:3.21 is not already present; no image is pulled')

    report['failedStep'] = 'initial-verification'
    initial_verify = command(['./manage.sh', 'verify'], cwd=root, timeout=600)
    report['initialVerifyExitCode'] = initial_verify.returncode
    initial_count, initial_unhealthy, _ = compose_status(root)
    report['initialServiceCount'] = initial_count
    report['initialUnhealthyServiceCount'] = initial_unhealthy
    report['passCriteria']['initialVerifySucceeded'] = initial_verify.returncode == 0
    report['passCriteria']['initialServicesHealthy'] = initial_unhealthy == 0
    if initial_verify.returncode or initial_unhealthy:
        raise RuntimeError('Initial verification or service-health check failed; no load probe started')

    before_resource = resource_history(root)
    report['resourceControllerBefore'] = {k: v for k, v in before_resource.items() if k != 'history'}
    report['failedStep'] = 'start-bounded-load'
    load = subprocess.Popen(
        ['docker', 'run', '--rm', '--pull=never', '--name', LOAD_NAME,
         '--cpus', '0.50', '--memory', '256m', 'alpine:3.21', 'sh', '-c', 'while :; do :; done'],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    started = int(time.time())
    cpu_psi: list[float] = []
    memory_psi: list[float] = []
    io_psi: list[float] = []
    cpu_pct: list[float] = []
    service_samples = 0
    unhealthy_samples = 0
    interrupted = False
    hermes_load = None
    try:
        time.sleep(1)
        if load.poll() is not None:
            raise RuntimeError('The capped synthetic load container did not start')
        report['failedStep'] = 'sample-service-health'
        if exercise_hermes_cpu:
            # Explicitly opt in, only after the disposable-stack marker was validated.
            # In-container Python exits on its own after at most 120 seconds.
            # No models, files, options, or user data are changed by this probe.
            available = {str(r.get('Service') or '') for r in compose_rows(root)}
            if 'hermes' not in available:
                raise RuntimeError('Hermes is not in this marked Compose project')
            seconds = min(120, max(30, duration // 2))
            # A multiline statement is needed for Python's compound while.
            code = 'import time\nend=time.monotonic()+%d\nn=0\nwhile time.monotonic()<end:\n n=(n+1)%%1000003' % seconds
            hermes_load = subprocess.Popen(
                ['docker', 'compose', 'exec', '-T', '-u', 'hermes', 'hermes',
                 'python3', '-c', code], cwd=root, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            report['hermesCpuProbe'] = {'requested': True, 'durationSeconds': seconds,
                                        'status': 'started-bounded-in-container'}
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            count, unhealthy, _known = compose_status(root)
            service_samples += 1
            unhealthy_samples += unhealthy
            if count != initial_count or unhealthy:
                interrupted = True
                break
            for path, values in (('/proc/pressure/cpu', cpu_psi),
                                 ('/proc/pressure/memory', memory_psi),
                                 ('/proc/pressure/io', io_psi)):
                value = psi_avg10(path)
                if value is not None:
                    values.append(value)
            current_cpu = stats_max_cpu(root)
            if current_cpu is not None:
                cpu_pct.append(current_cpu)
            time.sleep(min(10, max(0, deadline - time.monotonic())))
    finally:
        if hermes_load is not None:
            try:
                hermes_load.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # The in-container process still has its own monotonic deadline.
                hermes_load.terminate()
                try:
                    hermes_load.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    hermes_load.kill()
                    hermes_load.wait(timeout=3)
        # Cleanup is attempted on every post-launch path, including exceptions.
        command(['docker', 'stop', '--time', '3', LOAD_NAME], cwd=root, timeout=15)
        try:
            load.wait(timeout=10)
        except subprocess.TimeoutExpired:
            load.kill()
            load.wait(timeout=5)
        report.update({
            'durationSeconds': int(time.time()) - started,
            'samples': service_samples,
            'unhealthyServiceSamples': unhealthy_samples,
            'hostPressureAvg10Max': {
                'cpuSome': max(cpu_psi) if cpu_psi else None,
                'memorySome': max(memory_psi) if memory_psi else None,
                'ioSome': max(io_psi) if io_psi else None,
            },
            'containerCpuPercentMax': max(cpu_pct) if cpu_pct else None,
        })

    if exercise_hermes_cpu and hermes_load is not None:
        if hermes_load.returncode != 0:
            report['hermesCpuProbe']['status'] = 'command-failed'
            raise RuntimeError('Opted-in Hermes CPU probe did not complete successfully')
        report['hermesCpuProbe']['status'] = 'completed'
    after_resource = resource_history(root)
    report['resourceControllerAfter'] = {k: v for k, v in after_resource.items() if k != 'history'}
    report['resourceRedistribution'] = observe_transfers(before_resource, after_resource)
    # Seeing no transfer is NOT a qualification PASS: it may simply mean no donor
    # was available, no managed load crossed thresholds, or the timer was inactive.
    report['passCriteria']['stableServiceCountAndHealth'] = not interrupted
    report['failedStep'] = 'final-verification'
    final_verify = command(['./manage.sh', 'verify'], cwd=root, timeout=600)
    report['finalVerifyExitCode'] = final_verify.returncode
    final_count, final_unhealthy, known_services = compose_status(root)
    report.update({
        'finalServiceCount': final_count,
        'knownLatticeValeServiceCount': known_services,
        'finalUnhealthyServiceCount': final_unhealthy,
        'recentHermesGatewayWatchdogSignalCount': recent_gateway_watchdog_signals(root),
    })
    report['passCriteria'] = {
        'initialVerifySucceeded': True,
        'initialServicesHealthy': initial_unhealthy == 0,
        'stableServiceCountAndHealth': not interrupted,
        'finalVerifySucceeded': final_verify.returncode == 0,
        'finalServicesHealthy': final_unhealthy == 0,
        'pressureAndWatchdog': 'observed-not-judged',
    }
    # Preserve original verdict logic; no pressure thresholds are invented.
    if not interrupted and final_verify.returncode == 0 and final_unhealthy == 0:
        report['result'] = 'pass'
        report['failedStep'] = None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stack', type=Path, required=True)
    parser.add_argument('--duration-seconds', type=int, default=300)
    parser.add_argument('--exercise-hermes-cpu', action='store_true',
                        help='Opt-in bounded Hermes CPU probe; disposable stack only')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, object] = {
        'schema': 1, 'result': 'fail', 'failedStep': 'preflight',
        'directmlInference': 'not-exercised-by-this-WSL-load-probe',
        'syntheticProbe': {'cpuLimit': '0.50', 'memoryLimitMiB': 256, 'imagePulled': False},
        'passCriteria': {
            'initialVerifySucceeded': None, 'initialServicesHealthy': None,
            'stableServiceCountAndHealth': None, 'finalVerifySucceeded': None,
            'finalServicesHealthy': None, 'pressureAndWatchdog': 'observed-not-judged',
        },
    }
    try:
        qualify(args.stack.resolve(), args.duration_seconds, report,
                exercise_hermes_cpu=args.exercise_hermes_cpu)
    except Exception as exc:
        report['failureType'] = type(exc).__name__
        print(f"Qualification failed safely at step {report['failedStep']}: {type(exc).__name__}", file=sys.stderr)
    try:
        write_report(args.output.resolve(), report)
    except OSError as exc:
        print(f'Could not write qualification report: {type(exc).__name__}', file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report['result'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
