#!/usr/bin/env python3
"""v14.4.6 upgrade/repair refresh-gating regressions."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()
assert VERSION in {'14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}, VERSION

boot = (ROOT / 'linux/bootstrap.sh').read_text(encoding='utf-8')
compat = (ROOT / 'compatibility.conf').read_text(encoding='utf-8')
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
audit = (ROOT / 'stack/state-audit.py').read_text(encoding='utf-8')
arch = (ROOT / 'stack/latticevale_arch.py').read_text(encoding='utf-8')

m = re.search(r'^MANAGED_REPAIR_REFRESH_REVISION=(\d+)$', compat, re.M)
assert m
current_refresh_revision = int(m.group(1))
assert current_refresh_revision == (4 if VERSION == '14.6.0' else (3 if VERSION == '14.5.47' else 2))
assert 'VERSION.txt alone is' in compat and 'not a managed-refresh trigger' in compat

# Public v14.4.2 shipped refresh revision 1 and adaptive resource policy v2. A direct
# public 14.4.2 -> v14.4.6 Option-1 repair must therefore cross both explicit migration
# boundaries even though bundle version itself is no longer a refresh predicate.
PUBLIC_14_4_2_REFRESH_REVISION = 1
PUBLIC_14_4_2_RESOURCE_POLICY = 2
assert current_refresh_revision > PUBLIC_14_4_2_REFRESH_REVISION
assert '[POLICY_VERSION]=12' in cfg and '[RESOURCE_POLICY_MODE]=adaptive' in cfg
assert PUBLIC_14_4_2_RESOURCE_POLICY < 5

# Ordinary repair refresh gating must use marker validity, refresh revision, or age.
refresh_condition = re.search(
    r'elif \[\[ ! "\$last_refresh_epoch" =~ \^\[0-9\]\+\$ \]\] \|\| '
    r'\[\[ "\$last_refresh_revision" != "\$repair_refresh_revision" \]\] \|\| '
    r'\(\( now_epoch - last_refresh_epoch >= repair_refresh_interval_seconds \)\); then',
    boot,
)
assert refresh_condition, 'ordinary repair refresh condition changed unexpectedly'
assert '[[ "$last_refresh_installer_version" != "$installer_version" ]] ||' not in boot
assert 'Managed repair package/image/source refresh is due because the LatticeVale bundle changed' not in boot
assert 'bundle changed since the last managed component refresh' in boot
assert 'Resume / repair remains local-first' in boot

# Pending refreshes are compatible across a version-only bump when the explicit refresh
# policy revision is unchanged. Provenance is retained but must not force root APT/Docker
# work to repeat.
assert '[[ "$pending_refresh_revision" == "$repair_refresh_revision" ]]' in boot
assert '&& "$pending_refresh_installer_version" == "$installer_version"' not in boot
assert 'compatible refresh policy revision' in boot
assert 'different/legacy refresh policy' in boot
assert "printf 'POLICY_REVISION=%s\\nINSTALLER_VERSION=%s\\n'" in boot

# Option 6 remains the explicit force-refresh escape hatch.
assert 'if [[ "$force_managed_update" == true ]]' in boot
assert "Explicit Update / repair requested: forcing this bundle's installer-managed package/image/source refresh now" in boot

# Policy-v3 migration remains an explicit repair obligation and must reconcile containers
# only when the resource overlay actually changes.
assert "run_uncheckpointed_repair_step repair_runtime_policy 'Reconcile adaptive runtime/RAM policy'" in cfg
assert "state_mark infrastructure pending 'adaptive runtime/RAM policy changed; selected infrastructure containers require Compose reconciliation'" in cfg
assert "state_mark reconcile pending 'adaptive runtime/RAM policy changed; complete stack requires Compose reconciliation'" in cfg
assert 'Adaptive runtime/RAM policy is already current.' in cfg

# v14.4.6 CPU audit fix remains present; a 14.4.5 -> 14.4.6 repair can adopt this file
# without a managed image/source refresh when its current adaptive-policy state is healthy.
if VERSION == '14.6.0':
    assert 'def visible_cpu_count() -> int:' in arch
    assert 'os.sched_getaffinity(0)' in arch
    assert 'cpus = visible_cpu_count()' in arch
    assert 'probe_hardware' in audit and 'classify_backends' in audit
else:
    assert 'def visible_cpu_count() -> int:' in audit
    assert 'os.sched_getaffinity(0)' in audit
    assert 'current_cpus = visible_cpu_count()' in audit

# Current documentation must make both upgrade paths explicit.
docs = '\n'.join([
    (ROOT.parent / 'README.md').read_text(encoding='utf-8'),
    (ROOT.parent / 'docs/README.md').read_text(encoding='utf-8'),
    (ROOT.parent / 'docs/PATCH-NOTES.md').read_text(encoding='utf-8'),
])
assert '14.4.5→14.4.6' in docs
assert '14.4.2→14.4.6' in docs
assert 'bundle-version change' in docs

print('v14.4.6 upgrade refresh-gating fixtures: PASS')
