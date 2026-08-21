#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
helper=(ROOT.parent/'tools'/'Repair-LatticeVale-WslHost.ps1').read_text(encoding='ascii')

if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6'}:
    # v14.3.41 supersedes the old mirrored fallback: installer runtime may consume an
    # already-working mirrored topology, but can no longer write or switch networkingMode.
    assert 'function Resolve-LatticeValeNativeOllamaMirroredFallback' not in ps
    assert 'function Set-WslGlobalNetworkingModeValue' not in ps
    assert 'function Restart-LatticeValeWslForNativeOllamaNetworking' not in ps
    assert 'Switch global WSL2 networkingMode to mirrored' not in ps
    assert 'Use mirrored WSL networking as the shared mode' not in ps
    assert 'Configure native Windows Ollama for direct WSL access as a final fallback?' in ps
    assert 'v14.3.41 host-safety rule: never change global WSL networking' in ps
    # Host recovery remains explicit, reversible, and outside normal installer runtime.
    assert 'Set-WslNetworkingModeNat' in helper
    assert 'ApplyNatFallback' in helper
    assert 'Applying backed-up NAT compatibility recovery before component repair' in helper
    assert helper.index("$initialNetworkingMode = Get-WslNetworkingModeFromConfig") < helper.index("dism.exe /Online /Cleanup-Image /RestoreHealth")
else:
    assert 'function Resolve-LatticeValeNativeOllamaMirroredFallback' in ps
    resolver=ps[ps.index('function Resolve-LatticeValeNativeOllamaDirectFallback'):ps.index('function Get-LatticeValeNativeBridgeCapability')]
    assert resolver.index('Resolve-LatticeValeNativeOllamaMirroredFallback') < resolver.index('Configure native Windows Ollama for direct WSL access as a final fallback?')
    assert 'Switch global WSL2 networkingMode to mirrored and re-check native Windows Ollama?' in ps
    assert 'Apply the existing global WSL mirrored-networking setting now and re-check native Ollama?' in ps
    assert '$useMirrored = Read-Choice $question $yesText $noText $false' in ps
    assert 'function Set-WslGlobalNetworkingModeValue' in ps
    assert 'function Restore-WslGlobalNetworkingModeChange' in ps

print('v14.3.20 native Ollama mirrored-fallback compatibility fixtures: PASS')
