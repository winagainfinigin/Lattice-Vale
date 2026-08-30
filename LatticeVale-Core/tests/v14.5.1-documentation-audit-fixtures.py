#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import unquote
import re

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent

current_docs = [
    ROOT / "README.md",
    CORE / "README.md",
    CORE / "AUDIT.md",
    ROOT / "docs/README.md",
    ROOT / "docs/FEATURES.md",
    ROOT / "docs/Installer Description.txt",
    ROOT / "docs/Instructions.txt",
    ROOT / "docs/NATIVE-OLLAMA-INTEGRATION.md",
    ROOT / "docs/PATCH-NOTES.md",
    ROOT / "docs/RELEASE.md",
    ROOT / "docs/SECURITY.md",
    ROOT / "docs/SOURCES.md",
    ROOT / "docs/SUPPORT.md",
    ROOT / "docs/THIRD-PARTY-NOTICES.md",
    ROOT / "docs/WINDOWS-INTEGRATION-TEST-MATRIX.md",
    ROOT / "docs/CONTRIBUTING.md",
    ROOT / "docs/CHANGELOG.md",
    ROOT / ".github/PULL_REQUEST_TEMPLATE.md",
]
for path in current_docs:
    assert path.is_file(), path

headers = {
    ROOT / "README.md": "# LatticeVale v14.5.1",
    CORE / "README.md": "# LatticeVale v14.5.1 — Technical README",
    ROOT / "docs/README.md": "# LatticeVale v14.5.1 — Stable",
    ROOT / "docs/FEATURES.md": "# LatticeVale v14.5.1 — Complete Features and Install Options Reference",
    ROOT / "docs/Instructions.txt": "LATTICEVALE v14.5.1 — INSTRUCTIONS",
    ROOT / "docs/Installer Description.txt": "LATTICEVALE v14.5.1 — INSTALLER DESCRIPTION",
}
for path, prefix in headers.items():
    assert path.read_text(encoding="utf-8").startswith(prefix), path

required = {
    ROOT / "README.md": ["resource policy **v9**", "4608 MiB", "memory.max", "HostConfig.Memory", "HostConfig.NanoCpus", "OOMKilled=true", "model-aware", "Honcho", "v14.5.1** | **Current install release"],
    ROOT / "docs/FEATURES.md": ["Current policy v9", "4608 MiB", "memory.max", "HostConfig.Memory", "HostConfig.NanoCpus", "OOMKilled=true", "secondary Matrix gateway", "Kanban concurrency", "helper runtime", "./manage.sh repair --plan", "./manage.sh audit-free", "model-aware", "OLLAMA_MODEL_FLOOR_MIB"],
    ROOT / "docs/Instructions.txt": ["resource policy v9", "4608 MiB", "memory.max", "HostConfig.Memory", "HostConfig.NanoCpus", "secondary Matrix gateway", "root startup helper", "544 MiB", "model-aware"],
    ROOT / "docs/Installer Description.txt": ["Policy v9", "4608 MiB", "memory.max", "HostConfig.Memory", "HostConfig.NanoCpus", "OOMKilled=true", "model-aware"],
    ROOT / "docs/SUPPORT.md": ["v14.5.1 adaptive CPU/RAM / OOM support note", "OOMKilled=true"],
    ROOT / "docs/RELEASE.md": ["v14.5.1 current release", "HostConfig.Memory", "544 MiB", "v14.5.1-option-topology-resource-fixtures.py", "v14.5.1-delayed-gateway-reconcile-fixtures.py", "v14.5.1-model-aware-ollama-honcho-fixtures.py"],
    ROOT / "docs/CHANGELOG.md": ["## 14.5.1 - 2026-08-29", "HostConfig.Memory", "60-second stable-start window", "printf"],
    ROOT / "docs/PATCH-NOTES.md": ["# Current v14.5.1 patch notes", "## v14.5.1 — adaptive resource policy v9 / model-aware Ollama + adaptive Honcho timeout", "HostConfig.Memory", "HostConfig.NanoCpus", "old 20-second s6 readiness window", "STARTING"],
    CORE / "AUDIT.md": ["POLICY_VERSION=9", "profile/Kanban topology", "startup helper", "4608 MiB", "OOMKilled=true"],
    CORE / "README.md": ["v14.5.1 adds resource policy v9", "4608 MiB", "HostConfig.Memory", "HostConfig.NanoCpus"],
    ROOT / "docs/WINDOWS-INTEGRATION-TEST-MATRIX.md": ["v14.5.1 resource-policy/OOM case", "HostConfig.Memory", "HostConfig.NanoCpus"],
    ROOT / "docs/THIRD-PARTY-NOTICES.md": ["v14.5.1 adds no new third-party runtime dependency"],
}
for path, needles in required.items():
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{path}: {needle}"

# Historical v4 statements may remain in changelog/audit/patch history, but current operator
# surfaces must never advertise them as the active release/policy.
for path in current_docs:
    if path in {ROOT / "docs/CHANGELOG.md", ROOT / "docs/PATCH-NOTES.md", CORE / "AUDIT.md"}:
        continue
    text = path.read_text(encoding="utf-8")
    assert "Current managed software/source pins documented by v14.4.85" not in text, path
    assert "LatticeVale resource policy **v4** is designed" not in text, path
    assert "When adaptive container resource limits are enabled, policy v8:" not in text, path
    assert "migrates enabled adaptive resource policy to v8" not in text, path
    assert "regenerates to v8 on repair/start" not in text, path

features = (ROOT / "docs/FEATURES.md").read_text(encoding="utf-8")
for command in (
    "./manage.sh audit",
    "./manage.sh plan [--offline]",
    "./manage.sh repair --plan [--offline]",
    "./manage.sh audit-free",
):
    assert command in features, command

# Validate local Markdown targets, including URL-escaped filenames such as Installer%20Description.txt.
link_re = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
for path in [p for p in current_docs if p.suffix.lower() == ".md"]:
    text = path.read_text(encoding="utf-8")
    for target in link_re.findall(text):
        target = target.strip().split()[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        relative = unquote(target.split("#", 1)[0])
        if relative:
            assert (path.parent / relative).resolve().exists(), f"{path}: broken link {target}"

print("v14.5.1 DOCUMENTATION AUDIT FIXTURES: PASS")
