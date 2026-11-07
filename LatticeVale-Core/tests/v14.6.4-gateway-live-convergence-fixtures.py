#!/usr/bin/env python3
"""Regression coverage for verified, idempotent Hermes shared-gateway convergence."""
from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import sys
import tempfile
import json

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "stack/gateway-multiplex-verify.py"
spec = importlib.util.spec_from_file_location("gateway_multiplex_verify", VERIFY_PATH)
verify = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(verify)

NOW = datetime(2026, 10, 15, 23, 3, 4, tzinfo=timezone.utc)
BASE = {
    "gateway_state": "running",
    "pid": 5799,
    "updated_at": NOW.isoformat(),
    "served_profiles": ["default", "assistant"],
}
assert verify.verify_state(BASE, 5799, ["default", "assistant"], NOW) is None
assert "stale" in verify.verify_state({**BASE, "updated_at": (NOW - timedelta(seconds=121)).isoformat()}, 5799, ["default", "assistant"], NOW)
assert "missing from live served_profiles" in verify.verify_state({**BASE, "served_profiles": ["default"]}, 5799, ["default", "assistant"], NOW)
assert "does not match" in verify.verify_state(BASE, 5800, ["default", "assistant"], NOW)
# Explicit standalone profiles are deliberately omitted from the shared expected set.
assert verify.verify_state(BASE, 5799, ["default"], NOW) is None

CONFIGURE = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
MANAGE = (ROOT / "stack/manage.sh").read_text(encoding="utf-8")
AUDIT = (ROOT / "stack/state-audit.py").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8")
INSTALLER = (ROOT / "Install-LatticeVale.ps1").read_text(encoding="utf-8-sig")

# Upstream Hermes dynamically registers gateways beneath a hermes-owned nested s6 tree.
# Root's /run/service scandir is for static s6-rc services and must never be used for
# dynamic gateway lifecycle, health, or audit operations.
for script in (CONFIGURE, MANAGE, AUDIT):
    assert '/run/service/gateway-' not in script
    assert '/run/hermes-service/gateway-' in script
for script in (CONFIGURE, MANAGE):
    assert 'register_profile_gateway(name, start_now=False)' in script
    assert 'S6_DYNAMIC_SCANDIR' in script
    assert 'docker exec -u hermes hermes-agent /command/s6-svc' in script
    assert 'docker exec hermes-agent /command/s6-svc' not in script
    assert 'Hermes dynamic gateway registration failed (' in script
    assert '"$name" >/dev/null; then' in script
assert 'f"/run/hermes-service/gateway-{name}"' in AUDIT

# The parked-marker fix works for arbitrary named profiles (including 14.6.5
# upgrades). LatticeVale-owned stop receipts are durable; legacy/unowned markers
# require an explicit approval; user standalone/unmanaged markers stay untouched.
import subprocess
import os
from pathlib import Path as _Path
PARK_POLICY = ROOT / "stack/gateway-park-policy.py"
assert PARK_POLICY.is_file()
assert "profile_is_parked" not in PARK_POLICY.read_text(encoding="utf-8") or "gateway.parked" in PARK_POLICY.read_text(encoding="utf-8")
assert BOOTSTRAP.count("gateway-park-policy.py") >= 4
assert "'stack\\gateway-park-policy.py'" in INSTALLER
for script in (CONFIGURE, MANAGE):
    assert 'gateway-park-policy.py prepare-stop' in script
    assert 'gateway-park-policy.py reconcile' in script
    assert 'gateway-park-policy.py pending' in script

