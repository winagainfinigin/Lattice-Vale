# LatticeVale 14.6.0 Test Confidence Levels

1. **Static/source** — syntax, encoding, manifest, forbidden patterns, architecture ownership assertions.
2. **Deterministic fixtures** — mocked migration, repair, backend, resource-policy, networking, preservation, and release contracts.
3. **WSL integration** — real supported Ubuntu WSL distro behavior.
4. **Docker/service integration** — actual Compose/container health and host-gateway routing.
5. **GPU/backend integration** — physical DirectML/CUDA/ROCm/Vulkan execution on representative hardware.
6. **Complete Windows installer flow** — real fresh install/repair/change/verify/update/uninstall qualification.

A lower level does not claim proof of a higher one. `docs/WINDOWS-INTEGRATION-TEST-MATRIX.md` records live/manual qualification targets separately from deterministic regression coverage.

## Current deterministic contract

v14.6.0 requires exactly **142 deterministic fixtures** across six shards, plus both resume simulations, static architecture checks, source-manifest/release-policy verification, and contamination rejection. Resource-policy fixtures sweep irregular/boundary CPU/RAM/model/GPU inputs and assert invariants; they do not target a specific machine topology.

Current GPU/backend regression coverage must include: DirectML with zero Linux-native Ollama adapters; missing `torch_directml.gpu_memory()` with canonical Windows capacity fallback; >4 GiB devices where legacy 32-bit telemetry is only a lower bound; UMA/shared-memory admission across irregular WSL RAM envelopes; same-name multi-GPU stable-ID selection; a generic non-named-vendor DirectX 12 adapter; transient DirectML failure that activates fallback without changing the policy fingerprint; CUDA/ROCm/Vulkan auto paths; forced-backend fail-closed behavior; and CPU-only qualification. A named physical test PC may appear as an example fixture but must never be a production policy branch or exact resource target.
