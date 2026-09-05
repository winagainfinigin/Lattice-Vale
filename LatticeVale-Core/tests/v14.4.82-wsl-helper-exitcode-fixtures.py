#!/usr/bin/env python3
"""Regression assertions for v14.4.82 WSL helper exit-code isolation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert VERSION in {'14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}, VERSION
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')

start = ps.index('function Invoke-LatticeValeWslHostLaunchRecoveryHelper')
end = ps.index('function Try-RecoverLatticeValeWslHostLaunch', start)
helper_wrapper = ps[start:end]

# The child helper's diagnostics must remain visible, but must not become success-stream
# return objects from this wrapper. The caller expects one scalar native exit code.
assert '& $powershellExe @helperArgs | Out-Host' in helper_wrapper
assert '$helperExitCode = [int]$LASTEXITCODE' in helper_wrapper
assert 'return $helperExitCode' in helper_wrapper
assert '& $powershellExe @helperArgs\n    return [int]$LASTEXITCODE' not in helper_wrapper

# The caller must still treat zero as success and immediately re-probe the distro.
assert '$exitCode = Invoke-LatticeValeWslHostLaunchRecoveryHelper $Name' in ps
assert 'if ($exitCode -eq 0) { return $true }' in ps
assert "Write-Step 'Rechecking Ubuntu WSL2 eligibility after host recovery'" in ps

# Storage policy is intentionally unchanged by this hotfix.
compat = (ROOT / 'compatibility.conf').read_text(encoding='ascii')
assert 'MIN_HOST_PARTITION_FREE_GIB=50' in compat
assert 'MIN_MANAGED_REPAIR_FREE_GIB=10' in compat

print('v14.4.82 WSL helper exit-code fixtures: PASS')
