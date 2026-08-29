#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STACK_SRC = ROOT / "stack"
sys.path.insert(0, str(STACK_SRC))
from latticevale_readonly import StackSnapshot, options_hash  # noqa: E402

version = (ROOT / "VERSION.txt").read_text(encoding="ascii").strip()
assert version == "14.5.0", version

metadata = json.loads((STACK_SRC / "checkpoint-metadata.json").read_text())
assert metadata["schema"] == 1
assert metadata["stages"]["reconcile"]["revision"] == 4
assert metadata["stages"]["kanban_gateway"]["revision"] == 4
configure = (STACK_SRC / "configure-stack.sh").read_text()
assert "checkpoint-metadata.json" not in configure
expected_revisions = {
    "prepare_config": 1,
    "infrastructure": 1,
    "matrix_bootstrap": 1,
    "provider_setup": 1,
    "profiles": 1,
    "matrix_profiles": 3,
    "matrix_cross_signing": 1,
    "matrix_profile_cross_signing": 3,
    "integrations": 4,
    "reconcile": 4,
    "kanban_gateway": 4,
    "finalize": 2,
}
assert {name: item["revision"] for name, item in metadata["stages"].items()} == expected_revisions
assert "prepare_config|infrastructure|matrix_bootstrap|provider_setup|profiles|matrix_cross_signing) printf '1'" in configure
for stage, revision in expected_revisions.items():
    if revision == 1 and stage not in {"matrix_profiles", "matrix_profile_cross_signing", "kanban_gateway", "finalize", "reconcile", "integrations"}:
        continue
    assert f"{stage}) printf '{revision}'" in configure or (
        stage in {"matrix_profiles", "matrix_profile_cross_signing"}
        and "matrix_profiles|matrix_profile_cross_signing) printf '3'" in configure
    )

manage = (STACK_SRC / "manage.sh").read_text()
for marker in (
    "repair --plan [--offline]",
    "python3 ./repair-plan.py --stack .",
    "audit-free) python3 ./audit-free.py --stack .",
    "Repair application remains owned by the Windows installer",
):
    assert marker in manage, marker

with tempfile.TemporaryDirectory(prefix="lv145-plan-") as td:
    stack = Path(td)
    for name in (
        "state-audit.py",
        "latticevale_readonly.py",
        "repair-plan.py",
        "audit-free.py",
        "checkpoint-metadata.json",
    ):
        shutil.copy2(STACK_SRC / name, stack / name)
    for name in ("compose.yaml", "configure-stack.sh", "manage.sh"):
        shutil.copy2(STACK_SRC / name, stack / name)

    options = {
        "schema": 19,
        "installerVersion": "14.5.0",
        "installerMode": "resume",
        "dashboard": False,
        "multiAgent": False,
        "workers": [],
        "kanban": False,
        "matrix": False,
        "tailscale": False,
        "searxng": False,
        "qmd": False,
        "honcho": False,
        "hermesLocalAI": True,
        "ollamaBackend": "managed",
        "containerResourceLimits": True,
        "obsidian": False,
    }
    (stack / "install-options.json").write_text(json.dumps(options) + "\n")
    (stack / ".env").write_text("HERMES_IMAGE=nousresearch/hermes-agent:v2026.8.16\n")
    (stack / "compose.override.yaml").write_text("# user-owned fixture override\nservices: {}\n")
    current_hash = options_hash(options)
    state = {
        "schema": 1,
        "installerVersion": "14.5.0",
        "optionsHash": current_hash,
        "status": "complete",
        "stages": {
            name: {
                "status": "done",
                "optionsHash": current_hash,
                "revision": item["revision"],
            }
            for name, item in metadata["stages"].items()
        },
    }
    (stack / ".installer-state.json").write_text(json.dumps(state) + "\n")

    snap = StackSnapshot.load(stack)
    assert snap.options.hermes_local_ai is True
    assert snap.options.ollama_backend == "managed"
    assert snap.user_override_present is True
    assert snap.computed_options_hash == current_hash
    override_source = [s for s in snap.sources if s.path == "compose.override.yaml"][0]
    assert "opaque/user-owned" in override_source.note

    def tree_hash() -> str:
        h = sha256()
        for path in sorted(p for p in stack.rglob("*") if p.is_file()):
            h.update(str(path.relative_to(stack)).encode())
            h.update(path.read_bytes())
        return h.hexdigest()

    before = tree_hash()
    plan = subprocess.run(
        [sys.executable, str(stack / "repair-plan.py"), "--stack", str(stack), "--offline", "--json"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    assert payload["mode"] == "read-only"
    assert payload["apply"]["supportedByPlanner"] is False
    assert payload["destructiveOperations"] == []
    assert any("user-owned" in note for note in payload["warnings"])
    assert tree_hash() == before, "repair planner modified stack files"

    free = subprocess.run(
        [sys.executable, str(stack / "audit-free.py"), "--stack", str(stack), "--json"],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert free.returncode == 0, free.stderr
    free_payload = json.loads(free.stdout)
    assert free_payload["currentConfigurationFreeOnly"] is True
    assert free_payload["localDefaultHermesAI"] is True
    assert free_payload["wslNativeCoreAIPath"] is True
    assert tree_hash() == before, "free audit modified stack files"

    windows_options = dict(options)
    windows_options["ollamaBackend"] = "windows-native"
    (stack / "install-options.json").write_text(json.dumps(windows_options) + "\n")
    before_windows_audit = tree_hash()
    windows_free = subprocess.run(
        [sys.executable, str(stack / "audit-free.py"), "--stack", str(stack), "--json"],
        text=True, capture_output=True, timeout=20, check=False,
    )
    assert windows_free.returncode == 0, windows_free.stderr
    windows_payload = json.loads(windows_free.stdout)
    assert windows_payload["currentConfigurationFreeOnly"] is True
    assert windows_payload["wslNativeCoreAIPath"] is False
    assert any("Windows-native Ollama" in item for item in windows_payload["optionalExternalIntegrations"])
    assert tree_hash() == before_windows_audit, "Windows-native free audit modified stack files"

print("v14.5.0 READ-ONLY PLANNER + FREE AUDIT FIXTURES: PASS")
