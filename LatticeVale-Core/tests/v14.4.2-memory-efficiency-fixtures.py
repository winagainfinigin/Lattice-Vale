#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
cs=(root/'stack/configure-stack.sh').read_text()
boot=(root/'linux/bootstrap.sh').read_text()
audit=(root/'stack/state-audit.py').read_text()
installer=(root/'Install-LatticeVale.ps1').read_text()

assert "POLICY_VERSION=11" in cs
assert './configure-stack.sh --refresh-resource-policy' in boot
assert 'values.get("POLICY_VERSION") != "11"' in audit
assert 'mem_mib <= 6144 )); then' in cs and 'reserve_pct=30' in cs
assert 'mem_mib <= 12288 )) && [[ "$accel" == cpu ]] && managed_ollama_enabled' in cs
assert 'reserve_pct=10' in cs
assert 'mem_mib <= 24576 )); then' in cs and 'reserve_pct=20' in cs
assert 'MALLOC_ARENA_MAX:' in cs
assert 'SYNAPSE_CACHE_FACTOR:' in cs
assert 'shared_buffers=%s' in cs
assert 'max_connections=200' in cs
assert 'synapse_cache_factor=0.25' in cs
assert 'synapse_cache_factor=0.35' in cs
assert 'pg_shared_buffers=64MB' in cs
assert 'adaptive RAM-efficiency allocator tuning is missing' in audit
assert 'adaptive Synapse cache tuning is missing' in audit
assert 'adaptive PostgreSQL shared-buffer tuning is missing' in audit
assert 'allocator/Synapse/PostgreSQL RAM tuning' in installer
assert 'compose.override.yaml remains authoritative' in installer
print('v14.4.2/v14.4.3 memory-efficiency fixtures: PASS')
