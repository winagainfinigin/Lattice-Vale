#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
compose=(root/'stack/compose.yaml').read_text(encoding='utf-8')
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
helper=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')

assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
assert 'tailscale/tailscale' not in compose
assert '${DASHBOARD_HOST_BIND:-127.0.0.1}:${DASHBOARD_HOST_PORT:-9119}:9119' in compose
assert '${MATRIX_HOST_BIND:-127.0.0.1}:${MATRIX_HOST_PORT:-8008}:8008' in compose
assert '[[ "$(opt_bool tailscaleDashboard)" == true ]] && DASHBOARD_HOST_BIND=0.0.0.0' in cfg
assert '[[ "$(opt_bool tailscaleMatrix)" == true ]] && MATRIX_HOST_BIND=0.0.0.0' in cfg
for key in ('dashboardBridgePort','matrixBridgePort'):
    assert key in ps and key in cfg
for text in (
    'LatticeVale-WslNativeRelay.ps1',
    "transport='windows-native-tcp-relay'",
    'Resolve-LatticeValeWindowsBridgePort',
    'Write-LatticeValeBridgeConfig',
    'Register-LatticeValeBridgeRefreshTask',
    "Invoke-NativeProcessCapture 'wsl.exe' @('--shutdown') 30",
    'Set-SynapsePublicBaseUrl',
    'DASHBOARD_BRIDGE_PORT',
    'MATRIX_BRIDGE_PORT',
    'Test-HttpEndpointNoProxy',
    'Remove-LegacyHermesManualRelay',
):
    assert text in ps, text
version=(root/'VERSION.txt').read_text().strip()
assert ('shared-native-ollama-tailscale' in ps and 'user-existing-mirrored' in ps and 'Use mirrored WSL networking as the shared mode' not in ps) if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'} else (('shared-native-ollama-tailscale' in ps and 'mirrored-localhost' in ps) if version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40'} else ('networkingMode=nat' in ps))
for text in (
    'new TcpListener(IPAddress.Loopback, listenPort)',
    'TargetAddress',
    'Get-ReachableWslIp',
    'EnsureDistroRunning',
    "Invoke-WslDistroCommand $DistroName '' 'true' @() 30",
    "Invoke-WslDistroCommand $DistroName 'root' '/usr/local/sbin/hermes-stack-start' @() 900",
    '[ValidateRange(1, 900)]',
    'var ignored = HandleClient(client, targetPort);',
):
    assert text in helper, text
# Primary v13.13+ transport may not create/set portproxy. Installer keeps only
# narrowly-proven v13.12 migration cleanup for old rules.
assert 'interface portproxy add' not in helper.lower()
assert 'interface portproxy set' not in helper.lower()
assert 'netsh.exe' not in helper.lower()
assert 'Migration cleanup only: v13.12.x used netsh portproxy' in ps
assert 'tailscale serve reset' not in ps.lower()
assert "@('serve','status','--json')" in ps
assert "@('serve','get-config','--all')" in ps
assert 'Add-WindowsTailscaleServeJsonState' in ps
assert "'-EnsureDistroRunning'" in ps
assert "$relayWaitSeconds = if ($SelfTest) { '30' } else { '120' }" in ps
assert '-ExecutionTimeLimit ([TimeSpan]::Zero)' in ps
assert '-RestartCount 5' in ps and '-RestartInterval (New-TimeSpan -Minutes 1)' in ps
assert 'Test-LatticeValeBridgeIpv4' in ps
assert 'Windows WSL native relay did not record a usable backend target' in ps
assert 'Waiting for Windows-native WSL relay' in ps
assert 'Stop-LatticeValeBridgeTaskAndWait' in ps
assert 'Find-ReachableWslIp $DistroName $Services $initialProbeSeconds' in helper
assert "if ($script:RelayTargetMode -eq 'mirrored-localhost')" in helper
assert "Test-RelayTargetForServices '127.0.0.1'" in helper
assert 'if (-not (Test-LocalTcpPort $bridgePort))' in ps
assert 'Do not rewrite the relay config here.' in ps
assert "pattern=re.compile(r'(?m)^public_baseurl\\s*:\\s*(.*?)\\s*$')" in ps
assert "print('UNCHANGED')" in ps
set_base=ps[ps.index('function Set-SynapsePublicBaseUrl'):ps.index('function Test-HttpsEndpoint')]
assert 'server_name' not in set_base
assert '[void](Set-SynapsePublicBaseUrl $DistroName $linuxUser $linuxHome "http://localhost:$matrixLocalPort")' in ps
print('TAILSCALE WINDOWS-NATIVE RELAY FIXTURES: PASS')
