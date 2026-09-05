#!/usr/bin/env python3
"""v14.6.0 canonical hardware/backend/resource architecture regressions.

The resource tests intentionally assert invariants over many arbitrary envelopes.
They do not encode one developer/user machine topology as a policy target.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stack"))
from latticevale_arch import (  # noqa:E402
    _windows_gpu_normalize,
    atomic_write_json,
    classify_backends,
    cpu_quota_plan,
    directml_context_recommendation,
    fingerprint,
    gpu_context_recommendation,
    host_memory_budget,
    ollama_model_floor,
    parse_compatibility,
    ram_context_recommendation,
    runtime_tuning,
    service_memory_plan,
    validate_install_options,
    validate_runtime_policy_state,
    write_backend_health,
)

compat = parse_compatibility(ROOT / "compatibility.conf")
assert compat["INSTALL_OPTIONS_SCHEMA"] == "22"
assert compat["HARDWARE_CAPABILITIES_SCHEMA"] == "1"
assert compat["BACKEND_CAPABILITIES_SCHEMA"] == "1"
assert compat["BACKEND_HEALTH_SCHEMA"] == "1"
assert compat["RUNTIME_POLICY_SCHEMA"] == "12"
assert compat["DIAGNOSTICS_SCHEMA"] == "1"
assert compat["MANAGED_REPAIR_REFRESH_REVISION"] == "4"

# One canonical schema owner: current state passes, future state fails closed, and
# corrected v14.5.47 schema-21 durable choices remain valid migration input.
base_options = {
    "schema": 22,
    "installerVersion": "14.6.0",
    "localTextBackend": "directml",
    "directmlTextModel": "Qwen/Qwen2.5-1.5B-Instruct",
    "ollamaBackend": "managed",
    "ollamaAcceleration": "auto",
    "gpuPreferenceMode": "explicit",
    "gpuPreferenceName": "AMD Radeon RX 6700 XT",
    "gpuPreferenceVendor": "amd",
    "inferenceBackendPreference": "directml",
    "workers": [],
}
validate_install_options(dict(base_options), 22)
try:
    validate_install_options(dict(base_options, schema=23), 22)
except ValueError:
    pass
else:
    raise AssertionError("future install-options schema must fail closed")
validate_install_options(dict(base_options, schema=21, installerVersion="14.5.47", repairOriginSchema=21), 22)

# Host budgeting is continuously derived from live WSL RAM and selected paths.
# Sweep deliberately irregular values so a hidden size table cannot satisfy this test.
ram_samples = [2049, 3077, 4099, 5633, 7427, 10009, 13729, 19661, 28657, 45013, 65521]
for accel in ("cpu", "vulkan", "nvidia", "amd"):
    for managed in (False, True):
        for directml in (False, True):
            previous_budget = -1
            previous_reserve = -1
            for mem in ram_samples:
                result = host_memory_budget(mem, accel, managed, directml)
                reserve = result["reserveMiB"]
                dml = result["directmlHostReserveMiB"]
                budget = result["containerBudgetMiB"]
                assert reserve + budget == mem
                assert 384 <= budget < mem
                assert 0 < reserve < mem
                assert reserve >= previous_reserve
                assert budget > previous_budget
                if directml:
                    assert dml > 0 and reserve >= dml
                else:
                    assert dml == 0
                previous_budget, previous_reserve = budget, reserve

# Supported model contexts scale monotonically from arbitrary RAM/VRAM capacities.
allowed_contexts = {4096, 8192, 16384, 32768, 65536}
for fn in (ram_context_recommendation, gpu_context_recommendation):
    previous = 0
    for mib in [1024, 2311, 4096, 6667, 8193, 12001, 18007, 24581, 36013, 52009, 98317]:
        ctx = fn(mib)
        assert ctx in allowed_contexts and ctx >= previous
        previous = ctx
for mem in [4097, 7169, 11213, 18433, 32771, 65537]:
    for vram in [0, 3073, 6145, 10241, 24577]:
        ctx = directml_context_recommendation(mem, vram)
        assert ctx in allowed_contexts and ctx <= 32768
        assert ctx <= ram_context_recommendation(mem)
        if vram:
            assert ctx <= gpu_context_recommendation(vram)

# CPU ceilings derive from live nproc and workload topology. Every service ceiling is
# bounded by the visible CPU envelope; adding CPUs never lowers a ceiling.
for accel in ("cpu", "vulkan", "nvidia", "amd"):
    prior = None
    for cpus in [1, 2, 3, 5, 7, 11, 16, 24]:
        plan = cpu_quota_plan(cpus, matrix_gateways=3, kanban_concurrency=6, accel=accel)
        assert plan and all(250 <= q <= cpus * 1000 and q % 50 == 0 for q in plan.values())
        if prior is not None:
            assert all(plan[name] >= prior[name] for name in plan)
        prior = plan

# Service memory has one water-filling algorithm. Increasing the budget for the same
# workload cannot reduce an allocation; total allocation never exceeds live budget.
service_budgets = [6143, 7777, 9991, 13007, 17011, 24029, 36037]
previous_plan = None
for budget in service_budgets:
    plan = service_memory_plan(
        budget,
        matrix=True,
        searxng=True,
        qmd=True,
        ollama=False,
        honcho=True,
        hermes_floor=1216,
        ollama_floor=2048,
    )
    assert {"hermes", "synapse", "searxng", "qmd", "honcho-api"} <= set(plan)
    assert plan["hermes"] >= 1216
    assert sum(plan.values()) <= budget
    if previous_plan is not None:
        assert all(plan[name] >= previous_plan[name] for name in previous_plan)
    previous_plan = plan

# Model admission uses actual model/context/GPU inputs. A larger measured model cannot
# produce a smaller host floor; usable GPU memory can reduce host pressure.
for mem in [6147, 10003, 16001, 28001, 48017]:
    ctx = ram_context_recommendation(mem)
    provisional = ollama_model_floor(mem, 0, ctx, "cpu", False)
    measured = [ollama_model_floor(mem, artifact, ctx, "cpu", False) for artifact in (1024, 3072, 6144)]
    assert provisional > 0 and measured == sorted(measured)
    gpu_without_room = ollama_model_floor(mem, 6144, ctx, "nvidia", False, 0, 0)
    gpu_with_room = ollama_model_floor(mem, 6144, ctx, "nvidia", False, 8192, 8192)
    assert gpu_with_room <= gpu_without_room
    assert 0 < provisional < mem

# Allocator/database/cache tuning consumes live host resources and the actual service
# allocations, not RAM-size buckets.
for mem, cpus, synapse_mib, db_mib in [
    (4099, 1, 256, 192), (7181, 3, 448, 320), (12007, 4, 768, 512),
    (19001, 7, 1024, 768), (33013, 12, 1536, 1536), (65521, 24, 2048, 3072),
]:
    tune = runtime_tuning(mem, cpus, synapse_mib, db_mib)
    assert 2 <= tune["mallocArenaMax"] <= 8
    factor = float(tune["synapseCacheFactor"])
    assert 0.20 <= factor <= 0.50
    shared = int(tune["postgresSharedBuffers"].removesuffix("MB"))
    assert 32 <= shared <= 512 and shared <= max(32, db_mib // 2)

# Stable Windows GPU identity is deterministic and distinguishes same-name adapters.
g0 = _windows_gpu_normalize({"name": "Example GPU", "vendor": "amd", "pnpDeviceId": "PCI\\VEN_1002&DEV_0001", "vramMiB": 8192})
g0_again = _windows_gpu_normalize({"name": "Example GPU", "vendor": "amd", "pnpDeviceId": "pci\\ven_1002&dev_0001", "vramMiB": 8192})
g1 = _windows_gpu_normalize({"name": "Example GPU", "vendor": "amd", "pnpDeviceId": "PCI\\VEN_1002&DEV_0002", "vramMiB": 8192})
assert g0["id"] == g0_again["id"] and g0["id"] != g1["id"] and g0["id"].startswith("gpu-")

bridge = {k: {"present": True} for k in ("libd3d12.so", "libd3d12core.so", "libdxcore.so")}
def hw(*, dxg=False, kfd=False, dri=(), nvidia=False, gpus=None, windows_build=26200, memory_mib=16384):
    payload = {"schema": 1, "windows": {"build": windows_build, "gpus": gpus or []}, "wsl": {
        "architecture": "x86_64", "memoryMiB": memory_mib, "dxg": {"present": dxg}, "directxBridgeLibraries": bridge if dxg else {},
        "driRenderNodes": list(dri), "drmAdapters": [], "kfd": {"present": kfd},
        "nvidiaSmi": {"available": nvidia, "gpus": [{"name": "NVIDIA Example", "vramMiB": 12291}] if nvidia else []},
        "vulkan": {"toolPresent": bool(dri), "probeSucceeded": bool(dri), "devices": ["Example"] if dri else []},
    }}
    payload["hardwareFingerprint"] = fingerprint(payload)
    return payload

# User test-PC regression profile: RDNA2 RX 6700 XT with DirectML exposed through
# /dev/dxg but no Linux-native ROCm/DRM device requirement. The exact model is an
# example only; policy behavior is driven entirely by reported capabilities/memory.
amd_gpu = {"id": "gpu-amd", "name": "AMD Radeon RX 6700 XT", "vendor": "amd", "vramMiB": 12272,
           "dedicatedMemoryMiB": 12272, "sharedMemoryMiB": 16384,
           "memorySource": "windows-dxdiag-text", "memoryConfidence": "high", "memoryIsLowerBound": False}
intel_gpu = {"id": "gpu-intel", "name": "Intel Arc Example", "vendor": "intel", "vramMiB": 8195,
             "dedicatedMemoryMiB": 8195, "sharedMemoryMiB": 8192,
             "memorySource": "windows-dxdiag-xml", "memoryConfidence": "high", "memoryIsLowerBound": False}
with tempfile.TemporaryDirectory() as td:
    stack = Path(td)
    # The example discrete adapter is tested across unrelated WSL memory envelopes.
    # Dedicated-memory admission comes from detected adapter facts, never a host-RAM
    # table or a model-name special case.
    discrete_results = []
    for live_mem in (6145, 10007, 17321, 32771, 65539):
        case_hw = hw(dxg=True, gpus=[amd_gpu], memory_mib=live_mem)
        case = classify_backends(case_hw, base_options, stack, compat)
        assert case["selection"]["inferenceBackend"] == "directml"
        assert case["selection"]["textBackend"] == "directml"
        assert case["selection"]["activeTextBackend"] == "directml"
        assert case["adapterSelection"]["selected"]["id"] == "gpu-amd"
        assert case["capabilities"]["rocm"]["available"] is False
        assert case["adapterSelection"]["selected"]["directmlAdmission"]["capacityMiB"] == amd_gpu["dedicatedMemoryMiB"]
        assert case["adapterSelection"]["selected"]["directmlAdmission"]["source"] == amd_gpu["memorySource"]
        discrete_results.append((case_hw, case))

    # A runtime DirectML failure must activate the gateway fallback without making
    # the resource-policy topology stale. This is the exact failure class observed
    # on a real repair where tensor/device setup worked but VRAM reporting did not.
    test_hw, d = discrete_results[2]
    policy_fp = d["backendFingerprint"]
    runtime_fp = d["runtimeHealthFingerprint"]
    write_backend_health(stack, compat, "directml", "failed", "DML_VRAM_CAPACITY_UNAVAILABLE", test_hw["hardwareFingerprint"], "runtime memory API unavailable")
    degraded = classify_backends(test_hw, base_options, stack, compat)
    assert degraded["backendFingerprint"] == policy_fp
    assert degraded["runtimeHealthFingerprint"] != runtime_fp
    assert degraded["selection"]["textBackend"] == "directml"
    assert degraded["selection"]["activeTextBackend"] == "ollama"
    assert degraded["selection"]["runtimeFallbackActive"] is True

    # UMA/integrated adapters can have little dedicated memory but a bounded shared
    # memory ceiling. Admission scales from live WSL RAM and the Windows-reported
    # shared limit instead of using a fixed PC topology.
    uma = {"id": "gpu-uma", "name": "Intel Integrated Example", "vendor": "intel",
           "dedicatedMemoryMiB": 128, "vramMiB": 128, "sharedMemoryMiB": 8192,
           "memorySource": "windows-dxdiag-text", "memoryConfidence": "high"}
    uma_opts = dict(base_options, gpuPreferenceName="Intel Integrated Example", gpuPreferenceVendor="intel", gpuPreferenceId="gpu-uma")
    prior_capacity = 0
    for live_mem in (4099, 7177, 12293, 24593, 49157):
        uma_hw = hw(dxg=True, gpus=[uma], memory_mib=live_mem)
        uma_caps = classify_backends(uma_hw, uma_opts, stack, compat)
        admission = uma_caps["adapterSelection"]["selected"]["directmlAdmission"]
        assert admission["memoryKind"] == "shared-uma"
        assert 512 <= admission["capacityMiB"] <= min(uma["sharedMemoryMiB"], live_mem)
        assert admission["capacityMiB"] >= prior_capacity
        prior_capacity = admission["capacityMiB"]

    same_name = [dict(amd_gpu, id="gpu-a", pnpDeviceId="PCI-A"), dict(amd_gpu, id="gpu-b", pnpDeviceId="PCI-B")]
    explicit_id = dict(base_options, gpuPreferenceId="gpu-b", gpuPreferencePnpDeviceId="PCI-B", gpuPreferenceName="AMD Radeon RX 6700 XT")
    d = classify_backends(hw(dxg=True, gpus=same_name), explicit_id, stack, compat)
    assert d["adapterSelection"]["selected"]["id"] == "gpu-b"
    assert d["adapterSelection"]["reasonCode"] == "GPU_EXPLICIT_STABLE_ID_MATCH"

    d = classify_backends(hw(dxg=True, gpus=[amd_gpu], windows_build=19045), base_options, stack, compat)
    assert d["capabilities"]["directml"]["available"] is False
    assert d["capabilities"]["directml"]["reasonCode"] == "DML_WINDOWS_BUILD_UNSUPPORTED"

    missing = dict(base_options, gpuPreferenceName="GPU that no longer exists")
    d = classify_backends(hw(dxg=True, gpus=[amd_gpu]), missing, stack, compat)
    assert d["selection"]["requestedInferenceBackend"] == "directml"
    assert d["selection"]["inferenceBackend"] == "cpu"
    assert d["selection"]["selectionReasonCode"] == "BACKEND_EXPLICIT_UNAVAILABLE_SAFE_FALLBACK"

    # Generic DirectX 12 adapters are not rejected solely because their vendor is
    # outside the named CUDA/ROCm families. DirectML remains capability-driven and
    # an explicit generic adapter can be selected by stable ID/name.
    other_gpu = {"id": "gpu-other", "name": "DirectX 12 Example Adapter", "vendor": "other",
                 "dedicatedMemoryMiB": 6147, "vramMiB": 6147, "sharedMemoryMiB": 4096,
                 "memorySource": "windows-registry-qword", "memoryConfidence": "high"}
    other_opts = dict(base_options, gpuPreferenceName=other_gpu["name"], gpuPreferenceVendor="other", gpuPreferenceId="gpu-other")
    validate_install_options(other_opts, 22)
    other_caps = classify_backends(hw(dxg=True, gpus=[other_gpu], memory_mib=14011), other_opts, stack, compat)
    assert other_caps["selection"]["textBackend"] == "directml"
    assert other_caps["adapterSelection"]["selected"]["vendor"] == "other"
    assert other_caps["adapterSelection"]["selected"]["directmlAdmission"]["capacityMiB"] == 6147

    auto = dict(base_options, localTextBackend="ollama", inferenceBackendPreference="auto", gpuPreferenceMode="auto", gpuPreferenceName="", gpuPreferenceVendor="")
    assert classify_backends(hw(nvidia=True), auto, stack, compat)["selection"]["inferenceBackend"] == "cuda"
    assert classify_backends(hw(kfd=True, dri=["/dev/dri/renderD128"]), auto, stack, compat)["selection"]["inferenceBackend"] == "rocm"
    assert classify_backends(hw(dri=["/dev/dri/renderD128"], gpus=[intel_gpu]), auto, stack, compat)["selection"]["inferenceBackend"] == "vulkan"
    cpu = classify_backends(hw(), auto, stack, compat)
    assert cpu["selection"]["inferenceBackend"] == "cpu"
    assert cpu["qualification"]["qualifiedForCoreStack"] is True

# Persisted writer/verifier agreement is tested from dynamically calculated values,
# never from one known machine's numbers.
for mem in [4099, 7331, 10103, 15401, 27109, 50021]:
    budget = host_memory_budget(mem, "cpu", True, True)
    state = {
        "POLICY_VERSION": "12",
        "MEM_MIB": str(mem),
        "OLLAMA_ACCELERATION": "cpu",
        "MANAGED_OLLAMA_SELECTED": "true",
        "DIRECTML_SELECTED": "true",
        "RESERVE_MIB": str(budget["reserveMiB"]),
        "DIRECTML_HOST_RESERVE_MIB": str(budget["directmlHostReserveMiB"]),
        "BUDGET_MIB": str(budget["containerBudgetMiB"]),
        "RESOURCE_POLICY_MODE": "adaptive",
    }
    material = "".join(f"{k}={state[k]}\n" for k in sorted(state))
    state["POLICY_FINGERPRINT"] = hashlib.sha256(material.encode()).hexdigest()
    valid = validate_runtime_policy_state(state, compat)
    assert valid["policyFingerprint"] == state["POLICY_FINGERPRINT"]
    bad = dict(state, RESERVE_MIB=str(budget["reserveMiB"] + 64))
    try:
        validate_runtime_policy_state(bad, compat)
    except ValueError as exc:
        assert "mismatch" in str(exc).lower()
    else:
        raise AssertionError("writer/verifier memory drift must fail")

with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "state.json"
    atomic_write_json(path, {"schema": 1, "ok": True})
    assert json.loads(path.read_text()) == {"ok": True, "schema": 1}
    assert not list(Path(td).glob(".*.tmp-*"))

cfg = (ROOT / "stack/configure-stack.sh").read_text()
arch = (ROOT / "stack/latticevale_arch.py").read_text()
runtime = (ROOT / "stack/runtime-policy.py").read_text()
assert "latticevale_arch.py validate-options install-options.json" in cfg
assert "PY_OPTIONS_VALIDATE" not in cfg
assert "DEFAULT_SCHEMAS" not in arch
assert "Missing {key} in compatibility.conf" in arch
for marker in ("runtime-policy.py host-budget", "runtime-policy.py cpu-plan", "runtime-policy.py service-plan", "runtime-policy.py tuning", "runtime-policy.py ollama-floor"):
    assert marker in cfg
assert "LOW_MEMORY_PROFILE" not in cfg and "mem_mib <= 12288" not in cfg
assert "lowmem" not in runtime.lower()
assert "resource_cpu_limit_string" in cfg
assert "directml_reserve_mib=$((mem_mib/4))" not in cfg
assert "PY_RESOURCE_PLAN" not in cfg and "hermes_cpu=$(((" not in cfg
# Current architecture code may contain safety minima/caps, but no known-user topology
# numbers may appear as policy branches or exact expected outputs.
for forbidden in ("11962", "2990", "8972"):
    assert forbidden not in arch and forbidden not in cfg

ps = (ROOT / "Install-LatticeVale.ps1").read_text()
assert "Get-LatticeValeGpuStableId" in ps
for marker in ("HardwareInformation.qwMemorySize", "MatchingDeviceId", "SharedMemoryMiB", "MemoryConfidence", "Get-LatticeValeWindowsHardwareSnapshot", "windows-hardware.json",
               "windows-registry-dword-lower-bound", "may never cap", "Other DirectX 12 display adapter"):
    assert marker in ps
assert "gpuPreferenceId = if ($localTextBackend" in ps and "gpuPreferencePnpDeviceId = if ($localTextBackend" in ps
assert "stableId = [string]$_.StableId" in ps
print("v14.6.0 canonical architecture fixtures: PASS")
