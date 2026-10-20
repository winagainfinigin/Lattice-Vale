#!/usr/bin/env python3
"""Regression coverage for accepting only verified live Hermes convergence."""
from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import sys

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
assert "stale" in verify.verify_state(
    {**BASE, "updated_at": (NOW - timedelta(seconds=121)).isoformat()},
    5799,
    ["default", "assistant"],
    NOW,
)
assert "missing from live served_profiles" in verify.verify_state(
    {**BASE, "served_profiles": ["default"]}, 5799, ["default", "assistant"], NOW
)
assert "does not match" in verify.verify_state(BASE, 5800, ["default", "assistant"], NOW)
# An explicitly standalone profile is deliberately omitted from the expected set.
assert verify.verify_state(BASE, 5799, ["default"], NOW) is None

CONFIGURE = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
MANAGE = (ROOT / "stack/manage.sh").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8")
INSTALLER = (ROOT / "Install-LatticeVale.ps1").read_text(encoding="utf-8-sig")
assert "gateway.get('standalone') is not True: print(name)" in CONFIGURE
assert '| tee;' in CONFIGURE
assert CONFIGURE.index("< gateway-multiplex-verify.py") < CONFIGURE.index("default_s6_status_after=")
assert BOOTSTRAP.count("gateway-multiplex-verify.py") >= 5
assert BOOTSTRAP.count("configure-stack.sh gateway-multiplex-verify.py manage.sh") == 2
assert '"$bundle_root/stack/gateway-multiplex-verify.py" "$stack_dir/gateway-multiplex-verify.py"' in BOOTSTRAP
assert '"$stack_dir/configure-stack.sh" "$stack_dir/gateway-multiplex-verify.py" "$stack_dir/manage.sh"' in BOOTSTRAP
assert "'stack\\gateway-multiplex-verify.py'" in INSTALLER
assert "'configure-stack.sh','gateway-multiplex-verify.py','manage.sh'" in INSTALLER
expected_scan_start = CONFIGURE.index("if ! multiplex_profiles_text=")
expected_profile_scan = CONFIGURE[
    expected_scan_start : CONFIGURE.index('default_s6_status="', expected_scan_start)
]
assert 'if ! multiplex_profiles_text="$(python3 - data/hermes' in expected_profile_scan
assert "has no config.yaml; cannot verify migration" in expected_profile_scan
assert "config.yaml is not a mapping" in expected_profile_scan
assert "gateway settings are malformed" in expected_profile_scan
assert "Unable to determine the complete managed gateway profile set" in expected_profile_scan
failed_migration_branch_start = CONFIGURE.index(
    "if (( migration_rc != 0 )); then", CONFIGURE.index("multiplex_profiles=()")
)
success_migration_branch = CONFIGURE.index("gateway_status=", failed_migration_branch_start)
failed_migration_branch = CONFIGURE[failed_migration_branch_start:success_migration_branch]
assert "< gateway-multiplex-verify.py" in failed_migration_branch
assert "Default gateway s6 PID changed during live-state verification" in failed_migration_branch
success_migration_path = CONFIGURE[success_migration_branch:CONFIGURE.index(": > .installer-gateway-multiplex-owned", success_migration_branch)]
assert "gateway migration returned success, but gateway status could not be read" in success_migration_path
assert "PY_VERIFY_SERVED_PROFILES" in success_migration_path
assert "default s6 PID" in VERIFY_PATH.read_text(encoding="utf-8")

managed_roster_start = MANAGE.index("managed_multiplex_profiles_manage() {")
managed_roster_end = MANAGE.index("verify_live_multiplex_gateway_manage() {", managed_roster_start)
managed_roster = MANAGE[managed_roster_start:managed_roster_end]
assert "expected={'default'}" in managed_roster
assert "gateway.get('standalone') is not True" in managed_roster
assert "has no config.yaml" in managed_roster
assert "gateway settings are malformed" in managed_roster

startup_start = MANAGE.index("start_selected_matrix_profile_gateways() {")
startup_end = MANAGE.index("\n}\n", startup_start)
startup = MANAGE[startup_start:startup_end]
migration_call = startup.index("hermes gateway migrate --multiplex -y")
assert "gateway_migration.json" in startup[:migration_call]
assert ".installer-gateway-multiplex-owned" in startup[:migration_call]
assert "verify_live_multiplex_gateway_manage" in startup[:migration_call]
assert "2>&1 | tee; then" in startup[migration_call:migration_call + 180]
assert "exit 10" in startup[:migration_call]
assert "migration_manifest_rc != 10" in startup[:migration_call]
assert "migration_rc=$?" in startup[migration_call:]
assert "if ! verify_live_multiplex_gateway_manage; then" in startup[migration_call:]
assert "preserving Hermes migration state" in startup
assert "rm -f /opt/data/gateway_migration.json" not in MANAGE
print("PASS live convergence, stale heartbeat, missing profile, PID mismatch, standalone exclusion, and startup resume recovery")
