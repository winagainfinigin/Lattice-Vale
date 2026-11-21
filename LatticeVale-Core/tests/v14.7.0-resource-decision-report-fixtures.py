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
