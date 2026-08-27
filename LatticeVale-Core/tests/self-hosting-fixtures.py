#!/usr/bin/env python3
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
ps1=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
compose_text=(ROOT/'stack/compose.yaml').read_text(encoding='utf-8')
configure=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
readme=(ROOT/'README.md').read_text(encoding='utf-8')
compose=yaml.safe_load(compose_text)
services=compose['services']

assert 'ollama' in services
ollama=services['ollama']
assert 'local-ai' in ollama.get('profiles',[])
assert str(ollama['environment']['OLLAMA_NO_CLOUD']) in ('1','True','true')
assert './data/ollama:/root/.ollama' in ollama.get('volumes',[])
assert not ollama.get('ports'), 'Ollama should remain Docker-network-local by default'

for svc in ('honcho-api','honcho-deriver'):
    assert './config/honcho/config.toml:/app/config.toml:ro' in services[svc].get('volumes',[])
    assert 'ollama' not in services[svc].get('depends_on',{}), 'Honcho must also work with the native Windows Ollama backend'
    assert any(str(x).startswith('windows.host:') for x in services[svc].get('extra_hosts',[]))

assert 'OpenAI API key for Honcho' not in configure
assert 'LLM_OPENAI_API_KEY ollama-local' in configure
assert 'OLLAMA_NO_CLOUD' in compose_text
assert 'ollama_openai_base_url' in configure and "f'base_url = {q(ollama_base)}'" in configure
assert 'verify_honcho_embedding_model' in configure
assert "'dimensions':1536" in configure
assert "base+'/embeddings'" in configure
assert 'VECTOR_DIMENSIONS = 1536' in configure
assert 'dimensions_mode = "always"' in configure
for section in (
    "add_model('deriver.model_config')",
    "add_model(f'dialectic.levels.{level}.model_config')",
    "add_model('summary.model_config')",
    "add_model('dream.deduction_model_config')",
    "add_model('dream.induction_model_config')",
):
    assert section in configure, section

assert 'Use Ollama as the default Hermes AI provider?' in ps1
assert 'LatticeVale-managed WSL/Docker Ollama can be installed automatically' in ps1
assert 'Native Windows Ollama can be detected while stopped, but it must be running before LatticeVale can use and link its local API' in ps1
assert 'native Windows Ollama is usable only after both its Windows-local API and safe WSL relay path are verified' in ps1
assert "Get-OptionValue $old 'hermesLocalAI' $true" in ps1
assert "Get-OptionValue $existingOptions 'hermesLocalAI' $false" in ps1, 'pre-v12 resume must preserve existing Hermes provider'
assert "m['provider']='custom'" in configure
assert "m['base_url']=base_url" in configure
assert "m['context_length']=context" in configure

# Pre-v12/partial Honcho migration must preserve any populated DB that cannot prove local embedding provenance.
assert 'honcho-db-pre-local-' in configure
assert 'honcho-redis-pre-local-' in configure
assert 'honcho-env-pre-local-' in configure
assert 'data/honcho-db/pgdata/PG_VERSION' in configure
assert 'honcho_db_populated' in configure and 'honcho_local_config' in configure
assert 'Existing Honcho data predates or cannot prove the v12 local embedding configuration.' in configure
assert 'mv data/honcho-db "backups/honcho-db-pre-local-$stamp"' in configure
assert "cfg.get('baseUrl')=='http://honcho-api:8000'" in configure, 'Hermes self-hosted Honcho route verifier missing'

# Deliberate external exceptions remain documented rather than pretending they are self-hosted.
assert 'Windows Tailscale' in readme and 'Ubuntu Pro' in readme and 'no longer offers or manages Ubuntu Pro for WSL' in readme
assert 'SearXNG itself is local' in readme or 'SearXNG + Valkey' in readme

print('SELF-HOSTING FIXTURES: PASS')
print('- Honcho inference and embeddings route to the selected managed/native Ollama backend')
print('- Ollama cloud features disabled and no host port exposed')
print('- fresh Hermes installs default to local Ollama; legacy resumes preserve provider')
print('- pre-v12/uncertain Honcho data receives backup-first embedding migration')
