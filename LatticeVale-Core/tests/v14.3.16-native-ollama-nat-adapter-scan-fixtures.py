#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
assert (ROOT/'VERSION.txt').read_text(encoding='ascii').strip() in {'14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
relay=(ROOT/'windows/LatticeVale-WindowsNativeServiceRelay.ps1').read_text(encoding='ascii')
conf=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')

# Native Ollama installation discovery has a bounded folder fallback only.
assert "Get-ChildItem -LiteralPath $root -Directory -Filter 'Ollama*'" in ps
scanner=ps[ps.index('# Bounded fallback discovery:'):ps.index('# Discover custom installer locations', ps.index('# Bounded fallback discovery:'))]
assert '-Recurse' not in scanner
assert "Join-Path $env:LOCALAPPDATA 'Programs'" in scanner
assert "[Environment]::GetEnvironmentVariable('ProgramFiles(x86)')" in scanner
assert "'bin\\ollama.exe'" in scanner
assert 'Never recurse through user data' in scanner and 'arbitrary mounted volumes' in scanner

# NAT host discovery is route-first but falls back to a Windows WSL/Hyper-V adapter.
assert 'function Get-WindowsWslAdapterIpv4Candidates' in ps
assert 'Get-NetIPAddress -AddressFamily IPv4' in ps
assert "(?i)(WSL|Hyper-V|vEthernet|Virtual Ethernet)" in ps
assert 'Test-LatticeValeIpv4SubnetMatch' in ps
assert 'function Test-WindowsHostIpv4FromWsl' in ps
assert 'LatticeVale temporary WSL native-service probe' in ps
assert 'temporary WSL-scoped TCP reachability probe' in ps
assert 'Windows WSL/Hyper-V virtual adapter matched to the selected distro subnet' in ps

# The long-lived Windows relay independently retains the same adapter fallback.
assert 'Get-NetIPAddress -AddressFamily IPv4' in relay
assert 'Get-NetIPAddress -AddressFamily IPv4 -IPAddress $candidate' in relay
assert 'Test-Ipv4SubnetMatch' in relay
assert "(?i)(WSL|Hyper-V|vEthernet|Virtual Ethernet)" in relay
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
if version == '14.3.16':
    route_idx=relay.index("ip -4 route show default")
else:
    route_idx=relay.index("'ip' @('-4','route','show','default')")
adapter_idx=relay.index('Get-NetIPAddress -AddressFamily IPv4')
assert route_idx < adapter_idx

# Persist the verified host address so Linux lifecycle paths do not re-assume ip route.
assert 'schema = 19' in ps
assert 'windowsOllamaHostAddress' in ps
assert 'schema must be an integer from 1 through 19' in conf
assert 'windowsOllamaHostAddress' in conf
assert 'HOST_ADDRESS=%s' in conf
assert 'native_info_field HOST_ADDRESS' in manage
assert '.windows-native-host-ip' in relay and '.windows-native-host-ip' in manage and '.windows-native-host-ip' in boot
assert 'stackPath = $StackPath' in ps
assert 'native_host_address=' in boot

conf_fn=conf[conf.index('windows_host_ip() {'):conf.index('ollama_api_base_url()', conf.index('windows_host_ip() {'))]
manage_fn=manage[manage.index('windows_host_ip() {'):manage.index('native_ollama_base_url()', manage.index('windows_host_ip() {'))]
assert 'ip -4 route show default' not in conf_fn
assert 'ip -4 route show default' not in manage_fn
boot_gateway=boot[boot.index('windows-gateway-relay)'):boot.index(';;', boot.index('windows-gateway-relay)'))]
assert 'ip -4 route show default' not in boot_gateway
assert 'native_host_address' in boot_gateway

print('v14.3.16 native Ollama NAT adapter/folder scan fixtures: PASS')
