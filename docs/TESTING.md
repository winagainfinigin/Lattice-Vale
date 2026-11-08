# LatticeVale 14.6.7 Test Confidence Levels

## Portable CPU-priority and timer-activation follow-up verification

The same-version follow-up tests static CPU weights on 1, 2, 4, 8, 16, 32,
and 64 logical CPUs, CPU/Vulkan/NVIDIA/AMD backend selections, optional local
Ollama, and DirectML host reservation. They verify every enabled service's
50-milli-CPU minimum, unchanged aggregate/system headroom, and higher Hermes
and CPU-inference weighting where the envelope permits it. Synthetic high
CPU PSI with low/high host runqueue load must not block **within-envelope**
borrowing; genuine host contention suppresses additional DirectML reserve
lending. Bootstrap must admit the same verified image-only override as the
controller's resolved Compose comparison. Timer cadence and cooldown checks
are covered. `--check-override` is read-only and needs no Docker socket inside
Hermes. Full live behavior still requires Windows/WSL/Docker integration tests.

## Demand-matched burst scheduler follow-up verification

The updated `v14.6.6-burst-resource-fixtures.py` covers recipient-capacity
matching, no speculative CPU/memory donation, priority-dependent idle service
CPU floors, cgroup-charged memory protection and missing-telemetry fallback,
measured CPU throttling bypass during cooldown, DirectML reserve recovery,
Compose image-only override admission versus resource/env override rejection,
transaction rollback, and deterministic CPU/RAM invariant sweeps. It also
exercises WSL-visible processor counts of 1, 2, 4, 8, 16, 32, and 64, and
RAM allocations from 2 through 128 GiB for both ordinary and DirectML
planning. Impossible full-stack topologies fail instead of manufacturing
capacity. The overall regression file count stays at 151.

These tests prove **source behavior and conserved envelopes**, not deployment
or speed. For real qualification, compare the pre-burst canonical v13 policy,
original v14 scheduler, and demand-matched hotfix using equivalent WSL CPU/RAM
settings and workloads. Observe p50/p95 interactive response time, throughput,
per-container CPU throttling, memory PSI, `memory.events`, crashes, CPU/RAM
quota restoration, DirectML activity, and Windows/WSL responsiveness. A few
Docker stats snapshots alone cannot establish causality. Preserve explicit
`.wslconfig` and user-owned Compose settings across comparisons.


> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.

> **v14.6.6 Tailscale correction (carried forward from the v14.6.5 corrective overlay):** Dashboard and Matrix remote HTTPS may validate over IPv4, IPv6, or both. Certificate validation and direct-IP/no-proxy testing remain enabled. Windows listener enumeration is advisory when an authenticated HTTPS path and the selected application checks succeed; successful Serve mappings are retained rather than removed after a listener-only false-negative.


> **v14.6.5:** Windows Tailscale setup validates the local relay, Serve listener, and Matrix client API without a second-device page challenge. Permitted tailnet devices use the displayed service URL; exact matching Serve rules remain in place without a restart. Existing Synapse identity stays authoritative; Matrix ID domains, Element URLs, and Tailscale hostnames remain separate. Existing-stack repairs include pre-install backup progress with a per-run skip, planned Ubuntu APT refresh progress with a per-run skip, streamed cleanup output, and a fast path that skips unnecessary cache/staging cleanup when the WSL root has at least 2 GiB free. Schema 24 remains compatible.

