#!/usr/bin/env python3
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()
assert version in {'14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}, version
ps = (ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
cfg = (ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (ROOT/'stack/manage.sh').read_text(encoding='utf-8')
compose = yaml.safe_load((ROOT/'stack/compose.yaml').read_text(encoding='utf-8'))

# Ollama-dependent setup must ask the runtime location directly instead of hiding it behind
# availability-dependent branching.
assert "Read-Menu 'Where should Ollama run?'" in ps
assert 'Use native Windows Ollama: $nativeStatus' in ps
assert 'LatticeVale-managed Ollama inside WSL/Docker' in ps
if version in {'14.3.12','14.3.13'}:
    assert 'UNAVAILABLE THIS RUN' in ps
else:
    assert 'INSTALLED, NOT READY' in ps
    assert 'API READY, RELAY UNAVAILABLE' in ps
assert 'No managed Ollama fallback was selected automatically' in ps
assert 'Selected native Windows Ollama at $($windowsOllamaState.Endpoint)' in ps
assert 'Selected LatticeVale-managed WSL/Docker Ollama' in ps

# Native mode must not activate, create new storage for, pull, or start managed Ollama.
assert 'managed_ollama_enabled && mkdir -p data/ollama' in cfg
prepare = cfg[cfg.index('stage_prepare_config()'):cfg.index('\nverify_prepare_config()')]
assert 'data/honcho-db data/honcho-redis data/ollama data/searxng-valkey' not in prepare
assert 'managed_ollama_enabled && profiles+=(local-ai)' in cfg
assert 'native Windows Ollama was selected but the managed local-ai Compose profile is active' in cfg
# Local Ollama is a Hermes model.base_url custom endpoint, not OLLAMA_BASE_URL (which
# upstream reserves for the Ollama Cloud provider). Cloned profiles still on the managed
# local model get their endpoint repaired without overwriting profiles using other providers.
assert 'PY_REPAIR_CLONED_LOCAL_OLLAMA' in cfg
assert "m.get('provider')=='custom' and m.get('default')==sys.argv[2]" in cfg
assert "m['base_url']=sys.argv[3]" in cfg
verify_profiles = cfg[cfg.index('verify_profiles()'):cfg.index('verify_matrix_profiles()')]
assert 'PY_VERIFY_CLONED_LOCAL_OLLAMA' in verify_profiles
assert 'OLLAMA_BASE_URL' not in verify_profiles
assert 'managed_ollama_enabled && echo ollama' in cfg
assert 'docker compose pull --ignore-buildable "${infrastructure_services[@]}"' in cfg

# Explicit updates are also service-scoped, so inactive-profile images cannot be pulled as
# unrelated side effects.
assert 'mapfile -t update_services < <(selected_service_names)' in manage
assert 'docker compose pull --ignore-buildable "${update_services[@]}"' in manage
assert 'docker compose pull --ignore-buildable\n' not in manage
assert 'if managed_ollama_enabled; then echo ollama; fi' in manage

ollama = compose['services']['ollama']
assert 'local-ai' in ollama.get('profiles', [])
print('v14.3.12 explicit Ollama backend fixtures: PASS')
