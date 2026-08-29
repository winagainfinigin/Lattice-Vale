#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() == "14.5.0"
assert (REPO / "README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.0\n")
assert (ROOT / "README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.0 — Technical README\n")
assert (REPO / "docs/README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.0 — Stable\n")
assert (REPO / "docs/Instructions.txt").read_text(encoding="utf-8").startswith("LATTICEVALE v14.5.0 — INSTRUCTIONS\n")
assert (REPO / "docs/Installer Description.txt").read_text(encoding="utf-8").startswith("LATTICEVALE v14.5.0 — INSTALLER DESCRIPTION\n")
assert (REPO / "docs/FEATURES.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.0 — Complete Features and Install Options Reference\n")
assert "## 14.5.0 - 2026-08-28" in (REPO / "docs/CHANGELOG.md").read_text(encoding="utf-8")
assert "## v14.5.0 — read-only planning foundation" in (REPO / "docs/PATCH-NOTES.md").read_text(encoding="utf-8")
workflow = (REPO / ".github/workflows/validate.yml").read_text(encoding="utf-8")
assert "python tests/run-regressions.py" in workflow
assert "for test in tests/*-fixtures.py" not in workflow
assert "grep -q '^14.5.0$' LatticeVale-Core/VERSION.txt" in workflow
issue = (REPO / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
assert "placeholder: 14.5.0" in issue
for name in ("latticevale_readonly.py", "repair-plan.py", "audit-free.py", "checkpoint-metadata.json"):
    assert (ROOT / "stack" / name).is_file(), name
print("v14.5.0 RELEASE IDENTITY FIXTURES: PASS")
