#!/usr/bin/env python3
"""Decision fixtures for functional-first WSL prerequisite behavior."""

def decide(wsl_exe: bool, list_exit: int, distro_count: int, wsl_feature_state: str, vmp_state: str):
    # Optional-feature metadata is advisory because modern Store/MSI WSL2 can be
    # functional while legacy/inbox feature state is unusual. Real CLI enumeration
    # and later per-distro WSL2/launch probes are authoritative.
    if not wsl_exe:
        return False, 'missing-wsl'
    if list_exit != 0:
        return False, 'enumeration-failed'
    if distro_count == 0:
        return False, 'no-existing-distro'
    return True, 'enumerate-candidates'

cases=[
    ('modern WSL with existing distros',True,0,2,'Enabled','Enabled',True),
    ('legacy-compatible WSL with existing distro',True,0,1,'Enabled','Enabled',True),
    ('no wsl.exe',False,0,1,'Enabled','Enabled',False),
    ('legacy WSL optional feature disabled but enumeration works',True,0,1,'Disabled','Enabled',True),
    ('WSL enumeration failure',True,1,1,'Enabled','Enabled',False),
    ('fresh WSL with zero distros',True,0,0,'Enabled','Enabled',False),
    ('VMP metadata disabled but enumeration works',True,0,1,'Enabled','Disabled',True),
    ('feature states unavailable but enumeration works',True,0,1,'','',True),
]
for name,exe,lx,count,wsl_feature,vmp,expected in cases:
    got,reason=decide(exe,lx,count,wsl_feature,vmp)
    if got!=expected:
        raise SystemExit(f'FAIL: {name}: expected {expected}, got {got} ({reason})')
print('WSL PREFLIGHT FIXTURES: PASS')
for c in cases: print('-',c[0])
