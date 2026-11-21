# LatticeVale v14.7.0 resource and qualification review

## Release identity and authority

- Release version: **14.7.0**.
- Install-options schema remains 24; runtime-policy schema remains 13. No persistent-state migration is introduced by this release review.
- `stack/latticevale_arch.py` remains the sole canonical hardware, backend, model, CPU and RAM admission planner.
- `stack/resource-burst-controller.py` remains a bounded runtime allocator. It cannot enlarge the aggregate Docker envelope, lower canonical service floors, or act when ownership, telemetry, fingerprints, or transaction state are uncertain.
- User `compose.override.yaml`, user-selected models/providers, persistent Hermes and Matrix state, secrets, and explicit software references remain user-owned.

## Improvements in this release

1. CI can package a release only from a manifest-verified tree. The generated archive has exactly one `Lattice-Vale/` root, excludes Git metadata and bytecode, records the source commit and archive SHA-256, and is checked before upload.
2. Release-tag builds attach the package, SHA-256 sidecar, and provenance record to the matching GitHub release. Workflow actions are pinned to commit SHAs and Dependabot tracks action updates.
3. A manually dispatched Windows/WSL qualification workflow is available for a dedicated disposable runner. It requires an explicit stack marker, performs read-only verification, and runs a CPU/memory-limited load probe while watching service health and pressure metrics.
4. The resource controller records a bounded, sanitized decision history with per-service before/after limits and the measured signals used by the planner. Allocation rules and aggregate limits are unchanged.
5. The supplied Hermes/Kanban utilities are included as opt-in tools with output redaction, scoped export options, and a clear distinction between safe card metadata and sensitive comments, paths, and worker errors.

## Qualification boundaries

Green hosted CI proves deterministic source, packaging, and parser checks. It does not prove a live Windows install, all WSL configurations, DirectML execution on a specific GPU, Tailscale reachability, sustained-load stability, or preservation on a user's actual data. Run the manual qualification workflow only on an isolated, disposable stack; qualify DirectML inference separately on hardware with that backend.

The resource timer controls Docker service/container cgroup quotas, not per-thread CPU affinity. Per-service limits do not eliminate contention when concurrent demand exceeds available CPU or memory. Hard memory limits can still trigger reclaim or OOM; model-aware floors, host reserve, and the existing fail-closed recovery checks remain authoritative.

## Acceptance checks

- Build from the exact version tag; verify source manifest, package root, no `.git`, no bytecode, artifact SHA-256, and commit provenance.
- Run all deterministic regression shards and both Windows PowerShell parsers.
- On a dedicated target, run install/repair/verify, a bounded CPU/memory soak, and repeat repair. Preserve profiles, Matrix identity and rooms, models, overrides, secrets, and all persistent volumes.
- For DirectML, show selected-adapter identity and successful model inference from the runtime; device enumeration alone is insufficient.
- Review sanitized controller history alongside CPU PSI, runqueue load, cgroup throttling, memory pressure, `memory.events`, and service-health results before changing any limits.
