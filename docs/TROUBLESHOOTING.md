# LatticeVale 14.6.0 Troubleshooting

## Repair fails after generating configuration

Use the reported stage and reason code. Do not immediately recreate the distro. Run the read-only diagnostics and rerun Option 1 after correcting the prerequisite. Current generated options/policy must validate through the canonical architecture layer before downstream service work continues.

## Windows sees a GPU but WSL reports no Linux GPU adapters

That is not enough evidence to declare all GPU acceleration broken. Check each route separately:

- DirectML: `/dev/dxg`, projected D3D12/DXCore libraries, DirectML runtime/tensor probe;
- CUDA: WSL NVIDIA runtime/device visibility;
- ROCm: `/dev/kfd` and DRM topology;
- Vulkan: DRM render device plus runtime execution proof.

CPU fallback remains valid when no GPU backend is usable.

## DirectML gateway uses Ollama fallback because memory capacity is unavailable

If the gateway reports `DML_VRAM_CAPACITY_UNAVAILABLE`, do not install arbitrary WSL GPU packages or disable the safety check. Current 14.6.0 first tries the DirectML runtime's own capacity API, then the canonical PNP-correlated Windows memory inventory. Discrete dedicated memory and UMA/shared memory are handled differently. If neither produces a trustworthy bounded admission ceiling, DirectML intentionally falls back rather than loading an unbounded model.

Run Option 8 or `./directml-gateway.sh diagnose` and inspect the selected adapter, declared memory source/confidence, `/dev/dxg`, D3D12/DXCore bridge libraries, and tensor result. Windows/WSL projection or vendor-driver failure is a host prerequisite problem; successful projection with missing/mis-correlated canonical memory is a LatticeVale diagnostic/admission problem.

A DirectML runtime fallback is transient health state. It should not by itself make `runtime-policy.json` stale when the policy topology and host reserve remain conservative; Resume / repair may retry DirectML after a material hardware/driver/WSL fingerprint change.

## DirectML chose the wrong GPU

Run `./directml-gateway.sh diagnose` and `./manage.sh diagnose-backends`. Explicit adapter identity is applied before DirectML import and verified again in runtime. If the explicitly saved adapter no longer exists, LatticeVale preserves the saved intent but does not silently redirect it to an unrelated device.

## Resource policy says stale

Run `./manage.sh diagnose-policy`. Hardware/backend fingerprint changes intentionally invalidate dependent derived policy. Option 1 regenerates it using the canonical budget API.

## Patch ZIP versus full release

The repository patch ZIP contains only changed/new repository files relative to the declared parent release. It is not a live-stack overlay. Existing installations should always be updated/repaired through the full release installer.
