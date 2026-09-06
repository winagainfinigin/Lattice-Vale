#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
relay=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
compose=(root/'stack/compose.yaml').read_text(encoding='utf-8')
boot=(root/'linux/bootstrap.sh').read_text(encoding='utf-8')
version=(root/'VERSION.txt').read_text().strip()
assert version in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}

# Live-reproduced Tailscale/WSL 502: v13.13.2 uses a real Windows user-space loopback listener.
assert 'new TcpListener(IPAddress.Loopback, listenPort)' in relay
assert 'TargetAddress' in relay and 'Get-ReachableWslIp' in relay and 'Start-HermesStack' in relay
assert ('Using verified relay target' in relay) if version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'} else ('Using installer-seeded WSL IPv4' in relay)
assert 'Invoke-WslDistroCommand' in relay
if version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}:
    reach=relay[relay.index('function Get-ReachableWslIp'):relay.index('function Write-RelayState')]
    nat=reach[reach.index('$initialProbeSeconds'):]
    assert nat.index('Find-ReachableWslIp $DistroName $Services $initialProbeSeconds') < nat.index('Start-HermesStack $DistroName')
else:
    assert relay.index('Find-ReachableWslIp $DistroName $Services $initialProbeSeconds') < relay.index('Start-HermesStack $DistroName')
assert 'interface portproxy add' not in relay.lower()
assert "transport='windows-native-tcp-relay'" in ps
assert (("$relayWaitSeconds = if ($SelfTest) { '30' } else { '120' }" in ps) if version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'} else ("'-WaitSeconds','120'" in ps)) and '[ValidateRange(1, 900)]' in relay
assert '-ExecutionTimeLimit ([TimeSpan]::Zero)' in ps and '-RestartCount 5' in ps
assert '-RunLevel Highest' in ps
assert '#Requires -RunAsAdministrator' not in relay
assert 'Do not rewrite the relay config here.' in ps
assert 'Test-HttpsEndpoint' in ps and '$request.Proxy = $null' in ps

# Fresh Windows state can adopt the exact already-compatible Serve mapping from manual recovery.
assert 'Adopted existing compatible Tailscale Dashboard Serve mapping' in ps
assert 'Adopted existing compatible Tailscale Matrix Serve mapping' in ps
assert 'tailscale serve reset' not in ps.lower()

# Matrix fresh install: pinned stable Synapse, server-negotiated stable room version, E2EE from creation.
assert 'matrixdotorg/synapse:v1.158.0' in cfg
assert 'matrixdotorg/synapse:v1.158.0' in compose
assert '/_matrix/client/v3/capabilities' in cfg
if version in {'14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}:
    assert 'LATTICEVALE_MATRIX_ROOM_VERSION=10' in cfg
    assert '.capabilities["m.room_versions"].available[$v]' in cfg
else:
    assert 'select(.value == "stable")' in cfg
assert 'room_version:$rv' in cfg
assert 'm.megolm.v1.aes-sha2' in cfg
assert 'MATRIX_E2EE_MODE required' in cfg
assert 'MATRIX_DEVICE_ID "$bot_device_id"' in cfg
assert "cfg['default_room_version']=str(sys.argv[1])" in cfg
assert 'returned_bot_device_id' in cfg
assert "docker exec -u hermes hermes-agent python -c 'import mautrix, olm'" in cfg
assert '/_matrix/client/v3/join/$encoded_room' not in cfg
assert '/_matrix/client/v3/joined_rooms' in cfg

# Startup should be automatic and retry instead of requiring the user to manually start Hermes first.
assert 'for attempt in 1 2 3; do' in boot
assert 'docker compose up -d' in boot
assert r'runuser -u "\$stack_user"' in boot
assert "[[ \"\\$started\" == true ]]" in boot
print('v13.13.2 native relay + Matrix fixtures: PASS')
