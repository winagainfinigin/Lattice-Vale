from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
core = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
relay = (ROOT / 'windows' / 'LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}

# v14.3.2 must not depend on Start-Process -PassThru for any exit-code-sensitive path.
for text, name in ((core, 'core installer'), (relay, 'native relay')):
    lowered = text.lower()
    assert 'start-process -filepath' not in lowered or '-passthru' not in lowered, name

# The bounded process paths must own a System.Diagnostics.Process directly.
for needle in (
    'New-Object System.Diagnostics.ProcessStartInfo',
    'New-Object System.Diagnostics.Process',
    '$process.StartInfo = $startInfo',
    '$process.Start()',
    '$process.WaitForExit($TimeoutSeconds * 1000)',
    '$exitCode = [int]$process.ExitCode',
):
    assert needle in core, needle

for needle in (
    'New-Object System.Diagnostics.ProcessStartInfo',
    'New-Object System.Diagnostics.Process',
    '$process.StartInfo = $startInfo',
    '$process.Start()',
    '$process.WaitForExit($TimeoutSeconds * 1000)',
    '$exitCode = [int]$process.ExitCode',
):
    assert needle in relay, needle

# Capture paths must drain stdout/stderr concurrently before waiting to avoid pipe deadlocks.
for text in (core, relay):
    assert '.StandardOutput.ReadToEndAsync()' in text
    assert '.StandardError.ReadToEndAsync()' in text

# Binary stdin staging and the interactive inherited-console path must remain intact.
assert '$inputStream.CopyTo($process.StandardInput.BaseStream)' in core
assert '$process.StandardInput.Close()' in core
assert '$startInfo.CreateNoWindow = $false' in core

# The WSL preflight itself must still fail closed on a genuine nonzero/timeout result.
assert "Invoke-NativeProcessCapture 'wsl.exe' @('--list', '--quiet')" in core
assert 'if (-not $listProbe.Success)' in core
assert "installed distributions could not be enumerated" in core

print('v14.3.2 native process exit-code fixtures: PASS')
