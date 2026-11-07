#!/usr/bin/env python3
"""Preservation-first ownership for Hermes gateway.parked markers.

The upstream `hermes -p NAME gateway stop` persistently parks NAME. An
installer-requested quiesce must not silently disable the multiplexing target.
Legacy 14.6.5/14.6.6 markers without ownership proof require consent.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile

import yaml

NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")
RECORD = ".installer-owned-gateway-parks.json"


def fail(message: str) -> None:
    raise SystemExit("Gateway park reconciliation refused: " + message)


def checked_profile(root: Path, name: str) -> Path:
    if not NAME.fullmatch(name) or name == "default":
        fail("invalid named-profile identity")
    home = root / "profiles" / name
    if home.is_symlink() or not home.is_dir():
        fail("profile home missing or symlink: " + name)
    cfg = home / "config.yaml"
    if cfg.is_symlink() or not cfg.is_file():
        fail("profile config missing or symlink: " + name)
    return home


def managed_names(roster: Path) -> set[str]:
    if roster.is_symlink() or not roster.is_file():
        fail("installer-managed profile roster missing or symlink")
    names = set(roster.read_text(encoding="utf-8").splitlines()) - {""}
    if any(not NAME.fullmatch(n) or n == "default" for n in names):
        fail("invalid name in managed profile roster")
    return names


def load_owned(path: Path) -> set[str]:
    if path.is_symlink():
        fail("ownership record is a symlink")
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("names"), list):
        fail("invalid ownership record")
    names = data["names"]
    if any(not isinstance(n, str) or not NAME.fullmatch(n) for n in names):
        fail("invalid name in ownership record")
    return set(names)


def save_owned(path: Path, names: set[str]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".gateway-parks-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump({"schema": 1, "names": sorted(names)}, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def parked_path(home: Path) -> Path:
    marker = home / "gateway.parked"
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        fail("unsafe parked marker for " + home.name)
    return marker


def pending(root: Path, roster: Path, owned: set[str]) -> dict[str, list[str]]:
    result = {"owned": [], "legacy": []}
    for name in sorted(managed_names(roster)):
        home = root / "profiles" / name
        if not home.exists():
            continue  # Ever-managed profiles can be removed independently.
        home = checked_profile(root, name)
        cfg = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8")) or {}
        if not isinstance(cfg, dict):
            fail("profile config not a mapping: " + name)
        gateway = cfg.get("gateway") or {}
        if not isinstance(gateway, dict):
            fail("gateway config not a mapping: " + name)
        standalone = gateway.get("standalone")
        if standalone is True or (isinstance(standalone, str) and
                                  standalone.strip().lower() in {"true", "yes", "on", "1"}):
            continue  # Explicit user-owned topology is preserved, including quoted YAML booleans.
        if parked_path(home).exists():
            result["owned" if name in owned else "legacy"].append(name)
    return result


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare-stop", "pending", "reconcile"))
    parser.add_argument("root", type=Path)
    parser.add_argument("roster", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--approve-legacy", action="store_true")
    args = parser.parse_args(argv)
    root = args.root
    if root.is_symlink() or not root.is_dir():
        fail("Hermes root missing or symlink")
    record = root.parent.parent / RECORD  # data/hermes -> stack root
    if record.parent.is_symlink():
        fail("ownership record parent is symlink")
    owned = load_owned(record)
    names = managed_names(args.roster)
    if args.action == "prepare-stop":
        if not args.name or args.name not in names:
            fail("stop target is not installer-managed")
        home = checked_profile(root, args.name)
        # A pre-existing marker may be an independent user stop. Never claim it.
        if not parked_path(home).exists():
            owned.add(args.name)
            save_owned(record, owned)  # Durable before the CLI creates the marker.
        print("Stop ownership checked:", args.name)
        return
    found = pending(root, args.roster, owned)
    if args.action == "pending":
        print(json.dumps(found, sort_keys=True))
        return
    if found["legacy"] and not args.approve_legacy:
        fail("unowned parked managed profiles require explicit approval: " + ", ".join(found["legacy"]))
    # Validate EVERY candidate before performing any removals.
    targets = found["owned"] + found["legacy"]
    for name in targets:
        parked_path(checked_profile(root, name))
    for name in targets:
        parked_path(checked_profile(root, name)).unlink()
        print("Unparked managed profile:", name)
    # A stop command may fail before creating the parked marker; such prepared
    # ownership must not remain a permanent authority over a later user stop.
    if targets or owned:
        # Every recorded managed non-standalone park has now been cleared;
        # other ownership receipts expire rather than claiming future stops.
        save_owned(record, set())


if __name__ == "__main__":
    run()
