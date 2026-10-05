# LatticeVale 14.6.3 Test Confidence Levels

> **v14.6.3:** Windows Tailscale remote validation is repeatable for as many already-authorized tailnet devices as desired in one installer run. Every device gets a fresh one-time HTTPS challenge, per-device results are shown immediately, and aggregate results are saved without changing the real Dashboard/Matrix Serve mappings. Installer-options schema 24 remains compatible with interim v14.6.3 state; the obsolete `tailscaleMatrixMaxConnections` value is ignored and no longer written. Current unattended-upgrades feature references remain removed; only ownership-proven cleanup of old LatticeVale APT policy remains.

> **v14.6.2 Hotfix:** fixes the original v14.6.2 Linux bootstrap staging typo that duplicated an `install -m 0644 ... \` command immediately before the `compatibility.conf` copy. The defect could stop Resume / repair or Update / repair with `install: target .../compatibility.conf: Not a directory`. The hotfix changes no schema, data layout, managed-update policy, database-major bounds, DirectML/PyTorch compatibility envelope, or explicit user overrides. Apply the hotfix and rerun the installer; no uninstall or data reset is required.


> **v14.6.3 current-release update policy:** installer-managed application software now uses latest-supported stable upstream resolution when a managed refresh is due; Option 6 forces that refresh immediately after the verified safety backup. Explicit overrides remain preserved, stateful database/cache majors stay compatibility-bounded, and PyTorch/DirectML remains a qualified ABI envelope. Exact resolved artifacts are recorded in `data/latticevale/managed-upstreams.json`.


## v14.6.3 current contract (inheriting v14.6.0 policy-13 architecture)

The canonical architecture fixture includes a **3,328-case** CPU/backend/service-topology property sweep (13 CPU counts × 4 acceleration modes × 64 service/DirectML topologies), irregular RAM/resource sweeps, explicit boundary probes around host-reserve floor/ratio/cap transitions, GPU opt-out, DirectML fail-closed fallback, schema-21→23 and schema-22→23 migration, and aggregate CPU conservation. DirectML fixtures prohibit `torch.inference_mode()` and require `torch.no_grad()`, require the fail-closed fallback helper to exist, require bounded gateway diagnostics on a failed HTTP self-test, and require the version-gated Qwen2 `torch.where` compatibility path. The regression runner isolates each fixture in its own process group so descendants cannot retain CI pipes.

1. **Static/source** — syntax, encoding, manifest, forbidden patterns, architecture ownership assertions.
2. **Deterministic fixtures** — mocked migration, repair, backend, resource-policy, networking, preservation, and release contracts.
3. **WSL integration** — real supported Ubuntu WSL distro behavior.
4. **Docker/service integration** — actual Compose/container health and host-gateway routing.
5. **GPU/backend integration** — physical DirectML/CUDA/ROCm/Vulkan execution on representative hardware.
6. **Complete Windows installer flow** — real fresh install/repair/change/verify/update/uninstall qualification.

A lower level does not claim proof of a higher one. `docs/WINDOWS-INTEGRATION-TEST-MATRIX.md` records live/manual qualification targets separately from deterministic regression coverage.

## Current deterministic contract

The v14.6.3 remote-validation contract validates schema-23/schema-24 compatibility, ignores obsolete `tailscaleMatrixMaxConnections` data, requires fixed independent relay gates, verifies the repeatable device loop, fresh per-device token generation, path-specific Serve cleanup on the Matrix listener, permanent-root preservation, aggregate-result persistence, and absence of the current unattended-upgrades feature. The 14.6.3 hotfix adds identity-domain/client-URL separation and managed Hermes gateway migration coverage. Live device reachability remains a Windows/Tailscale integration qualification target, not a claim made by static fixtures.

The v14.6.3 hotfix requires exactly **147 deterministic fixtures** across six shards, plus both resume simulations, static architecture checks, source-manifest/release-policy verification, and contamination rejection. `v14.6.3-matrix-identity-gateway-hotfix-fixtures.py` covers the identity/URL split, legacy manual-entry diagnostic, listener-path validation, route preservation, and gateway migration contract. The added `v14.6.2-latest-supported-upstream-fixtures.py` contract verifies stable rolling application refs, compatible stateful-major bounds, QMD native host binding, managed ownership migration, custom-override preservation, Option 6 forcing, exact-artifact recording, and the DirectML compatibility envelope. The inherited v14.6.1 additions cover same-version canonical runtime-policy/DirectML repair convergence and cross-version continuity for all eight installer options (v14.5.2 Options 1-7 plus the v14.6.0 Option 8 baseline). Resource-policy fixtures sweep irregular/boundary CPU/RAM/model/GPU inputs and assert invariants; they do not target a specific machine topology.

Current GPU/backend regression coverage must include: DirectML with zero Linux-native Ollama adapters; missing `torch_directml.gpu_memory()` with canonical Windows capacity fallback; >4 GiB devices where legacy 32-bit telemetry is only a lower bound; UMA/shared-memory admission across irregular WSL RAM envelopes; same-name multi-GPU stable-ID selection; a generic non-named-vendor DirectX 12 adapter; transient DirectML failure that activates fallback without changing the policy fingerprint; CUDA/ROCm/Vulkan auto paths; forced-backend fail-closed behavior; and CPU-only qualification. A named physical test PC may appear as an example fixture but must never be a production policy branch or exact resource target.
