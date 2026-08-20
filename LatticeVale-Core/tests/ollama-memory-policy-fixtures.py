#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cs=(root/'stack/configure-stack.sh').read_text()
compose=(root/'stack/compose.yaml').read_text()
assert 'OLLAMA_CONTEXT_LENGTH=65536' not in cs
assert 'set_env .env OLLAMA_CONTEXT_LENGTH 65536' not in cs
assert 'choose_ollama_context_length' in cs
assert "printf '8192'" in cs and "printf '16384'" in cs and "printf '32768'" in cs and "printf '65536'" in cs
assert 'LATTICEVALE_OLLAMA_CONTEXT_AUTO' in cs
assert 'FOUNDRY_OLLAMA_CONTEXT_AUTO' in cs  # read/remove migration compatibility
assert 'OLLAMA_MAX_LOADED_MODELS=1' in cs
assert 'OLLAMA_NUM_PARALLEL=1' in cs
assert 'OLLAMA_KEEP_ALIVE=30s' in cs
assert 'docker compose stop hermes honcho-api honcho-deriver' in cs
assert 'docker compose restart ollama' in cs
assert "m['context_length']=context" in cs
assert 'local_context=' in cs
assert 'OLLAMA_MAX_LOADED_MODELS: ${OLLAMA_MAX_LOADED_MODELS:-1}' in compose
assert 'OLLAMA_NUM_PARALLEL: ${OLLAMA_NUM_PARALLEL:-1}' in compose
print('ollama memory policy fixtures: PASS')
