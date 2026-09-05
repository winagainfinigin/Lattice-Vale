#!/usr/bin/env python3
from pathlib import Path
import yaml

root=Path(__file__).resolve().parents[1]
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
assert 'v13.16.0' in (root.parent/'docs/CHANGELOG.md').read_text(encoding='utf-8')
assert 'v13.16.0 repair maintenance' in (root/'README.md').read_text(encoding='utf-8').lower()
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
boot=(root/'linux/bootstrap.sh').read_text(encoding='utf-8')
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
audit=(root/'stack/state-audit.py').read_text(encoding='utf-8')
compose_text=(root/'stack/compose.yaml').read_text(encoding='utf-8')
compose=yaml.safe_load(compose_text)

# Clean-install behavior remains present and repair maintenance is gated to a recognized
# managed existing stack; it is never enabled for the normal fresh path.
assert "$repairMaintenance = $false" in ps
assert "$repairMaintenance = ($stackState -eq 'managed'" in ps
assert "'resume','change','reconfigure','advanced'" in ps
assert 'repairMaintenance = $repairMaintenance' in ps
assert "Preparing aged managed stack for repair staging" in ps
assert "apt-get clean >/dev/null 2>&1 || true; find /tmp" in ps
assert 'repair_maintenance_enabled()' in cfg
assert '"$(opt_text installerMode)" != fresh' in cfg

# Repair always performs the safe maintenance steps even if same-version checkpoints are
# already complete; the normal stage/checkpoint machinery for clean install remains intact.
assert "run_uncheckpointed_repair_step repair_storage_maintenance" in cfg
assert "run_uncheckpointed_repair_step repair_database_maintenance" in cfg
assert "run_stage prepare_config" in cfg and "run_stage finalize" in cfg

# Storage cleanup is ownership-bounded. Repair must not prune engine-global Docker
# images/build cache because unrelated projects may share the selected distro's Engine.
for forbidden in ('docker system prune', 'docker volume prune', 'docker image prune -a', 'docker image prune -f', 'docker builder prune', 'docker container prune', 'docker network prune'):
    assert forbidden not in cfg
assert 'engine-global Docker images and build cache untouched' in cfg
assert "-name 'pre-*'" in cfg
assert '^pre-[A-Za-z0-9._-]+-[0-9]{8}T[0-9]{6}Z$' in cfg
assert "timestamp-only names" in cfg
assert "tail -n 5000" in cfg
assert 'data/ollama' not in cfg[cfg.index('repair_storage_maintenance() {'):cfg.index('repair_database_maintenance() {')].replace('preserves Matrix/Postgres data, Hermes profiles/memory/sessions, QMD data, Ollama models, vault/workspace files, credentials, and user backups.','')

# Repair handles APT/stale interrupted staging before package work can need the space.
assert 'Repair pre-maintenance: clearing disposable APT cache' in boot
assert 'apt-get clean' in boot
assert "-name 'hermes-installer-*'" in boot and "-name 'hermes-audit-*'" in boot

# Long-lived databases receive standard online maintenance, never VACUUM FULL or destructive
# identity/data resets. A failed maintenance pass cannot cause user data deletion.
assert cfg.count("VACUUM (ANALYZE);") == 2
assert "-c 'VACUUM FULL" not in cfg and '-c \"VACUUM FULL' not in cfg
assert 'persistent data is unchanged and repair will continue' in cfg

# Docker logs are now bounded on every LatticeVale container; this is preventive and does not
# remove docker logs functionality or any persistent bind-mounted data.
base=compose.get('x-service-defaults') or {}
assert base.get('restart') == 'unless-stopped'
assert (base.get('logging') or {}).get('driver') == 'local'
opts=(base.get('logging') or {}).get('options') or {}
assert str(opts.get('max-size')) == '20m' and str(opts.get('max-file')) == '5'
services=compose.get('services') or {}
assert len(services) == 12
for name,svc in services.items():
    assert (svc.get('logging') or {}).get('driver') == 'local', name

# Audit now surfaces WSL filesystem free space/stack footprint but does not claim that this
# equals the host-side VHDX physical file size.
assert 'WSL filesystem free=' in audit
assert 'Do not infer physical VHDX size here.' in audit
assert '"storage"' in audit

print('v13.16.0 repair-maintenance fixtures: PASS')
