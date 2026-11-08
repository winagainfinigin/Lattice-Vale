#!/usr/bin/env python3
"""Prove live Hermes gateway state against its exact s6-supervised process."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

MAX_HEARTBEAT_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 30
MAX_BIRTH_CLOCK_SKEW_SECONDS = 2


def process_birth_epoch(pid, proc_root=Path('/proc')):
    """Return kernel process-birth UTC epoch, or None if it cannot be proven.

    Both files are read in the container's PID namespace; a host's /proc cannot
    establish the birth of a container PID. /proc/PID/stat starttime is field 22.
    """
    try:
        stat = (proc_root / str(int(pid)) / 'stat').read_text(encoding='ascii')
        ending = stat.rfind(')')
        if ending < 0:
            return None
        fields = stat[ending + 1:].split()  # starts at stat field 3 (state)
        ticks = int(fields[19])               # field 22: starttime
        if ticks < 0:
            return None
        boot = None
        for line in (proc_root / 'stat').read_text(encoding='ascii').splitlines():
            if line.startswith('btime '):
                boot = int(line.split()[1])
                break
        hz = os.sysconf('SC_CLK_TCK')
        if boot is None or hz <= 0:
            return None
        return boot + ticks / hz
    except (OSError, IndexError, TypeError, ValueError, OverflowError):
        return None


def verify_state(state, s6_pid, expected_profiles, now=None, platform_key=None, process_start_epoch=None):
    """Return a diagnostic on failure, or None; stale records require PID-birth proof."""
    if not isinstance(state, dict):
        return 'gateway_state.json is not a JSON object'
    if state.get('gateway_state') != 'running':
        return "gateway_state is not 'running'"
    try:
        live_pid = int(state.get('pid'))
        supervisor_pid = int(s6_pid)
        if live_pid < 1 or supervisor_pid < 1:
            raise ValueError('non-positive PID')
    except (TypeError, ValueError, OverflowError):
        return 'gateway state PID or default s6 PID is invalid'
    if live_pid != supervisor_pid:
        return f'gateway_state PID {live_pid} does not match default s6 PID {supervisor_pid}'

    updated_at = state.get('updated_at')
    if not isinstance(updated_at, str) or not updated_at.strip():
        return 'gateway_state heartbeat timestamp is missing'
    try:
        heartbeat = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
    except (TypeError, ValueError, OverflowError):
        return 'gateway_state heartbeat timestamp is invalid'
    if heartbeat.tzinfo is None:
        return 'gateway_state heartbeat timestamp has no timezone'
    current_time = now if now is not None else datetime.now(timezone.utc)
    age = (current_time - heartbeat.astimezone(timezone.utc)).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return f'gateway_state heartbeat is {int(-age)}s in the future'
    if age > MAX_HEARTBEAT_AGE_SECONDS:
        # Hermes advances updated_at on state transitions, not periodically while
        # idle. A kernel birth time newer than the record indicates a recycled
        # PID/old record; missing evidence fails closed.
        birth = process_start_epoch if process_start_epoch is not None else process_birth_epoch(live_pid)
        if birth is None or birth > heartbeat.timestamp() + MAX_BIRTH_CLOCK_SKEW_SECONDS:
            return f'gateway_state heartbeat is stale ({int(age)}s old; kernel process-birth proof failed)'

    served = state.get('served_profiles')
    # Standalone Matrix gateways need not publish a multiplex roster. Shared
    # gateway checks still require the roster, even with zero extra profiles.
    if platform_key is None or expected_profiles or served is not None:
        if not isinstance(served, list) or any(not isinstance(name, str) for name in served):
            return 'gateway_state served_profiles is missing or malformed'
        missing = sorted(set(expected_profiles) - set(served))
        if missing:
            return 'missing from live served_profiles: ' + ', '.join(missing)
    if platform_key is not None:
        platforms = state.get('platforms')
        row = platforms.get(platform_key) if isinstance(platforms, dict) else None
        if not isinstance(row, dict) or str(row.get('state') or '').strip().lower() != 'connected':
            return f'gateway platform {platform_key!r} is not connected'
    return None


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', dest='platform_key')
    parser.add_argument('state_file', type=Path)
    parser.add_argument('s6_pid')
    parser.add_argument('expected_profiles', nargs='*')
    args = parser.parse_args(argv)
    try:
        state = json.loads(args.state_file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        print(f'cannot read gateway state: {exc}', file=sys.stderr)
        return 1
    diagnostic = verify_state(state, args.s6_pid, args.expected_profiles,
                              platform_key=args.platform_key)
    if diagnostic:
        print(diagnostic, file=sys.stderr)
        return 1
    print('Verified live default s6 gateway PID, state and requested platforms/profiles.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