with tempfile.TemporaryDirectory() as td:
    td = _Path(td)
    hermes = td / "data/hermes"
    roster = td / ".installer-managed-profiles"
    hermes.mkdir(parents=True)
    # Three active named profiles + one explicitly standalone profile, plus an
    # unrelated user profile: no assumptions about exactly two profiles.
    names = ("assistant", "coder", "reviewer", "observer")
    roster.write_text("\n".join(names) + "\n", encoding="utf-8")
    for name in (*names, "outside"):
        home = hermes / "profiles" / name
        home.mkdir(parents=True)
        standalone = "'true'" if name == "observer" else "false"
        (home / "config.yaml").write_text("gateway:\n  standalone: " + standalone + "\n", encoding="utf-8")
    def policy(*args, ok=True):
        proc = subprocess.run(
            [sys.executable, str(PARK_POLICY), args[0], str(hermes), str(roster), *args[1:]],
            text=True, capture_output=True, cwd=td, timeout=10,
        )
        assert (proc.returncode == 0) == ok, proc.stdout + proc.stderr
        return proc.stdout if ok else proc.stderr
    # Ownership is recorded before the CLI stop writes gateway.parked.
    for name in ("assistant", "reviewer"):
        policy("prepare-stop", "--name", name)
        (hermes / "profiles" / name / "gateway.parked").write_text("", encoding="utf-8")
    # A 14.6.5/14.6.6 stop without ownership proof and two user stops.
    for name in ("coder", "observer", "outside"):
        (hermes / "profiles" / name / "gateway.parked").write_text("", encoding="utf-8")
    receipt = td / ".installer-owned-gateway-parks.json"
    assert sorted(json.loads(receipt.read_text())["names"]) == ["assistant", "reviewer"]
    before = json.loads(policy("pending"))
    assert before == {"owned": ["assistant", "reviewer"], "legacy": ["coder"]}, before
    assert "explicit approval" in policy("reconcile", ok=False)
    assert all((hermes / "profiles" / name / "gateway.parked").exists() for name in names)
    out = policy("reconcile", "--approve-legacy")
    assert all("Unparked managed profile: " + name in out for name in ("assistant", "coder", "reviewer")), out
    assert json.loads(policy("pending")) == {"owned": [], "legacy": []}
    assert not any((hermes / "profiles" / name / "gateway.parked").exists() for name in ("assistant", "coder", "reviewer"))
    assert all((hermes / "profiles" / name / "gateway.parked").exists() for name in ("observer", "outside"))
    assert json.loads(receipt.read_text())["names"] == []
    # A newly stopped managed profile can unpark without legacy approval.
    policy("prepare-stop", "--name", "assistant")
    (hermes / "profiles/assistant/gateway.parked").touch()
    assert "Unparked managed profile: assistant" in policy("reconcile")
    # Existing user marker is NEVER claimed by prepare-stop.
    (hermes / "profiles/assistant/gateway.parked").touch()
    policy("prepare-stop", "--name", "assistant")
    assert json.loads(policy("pending"))["legacy"] == ["assistant"]
    assert "explicit approval" in policy("reconcile", ok=False)
    # Invalid name and symlink cannot escape the controlled managed profile home.
    assert "not installer-managed" in policy("prepare-stop", "--name", "outside", ok=False)
    (hermes / "profiles/assistant/gateway.parked").unlink()
    (hermes / "profiles/assistant/gateway.parked").symlink_to(td / "elsewhere")
    assert "unsafe parked marker" in policy("pending", ok=False)

# The verifier is release content and is staged into every managed stack.
assert BOOTSTRAP.count("gateway-multiplex-verify.py") >= 5
assert '"$bundle_root/stack/gateway-multiplex-verify.py" "$stack_dir/gateway-multiplex-verify.py"' in BOOTSTRAP
assert "'stack\\gateway-multiplex-verify.py'" in INSTALLER
assert "default s6 PID" in VERIFY_PATH.read_text(encoding="utf-8")

# Canonical durable configuration: only default may keep Hermes' nested true setting.
verify_integrations = CONFIGURE[CONFIGURE.index("verify_integrations() {"):CONFIGURE.index("verify_reconcile() {")]
assert "paths=[('default',root/'config.yaml')]" in verify_integrations
assert "cfg.get('multiplex_profiles') is not None" in verify_integrations
assert "name == 'default' and multiplex_value is True" in verify_integrations
assert "name != 'default' or value != 'true'" in verify_integrations
clone = CONFIGURE[CONFIGURE.index("PY_PROFILE_SAFE_CLONE"):CONFIGURE.index("PY_PROFILE_SAFE_CLONE", CONFIGURE.index("PY_PROFILE_SAFE_CLONE") + 1)]
assert "not line.startswith('GATEWAY_MULTIPLEX_PROFILES=')" in clone

