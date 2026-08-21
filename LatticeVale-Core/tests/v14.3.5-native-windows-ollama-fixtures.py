from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
relay = (ROOT / 'windows' / 'LatticeVale-WindowsNativeServiceRelay.ps1').read_text(encoding='utf-8')
conf = (ROOT / 'stack' / 'configure-stack.sh').read_text(encoding='utf-8')
manage = (ROOT / 'stack' / 'manage.sh').read_text(encoding='utf-8')
boot = (ROOT / 'linux' / 'bootstrap.sh').read_text(encoding='utf-8')
audit = (ROOT / 'stack' / 'state-audit.py').read_text(encoding='utf-8')
compose_text = (ROOT / 'stack' / 'compose.yaml').read_text(encoding='utf-8')
compose = yaml.safe_load(compose_text)
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}

# Native Windows Ollama is detection/consent based, not assumed from the Windows GPU.
assert 'function Get-WindowsNativeOllamaState' in ps

if version in {'14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}:
    assert "http://127.0.0.1:11434" in ps and "/api/version" in ps
else:
    assert "http://127.0.0.1:11434/api/version" in ps
assert 'function Get-LatticeValeNativeBridgeCapability' in ps
if version in {'14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}:
    assert 'temporary WSL-scoped TCP reachability probe' in ps and 'Test-WindowsHostIpv4FromWsl' in ps
else:
    assert 'Windows could not bind that address' in ps
if version in {'14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}:
    assert 'must be running so its local API can be verified' in ps
    assert 'API READY, RELAY UNAVAILABLE' in ps
elif version in {'14.3.11','14.3.12','14.3.13'}:
    assert 'did not verify both a Windows-local Ollama API and a safe WSL-only relay path' in ps
else:
    assert 'did not verify both an already-running Windows localhost API and a safe WSL-only relay path' in ps
assert 'LatticeVale does not install or update the Windows Ollama application' in ps
assert 'Detected native Windows Ollama' in ps
assert 'LatticeVale-managed Ollama inside WSL/Docker' in ps

# Private relay remains preferred. A direct-host fallback may change OLLAMA_HOST only after
# explicit consent and owns/rolls back its narrowly scoped firewall state.
assert 'LatticeVale did not need to change OLLAMA_HOST. Only an installer-owned WSL-scoped relay is configured.' in ps
assert (('Configure native Windows Ollama for direct WSL access as a final fallback?' in ps) if version in {'14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'} else ('Configure native Windows Ollama for direct WSL access as a fallback?' in ps))
assert "[Environment]::SetEnvironmentVariable('OLLAMA_HOST',$desiredHost,$scope)" in ps
if version in {'14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}:
    assert 'targetAddress = $TargetAddress' in ps and 'targetPort = $TargetPort' in ps
else:
    assert 'targetAddress = \'127.0.0.1\'' in ps and 'targetPort = 11434' in ps
assert '-LocalAddress $GatewayIp -RemoteAddress $WslIp -LocalPort' in relay
assert "throw 'Windows Firewall cmdlets are unavailable; the WSL-only native-service bridge cannot be safely exposed.'" in relay
assert '0.0.0.0' not in relay, 'native Windows relay must not bind all Windows interfaces'
assert '/dev/tcp/' in relay, 'pre-bootstrap relay probe must not assume Python/curl is already installed'

# Missing selected models are pulled through the official native Ollama API, so model storage stays native.
assert "base+'/api/pull'" in conf
assert "{'model':model,'stream':False}" in conf
assert 'They are not duplicated into WSL Ollama storage.' in ps
assert 'pull_ollama_model' in manage and "'/api/pull'" in manage

# Native backend disables the local Ollama Compose profile/container and routes consumers to windows.host.
assert 'managed_ollama_enabled && profiles+=(local-ai)' in conf
assert 'managed_ollama_enabled || { docker rm -f hermes-ollama' in conf
assert "printf 'http://windows.host:%s/v1'" in conf
for svc in ('hermes', 'honcho-api', 'honcho-deriver'):
    assert any(str(x).startswith('windows.host:') for x in compose['services'][svc].get('extra_hosts', [])), svc
for svc in ('honcho-api', 'honcho-deriver'):
    assert 'ollama' not in compose['services'][svc].get('depends_on', {}), svc

# WSL GPU toolkit mutation applies only to the managed WSL/Docker backend.
assert '"$ollama_backend" == managed' in boot
assert "backend not in ('managed','windows-native')" in boot

# Start/restart paths refresh the relay before consumers so WSL address changes are reconciled.
assert 'control_windows_native_services start; docker compose up -d --pull never --no-build' in manage
assert '.windows-native-info' in manage and '.windows-native-info' in boot
assert 'native_ollama' in audit and 'windows.host' in audit

print('v14.3.5 native Windows Ollama fixtures: PASS')
