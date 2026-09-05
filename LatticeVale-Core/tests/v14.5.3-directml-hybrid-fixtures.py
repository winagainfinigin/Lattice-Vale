#!/usr/bin/env python3
from pathlib import Path
import ast,sys
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'stack'))
from latticevale_arch import host_memory_budget  # noqa:E402
assert (ROOT/'VERSION.txt').read_text().strip() in {'14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
ps=(ROOT/'Install-LatticeVale.ps1').read_text(); boot=(ROOT/'linux/bootstrap.sh').read_text(); cfg=(ROOT/'stack/configure-stack.sh').read_text(); manage=(ROOT/'stack/manage.sh').read_text(); compose=(ROOT/'stack/compose.yaml').read_text(); audit=(ROOT/'stack/state-audit.py').read_text(); free=(ROOT/'stack/audit-free.py').read_text(); un=(ROOT/'Uninstall-LatticeVale.ps1').read_text(); req=(ROOT/'stack/directml-requirements.txt').read_text(); py=(ROOT/'stack/directml-gateway.py').read_text(); sh=(ROOT/'stack/directml-gateway.sh').read_text()
ast.parse(py); ast.parse(audit); ast.parse(free)
for f in ('directml-gateway.py','directml-gateway.sh','directml-requirements.txt'): assert (ROOT/'stack'/f).is_file()
assert "localTextBackend" in ps and "'ollama','directml'" in ps
assert 'PyTorch DirectML gateway (experimental' in ps
assert "Get-OptionValue $existingOptions 'localTextBackend' 'ollama'" in ps
assert 'Qwen/Qwen2.5-1.5B-Instruct' in ps and 'directmlPort' in ps
assert 'python3-venv libblas3 libomp5 liblapack3' in boot
assert 'latticevale-directml-gateway.service' in boot and 'directml-gateway.sh supervise' in boot
assert 'DIRECTML_HOST_RESERVE_MIB' in cfg and 'runtime-policy.py host-budget' in cfg
# DirectML host reserve scales from live WSL RAM; it must be positive, bounded,
# and container budget must grow monotonically across arbitrary host allocations.
prev=-1
for mem in (2057,3181,4783,7031,10009,14983,23819,40111,79301):
    b=host_memory_budget(mem,'cpu',True,True)
    assert b['reserveMiB'] + b['containerBudgetMiB'] == mem
    assert 0 < b['directmlHostReserveMiB'] <= b['reserveMiB']
    assert b['containerBudgetMiB'] >= prev
    prev=b['containerBudgetMiB']
assert 'http://directml.host:%s/v1' in cfg and 'local_text_openai_base_url' in cfg
assert 'embedding_base' in cfg and 'text_base' in cfg and 'VECTOR_DIMENSIONS = 1536' in cfg
assert compose.count('directml.host:host-gateway')==3
assert 'INFERENCE_LOCK = threading.Lock()' in py and 'IDLE_UNLOAD_SECONDS' in py and 'MAX_CONTEXT' in py
assert 'unload_model("inference failure before Ollama fallback")' in py and 'return ollama_chat(payload, error)' in py
assert 'trust_remote_code=False' in py and 'torch_dtype": TORCH.float16' in py and 'low_cpu_mem_usage": True' in py
assert 'torch==2.4.1' in req and 'torchvision==0.19.1' in req and 'torch-directml==0.2.5.dev240914' in req and 'accelerate==0.34.2' in req
assert 'control_directml_gateway start' in manage and 'control_directml_gateway restart' in manage and 'control_directml_gateway stop' in manage
assert 'c["directml"]' in audit and 'DirectML gateway with Ollama fallback' in audit
assert 'directml' in free.lower()
assert 'latticevale-directml-gateway.service' in un and 'directml-gateway.sh stop' in un
assert '# LatticeVale v14.6.0' in (REPO/'README.md').read_text()
assert '## 14.5.3 - 2026-09-02' in (REPO/'docs/CHANGELOG.md').read_text()
print('v14.5.3 DIRECTML HYBRID FIXTURES: PASS')
