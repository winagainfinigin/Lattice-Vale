# LatticeVale 14.6.1 GPU and Inference Backends

## Current GPU-choice and DirectML fallback contract

The installer asks **Use GPU acceleration?**. Choosing No is a durable CPU-only policy preserved by Resume / repair. If DirectML is selected, text fallback is separately chosen as **Native Windows Ollama**, **Managed WSL/Docker Ollama**, or **No Ollama text fallback — fail closed**. Honcho may still use Ollama for embeddings when DirectML text fallback is disabled; embedding use does not silently enable text fallback. DirectML generation uses `torch.no_grad()`. Repeated DirectML startup/self-test failure may create a forced-fallback marker only when a text fallback was explicitly enabled; fallback `none` removes legacy markers and remains unavailable/fail-closed.

## Capability model

14.6.0 does not equate "a GPU exists" with "a backend works." It records Windows GPU identity separately from WSL-visible device/runtime capability and classifies each inference route independently.

| Route | Minimum topology signal | Runtime proof |
|---|---|---|
| DirectML | WSL `/dev/dxg` + projected D3D12/DXCore libraries | `torch_directml` import, adapter enumeration/identity, tensor execution; model self-test before healthy state |
| CUDA | usable WSL NVIDIA runtime/device visibility | managed Ollama GPU execution proof |
| ROCm | appropriate `/dev/kfd` + DRM devices on supported architecture | managed Ollama GPU execution proof |
| Vulkan | WSL DRM render device | managed Ollama Vulkan execution/offload proof |
| Native Windows Ollama | selected user-owned Windows Ollama relay path | relay/runtime health |
| CPU | qualified CPU/WSL environment | normal model/runtime health |

DirectML is a WSL-host path and is intentionally independent of Docker/Linux-native CUDA/ROCm enumeration. A machine can therefore have `Linux-native Ollama GPU inventory=0` while DirectML remains valid through `/dev/dxg`.

Microsoft supports PyTorch with DirectML inside WSL2 on supported Windows 11 builds. LatticeVale therefore does not force DirectML workloads back to native Windows merely because the GPU is AMD, Intel, NVIDIA, Qualcomm, or another adapter that the actual WSL DirectML runtime can qualify. Windows/WSL GPU projection and the vendor display driver are host prerequisites; LatticeVale owns its isolated `torch-directml` environment, adapter correlation, bounded model admission, runtime qualification, and fallback.

## DirectML framework compatibility

The managed DirectML environment is isolated under the LatticeVale stack and pins the tested PyTorch/torch-directml/Transformers envelope. A system-wide Python or CUDA wheel is not used as runtime proof for the managed gateway. The installer first performs a real DirectML tensor operation, then a model-generation self-test before marking DirectML healthy.

Transformers 4.46.3 Qwen2/Qwen2.5 uses causal-mask operations that have failed on torch-directml despite a successful basic tensor probe. v14.6.0 applies a narrowly scoped process-local compatibility shim for that pinned Qwen2 path, replacing the problematic in-place boolean multiplication/`masked_fill` construction with equivalent `torch.where` operations. The shim is version-gated, does not patch upstream files on disk, and is not keyed to AMD, NVIDIA, Intel, Qualcomm, a GPU model name, or a fixed PC configuration. Other models remain subject to the normal model self-test and fail/fallback policy.

## DirectML memory admission

`torch_directml.gpu_memory()` is useful when available but is not treated as the only trustworthy capacity source. LatticeVale correlates the selected Windows adapter by stable/PNP identity and records memory evidence with provenance/confidence:

1. DXDiag XML and text dedicated/shared/display memory, correlated to the selected Windows adapter where possible;
2. the display driver's 64-bit `HardwareInformation.qwMemorySize`;
3. legacy DWORD/WMI values only as conservative lower bounds. Lower-bound telemetry can fill a missing capacity but is never allowed to cap a stronger full-capacity source.

Discrete GPUs use bounded dedicated-memory evidence. Integrated/UMA adapters keep shared memory separate and receive a conservative ceiling bounded by both Windows-reported shared capacity and live WSL RAM. No production rule contains a GPU-model lookup or a known-PC RAM value. If no bounded source can be established, DirectML model admission still fails closed and the configured fallback remains available.

An RX 6700 XT is retained only as a regression example: with a healthy WSL DirectML bridge it remains DirectML-eligible even when a Linux-native ROCm path is absent. ROCm, CUDA, Vulkan, and DirectML are qualified independently from live topology/runtime evidence rather than inferred from the adapter name.

## Adapter identity

Windows adapters receive stable derived IDs from vendor, PNP identity, and name. Explicit adapter choice is matched against the current Windows snapshot. LatticeVale does not silently redirect an explicit saved adapter to an unrelated GPU if hardware order changes.

For DirectML, the selected adapter name is applied before `torch_directml` initialization using the WSL D3D12 adapter-selection environment, then checked again inside the runtime.

## Health and fingerprints

Runtime success/failure state is tied to the canonical hardware fingerprint, but runtime health has its **own** fingerprint and is not part of the resource-policy topology fingerprint. A DirectML model failure may therefore activate Ollama fallback without making an otherwise conservative DirectML host/resource policy stale. A materially different driver/WSL/GPU environment invalidates stale health evidence and permits a bounded retry; repeated failures on the same environment remain bounded to avoid crash loops.

## Automatic selection

Automatic mode prefers a usable native GPU runtime when proven/available, may use Vulkan where appropriate, and falls back to CPU. DirectML is selected for the DirectML text path when its WSL bridge and explicit adapter requirements are satisfied. Runtime proof can demote a candidate backend without rewriting durable user preference.

## Multi-GPU systems

GPU memory is not blindly aggregated. Per-device identity/capacity is retained, DirectML is pinned to a validated adapter, and shared/heterogeneous GPU topology is handled separately by the existing resource-policy layer. A selected adapter disappearing is a recoverable capability change, not permission to silently choose a different explicit device.

## External driver ownership

LatticeVale does not install or replace Windows/vendor display drivers and does not fabricate missing WSL GPU device projection. CUDA/ROCm/Vulkan/DirectML availability depends on the host/WSL environment exposed by those external components. Once a LatticeVale-managed backend is selected, its isolated packages, probes, adapter selection, admission policy, and safe fallback are LatticeVale responsibilities.
