#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
assert (ROOT/'VERSION.txt').read_text(encoding='ascii').strip() in {'14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
relay=(ROOT/'windows/LatticeVale-WindowsNativeServiceRelay.ps1').read_text(encoding='ascii')

# Machine-readable WSL network discovery must cross wsl.exe as direct argv, not as
# nested bash/awk text. A normal WSL NAT route has the generic shape:
#   default via <windows-host-ip> dev <interface> ...
assert "Invoke-WslDirectCapture $Name '' 'ip' @('-4','route','show','default')" in ps
assert "Invoke-WslDirectCapture $Name '' 'ip' @('-4','-o','addr','show','scope','global')" in ps
assert "Invoke-WslDirectCapture $Name '' 'wslinfo' @('--networking-mode')" in ps
assert 'function Get-WslDefaultIpv4GatewayCandidates' in ps
assert "if ($tokens[$i] -ne 'via')" in ps
assert "if ($tokens[$i] -ne 'inet')" in ps

network_mode=ps[ps.index('function Get-WslNetworkingMode'):ps.index('function Test-WslHttpEndpointDirect')]
ipv4_slice=ps[ps.index('function Get-WslIpv4Candidates'):ps.index('function ConvertTo-LatticeValeIpv4UInt32')]
assert "'bash' @('-lc'" not in network_mode
assert "'bash' @('-lc'" not in ipv4_slice
assert "awk 'NR==1 {print $3; exit}'" not in ipv4_slice

# The scheduled Windows relay must independently use the same direct route query so
# a later WSL restart does not reintroduce the original parsing failure.
assert "Invoke-WslDistro $DistroName '' 'ip' @('-4','route','show','default')" in relay
relay_route=relay[relay.index('function Get-WslDefaultIpv4GatewayCandidates'):relay.index('function Get-WindowsHostIpv4FromWsl')]
assert "'bash' @('-lc'" not in relay_route
assert "awk 'NR==1 {print $3; exit}'" not in relay_route

# Windows command-line quoting in the relay uses the same backslash handling as the
# core native-process helper; a char is compared by code point, not to a two-char '\\\\'.
quote_fn=relay[relay.index('function ConvertTo-WindowsProcessArgument'):relay.index('function Invoke-WslBounded')]
assert 'if ([int]$ch -eq 92)' in quote_fn
assert "if ($ch -eq '\\\\')" not in quote_fn

# No machine-specific addresses or adapter names are hard-coded into the runtime.
for forbidden in ('172.31.240.1','172.31.241.50','192.168.250.25','ExampleEthernet'):
    assert forbidden not in ps
    assert forbidden not in relay

print('v14.3.17 direct WSL network discovery fixtures: PASS')
