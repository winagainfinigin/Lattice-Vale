#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
helper=(root.parent/'tools/Repair-LatticeVale-WslHost.ps1').read_text(encoding='utf-8')

# Functional WSL discovery must use STDOUT for successful structured output and
# reserve combined stdout/stderr for diagnostics only.
assert "$listText = $listProbe.StdOut.Trim()" in ps
assert "$detailText = Get-SafeDiagnosticExcerpt $listProbe.Text" in ps
assert "$kernel = $probe.StdOut.Trim()" in ps
wslver=ps[ps.index('function Get-DistroWslVersion([string]$Name) {'):ps.index('function Get-WindowsOptionalFeatureStateSafe')]
assert 'foreach ($line in ($probe.StdOut -split "`r?`n"))' in wslver
assert '$probe.Text -split' not in wslver
assert "$versionText = $versionProbe.StdOut.Trim()" in ps

# Optional Windows feature metadata remains advisory; the installer must not mutate
# Windows features as part of normal installation.
cap=ps[ps.index('function Get-WslCapabilities'):ps.index('function Get-DistroRegistrationInfo')]
assert "Get-WindowsOptionalFeatureStateSafe 'Microsoft-Windows-Subsystem-Linux'" in cap
assert "Get-WindowsOptionalFeatureStateSafe 'VirtualMachinePlatform'" in cap
assert 'Enable-WindowsOptionalFeature' not in cap
assert 'functional WSL/distro checks' in cap or 'Functional WSL CLI and distro-launch probes' in cap

# Repair helper is distro-neutral by default and refuses to guess when several are registered.
assert "[string]$DistroName = ''" in helper
assert 'function Get-RegisteredWslDistroNames' in helper
assert 'Auto-selected the only registered WSL distro' in helper
assert 'More than one WSL distro is registered' in helper
assert "Do not unregister '$DistroName'" in helper
assert 'Do not unregister Ubuntu-24.04' not in helper

# Custom local fixed storage may be a drive letter, mounted volume, or volume-GUID path.
assert 'Get-Volume -FilePath $expanded' in ps
assert 'volume-GUID paths' in ps
assert "if ($basePath -match '^\\\\\\\\\\?\\\\(?<drive>[A-Za-z]:\\\\.*)$')" in ps
assert 'resolvable local fixed Windows volume' in ps

# Stale LatticeVale bridge ownership is proven by exact script+config paths, never by port alone.
for marker in (
    'function Test-LatticeValeBridgeTaskOwned',
    'function Stop-LatticeValeOwnedBridgeProcesses',
    'function Prepare-LatticeValeBridgePortsForReconcile',
    '$hasScript', '$hasConfig',
    'Reclaimed installer-owned Windows bridge port',
):
    assert marker in ps, marker
owned=ps[ps.index('function Stop-LatticeValeOwnedBridgeProcesses'):ps.index('function Prepare-LatticeValeBridgePortsForReconcile')]
assert 'Stop-Process -Id' in owned
assert '$hasScript -and $hasConfig' in owned
assert 'Get-NetTCPConnection' not in owned  # never kill merely by listener ownership

# Stop verified old relay before allocation, then prefer the canonical port again.
main_cleanup=ps.index('[void](Prepare-LatticeValeBridgePortsForReconcile $DistroName @(19119,18008')
main_dashboard=ps.index("Resolve-LatticeValeWindowsBridgePort 'Dashboard' 19119")
main_matrix=ps.index("Resolve-LatticeValeWindowsBridgePort 'Matrix' 18008")
assert main_cleanup < main_dashboard < main_matrix
resolver=ps[ps.index('function Resolve-LatticeValeWindowsBridgePort'):ps.index('function Stop-LatticeValeBridgeTaskAndWait')]
assert '$candidates.Add($Preferred)' in resolver
assert '$candidates.Add($PriorPort)' in resolver
assert resolver.index('$candidates.Add($Preferred)') < resolver.index('$candidates.Add($PriorPort)')
assert 'after owned-state cleanup' in resolver
assert 'Unknown listeners are never stopped.' in resolver

# The supported-bundle boundary remains explicit rather than pretending unverified
# architectures/distros are safe.
assert "$nativeArch -ne 'X64'" in ps
assert "WSL$wslVersion detected; WSL2 is required" in ps
assert "if ($osRelease.Id -ne 'ubuntu')" in ps

print('V14.3.30 COMPATIBILITY + STALE BRIDGE PORT RECLAIM FIXTURES: PASS')
