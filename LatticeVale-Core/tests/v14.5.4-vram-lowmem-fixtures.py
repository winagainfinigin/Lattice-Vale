#!/usr/bin/env python3
"""v14.5.4 DirectML VRAM admission + <=12 GiB WSL low-memory regression fixtures."""
from pathlib import Path
import importlib.util
import subprocess
import sys
sys.dont_write_bytecode = True

ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
assert (ROOT/'VERSION.txt').read_text().strip() in {'14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}
cfg=(ROOT/'stack/configure-stack.sh').read_text(); py=(ROOT/'stack/directml-gateway.py').read_text(); req=(ROOT/'stack/directml-requirements.txt').read_text(); audit=(ROOT/'stack/state-audit.py').read_text()

# DirectML no longer has unbounded managed VRAM admission.
for marker in (
    'VRAM_LIMIT_PCT', '_directml_device_and_vram', '_model_vram_plan',
    'gpu_memory', 'refusing unbounded GPU model admission',
    'low_cpu_mem_usage": True', 'EFFECTIVE_MAX_CONTEXT',
    'vram_budget_mib', 'estimated_model_vram_mib',
): assert marker in py, marker
assert 'accelerate==0.34.2' in req
assert 'DIRECTML_VRAM_LIMIT_PCT=75' in cfg

# Resource policy v11 removes the v14.5.3 additive host-reserve double count and
# introduces a tighter <=12 GiB WSL profile without weakening the 1 GiB Hermes floor.
for marker in ('POLICY_VERSION=11','[LOW_MEMORY_PROFILE]="$(if (( mem_mib <= 12288 ))','mem_mib <= 12288','directml_reserve_mib=1792'):
    assert marker in cfg, marker
assert 'reserve_mib=$((reserve_mib+directml_reserve_mib))' not in cfg
assert '(( reserve_mib < directml_reserve_mib )) && reserve_mib=$directml_reserve_mib' in cfg
assert "('honcho-api',4,384,1024)" in cfg
assert "('honcho-deriver',3,256,1024)" in cfg
assert 'OLLAMA_AUTO_KEEP_ALIVE' in cfg and "printf '0s'" in cfg
assert "printf 4096" in cfg
assert 'values.get("POLICY_VERSION") != "11"' in audit

# Current release identity/documentation must describe the new safety responsibility.
readme=(REPO/'README.md').read_text(); release=(REPO/'docs/RELEASE.md').read_text(); support=(REPO/'docs/SUPPORT.md').read_text(); changelog=(REPO/'docs/CHANGELOG.md').read_text()
assert readme.startswith(('# LatticeVale v14.5.42', '# LatticeVale v14.5.43', '# LatticeVale v14.5.44', '# LatticeVale v14.5.45', '# LatticeVale v14.5.46')) and 'VRAM admission' in readme and '16 GB' in readme
assert 'v14.5.46 current release' in release and 'v14.5.42 historical release gate' in release and 'v14.5.4-vram-lowmem-fixtures.py' in release
assert 'v14.5.4 DirectML / low-memory support note' in support
assert '## 14.5.4 - 2026-09-03' in changelog

# Execute the embedded planner. The same 6400 MiB container budget cannot fit the
# old normal minima with a 3072 MiB hybrid Ollama floor, but it fits policy-v11's
# low-memory profile while keeping Hermes at >=1024 MiB.
start=cfg.index('import sys\nbudget=int(sys.argv[1])', cfg.index("<<'PY_RESOURCE_PLAN'")); end=cfg.index('\nPY_RESOURCE_PLAN',start); planner=cfg[start:end]
def run(low):
    args=['6400','true','true','true','true','true','cpu','1024','3072','true' if low else 'false']
    return subprocess.run([sys.executable,'-c',planner,*args],text=True,capture_output=True,timeout=10)
old=run(False); assert old.returncode==3, (old.returncode,old.stdout,old.stderr)
low=run(True); assert low.returncode==0, low.stderr
alloc={k:int(v) for k,v in (line.split('=',1) for line in low.stdout.splitlines())}
assert alloc['hermes']>=1024 and alloc['ollama']>=3072 and sum(alloc.values())<=6400,alloc
assert alloc['honcho-api']>=384 and alloc['honcho-deriver']>=256,alloc

# 16 GB-class Windows hosts commonly expose about 8 GiB to WSL by default. With
# DirectML's 1536 MiB host-reserve floor, the container budget is 6656 MiB. The
# audited user's ~9.7 GiB WSL case yields an 8154 MiB container budget. Both must
# admit the full provisional hybrid topology before downloaded model artifacts are
# measured; post-download model sizing remains authoritative.
def run_budget(budget):
    args=[str(budget),'true','true','true','true','true','cpu','1024','3072','true']
    return subprocess.run([sys.executable,'-c',planner,*args],text=True,capture_output=True,timeout=10)
for budget in (6656,8154):
    r=run_budget(budget); assert r.returncode==0,(budget,r.stderr)
    a={k:int(v) for k,v in (line.split('=',1) for line in r.stdout.splitlines())}
    assert sum(a.values())<=budget and a['hermes']>=1024 and a['ollama']>=3072,(budget,a)

# Exercise DirectML adapter VRAM normalization for both the historical MiB-style
# API value and a byte-style wrapper value.
spec=importlib.util.spec_from_file_location('lv_dml',ROOT/'stack/directml-gateway.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class FakeDML:
    def __init__(self, raw): self.raw=raw
    def device_count(self): return 1
    def device_name(self, idx): return 'AMD Radeon RX Test'
    def default_device(self): return 0
    def device(self, idx=0): return f'privateuseone:{idx}'
    def gpu_memory(self, idx=0): return self.raw
for raw in (12288, 12288*1024*1024):
    dev,idx,vram,name=mod._directml_device_and_vram(FakeDML(raw))
    assert idx==0 and vram==12288 and 'Radeon' in name,(raw,dev,idx,vram,name)

# Exercise the gateway admission calculation without importing torch.
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

print('v14.5.4 VRAM / LOW-MEMORY FIXTURES: PASS')
