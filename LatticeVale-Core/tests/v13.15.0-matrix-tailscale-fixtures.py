#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1'}
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(root/'stack/manage.sh').read_text(encoding='utf-8')
relay=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
compose=(root/'stack/compose.yaml').read_text(encoding='utf-8')

# Tailscale remains Windows-native and tailnet-only. Matrix uses standard HTTPS 443;
# Dashboard keeps its separate 9443 endpoint.
assert 'tailscale/tailscale' not in compose
assert "Get-OptionTcpPort $existingOptions 'tailscaleMatrixPort' 443" in ps
assert "Get-OptionTcpPort $old 'tailscaleMatrixPort' 443" in ps
assert "Read-TcpPort 'Matrix Tailscale HTTPS port' $defaultMatrixPort $disallow" in ps
assert "if ($tailscaleMatrix -and $tailscaleMatrixPort -eq 8448)" in ps
assert 'Migrating the prior LatticeVale Matrix Tailscale HTTPS default from 8448 to standard HTTPS 443.' in ps
assert 'if ($Port -eq 443) { return "https://$DnsName" }' in ps
assert "@('serve','--bg',\"--https=$HttpsPort\",\"http://127.0.0.1:$BackendPort\")" in ps
assert 'tailscale funnel' not in ps.lower()

# Relay availability is independent from stack startup. At logon it only binds the
# Windows localhost endpoints and waits; it cannot wake WSL unless autoStart grants it.
assert 'Register-LatticeValeBridgeRefreshTask $bridgePaths $true $autoStart' in ps
assert "if ($EnsureStackRunning) { $relayArgs += '-EnsureDistroRunning' }" in ps
assert 'Starting relay listeners without a live WSL target' in relay
assert 'passive relay is waiting for the user to start Hermes' in relay
assert ('if (Test-RelayTargetForServices $currentIp $services)' in relay) if (root/'VERSION.txt').read_text().strip() in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1'} else ('if (Test-WslIpForServices $currentIp $services)' in relay)
assert "if (-not $EnsureDistroRunning -and -not (Test-WslDistroRunning $DistroName)) { return '' }" in relay

# Matrix rooms are encrypted from creation and Hermes gets a stable device ID plus
# a retained recovery key so the device can self-sign on future starts.
assert 'm.room.encryption' in cfg
assert 'MATRIX_E2EE_MODE required' in cfg
assert "bot_device_id='LATTICEVALE_BOT'" in cfg
assert "sed -n 's/^MATRIX_DEVICE_ID=//p' secrets/matrix-bot.env" in cfg
assert 'MATRIX_RECOVERY_KEY_OUTPUT_FILE=/opt/data/matrix-recovery-key.once' in cfg
assert 'MATRIX_RECOVERY_KEY' in cfg
assert "run_stage matrix_cross_signing 'Secure Matrix device cross-signing settings'" in cfg
assert 'Matrix: cross-signing verified via recovery key' in cfg
assert 'never delete crypto.db here' in cfg
assert 'MATRIX_CROSS_SIGNING=installer-managed' in cfg
assert '.matrix-cross-signing-pending' in cfg
cross=cfg[cfg.index('stage_matrix_cross_signing() {'):cfg.index('verify_provider() {')]
assert cross.index('if [[ ! -s "$host_once" ]]') < cross.index("recycle_hermes_bounded 'Matrix recovery-key bootstrap'")
assert 'Capture that' in cross and 'BEFORE any recycle' in cross

# Missing recovery material on a pre-v13.15 repair does not make the old bot identity
# invalid or block Windows/Tailscale reconciliation. No crypto identity is rotated.
verify_matrix=cfg[cfg.index('verify_matrix() {'):cfg.index('verify_matrix_cross_signing() {')]
assert 'MATRIX_RECOVERY_KEY' not in verify_matrix
assert 'The repair will continue so Windows/Tailscale reconciliation can complete.' in cfg
assert 'rm -f ~/.hermes/platforms/matrix/store/crypto.db' not in cfg

# Explicit secret-inspection command can surface the retained key when requested.
assert 'MATRIX_RECOVERY_KEY' in manage[manage.index('matrix-credentials'):]
print('v13.15.0 Matrix/Tailscale fixtures: PASS')
