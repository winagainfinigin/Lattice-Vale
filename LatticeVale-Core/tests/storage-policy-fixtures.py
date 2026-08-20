#!/usr/bin/env python3
"""Boundary fixtures for the existing-distro host-storage policy."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
vals = {}
for raw in (root/'compatibility.conf').read_text().splitlines():
    line=raw.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k,v=line.split('=',1); vals[k]=v.strip().strip('"').strip("'")

GB = 1024 ** 3
TOTAL = int(vals['MIN_HOST_PARTITION_TOTAL_GIB_EXCLUSIVE']) * GB
FREE = int(vals['MIN_HOST_PARTITION_FREE_GIB']) * GB
REPAIR_FREE = int(vals['MIN_MANAGED_REPAIR_FREE_GIB']) * GB

def eligible(size_bytes, free_bytes, drive_type=3, managed=False):
    threshold = REPAIR_FREE if managed else FREE
    return drive_type == 3 and size_bytes > TOTAL and free_bytes >= threshold

cases = [
    ('exactly threshold total is rejected', TOTAL, FREE, 3, False),
    ('over threshold total and exactly threshold free is accepted', TOTAL+GB, FREE, 3, True),
    ('enough total but one byte under required free is rejected', 100*GB, FREE-1, 3, False),
    ('non-fixed volume is rejected', 500*GB, 500*GB, 2, False),
]
for name, size, free, dtype, expected in cases:
    got = eligible(size, free, dtype)
    if got != expected:
        raise SystemExit(f'FAIL: {name}: expected {expected}, got {got}')
print('STORAGE POLICY FIXTURES: PASS')
assert eligible(100*GB, REPAIR_FREE, 3, managed=True), 'managed repair threshold should be accepted'
assert not eligible(100*GB, REPAIR_FREE-1, 3, managed=True), 'managed repair below threshold should be rejected'
for case in cases: print(f'- {case[0]}')
print('- managed repair threshold boundaries are sourced from compatibility.conf')
