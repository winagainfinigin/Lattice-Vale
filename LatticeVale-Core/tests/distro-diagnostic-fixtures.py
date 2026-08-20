#!/usr/bin/env python3
"""Regression model for the exact failure state reported during v10 testing."""

def classify(*, wsl2, launch_ok, ubuntu_version, supported, host_total_gb, host_free_gb, users, legacy=False):
    blockers=[]
    if not wsl2: blockers.append(('WSL', 'WSL2 required'))
    if not launch_ok: blockers.append(('UNLAUNCHABLE', 'distro could not launch'))
    if launch_ok and ubuntu_version not in supported: blockers.append(('UBUNTU', 'unsupported Ubuntu'))
    if host_total_gb <= 50: blockers.append(('STORAGE_TOTAL_LOW', 'host total too small'))
    if host_free_gb < 50: blockers.append(('STORAGE_FREE_LOW', 'host free too low'))
    if launch_ok and users == 0: blockers.append(('USER', 'no normal user'))
    codes=[x[0] for x in blockers]
    storage_only=bool(codes) and all(c.startswith('STORAGE_') for c in codes)
    if not blockers: result='ELIGIBLE'
    elif storage_only: result='BLOCKED BY STORAGE'
    elif 'UNLAUNCHABLE' in codes: result='UNLAUNCHABLE'
    else: result='INELIGIBLE'
    return {'result':result,'codes':codes,'legacy':legacy,'storage_only':storage_only}

supported={'22.04','24.04','26.04'}
real=classify(wsl2=True, launch_ok=True, ubuntu_version='24.04', supported=supported,
              host_total_gb=500, host_free_gb=31.2, users=1)
legacy=classify(wsl2=True, launch_ok=False, ubuntu_version='', supported=supported,
                host_total_gb=1000, host_free_gb=800, users=0, legacy=True)
assert real['result']=='BLOCKED BY STORAGE'
assert real['storage_only'] is True
assert real['codes']==['STORAGE_FREE_LOW']
assert legacy['result']=='UNLAUNCHABLE'
assert legacy['legacy'] is True
assert 'UBUNTU' not in legacy['codes'], 'unlaunchable distro must not be mislabeled unsupported Ubuntu'

# Critical UX regression: a valid Ubuntu distro blocked only by storage must explicitly
# say no new Ubuntu installation is needed, rather than instructing the user to reinstall it.
ps1=(__import__('pathlib').Path(__file__).resolve().parents[1]/'Install-LatticeVale.ps1').read_text()
assert 'No new Ubuntu installation is required.' in ps1
assert 'BLOCKED BY STORAGE' in ps1 and 'UNLAUNCHABLE' in ps1
print('DISTRO DIAGNOSTIC REGRESSION FIXTURES: PASS')
