#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
boot=(root/'linux/bootstrap.sh').read_text(encoding='utf-8')
audit=(root/'stack/state-audit.py').read_text(encoding='utf-8')

# Repair discovery must not depend on broken selected-user traversal/read permissions.
assert 'function Test-ManagedLatticeValeStackForUser' in ps
assert "Invoke-WslDirectCapture $Name 'root' 'test'" in ps
assert 'function Get-LatticeValeStackPathState' in ps
assert "Fall back to root so a permissions regression" in ps
assert '$stackState = Get-LatticeValeStackPathState $DistroName $linuxUser' in ps

# Only intended user-owned paths are recursively normalized.
assert 'repair_user_tree()' in boot
for rel in ('data/hermes','data/qmd','data/synapse','data/searxng-valkey','data/honcho-redis','secrets','vendor','vault','workspace'):
    assert rel in boot
for forbidden in ('repair_user_tree data/synapse-db','repair_user_tree data/honcho-db','repair_user_tree data/ollama',
                  'chown -R "$linux_uid:$linux_gid" "$stack_dir"'):
    assert forbidden not in boot, forbidden
assert 'data/synapse-db, data/honcho-db, and data/ollama' in boot
assert 'chown -hR -P --preserve-root' in boot
assert 'Selected Ubuntu user cannot write required installer paths:' in boot
assert 'verify_write_dirs=(' in boot
assert 'verify_write_files=(' in boot

# Read-only audit must surface permissions as a first-class repair condition.
assert 'c["permissions"]' in audit
assert 'installer/user-owned write paths are writable' in audit
assert '("stack", "permissions", "storage", "docker", "hermes", "api")' in audit
print('PERMISSION REPAIR FIXTURES: PASS')
