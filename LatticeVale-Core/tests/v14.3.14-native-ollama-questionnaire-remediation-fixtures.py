#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'}, version
ps1 = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')

# The questionnaire must distinguish API/runtime failure from relay-topology failure.
assert 'INSTALLED, NOT READY - native Windows Ollama must be running so its local API can be verified' in ps1
assert 'API READY, RELAY UNAVAILABLE - $relayReason' in ps1
assert "Opening Ollama again will not fix this relay condition" in ps1

# Choosing native is an active retry/remediation request, not a dead loop.
menu_pos = ps1.index("$backendChoice = Read-Menu 'Where should Ollama run?'")
choice_pos = ps1.index('if ($backendChoice -eq 1)', menu_pos)
retry_pos = ps1.index('$windowsOllamaState = Get-WindowsNativeOllamaState', choice_pos)
start_pos = ps1.index('$windowsOllamaState = Resolve-WindowsNativeOllamaForQuestionnaire $windowsOllamaState', retry_pos)
bridge_pos = ps1.index('$windowsNativeBridgeState = Get-LatticeValeNativeBridgeCapability $DistroName', start_pos)
assert choice_pos < retry_pos < start_pos < bridge_pos

# The ownership boundary remains explicit: no silent managed fallback.
assert 'No managed Ollama fallback was selected automatically.' in ps1
assert 'LatticeVale does not install or update the Windows Ollama application.' in ps1

# The high-level questionnaire note must tell users the runtime requirement before the menu.
assert 'Native Windows Ollama can be detected while stopped, but it must be running before LatticeVale can use and link its local API' in ps1

print('v14.3.14 native Ollama questionnaire remediation fixtures: PASS')
