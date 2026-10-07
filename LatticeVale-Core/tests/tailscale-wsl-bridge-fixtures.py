#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
compose=(root/'stack/compose.yaml').read_text(encoding='utf-8')
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
helper=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
uninstaller=(root/'Uninstall-LatticeVale.ps1').read_text(encoding='utf-8')

assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0','14.6.1','14.6.2','14.6.3'}
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
    'Test-MatrixClientDiscovery',
    'Test-MatrixLoginEndpoint',
    'DASHBOARD_BRIDGE_PORT',
    'MATRIX_BRIDGE_PORT',
    'Test-HttpEndpointNoProxy',
    'Remove-LegacyHermesManualRelay',
):
    assert text in ps, text
version=(root/'VERSION.txt').read_text().strip()
assert ('shared-native-ollama-tailscale' in ps and 'user-existing-mirrored' in ps and 'Use mirrored WSL networking as the shared mode' not in ps) if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0','14.6.1','14.6.2','14.6.3'} else (('shared-native-ollama-tailscale' in ps and 'mirrored-localhost' in ps) if version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40'} else ('networkingMode=nat' in ps))
for text in (
    'new TcpListener(IPAddress.Loopback, listenPort)',
    'TargetAddress',
    'Get-ReachableWslIp',
    'EnsureDistroRunning',
    "Invoke-WslDistroCommand $DistroName '' 'true' @() 30",
    "Invoke-WslDistroCommand $DistroName 'root' '/usr/local/sbin/hermes-stack-start' @() 900",
    '[ValidateRange(1, 900)]',
    'var ignored = HandleClient(client, targetPort, listenPort, gate);',
):
    assert text in helper, text
# Primary v13.13+ transport may not create/set portproxy. Installer keeps only
# narrowly-proven v13.12 migration cleanup for old rules.
assert 'interface portproxy add' not in helper.lower()
assert 'interface portproxy set' not in helper.lower()
assert 'netsh.exe' not in helper.lower()
assert 'Migration cleanup only: v13.12.x used netsh portproxy' in ps
assert 'tailscale serve reset' not in ps.lower()
# Serve removal uses the supported per-port command and keeps output visible.
serve_disable = ps[ps.index('function Disable-WindowsTailscaleServe'):ps.index('function Resolve-UnownedTailscaleServeConflict')]
assert "Invoke-NativeProcessPassthrough $TailscaleExe @('serve',\"--https=$Port\",'off') 30" in serve_disable
assert "Check 'tailscale serve status --json' in Windows." in serve_disable
assert 'return $false' in serve_disable
serve_conflict = ps[ps.index('function Resolve-UnownedTailscaleServeConflict'):ps.index('function Enable-WindowsTailscaleServe')]
assert 'adopting it without changing or restarting Tailscale Serve' in serve_conflict
assert "return 'adopt'" in serve_conflict
matching_rule = serve_conflict.split('if (-not (Read-Choice "Replace the existing untracked Tailscale rule', 1)[0]
assert "@('serve',\"--https=$HttpsPort\",'off')" not in matching_rule
assert 'return \'leave\'' in serve_conflict
assert "@('serve',\"--https=$port\",'off')" in uninstaller
# Matrix remote access remains multi-client through fixed internal per-service gates.
# The corrected v14.6.3 removes the accidental user-facing relay-session setting.
assert "maxConnections=64" in ps
assert "maxConnections=512" in ps
assert "tailscaleMatrixMaxConnections" not in ps
assert "Maximum simultaneous remote Matrix relay connections" not in ps
assert "Matrix remote relay connection ceiling:" not in ps
assert "schema=5" in ps
assert 'ConcurrentDictionary<int, SemaphoreSlim> Gates' in helper
assert 'Start(int listenPort, int targetPort, int maxConnections)' in helper
assert 'new SemaphoreSlim(maxConnections, maxConnections)' in helper
assert 'private static readonly SemaphoreSlim Gate' not in helper
assert "$maxConnections = if ([string]$service.label -eq 'Matrix') { 512 } else { 64 }" in helper
assert '$configuredMax' not in helper
assert "$service.PSObject.Properties.Name -contains 'maxConnections'" not in helper
assert 'per-service concurrency limit' in helper
assert "@('set','--accept-dns=true')" not in ps
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
assert 'does not require rewriting relay config.' in ps
assert "pattern=re.compile(r'(?m)^public_baseurl\\s*:\\s*(.*?)\\s*$')" in ps
assert "print('UNCHANGED')" in ps
set_base=ps[ps.index('function Set-SynapsePublicBaseUrl'):ps.index('function Test-HttpsEndpoint')]
assert 'server_name' not in set_base
assert '[void](Set-SynapsePublicBaseUrl $DistroName $linuxUser $linuxHome "http://localhost:$matrixLocalPort")' in ps
assert '$matrixBaseUrlReady = Set-SynapsePublicBaseUrl $DistroName $linuxUser $linuxHome $matrixPublicUrl' in ps
assert '$matrixPath = Test-MatrixTailscaleClientPathViaIpv4 $matrixPublicUrl $dnsName $tsStatus.IPv4 $tailscaleMatrixPort' in ps
assert '$matrixDiscoveryReady = $matrixPath.Discovery' in ps
assert '$matrixLoginReady = $matrixPath.Login' in ps
for text in (
    'Ensure-WindowsTailscaleRemoteAccessPreferences',
    'Authenticated = $authenticated',
    "elseif (-not $tsStatus.Authenticated)",
    'Test-WindowsTailscaleDnsResolution',
    'Test-WindowsTailscaleServeListener',
    'Invoke-TailscaleHttpsProbeViaIpv4',
    'Test-MatrixTailscaleClientPathViaIpv4',
    'Remote-device page challenge skipped',
    "@('set','--shields-up=false')",
    "@('syspolicy','list')",
    "--resolve",
    'REMOTE_VALIDATION_STATUS',
    'Remote-device page validation is not part of installation',
    'Tailscale remote access: {0} - {1}',
):
    assert text in ps, text