# The ever-managed roster may contain a profile whose whole directory was later removed;
# that must not deadlock repair. A partially present profile directory without config remains an error.
configure_roster = CONFIGURE[CONFIGURE.index("managed_multiplex_profiles_configure() {"):CONFIGURE.index("verify_live_multiplex_gateway_configure() {")]
manage_roster = MANAGE[MANAGE.index("managed_multiplex_profiles_manage() {"):MANAGE.index("verify_live_multiplex_gateway_manage() {")]
for roster in (configure_roster, manage_roster):
    assert "if path.parent.exists(): raise SystemExit" in roster
    assert "exists but has no config.yaml" in roster
    assert "continue" in roster

# Speculative checkpoint verification must be silent. A stopped/settling service is
# a reason to run its stage, not a user-visible installer failure. Post-stage verification
# remains unsuppressed and therefore retains authoritative diagnostics.
run_stage = CONFIGURE[CONFIGURE.index("run_stage() {"):CONFIGURE.index("http_status_ok() {")]
assert 'state_stage_current "$stage" && "$verifier" >/dev/null 2>&1' in run_stage
assert 'state_stage_legacy_adoptable "$stage" && "$verifier" >/dev/null 2>&1' in run_stage
post_verify = run_stage[run_stage.index('"$action"'):]
assert 'if ! "$verifier"; then' in post_verify
assert 'if ! "$verifier" >/dev/null' not in post_verify

# Same-version Resume/repair must prove an already-converged live gateway before migration.
reconcile = CONFIGURE[CONFIGURE.index("stage_reconcile() {"):CONFIGURE.index("stage_kanban_gateway() {")]
first_live_check = reconcile.index("wait_live_multiplex_gateway_configure \"$convergence_wait\"")
migration_call = reconcile.index("hermes gateway migrate --multiplex -y")
assert first_live_check < migration_call
assert "already live and serves every managed non-standalone profile" in reconcile[:migration_call]
assert "if ! wait_live_multiplex_gateway_configure 45; then" in reconcile[migration_call:]
assert "90-second safety timeout" in reconcile
assert "timed out after the gateway had converged" in reconcile
assert ": > .installer-gateway-multiplex-owned" in reconcile
assert reconcile.index(": > .installer-gateway-multiplex-owned") > reconcile.index("wait_live_multiplex_gateway_configure 45", migration_call)
assert "Default Hermes Matrix adapter is already connected; preserving the healthy gateway without an unnecessary restart." in reconcile
assert reconcile.index("wait_matrix_adapter_runtime_configure default data/hermes/gateway_state.json matrix 3") < reconcile.index("start_or_restart_default_gateway_exact")

# Checkpoint adoption itself also requires the marker plus exact live convergence.
verify_reconcile = CONFIGURE[CONFIGURE.index("verify_reconcile() {"):CONFIGURE.index("verify_kanban_gateway() {")]
assert "shared-gateway ownership marker is missing" in verify_reconcile
assert "verify_live_multiplex_gateway_configure" in verify_reconcile
assert "default Hermes Matrix adapter is not live and connected" in verify_reconcile
assert "verify_matrix_adapter_runtime_configure default data/hermes/gateway_state.json matrix" in verify_reconcile

# Ordinary start treats the marker as evidence, not health proof, and only migrates after a failed live proof.
startup = MANAGE[MANAGE.index("start_selected_matrix_profile_gateways() {"):MANAGE.index("refresh_adaptive_resource_policy() {")]
assert startup.index("wait_live_multiplex_gateway_manage \"$convergence_wait\"") < startup.index("hermes gateway migrate --multiplex -y")
assert "ownership marker is not backed by current live convergence" in startup
assert "restoring the LatticeVale ownership marker without replaying migration" in startup
assert "if ! wait_live_multiplex_gateway_manage 45; then" in startup
assert startup.index(": > .installer-gateway-multiplex-owned") > startup.index("hermes gateway migrate --multiplex -y")
assert "90-second safety timeout" in startup
assert "timed out after the gateway had converged" in startup

