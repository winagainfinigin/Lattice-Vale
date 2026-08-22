#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
relay=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82'}
# Parent installer resolves the WSL VM address while its own WSL context is known-good.
assert 'function Get-LatticeValeWslIpv4Candidates' in ps
assert "Invoke-WslDirectCapture $Name '' 'ip' @('-4','-o','addr','show','dev','eth0','scope','global')" in ps
assert "Invoke-WslDirectCapture $Name '' 'hostname' @('-I')" in ps
assert 'Resolve-LatticeValeReachableWslIpv4' in ps
assert 'Test-RemoteTcpEndpoint $ip $port 1500' in ps
assert '$bridgeSeedIp' in ps
# Persistent relay accepts the verified/cached target without needing WSL command execution first.
if (root/'VERSION.txt').read_text().strip() in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82'}:
    assert 'Test-RelayTargetForServices $seedTarget $services' in relay
    assert relay.index('Test-RelayTargetForServices $seedTarget $services') < relay.index('$chosenIp = Get-ReachableWslIp')
else:
    assert 'Test-WslIpForServices $seedIp $services' in relay
    assert relay.index('Test-WslIpForServices $seedIp $services') < relay.index('$chosenIp = Get-ReachableWslIp')
# Later refresh uses compatible WSL command forms and two IP sources.
assert 'function Invoke-WslDistroCommand' in relay
assert "@('--',$Command)" in relay and "@($Command)" in relay
assert "'ip' @('-4','-o','addr','show','dev','eth0','scope','global')" in relay
assert "'hostname' @('-I')" in relay
# Relay itself does not require an elevated runtime token.
assert '#Requires -RunAsAdministrator' not in relay
assert '-RunLevel Highest' in ps
print('v13.13.2 WSL IP seed fixtures: PASS')
