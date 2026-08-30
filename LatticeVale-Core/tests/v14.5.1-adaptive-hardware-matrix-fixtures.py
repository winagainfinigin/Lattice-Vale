#!/usr/bin/env python3
"""v14.5.1 policy-v9 CPU/RAM adaptation matrix regression fixtures."""
from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
assert (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip() == '14.5.1'
assert 'POLICY_VERSION=9' in cfg

# CPU policy is based on CPUs actually visible to WSL, never Windows host guesses.
def cpu_plan(cpus: int):
    assert cpus >= 1
    hermes = (cpus * 3 + 3) // 4
    hermes = min(cpus, max(1, hermes))
    heavy = cpus
    medium = max(1, (cpus + 1) // 2)
    light = max(1, (cpus + 3) // 4)
    return hermes, heavy, medium, light

expected = {
    1: (1, 1, 1, 1),
    2: (2, 2, 1, 1),
    3: (3, 3, 2, 1),
    4: (3, 4, 2, 1),
    6: (5, 6, 3, 2),
    8: (6, 8, 4, 2),
    16: (12, 16, 8, 4),
    32: (24, 32, 16, 8),
    64: (48, 64, 32, 16),
}
for cpus, want in expected.items():
    got = cpu_plan(cpus)
    assert got == want, (cpus, got, want)
    assert all(1 <= v <= cpus for v in got), (cpus, got)

for marker in (
    'hermes_cpu=$(((cpus*3+3)/4))',
    'heavy_cpu=$cpus',
    'medium_cpu=$(((cpus+1)/2))',
    'light_cpu=$(((cpus+3)/4))',
    'CPU_%s_MILLI=%s000',
    '{{.HostConfig.NanoCpus}}',
    'effective Compose CPU limit',
):
    assert marker in cfg, marker

start = cfg.index('import sys\nbudget=int(sys.argv[1])', cfg.index("<<'PY_RESOURCE_PLAN'"))
end = cfg.index('\nPY_RESOURCE_PLAN', start)
planner = cfg[start:end]

def reserve(mem_mib: int, ollama=True, accel='cpu'):
    if mem_mib <= 6144:
        pct = 30
    elif mem_mib <= 12288 and ollama and accel == 'cpu':
        pct = 10
    elif mem_mib <= 24576:
        pct = 20
    else:
        pct = 15
    reserve_mib = mem_mib * pct // 100
    reserve_mib = max(768, min(4096, reserve_mib))
    return reserve_mib, mem_mib - reserve_mib

def run_plan(mem_mib: int, matrix=True, searxng=True, qmd=True, ollama=True, honcho=True, accel='cpu', ollama_floor=None):
    reserve_mib, budget = reserve(mem_mib, ollama=ollama, accel=accel)
    if budget < 384:
        return 1, {}, reserve_mib, budget, 'budget too small'
    if ollama_floor is None: ollama_floor = 5120 if accel == 'cpu' else 2304
    args = [str(budget)] + ['true' if x else 'false' for x in (matrix,searxng,qmd,ollama,honcho)] + [accel, '1024', str(ollama_floor)]
    p = subprocess.run([sys.executable, '-c', planner, *args], text=True, capture_output=True, timeout=10)
    out = {}
    if p.returncode == 0:
        for line in p.stdout.splitlines():
            k,v = line.split('=',1); out[k] = int(v)
    return p.returncode, out, reserve_mib, budget, p.stderr

# Full CPU-backed managed stack: undersized systems are rejected instead of receiving
# an Ollama hard limit below the model-aware 5120 MiB representative floor.
for mem in (1536, 2048, 3072, 4096, 5120, 6144, 7168, 8192, 9216):
    rc, alloc, reserve_mib, budget, err = run_plan(mem)
    assert rc != 0 and not alloc, (mem, reserve_mib, budget, alloc, err)
    assert 'cannot safely fit' in err or budget < 384, (mem, err)

# The audited ~9.7 GiB host and larger systems fit the CPU-backed full stack with
# bounded aggregate ceilings and >=5120 MiB managed Ollama headroom.
for mem in (9946, 10240, 12288, 16384, 24576, 32768, 65536):
    rc, alloc, reserve_mib, budget, err = run_plan(mem)
    assert rc == 0, (mem, reserve_mib, budget, err)
    assert sum(alloc.values()) <= budget, (mem, budget, sum(alloc.values()), alloc)
    assert alloc['hermes'] >= 1024 and alloc['honcho-api'] >= 512 and alloc['ollama'] >= 5120, (mem, alloc)

# Non-CPU managed Ollama retains the less RAM-intensive protected-floor behavior;
# it does not inherit the CPU-only 4608 MiB viability requirement.
for mem in (8192, 9216, 12288):
    rc, alloc, reserve_mib, budget, err = run_plan(mem, accel='nvidia')
    assert rc == 0, (mem, reserve_mib, budget, err)
    assert alloc['ollama'] >= 2304 and sum(alloc.values()) <= budget, (mem, alloc)

# Feature-awareness: small systems can still use lighter selections when their minima fit.
rc, alloc, _, budget, err = run_plan(2048, matrix=False, searxng=False, qmd=False, ollama=False, honcho=False)
assert rc == 0 and alloc['hermes'] >= 1024 and sum(alloc.values()) <= budget, (alloc, err)
# CPU-backed Ollama + core requires its real 4.5 GiB floor, but an 8 GiB WSL VM
# with the lighter service set has enough post-reserve budget.
rc, alloc, _, budget, err = run_plan(6144, matrix=False, searxng=False, qmd=False, ollama=True, honcho=False)
assert rc != 0, (budget, alloc, err)
rc, alloc, _, budget, err = run_plan(8192, matrix=False, searxng=False, qmd=False, ollama=True, honcho=False)
assert rc == 0 and alloc['hermes'] >= 1024 and alloc['ollama'] >= 5120, (alloc, err)
# GPU-backed core + Ollama can still fit a 5 GiB WSL allocation.
rc, alloc, _, budget, err = run_plan(5120, matrix=False, searxng=False, qmd=False, ollama=True, honcho=False, accel='nvidia', ollama_floor=2304)
assert rc == 0 and alloc['hermes'] >= 1024 and alloc['ollama'] >= 2304, (alloc, err)

print('v14.5.1 ADAPTIVE HARDWARE MATRIX FIXTURES: PASS')
