#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'}
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
conf=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
relay_sh=(ROOT/'stack/native-ollama-relay.sh').read_text(encoding='utf-8')
relay_py=(ROOT/'stack/native-ollama-relay.py').read_text(encoding='utf-8')

# Direct Windows-host exposure is an explicit fallback, never the first transport.
assert 'function Resolve-LatticeValeNativeOllamaDirectFallback' in ps
assert ('Configure native Windows Ollama for direct WSL access as a final fallback?' in ps) if version in {'14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'} else ('Configure native Windows Ollama for direct WSL access as a fallback?' in ps)
cap=ps[ps.index('function Get-LatticeValeNativeBridgeCapability'):ps.index('function Get-LatticeValeNativeServiceTaskName')]
if version in {'14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'}:
    # v14.3.22 first trusts the real Ollama API if it is already reachable; the private
    # synthetic relay remains available when the application endpoint is not reachable.
    assert "$state.Transport = 'windows-gateway-relay'" in cap
    assert "$state.Transport = 'wsl-localhost-relay'" in cap
    assert "$state.Transport = 'wsl-host-relay'" in cap
    assert cap.index('First trust the application-level endpoint') < cap.index('temporary WSL-scoped TCP reachability probe')
else:
    assert cap.index("$state.Transport = 'windows-gateway-relay'") < cap.index("$state.Transport = 'wsl-localhost-relay'") < cap.index("$state.Transport = 'wsl-host-relay'")

# Ollama's supported bind variable is persisted. Standard tray installs use User scope;
# a genuinely detected service uses Machine scope. The process environment is also set
# for the app LatticeVale relaunches immediately.
assert '$desiredHost = "0.0.0.0:$port"' in ps
assert "$scopeName = if ($service) { 'Machine' } else { 'User' }" in ps
assert "[Environment]::SetEnvironmentVariable('OLLAMA_HOST',$desiredHost,$scope)" in ps
assert '$env:OLLAMA_HOST = $desiredHost' in ps
assert 'Send-LatticeValeEnvironmentChanged' in ps

# Browser CORS is unrelated to Hermes/Honcho's server-side HTTP path. Never wildcard it.
assert "SetEnvironmentVariable('OLLAMA_ORIGINS'" not in ps
assert 'OLLAMA_ORIGINS=*' in ps  # explanatory text explicitly says it is NOT set

# Normal Ollama is an app, not assumed to be a service. Custom service installs are handled.
assert 'function Get-WindowsNativeOllamaService' in ps
assert 'Restart-Service -Name $service.Name' in ps
assert "Name='ollama.exe' OR Name='ollama app.exe'" in ps
assert 'Stop-Process -Id ([int]$proc.ProcessId)' in ps
assert 'Start-Process ([string]$State.AppExecutable)' in ps
assert "-ArgumentList @('serve')" in ps

# Firewall is installer-owned and constrained to WSL-facing traffic rather than an
# unrestricted inbound TCP/11434 rule. v14.3.19 narrows this further to exact host/source
# addresses and adds a separate Hyper-V outbound rule when supported.
if version == '14.3.18':
    assert "RemoteAddress='LocalSubnet4'" in ps
    assert '$firewallArgs.InterfaceAlias=[string]$interface.InterfaceAlias' in ps
    assert 'else { $firewallArgs.LocalAddress=$hostAddress }' in ps
else:
    assert 'LocalAddress=$hostAddress; RemoteAddress=$wslAddresses; LocalPort=$port' in ps
    assert 'New-LatticeValeWslHyperVOutboundRule' in ps
assert "Profile='Any'" in ps and "Protocol='TCP'" in ps and 'LocalPort=$port' in ps
assert "Group='LatticeVale'" in ps

# The listener and actual WSL API endpoint must both verify before acceptance.
assert 'Test-WindowsNativeOllamaNonLoopbackListener $port' in ps
assert "Test-WslHttpEndpointDirect $Name $hostAddress $port '/api/version'" in ps
assert "Test-WslHttpEndpointDirect $DistroName $directHost ([int]$nativeOllamaNow.RelayTargetPort) '/api/version'" in ps

# Installer ownership/rollback preserves a pre-existing user or service setting and will
# not overwrite a later manual change.
assert 'previousHostWasSet=$originalPreviousWasSet' in ps
assert 'configuredHost=$desiredHost' in ps
assert "if ([string]$current -eq [string]$owned.configuredHost)" in ps
assert 'left the newer environment value untouched' in ps
assert 'Remove-LatticeValeWindowsNativeOllamaDirectWslAccess' in ps

# The stack gains a third transport. Containers still see only the WSL-local Docker
# host-gateway relay; that relay dynamically discovers the current NAT gateway.
for text in (ps,conf,manage,boot,audit,relay_sh):
    assert 'wsl-host-relay' in text
assert 'windows_host_gateway_ip()' in relay_sh
assert 'ip -4 route show default' in relay_sh
assert 'target_mode_args+=(--allow-private-target)' in relay_sh
assert '--allow-private-target' in relay_py
assert 'not target_ip.is_private' in relay_py
assert 'relay listen address must be a specific non-loopback IPv4 owned by the WSL host' in relay_py

# Do not write a potentially stale Windows NAT address into the Linux user's shell profile.
for text in (ps,conf,manage,boot,relay_sh):
    assert '>> ~/.bashrc' not in text and '>>~/.bashrc' not in text

print('v14.3.18 native Ollama direct WSL fallback fixtures: PASS')
