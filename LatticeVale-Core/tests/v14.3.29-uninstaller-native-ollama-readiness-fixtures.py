#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83'}, version
un=(ROOT/'Uninstall-LatticeVale.ps1').read_text(encoding='ascii')
cs=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
relay=(ROOT/'stack/native-ollama-relay.sh').read_text(encoding='utf-8')

# Uninstall discovery must avoid the multiline bash -lc blob that could fail silently.
assert 'function Get-WslPasswdEntries' in un
assert "Invoke-Wsl $Name 'root' 'getent' @('passwd')" in un
assert "Invoke-Wsl $Name 'root' '/usr/bin/test'" in un
assert "Invoke-Wsl $Name 'root' 'find'" in un
start=un.index('function Get-LatticeValeUsers')
end=un.index('function Assert-SelectedStackTarget', start)
discovery=un[start:end]
assert "'bash' @('-lc',$script)" not in discovery
assert 'if (-not $r.Success) { return @() }' not in discovery
assert 'nonstandard primary GID' in un

# A calculated Docker host-gateway URL is not considered ready until /api/version succeeds.
assert 'native_ollama_ready_base_url()' in cs
ready=cs[cs.index('native_ollama_ready_base_url()'):cs.index('ollama_openai_base_url()', cs.index('native_ollama_ready_base_url()'))]
assert './native-ollama-relay.sh start' in ready
assert "+'/api/version'" in ready
assert './native-ollama-relay.sh restart' in ready
assert 'tail -n 16 logs/native-ollama-relay.log' in ready

# All model-critical native operations use the health-checked endpoint.
for fn in ('ollama_model_present()','ensure_ollama_model()','verify_honcho_embedding_model()'):
    pos=cs.index(fn)
    block=cs[pos:pos+7000]
    assert 'native_ollama_ready_base_url' in block, fn
infra=cs[cs.index('stage_infrastructure()'):cs.index('stage_matrix_profiles()', cs.index('stage_infrastructure()'))]
assert 'native_base="$(native_ollama_ready_base_url)"' in infra
assert 'Could not establish the verified native Windows Ollama relay/API before model validation.' in infra
assert 'model validation will not misreport this as a missing model' in cs

# An alive-but-unhealthy supervisor/service is actively recovered rather than trusted.
assert 'existing relay supervisor pid=${supervisor} is alive but unhealthy; restarting supervisor' in relay
assert "systemd relay service is active but unhealthy; restarting it once" in relay

print('v14.3.29 uninstaller/native Ollama readiness fixtures: PASS')
