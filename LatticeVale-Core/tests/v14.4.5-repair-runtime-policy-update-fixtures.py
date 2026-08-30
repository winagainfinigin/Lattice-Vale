#!/usr/bin/env python3
"""v14.4.5 repair runtime-policy and managed-update regressions."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
version = (root / 'VERSION.txt').read_text(encoding='utf-8').strip()
assert version in {'14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1'}, version

cfg = (root / 'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (root / 'stack/manage.sh').read_text(encoding='utf-8')
boot = (root / 'linux/bootstrap.sh').read_text(encoding='utf-8')
compat = (root / 'compatibility.conf').read_text(encoding='utf-8')

# Resume / repair must explicitly reconcile current adaptive policy even when prepare_config has an
# old completed checkpoint. The final installer state must not become complete while
# that live policy is still stale/partial.
for token in (
    'verify_adaptive_runtime_policy() {',
    'repair_runtime_policy_reconcile() {',
    "run_uncheckpointed_repair_step repair_runtime_policy 'Reconcile adaptive runtime/RAM policy' repair_runtime_policy_reconcile",
    "state_mark infrastructure pending 'adaptive runtime/RAM policy changed; selected infrastructure containers require Compose reconciliation'",
    "state_mark reconcile pending 'adaptive runtime/RAM policy changed; complete stack requires Compose reconciliation'",
    'Final repair verification failed: adaptive runtime/RAM policy is still stale or incomplete.',
):
    assert token in cfg, token

# The explicit repair reconciliation must occur after prepare_config but before
# infrastructure, so an old prepare_config checkpoint can no longer swallow policy
# migration and changed Compose settings are applied before infrastructure is verified.
sequence = [
    "run_stage prepare_config 'Prepare installer-owned configuration'",
    "run_uncheckpointed_repair_step repair_runtime_policy 'Reconcile adaptive runtime/RAM policy'",
    "run_stage infrastructure 'Start and verify selected supporting infrastructure'",
]
pos = [cfg.index(x) for x in sequence]
assert pos == sorted(pos), pos

# Policy verification must require the current fingerprint and all v3 RAM controls.
for token in (
    'saved_version" == 9',
    'MALLOC_ARENA_MAX:',
    'SYNAPSE_CACHE_FACTOR:',
    'shared_buffers=',
    'max_connections=200',
    'compose.latticevale.yaml',
):
    assert token in cfg, token

# Execute the exact v14.4.5 verifier/reconciliation functions in a small repair
# harness. This reproduces a stale policy-v2 install and proves reconciliation writes a
# current policy, marks live Compose-owning stages pending, and becomes idempotent.
def between(text: str, start: str, end: str) -> str:
    a = text.index(start)
    b = text.index(end, a)
    return text[a:b]

verify_fn = between(cfg, 'verify_adaptive_runtime_policy() {', 'repair_runtime_policy_reconcile() {')
repair_fn = between(cfg, 'repair_runtime_policy_reconcile() {', 'choose_ollama_context_length() {')
with tempfile.TemporaryDirectory(prefix='lv145-runtime-policy-') as td:
    td = Path(td)
    harness = td / 'harness.sh'
    harness.write_text(
        r'''#!/usr/bin/env bash
set -euo pipefail
opt_bool() {
  case "$1" in
    containerResourceLimits|matrix|honcho) printf true ;;
    *) printf false ;;
  esac
}
managed_ollama_enabled() { return 1; }
resource_matrix_profile_gateways() { printf '0'; }
resource_kanban_concurrency() { printf '1'; }
resource_hermes_floor_mib() { printf '1024'; }
resource_ollama_model_metrics() { printf '0:0:0:0'; }
state_mark() { printf '%s|%s|%s\n' "$1" "$2" "${3:-}" >> state.log; }
write_latticevale_compose_overlay() {
  local cpus mem_mib
  cpus="$(nproc)"
  mem_mib="$(awk '/^MemTotal:/ {print int($2/1024); exit}' /proc/meminfo)"
  cat > .latticevale-resource-state <<EOF
POLICY_VERSION=9
CPUS=$cpus
MEM_MIB=$mem_mib
RESERVE_MIB=1024
BUDGET_MIB=$((mem_mib-1024))
MATRIX_PROFILE_GATEWAYS=0
KANBAN_CONCURRENCY=1
HERMES_MIN_MIB=1024
OLLAMA_TEXT_ARTIFACT_MIB=0
OLLAMA_EMBED_ARTIFACT_MIB=0
OLLAMA_CONTEXT_LENGTH=0
OLLAMA_MODEL_FLOOR_MIB=0
EOF
  cat > compose.latticevale.yaml <<'EOF'
services:
  hermes:
    environment:
      MALLOC_ARENA_MAX: "2"
  synapse-db:
    command: ["postgres", "-c", "shared_buffers=64MB"]
  synapse:
    environment:
      MALLOC_ARENA_MAX: "2"
      SYNAPSE_CACHE_FACTOR: "0.35"
  honcho-db:
    command: ["postgres", "-c", "max_connections=200", "-c", "shared_buffers=64MB"]
  honcho-api:
    environment:
      MALLOC_ARENA_MAX: "2"
EOF
  printf 'COMPOSE_FILE=compose.yaml:compose.latticevale.yaml:compose.override.yaml\n' > .env
}
# Seed the observed legacy condition: old policy fingerprint + completed unrelated config.
printf 'POLICY_VERSION=2\nCPUS=1\nMEM_MIB=1024\n' > .latticevale-resource-state
printf 'COMPOSE_FILE=compose.yaml:compose.override.yaml\n' > .env
'''
        + verify_fn
        + repair_fn
        + r'''
if verify_adaptive_runtime_policy; then
  echo 'stale policy unexpectedly verified' >&2
  exit 20
fi
repair_runtime_policy_reconcile
verify_adaptive_runtime_policy
[[ "$(grep -c '^infrastructure|pending|' state.log)" == 1 ]]
[[ "$(grep -c '^reconcile|pending|' state.log)" == 1 ]]
[[ "$(sed -n 's/^POLICY_VERSION=//p' .latticevale-resource-state)" == 9 ]]
grep -q '^COMPOSE_FILE=compose.yaml:compose.latticevale.yaml:compose.override.yaml$' .env
before="$(wc -l < state.log)"
repair_runtime_policy_reconcile
[[ "$(wc -l < state.log)" == "$before" ]]
''',
        encoding='utf-8',
    )
    r = subprocess.run(['bash', str(harness)], cwd=td, text=True, capture_output=True, timeout=20)
    assert r.returncode == 0, r.stdout + r.stderr

# Normal starts use the same policy version as the generator; do not regenerate older policy
# forever because of a stale v2 comparison constant.
assert './configure-stack.sh --refresh-resource-policy' in manage
assert 'model artifacts/context' in manage

# If manage.sh itself refreshes the policy during restart, it must reconcile Compose
# before restart because `docker compose restart` alone does not apply changed
# environment/command/memory settings.
for token in (
    'RESOURCE_POLICY_CHANGED=false',
    'RESOURCE_POLICY_CHANGED=true',
    "if [[ \"${RESOURCE_POLICY_CHANGED:-false}\" == true ]]; then",
    "docker compose up -d --pull never --no-build",
    'Adaptive resource policy changed; reconciling Compose before restart',
):
    assert token in manage, token

# v14.4.5 originally used bundle-version mismatch as an immediate refresh trigger.
# v14.4.6 supersedes that behavior: VERSION.txt remains provenance only, while the
# explicit managed-refresh revision/age/legacy-state gate decides ordinary repair.
assert 'last_refresh_installer_version=' in boot
assert 'MANAGED_REPAIR_REFRESH_REVISION=2' in compat
if version == '14.4.5':
    assert '[[ "$last_refresh_installer_version" != "$installer_version" ]]' in boot
    assert 'Managed repair package/image/source refresh is due because the LatticeVale bundle changed' in boot
else:
    assert '[[ "$last_refresh_installer_version" != "$installer_version" ]]' not in boot
    assert 'Managed repair package/image/source refresh is due because the LatticeVale bundle changed' not in boot
    assert 'bundle changed since the last managed component refresh' in boot
    assert 'managed-refresh policy revision $repair_refresh_revision is unchanged and the age gate is not due' in boot

# Interrupted refresh state remains provenance-aware, but v14.4.6 repeats root package
# work only for an incompatible refresh-policy revision, not a version-only bundle bump.
for token in (
    'pending_refresh_installer_version=',
    'pending_refresh_revision=',
    'repair_root_refresh_needed=true',
    "printf 'POLICY_REVISION=%s\\nINSTALLER_VERSION=%s\\n' \"$repair_refresh_revision\" \"$installer_version\" > \"$repair_refresh_pending_file\"",
):
    assert token in boot, token
if version == '14.4.5':
    assert '[[ "$pending_refresh_revision" == "$repair_refresh_revision" && "$pending_refresh_installer_version" == "$installer_version" ]]' in boot
else:
    assert '[[ "$pending_refresh_revision" == "$repair_refresh_revision" ]]' in boot
    assert 'compatible refresh policy revision' in boot
    assert 'different/legacy refresh policy' in boot

# A pending managed refresh must bypass the relevant old checkpoints and actually use
# network-aware bounded update paths for installer-owned components.
assert 'prepare_config|infrastructure) repair_package_refresh_pending' in cfg
assert 'provider_setup) [[ "$(opt_bool forceProviderSetup)" == true ]] || repair_package_refresh_pending' in cfg
assert 'profiles) [[ "$(opt_bool forceProfileSetup)" == true ]] || repair_package_refresh_pending' in cfg
assert 'docker compose pull --ignore-buildable' in cfg
assert 'docker compose build --pull qmd' in cfg
assert 'docker compose build --pull honcho-api' in cfg
assert 'docker pull "$hermes_image"' in cfg
assert 'complete_repair_package_refresh' in cfg

# User Compose overrides remain authoritative after the regenerated installer overlay.
assert "compose_files+=':compose.latticevale.yaml'" in cfg
assert "compose_files+=':compose.override.yaml'" in cfg
assert cfg.index("compose_files+=':compose.latticevale.yaml'") < cfg.index("compose_files+=':compose.override.yaml'")

# Current public docs must describe the same repair/update behavior being tested.
docs = {
    'root': (root.parent / 'README.md').read_text(encoding='utf-8'),
    'features': (root.parent / 'docs/FEATURES.md').read_text(encoding='utf-8'),
    'support': (root.parent / 'docs/SUPPORT.md').read_text(encoding='utf-8'),
    'instructions': (root.parent / 'docs/Instructions.txt').read_text(encoding='utf-8'),
    'matrix': (root.parent / 'docs/WINDOWS-INTEGRATION-TEST-MATRIX.md').read_text(encoding='utf-8'),
}
if version == '14.4.5':
    assert 'different LatticeVale bundle' in docs['root']
else:
    assert 'bundle-version change by itself' in docs['root']
    assert 'bundle-version change alone does not force a refresh' in docs['features']
    assert 'bundle-version change alone' in docs['support']
    assert 'bundle-version change alone remains local-first' in docs['instructions']
    assert '14.4.2-style revision-1 state triggers' in docs['matrix']

print('v14.4.5 repair runtime-policy/update fixtures: PASS')
