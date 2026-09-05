#!/usr/bin/env python3
"""v14.5.1-derived policy-v11 public option/topology adaptive-resource regression fixtures."""
from pathlib import Path
from itertools import product
import sys

ROOT = Path(__file__).resolve().parents[1]
assert (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip() in {'14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (ROOT / 'stack/manage.sh').read_text(encoding='utf-8')
boot = (ROOT / 'linux/bootstrap.sh').read_text(encoding='utf-8')
audit = (ROOT / 'stack/state-audit.py').read_text(encoding='utf-8')
sys.path.insert(0,str(ROOT/'stack'))
from latticevale_arch import cpu_quota_plan, hermes_floor_mib, service_memory_plan  # noqa:E402

for marker in (
    '[POLICY_VERSION]=12',
    'resource_matrix_profile_gateways() {',
    'resource_kanban_concurrency() {',
    'resource_hermes_floor_mib() {',
    '[MATRIX_PROFILE_GATEWAYS]="$matrix_profile_gateways"',
    '[KANBAN_CONCURRENCY]="$kanban_concurrency"',
    '[HERMES_MIN_MIB]="$hermes_floor_mib"',
    'HARDWARE_FINGERPRINT',
    'POLICY_FINGERPRINT',
    'runtime-policy.py cpu-plan',
    'runtime-policy.py service-plan',
    'Hermes topology floor=',
):
    assert marker in cfg, marker


# Canonical topology floor preserves the common case and scales for additional
# persistent Matrix profile gateways / Kanban concurrency.
hermes_floor=hermes_floor_mib
assert hermes_floor(0, 1) == 1024
assert hermes_floor(1, 3) == 1024
assert hermes_floor(2, 3) == 1216
assert hermes_floor(4, 5) == 1792
assert hermes_floor(8, 3) == 2368
assert hermes_floor(8, 8) == 2848

# CPU quota behavior is tested through the same canonical function used by generation
# and verification rather than a duplicated fixture formula.
for accel in ('cpu','vulkan','nvidia','amd'):
    previous=0
    for cpus in (1,2,4,7,13,29):
        base=cpu_quota_plan(cpus,1,3,accel)
        busy=cpu_quota_plan(cpus,8,8,accel)
        cap=cpus*1000
        assert all(250 <= value <= cap for value in base.values())
        assert all(250 <= value <= cap for value in busy.values())
        assert base['hermes'] >= previous
        assert busy['hermes'] >= base['hermes']
        previous=base['hermes']

# Execute the canonical memory planner for option combinations.
class PlanResult:
    def __init__(self, returncode:int, stderr:str=''):
        self.returncode=returncode; self.stderr=stderr

def run_plan(budget, matrix, searxng, qmd, ollama, honcho, accel, floor, ollama_floor=None):
    if ollama_floor is None: ollama_floor = 5120 if accel == 'cpu' else 2304
    try:
        alloc=service_memory_plan(
            budget, matrix=matrix, searxng=searxng, qmd=qmd, ollama=ollama, honcho=honcho,
            hermes_floor=floor, ollama_floor=ollama_floor,
        )
        return PlanResult(0),alloc
    except ValueError as exc:
        return PlanResult(3,str(exc)),{}

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

# Topology pressure changes the minimum dynamically; do not freeze a host-size threshold.
def first_fit(floor):
    lo,hi=384,131072
    while lo<hi:
        mid=(lo+hi)//2
        result,_=run_plan(mid,True,True,True,True,True,'cpu',floor)
        if result.returncode==0: hi=mid
        else: lo=mid+1
    return lo
common_min=first_fit(hermes_floor(1,3))
max_min=first_fit(hermes_floor(8,8))
assert max_min > common_min
p,common=run_plan(common_min+733,True,True,True,True,True,'cpu',hermes_floor(1,3))
assert p.returncode==0 and common['hermes']>=hermes_floor(1,3) and sum(common.values())<=common_min+733
p,max_large=run_plan(max_min+733,True,True,True,True,True,'cpu',hermes_floor(8,8))
assert p.returncode==0 and max_large['hermes']>=hermes_floor(8,8) and sum(max_large.values())<=max_min+733

# Profile-only topology needs only the live Hermes floor plus water-fill headroom.
profile_floor=hermes_floor(8,8)
p,profile_only=run_plan(profile_floor+113,False,False,False,False,False,'cpu',profile_floor)
assert p.returncode==0 and profile_only['hermes']>=profile_floor
assert sum(profile_only.values())<=profile_floor+113

# State/start surfaces must treat topology as part of the adaptive fingerprint.
for text, markers in (
    (cfg, ('runtime-policy.py verify','MATRIX_PROFILE_GATEWAYS','KANBAN_CONCURRENCY','HERMES_MIN_MIB')),
    (manage, ('./configure-stack.sh --refresh-resource-policy','Adaptive resource fingerprint changed')),
    (audit, ('canonical runtime policy validation failed','canonical architecture','runtime-policy.json')),
):
    for marker in markers: assert marker in text, marker

# The root startup helper heredoc must defer resource/topology probes until the
# generated helper RUNS. Escaped command substitutions are required because the
# outer bootstrap heredoc is intentionally unquoted to inject stack identity once.
for marker in (
    'resource_limits_enabled="\\$(python3 - "\\$stack_dir/install-options.json"',
    './configure-stack.sh --refresh-resource-policy',
    'policy v12 fingerprints already match',
):
    assert marker in boot, marker

# Explicitly disabling LatticeVale ceilings remains an intentional user choice; the current
# policy must not silently re-enable them just because a topology is large.
assert '[[ "$(opt_bool containerResourceLimits)" == true ]] || return 0' in manage
assert "rm -f .latticevale-resource-state" in cfg

print('v14.5.1 OPTION/TOPOLOGY RESOURCE FIXTURES: PASS')
