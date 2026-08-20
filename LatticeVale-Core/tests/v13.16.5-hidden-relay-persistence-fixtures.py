from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
assert "'-WindowStyle','Hidden'" in ps, 'relay PowerShell must be launched hidden'
assert 'The native relay is intentionally long-running' in ps
assert "($tailscaleDashboard -or $tailscaleMatrix) -and -not $keepWslServicesRunning" in ps
ver=(root/'VERSION.txt').read_text().strip()
if ver in {'14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'}:
    assert 'LatticeVale will preserve that choice; remote endpoints may become unavailable when WSL terminates.' in ps
    assert '$keepWslServicesRunning = $true' not in ps[ps.index('# Remote Tailscale endpoints can become unavailable'):ps.index('$applyWslInstanceIdleTimeout')]
else:
    assert "$keepWslServicesRunning = $true" in ps
assert "instanceIdleTimeout=-1" in ps
assert 'sleep infinity' not in ps.lower()
print('v13.16.5 hidden relay + persistence fixtures: PASS')
