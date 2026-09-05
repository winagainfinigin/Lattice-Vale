#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / "VERSION.txt").read_text(encoding="ascii").strip()
assert version in {"14.5.1", "14.5.2","14.5.3","14.5.4","14.5.42","14.5.43","14.5.44",'14.5.45','14.5.46'}, version
changelog = (REPO / "docs/CHANGELOG.md").read_text(encoding="utf-8")
patch_notes = (REPO / "docs/PATCH-NOTES.md").read_text(encoding="utf-8")
root_readme = (REPO / "README.md").read_text(encoding="utf-8")
assert "## 14.5.1 - 2026-08-29" in changelog
assert "## v14.5.1 — adaptive resource policy v9 / model-aware Ollama + adaptive Honcho timeout" in patch_notes
assert "### v14.5.1 — adaptive CPU/RAM/OOM reliability patch" in root_readme
assert "resource policy **v9**" in root_readme
for name in (
    "v14.5.1-resource-policy-oom-fixtures.py",
    "v14.5.1-adaptive-hardware-matrix-fixtures.py",
    "v14.5.1-option-topology-resource-fixtures.py",
    "v14.5.1-model-aware-ollama-honcho-fixtures.py",
    "v14.5.1-delayed-gateway-reconcile-fixtures.py",
):
    assert (ROOT / "tests" / name).is_file(), name
print("v14.5.1 HISTORICAL RELEASE INHERITANCE FIXTURES: PASS")
