#!/usr/bin/env python3
"""v14.5.42 resource-policy v11, hardware diversity, and release-consistency fixtures."""
from pathlib import Path
import importlib.util
import os
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() in {"14.5.42", "14.5.43","14.5.44",'14.5.45','14.5.46'}
cfg = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
audit = (ROOT / "stack/state-audit.py").read_text(encoding="utf-8")
compose = (ROOT / "stack/compose.yaml").read_text(encoding="utf-8")
gateway = (ROOT / "stack/directml-gateway.py").read_text(encoding="utf-8")
installer = (ROOT / "Install-LatticeVale.ps1").read_text(encoding="ascii")
runner = (ROOT / "tests/run-regressions.py").read_text(encoding="utf-8")

# Canonical policy v11 is frozen once, then consumed by Compose/state/diagnostics.
for marker in (
    "Policy v11 canonicalization", "declare -A resource_policy=(", "[POLICY_VERSION]=11",
    "resource_policy[POLICY_FINGERPRINT]", "resource_policy[HARDWARE_FINGERPRINT]",
    "resource_policy[\"LIMIT_${resource_state_key}_MIB\"]", "resource_policy[\"CPU_${resource_state_key}_MILLI\"]",
    "resource-policy-report.txt", "GPU execution verified:", "Policy fingerprint:", "Hardware fingerprint:",
    "resource_ram_profile() {", "resource_cpu_profile() {", "ollama_gpu_inventory() {", "ollama_gpu_metrics() {",
    "resource_gpu_coordination() {", "GPU_HETEROGENEOUS", "OLLAMA_GPU_OVERHEAD_MIB", "DIRECTML_VRAM_LIMIT_PCT",
):
    assert marker in cfg, marker
for marker in ("POLICY_FINGERPRINT", "HARDWARE_FINGERPRINT", "GPU_HETEROGENEOUS", "resource-policy-report.txt"):
    assert marker in audit, marker

# Downstream generated Compose must consume the canonical service values rather than
# recomputing or substituting the pre-finalized CPU/memory variables.
emit_start = cfg.index("rm -f compose.latticevale.yaml", cfg.index("Policy v11 canonicalization"))
emit_end = cfg.index("  compose_files=\'compose.yaml\'", emit_start)
emit = cfg[emit_start:emit_end]
assert "resource_policy[CPU_HERMES_MILLI]" in emit and "resource_policy[LIMIT_HERMES_MIB]" in emit
assert "resource_policy[CPU_OLLAMA_MILLI]" in emit and "resource_policy[LIMIT_OLLAMA_MIB]" in emit
assert '"$ollama_cpu" "${mem_limits[ollama]}"' not in emit
assert '"$hermes_cpu" "${mem_limits[hermes]}"' not in emit

# Compact 8 GiB WSL target: 10% CPU-Ollama reserve -> 7373 MiB container budget.
start = cfg.index("import sys\nbudget=int(sys.argv[1])", cfg.index("<<'PY_RESOURCE_PLAN'"))
end = cfg.index("\nPY_RESOURCE_PLAN", start)
planner = cfg[start:end]
args = ["7373", "true", "true", "true", "true", "true", "cpu", "1024", "4096", "true"]
r = subprocess.run([sys.executable, "-c", planner, *args], text=True, capture_output=True, timeout=10)
assert r.returncode == 0, r.stderr
alloc = {k: int(v) for k, v in (line.split("=", 1) for line in r.stdout.splitlines())}
assert sum(alloc.values()) <= 7373, alloc
assert alloc["hermes"] >= 1024 and alloc["ollama"] >= 4096, alloc

# Execute the exact shared-GPU coordination function over diverse synthetic topology.
def between(text: str, start_marker: str, end_marker: str) -> str:
    a = text.index(start_marker); b = text.index(end_marker, a); return text[a:b]
coord_fn = between(cfg, "resource_gpu_coordination() {", "resource_ram_profile() {")
with tempfile.TemporaryDirectory(prefix="lv14542-gpu-coord-") as td:
    h = Path(td) / "h.sh"
    h.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "opt_text(){ [[ \"$1\" == directmlGpuVendor ]] && printf nvidia || true; }\n"
        "resource_directml_selected(){ return 0; }\n" + coord_fn + "\n"
        "for spec in '1 4096 4096' '1 8192 8192' '1 12288 12288' '2 8192 8192' '2 8192 12288' '2 4096 24576' '2 1024 8192' '3 8192 12288'; do\n"
        "  set -- $spec; resource_gpu_coordination nvidia \"$1\" \"$2\" \"$3\";\n"
        "done\n",
        encoding="utf-8",
    )
    rr = subprocess.run(["bash", str(h)], text=True, capture_output=True, timeout=10)
    assert rr.returncode == 0, rr.stderr
    lines = rr.stdout.splitlines()
    assert lines == [
        "2048:50:true", "4096:50:true", "6144:50:true", "4096:50:true",
        "6144:50:true", "3072:12:true", "768:9:true", "6144:50:true",
    ], lines

# Topology is never represented as one fictitious aggregate GPU, and missing VRAM
# telemetry is fail-closed for a selected GPU backend.
assert "count:min:max:aggregate" in cfg
assert "treating aggregate VRAM as one interchangeable pool" in cfg
assert "GPU-backed hard limits must never be based on an invented capacity" in cfg
assert "[[ -n \"$inventory\" ]] || return 1" in cfg
# Auto intentionally prefers a verified NVIDIA runtime, then AMD/ROCm; simultaneous
# vendors therefore resolve deterministically rather than merging unlike devices.
auto_block = cfg[cfg.index("    auto)"):cfg.index("    *) echo \"Unsupported Ollama acceleration policy", cfg.index("    auto)"))]
assert auto_block.index("nvidia_container_runtime_ready") < auto_block.index("/dev/kfd")

