#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
detect=ps[ps.index('function Test-ManagedLatticeValeStackForUser'):ps.index('function Get-LatticeValeStackPathState')]
getopts=ps[ps.index('function Get-ExistingInstallOptions'):ps.index('function Get-OptionValue')]
for archive in ('installer-config.tar.gz','files.tar.gz'):
    assert archive in detect, f'managed detection must recognize {archive}'
    assert archive in getopts, f'options recovery must search {archive}'
assert "tar -tzf" in getopts, 'recovery must inspect archive membership before extraction'
assert 'install-options.json' in getopts
assert 'isinstance(d,dict)' in getopts, 'recovered JSON must be a top-level object'
assert "sort -nr" in getopts, 'backup candidates must be newest-first'
assert 'will NOT fall back to clean-install choices' in ps
print('V13.16.8 BACKUP RECOVERY FIXTURES: PASS')
