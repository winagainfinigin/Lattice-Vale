#!/usr/bin/env python3
from pathlib import Path
import ast,sys
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'stack'))
from latticevale_arch import host_memory_budget  # noqa:E402
assert (ROOT/'VERSION.txt').read_text().strip() in {'14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0','14.6.1','14.6.2','14.6.3','14.6.4','14.6.5','14.6.6','14.6.7','14.6.9','14.7.0'}
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
    if mem >= 10240:
        assert b['directmlHostReserveMiB'] >= 3072
    prev=b['containerBudgetMiB']
assert 'http://directml.host:%s/v1' in cfg and 'local_text_openai_base_url' in cfg
assert 'embedding_base' in cfg and 'text_base' in cfg and 'VECTOR_DIMENSIONS = 1536' in cfg
assert compose.count('directml.host:host-gateway')==3
assert 'INFERENCE_LOCK = threading.Lock()' in py and 'IDLE_UNLOAD_SECONDS' in py and 'MAX_CONTEXT' in py
assert 'with TORCH.no_grad():' in py and 'torch.inference_mode()' not in py and 'TORCH.inference_mode()' not in py
assert 'LATTICEVALE_DIRECTML_FALLBACK_POLICY' in py and 'FALLBACK_ENABLED' in py
assert 'disabled by fail-closed policy' in py and 'Ollama text fallback is disabled by fail-closed policy' in py
assert 'text_fallback_enabled()' in sh and 'refusing forced Ollama fallback marker because directmlFallbackPolicy=none' in sh
assert 'text_fallback_enabled() {' in cfg and 'directml_text_enabled && [[ "$(directml_fallback_policy)" != none ]]' in cfg
assert 'rm -f "$force_fallback_file"' in sh and 'text fallback is disabled' in sh
assert 'unload_model("inference failure before Ollama fallback")' in py and 'return ollama_chat(payload, error)' in py
assert 'trust_remote_code=False' in py and 'torch_dtype": TORCH.float16' in py and 'low_cpu_mem_usage": True' in py
assert 'def _install_transformers_directml_compat()' in py and 'qwen2-mask-where-v1' in py
assert 'torch.where(diagonal_attend_mask' in py and 'torch.where(padding_mask' in py
assert 'DirectML self-test HTTP request failed. Gateway diagnostics follow:' in sh and 'tail -n 120 "$log_file"' in sh
assert 'torch==2.4.1' in req and 'torchvision==0.19.1' in req and 'torch-directml==0.2.5.dev240914' in req and 'accelerate==0.34.2' in req
assert 'control_directml_gateway start' in manage and 'control_directml_gateway restart' in manage and 'control_directml_gateway stop' in manage
assert 'c["directml"]' in audit and 'fail-closed no-Ollama fallback' in audit and 'directml_fallback_policy' in audit
assert 'directml' in free.lower()
assert 'latticevale-directml-gateway.service' in un and 'directml-gateway.sh stop' in un
assert '# LatticeVale v14.7.0' in (REPO/'README.md').read_text(encoding='utf-8')
assert '## 14.5.3 - 2026-09-02' in (REPO/'docs/CHANGELOG.md').read_text(encoding='utf-8')
print('v14.5.3 DIRECTML HYBRID FIXTURES: PASS')

# Behavioral DirectML tests use an in-process HTTP server and stub tokenizer,
# not a GPU, model weights, live Hermes instance, or source-text-only greps.
import importlib.util
import json
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('directml_gateway', ROOT / 'stack/directml-gateway.py')
assert spec is not None and spec.loader is not None
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)

class StubTokens:
    shape = (1, 700)
    def to(self, device):
        raise AssertionError('A context-overflow prompt must never be dispatched to GPU')

class StubTokenizer:
    def apply_chat_template(self, messages, **kwargs): return 'generated prompt'
    def __call__(self, prompt, **kwargs):
        assert kwargs.get('truncation') is False
        return {'input_ids': StubTokens()}

def _unavailable_model():
    return object(), StubTokenizer(), 'mock-device'

with patch.object(gateway, '_load_model', _unavailable_model), \
     patch.object(gateway, 'EFFECTIVE_MAX_CONTEXT', 1024):
    try:
        gateway.routed_chat({'messages': [{'role': 'user', 'content': 'test'}], 'max_tokens': 512})
    except gateway.ContextLengthExceeded:
        pass
    else:
        raise AssertionError('Oversized DirectML prompt was neither rejected nor surfaced')

with patch.object(gateway, 'GATEWAY_BEARER_TOKEN', 'fixture-secret'), \
     patch.object(gateway, 'fallback_ready', return_value=(False, 'not-probed')), \
     patch.object(gateway, 'routed_chat', side_effect=gateway.ContextLengthExceeded('exceeds context')):
    server = gateway.BoundedGatewayServer(('127.0.0.1', 0), gateway.GatewayHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base = 'http://127.0.0.1:' + str(server.server_address[1])
    try:
        try:
            urllib.request.urlopen(base + '/v1/models', timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError('A protected model endpoint accepted unauthenticated access')
        request = urllib.request.Request(base + '/v1/models', headers={'Authorization': 'Bearer fixture-secret'})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
        try:
            urllib.request.urlopen(base + '/health', timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 503  # exempt from auth; backend not available in stub
        else:
            raise AssertionError('The mocked health path should report no healthy backend')
        request = urllib.request.Request(base + '/v1/chat/completions', method='POST',
            headers={'Authorization': 'Bearer fixture-secret', 'Content-Type': 'application/json'},
            data=b'{"messages":[{"role":"user","content":"hi"}]}')
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            error = json.loads(exc.read())['error']
            assert error['code'] == 'context_length_exceeded'
        else:
            raise AssertionError('Oversized prompt did not produce HTTP 400')
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

print('PASS DirectML over-context behavior, opt-in bearer authorization, and health exemption over HTTP')

# Exercise bounded server behavior with an occupied slot; do not rely on
# source-string checks or a real GPU/hanging client to trigger saturation.
import socket
with patch.object(gateway, 'MAX_HTTP_HANDLERS', 1):
    server = gateway.BoundedGatewayServer(('127.0.0.1', 0), gateway.GatewayHandler)
    assert server._request_slots.acquire(blocking=False)
    left, right = socket.socketpair()
    try:
        server.process_request(left, ('127.0.0.1', 7))
        right.settimeout(3)
        rejection = right.recv(512)
        assert b'503 Service Unavailable' in rejection
        assert b'Retry-After: 1' in rejection
    finally:
        right.close()
        server._request_slots.release()
        server.server_close()
print('PASS bounded handler saturation returns HTTP 503 without spawning a worker')
