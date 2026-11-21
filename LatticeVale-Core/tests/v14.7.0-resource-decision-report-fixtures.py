from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stack'))
spec = importlib.util.spec_from_file_location(
    'resource_burst_controller', ROOT / 'stack/resource-burst-controller.py')
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

expected = {'hermes': {'cpu': 500, 'mem': 1024}}
actual = {'hermes': {'cpu': 600, 'mem': 1280}}
usage = {'hermes': {
    'cpu_pct': 49.2, 'mem': 1000, 'charged_mem': 980,
    'throttled': True, 'memory_limit_hit': True,
    'raw_error': 'must never be copied to the report',
}}
target = {'hermes': {'cpu': 700, 'mem': 1344}}
report = module.decision_report(
    expected, actual, usage, target,
    policy_fingerprint='f' * 64, sampled_at=123456,
    host_metrics={
        'availableMiB': 4096, 'memoryPsiSomeAvg10': 1.25,
        'cpuPsiSomeAvg10': 20.0, 'ioPsiSomeAvg10': 0.0,
        'hostLoad1': 1.0, 'directmlBusy': False, 'freshOom': False,
        'api_token': 'must never be copied to the report',
    })

assert report['sampledAt'] == 123456
assert report['services']['hermes']['cpuMilli'] == {
    'before': 600, 'after': 700, 'reason': 'measured-quota-throttling'}
assert report['services']['hermes']['memoryMiB']['reason'] == 'recent-memory-limit-event'
assert report['services']['hermes']['usage']['chargedMemoryMiB'] == 980
assert 'raw_error' not in repr(report) and 'api_token' not in repr(report)
assert 'must never be copied' not in repr(report)
print('PASS sanitized bounded resource decision report')

# Behavioral qualification tests: exercise the actual handler with a mocked Docker
# engine; reject unmarked stacks before making any Docker API call.
import json
import subprocess
import tempfile
from unittest.mock import patch

qualification_spec = importlib.util.spec_from_file_location('latticevale_qualification',
                                                            ROOT / 'tests/live-qualification.py')
assert qualification_spec is not None and qualification_spec.loader is not None
qualification = importlib.util.module_from_spec(qualification_spec)
qualification_spec.loader.exec_module(qualification)

with tempfile.TemporaryDirectory() as tmp:
    testroot = Path(tmp)
    output = testroot / 'failed-report.json'
    probe = subprocess.run([sys.executable, str(ROOT / 'tests/live-qualification.py'),
                            '--stack', str(testroot), '--duration-seconds', '60',
                            '--output', str(output)], capture_output=True, text=True, timeout=10)
    assert probe.returncode == 1
    rejected = json.loads(output.read_text())
    assert rejected['result'] == 'fail' and rejected['failedStep'] == 'disposable-stack-marker'
    assert rejected['passCriteria']['pressureAndWatchdog'] == 'observed-not-judged'

    (testroot / qualification.MARKER).write_text(qualification.MARKER_TEXT)
    calls = []
    def fake_command(args, *, cwd, timeout=30):
        calls.append(args)
        if args[:3] == ['docker', 'compose', 'ps']:
            result = json.dumps([{'ID': 'id_hermes_123', 'Service': 'hermes',
                                  'State': 'running', 'Health': 'healthy'}])
        elif args[:2] == ['docker', 'stats']:
            result = json.dumps({'CPUPerc': '5.00%'})
        elif args[:3] == ['docker', 'compose', 'logs']:
            result = 'hermes | watchdog once'
        else:
            result = ''
        return subprocess.CompletedProcess(args, 0, result, '')

    with patch.object(qualification, 'command', fake_command):
        assert qualification.stats_max_cpu(testroot) == 5.0
        assert qualification.recent_gateway_watchdog_signals(testroot) == 1
    stats = next(args for args in calls if args[:2] == ['docker', 'stats'])
    assert stats[-1] == 'id_hermes_123' and len(stats) == 6, stats
    logs = next(args for args in calls if args[:3] == ['docker', 'compose', 'logs'])
    assert logs[-1] == 'hermes' and 'hermes-agent' not in logs

    class FakeProcess:
        def poll(self): return None
        def wait(self, timeout): return 0
        def kill(self): raise AssertionError('The bounded probe should not need killing')

    times = iter([0, 61])
    report = {'result': 'fail', 'passCriteria': {}}
    calls.clear()
    with patch.object(qualification, 'command', fake_command), \
         patch.object(qualification.subprocess, 'Popen', return_value=FakeProcess()), \
         patch.object(qualification.time, 'sleep', return_value=None), \
         patch.object(qualification.time, 'monotonic', side_effect=lambda: next(times)):
        qualification.qualify(testroot, 60, report)
    assert report['result'] == 'pass' and report['failedStep'] is None
    assert report['passCriteria']['pressureAndWatchdog'] == 'observed-not-judged'
    assert any(args[:2] == ['docker', 'stop'] for args in calls)

print('PASS opt-in qualification failure report, scoped Docker evidence and mocked success path')
