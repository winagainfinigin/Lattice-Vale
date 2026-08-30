#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
cs=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
bridge=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
ver=(root/'VERSION.txt').read_text().strip()
assert ver in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'}
# WSL networking changes must never interrupt active model/database work. v14.3.30
# resolves the one shared topology before bootstrap; older releases applied the Tailscale
# NAT mutation only after bootstrap.
bootstrap=ps.index("Write-Step 'Bootstrapping Docker and the selected LatticeVale stack inside Ubuntu'")
if ver in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'}:
    shared=ps.index('$sharedNativeTailscale')
    assert shared < bootstrap
    assert "Write-Step 'Applying WSL NAT networking for the Windows Tailscale bridge'" not in ps
    assert 'Set-WslGlobalNetworkingModeNat' not in ps
    if ver in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'}:
        assert 'Set-WslGlobalNetworkingModeValue' not in ps
        assert 'Resolve-LatticeValeNativeOllamaMirroredFallback' not in ps
else:
    apply=ps.index("Write-Step 'Applying WSL NAT networking for the Windows Tailscale bridge'")
    assert apply > bootstrap
    pre=ps[:bootstrap]
    assert "Set-WslGlobalNetworkingModeNat $wslNetworking.Path" not in pre
assert "Invoke-NativeProcessCapture 'wsl.exe' @('--shutdown') 30" in ps
assert 'Wait-LatticeValeWslResponsive' in ps
assert 'Invoke-LatticeValeWslInteractiveGuarded' in ps
assert 'MaxHeartbeatFailures = 6' in ps
assert 'WSL stopped responding during Linux setup' in ps
assert "'/usr/local/sbin/hermes-stack-start' @() 900" in ps
# The known indefinite Ollama/Docker paths must have outer timeouts.
assert '3600s docker compose exec -T ollama ollama pull' in cs
assert '30s docker compose exec -T ollama ollama list' in cs
assert '240s docker run --rm -i --network hermes-backend' in cs
assert 'docker compose exec -T ollama ollama stop "$model"' in cs
assert '3600s docker compose pull --ignore-buildable' in cs
# Bridge scheduled task may not invoke wsl.exe directly without a timeout wrapper.
assert 'function Invoke-WslBounded' in bridge
assert '@(& wsl.exe' not in bridge
print('runtime hang hardening fixtures: PASS')

# Low-memory Ollama policy: no global 64k default, single resident model, and repair
# must clear existing consumers before Honcho embedding verification.
compose=(root/'stack/compose.yaml').read_text(encoding='utf-8')
assert 'OLLAMA_CONTEXT_LENGTH: ${OLLAMA_CONTEXT_LENGTH:-8192}' in compose
assert 'OLLAMA_MAX_LOADED_MODELS: ${OLLAMA_MAX_LOADED_MODELS:-1}' in compose
assert 'OLLAMA_NUM_PARALLEL: ${OLLAMA_NUM_PARALLEL:-1}' in compose
assert 'OLLAMA_KEEP_ALIVE: ${OLLAMA_KEEP_ALIVE:-30s}' in compose
assert 'choose_ollama_context_length' in cs
assert 'LATTICEVALE_OLLAMA_CONTEXT_AUTO' in cs
assert 'FOUNDRY_OLLAMA_CONTEXT_AUTO' in cs  # read/remove migration compatibility
assert "docker compose stop hermes honcho-api honcho-deriver" in cs
assert ('Restarting Ollama before embedding verification' in cs or 'Restarting managed Ollama before embedding verification' in cs)

manage=(root/'stack/manage.sh').read_text(encoding='utf-8')
assert '3600s docker compose exec -T ollama ollama pull' in manage
assert '3600s docker compose pull --ignore-buildable' in manage
