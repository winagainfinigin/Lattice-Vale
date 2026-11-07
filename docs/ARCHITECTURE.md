# LatticeVale 14.6.6 Corrective Hotfix Architecture

> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.

> **v14.6.6 Tailscale correction (carried forward from the v14.6.5 corrective overlay):** Dashboard and Matrix remote HTTPS may validate over IPv4, IPv6, or both. Certificate validation and direct-IP/no-proxy testing remain enabled. Windows listener enumeration is advisory when an authenticated HTTPS path and the selected application checks succeed; successful Serve mappings are retained rather than removed after a listener-only false-negative.


> **v14.6.2 Hotfix:** fixes the original v14.6.2 Linux bootstrap staging typo that duplicated an `install -m 0644 ... \` command immediately before the `compatibility.conf` copy. The defect could stop Resume / repair or Update / repair with `install: target .../compatibility.conf: Not a directory`. The hotfix changes no schema, data layout, managed-update policy, database-major bounds, DirectML/PyTorch compatibility envelope, or explicit user overrides. Apply the hotfix and rerun the installer; no uninstall or data reset is required.


> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.


## Schema 23 / policy 13 ownership

Schema 23 adds durable GPU enablement and DirectML text-fallback intent. Policy 13 derives one CPU envelope from WSL-visible processors and divides only its Docker portion among enabled services; it does not let each container independently claim the whole WSL CPU set. Ollama roles are modeled separately for normal text, DirectML text fallback, and Honcho embeddings. Runtime DirectML failure is allowed to alter active health/fallback state without changing durable resource topology.

## Principle

**Detect once, classify once, calculate once, validate once.** Downstream components consume canonical derived state instead of independently recreating hardware/backend/resource assumptions.

```text
Windows host snapshot + live WSL probes
                  |
                  v
      hardware-capabilities.json
                  |
                  v
       Backend Capability Engine
      /      |       |       \\
 DirectML   CUDA    ROCm    Vulkan -- CPU/native-Windows fallback
                  |
                  v
       backend-capabilities.json
                  |
                  v
      Canonical Resource Policy
                  |
                  v
          runtime-policy.json
                  |
     +------------+-------------------------------+
     |            |             |                 |
 DirectML       Ollama        Hermes/Honcho    Compose/service limits
                  |
                  v
        Canonical validation/audit
                  |
                  v
       Repair planner / diagnostics
```

## Hermes gateway topology

The canonical steady state has one default host gateway with `gateway.multiplex_profiles: true`. Installer-managed named profiles without an explicit `gateway.standalone: true` opt-out are served by that process and appear in the default gateway's live `served_profiles` record. Explicit standalone profiles retain their exact `/run/hermes-service/gateway-<profile>` s6 slot. `.installer-gateway-multiplex-owned` records LatticeVale ownership only; repair/start/audit verify live PID, heartbeat freshness, served-profile membership, PID stability, and enabled Matrix adapter connectivity independently before treating the topology as healthy. A healthy connected gateway is preserved rather than restarted or remigrated merely because a lifecycle command was invoked again.

## Ownership

- `install-options.json`: durable user intent and component choices.
- `latticevale_arch.py`: canonical schemas, hardware/backend classification, stable fingerprints, resource-policy invariants, atomic JSON writes, backend-health state.
- `hardware-capabilities.py`: live hardware document generator.
- `backend-capabilities.py`: capability/selection document generator.
- `runtime-policy.py`: canonical resource-policy document write/verify CLI.
- `diagnostics.py`: read-only architecture summary.
- `state-audit.py`: independent invariant/state verification that consumes canonical documents rather than duplicating formulas.
- `repair-plan.py`: dependency-aware repair recommendation.

## Provenance

Generated architecture documents include schema, architecture version, generation time, source/hardware/policy fingerprints as appropriate. Atomic replacement is used for canonical JSON documents so interrupted generation does not expose a half-written active file.

## Compatibility

v14.6.5 inherits the v14.6.0 canonical architecture, retains the v14.6.1 repair hardening and v14.6.2 managed-upstream policy, and migrates recognized managed 14.x installations preservation-first. For older recognized stacks, cumulative migration precedes mutating Options 1, 2, 4, 5, and 6; Options 3 and 8 remain read-only, while Option 7 remains isolated cleanup. Durable historical option names remain understood for migration. Future schemas fail closed. User/application data, persistent identities, and explicit overrides remain preservation-first.

### Resource scheduler v14 over canonical schema v13

`latticevale_arch.py` and `runtime-policy.py` remain the only canonical
calculation/verification engine for the fixed WSL host reserve, managed-container
memory floors, and total CPU/RAM safety envelopes. `configure-stack.sh` emits
static Compose `cpus`/`mem_limit`, relative `cpu_shares`, and `mem_reservation`
values from canonical functions. `resource-burst-controller.py` optionally
rebudgets live managed-container quotas within those envelopes using a
fingerprint-bound transaction journal, Docker inspection, WSL PSI,
`MemAvailable`, and cgroup v2 counters. `linux/bootstrap.sh` installs the
unprivileged host-side timer; repair restores baseline limits before policy
reconciliation. The controller itself does not write shared app state or
restart containers. See `RESOURCE-POLICY.md`.
