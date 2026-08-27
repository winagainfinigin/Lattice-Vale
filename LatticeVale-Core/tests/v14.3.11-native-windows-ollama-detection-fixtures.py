#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()
assert version in {'14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83'}, version
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')

# Installation discovery must not be synonymous with one API probe.
assert 'Installed = $false' in ps
assert 'ProcessRunning = $false' in ps
assert 'ApiReady = $false' in ps
assert "GetEnvironmentVariable('Path', $target)" in ps
assert "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*" in ps
assert "HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*" in ps
assert "Get-CimInstance Win32_Process" in ps
assert "ollama app.exe" in ps
assert "InstallLocation" in ps

# Official custom listener support: loopback OLLAMA_HOST is discovered and probed.
assert "GetEnvironmentVariable('OLLAMA_HOST', $target)" in ps
assert "0.0.0.0" in ps and "127.0.0.1" in ps
assert "::1" in ps
assert 'RelayTargetAddress' in ps and 'RelayTargetPort' in ps
assert 'targetAddress = $TargetAddress' in ps
assert 'targetPort = $TargetPort' in ps

# Installed-but-stopped copies must be visible and explicitly startable, never silently installed.
assert 'function Start-DetectedWindowsNativeOllama' in ps
assert 'function Resolve-WindowsNativeOllamaForQuestionnaire' in ps
assert 'Start the detected native Windows Ollama now and re-check its local API?' in ps
assert "@('serve')" in ps
assert ps.count('Resolve-WindowsNativeOllamaForQuestionnaire $windowsOllamaState') >= 2
assert 'does not install or update the Windows Ollama application' in ps

# Final bridge configuration must use the endpoint actually verified at install time.
assert 'Write-LatticeValeNativeOllamaBridgeConfig $DistroName $windowsOllamaBridgePort $nativeOllamaNow.RelayTargetAddress $nativeOllamaNow.RelayTargetPort' in ps

print('v14.3.11 native Windows Ollama discovery fixtures: PASS')
