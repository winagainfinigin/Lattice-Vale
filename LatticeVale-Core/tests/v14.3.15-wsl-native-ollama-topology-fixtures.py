#!/usr/bin/env python3
from pathlib import Path
import socket, subprocess, sys, tempfile, time, urllib.request

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
conf=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
relay_sh=(ROOT/'stack/native-ollama-relay.sh').read_text(encoding='utf-8')
relay_py=ROOT/'stack/native-ollama-relay.py'
compose=(ROOT/'stack/compose.yaml').read_text(encoding='utf-8')

# Current WSL topology is detected, but capability is proven functionally rather than assumed.
assert ("'wslinfo' @('--networking-mode')" in ps) if version in {'14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'} else ('wslinfo --networking-mode' in ps)
assert "'wsl-localhost-relay'" in ps and "'windows-gateway-relay'" in ps
assert "Test-WslHttpEndpointDirect $Name $targetAddress $targetPort '/api/version'" in ps
assert "Current WSL networking mode: $($state.NetworkingMode)" in ps
assert "$state.NetworkingMode -eq 'virtioproxy'" in ps
assert 'LatticeVale will not change it automatically for native Ollama' in ps

# Mirrored/local transport is persisted and consumed by every lifecycle surface.
for text in (conf, manage, boot):
    assert 'wsl-localhost-relay' in text
assert 'TRANSPORT=%s' in conf
assert 'probe_url "http://${target}:${tport}/api/version"' in relay_sh and 'TARGET_ADDRESS=%s' in conf and 'TARGET_PORT=%s' in conf
assert 'native-ollama-relay.sh start' in conf
assert 'native-ollama-relay.sh start' in manage
assert 'native-ollama-relay.sh start' in boot
assert 'WINDOWS_HOST_IP' in audit and 'ip -4 route show default' not in audit[audit.index('elif native_ollama and not args.offline:'):audit.index('ollama_state =', audit.index('elif native_ollama and not args.offline:'))]

# Container reachability stays on Docker host-gateway. The preferred transports do not
# introduce a wildcard Windows listener; the explicit fallback is separately scoped by firewall.
assert 'windows.host:${WINDOWS_HOST_IP:-127.0.0.1}' in compose
assert "docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}'" in relay_sh
assert '--listen-address 0.0.0.0' not in relay_sh
relay_text=relay_py.read_text(encoding='utf-8')
assert 'listen_ip.is_loopback or listen_ip.is_unspecified or listen_ip.is_link_local' in relay_text
assert 'not target_ip.is_loopback' in relay_text
assert '--allow-private-target' in relay_text
assert 'not target_ip.is_private' in relay_text
assert 'relay target must remain on IPv4 loopback unless the verified WSL-host fallback explicitly enables a private target' in relay_text

# Native Ollama + remote Tailscale share one centralized WSL networking policy.
if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}:
    assert 'shared-native-ollama-tailscale' in ps
    assert 'user-existing-mirrored' in ps
    assert 'Use mirrored WSL networking as the shared mode for native Windows Ollama and Tailscale remote access?' not in ps
    assert 'Resolve-LatticeValeNativeOllamaMirroredFallback' not in ps
    assert 'LatticeVale will not change global WSL networking' in ps
elif version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40'}:
    assert 'shared-native-ollama-tailscale' in ps
    assert 'Use mirrored WSL networking as the shared mode for native Windows Ollama and Tailscale remote access?' in ps
    assert "$wslNetworkingModeOwner = 'shared-native-ollama-tailscale'" in ps
    assert 'capability-first rather than mode-first' in ps
else:
    assert 'Applying that change would invalidate the native Ollama path that this run just verified.' in ps
    assert 'Cancelled the pending global WSL NAT change to preserve the verified native Windows Ollama localhost path.' in ps

# The relay implementation can bind a non-loopback local interface and forward to loopback.
def local_ipv4():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.2.1',9)); return s.getsockname()[0]
    finally: s.close()
ip=local_ipv4()
if not ip.startswith('127.'):
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); target_port=s.getsockname()[1]
    with socket.socket() as s:
        s.bind((ip,0)); relay_port=s.getsockname()[1]
    server=subprocess.Popen([sys.executable,'-m','http.server',str(target_port),'--bind','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    relay=subprocess.Popen([sys.executable,str(relay_py),'--listen-address',ip,'--listen-port',str(relay_port),'--target-address','127.0.0.1','--target-port',str(target_port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        ok=False
        for _ in range(30):
            try:
                with opener.open(f'http://{ip}:{relay_port}/',timeout=1) as r:
                    ok=(r.status==200)
                if ok: break
            except Exception: time.sleep(.1)
        assert ok, 'local relay did not forward to loopback test server'
    finally:
        relay.terminate(); server.terminate()
        relay.wait(timeout=5); server.wait(timeout=5)

print('v14.3.15 WSL/native Ollama topology fixtures: PASS')