assert '/.well-known/matrix/client' in ps
# v14.6.1 live remote-access regression: Win32/WSL nested shell quoting must not
# be used for the Synapse post-restart readiness check. Probe env + curl via direct argv.
set_base=ps[ps.index('function Set-SynapsePublicBaseUrl'):ps.index('function Test-MatrixClientDiscovery')]
assert "Invoke-WslDirectCapture $Name $User 'grep' @('-m','1','^MATRIX_HOST_PORT=',$envPath)" in set_base
assert "Invoke-WslDirectCapture $Name $User 'curl' @('-fsS','--connect-timeout','3','--max-time','5'" in set_base
assert 'MATRIX_HOST_PORT=//p' not in set_base
# Backend matching is a PowerShell/.NET regex: one regex escape per IPv4 dot.
assert '(?:127\\.0\\.0\\.1|localhost)' in ps
assert '(?:127\\\\.0\\\\.0\\\\.1|localhost)' not in ps
# A Matrix failure must not be overwritten by the later bridge-metadata summary.
assert "if ((-not $bridgeTracked -or -not $bridgeTaskTracked) -and $tailscaleFailureCategory -eq 'NONE')" in ps

# Corrected v14.6.3 keeps schema 24 compatible with interim builds but treats
# tailscaleMatrixMaxConnections as obsolete data. Values such as 2 must never block
# migration or constrain runtime behavior, and new options no longer persist the field.
import importlib.util
_arch_spec = importlib.util.spec_from_file_location("latticevale_arch_relay_fixture", root/"stack/latticevale_arch.py")
_arch = importlib.util.module_from_spec(_arch_spec)
_arch_spec.loader.exec_module(_arch)
_arch.validate_install_options({"schema": 23}, 24)
for _legacy in (2, 0, 4097, True, "obsolete"):
    _arch.validate_install_options({"schema": 24, "tailscaleMatrixMaxConnections": _legacy}, 24)

assert 'Invoke-TailscaleRemotePeerValidation' not in ps
assert 'Validate another Tailscale device?' not in ps
assert 'REMOTE-DEVICE VALIDATION' not in ps
assert 'Remote-device page challenge skipped' in ps
assert "Status='NOT_RUN'; Category='NOT_RUN'" in ps
assert "if ($resolution -eq 'adopt')" in ps
assert 'Could not deterministically rebuild the installer-owned Matrix Serve mapping' not in ps
for key in (
    'REMOTE_VALIDATION_ATTEMPTED', 'REMOTE_VALIDATION_PASSED', 'REMOTE_VALIDATION_FAILED',
    'REMOTE_VALIDATION_SKIPPED', 'REMOTE_VALIDATION_LAST_UTC'
):
    assert key in ps, key

# Aggregate-status truth table required by the multi-device contract.
def aggregate(states):
    attempted=len(states); passed=states.count('PASS'); failed=states.count('FAIL'); skipped=states.count('SKIP')
    if attempted == 0: return 'PARTIAL'
    if passed == attempted: return 'PASS'
    if passed > 0: return 'PARTIAL'
    if failed == attempted: return 'FAIL'
    return 'PARTIAL'
assert aggregate(['PASS','PASS']) == 'PASS'
assert aggregate(['PASS','PASS','PASS']) == 'PASS'
assert aggregate(['PASS','FAIL']) == 'PARTIAL'
assert aggregate(['FAIL','PASS']) == 'PARTIAL'
assert aggregate(['PASS','SKIP']) == 'PARTIAL'
assert aggregate(['FAIL','FAIL']) == 'FAIL'
assert aggregate([]) == 'PARTIAL'
assert "Enable unattended Ubuntu security updates?" not in ps
assert "unattendedUpdates =" not in ps
features=(root.parent/"docs/FEATURES.md").read_text(encoding="utf-8")
installer_description=(root.parent/"docs/Installer Description.txt").read_text(encoding="utf-8")
assert "## 3.21 Unattended Ubuntu security updates" not in features
assert "optional unattended Ubuntu security updates" not in features
assert "optional unattended-updates integration" not in installer_description
bootstrap=(root/"linux/bootstrap.sh").read_text(encoding="utf-8")
assert "Unattended-upgrades integration was removed." in bootstrap
assert "install -y --no-install-recommends unattended-upgrades" not in bootstrap

print('TAILSCALE WINDOWS-NATIVE RELAY FIXTURES: PASS')
