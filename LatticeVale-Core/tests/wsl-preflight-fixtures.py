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

# V14.6.7: WSL account probe failures cannot mean 'no accounts'.
from pathlib import Path
CORE = Path(__file__).resolve().parents[1]
STACK = CORE / 'stack'
main = (CORE / 'Install-LatticeVale.ps1').read_text(encoding='utf-8-sig')
select = main.split('function Select-ExistingLinuxUser(', 1)[1].split('\nfunction ', 1)[0]
lookup = main.split('function Get-ExistingLinuxUsers(', 1)[1].split('\nfunction ', 1)[0]
configure = (STACK / 'configure-stack.sh').read_text(encoding='utf-8')
assert '$usersProbe = Get-ExistingLinuxUsers $Name -ReturnProbe' in select
assert 'if (-not $usersProbe.Success)' in select
assert 'Get-ExistingLinuxUsers $Name)' not in select
assert "throw \"Could not verify existing Ubuntu accounts" in select
assert '$attempt -le 2' in lookup
assert "Invoke-WslDirectCapture $Name 'root' 'getent' @('passwd')" in lookup
assert 'if (-not $probe.Success -or $detail)' in lookup
assert 'Start-Sleep -Milliseconds 350' in lookup
assert 'Get-SafeDiagnosticExcerpt $probe.Text' in lookup
assert 'Get-WindowsTailscaleServePortState' in main
assert 'python3 resource-burst-controller.py --reconcile-static --stack "$PWD"' in configure
assert configure.index('python3 resource-burst-controller.py --reconcile-static') < configure.index('verify_live_resource_policy_limits || {')

print('V14.6.7 WSL ACCOUNT PROBE CONTRACT: PASS')
