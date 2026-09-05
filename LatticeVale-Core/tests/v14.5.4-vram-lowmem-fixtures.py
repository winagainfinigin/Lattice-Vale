#!/usr/bin/env python3
"""v14.5.4 DirectML VRAM admission + small-resource safety regressions under v14.6."""
from pathlib import Path
import importlib.util
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
assert (ROOT/'VERSION.txt').read_text().strip() in {'14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
sys.path.insert(0,str(ROOT/'stack'))
from latticevale_arch import host_memory_budget, service_memory_plan  # noqa:E402
cfg=(ROOT/'stack/configure-stack.sh').read_text(); py=(ROOT/'stack/directml-gateway.py').read_text(); req=(ROOT/'stack/directml-requirements.txt').read_text(); audit=(ROOT/'stack/state-audit.py').read_text()

for marker in ('VRAM_LIMIT_PCT','_directml_device_and_vram','_model_vram_plan','gpu_memory',
               'no trusted bounded memory-capacity source','low_cpu_mem_usage": True','EFFECTIVE_MAX_CONTEXT',
               'vram_budget_mib','estimated_model_vram_mib'):
    assert marker in py, marker
assert 'accelerate==0.34.2' in req
assert 'DIRECTML_VRAM_LIMIT_PCT=75' in cfg

# 14.6 replaces the historical low-memory tier with one adaptive canonical policy.
assert '[POLICY_VERSION]=12' in cfg
assert '[RESOURCE_POLICY_MODE]=adaptive' in cfg
assert 'LOW_MEMORY_PROFILE' not in cfg and 'mem_mib <= 12288' not in cfg
assert 'runtime-policy.py host-budget' in cfg and 'runtime-policy.py service-plan' in cfg
assert 'reserve_mib=$((reserve_mib+directml_reserve_mib))' not in cfg
assert 'OLLAMA_AUTO_KEEP_ALIVE' in cfg
assert 'validate_runtime_policy_state' in audit and 'validate_runtime_policy_document' in audit

# Small-resource safety is expressed by invariants, not an exact RAM topology.
for mem in (2059,3079,4201,5813,7993,11317,17123):
    b=host_memory_budget(mem,'cpu',True,True)
    assert b['reserveMiB']+b['containerBudgetMiB']==mem
    assert 0 < b['directmlHostReserveMiB'] <= b['reserveMiB']
# Dynamically locate full-stack viability for a representative hybrid model floor.
def try_plan(budget):
    try:
        return service_memory_plan(budget,matrix=True,searxng=True,qmd=True,ollama=True,honcho=True,
                                   hermes_floor=1024,ollama_floor=3072)
    except ValueError:
        return None
lo,hi=384,65536
while lo<hi:
    mid=(lo+hi)//2
    if try_plan(mid) is None: lo=mid+1
    else: hi=mid
threshold=lo
assert try_plan(threshold) is not None and try_plan(threshold-1) is None
for budget in (threshold,threshold+379,threshold+1781,threshold+6907):
    a=try_plan(budget); assert a and sum(a.values())<=budget
    assert a['hermes']>=1024 and a['ollama']>=3072 and a['honcho-api']>=384 and a['honcho-deriver']>=256

# DirectML adapter VRAM normalization accepts MiB-style and byte-style wrapper values.
spec=importlib.util.spec_from_file_location('lv_dml',ROOT/'stack/directml-gateway.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class FakeDML:
    def __init__(self,raw): self.raw=raw
    def device_count(self): return 1
    def device_name(self,idx): return 'AMD Radeon RX Test'
    def default_device(self): return 0
    def device(self,idx=0): return f'privateuseone:{idx}'
    def gpu_memory(self,idx=0): return self.raw
for raw in (12288,12288*1024*1024):
    result=mod._directml_device_and_vram(FakeDML(raw))
    dev,idx,vram,name=result[:4]
    assert idx==0 and vram==12288 and 'Radeon' in name,(raw,result)

# WSL torch-directml builds can execute tensors while exposing no usable gpu_memory().
# Canonical Windows/WSL hardware state must provide the bounded fallback instead of
# treating one missing runtime API as proof that the GPU is unusable.
mod.DECLARED_VRAM_MIB=12272
mod.DECLARED_VRAM_SOURCE='windows-dxdiag-text'
mod.DECLARED_VRAM_CONFIDENCE='high'
result=mod._directml_device_and_vram(FakeDML(0))
assert result[2]==12272 and result[4]=='canonical:windows-dxdiag-text:high',result

# Gateway admission remains fail-closed relative to actual adapter VRAM.
class T:
    def __init__(self,n,e=2): self.n=n; self.e=e
    def numel(self): return self.n
    def element_size(self): return self.e
class C:
    num_hidden_layers=28; hidden_size=1536; num_attention_heads=12; num_key_value_heads=2
class M:
    config=C()
    def parameters(self): return [T(1_500_000_000)]
    def buffers(self): return []
mod.VRAM_TOTAL_MIB=12288
w,est,ctx,budget,detail=mod._model_vram_plan(M())
assert 2800<=w<=3000 and budget==9216 and 1024<=ctx<=8192 and est<=budget,(w,est,ctx,budget,detail)
mod.VRAM_TOTAL_MIB=4096
try: mod._model_vram_plan(M())
except RuntimeError as exc: assert 'admission refused' in str(exc)
else: raise AssertionError('oversized model was admitted to a 4 GiB adapter')

readme=(REPO/'README.md').read_text(); release=(REPO/'docs/RELEASE.md').read_text(); changelog=(REPO/'docs/CHANGELOG.md').read_text()
assert readme.startswith('# LatticeVale v14.6.0') and 'VRAM' in readme
assert 'v14.6.0 current release' in release and '14.5.4' in changelog
print('v14.5.4 VRAM / ADAPTIVE SMALL-RESOURCE FIXTURES: PASS')
