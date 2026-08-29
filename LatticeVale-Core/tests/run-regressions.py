#!/usr/bin/env python3
"""Auto-discover deterministic LatticeVale regression fixtures.

A fixture added to tests/*-fixtures.py is automatically part of CI; release authors no longer
need to maintain a second explicit list in validate.yml. Execution remains sequential, matching
the previous shell loop and avoiding new concurrency or timeout semantics in historical tests.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main() -> int:
    fixtures = sorted(ROOT.glob("*-fixtures.py"), key=lambda p: p.name.lower())
    if not fixtures:
        print("No regression fixtures discovered.", file=sys.stderr)
        return 2
    failures: list[str] = []
    for fixture in fixtures:
        print(f"==> {fixture.name}", flush=True)
        proc = subprocess.run(
            [sys.executable, str(fixture)],
            cwd=str(ROOT.parent),
            check=False,
        )
        if proc.returncode:
            failures.append(f"{fixture.name} (exit {proc.returncode})")
    if failures:
        print("Regression failures:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(f"AUTO-DISCOVERED REGRESSION SUITE: PASS ({len(fixtures)} fixtures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
