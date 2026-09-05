#!/usr/bin/env python3
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
version = (CORE / "VERSION.txt").read_text(encoding="ascii").strip()
assert version in {"14.5.1", "14.5.2","14.5.3","14.5.4","14.5.42","14.5.43","14.5.44",'14.5.45','14.5.46','14.5.47','14.6.0'}, version
changelog = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
patch_notes = (ROOT / "docs/PATCH-NOTES.md").read_text(encoding="utf-8")
root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
assert "## 14.5.1 - 2026-08-29" in changelog
assert "## v14.5.1 — adaptive resource policy v9 / model-aware Ollama + adaptive Honcho timeout" in patch_notes
assert "### v14.5.1 — adaptive CPU/RAM/OOM reliability patch" in root_readme
for needle in ("4608 MiB", "HostConfig.Memory", "HostConfig.NanoCpus", "OOMKilled=true", "model-aware"):
    assert needle in root_readme, needle
print("v14.5.1 HISTORICAL DOCUMENTATION INHERITANCE FIXTURES: PASS")
