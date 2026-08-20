#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
launcher=(ROOT.parent/'installer/install.ps1').read_text(encoding='utf-8')
verifier=(ROOT.parent/'tools/ReleaseManifest.ps1').read_text(encoding='utf-8')
assert (ROOT/'VERSION.txt').read_text(encoding='utf-8').strip() in {'14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'}
assert '. $Verifier' in launcher
# StrictMode must remain inside verifier function scopes, not at dot-source scope.
lines=[line.strip() for line in verifier.splitlines() if line.strip() and not line.lstrip().startswith('#')]
assert lines[0].startswith('function Assert-LatticeValePortableReleaseRelativePath')
assert verifier.count('Set-StrictMode -Version 2.0') == 2
assert 'param([Parameter(Mandatory=$true)][string]$RelativePath)\n    Set-StrictMode -Version 2.0' in verifier
assert '[switch]$WriteEachFile\n    )\n    Set-StrictMode -Version 2.0' in verifier
# Core also pre-creates its lazy script cache so direct callers using StrictMode are safe.
init='$script:HermesCompatibility = $null'
first_read='if ($null -ne $script:HermesCompatibility)'
assert init in ps and first_read in ps
assert ps.index(init) < ps.index(first_read)
assert ps.count(init) == 1
print('v14.3.1 StrictMode startup fixtures: PASS')
