#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() == "14.5.1"
assert (REPO / "README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.1\n")
assert (ROOT / "README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.1 — Technical README\n")
assert (REPO / "docs/README.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.1 — Stable\n")
assert (REPO / "docs/Instructions.txt").read_text(encoding="utf-8").startswith("LATTICEVALE v14.5.1 — INSTRUCTIONS\n")
assert (REPO / "docs/Installer Description.txt").read_text(encoding="utf-8").startswith("LATTICEVALE v14.5.1 — INSTALLER DESCRIPTION\n")
assert (REPO / "docs/FEATURES.md").read_text(encoding="utf-8").startswith("# LatticeVale v14.5.1 — Complete Features and Install Options Reference\n")
changelog = (REPO / "docs/CHANGELOG.md").read_text(encoding="utf-8")
assert "## 14.5.1 - 2026-08-29" in changelog
assert "## 14.5.0 - 2026-08-28" in changelog
patch_notes = (REPO / "docs/PATCH-NOTES.md").read_text(encoding="utf-8")
assert "## v14.5.1 — adaptive resource policy v9 / model-aware Ollama + adaptive Honcho timeout" in patch_notes

root_readme = (REPO / "README.md").read_text(encoding="utf-8")
assert "resource policy **v9**" in root_readme
assert "| **v14.5.1** | **Current install release** |" in root_readme
assert "LatticeVale resource policy **v4** is designed" not in root_readme
features = (REPO / "docs/FEATURES.md").read_text(encoding="utf-8")
for command in ("./manage.sh audit", "./manage.sh plan [--offline]", "./manage.sh repair --plan [--offline]", "./manage.sh audit-free"):
    assert command in features, command
assert "Current managed software/source pins documented by v14.5.1" in features
assert "Current managed software/source pins documented by v14.4.85" not in features
assert "HostConfig.Memory" in features
assert "HostConfig.NanoCpus" in features
installer_description = (REPO / "docs/Installer Description.txt").read_text(encoding="utf-8")
assert "HostConfig.Memory" in installer_description
assert "HostConfig.NanoCpus" in installer_description
assert "Docker `OOMKilled=true`" in installer_description
assert "# Historical v14.4.x patch notes" in patch_notes
assert "# Current v14.5.x and consolidated patch notes" in patch_notes

workflow = (REPO / ".github/workflows/validate.yml").read_text(encoding="utf-8")
assert "grep -q '^14.5.1$' LatticeVale-Core/VERSION.txt" in workflow
assert "grep -q '^## 14.5.1 ' docs/CHANGELOG.md" in workflow
issue = (REPO / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
assert "placeholder: 14.5.1" in issue
print("v14.5.1 RELEASE IDENTITY FIXTURES: PASS")
