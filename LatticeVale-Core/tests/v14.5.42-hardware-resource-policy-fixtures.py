#!/usr/bin/env python3
"""v14.5.42-origin hardware/resource safety fixtures against the current canonical policy."""
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
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() in {"14.5.42", "14.5.43","14.5.44",'14.5.45','14.5.46','14.5.47','14.6.0'}
cfg = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
audit = (ROOT / "stack/state-audit.py").read_text(encoding="utf-8")
compose = (ROOT / "stack/compose.yaml").read_text(encoding="utf-8")
gateway = (ROOT / "stack/directml-gateway.py").read_text(encoding="utf-8")
installer = (ROOT / "Install-LatticeVale.ps1").read_text(encoding="ascii")
runner = (ROOT / "tests/run-regressions.py").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "stack"))
from latticevale_arch import (  # noqa: E402
    gpu_context_recommendation,
    gpu_coordination,
    ram_context_recommendation,
    service_memory_plan,
)

# Canonical policy v12 is frozen once, then consumed by Compose/state/diagnostics.
for marker in (
    "Policy v12 canonicalization", "declare -A resource_policy=(", "[POLICY_VERSION]=12",
    "resource_policy[POLICY_FINGERPRINT]", "resource_policy[HARDWARE_FINGERPRINT]",
    "resource_policy[\"LIMIT_${resource_state_key}_MIB\"]", "resource_policy[\"CPU_${resource_state_key}_MILLI\"]",
    "resource-policy-report.txt", "GPU execution verified:", "Policy fingerprint:", "Hardware fingerprint:",
    "resource_ram_profile() {", "resource_cpu_profile() {", "ollama_gpu_inventory() {", "ollama_gpu_metrics() {",
    "resource_gpu_coordination() {", "runtime-policy.py gpu-coordination", "runtime-policy.py service-plan",
    "GPU_HETEROGENEOUS", "OLLAMA_GPU_OVERHEAD_MIB", "DIRECTML_VRAM_LIMIT_PCT",
):
    assert marker in cfg, marker
for marker in ("canonical architecture", "hardware-capabilities.json", "backend-capabilities.json", "runtime-policy.json", "resource-policy-report.txt", "validate_runtime_policy_document"):
    assert marker in audit, marker

# Downstream generated Compose must consume canonical values rather than re-deriving
# finalized CPU/memory decisions.
emit_start = cfg.index("rm -f compose.latticevale.yaml", cfg.index("Policy v12 canonicalization"))
emit_end = cfg.index("  compose_files='compose.yaml'", emit_start)
emit = cfg[emit_start:emit_end]
assert "resource_policy[CPU_HERMES_MILLI]" in emit and "resource_policy[LIMIT_HERMES_MIB]" in emit
assert "resource_policy[CPU_OLLAMA_MILLI]" in emit and "resource_policy[LIMIT_OLLAMA_MIB]" in emit
assert '"$ollama_cpu" "${mem_limits[ollama]}"' not in emit
assert '"$hermes_cpu" "${mem_limits[hermes]}"' not in emit

# Compact 8 GiB WSL target: service allocation is owned by the canonical engine.
alloc = service_memory_plan(
    7373, matrix=True, searxng=True, qmd=True, ollama=True, honcho=True,
    hermes_floor=1024, ollama_floor=4096,
)
assert sum(alloc.values()) <= 7373, alloc
assert alloc["hermes"] >= 1024 and alloc["ollama"] >= 4096, alloc

# Diverse single/multi-GPU coordination remains per-device, not aggregate VRAM.
for spec in [(1,3071,3071),(1,7169,7169),(2,5921,9713),(2,3587,18721),(3,8011,12289)]:
    got = gpu_coordination("nvidia", spec[0], spec[1], spec[2], "nvidia", True)
    assert got["sharedVendor"] is True, (spec, got)
    assert 256 <= got["ollamaGpuOverheadMiB"] <= int(spec[1] * 0.75) + 256, (spec, got)
    assert 5 <= got["directmlVramLimitPct"] <= 50, (spec, got)
for mismatch in (("cpu",1,4096,4096,"nvidia",True),("nvidia",1,4096,4096,"amd",True),("nvidia",0,0,0,"nvidia",True),("nvidia",1,4096,4096,"nvidia",False)):
    got=gpu_coordination(*mismatch)
    assert got["sharedVendor"] is False and got["ollamaGpuOverheadMiB"] == 0

# Topology is never represented as one fictitious aggregate GPU, and missing VRAM
# telemetry is fail-closed for a selected GPU backend.
assert "count:min:max:aggregate" in cfg
assert "treating aggregate VRAM as one interchangeable pool" in cfg
assert "GPU-backed hard limits must never be based on an invented capacity" in cfg
assert '[[ -n "$inventory" ]] || return 1' in cfg
# Auto intentionally prefers a verified NVIDIA runtime, then AMD/ROCm; simultaneous
# vendors therefore resolve deterministically rather than merging unlike devices.
auto_block = cfg[cfg.index("    auto)"):cfg.index("    *) echo \"Unsupported Ollama acceleration policy", cfg.index("    auto)"))]
assert auto_block.index("nvidia_container_runtime_ready") < auto_block.index("/dev/kfd")

# RAM- and usable-VRAM-aware context sizing is canonical.
allowed={4096,8192,16384,32768,65536}
prev=0
for mem in (2051,4777,8093,12017,19001,33331,70001):
    ctx=ram_context_recommendation(mem)
    assert ctx in allowed and ctx >= prev
    prev=ctx
prev=0
for usable in (0,1537,3581,6143,11003,24011,50021):
    ctx=gpu_context_recommendation(usable)
    assert ctx in allowed and ctx >= prev
    prev=ctx
assert "runtime-policy.py context ram" in cfg and "runtime-policy.py context gpu" in cfg

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

# Active documentation describes 14.6.0/policy v12; historical release notes retain
# the 14.5.42 provenance this fixture protects.
current_docs = [
    REPO / "README.md", ROOT / "README.md", ROOT / "AUDIT.md", REPO / "docs/README.md",
    REPO / "docs/FEATURES.md", REPO / "docs/Instructions.txt", REPO / "docs/RELEASE.md",
    REPO / "docs/SUPPORT.md", REPO / "docs/RESOURCE-POLICY.md", REPO / "docs/GPU-BACKENDS.md",
]
for path in current_docs:
    text = path.read_text(encoding="utf-8")
    assert "14.6.0" in text, path
for path in (REPO / "README.md", ROOT / "README.md", REPO / "docs/README.md", REPO / "docs/FEATURES.md", REPO / "docs/RESOURCE-POLICY.md"):
    text = path.read_text(encoding="utf-8").lower()
    assert "policy v12" in text or "resource policy v12" in text, path
for path in (REPO / "docs/CHANGELOG.md", REPO / "docs/PATCH-NOTES.md"):
    assert "14.5.42" in path.read_text(encoding="utf-8"), path
root_readme=(REPO / "README.md").read_text(encoding="utf-8")
assert "Resume / repair installation" in root_readme
assert "resource-policy-report.txt" in root_readme
for path in (ROOT / "README.md", ROOT / "AUDIT.md", REPO / "docs/README.md", REPO / "docs/FEATURES.md", REPO / "docs/RELEASE.md", REPO / "docs/SUPPORT.md"):
    assert "resource-policy-report.txt" in path.read_text(encoding="utf-8"), path

print("v14.5.42 HARDWARE / CANONICAL RESOURCE / RELEASE CONSISTENCY FIXTURES: PASS")
