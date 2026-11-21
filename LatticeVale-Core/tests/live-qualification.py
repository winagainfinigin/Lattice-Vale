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


def qualify(root: Path, duration: int, report: dict[str, object]) -> None:
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
    try:
        time.sleep(1)
        if load.poll() is not None:
            raise RuntimeError('The capped synthetic load container did not start')
        report['failedStep'] = 'sample-service-health'
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
        qualify(args.stack.resolve(), args.duration_seconds, report)
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
