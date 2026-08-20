from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
relay=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'}
assert 'function Get-LatticeValeRelayPowerShellCandidates' in ps
assert 'Get-Command pwsh.exe' in ps
assert "WindowsPowerShell\\v1.0\\powershell.exe" in ps
assert 'function Select-LatticeValeRelayPowerShell' in ps
assert 'Get-LatticeValeRelayArguments $Paths $EnsureStackRunning -SelfTest' in ps
assert "-RunLevel Highest" in ps
assert '-WorkingDirectory $Paths.Directory' in ps
assert "Registered Windows-native relay task" in ps
assert 'PreserveArtifacts' in ps
assert 'Preserved failed relay script/config for diagnostics' in ps
assert '[switch]$SelfTest' in relay
assert 'SELFTEST PASS' in relay
assert 'Relay process entered under' in relay
print('v13.13.3 relay task engine fixtures: PASS')