# Explicit standalone named profiles stay independent; non-standalone Matrix profiles stay shared.
assert "profile_gateway_is_explicit_standalone_manage" in startup
assert "Standalone profile gateway running with Matrix adapter verified" in startup
assert "Matrix profile served by verified shared gateway with Matrix adapter connected" in startup
assert "Default Hermes Matrix adapter is already connected; preserving the healthy gateway without an unnecessary restart." in startup
assert "wait_matrix_adapter_runtime_manage default data/hermes/gateway_state.json matrix 3" in startup
assert 'wait_matrix_adapter_runtime_manage default data/hermes/gateway_state.json "$name:matrix"' in startup
kanban = CONFIGURE[CONFIGURE.index("stage_kanban_gateway() {"):CONFIGURE.index("stage_finalize() {")]
assert "profile_gateway_is_explicit_standalone_configure" in kanban
assert "served by the verified shared Hermes host gateway with its Matrix adapter connected" in kanban
assert "wait_matrix_adapter_runtime_configure default data/hermes/gateway_state.json matrix 30" in kanban
assert 'wait_matrix_adapter_runtime_configure default data/hermes/gateway_state.json "$matrix_profile:matrix" 30' in kanban

# Audit semantics use authoritative s6 + runtime state and namespaced adapter state.
assert "verify_shared_gateway_runtime" in AUDIT
assert "verify_standalone_gateway_runtime" in AUDIT
assert 'f"{name}:matrix"' in AUDIT
assert "Hermes shared host gateway is durably configured and live-verified" in AUDIT
assert "explicit standalone gateway" in AUDIT
assert "independent gateway running" not in AUDIT
assert "gateway.multiplex_profiles: true" in AUDIT
verify_kanban = CONFIGURE[CONFIGURE.index("verify_kanban_gateway() {"):CONFIGURE.index("verify_finalize() {")]
assert "verify_matrix_adapter_runtime_configure default data/hermes/gateway_state.json matrix" in verify_kanban
assert 'verify_matrix_adapter_runtime_configure default data/hermes/gateway_state.json "$matrix_profile:matrix"' in verify_kanban
assert 'verify_matrix_adapter_runtime_configure "$matrix_profile" "data/hermes/profiles/$matrix_profile/gateway_state.json" matrix' in verify_kanban

# Exercise the audit helpers directly: default nested true is valid, worker true is not;
# shared and standalone live records require exact/stable s6 PID and fresh heartbeat.
audit_spec = importlib.util.spec_from_file_location("state_audit", ROOT / "stack/state-audit.py")
audit = importlib.util.module_from_spec(audit_spec)
assert audit_spec and audit_spec.loader
audit_spec.loader.exec_module(audit)
with tempfile.TemporaryDirectory() as td:
    stack = Path(td)
    default_cfg = stack / "data/hermes/config.yaml"
    worker_cfg = stack / "data/hermes/profiles/assistant/config.yaml"
    default_cfg.parent.mkdir(parents=True)
    worker_cfg.parent.mkdir(parents=True)
    default_cfg.write_text("gateway:\n  multiplex_profiles: true\n", encoding="utf-8")
    worker_cfg.write_text("gateway:\n  multiplex_profiles: true\n", encoding="utf-8")
    assert audit.yaml_multiplex_enabled(default_cfg) is False
    assert audit.yaml_multiplex_enabled(worker_cfg) is True
    worker_cfg.write_text("gateway:\n  standalone: true\n", encoding="utf-8")
    assert audit.yaml_gateway_standalone(worker_cfg) is True

    now = datetime.now(timezone.utc).isoformat()
    shared_record = {
        "gateway_state": "running", "pid": 5799, "updated_at": now,
        "served_profiles": ["default", "assistant"],
        "platforms": {"assistant:matrix": {"state": "connected"}},
    }
    (stack / "data/hermes/gateway_state.json").write_text(json.dumps(shared_record), encoding="utf-8")
    standalone_record = {
        "gateway_state": "running", "pid": 5800, "updated_at": now,
        "platforms": {"matrix": {"state": "connected"}},
    }
    (stack / "data/hermes/profiles/assistant/gateway_state.json").write_text(json.dumps(standalone_record), encoding="utf-8")
    def fake_run(cmd, cwd=None, timeout=8):
        joined = " ".join(cmd)
        if "/run/hermes-service/gateway-default" in joined:
            return 0, "up (pid 5799 pgid 5799) 1 seconds"
        if "/run/hermes-service/gateway-assistant" in joined:
            return 0, "up (pid 5800 pgid 5800) 1 seconds"
        return 127, ""
    audit.run = fake_run
    ok, _, record = audit.verify_shared_gateway_runtime(stack, {"default", "assistant"})
    assert ok and audit.gateway_platform_state(record, "assistant:matrix") == "connected"
    ok, _, record = audit.verify_standalone_gateway_runtime(stack, "assistant")
    assert ok and audit.gateway_platform_state(record, "matrix") == "connected"

