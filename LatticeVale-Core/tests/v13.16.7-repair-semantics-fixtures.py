#!/usr/bin/env python3
from pathlib import Path
import hashlib, json

ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')

# Bundle version is metadata, not an all-stage invalidation token.
hash_start=cfg.index('OPTIONS_HASH=')
hash_end=cfg.index('CURRENT_STAGE="startup"', hash_start)
hash_block=cfg[hash_start:hash_end]
assert "payload=json.dumps({'options':d}" in hash_block
assert "{'installerVersion':ver,'options':d}" not in hash_block
for transient in ('installerVersion','installerMode','resetCheckpoints','forceProviderSetup','forceProfileSetup','rebuildMatrixIdentity','repairMaintenance'):
    assert transient in hash_block, transient

# Stable choices must hash identically across LatticeVale bundle versions.
def stable_hash(options):
    d=dict(options)
    for k in ('installerVersion','installerMode','resetCheckpoints','forceProviderSetup','forceProfileSetup','rebuildMatrixIdentity','repairMaintenance'):
        d.pop(k,None)
    payload=json.dumps({'options':d},sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(payload).hexdigest()
a={'installerVersion':'13.16.6','installerMode':'resume','dashboard':True,'qmd':True,'matrix':True}
b={**a,'installerVersion':'13.16.7'}
assert stable_hash(a)==stable_hash(b)
assert stable_hash(a)!=stable_hash({**b,'qmd':False})

# A real migration is opt-in per stage, and pre-13.16.7 checkpoints can be adopted
# only in Resume/Reconfigure after the live verifier succeeds.
assert 'checkpoint_revision()' in cfg
for stage in ('prepare_config','infrastructure','matrix_bootstrap','provider_setup','profiles','matrix_cross_signing','integrations','reconcile','kanban_gateway','finalize'):
    assert stage in cfg[cfg.index('checkpoint_revision()'):cfg.index('state_init()')], stage
assert 'state_stage_legacy_adoptable()' in cfg
assert 'resume_adoption_allowed()' in cfg
run=cfg[cfg.index('run_stage()'):cfg.index('http_status_ok()',cfg.index('run_stage()'))]
assert 'if ! checkpoint_bypass_requested "$stage"; then' in run
assert 'state_stage_current "$stage" && "$verifier"' in run
assert 'resume_adoption_allowed && state_stage_legacy_adoptable "$stage" && "$verifier"' in run
assert 'checkpoint migrated' in run

# Explicit reconfigure/rebuild requests must bypass a healthy checkpoint.
forced=cfg[cfg.index('checkpoint_bypass_requested()'):cfg.index('resume_adoption_allowed()')]
assert 'provider_setup)' in forced and 'forceProviderSetup' in forced
assert 'profiles)' in forced and 'forceProfileSetup' in forced
assert 'matrix_bootstrap)' in forced and 'rebuildMatrixIdentity' in forced

# Missing options must not demote a stack with strong LatticeVale markers to the
# unrecognized/fresh-style adoption path.
detect=ps[ps.index('function Test-ManagedLatticeValeStackForUser'):ps.index('function Get-LatticeValeStackPathState')]
assert 'configure-stack.sh' in detect and 'manage.sh' in detect and '.installer-state.json' in detect
assert 'installer-config.tar.gz' in detect and 'files.tar.gz' in detect

# A recognized managed stack with damaged current options must recover prior metadata
# or fail closed before the fresh-install question flow.
get_opts=ps[ps.index('function Get-ExistingInstallOptions'):ps.index('function Get-OptionValue')]
assert 'installer-config.tar.gz' in get_opts and 'files.tar.gz' in get_opts
assert 'isinstance(d,dict)' in get_opts
assert 'recovered the newest valid installer options' in get_opts
managed=ps[ps.index("'managed' {"):ps.index("'absent' {")]
assert 'if ($null -eq $existingOptions)' in managed
assert 'will NOT fall back to clean-install choices' in managed
assert managed.index('if ($null -eq $existingOptions)') < min(i for i in (managed.find("Read-Menu 'Choose how to handle the existing LatticeVale stack:'"), managed.find("Read-MenuExplicit 'Choose how to handle the existing LatticeVale stack:'")) if i >= 0)

print('V13.16.7+ REPAIR SEMANTICS FIXTURES: PASS')
print('- bundle-version-only changes preserve healthy checkpoints')
print('- per-stage revisions retain targeted migration support')
print('- explicit provider/profile recovery bypasses checkpoint skip')
print('- damaged managed options recover from pre-repair/manage backups or fail closed')
