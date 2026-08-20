#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = (ROOT / "LatticeVale-Core/stack/configure-stack.sh").read_text(encoding="utf-8")
BOOT = (ROOT / "LatticeVale-Core/linux/bootstrap.sh").read_text(encoding="utf-8")

# An optional Matrix profile must never make global configuration fail merely because
# its bounded activation retry or dedicated gateway cannot complete.
assert './manage.sh matrix-profile-finish "$matrix_profile" || return 1' not in CONF
assert 'Matrix profile \'$matrix_profile\' remains pending; skipping its gateway reconciliation without blocking the core stack.' in CONF
assert 'Matrix profile \'$matrix_profile\' gateway could not be started; preserving profile state without blocking the core stack.' in CONF

# Startup runs with `set -Eeuo pipefail`; missing adaptive state must be handled explicitly
# so it reaches the refresh path instead of exiting on a failed sed pipeline.
assert 'if [[ -s "\\$stack_dir/.latticevale-resource-state" ]]; then' in BOOT
assert "saved_version=''" in BOOT
assert "saved_cpus=''" in BOOT
assert "saved_mem=''" in BOOT

# Plugin enforcement must not be documented as universal when upstream hook coverage can
# vary by execution surface. Prompt policy is retained as a fallback.
assert '# Hard guard for model-driven Kanban creation.' not in CONF
assert 'if not bound and args.get("triage") is not True:' in CONF
assert 'return _modify(triage=True)' in CONF
assert 'shallow argument' in CONF and 'ambiguous or' in CONF


# Every secondary-profile gateway/cross-signing failure is isolated from global setup.
assert 'Matrix gateway did not become running." >&2; return 1' not in CONF
assert "Matrix profile '$name' credentials are incomplete.\" >&2; return 1" not in CONF
assert "Fresh Matrix profile '$name' did not emit its one-time recovery key." in CONF
assert 'skipping this profile without destructive recovery.' in CONF
assert 'gateway reload after cross-signing failed; recovery state is safely persisted' in CONF

print('backport online-audit fixtures: PASS')
