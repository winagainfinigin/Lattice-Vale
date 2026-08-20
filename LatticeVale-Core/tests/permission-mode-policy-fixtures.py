#!/usr/bin/env python3
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
boot = (root/'linux/bootstrap.sh').read_text(encoding='utf-8')
cfg = (root/'stack/configure-stack.sh').read_text(encoding='utf-8')
compose = (root/'stack/compose.yaml').read_text(encoding='utf-8')
manage = (root/'stack/manage.sh').read_text(encoding='utf-8')

# Installer-managed host files/directories must never be made owner-read-only. 0600/0700
# are private but writable by the selected owner; 0644/0755 likewise keep owner write.
for text, name in ((boot,'bootstrap'), (cfg,'configure'), (manage,'manage')):
    for m in re.finditer(r'\b(?:chmod|install\s+(?:[^\n]*?\s)?-m)\s+(0?[0-7]{3,4})\b', text):
        raw=m.group(1)
        mode=int(raw,8)
        assert mode & 0o200, f'{name}: owner-write bit missing from explicit mode {raw} near {m.start()}'

# No blanket removal of owner write access anywhere in the shipped shell code.
for text, name in ((boot,'bootstrap'), (cfg,'configure'), (manage,'manage')):
    assert 'u-w' not in text, f'{name}: chmod removes owner write access'
    assert 'a-w' not in text, f'{name}: chmod removes all write access'
    assert 'go-rwx' in (boot + manage), 'expected privacy hardening should remove only group/other access'

# Read-only bind mounts are intentionally narrow and container-side only. They must never
# include mutable Hermes state, secrets, workspace, databases, or model data.
ro_mounts=[]
for line in compose.splitlines():
    s=line.strip()
    if (s.startswith('- ./') or s.startswith('- ${OBSIDIAN_VAULT_HOST_PATH')) and s.endswith(':ro'):
        ro_mounts.append(s)
expected={
    '- ${OBSIDIAN_VAULT_HOST_PATH:-./vault}:/vault:ro',
    '- ./qmd-index-cycle.sh:/usr/local/bin/qmd-index-cycle:ro',
    '- ./vendor/honcho/database/init.sql:/docker-entrypoint-initdb.d/init.sql:ro',
    '- ./config/honcho/config.toml:/app/config.toml:ro',
}
assert set(ro_mounts)==expected, f'unexpected read-only bind mount set: {ro_mounts}'
for forbidden in ('data/hermes','secrets','workspace','data/synapse-db','data/honcho-db','data/ollama'):
    assert not any(forbidden in x for x in ro_mounts), f'mutable path unexpectedly read-only: {forbidden}'

# Permission reconciliation is selective, and repair verifies selected-user write access.
assert 'repair_user_tree()' in boot
assert 'verify_write_dirs=(' in boot
assert 'verify_write_files=(' in boot
assert 'data/synapse-db, data/honcho-db, and data/ollama' in boot
assert 'chown -R "$linux_uid:$linux_gid" "$stack_dir"' not in boot

print('PERMISSION MODE POLICY: PASS')
