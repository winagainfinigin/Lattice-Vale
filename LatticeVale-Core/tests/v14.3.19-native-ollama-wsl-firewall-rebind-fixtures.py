#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'}
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
relay=(ROOT/'windows/LatticeVale-WindowsNativeServiceRelay.ps1').read_text(encoding='ascii')

# A resumed/elevated installer must launch Ollama with the current persisted Windows
# setting, not a stale environment inherited before the user changed OLLAMA_HOST.
assert 'function Get-WindowsNativeOllamaHostForChildProcess' in ps
assert "foreach ($scopeName in @('User','Machine','Process'))" in ps
assert '$env:OLLAMA_HOST = $processHost' in ps

# Post-update stale app/server processes are cleared by process name after explicit user
# consent, and the normal app launch has a bounded documented CLI fallback.
assert 'function Stop-DetectedWindowsNativeOllamaProcesses' in ps
assert "Name='ollama.exe' OR Name='ollama app.exe'" in ps
assert "-ArgumentList @('serve')" in ps
assert 'Never run `ollama serve` alongside a' in ps
assert 'Wait-WindowsTcpPortReleased $port 12' in ps

# Do not treat a loopback API response as proof that OLLAMA_HOST=0.0.0.0 was applied.
assert '$requireNonLoopback' in ps
assert 'Test-WindowsNativeOllamaNonLoopbackListener $port' in ps

# NAT host access is scoped by exact endpoints and modern WSL Hyper-V firewall is handled
# without changing WSL's global default firewall policy.
assert 'function New-LatticeValeWslHyperVOutboundRule' in ps
assert "Direction Outbound -Action Allow -Enabled True -Profiles Any" in ps
assert '-RemoteAddresses $RemoteAddress -RemotePorts ([string]$RemotePort)' in ps
assert "LocalAddress=$hostAddress; RemoteAddress=$wslAddresses; LocalPort=$port" in ps
assert "RemoteAddress='LocalSubnet4'" not in ps[ps.index('function Enable-LatticeValeWindowsNativeOllamaDirectWslAccess'):ps.index('function Remove-LatticeValeWindowsNativeOllamaDirectWslAccess')]
assert '$firewallArgs.InterfaceAlias' not in ps
assert '$firewallArgs.Program' not in ps

# Preferred private Windows relay gets the same narrowly scoped Hyper-V allowance, so a
# machine that filters WSL traffic need not expose Ollama itself just to make the relay work.
assert 'Get-HyperVFirewallRuleName' in relay
assert 'New-NetFirewallHyperVRule' in relay
assert '-RemoteAddresses $GatewayIp -RemotePorts ([string][int]$service.listenPort)' in relay
assert 'LatticeValeNativeBridge-HyperV-' in ps
assert 'Remove-NetFirewallHyperVRule' in ps

# Historical mirrored-remediation builds clarified that a shell assignment could not change
# the host networking architecture. v14.3.41 removes the mirrored remediation entirely.
if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'}:
    assert 'Use mirrored WSL networking as the shared mode' not in ps
    assert 'Switch global WSL2 networkingMode to mirrored' not in ps
else:
    assert 'typing networkingMode=mirrored inside Ubuntu does not change WSL networking' in ps
print('v14.3.19 native Ollama WSL firewall/rebind fixtures: PASS')
