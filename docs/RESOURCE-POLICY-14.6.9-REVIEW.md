# LatticeVale v14.6.9 — consolidated resource-policy review

## Authority boundaries

1. `compatibility.conf` controls schema/version compatibility.
2. `stack/latticevale_arch.py` is the canonical, deterministic host CPU/RAM, GPU/backend, model/context and service-floor planner. It emits the policy fingerprint and resource state.
3. `stack/runtime-policy.py` and `stack/backend-capabilities.py` audit canonical admission; `stack/hardware-capabilities.py` supplies measured capabilities.
4. `stack/configure-stack.sh` converts selected options to managed Compose limits and installs the timer. `stack/compose.yaml` defines safe service defaults; managed overlays are generated.
5. `stack/resource-burst-controller.py` may reassign *existing* aggregate Docker hard caps only after identity, fingerprint, current cgroup charge and journal verification. It never adds budget.
6. `stack/state-audit.py`, `stack/diagnostics.py`, and `stack/manage.sh` are verification/entrypoints rather than alternate budgeting authorities.
7. `linux/bootstrap.sh` and `Install-LatticeVale.ps1` handle lifecycle, WSL preflight and verified repair; they must not create a second independent quota formula.

## Historical comparison (supplied source archives)

| Version | Resource-policy capabilities to retain |
|---|---|
| 14.5.46 | Conservative GPU/DirectML readiness, host prerequisites and per-service safeguards; pre-v13 policy, not authoritative for new envelopes |
| 14.6.0 | One canonical policy-v13 CPU/RAM envelope; capability/backend fingerprints; model/context-aware admission |
| 14.6.1 | Canonical repair/runtime-state compatibility and validation |
| 14.6.2 | Bootstrap staging correctness and managed stack continuation |
| 14.6.3 | Runtime/Compose adaptation and feature integration without discarding policy-v13 safety |
| 14.6.4 | Explicit repair/managed configuration convergence |
| 14.6.5 | Config/topology-aware policy, preservation of user overrides and safe reconciliation |
| 14.6.6 | Static priority weights, bounded demand-matched CPU/RAM borrowing, cgroup memory.current donor protections and DirectML reserve |
| 14.6.7 | Durable transaction/rollback, verified replacement identity and conserved envelope rebind |
| 14.6.8 | Replacement CPU and memory recovery under failed repairs; source-level corrections retaining schema 13 |

## v14.6.9 control simplification

Keep a **single canonical deterministic allocator** and a **separate bounded runtime transfer layer**. Do not combine them into one mutable policy: canonical budgets must remain auditable, even when the timer is disabled. Avoid resetting proven burst leases on repair or touching user Compose overrides.

**Memory pressure** stops speculative memory reductions and expansions, but does not itself imply physically saturated CPU cores. A newly demonstrated per-cgroup CFS quota throttle can still request CPU from an already idle verified managed donor *within the exact existing envelope*. OOM-kill signals remain an immediate safety override. A fresh `memory.events:max` delta is a warning of limit reclaim even without an OOM kill, so its service is not eligible for memory donation.

**Limitations:** The observed gateway watchdog stall remains an application event-loop failure. This release cannot promise to resolve it; significant throttling and memory.max events are measured contributory pressure, not proven causation. QMD's 1 GiB floors are intentionally retained because earlier development recorded OOMs at ~304 MiB. No unmeasured memory redistribution or host/WSL RAM expansion is safe.

## Validation

The 151-fixture release contract remains unchanged; the existing bounded-resource regression adds focused memory.max and high-pressure throttle scenarios. The full official GitHub Actions run, Windows PowerShell 5.1/7 checks, and a live overwork soak test remain separate release gates.

## Exact source deltas across uploaded ZIPs

The following comparison is SHA-256 content based; it excludes bundled `.git` objects and generated caches. Counts include non-policy documentation and test changes, so they are *not* counts of independent resource algorithms.

| Transition | All changed files | Resource/lifecycle-related files |
|---|---:|---:|
| 14.5.46 → 14.6.0 | 196 | 12 |
| 14.6.0 → 14.6.1 | 146 | 6 |
| 14.6.1 → 14.6.2 | 165 | 10 |
| 14.6.2 → 14.6.3 | 165 | 10 |
| 14.6.3 → 14.6.4 | 151 | 7 |
| 14.6.4 → 14.6.5 | 153 | 8 |
| 14.6.5 → 14.6.6 | 153 | 10 |
| 14.6.6 → 14.6.7 | 156 | 7 |
| 14.6.7 → 14.6.8 | 145 | 4 |

The runtime burst controller first appears in the supplied 14.6.6 archive. The static canonical allocator appeared in the supplied 14.6.0 archive. Beginning with 14.6.7, the controller gained a substantially larger verified replacement-rebind/transaction layer. These are distinct responsibilities, not safe candidates for blindly concatenating historical implementations.

## Audit snapshot guiding v14.6.9

The user's Nov 20 WSL audit showed Hermes at ~97% of its own 1120 MiB cgroup cap, Honcho Deriver at ~99.8% of 272 MiB, Ollama at ~95% of 5728 MiB, strong CPU PSI and many `memory.events:max` occurrences, but zero `oom_kill` in inspected live cgroups. Gateway logs separately showed event-loop missed liveness probes and a watchdog-triggered exit. The application event-loop cause is not conclusively attributable to container policy. A fixed resource allocator cannot guarantee avoidance of a Python thread-start or event-loop blockage.

## Safety/acceptance gates

- The runtime policy schema remains 13 and options schema remains 24; no unreviewed migration is requested.
- The controller's missing-cgroup, unowned-container, unexpected Compose override, unknown fingerprint, pending journal, and unsupported topology gates remain fail-closed.
- Under memory/IO PSI, CPU borrowing requires measured recent throttling and verified multi-sample idle donors. It conserves the Docker envelope. Under a fresh OOM kill it borrows nothing.
- A fresh `memory.max` delta is a signal of memory reclaim and is *not* equivalent to OOM kill. It prevents use as an idle memory donor and can qualify receiver demand once the high-pressure gate permits redistribution.
- Release qualification requires 151 deterministic regressions, static audit, manifest verification, both Windows PowerShell parsers, and an actual current-install resume/repair/soak test. Do not infer any of those from a single focused fixture.
