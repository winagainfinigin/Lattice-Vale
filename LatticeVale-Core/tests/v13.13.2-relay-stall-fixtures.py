#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
relay=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83'}
# Healthy backends must be probed before the expensive recovery helper.
get=relay[relay.index('function Get-ReachableWslIp'):relay.index('function Write-RelayState')]
if (root/'VERSION.txt').read_text().strip() in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83'}:
    nat=get[get.index('$initialProbeSeconds'):]
    assert nat.index('Find-ReachableWslIp $DistroName $Services $initialProbeSeconds') < nat.index('Start-HermesStack $DistroName')
else:
    assert get.index('Find-ReachableWslIp $DistroName $Services $initialProbeSeconds') < get.index('Start-HermesStack $DistroName')
assert 'Initial WSL backend probe did not find all requested services; invoking installer-owned stack recovery.' in relay
# Installer-side wait is bounded and observable, not a silent 15-minute stall.
assert 'Invoke-LatticeValeBridgeRefresh $bridgePaths 120' in ps
assert ("$relayWaitSeconds = if ($SelfTest) { '30' } else { '120' }" in ps) if (root/'VERSION.txt').read_text().strip() in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83'} else ("'-WaitSeconds','120'" in ps)
assert 'Waiting for Windows-native WSL relay' in ps
assert 'task exited before its listeners became ready' in ps
assert 'Get-LatticeValeBridgeLogTail' in ps
# Installer seeds a directly tested WSL IP before scheduled-task startup.
assert 'Resolve-LatticeValeReachableWslIpv4 $DistroName $bridgeBackendPorts 20' in ps
assert 'Resolved and verified WSL IPv4' in ps
assert '$SeedWslIp' in ps and 'lastWslIp=$lastIp' in ps
# Fresh diagnostics cannot accidentally report an old manual relay log.
assert 'native-relay.previous.log' in ps
assert 'Installer preparing relay task' in ps
# Synapse rollback does not restart when public_baseurl is already correct.
assert "print('UNCHANGED')" in ps
assert "if ([string]$probe.Text -match '(?m)^UNCHANGED\\s*$')" in ps
assert 'seq 1 120' in ps
# Repair runs must stop the prior long-running relay before replacing config/script.
assert 'Stop-LatticeValeBridgeTaskAndWait' in ps
assert "throw \"Could not stop the prior installer-owned Windows WSL relay task" in ps
print('v13.13.2 relay stall fixtures: PASS')
