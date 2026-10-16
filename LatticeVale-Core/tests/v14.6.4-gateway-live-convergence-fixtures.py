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
assert "gateway.get('standalone') is not True: print(name)" in CONFIGURE
assert '| tee;' in CONFIGURE
assert CONFIGURE.index("< gateway-multiplex-verify.py") < CONFIGURE.index("default_s6_status_after=")
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
print("PASS live convergence, stale heartbeat, missing profile, PID mismatch, explicit standalone exclusion")
