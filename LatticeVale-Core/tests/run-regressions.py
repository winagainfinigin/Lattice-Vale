#!/usr/bin/env python3
"""Deterministic, sharded LatticeVale regression-suite runner.

The release contract is intentionally explicit: v14.5.46 ships 139 deterministic
*-fixtures.py programs.  The suite can be run as six bounded shards to avoid CI or
wrapper time ceilings, while invoking this file without --shard still executes all
shards and reports one authoritative 139/139 result.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
EXPECTED_FIXTURE_COUNT = 139
SHARDS: tuple[tuple[str, int, int], ...] = (
    ("01-core", 1, 25),
    ("02-installer", 26, 50),
    ("03-repair-update", 51, 75),
    ("04-resource-policy", 76, 100),
    ("05-gpu-directml", 101, 120),
    ("06-release", 121, 139),
)
FORBIDDEN_FILE_NAMES = {".DS_Store", "Thumbs.db"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak", ".swp"}


def fixtures() -> list[Path]:
    found = sorted(ROOT.glob("*-fixtures.py"), key=lambda p: p.name.lower())
    if len(found) != EXPECTED_FIXTURE_COUNT:
        raise RuntimeError(
            f"Expected exactly {EXPECTED_FIXTURE_COUNT} regression fixtures, found {len(found)}. "
            "Update the release contract deliberately if the suite size changes."
        )
    return found


def contamination() -> list[str]:
    bad: list[str] = []
    for path in REPO.rglob("*"):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(REPO).as_posix()
        if path.is_dir() and path.name == "__pycache__":
            bad.append(rel + "/")
        elif path.is_file() and (path.name in FORBIDDEN_FILE_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES):
            bad.append(rel)
    return sorted(bad)


def shard_slice(all_fixtures: list[Path], shard_name: str) -> list[tuple[int, Path]]:
    for name, start, end in SHARDS:
        if name == shard_name:
            return list(enumerate(all_fixtures[start - 1:end], start=start))
    raise KeyError(shard_name)


def run_items(items: Iterable[tuple[int, Path]]) -> tuple[int, list[dict[str, object]]]:
    failures = 0
    results: list[dict[str, object]] = []
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("TERM", "dumb")
    for index, fixture in items:
        print(f"[{index:03d}/{EXPECTED_FIXTURE_COUNT}] {fixture.name}", flush=True)
        proc = subprocess.run(
            [sys.executable, str(fixture)],
            cwd=str(ROOT.parent),
            check=False,
            env=env,
        )
        ok = proc.returncode == 0
        print(f"{'PASS' if ok else 'FAIL'} {index:03d} {fixture.name}", flush=True)
        results.append({"index": index, "fixture": fixture.name, "returncode": proc.returncode, "status": "PASS" if ok else "FAIL"})
        if not ok:
            failures += 1
    return failures, results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", choices=[x[0] for x in SHARDS], help="run one bounded release shard")
    parser.add_argument("--list-shards", action="store_true")
    parser.add_argument("--summary-file", type=Path, help="write machine-readable JSON results")
    args = parser.parse_args()

    if args.list_shards:
        for name, start, end in SHARDS:
            print(f"{name}: fixtures {start}-{end} ({end-start+1})")
        return 0

    try:
        all_fixtures = fixtures()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    before = contamination()
    if before:
        print("Release-tree contamination detected before regression execution:", file=sys.stderr)
        for item in before:
            print(f"  - {item}", file=sys.stderr)
        return 2

    if args.shard:
        selected = shard_slice(all_fixtures, args.shard)
        print(f"==> shard {args.shard}: {selected[0][0]}-{selected[-1][0]}", flush=True)
        failures, results = run_items(selected)
        expected = len(selected)
        passed = expected - failures
        label = args.shard
    else:
        results = []
        failures = 0
        for name, _start, _end in SHARDS:
            selected = shard_slice(all_fixtures, name)
            print(f"==> shard {name}: {selected[0][0]}-{selected[-1][0]}", flush=True)
            shard_failures, shard_results = run_items(selected)
            failures += shard_failures
            results.extend(shard_results)
            print(f"<== shard {name}: {'PASS' if shard_failures == 0 else 'FAIL'} ({len(selected)-shard_failures}/{len(selected)})", flush=True)
        expected = EXPECTED_FIXTURE_COUNT
        passed = expected - failures
        label = "all"

    after = contamination()
    if after:
        print("Release-tree contamination detected after regression execution:", file=sys.stderr)
        for item in after:
            print(f"  - {item}", file=sys.stderr)
        failures += 1

    summary = {
        "suite": "LatticeVale deterministic regressions",
        "selection": label,
        "expected": expected,
        "passed": passed,
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
        "skipped": 0,
        "tree_contamination": after,
        "results": results,
    }
    if args.summary_file:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        args.summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if failures:
        print(f"REGRESSION SUITE: FAIL (passed={passed}, failed={summary['failed']}, skipped=0)", file=sys.stderr)
        return 1
    if not args.shard and (passed != EXPECTED_FIXTURE_COUNT or len(results) != EXPECTED_FIXTURE_COUNT):
        print("REGRESSION SUITE: FAIL (incomplete aggregate result)", file=sys.stderr)
        return 1
    print(f"REGRESSION SUITE: PASS ({passed}/{expected}; failed=0; skipped=0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
