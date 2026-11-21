#!/usr/bin/env python3
"""Read-only stack qualification plus a bounded disposable CPU load probe.

This is deliberately opt-in. It refuses to run unless the selected stack has a
`.latticevale-qualification-stack` marker containing the exact disposable-stack
phrase. The synthetic container is separately capped at 0.5 CPU and 256 MiB;
the script never recreates, restarts, or updates a LatticeVale service.
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


def compose_status(root: Path) -> tuple[int, int, int]:
    proc = command(['docker', 'compose', 'ps', '--format', 'json'], cwd=root, timeout=30)
    if proc.returncode:
        raise RuntimeError('Compose service status could not be read')
    rows = parse_compose_ps(proc.stdout)
    if not rows:
        raise RuntimeError('No Compose services were returned for the marked stack')
    unhealthy = 0
    known = 0
    for row in rows:
        name = str(row.get('Service') or row.get('Name') or '').split('-', 1)[0].lower()
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
    proc = command(['docker', 'stats', '--no-stream', '--format', '{{json .}}'], cwd=root, timeout=30)
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
    proc = command(['docker', 'logs', '--since', '10m', '--tail', '1000', 'hermes-agent'], cwd=root, timeout=20)
    if proc.returncode:
        return None
    return sum(len(re.findall(pattern, proc.stdout + '\n' + proc.stderr, re.I))
               for pattern in (r'watchdog', r'missed liveness', r'event loop', r'slow callback'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stack', type=Path, required=True)
    parser.add_argument('--duration-seconds', type=int, default=300)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.stack.resolve()
    if not (60 <= args.duration_seconds <= 3600):
        raise SystemExit('--duration-seconds must be between 60 and 3600')
    marker = root / MARKER
    if not marker.is_file() or marker.read_text(encoding='utf-8').strip() != MARKER_TEXT:
        raise SystemExit(f'Refusing live qualification: {root.name} lacks the explicit disposable-stack marker.')

    image = command(['docker', 'image', 'inspect', 'alpine:3.21'], cwd=root, timeout=20)
    if image.returncode:
        raise SystemExit('The bounded probe image alpine:3.21 must already be present; no image is pulled.')

    initial_verify = command(['./manage.sh', 'verify'], cwd=root, timeout=600)
    initial_count, initial_unhealthy, _ = compose_status(root)
    if initial_verify.returncode or initial_unhealthy:
        raise SystemExit('Refusing load probe because the initial verification or service-health check failed.')

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
            raise RuntimeError('The capped synthetic load container did not start.')
        deadline = time.monotonic() + args.duration_seconds
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
        command(['docker', 'stop', '--time', '3', LOAD_NAME], cwd=root, timeout=15)
        try:
            load.wait(timeout=10)
        except subprocess.TimeoutExpired:
            load.kill()
            load.wait(timeout=5)

    final_verify = command(['./manage.sh', 'verify'], cwd=root, timeout=600)
    final_count, final_unhealthy, known_services = compose_status(root)
    watchdog_signals = recent_gateway_watchdog_signals(root)
    report = {
        'schema': 1,
        'result': 'pass' if not interrupted and final_verify.returncode == 0 and final_unhealthy == 0 else 'fail',
        'durationSeconds': int(time.time()) - started,
        'initialVerifyExitCode': initial_verify.returncode,
        'finalVerifyExitCode': final_verify.returncode,
        'initialServiceCount': initial_count,
        'finalServiceCount': final_count,
        'knownLatticeValeServiceCount': known_services,
        'samples': service_samples,
        'unhealthyServiceSamples': unhealthy_samples,
        'finalUnhealthyServiceCount': final_unhealthy,
        'hostPressureAvg10Max': {
            'cpuSome': max(cpu_psi) if cpu_psi else None,
            'memorySome': max(memory_psi) if memory_psi else None,
            'ioSome': max(io_psi) if io_psi else None,
        },
        'containerCpuPercentMax': max(cpu_pct) if cpu_pct else None,
        'recentHermesGatewayWatchdogSignalCount': watchdog_signals,
        'syntheticProbe': {'cpuLimit': '0.50', 'memoryLimitMiB': 256, 'imagePulled': False},
        'directmlInference': 'not-exercised-by-this-WSL-load-probe',
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['result'] == 'pass' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError) as exc:
        print(f'Qualification failed safely: {type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