# Existing profiles are not recreated or safe-cloned during same-version repair, which
# preserves user-owned filesystem layout such as an existing profile skills symlink.
profile_stage = CONFIGURE[CONFIGURE.index("stage_profiles() {"):CONFIGURE.index("stage_matrix_profiles()") ]
create_guard = profile_stage.index('if [[ ! -d "data/hermes/profiles/$name" ]]; then')
clone_block = profile_stage.index("PY_PROFILE_SAFE_CLONE", create_guard)
existing_branch = profile_stage.index("  else", clone_block)
assert create_guard < clone_block < existing_branch
assert 'rm -rf "data/hermes/profiles/$name/skills"' not in profile_stage

# Policy key remains compatibility-named, but user-visible current diagnostics must not
# imply that every Matrix-enabled secondary profile owns a resident gateway process.
assert "secondary Matrix profile workload(s)" in CONFIGURE
assert "secondary Matrix gateway(s)" not in CONFIGURE

# Exercise the actual embedded upstream-registration Python body from each shell
# call site with a fake upstream module. This covers registration ownership, an
# already-published exact slot, and error redaction without Docker or networking.
import os
import re
import subprocess
for shell_source in (CONFIGURE, MANAGE):
    bodies = re.findall(r"docker exec -u hermes hermes-agent python -c '\n(.*?)\n' \"\$name\" >/dev/null; then", shell_source, re.S)
    assert len(bodies) == 1, len(bodies)
    body = bodies[0]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        module = td / "hermes_cli"
        module.mkdir()
        (module / "__init__.py").write_text("", encoding="utf-8")
        (module / "service_manager.py").write_text('''
import os
from pathlib import Path
S6_DYNAMIC_SCANDIR = Path(os.environ["TEST_DYNAMIC_SCANDIR"])
def validate_profile_name(name):
    if name not in {"default", "assistant"}: raise ValueError("invalid profile")
def detect_service_manager(): return "s6"
class Manager:
    def supports_runtime_registration(self): return True
    def register_profile_gateway(self, name, *, start_now=True):
        Path(os.environ["TEST_REGISTRATION_RECORD"]).write_text(f"{name}:{start_now}")
        mode = os.environ.get("TEST_REGISTRATION_MODE", "ok")
        if mode == "race":
            (S6_DYNAMIC_SCANDIR / ("gateway-" + name)).mkdir()
            raise ValueError("already registered")
        if mode == "fail":
            raise RuntimeError("SECRET_API_KEY=should-never-appear")
def get_service_manager(): return Manager()
''', encoding="utf-8")
        scan = td / "dynamic"
        scan.mkdir()
        record = td / "registration.txt"
        base_env = {**os.environ, "PYTHONPATH": str(td), "TEST_DYNAMIC_SCANDIR": str(scan), "TEST_REGISTRATION_RECORD": str(record)}
        for name in ("default", "assistant"):
            for mode, expected_code in (("ok", 0), ("race", 0), ("fail", 1)):
                slot = scan / ("gateway-" + name)
                if slot.exists(): slot.rmdir()
                result = subprocess.run([sys.executable, "-c", body, name], env={**base_env, "TEST_REGISTRATION_MODE": mode}, capture_output=True, text=True, timeout=10)
                assert result.returncode == expected_code, (name, mode, result.stderr)
                assert record.read_text() == f"{name}:False", (name, mode, record.read_text())
                assert "SECRET_API_KEY" not in result.stderr, result.stderr
                if mode == "fail":
                    assert "RuntimeError" in result.stderr, result.stderr

print("PASS shared-gateway convergence, quiet speculative verification, bounded settle windows, same-version idempotency, timeout convergence, Matrix routing, explicit standalone preservation, audit live-state semantics, and existing-profile filesystem preservation")