# RAM- and usable-VRAM-aware context sizing.
assert "mem_mib <= 8192" in cfg and "printf 4096" in cfg
assert "usable_max=$((max_mib-overhead))" in cfg
assert '(( gpu_ctx < ram_ctx )) && ram_ctx="$gpu_ctx"' in cfg

# DirectML must honor a small coordinated percentage and fail admission rather than
# silently exceeding a sub-1GiB policy envelope.
assert "VRAM_LIMIT_PCT = max(5" in gateway
assert "refusing to exceed the requested percentage" in gateway
spec = importlib.util.spec_from_file_location("lv_dml_14542", ROOT / "stack/directml-gateway.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class T:
    def __init__(self, n, e=2): self.n=n; self.e=e
    def numel(self): return self.n
    def element_size(self): return self.e
class C:
    num_hidden_layers=2; hidden_size=256; num_attention_heads=8; num_key_value_heads=2
class M:
    config=C()
    def parameters(self): return [T(100_000_000)]
    def buffers(self): return []
mod.VRAM_LIMIT_PCT=12; mod.VRAM_TOTAL_MIB=24576
_plan=mod._model_vram_plan(M())
assert _plan[3] == 2949, _plan
mod.VRAM_TOTAL_MIB=4096
try:
    mod._model_vram_plan(M())
except RuntimeError as exc:
    assert "below the 1024MiB safe minimum" in str(exc)
else:
    raise AssertionError("DirectML silently exceeded a 12% budget on a 4 GiB adapter")

# Runtime truth is distinct from device eligibility. Auto GPU->CPU rebudgets;
# explicitly forced GPU is fail-closed.
for marker in (
    "managed_ollama_processor_class() {", "ollama ps", "LATTICEVALE_OLLAMA_GPU_OFFLOAD_VERIFIED",
    "if [[ \"$requested\" != auto ]]; then", "Refusing to retain GPU-sized resource assumptions",
    "Re-budgeting this hardware/runtime fingerprint as CPU", "write_latticevale_compose_overlay cpu",
):
    assert marker in cfg, marker
assert 'details.append(f"GPU execution verified at runtime by ollama ps ({resolved_accel})")' in audit

# Native Windows Ollama is advisory/user-owned: LatticeVale documents conservative
# recommendations but does not silently set global Windows GPU/resource variables.
assert 'OLLAMA_NUM_PARALLEL", "1", "User"' in installer
assert "OLLAMA_GPU_OVERHEAD" in installer and "does not silently set a global Windows value" in installer

# Existing-install migration remains preservation-first and policy changes force
# resource reconciliation rather than wiping state.
for marker in (
    "Resume / repair", "repair_runtime_policy", "state_mark infrastructure pending",
    "state_mark reconcile pending", "--refresh-resource-policy",
):
    assert marker in cfg, marker

# Release-tree contamination must be impossible to hide behind the test runner.
for bad in ("__pycache__", ".pyc", ".pyo"):
    assert bad in runner, bad
assert "PYTHONDONTWRITEBYTECODE" in runner

# Active documentation consistency: historical release notes may mention older
# versions, but current install/repair entry points must identify v14.5.42/policy v11.
active_docs = [
    REPO / "README.md", ROOT / "README.md", ROOT / "AUDIT.md", REPO / "docs/README.md",
    REPO / "docs/FEATURES.md", REPO / "docs/Instructions.txt", REPO / "docs/Installer Description.txt",
    REPO / "docs/RELEASE.md", REPO / "docs/CHANGELOG.md", REPO / "docs/PATCH-NOTES.md",
    REPO / "docs/SUPPORT.md", REPO / "docs/SOURCES.md", REPO / "docs/SECURITY.md",
    REPO / "docs/NATIVE-OLLAMA-INTEGRATION.md", REPO / "docs/WINDOWS-INTEGRATION-TEST-MATRIX.md",
    REPO / "docs/THIRD-PARTY-NOTICES.md",
]
for path in active_docs:
    text = path.read_text(encoding="utf-8")
    assert "14.5.42" in text, path
for path in (REPO / "README.md", ROOT / "README.md", REPO / "docs/README.md", REPO / "docs/FEATURES.md", REPO / "docs/Instructions.txt"):
    text=path.read_text(encoding="utf-8")
    assert "policy v11" in text.lower() or "resource policy v11" in text.lower(), path
root_readme=(REPO / "README.md").read_text(encoding="utf-8")
assert "Resume / repair installation" in root_readme
assert "resource-policy-report.txt" in root_readme
for path in (ROOT / "README.md", ROOT / "AUDIT.md", REPO / "docs/README.md", REPO / "docs/FEATURES.md", REPO / "docs/RELEASE.md", REPO / "docs/SUPPORT.md"):
    assert "resource-policy-report.txt" in path.read_text(encoding="utf-8"), path
# Current-release preambles cannot accidentally present historical policy v9/v10 as current.
current_sections = {
    REPO / "README.md": "### v14.5.4",
    ROOT / "AUDIT.md": "## v14.5.4",
    REPO / "docs/README.md": "> **v14.5.4:",
    REPO / "docs/SUPPORT.md": "## v14.5.4",
}
for path, boundary in current_sections.items():
    prefix=path.read_text(encoding="utf-8").split(boundary,1)[0].lower()
    assert "current policy v9" not in prefix and "current policy v10" not in prefix, path
    assert "current resource policy v9" not in prefix and "current resource policy v10" not in prefix, path

print("v14.5.42 HARDWARE / CANONICAL RESOURCE / RELEASE CONSISTENCY FIXTURES: PASS")
