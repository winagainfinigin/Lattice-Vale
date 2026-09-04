#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import unquote
import re

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
version=(CORE / "VERSION.txt").read_text(encoding="ascii").strip()
assert version in {"14.5.2","14.5.3","14.5.4","14.5.42","14.5.43","14.5.44",'14.5.45','14.5.46'}

headers = {
    ROOT / "README.md": f"# LatticeVale v{version}",
    CORE / "README.md": f"# LatticeVale v{version} — Technical README",
    ROOT / "docs/README.md": f"# LatticeVale v{version} — Stable",
    ROOT / "docs/FEATURES.md": f"# LatticeVale v{version} — Complete Features and Install Options Reference",
    ROOT / "docs/Instructions.txt": f"LATTICEVALE v{version} — INSTRUCTIONS",
    ROOT / "docs/Installer Description.txt": f"LATTICEVALE v{version} — INSTALLER DESCRIPTION",
}
for path, prefix in headers.items():
    assert path.read_text(encoding="utf-8").startswith(prefix), path

required = {
    ROOT / "README.md": ["v14.5.2 — cleanup / reclaim disk space maintenance release", "Option 7", "v14.5.1", "resource policy **v9**", "Current install release"],
    CORE / "README.md": ["v14.5.2 adds the install-preserving Option 7", "v14.5.1 adds resource policy v9"],
    CORE / "AUDIT.md": ["v14.5.2 Option 7 cleanup safety audit", "v14.5.1 adaptive resource-policy / OOM audit"],
    ROOT / "docs/FEATURES.md": ["Cleanup / reclaim disk space", "Current managed software/source pins documented by v14.5.46", "docker builder prune -f", "fstrim -v /"],
    ROOT / "docs/CHANGELOG.md": ["## 14.5.2 - 2026-08-29", "Option 7", "## 14.5.1 - 2026-08-29"],
    ROOT / "docs/PATCH-NOTES.md": ["# Current v14.5.46 patch notes", "## v14.5.2 — cleanup / reclaim disk space maintenance release", "## v14.5.1 — adaptive resource policy v9 / model-aware Ollama + adaptive Honcho timeout"],
    ROOT / "docs/RELEASE.md": ["v14.5.46 current release", "v14.5.4-vram-lowmem-fixtures.py", "v14.5.2-option7-cleanup-fixtures.py"],
    ROOT / "docs/SUPPORT.md": ["v14.5.2 cleanup / low-space recovery support note"],
    ROOT / "docs/SOURCES.md": ["v14.5.2 source-policy note"],
    ROOT / "docs/WINDOWS-INTEGRATION-TEST-MATRIX.md": ["v14.5.2 cleanup/low-space case"],
}
for path, needles in required.items():
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{path}: {needle}"

workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
assert "grep -q '^14.5.46$' LatticeVale-Core/VERSION.txt" in workflow
assert "grep -q '^## 14.5.46 ' docs/CHANGELOG.md" in workflow
issue = (ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
assert "placeholder: 14.5.46" in issue

# Validate local Markdown targets.
current_docs = [ROOT / "README.md", CORE / "README.md", CORE / "AUDIT.md"] + list((ROOT / "docs").glob("*.md")) + [ROOT / ".github/PULL_REQUEST_TEMPLATE.md"]
link_re = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
for path in current_docs:
    text = path.read_text(encoding="utf-8")
    for target in link_re.findall(text):
        target = target.strip().split()[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        relative = unquote(target.split("#", 1)[0])
        if relative:
            assert (path.parent / relative).resolve().exists(), f"{path}: broken link {target}"

print("v14.5.2 DOCUMENTATION AUDIT FIXTURES: PASS")
