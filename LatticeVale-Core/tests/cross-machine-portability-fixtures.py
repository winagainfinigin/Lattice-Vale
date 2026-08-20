#!/usr/bin/env python3
from pathlib import Path
import yaml
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text()
boot=(root/'linux/bootstrap.sh').read_text()
cfg=(root/'stack/configure-stack.sh').read_text()
manage=(root/'stack/manage.sh').read_text()
compose=yaml.safe_load((root/'stack/compose.yaml').read_text())
audit=(root/'stack/state-audit.py').read_text()

# Never inherit a user's selected/remote Docker daemon.
for text in (boot,cfg,manage):
    assert 'export DOCKER_HOST=unix:///var/run/docker.sock' in text
    assert 'unset DOCKER_CONTEXT' in text
assert 'export DOCKER_HOST=unix:///var/run/docker.sock' in ps
assert 'os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"' in audit
assert 'for attempt in 1 2 3; do' in boot
assert 'timeout --foreground --kill-after=10s 240s docker compose up -d' in boot
assert r'runuser -u "\$stack_user" -- env -u DOCKER_CONTEXT' in boot
assert r'HOME="\$stack_home" USER="\$stack_user"' in boot
assert 'LatticeVale stack could not be started after three attempts.' in boot
assert "bash -lc 'cd ~/hermes-stack && docker compose up -d'" not in boot

# Same fixed Compose namespace is accepted only from this exact stack directory.
assert 'com.docker.compose.project.working_dir' in cfg
assert 'expected_dir="$(pwd -P)"' in cfg
assert 'realpath -m -- "$working_dir"' in cfg
assert 'attached_ids' in cfg
assert 'ambiguous pre-existing network' in cfg


# Backend-only stateful services stay isolated, while services that need outbound
# provider/search/model/federation access also attach to a normal edge bridge.
assert compose['networks']['backend'].get('internal') is True
assert compose['networks']['edge'].get('internal', False) is False
for name in ('hermes','synapse','searxng','ollama'):
    assert 'edge' in compose['services'][name].get('networks', [])
for name in ('synapse-db','searxng-valkey','honcho-db','honcho-redis'):
    assert compose['services'][name].get('networks') == ['backend']

# APT automation uses an installer-owned file and only removes the legacy generic
# file when it is byte-for-byte the content written by old Hermes installers.
assert 'cat > /etc/apt/apt.conf.d/20auto-upgrades' not in boot
assert 'hermes_periodic=/etc/apt/apt.conf.d/52hermes-unattended-upgrades' in boot
assert 'cmp -s "$legacy_periodic" "$legacy_expected"' in boot
assert 'rm -f "$hermes_periodic"' in boot
assert 'systemctl disable --now unattended-upgrades' not in boot

# Timezone must exist in tzdata, not merely pass a character regex.
assert '! -f "/usr/share/zoneinfo/$timezone"' in cfg
print('CROSS-MACHINE PORTABILITY: PASS')
