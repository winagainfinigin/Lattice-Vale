#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() == "14.5.2"
assert (REPO / "README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.2\n")
assert (ROOT / "README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.2 — Technical README\n")
assert (REPO / "docs/README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.2 — Stable\n")
assert (REPO / "docs/Instructions.txt").read_text(encoding="utf-8").startswith("LATTICEVALE v14.5.2 — INSTRUCTIONS\n")
assert (REPO / "docs/Installer Description.txt").read_text(encoding="utf-8").startswith("LATTICEVALE v14.5.2 — INSTALLER DESCRIPTION\n")
assert (REPO / "docs/FEATURES.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.2 — Complete Features and Install Options Reference\n")
changelog = (REPO / "docs/CHANGELOG.md").read_text(encoding="utf-8")
assert "## 14.5.2 - 2026-08-29" in changelog
assert "## 14.5.1 - 2026-08-29" in changelog
patch_notes = (REPO / "docs/PATCH-NOTES.md").read_text(encoding="utf-8")
assert "# Current v14.5.2 patch notes" in patch_notes
assert "## v14.5.2 — cleanup / reclaim disk space maintenance release" in patch_notes
root_readme = (REPO / "README.md").read_text(encoding="utf-8")
assert "| **v14.5.2** | **Current install release** |" in root_readme
assert "| **v14.5.1** | Release |" in root_readme
features = (REPO / "docs/FEATURES.md").read_text(encoding="utf-8")
assert "Current managed software/source pins documented by v14.5.2" in features
workflow = (REPO / ".github/workflows/validate.yml").read_text(encoding="utf-8")
assert "grep -q '^14.5.2$' LatticeVale-Core/VERSION.txt" in workflow
assert "grep -q '^## 14.5.2 ' docs/CHANGELOG.md" in workflow
issue = (REPO / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
assert "placeholder: 14.5.2" in issue
assert (ROOT / "tests/v14.5.2-option7-cleanup-fixtures.py").is_file()
print("v14.5.2 RELEASE IDENTITY FIXTURES: PASS")
