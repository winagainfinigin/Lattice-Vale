#!/usr/bin/env python3
"""Verify the single executable compatibility policy used by PowerShell and Bash."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
values = {}
for raw in (root / 'compatibility.conf').read_text(encoding='utf-8').splitlines():
    line = raw.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    values[k.strip()] = v.strip().strip('"').strip("'")

required = {
    'SUPPORTED_UBUNTU_VERSIONS',
    'MIN_WINDOWS_BUILD',
    'MIN_HOST_PARTITION_TOTAL_GIB_EXCLUSIVE',
    'MIN_HOST_PARTITION_FREE_GIB',
    'MIN_MANAGED_REPAIR_FREE_GIB',
    'WSL_PROBE_TIMEOUT_SECONDS',
}
missing = required - values.keys()
assert not missing, f'missing compatibility values: {sorted(missing)}'
assert values['SUPPORTED_UBUNTU_VERSIONS'].split() == ['22.04', '24.04', '26.04']
assert int(values['MIN_WINDOWS_BUILD']) == 19041
assert int(values['MIN_HOST_PARTITION_TOTAL_GIB_EXCLUSIVE']) == 50
assert int(values['MIN_HOST_PARTITION_FREE_GIB']) == 50
assert int(values['MIN_MANAGED_REPAIR_FREE_GIB']) == 10
assert int(values['MIN_MANAGED_REPAIR_FREE_GIB']) <= int(values['MIN_HOST_PARTITION_FREE_GIB'])
assert 5 <= int(values['WSL_PROBE_TIMEOUT_SECONDS']) <= 120
print('COMPATIBILITY POLICY FIXTURES: PASS')