> **v14.6.2 Hotfix:** fixes the original v14.6.2 Linux bootstrap staging typo that duplicated an `install -m 0644 ... \` command immediately before the `compatibility.conf` copy. The defect could stop Resume / repair or Update / repair with `install: target .../compatibility.conf: Not a directory`. The hotfix changes no schema, data layout, managed-update policy, database-major bounds, DirectML/PyTorch compatibility envelope, or explicit user overrides. Apply the hotfix and rerun the installer; no uninstall or data reset is required.


> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.


## v14.6.7 current contract (inheriting v14.6.0 policy-13 architecture)

The canonical architecture fixture includes a **3,328-case** CPU/backend/service-topology property sweep (13 CPU counts × 4 acceleration modes × 64 service/DirectML topologies), irregular RAM/resource sweeps, explicit boundary probes around host-reserve floor/ratio/cap transitions, GPU opt-out, DirectML fail-closed fallback, schema-21→23 and schema-22→23 migration, and aggregate CPU conservation. DirectML fixtures prohibit `torch.inference_mode()` and require `torch.no_grad()`, require the fail-closed fallback helper to exist, require bounded gateway diagnostics on a failed HTTP self-test, and require the version-gated Qwen2 `torch.where` compatibility path. The regression runner isolates each fixture in its own process group so descendants cannot retain CI pipes.

1. **Static/source** — syntax, encoding, manifest, forbidden patterns, architecture ownership assertions.
2. **Deterministic fixtures** — mocked migration, repair, backend, resource-policy, networking, preservation, and release contracts.
3. **WSL integration** — real supported Ubuntu WSL distro behavior.
4. **Docker/service integration** — actual Compose/container health and host-gateway routing.
5. **GPU/backend integration** — physical DirectML/CUDA/ROCm/Vulkan execution on representative hardware.
6. **Complete Windows installer flow** — real fresh install/repair/change/verify/update/uninstall qualification.

A lower level does not claim proof of a higher one. `docs/WINDOWS-INTEGRATION-TEST-MATRIX.md` records live/manual qualification targets separately from deterministic regression coverage.

## Current deterministic contract

The v14.6.5 remote-access contract validates schema-23/schema-24 compatibility, ignores obsolete `tailscaleMatrixMaxConnections` data, requires fixed independent relay gates, keeps matching Serve routes without restart, and verifies local relay/listener/Matrix API checks without a second-device page challenge. It also covers pre-install backup progress and run-level skip, APT refresh progress and run-level skip, low-space-only pre-maintenance cleanup, streamed Option 7 cleanup, identity-domain/client-URL separation, managed Hermes gateway migration, and absence of current unattended-upgrades behavior. Live device reachability remains a Windows/Tailscale integration qualification target, not a claim made by static fixtures.

The v14.6.5 hotfix requires exactly **148 deterministic fixtures** across six shards, plus both resume simulations, static architecture checks, source-manifest/release-policy verification, and contamination rejection. `v14.6.4-gateway-live-convergence-fixtures.py` remains the inherited gateway-convergence fixture and now also asserts 14.6.5 hotfix behavior: quiet speculative checkpoint verification, bounded settle windows before shared-gateway migration, timeout-with-convergence recovery, fresh/stale state, missing profiles, PID mismatch, explicit standalone exclusion, same-version no-remigration/no-unnecessary-restart ordering, marker-as-evidence semantics, shared/standalone Matrix routing, connected adapter verification, and corrected audit wording. `v14.6.3-matrix-identity-gateway-hotfix-fixtures.py` covers the identity/URL split, legacy manual-entry diagnostic, listener-path validation, route preservation, and gateway migration contract. The `v14.6.2-latest-supported-upstream-fixtures.py` contract verifies stable rolling application refs, compatible stateful-major bounds, QMD's effective Compose `--host 0.0.0.0` binding, `QMD_ALLOWED_HOSTS`, and its Dockerfile default, managed ownership migration, custom-override preservation, Option 6 forcing, exact-artifact recording, and the DirectML compatibility envelope. The inherited v14.6.1 additions cover same-version canonical runtime-policy/DirectML repair convergence and cross-version continuity for all eight installer options (v14.5.2 Options 1-7 plus the v14.6.0 Option 8 baseline). Resource-policy fixtures sweep irregular/boundary CPU/RAM/model/GPU inputs and assert invariants; they do not target a specific machine topology.

Current GPU/backend regression coverage must include: DirectML with zero Linux-native Ollama adapters; missing `torch_directml.gpu_memory()` with canonical Windows capacity fallback; >4 GiB devices where legacy 32-bit telemetry is only a lower bound; UMA/shared-memory admission across irregular WSL RAM envelopes; same-name multi-GPU stable-ID selection; a generic non-named-vendor DirectX 12 adapter; transient DirectML failure that activates fallback without changing the policy fingerprint; CUDA/ROCm/Vulkan auto paths; forced-backend fail-closed behavior; and CPU-only qualification. A named physical test PC may appear as an example fixture but must never be a production policy branch or exact resource target.


### 14.6.5 regression gate

The Windows Obsidian check now verifies an executable through registered Windows application locations, uninstall records, common installations, and optional Winget inventory. Confirmed installations are preserved; inconclusive evidence remains UNKNOWN rather than being treated as absent. Resource-policy source-option identity now selects durable resource-relevant inputs rather than transient repair/backup/Windows integration controls; unchanged legacy full-options hashes with valid document integrity are accepted for compatibility. Pre-migration shared-gateway live readiness now receives up to twelve checks separated by two seconds, preserving already converging processes. Windows storage display normalizes a drive's trailing colon. Added deterministic preservation fixtures; the live Windows/WSL end-to-end path still requires verification on its target host.

## 14.6.5 follow-up fixtures

`LatticeVale-Core/tests/v14.6.5-preservation-hotfix-fixtures.py` executes the installer-embedded Windows-state Python writer against temporary state files: installed Obsidian/live Windows metadata, Linux checkpoint preservation, repeatable writes, optional event-log failure, malformed existing JSON, and atomic temporary-file cleanup. It also simulates OOM/no-OOM Docker inspect outputs for the bounded, non-mutating warning path. The deterministic fixture count remains **149**. These tests do not substitute for PowerShell/WSL end-to-end execution or measuring actual QMD memory usage on the target PC.

### QMD allocation correction regression (14.6.5)

`tests/v14.6.5-qmd-resource-floor-fixtures.py` exercises minimum-fit, full multi-service budget conservation, monotonic service allocations, disabled-service identity, under-budget refusal, and the shipping generator/verifier's shared canonical resource formula. Verify that Resume / repair changes stale 304 MiB QMD indexer ceilings rather than concluding an unchanged policy fingerprint is current. Live WSL/Docker verification of the actual default QMD embedding workload remains necessary; fixture results do not prove `qmd embed` succeeds under every container/runtime environment.

### v14.6.6 bounded resource-burst hotfix verification

The 151-fixture suite adds `v14.6.6-burst-resource-fixtures.py`. It tests
canonical host-budget relaxation, workload-derived CPU weights/memory floors,
unused quota borrowing, aggregate conservation, DirectML transitions,
CPU/memory/I/O pressure response, Docker OOM freshness, fake transaction
rollback, and hundreds of arbitrary simulated loads. The fixture also checks
timer registration, uninstall cleanup, source/Compose wiring, and read-only
audit acceptance of exact dynamic snapshots. Live Windows/WSL/Docker
reconciliation must still be verified on the target host; simulated tests
are not an end-to-end performance result.
