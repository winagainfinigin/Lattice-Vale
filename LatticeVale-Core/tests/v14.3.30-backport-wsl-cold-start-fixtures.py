#!/usr/bin/env python3
"""Static regression fixtures for the 14.3.30 stability-backport WSL cold-start preflight."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')

assert "$coldStartRetryTimeout" in ps
assert "[math]::Max(45, ($probeTimeout * 3))" in ps
assert "cat' @('/etc/os-release') $coldStartRetryTimeout" in ps
assert "automatically terminate the distro" in ps
assert "$storageDeferred = $true" in ps
assert "Managed-repair eligibility (minimum $($compat.MinManagedRepairFreeGiB) GB) will be evaluated once the distro responds." in ps
assert "elseif ($storageDeferred) { 'DEFERRED' }" in ps

# Preserve the established repair floor rather than weakening fresh-install policy globally.
compat = (ROOT / 'compatibility.conf').read_text(encoding='utf-8')
assert 'MIN_HOST_PARTITION_FREE_GIB=50' in compat
assert 'MIN_MANAGED_REPAIR_FREE_GIB=10' in compat
assert 'WSL_PROBE_TIMEOUT_SECONDS=15' in compat

print('v14.3.30 BACKPORT WSL COLD-START FIXTURES: PASS')
