# LatticeVale v14.7.0 resource and qualification review

## Release identity and authority

- Release version: **14.7.0**.
- Install-options schema remains 24; runtime-policy schema remains 13. No persistent-state migration is introduced by this release review.
- `stack/latticevale_arch.py` remains the sole canonical hardware, backend, model, CPU and RAM admission planner.
- `stack/resource-burst-controller.py` remains a bounded runtime allocator. It cannot enlarge the aggregate Docker envelope, lower canonical service floors, or act when ownership, telemetry, fingerprints, or transaction state are uncertain.
- User `compose.override.yaml`, user-selected models/providers, persistent Hermes and Matrix state, secrets, and explicit software references remain user-owned.

## Improvements in this release

1. CI can package a release only from a manifest-verified tree. The generated archive has exactly one `Lattice-Vale/` root, excludes Git metadata and bytecode, records the source commit and archive SHA-256, and is checked before upload.
2. Release-tag builds attach the package, SHA-256 sidecar, and provenance record to the matching GitHub release. Workflow actions remain pinned to reviewed commit SHAs; updates are manual.
3. A manually dispatched Windows/WSL qualification workflow is available for a dedicated disposable runner. It requires an explicit stack marker, performs read-only verification, and runs a CPU/memory-limited load probe while watching service health and pressure metrics.
4. The resource controller records a bounded, sanitized decision history with per-service before/after limits and measured signals. A same-version regression correction restores the original v14.6.6 workload-based optional RAM burst cap (larger of baseline + 256 MiB and baseline x 1.75); the later v14.6.9 per-service WSL percentage limits are removed because they can equal the canonical baseline and prohibit borrowing. Static admission rules, per-service model floors, conserved Docker/WSL envelopes, CPU borrowing, pressure guards, Docker ownership checks, and recovery transactions remain unchanged.
5. The supplied Hermes/Kanban utilities are included as opt-in tools with output redaction, scoped export options, and a clear distinction between safe card metadata and sensitive comments, paths, and worker errors.

## Historical-regression acceptance

The original v14.4.1 installation-time weighted allocator is evidence of the
conserved-host-budget principle, **not** a valid runtime donor-safety algorithm:
its hard ceilings did not use live cgroup memory.current or replacement/rollback
transactions. v14.6.0 introduced the canonical backend-aware planner; v14.6.6
introduced demand-driven burst transfers; v14.6.7/8 hardened exact-owned
replacement recovery; v14.6.9 added memory.max and CPU-PSI improvements, but
also introduced per-role WSL-RAM percentage caps that can eliminate Hermes's
borrowable RAM. The consolidated policy restores only the older demand-based
RAM cap while retaining the later protections. Historical v14.6.9 review notes
remain as a record of what changed then, not the current policy authority.

A deterministic 12-GiB, 12-service fixture compares real canonical service
allocations with idle cgroup-measured donors and 88%-utilized Hermes: the prior
per-role cap permitted zero additional Hermes RAM; the restored policy permits
a bounded 16-MiB-quantized loan without increasing aggregate container RAM.
Additional representative 2-64-GiB and 1-32-vCPU cross-product simulation
includes CPU/Vulkan/CUDA/ROCm paths, Windows-native Ollama, WSL-host DirectML,
DirectML with managed or Windows-native fallback, optional services, and
insufficient-service-budget rejection. This is mocked policy behavior.

A Hermes dashboard warning can be based on host MemAvailable thresholds rather
than only Docker's hard cap. A low dashboard number is not proof of a defective
controller: confirm cgroup usage, host PSI, timer logs, and decision history
on the real WSL host before attributing that symptom to this code.

## Qualification boundaries

Green hosted CI proves deterministic source, packaging, and parser checks. It does not prove a live Windows install, all WSL configurations, DirectML execution on a specific GPU, Tailscale reachability, sustained-load stability, or preservation on a user's actual data. Run the manual qualification workflow only on an isolated, disposable stack; qualify DirectML inference separately on hardware with that backend.

The resource timer controls Docker service/container cgroup quotas, not per-thread CPU affinity. Per-service limits do not eliminate contention when concurrent demand exceeds available CPU or memory. Hard memory limits can still trigger reclaim or OOM; model-aware floors, host reserve, and the existing fail-closed recovery checks remain authoritative.

## Acceptance checks

- Build from the exact version tag; verify source manifest, package root, no `.git`, no bytecode, artifact SHA-256, and commit provenance.
- Run all deterministic regression shards and both Windows PowerShell parsers.
- On a dedicated target, run install/repair/verify, a bounded CPU/memory soak, and repeat repair. Preserve profiles, Matrix identity and rooms, models, overrides, secrets, and all persistent volumes.
- For DirectML, show selected-adapter identity and successful model inference from the runtime; device enumeration alone is insufficient.
- Review sanitized controller history alongside CPU PSI, runqueue load, cgroup throttling, memory pressure, `memory.events`, and service-health results before changing any limits.
