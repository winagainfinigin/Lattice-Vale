#!/usr/bin/env python3
"""Historical v14.4.85 documentation/layout regression.

Current-release identity moved to v14.5.0-release-identity-fixtures.py.  This fixture keeps
v14.4.85's release-history markers from disappearing during later documentation cleanup.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / "VERSION.txt").read_text(encoding="ascii").strip()
assert version in {"14.4.85", "14.5.0","14.5.1"}, version
chg = (REPO / "docs/CHANGELOG.md").read_text(encoding="utf-8")
assert "## 14.4.85 - 2026-08-28" in chg
patch = (REPO / "docs/PATCH-NOTES.md").read_text(encoding="utf-8")
assert "## v14.4.85 — startup-aware reconcile, post-gateway readiness, and maintenance reliability" in patch
assert (REPO / "installer/PATCH-DELETE.txt").exists()
assert (REPO / "tools/Finalize-LatticeVale-OverwritePatch.ps1").exists()
for current in (
    "v14.4.85-reconcile-startup-fixtures.py",
    "v14.4.85-post-gateway-readiness-fixtures.py",
    "v14.4.85-update-backup-audit-fixtures.py",
):
    assert (ROOT / "tests" / current).exists(), current
print("v14.4.85 HISTORICAL RELEASE IDENTITY FIXTURES: PASS")
