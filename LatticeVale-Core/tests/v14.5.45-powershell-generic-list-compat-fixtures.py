#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.5.45','14.5.46','14.5.47','14.6.0'}, version

# PowerShell 7.6 on affected Windows 11 builds can throw
# "Argument types do not match" when New-Object-created generic lists are later
# coerced through array-subexpression binding. LatticeVale must avoid that engine path
# repository-wide; users must never need a manual source edit.
unsafe = re.compile(r'New-Object\s+[\'\"]?System\.Collections\.Generic\.', re.I)
violations = []
for path in sorted(REPO.rglob('*.ps1')):
    text = path.read_text(encoding='ascii')
    if unsafe.search(text):
        violations.append(path.relative_to(REPO).as_posix())
assert not violations, f'unsafe New-Object generic collections remain: {violations}'

installer = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
start = installer.index('function Get-WindowsGpuInventory {')
end = installer.index('function Select-LatticeValeDirectMLGpu', start)
gpu = installer[start:end]
assert '$items = [System.Collections.Generic.List[object]]::new()' in gpu
assert ('return @($script:LatticeValeWindowsGpuInventoryCache)' in gpu and '$items.ToArray()' in gpu) if version in {'14.5.47','14.6.0'} else ('return $items.ToArray()' in gpu)
assert 'New-Object System.Collections.Generic.List[object]' not in gpu

# Other user-facing Windows paths are covered too, so the crash cannot simply move
# from GPU inventory to repair/reset/uninstall/relay code later in the workflow.
required = {
    'tools/Repair-LatticeVale-WslHost.ps1': '[System.Collections.Generic.List[string]]::new()',
    'tools/Reset-LatticeVale-CleanHost.ps1': '[System.Collections.Generic.List[object]]::new()',
    'LatticeVale-Core/Uninstall-LatticeVale.ps1': '[System.Collections.Generic.List[object]]::new()',
    'LatticeVale-Core/windows/LatticeVale-WslNativeRelay.ps1': '[System.Collections.Generic.List[string]]::new()',
    'LatticeVale-Core/windows/LatticeVale-WindowsNativeServiceRelay.ps1': '[System.Collections.Generic.List[string]]::new()',
}
for rel, needle in required.items():
    text = (REPO / rel).read_text(encoding='ascii')
    assert needle in text, f'{rel}: missing constructor-form generic collection'

# v14.5.44 DirectML preflight is inherited unchanged: this is a PowerShell
# compatibility hotfix after successful GPU-bridge detection, not a GPU-policy rewrite.
preflight = (ROOT / 'tests/v14.5.44-directml-preflight-fixtures.py').read_text(encoding='utf-8')
assert 'Get-DirectMLWslPrerequisites' in preflight
assert 'torch_directml.device()' in preflight

print('v14.5.45 POWERSHELL GENERIC-LIST COMPAT FIXTURES: PASS')
print('- no New-Object System.Collections.Generic collection constructors remain in PowerShell source')
print('- GPU inventory uses List[object]::new() and ToArray()')
print('- repair/reset/uninstall/relay paths use constructor-form generic collections')
print('- v14.5.44 DirectML preflight behavior remains inherited')
