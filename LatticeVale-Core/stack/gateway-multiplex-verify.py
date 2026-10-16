#!/usr/bin/env python3
"""Validate live Hermes gateway state before accepting migration convergence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


MAX_HEARTBEAT_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 30


def verify_state(state, s6_pid, expected_profiles, now=None):
    """Return a diagnostic string on failure, otherwise None."""
    if not isinstance(state, dict):
        return "gateway_state.json is not a JSON object"
    if state.get("gateway_state") != "running":
        return "gateway_state is not 'running'"
    try:
        live_pid = int(state.get("pid"))
        supervisor_pid = int(s6_pid)
    except (TypeError, ValueError):
        return "gateway state PID or default s6 PID is invalid"
    if live_pid != supervisor_pid:
        return f"gateway_state PID {live_pid} does not match default s6 PID {supervisor_pid}"

    updated_at = state.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        return "gateway_state heartbeat timestamp is missing"
    try:
        heartbeat = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return "gateway_state heartbeat timestamp is invalid"
    if heartbeat.tzinfo is None:
        return "gateway_state heartbeat timestamp has no timezone"
    current_time = now or datetime.now(timezone.utc)
    age = (current_time - heartbeat.astimezone(timezone.utc)).total_seconds()
    if age > MAX_HEARTBEAT_AGE_SECONDS:
        return f"gateway_state heartbeat is stale ({int(age)}s old; limit {MAX_HEARTBEAT_AGE_SECONDS}s)"
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return f"gateway_state heartbeat is {int(-age)}s in the future"

    served = state.get("served_profiles")
    if not isinstance(served, list) or any(not isinstance(name, str) for name in served):
        return "gateway_state served_profiles is missing or malformed"
    missing = sorted(set(expected_profiles) - set(served))
    if missing:
        return "missing from live served_profiles: " + ", ".join(missing)
    return None


def main(argv):
    if len(argv) < 2:
        print("usage: gateway-multiplex-verify.py STATE_JSON S6_PID [EXPECTED_PROFILE ...]", file=sys.stderr)
        return 2
    try:
        state = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read gateway state: {exc}", file=sys.stderr)
        return 1
    diagnostic = verify_state(state, argv[1], argv[2:])
    if diagnostic:
        print(diagnostic, file=sys.stderr)
        return 1
    print("Verified fresh default s6 gateway PID and served profile set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
