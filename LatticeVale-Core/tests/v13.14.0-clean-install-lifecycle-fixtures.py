#!/usr/bin/env python3
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'}
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
boot=(root/'linux/bootstrap.sh').read_text(encoding='utf-8')
relay=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
manage=(root/'stack/manage.sh').read_text(encoding='utf-8')

# Reproduce the exact helper-generation heredoc with root's HOME set. The generated
# helper must retain the configured stack directory, never /root/hermes-stack.
start=boot.index("printf -v stack_user_q '%q' \"$linux_user\"")
end=boot.index("\nEOF", start)+len("\nEOF")
block=boot[start:end]
with tempfile.TemporaryDirectory() as td:
    helper_path=Path(td)/'hermes-stack-start'
    block=block.replace('/usr/local/sbin/hermes-stack-start', str(helper_path))
    script="""set -Eeuo pipefail
HOME=/root
linux_user=testuser
user_home=/home/testuser
stack_dir=/home/testuser/hermes-stack
""" + block + '\n'
    run=subprocess.run(['bash','-c',script],capture_output=True,text=True)
    assert run.returncode==0, run.stderr
    generated=helper_path.read_text(encoding='utf-8')
assert 'stack_user=testuser' in generated
assert 'stack_home=/home/testuser' in generated
assert 'stack_dir=/home/testuser/hermes-stack' in generated
assert 'bash -c \'cd "$1" && timeout --foreground --kill-after=10s 240s docker compose up -d --pull never --no-build\' bash "$stack_dir"' in generated
assert '/root/hermes-stack' not in generated
assert 'cd "$HOME/hermes-stack"' not in generated

# WSL service lifetime: use the distro/instance setting introduced in Store WSL 2.5.4,
# do not conflate it with the VM-level vmIdleTimeout, and validate across the observed
# >60 second failure window.
for text in (
    "[version]'2.5.4'",
    'instanceIdleTimeout=-1',
    'function Set-WslGlobalInstanceIdleTimeoutDisabled',
    'function Test-LatticeValeWslPersistence',
    'Test-LatticeValeWslPersistence $DistroName 75',
    'keepWslServicesRunning = $keepWslServicesRunning',
): assert text in ps, text
assert 'vmIdleTimeout=-1' not in ps
assert "Get-OptionValue $old 'autoStart' $false" in ps
assert "Get-OptionValue $existingOptions 'autoStart' $false" in ps
assert "$existingOptions.PSObject.Properties['keepWslServicesRunning']" in ps

# The relay may start independently at Windows logon, but it must remain passive:
# no WSL wake/recovery unless full stack auto-start was explicitly selected.
assert 'Register-LatticeValeBridgeRefreshTask $bridgePaths $true $autoStart' in ps
assert "if ($StartAtLogon) {" in ps
assert 'Register-ScheduledTask -TaskName $Paths.TaskName -Action $action -Trigger $atLogon -Principal $principal -Settings $settings -Force' in ps
assert "if ($EnsureStackRunning) { $relayArgs += '-EnsureDistroRunning' }" in ps
assert "if (-not $EnsureDistroRunning -and -not (Test-WslDistroRunning $DistroName)) { return '' }" in relay
assert 'Starting relay listeners without a live WSL target' in relay
assert 'passive relay is waiting for the user to start Hermes' in relay
assert ('if (Test-RelayTargetForServices $currentIp $services)' in relay) if (root/'VERSION.txt').read_text().strip() in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'} else ('if (Test-WslIpForServices $currentIp $services)' in relay)
assert 'control_windows_bridge start' in manage
assert 'control_windows_bridge stop' in manage
assert 'BRIDGE_AUTOSTART=' in ps

print('v13.15.0 clean-install/lifecycle fixtures: PASS')
