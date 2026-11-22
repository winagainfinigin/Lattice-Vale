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

# v14.7.0 resource-explain diagnostics must be derived from the exact planner
# and from verified read-only live allocations. Do not create another allocator.
from unittest.mock import patch as _patch
from io import StringIO
from contextlib import redirect_stdout

ro_expected = {
    'hermes': {'name': 'hermes-agent', 'mem': 1024, 'cpu': 700, 'floor': 600},
    'qmd-indexer': {'name': 'hermes-qmd-indexer', 'mem': 1024, 'cpu': 500, 'floor': 512},
}
ro_actual = {
    'hermes': {'mem': 1024, 'cpu': 700, 'memory_current_mib': 850},
    'qmd-indexer': {'mem': 1024, 'cpu': 500, 'memory_current_mib': 200},
}
ro_usage = {
    'hermes': {'mem': 870, 'cpu_pct': 65.0, 'charged_mem': 850},
    'qmd-indexer': {'mem': 220, 'cpu_pct': 2.0, 'charged_mem': 200},
}
ro_record = {'lastUpdate': 0, 'services': {
    'hermes': {'up': 1, 'idle': 0}, 'qmd-indexer': {'up': 0, 'idle': 2}}}
trace = {}
ro_goals, ro_counters = module.plan(
    ro_expected, ro_actual, ro_usage, ro_record,
    available_mib=4096, memory_psi=0, cpu_psi=0,
    io_psi=0, cpus=4, cpu_envelope=1200, budget=2048,
    host_memory_mib=4096, now=150, trace=trace)
assert ro_goals['hermes']['mem'] > ro_actual['hermes']['mem']
assert trace['hermes']['memory'] == 'measured-demand-transfer'
assert ro_goals['qmd-indexer']['mem'] < ro_actual['qmd-indexer']['mem']
assert trace['qmd-indexer']['memory'] == 'safe-cap-reclamation'
assert sum(x['mem'] for x in ro_goals.values()) <= 2048
assert trace.keys() == ro_expected.keys()

pressure_trace = {}
module.plan(ro_expected, ro_actual, ro_usage, ro_record,
            available_mib=200, memory_psi=8, cpu_psi=3,
            cpus=4, cpu_envelope=1200, budget=2048,
            host_memory_mib=4096, now=150, trace=pressure_trace)
assert pressure_trace['hermes']['memory'] == 'host-pressure-protection'
cooldown_trace = {}
module.plan(ro_expected, ro_actual, ro_usage, {'lastUpdate': 140, 'services': ro_record['services']},
            available_mib=4096, memory_psi=0, cpu_psi=0,
            cpus=4, cpu_envelope=1200, budget=2048,
            host_memory_mib=4096, now=150, trace=cooldown_trace)
assert cooldown_trace['hermes']['memory'] == 'controller-cooldown'

sample = module.decision_report(
    ro_expected, ro_actual, ro_usage, ro_goals, policy_fingerprint='z' * 64,
    sampled_at=12345, host_metrics={}, trace=trace)
assert sample['services']['hermes']['diagnosticReasonCodes']['memory'] == 'measured-demand-transfer'
assert 'unexpected_password' not in repr(sample)

fake_state = {
    'MEM_MIB': '4096', 'BUDGET_MIB': '2048', 'CPUS': '4', 'CPU_DOCKER_ENVELOPE_MILLI': '1200',
    'CPU_DIRECTML_RESERVE_MILLI': '0', 'DIRECTML_SELECTED': 'false',
    'POLICY_FINGERPRINT': 'z' * 64,
}
reader_record = {'services': {'hermes': {'idle': 0}, 'qmd-indexer': {'idle': 3}},
                 'decisionHistory': [sample]}
with _patch.object(module, 'load_expected', return_value=(ro_expected, fake_state)), \
     _patch.object(module, 'inspect_containers', return_value=ro_actual), \
     _patch.object(module, 'safe_state', return_value=reader_record), \
     _patch.object(module, 'read_usage', return_value=ro_usage), \
     _patch.object(module, 'host_available_mib', return_value=3000), \
     _patch.object(module, 'pressure', return_value=0.0), \
     _patch.object(module, 'write_json', side_effect=AssertionError('read-only violated')), \
     _patch.object(module, 'perform', side_effect=AssertionError('read-only violated')):
    output = StringIO()
    with redirect_stdout(output):
        assert module.explain_resources(Path('/not/an/actual/stack'), as_json=True) == 0
    view = json.loads(output.getvalue())
    assert view['status'] == 'verified-live-limits'
    assert view['dockerAssignedMiB'] == 2048
    assert view['services']['qmd-indexer']['verifiedIdleDonorHeadroomMiB'] >= 0
    assert view['services']['hermes']['lastDecisionReasonCodes']['memory'] == 'measured-demand-transfer'

assert qualification.observe_transfers(
    {'lastSampleAt': 100},
    {'history': [{'sampledAt': 101, 'services': {'hermes': {
        'cpuMilli': {'before': 500, 'after': 550},
        'memoryMiB': {'before': 1000, 'after': 1000}}}}]}) == {
            'freshControllerSamples': 1,
            'changedServicesAndResources': ['hermes:cpuMilli'],
            'borrowedServicesAndResources': ['hermes:cpuMilli'],
            'repaidServicesAndResources': [],
            'redistributionObserved': True, 'borrowAndReturnObserved': False,
            'qualification': 'transfer-observed-but-return-unproven'}
assert qualification.observe_transfers({'lastSampleAt': 100}, {'history': [
    {'sampledAt': 101, 'services': {'hermes': {'memoryMiB': {'before': 1000, 'after': 1128}}}},
    {'sampledAt': 102, 'services': {'hermes': {'memoryMiB': {'before': 1128, 'after': 1064}}}},
]})['qualification'] == 'borrow-and-return-observed'
assert qualification.observe_transfers({'lastSampleAt': 100}, {'history': []})['qualification'] == 'not-demonstrated'
print('PASS read-only explain, real planner trace, resource qualification observation')
