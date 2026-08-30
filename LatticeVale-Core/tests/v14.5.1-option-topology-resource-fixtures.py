#!/usr/bin/env python3
"""v14.5.1 policy-v9 public option/topology adaptive-resource regression fixtures."""
from pathlib import Path
from itertools import product
import subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
assert (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip() == '14.5.1'
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (ROOT / 'stack/manage.sh').read_text(encoding='utf-8')
boot = (ROOT / 'linux/bootstrap.sh').read_text(encoding='utf-8')
audit = (ROOT / 'stack/state-audit.py').read_text(encoding='utf-8')

for marker in (
    'POLICY_VERSION=9',
    'resource_matrix_profile_gateways() {',
    'resource_kanban_concurrency() {',
    'resource_hermes_floor_mib() {',
    'MATRIX_PROFILE_GATEWAYS=%s',
    'KANBAN_CONCURRENCY=%s',
    'HERMES_MIN_MIB=%s',
    'topology_cpu_pressure=',
    'Hermes topology floor=',
):
    assert marker in cfg, marker

# Policy-v9 topology floor: preserve the real-world-proven common case, then scale
# for additional persistent Matrix profile gateways and high Kanban concurrency.
def hermes_floor(matrix_gateways: int, kanban: int) -> int:
    return min(4096, 1024 + max(0, matrix_gateways - 1) * 192 + max(0, kanban - 3) * 96)

assert hermes_floor(0, 1) == 1024
assert hermes_floor(1, 3) == 1024       # audited user's topology stays unchanged
assert hermes_floor(2, 3) == 1216
assert hermes_floor(4, 5) == 1792
assert hermes_floor(8, 3) == 2368
assert hermes_floor(8, 8) == 2848       # public maximum supported profile/concurrency topology

# CPU quota remains a ceiling. Ordinary topology keeps ~75%; heavier profile/Kanban
# topology may rise toward 100%, without reserving cores away from other services.
def hermes_cpu(cpus: int, matrix_gateways: int, kanban: int) -> int:
    base = min(cpus, max(1, (cpus * 3 + 3) // 4))
    pressure = max(0, matrix_gateways - 1) + max(0, kanban - 3)
    if pressure:
        base = min(cpus, base + (pressure + 2) // 3)
    return base

assert hermes_cpu(4, 1, 3) == 3
assert hermes_cpu(4, 8, 8) == 4
assert hermes_cpu(8, 1, 3) == 6
assert hermes_cpu(8, 4, 5) == 8
assert hermes_cpu(2, 8, 8) == 2

# Execute the real embedded memory planner for option combinations.
start = cfg.index('import sys\nbudget=int(sys.argv[1])', cfg.index("<<'PY_RESOURCE_PLAN'"))
end = cfg.index('\nPY_RESOURCE_PLAN', start)
planner = cfg[start:end]

def run_plan(budget, matrix, searxng, qmd, ollama, honcho, accel, floor, ollama_floor=None):
    if ollama_floor is None: ollama_floor = 5120 if accel == 'cpu' else 2304
    args = [str(budget)] + [('true' if x else 'false') for x in (matrix,searxng,qmd,ollama,honcho)] + [accel, str(floor), str(ollama_floor)]
    p = subprocess.run([sys.executable, '-c', planner, *args], text=True, capture_output=True, timeout=10)
    alloc = {}
    if p.returncode == 0:
        for line in p.stdout.splitlines():
            k,v=line.split('=',1); alloc[k]=int(v)
    return p, alloc

# Every optional container service is included iff selected. Honcho may use native
# Windows Ollama, so honcho=True with ollama=False is a valid WSL resource shape.
# Exercise all 16 optional service selections once; managed-Ollama CPU/GPU presence
# is covered separately below and by the dedicated adaptive-hardware fixture.
for matrix,searxng,qmd,honcho in product((False,True), repeat=4):
    floor = hermes_floor(1,3)
    p,alloc = run_plan(12288, matrix,searxng,qmd,False,honcho,'cpu',floor)
    assert p.returncode == 0, (matrix,searxng,qmd,honcho,p.stderr)
    expected={'hermes'}
    if matrix: expected |= {'synapse-db','synapse'}
    if searxng: expected |= {'searxng-valkey','searxng'}
    if qmd: expected |= {'qmd','qmd-indexer'}
    if honcho: expected |= {'honcho-db','honcho-redis','honcho-api','honcho-deriver'}
    assert set(alloc) == expected, (expected,alloc)
    assert sum(alloc.values()) <= 12288

for accel in ('cpu','nvidia'):
    for shape in ((False,False,False,False),(True,True,True,True)):
        matrix,searxng,qmd,honcho=shape
        p,alloc=run_plan(16384,matrix,searxng,qmd,True,honcho,accel,hermes_floor(1,3))
        assert p.returncode == 0, (accel,shape,p.stderr)
        assert 'ollama' in alloc and 'hermes' in alloc, (accel,shape,alloc)

# The audited full-stack/common topology remains the same under v9 before downloaded-model sizing adds any required Ollama floor.
p,common = run_plan(8952, True,True,True,True,True,'cpu', hermes_floor(1,3))
assert p.returncode == 0, p.stderr
assert common['hermes'] == 1040 and common['ollama'] == 5152 and common['honcho-api'] == 528, common

# The same ~9.7 GiB budget is intentionally rejected for the maximum 8-secondary-
# gateway / 8-worker topology rather than starving Hermes. A larger host fits it.
p,max_small = run_plan(8952, True,True,True,True,True,'cpu', hermes_floor(8,8))
assert p.returncode == 3 and not max_small and 'cannot safely fit' in p.stderr, p.stderr
p,max_large = run_plan(13108, True,True,True,True,True,'cpu', hermes_floor(8,8))
assert p.returncode == 0 and max_large['hermes'] >= 2848 and sum(max_large.values()) <= 13108, (p.stderr,max_large)

# A profile-heavy but otherwise minimal external-provider setup remains viable on a
# much smaller WSL VM because unused Matrix/search/QMD/Honcho/Ollama services are absent.
p,profile_only = run_plan(2868, False,False,False,False,False,'cpu', hermes_floor(8,8))
assert p.returncode == 0, p.stderr
assert profile_only.get('hermes', 0) >= 2848, (p.stderr, profile_only)
assert sum(profile_only.values()) <= 2868, (p.stderr, profile_only)

# State/start surfaces must treat topology as part of the adaptive fingerprint.
for text, markers in (
    (cfg, ('saved_matrix_gateways','saved_kanban_concurrency','saved_hermes_floor')),
    (manage, ('./configure-stack.sh --refresh-resource-policy','Adaptive resource fingerprint changed')),
    (audit, ('MATRIX_PROFILE_GATEWAYS','KANBAN_CONCURRENCY','HERMES_MIN_MIB','Hermes profile/Kanban topology')),
):
    for marker in markers: assert marker in text, marker

# The root startup helper heredoc must defer resource/topology probes until the
# generated helper RUNS. Escaped command substitutions are required because the
# outer bootstrap heredoc is intentionally unquoted to inject stack identity once.
for marker in (
    'resource_limits_enabled="\\$(python3 - "\\$stack_dir/install-options.json"',
    './configure-stack.sh --refresh-resource-policy',
    'policy v9 fingerprints already match',
):
    assert marker in boot, marker

# Explicitly disabling LatticeVale ceilings remains an intentional user choice; policy
# v9 must not silently re-enable them just because a topology is large.
assert '[[ "$(opt_bool containerResourceLimits)" == true ]] || return 0' in manage
assert "rm -f .latticevale-resource-state" in cfg

print('v14.5.1 OPTION/TOPOLOGY RESOURCE FIXTURES: PASS')
