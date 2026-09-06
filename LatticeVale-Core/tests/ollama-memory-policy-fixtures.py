#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
cs=(root/'stack/configure-stack.sh').read_text()
compose=(root/'stack/compose.yaml').read_text()
runtime=(root/'stack/runtime-policy.py').read_text()
sys.path.insert(0,str(root/'stack'))
from latticevale_arch import ollama_runtime_settings, ram_context_recommendation  # noqa:E402
assert 'OLLAMA_CONTEXT_LENGTH=65536' not in cs
assert 'set_env .env OLLAMA_CONTEXT_LENGTH 65536' not in cs
assert 'choose_ollama_context_length' in cs
assert 'resource_ram_context_recommendation() {' in cs and 'runtime-policy.py context ram' in cs
assert 'runtime-policy.py ollama-runtime' in cs and "add_parser('ollama-runtime')" in runtime
assert 'LATTICEVALE_OLLAMA_CONTEXT_AUTO' in cs
assert 'FOUNDRY_OLLAMA_CONTEXT_AUTO' in cs  # read/remove migration compatibility
# Context grows monotonically from actual available memory and remains supported.
allowed={4096,8192,16384,32768,65536}; prev=0
for mem in (2051,4079,7193,11117,18301,29009,52021,95003):
    ctx=ram_context_recommendation(mem)
    assert ctx in allowed and ctx >= prev
    prev=ctx
# Runtime concurrency/model residency derives from live RAM/CPU/backend, never a fixed topology.
for accel in ('cpu','vulkan','nvidia','amd'):
    prev_parallel=0
    for mem,cpus in ((4099,1),(7199,3),(12011,5),(21001,9),(38003,17),(70001,31)):
        settings=ollama_runtime_settings(mem,cpus,accel,False)
        assert 1 <= settings['parallel'] <= 4
        assert 1 <= settings['maxLoadedModels'] <= 3
        assert settings['parallel'] >= prev_parallel
        assert settings['keepAlive'].endswith('s')
        prev_parallel=settings['parallel']
        hybrid=ollama_runtime_settings(mem,cpus,accel,True)
        assert hybrid['maxLoadedModels']==1 and hybrid['keepAlive']=='0s'
assert 'OLLAMA_MAX_LOADED_MODELS=$OLLAMA_AUTO_MAX_LOADED_MODELS' in cs
assert 'OLLAMA_NUM_PARALLEL=$OLLAMA_AUTO_NUM_PARALLEL' in cs
assert 'OLLAMA_KEEP_ALIVE=$OLLAMA_AUTO_KEEP_ALIVE' in cs
assert 'docker compose stop hermes honcho-api honcho-deriver' in cs
assert 'docker compose restart ollama' in cs
assert "m['context_length']=context" in cs
assert 'local_context=' in cs
assert 'OLLAMA_MAX_LOADED_MODELS: ${OLLAMA_MAX_LOADED_MODELS:-1}' in compose
assert 'OLLAMA_NUM_PARALLEL: ${OLLAMA_NUM_PARALLEL:-1}' in compose
assert 'OLLAMA_GPU_OVERHEAD: ${OLLAMA_GPU_OVERHEAD:-0}' in compose
print('ollama memory policy fixtures: PASS')
