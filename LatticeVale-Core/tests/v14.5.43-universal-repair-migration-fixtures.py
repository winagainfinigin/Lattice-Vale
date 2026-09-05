#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
core = ROOT / 'LatticeVale-Core'
version = (core / 'VERSION.txt').read_text(encoding='ascii').strip()
ps = (core / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
compat = (core / 'compatibility.conf').read_text(encoding='ascii')
bootstrap = (core / 'linux' / 'bootstrap.sh').read_text(encoding='utf-8')
config = (core / 'stack' / 'configure-stack.sh').read_text(encoding='utf-8')
readonly = (core / 'stack' / 'latticevale_readonly.py').read_text(encoding='utf-8')
sys.path.insert(0, str(core / 'stack'))
from latticevale_arch import load_compat, validate_install_options  # noqa: E402
policy = load_compat(core / 'compatibility.conf')

# The compatibility floor and current options schema are explicit release policy.
assert 'MIN_UNIVERSAL_REPAIR_MAJOR=0' in compat
assert policy['INSTALL_OPTIONS_SCHEMA'] == '22'
assert 'INSTALL_OPTIONS_SCHEMA=22' in compat
assert "MinUniversalRepairMajor = $universalRepairMajor" in ps
assert "InstallOptionsSchema = $installOptionsSchema" in ps

# Historical managed stacks remain discoverable without accepting arbitrary similarly
# named directories: the exact core trio is required before legacy finalization markers.
assert '$stackPath/compose.yaml' in ps
assert '$stackPath/configure-stack.sh' in ps
assert '$stackPath/manage.sh' in ps
assert "$stackPath/.install-info" in ps and "$stackPath/.configured" in ps
assert 'Get-LatticeValeRepairOriginInfo' in ps
assert 'ConvertTo-LatticeValeComparableVersion' in ps

# Repair protects against downgrade and unsupported/unproven history.
assert 'Refusing a repair downgrade' in ps
assert 'unsupported or corrupt installer metadata/options schema' in ps
assert '$universalRepairMajor -lt 0 -or $universalRepairMajor -gt 99' in ps
assert '$repairOriginInfo.NewerThanBundle' in ps
assert '$repairOriginInfo.Supported' in ps

# Resume/repair is the cumulative upgrader only when saved metadata is stale.
resume = ps[ps.index("1 {\n                $installMode = 'resume'"):ps.index("            2 {", ps.index("1 {\n                $installMode = 'resume'"))]
assert '$repairOriginInfo.NeedsMigration' in resume
assert '$universalRepairMigration = $true' in resume
assert '$forceManagedUpdate = $true' in resume
assert 'no intermediate LatticeVale installer is required' in ps

# The cumulative migration uses the existing verified pre-update rollback backup before
# any managed software/source refresh, and then stages current bundle-owned files.
backup_pos = ps.index("if ($forceManagedUpdate) {")
bootstrap_pos = ps.index("Write-Step 'Bootstrapping Docker and the selected LatticeVale stack inside Ubuntu'")
assert backup_pos < bootstrap_pos
assert 'Creating cumulative repair-migration safety backup' in ps
assert 'pre-update-safety-backup.sh' in ps

# Old pre-v14.2 managed Ollama state gets an explicit CPU policy during universal repair.
# This adopts current canonical CPU/RAM ownership without silently opting an existing user into GPU.
assert "if (-not $persistOllamaAcceleration -and $universalRepairMigration)" in ps
assert "$ollamaAcceleration = 'cpu'" in ps
assert '$persistOllamaAcceleration = $true' in ps

# The output options are normalized to the current schema and carry transient migration
# provenance; transient fields cannot invalidate otherwise healthy checkpoints next run.
assert 'schema = $compat.InstallOptionsSchema' in ps
for token in ('repairOriginVersion', 'repairOriginSchema', 'universalRepairMigration'):
    assert token in ps
    assert token in config
    assert f'"{token}"' in readonly
assert 'latticevale_arch.py validate-options install-options.json --compat compatibility.conf' in config
# Corrected 14.5.47 schema-21 state is valid migration input; current schema 22 is
# accepted; a future schema remains fail-closed from the same canonical validator.
assert validate_install_options({'schema': 21, 'repairOriginSchema': 21}, 22)['schema'] == 21
assert validate_install_options({'schema': 22, 'repairOriginSchema': 21}, 22)['schema'] == 22
try:
    validate_install_options({'schema': 23}, 22)
except ValueError as exc:
    assert 'SCHEMA_FUTURE_VERSION' in str(exc)
else:
    raise AssertionError('future schema 23 was accepted')

# Root bootstrap must identify historical finalized stacks as repair runs too, so a
# forced cumulative refresh cannot be mistaken for a fresh install after staging.
assert '-s "$stack_dir/.install-info"' in bootstrap
assert '-f "$stack_dir/.configured"' in bootstrap

# Same-version repair remains local-first: forceManagedUpdate is initialized false and
# only migration/update paths set it true.
assert '$forceManagedUpdate = $false' in ps
assert 'Between refresh windows it remains local-first and is not a blanket update.' in ps

print('v14.5.43 UNIVERSAL REPAIR MIGRATION FIXTURES: PASS')
print('- any recognized prior-version proven managed stacks can migrate directly through Resume / repair')
print('- older bundle downgrade is rejected')
print('- cumulative migration forces rollback backup + managed refresh')
print('- legacy Ollama resource ownership normalizes safely to the current CPU policy')
print('- schema/provenance migration fields are checkpoint-ephemeral')
