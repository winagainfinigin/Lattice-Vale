#!/usr/bin/env python3
"""Cross-version existing-install menu contract.

The behavioral baseline for Options 1-7 is the shipped v14.5.2 release.  Option 8
was added in v14.6.0.  v14.6.1 may add migration/canonical architecture and
DirectML behavior, but it must not silently repurpose an existing option.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
core = ROOT / 'LatticeVale-Core'
ps = (core / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
cfg = (core / 'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (core / 'stack/manage.sh').read_text(encoding='utf-8')
cleanup = (core / 'linux/cleanup-storage.sh').read_text(encoding='utf-8')
compat = (core / 'compatibility.conf').read_text(encoding='ascii')
features = (ROOT / 'docs/FEATURES.md').read_text(encoding='utf-8')
instructions = (ROOT / 'docs/Instructions.txt').read_text(encoding='utf-8')

# v14.5.2 baseline: the first seven existing-install choices keep their wording/order.
# v14.6.0 adds diagnostics as Option 8 without renumbering any baseline operation.
menu = [
    'Resume / repair installation - recommended; reuse previous choices and repair failed/incomplete/stale stages (targeted managed software also refreshes when the periodic window is due)',
    'Change installed components - reuse the stack but choose options again',
    'Verify installation only - read-only audit; make no changes',
    'Reconfigure providers/profiles - keep services/data but rerun Hermes provider setup',
    'Advanced recovery - reset checkpoints or explicitly rebuild installer-owned identities',
    "Update / repair installer-managed software - force this bundle''s declared component versions/channels and managed package/image/source layer now, then run normal repair",
    'Cleanup / reclaim disk space - choose safe cleanup categories without changing the current LatticeVale runtime/data configuration',
    'Diagnostics / compatibility test - read-only Windows + WSL + GPU/backend + stack verification; make no changes',
]
positions = [ps.index(item) for item in menu]
assert positions == sorted(positions)

menu_start = ps.index("        switch ($modeChoice) {")
menu_end = ps.index("    'absent' { }", menu_start)
menu_ps = ps[menu_start:menu_end]


# Option 1 baseline: preservation-first normal repair, no blanket same-version update.
assert "1 { $installMode = 'resume' }" in ps
assert 'Between refresh windows it remains local-first and is not a blanket update.' in ps
assert 'A bundle-version change alone remains local-first' in instructions

# v14.6.1 extension: when the *stack itself* predates the current schema, migration is
# common to every mutating existing-install choice.  This prevents Options 2/4/5/6 from
# applying current schemas/stages to only-partially-migrated v14.5.2-era durable state.
mutating = "@('resume','change','reconfigure','advanced','update')"
assert f'$mutatingManagedModes = {mutating}' in ps
assert '$repairOriginInfo.NeedsMigration -and $installMode -in $mutatingManagedModes' in ps
assert '$universalRepairMigration = $true' in ps
assert '$forceManagedUpdate = $true' in ps
assert 'then continue with the selected mode\'s normal semantics' in ps
assert 'Options 1, 2, 4, 5, or 6' in ps
assert 'Options 3, 7, and 8 remain read-only or isolated maintenance and do not migrate the stack' in ps

# Option 2 baseline: scoped changes only, preserving all unselected saved settings.
for scope in ('components','kanban','matrix-tailscale','local-ai','runtime'):
    assert f"$changeScopes -notcontains '{scope}'" in ps
assert "$changeScopes = @('components','kanban','matrix-tailscale','local-ai','runtime')" in ps
assert 'Only these categories will be changed:' in ps
assert 'Everything else remains exactly as saved.' in ps
assert '$wasHermesLocalAI = $hermesLocalAI' in ps
assert 'if ($wasHermesLocalAI -and -not $hermesLocalAI)' in ps
assert '$forceProviderSetup = $true' in ps

# Option 3 baseline: terminal read-only audit; it must exit before normal mutation.
opt3 = menu_ps[menu_ps.index("            3 {\n                $installMode = 'verify'"):menu_ps.index('            4 {', menu_ps.index("            3 {\n                $installMode = 'verify'"))]
assert 'Show-LatticeValeReadOnlyVerification' in opt3 and 'exit 0' in opt3
for forbidden in ('forceManagedUpdate = $true','resetCheckpoints = $true','rebuildMatrixIdentity = $true','Invoke-LatticeValeCleanupMaintenance'):
    assert forbidden not in opt3

# Option 4 baseline: provider/profile reconfiguration, not a component questionnaire.
opt4 = menu_ps[menu_ps.index("            4 {\n                $installMode = 'reconfigure'"):menu_ps.index('            5 {', menu_ps.index("            4 {\n                $installMode = 'reconfigure'"))]
assert '$forceProviderSetup = $true' in opt4 and '$forceProfileSetup = $true' in opt4
assert 'Read-MenuExplicit \'Select a category to change' not in opt4
assert 'use Change installed components -> Local AI / Honcho / Ollama' in opt4

# Option 5 baseline: same four recovery actions, preserving data; only explicit Matrix
# identity recovery may replace the installer-owned default bot/device/room identity.
for action in (
    'Reset installer checkpoints and re-verify/reconcile every stage (data is preserved)',
    'Rebuild only the installer-owned Matrix bot/room identity if Matrix authentication is broken',
    'Rerun provider/profile setup and reset checkpoints',
    'Return to a read-only verification and exit',
):
    assert action in ps
advanced = menu_ps[menu_ps.index("            5 {\n                $installMode = 'advanced'"):menu_ps.index('            6 {', menu_ps.index("            5 {\n                $installMode = 'advanced'"))]
assert 'docker volume rm' not in advanced.lower()
assert 'data/synapse' not in advanced.lower()
assert 'Advanced Matrix identity rebuild requires the shared Matrix service to be enabled' in advanced

# Option 6 baseline: force this bundle's managed software layer only after the independent
# verified safety backup, then continue through normal repair semantics.
opt6 = menu_ps[menu_ps.index("            6 {\n                $installMode = 'update'"):menu_ps.index('            7 {', menu_ps.index("            6 {\n                $installMode = 'update'"))]
assert '$forceManagedUpdate = $true' in opt6
assert 'CONTROLLED UPDATE / REPAIR' in opt6
assert 'pre-update-safety-backup.sh' in ps
assert ps.index("if ($forceManagedUpdate) {") < ps.index("Write-Step 'Bootstrapping Docker and the selected LatticeVale stack inside Ubuntu'")

# Option 7 v14.5.2 baseline: isolated bounded cleanup, never normal reconciliation.
opt7_start = menu_ps.index("            7 {\n                $installMode = 'cleanup'")
opt7_end = menu_ps.index("            8 {\n                $installMode = 'diagnostics'", opt7_start)
opt7 = menu_ps[opt7_start:opt7_end]
assert 'Invoke-LatticeValeCleanupMaintenance' in opt7 and 'exit 0' in opt7
assert 'docker image prune -f' in cleanup and 'docker builder prune -f' in cleanup and 'fstrim -v /' in cleanup
for forbidden in ('docker system prune','docker volume prune','docker network prune','docker image prune -a','docker builder prune --all','docker compose down','rm -rf data/'):
    assert forbidden not in cleanup

# Option 8 v14.6.0 baseline: read-only compatibility diagnostics using the current bundle's
# canonical validator/snapshot, then exit without entering the normal staged installer.
opt8_start = menu_ps.index("            8 {\n                $installMode = 'diagnostics'")
opt8_end = menu_ps.index('\n\n        # v14.6.1 hotfix:', opt8_start)
opt8 = menu_ps[opt8_start:opt8_end]
assert 'Get-LatticeValeGpuAccelerationPlan' in opt8
assert 'Show-LatticeValeReadOnlyVerification' in opt8
assert 'No installer-managed files, packages, services, WSL settings, or application data were changed.' in opt8
assert 'exit 0' in opt8
for staged in ('stack\\state-audit.py','stack\\latticevale_arch.py','compatibility.conf'):
    assert staged in ps
assert 'windows-hardware.json' in ps

# Mode topology is still the v14.5.2 preservation model: only 1/2/4/5/6 join repair
# maintenance/reuse; 3/7/8 do not leak into mutating stages.
assert "$repairMaintenance = ($stackState -eq 'managed' -and $installMode -in @('resume','change','reconfigure','advanced','update'))" in ps
assert "$reusePriorChoices = ($installMode -in @('resume','change','reconfigure','advanced','update')) -and $null -ne $existingOptions" in ps

# v14.6.1 feature contract must remain intact while the baseline menu is preserved.
for required in (
    'INSTALL_OPTIONS_SCHEMA=23',
    'RUNTIME_POLICY_SCHEMA=13',
    'HARDWARE_CAPABILITIES_SCHEMA=1',
    'BACKEND_CAPABILITIES_SCHEMA=1',
    'BACKEND_HEALTH_SCHEMA=1',
    'DIAGNOSTICS_SCHEMA=1',
    'DIRECTML_MIN_WINDOWS_BUILD=22000',
):
    assert required in compat
for required in (
    'refresh_canonical_architecture_state',
    'repair_runtime_policy_reconcile',
    'repair_directml_gateway',
    'register_missing_gateway_slot_exact',
):
    assert required in cfg
assert 'register_missing_gateway_slot_exact' in manage
assert 'Existing-install menu — all eight modes' in features
assert '## 5.8 Diagnostics / compatibility test' in features
for n in range(1,9):
    assert f'{n}. ' in instructions, f'Instructions.txt missing documented Option {n}'

print('v14.6.1 EIGHT-OPTION BASELINE REGRESSION: PASS')
print('- Options 1-7 preserve v14.5.2 behavioral roles and ordering')
print('- Option 8 preserves the v14.6.0 read-only diagnostics role')
print('- older proven stacks migrate before every mutating option, never before 3/7/8')
print('- schema 23, policy 13, canonical architecture, DirectML and gateway recovery remain present')
