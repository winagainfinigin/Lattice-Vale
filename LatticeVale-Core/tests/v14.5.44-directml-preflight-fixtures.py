#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.5.44','14.5.45','14.5.46'}, version

# v14.5.44 must use a DirectML-specific preflight rather than the broader Ollama
# GPU prerequisite parser that produced false /dev/dxg negatives on a valid WSL2 stack.
assert 'function Test-DirectMLWslPath(' in ps
assert 'function Get-DirectMLWslPrerequisites(' in ps
select_start = ps.index('function Select-LatticeValeDirectMLGpu(')
select_end = ps.index('function Get-WindowsNativeOllamaState', select_start)
select = ps[select_start:select_end]
assert '$wslState = Get-DirectMLWslPrerequisites $Name $User' in select
assert 'Get-OllamaWslGpuPrerequisites' not in select

# The DXG check is a direct, read-only `test -e` and every normal-user miss/failure
# is retried as root before the installer concludes that the bridge is absent.
helper_start = ps.index('function Test-DirectMLWslPath(')
helper_end = ps.index('function Get-DirectMLWslPrerequisites(', helper_start)
helper = ps[helper_start:helper_end]
assert "Invoke-WslDirectCapture $Name $User 'test' @($TestFlag, $Path)" in helper
assert "Invoke-WslDirectCapture $Name 'root' 'test' @($TestFlag, $Path)" in helper
assert helper.index("$result.RootRetried = $true") < helper.index("$rootAttempt = Invoke-WslDirectCapture")
assert "$rootAttempt.ExitCode -eq 1" in helper

pre_start = ps.index('function Get-DirectMLWslPrerequisites(')
pre_end = ps.index('function Get-LatticeValeGpuVendor', pre_start)
pre = ps[pre_start:pre_end]
for path in (
    '/dev/dxg',
    '/usr/lib/wsl/lib/libd3d12.so',
    '/usr/lib/wsl/lib/libd3d12core.so',
    '/usr/lib/wsl/lib/libdxcore.so',
):
    assert path in pre
assert 'BridgeLibrariesReady' in pre and 'LibraryProbeSucceeded' in pre

# Existing repair installs get a real tensor execution signal when the isolated
# DirectML venv already exists; fresh installs are not rejected just because it does not.
assert '$linuxHome/hermes-stack/data/directml/venv/bin/python' in pre
assert 'import torch,torch_directml' in pre
assert 'torch_directml.device()' in pre
assert 'TensorProbeAvailable' in pre and 'TensorProbeSucceeded' in pre
assert 'absence is not an error and does not block selection' in pre

# User-facing diagnostics distinguish an inconclusive probe from a confirmed absence.
assert 'This is a probe failure, not proof that /dev/dxg is absent.' in select
assert 'was probed directly and /dev/dxg is not present' in select
assert 'DirectML WSL preflight: /dev/dxg=present' in select
assert 'one or more Windows DirectX bridge libraries are missing' in select
assert 'real tensor execution probe' in select

# AMD remains a first-class DirectML vendor. DirectML works across DirectX 12-capable
# AMD/Intel/NVIDIA hardware; this hotfix must not special-case the reporter's GPU model.
assert "@('amd','nvidia','intel','qualcomm')" in select

print('v14.5.44 DIRECTML PREFLIGHT FIXTURES: PASS')
print('- DirectML no longer reuses the Ollama GPU parser for /dev/dxg detection')
print('- direct user/root DXG probe + D3D12/DXCore bridge checks are required')
print('- existing DirectML venvs receive a real tensor execution probe')
print('- probe failure and confirmed bridge absence are separate states')
