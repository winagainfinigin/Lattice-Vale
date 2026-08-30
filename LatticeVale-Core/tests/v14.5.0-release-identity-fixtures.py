#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / "VERSION.txt").read_text(encoding="ascii").strip()
assert version in {"14.5.0", "14.5.1","14.5.2"}, version
readme = (REPO / "README.md").read_text(encoding="utf-8")
changelog = (REPO / "docs/CHANGELOG.md").read_text(encoding="utf-8")
patch_notes = (REPO / "docs/PATCH-NOTES.md").read_text(encoding="utf-8")
workflow = (REPO / ".github/workflows/validate.yml").read_text(encoding="utf-8")
assert "read-only" in readme.lower() and "repair --plan" in readme
assert "## 14.5.0 - 2026-08-28" in changelog
assert "## v14.5.0 — read-only planning foundation" in patch_notes
assert "python tests/run-regressions.py" in workflow
assert "for test in tests/*-fixtures.py" not in workflow
for name in ("latticevale_readonly.py", "repair-plan.py", "audit-free.py", "checkpoint-metadata.json"):
    assert (ROOT / "stack" / name).is_file(), name
print("v14.5.0 READ-ONLY FOUNDATION INHERITANCE FIXTURES: PASS")
