#!/usr/bin/env python3
"""Deterministic, sharded LatticeVale regression-suite runner.

The release contract is intentionally explicit: v14.6.1 ships 144 deterministic
*-fixtures.py programs.  The suite can be run as six bounded shards to avoid CI or
wrapper time ceilings, while invoking this file without --shard still executes all
shards and reports one authoritative 144/144 result.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import signal
import time
from typing import Iterable

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
EXPECTED_FIXTURE_COUNT = 144
SHARDS: tuple[tuple[str, int, int], ...] = (
    ("01-core", 1, 25),
    ("02-installer", 26, 50),
    ("03-repair-update", 51, 75),
    ("04-resource-policy", 76, 100),
    ("05-gpu-directml", 101, 120),
    ("06-release", 121, 144),
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


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _reap_group(pgid: int, grace: float = 1.5) -> None:
    """Boundedly reap descendants so one fixture cannot retain the CI output pipe."""
    if not _group_exists(pgid):
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if not _group_exists(pgid):
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return


def run_items(items: Iterable[tuple[int, Path]]) -> tuple[int, list[dict[str, object]]]:
    failures = 0
    results: list[dict[str, object]] = []
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("TERM", "dumb")
    fixture_timeout = int(env.get("LATTICEVALE_FIXTURE_TIMEOUT", "900"))
    for index, fixture in items:
        print(f"[{index:03d}/{EXPECTED_FIXTURE_COUNT}] {fixture.name}", flush=True)
        with tempfile.TemporaryFile(mode="w+") as stdout, tempfile.TemporaryFile(mode="w+") as stderr:
            proc = subprocess.Popen(
                [sys.executable, str(fixture)],
                cwd=str(ROOT.parent),
                env=env,
                stdout=stdout,
                stderr=stderr,
                text=True,
                start_new_session=True,
            )
            pgid = proc.pid
            timed_out = False
            try:
                returncode = proc.wait(timeout=fixture_timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _reap_group(pgid)
                try:
                    returncode = proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    returncode = proc.wait()
            finally:
                _reap_group(pgid)
            stdout.seek(0); stderr.seek(0)
            out = stdout.read(); err = stderr.read()
        if out:
            print(out, end="" if out.endswith("\n") else "\n", flush=True)
        if err:
            print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr, flush=True)
        ok = returncode == 0 and not timed_out
        if timed_out:
            print(f"Fixture exceeded {fixture_timeout}s hard timeout.", file=sys.stderr, flush=True)
        print(f"{'PASS' if ok else 'FAIL'} {index:03d} {fixture.name}", flush=True)
        results.append({"index": index, "fixture": fixture.name, "returncode": returncode, "status": "PASS" if ok else "FAIL", "timedOut": timed_out})
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
