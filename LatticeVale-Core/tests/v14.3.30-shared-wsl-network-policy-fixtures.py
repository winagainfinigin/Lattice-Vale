#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'}, version
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
relay = (ROOT / 'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='ascii')
configure = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
audit = (ROOT / 'stack/state-audit.py').read_text(encoding='utf-8')
compose = (ROOT / 'stack/compose.yaml').read_text(encoding='utf-8')

# One canonical install-options policy coordinates native Ollama and Windows-host Tailscale.
assert 'wslNetworkingMode = $wslNetworkingModePolicy' in ps
assert 'wslNetworkingModeOwner = $wslNetworkingModeOwner' in ps
assert 'The existing native-Ollama path verified' not in ps or version != '14.3.41'
if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'}:
    assert "user-existing-mirrored" in ps
    assert 'v14.3.41 no longer owns or mutates networkingMode' in ps
    assert 'will not create, reapply, or require mirrored mode' in ps
    assert 'Use mirrored WSL networking as the shared mode for native Windows Ollama and Tailscale remote access?' not in ps
    assert 'Resolve-LatticeValeNativeOllamaMirroredFallback' not in ps
    assert 'Set-WslGlobalNetworkingModeValue' not in ps
    assert 'no global WSL networking change is required' in ps
else:
    assert "$wslNetworkingModeOwner = 'shared-native-ollama-tailscale'" in ps
    assert 'Use mirrored WSL networking as the shared mode for native Windows Ollama and Tailscale remote access?' in ps
    assert 'capability-first rather than mode-first' in ps
    assert 'The existing native-Ollama path verified' in ps
    assert '$sharedBridgeReady = ($windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)' in ps
    assert 'Resolve-LatticeValeNativeOllamaMirroredFallback $DistroName $ollamaForSharedMode $windowsNativeBridgeState $true' in ps
    assert 'LatticeVale will not switch global WSL networking automatically' in ps

# The existing Windows relay is reused; no second Tailscale/container transport is introduced.
assert 'tailscale/tailscale' not in compose
assert "tailscaleMode = if ($tailscale) { 'windows-host' } else { 'disabled' }" in ps
assert "targetMode = if ($normalizedMode -eq 'mirrored') { 'mirrored-localhost' } else { 'wsl-ip' }" in ps
assert "initialTarget = if ($targetMode -eq 'mirrored-localhost') { '127.0.0.1' }" in ps
assert 'lastTargetAddress=$initialTarget' in ps
assert 'schema=4' in ps

# Mirrored mode takes the stable localhost path; NAT remains dynamically discoverable.
assert 'function Get-ActiveWslNetworkingMode' in relay
assert "Invoke-WslDistroCommand $DistroName '' 'wslinfo' @('--networking-mode') 5" in relay
assert "Invoke-WslDistroCommand $DistroName @('wslinfo','--networking-mode') 5" not in relay
assert "if ($script:RelayTargetMode -eq 'mirrored-localhost')" in relay
assert "Test-RelayTargetForServices '127.0.0.1'" in relay
assert 'Find-ReachableWslIp $distro $services' in relay
assert 'Live WSL networking changed to mirrored; switching relay target policy to localhost.' in relay
assert 'switching relay target policy to WSL IPv4 discovery.' in relay
assert 'if (-not $EnsureDistroRunning -and -not (Test-WslDistroRunning $DistroName))' in relay
assert 'throw $_.Exception' in relay

# Relay self-test timeout must fit inside the parent process timeout.
assert "$relayWaitSeconds = if ($SelfTest) { '30' } else { '120' }" in ps
assert "Invoke-NativeProcessCapture $engine (Get-LatticeValeRelayArguments $Paths $EnsureStackRunning -SelfTest) 45" in ps

# Both Windows/WSL metadata surfaces copy the canonical policy for diagnostics/recovery.
assert 'WSL_NETWORKING_MODE=%s' in configure
assert 'WSL_NETWORKING_MODE_OWNER=%s' in configure
assert 'if [[ "$WSL_NETWORKING_MODE" != mirrored ]]; then' in configure
assert 'avoid unnecessarily exposing them on mirrored host/LAN interfaces' in configure
assert 'BRIDGE_TARGET_ADDRESS' in ps
assert 'WSL_NETWORKING_MODE_OWNER' in ps

# Read-only health reports the real dependency chain and a stale saved/live topology.
assert 'native Ollama/model dependency is not healthy' in audit
assert 'live WSL networking mode is {live_mode}, saved shared policy is {networking_mode}' in audit
assert ('shared native-Ollama/Tailscale networking policy must record a verified non-mirrored topology' in audit) if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'} else ('shared native-Ollama/Tailscale networking policy must record a verified NAT or mirrored topology' in audit)

print('v14.3.30 shared WSL networking policy fixtures: PASS')
