from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}, version

py=(ROOT/'stack/native-ollama-relay.py').read_text(encoding='utf-8')
sh=(ROOT/'stack/native-ollama-relay.sh').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
win=(ROOT/'windows/LatticeVale-WindowsNativeServiceRelay.ps1').read_text(encoding='ascii')
tail=(ROOT/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='ascii')
un=(ROOT/'Uninstall-LatticeVale.ps1').read_text(encoding='ascii')
security=(ROOT.parent/'docs/SECURITY.md').read_text(encoding='utf-8')
release=(ROOT.parent/'docs/RELEASE.md').read_text(encoding='utf-8')
doc=(ROOT.parent/'docs/NATIVE-OLLAMA-INTEGRATION.md').read_text(encoding='utf-8')
matrix=(ROOT.parent/'docs/WINDOWS-INTEGRATION-TEST-MATRIX.md').read_text(encoding='utf-8')

# WSL-local relay: useful logs, bounded connections/timeouts, supervisor/topology refresh.
for marker in ('--max-connections', '--connect-timeout', '--idle-timeout', 'asyncio.Semaphore', 'log_limited', 'relay started listen='):
    assert marker in py, marker
for marker in ('supervise_relay', 'relay topology changed; rebuilding worker', 'relay health probe failed', 'owned_supervisor_pid', 'systemctl start "$service_name"'):
    assert marker in sh, marker
assert 'nohup bash "$PWD/native-ollama-relay.sh" supervise' in sh
assert 'nohup python3 "$relay_py"' in sh  # worker is supervised, not the only lifecycle owner

# Use systemd only when already active; never enable it through wsl.conf.
assert 'latticevale-native-ollama-relay.service' in boot
assert 'Restart=on-failure' in boot
assert '[[ -d /run/systemd/system ]]' in boot
assert 'systemd=true' not in boot
assert 'cat > /etc/wsl.conf' not in boot
assert 'tee /etc/wsl.conf' not in boot
assert 'systemctl disable --now latticevale-native-ollama-relay.service' in un

# Windows native relay refreshes topology/firewall without waking a stopped distro.
for marker in ('Test-WslDistroRunning', 'preserving current listeners without waking WSL', 'Relay topology refreshed:', 'Set-RelayFirewall $config $newGateway $newWslIp', 'StopAll()', 'DrainEvents()', 'SemaphoreSlim', 'Task.WhenAll(ab, ba)', 'SessionTimeoutMs = 7200000'):
    assert marker in win, marker
assert "@('--list','--running','--quiet')" in win
assert '-Profile Any' in win  # retained only with exact local/remote address + port scope
assert '-LocalAddress $GatewayIp -RemoteAddress $WslIp -LocalPort' in win

# Existing Tailscale/WSL relay gets the same connection/task hardening.
for marker in ('SemaphoreSlim(64, 64)', 'DrainEvents()', 'Task.WhenAll(ab, ba)', 'SessionTimeoutMs = 7200000', 'connection rejected: relay concurrency limit reached'):
    assert marker in tail, marker

# Security/testing boundary is explicit rather than claiming static fixtures are E2E Windows tests.
assert 'PowerShell `Add-Type` / AV-EDR visibility' in security
assert 'docs/WINDOWS-INTEGRATION-TEST-MATRIX.md' in release
assert 'optional and advanced' in doc
lower_matrix=matrix.lower()
for marker in ('sleep/wake', 'wsl --shutdown', '64 simultaneous relay connections', 'av/edr'):
    assert marker in lower_matrix, marker

print('v14.3.26 native relay stabilization fixtures: PASS')
