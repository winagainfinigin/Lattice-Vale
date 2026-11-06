# LatticeVale 14.6.6 Resource Scheduler v14 (Canonical Schema v13)

> **v14.6.6 demand-matched resource hotfix:** The original v14 controller
> transferred quotas from every idle donor before checking what busy receivers
> could accept. The follow-up allocates only confirmed demand, protects
> priority-dependent idle-service CPU margins, reads cgroup `memory.current`
> before any hard-memory-cap donation, and permits an effective *Hermes-image-only*
> Compose override when all other resolved settings match the canonical stack.
> It also allows fresh, measured CPU quota throttling to bypass the normal
> cooldown for CPU-only transfers. Canonical schema 13, installed version
> 14.6.6, user-selected WSL limits, and existing service minima do not change.
> This is a source-level correction; throughput or responsiveness gains require
> real host/WSL/Docker measurements before they can be claimed.

> **v14.6.2 Hotfix:** fixes the original v14.6.2 Linux bootstrap staging typo that duplicated an `install -m 0644 ... \` command immediately before the `compatibility.conf` copy. The defect could stop Resume / repair or Update / repair with `install: target .../compatibility.conf: Not a directory`. The hotfix changes no schema, data layout, managed-update policy, database-major bounds, DirectML/PyTorch compatibility envelope, or explicit user overrides. Apply the hotfix and rerun the installer; no uninstall or data reset is required.


> **v14.6.6 current-release update policy:** installer-managed application software now uses latest-supported stable upstream resolution when a managed refresh is due; Option 6 forces that refresh after the per-run pre-install backup choice. Mutating existing-stack modes (Options 1, 2, 4, 5, and 6) offer the backup skip choice with live progress. A per-run Ubuntu APT refresh choice appears when refresh is planned or its need cannot be determined; targeted package installs still run when skipped. Explicit overrides remain preserved, stateful database/cache majors stay compatibility-bounded, and PyTorch/DirectML remains a qualified ABI envelope. Exact resolved artifacts are recorded in `data/latticevale/managed-upstreams.json`.



## v14.6.6 portable CPU-priority and burst activation correction (same version)

The v14.6.6 follow-up fixes two independent causes of high inference latency:

1. The canonical **static CPU planner** now gives proportionally higher shares of
   the existing Docker envelope to Hermes's interactive agent and CPU/Vulkan
   Ollama inference, while retaining at least 50 milli-CPU for every enabled
   service. GPU-accelerated Ollama receives a smaller CPU share. The weights
   are recalculated from **WSL-visible logical CPUs, enabled services,
   acceleration backend, gateway/profile count, and Kanban concurrency** on
   install/repair; they are not hardware-specific fixed CPU counts. On one
   example fully enabled **4-logical-CPU CPU-inference** stack the 3.6-core
   Docker envelope divides into about **1.35 CPUs for Ollama**, **0.85 for
   Hermes**, and **1.40 across the remaining services**; 0.40 CPU remains
   outside Docker for host/system scheduling. These are **Linux CPU-time
   ceilings**, not permanently pinned cores or physical reservations.
2. The **bootstrap timer eligibility** now uses the same full resolved-Compose
   comparison as the runtime controller: a user-selected Hermes **image-only**
   override remains eligible for dynamic borrowing, while any additional
   resource, environment, or topology override retains static fallback.
3. The controller's in-envelope CPU transfers proceed during **CPU PSI caused
   by cgroup quota throttling**, including high PSI with an otherwise lightly
   loaded WSL host. CPU PSI corroborated by heavy runqueue load still
   prevents *additional borrowing from an idle DirectML host reserve*;
   canonical aggregate Docker and host safety envelopes remain enforced.
   The timer now checks about every **25 seconds** after an initial 1-minute
   boot delay, with a **45-second** post-change cooldown. Sustained measured
   throttling can trigger a CPU-only lease during cooldown. The pressure
   and fresh-OOM safeguards for memory transfers remain unchanged.

The enhanced policy supports arbitrary validated WSL CPU/RAM assignments,
optional services, CPU/Vulkan/GPU backends, and DirectML. Tiny configurations
that cannot fit active service minimums are rejected rather than overcommitted.
Source and simulated Docker tests establish invariants only; measure real
latency/throughput on the deployed host before claiming a performance gain.

## v14.6.6 bounded resource-burst hotfix (scheduler policy v14)

This hotfix preserves the canonical **runtime-policy schema 13** and the fixed
`POLICY_VERSION=13` fallback contract. `RESOURCE_BURST_STRATEGY=bounded-v14`
enables a *separate runtime scheduling layer* after the canonical planner has
validated WSL-visible hardware, selected services, hard memory floors, CPU
headroom, and DirectML/GPU admission. An older v13 policy is regenerated on
Resume / repair. Version remains **14.6.6**.

The canonical hard budgets still sum to no more than the selected WSL CPU/RAM
envelopes. Docker Compose additionally receives `cpu_shares` (relative
priority) and `mem_reservation` (soft pressure target), while `cpus` and
`mem_limit` remain the safe static baseline. The controller can rebalance
**hard quota within those conserved totals** using `docker update` without
restarting the applications. It does not set WSL's global CPU/RAM limits or
write `.wslconfig`, alter GPU VRAM ceilings, or modify user-owned Compose files.

The 12 container roles have separate priority weights and their existing
canonical memory minima. The Hermes/Matrix/Honcho interactive roles receive
higher CPU scheduling priorities than background QMD indexing/derivation.
Each eligible recipient can borrow at most 400 milli-CPU and 128 MiB in one
rebalancing cycle, subject to aggregate limits; per-service CPU limits are
capped at the smaller of 75% of WSL logical CPU capacity and a bounded
multiple of the baseline. Memory recipients retain at most a 1.75× baseline ceiling. CPU donor
headroom depends on workload priority: background services keep at least 65%
of baseline CPU quota, standard services 80%, and high-priority interactive
services 90%, rounded up to 50 milli-CPU scheduling units. Memory donors keep
the greater of their canonical service/model minimum, 85% of baseline for
background roles or 90% for other roles, and 120% of the *charged cgroup*
`memory.current` value plus 64 MiB. The memory floor and actual recipient
capacity must permit the full transfer; donations no longer occur speculatively.
Previously idle services regain baseline CPU quota when they reawaken,
including during normal cooldown. Borrowed RAM is reclaimed only when cgroup
memory usage safely permits it. No pool grows merely because a service exists.

The optional host-side controller at `~/hermes-stack/resource-burst-controller.py`
uses local Docker inspection/statistics, cgroup v2 CPU-throttling and OOM-event
counters where accessible, cgroup `memory.current` (including charged file cache)
for *reducing* memory limits, and Linux CPU/memory/I/O pressure plus `MemAvailable`.
Normally it requires two demand samples, three idle samples, and a 45-second
post-change cooldown. A newly measured quota-throttling interval can override
the cooldown and two-sample requirement for CPU redistribution only; unrelated
memory-limit changes remain on cooldown. Missing cgroup memory-current telemetry
prevents reducing memory limits but does not prevent ordinary CPU borrowing. It holds or contracts allocations during
high memory pressure (10-second PSI average at least 2%), high I/O pressure
(at least 12%), newly observed cgroup OOMs, missing essential pressure
measurements, or low available RAM. CPU PSI alone is not a reason to stop
quota redistribution **inside** the Docker envelope; true host CPU load
corroborates CPU PSI only for protecting additional DirectML reserve lending. A pre-existing
`OOMKilled` marker alone is not treated as a newly timed kernel event.

When DirectML is selected **and its host-side gateway process is absent or has remained CPU-idle for two samples**, at
most one third of its normally reserved CPU slice (and at most 10% of WSL
CPUs) may be lent transiently to Docker; the protected system scheduler slice
remains intact. Detecting renewed DirectML CPU activity restores the full DirectML CPU reserve
on the next sample, even during cooldown. DirectML host RAM is reserved at
28% of WSL-visible memory with the existing 2 GiB floor/8 GiB cap.
Managed-Ollama host reserve is 10%, otherwise 13%, with the original
independent min/max host safeguards. The smaller ordinary reserve increases
container availability only when selected service minima still fit safely.

The host timer `latticevale-resource-burst.timer` runs as the selected normal
Ubuntu user, reads only the **local** rootful Docker Engine, and never exposes
Docker's control socket to an application container. It uses a
fingerprint- and container-ID-bound transaction snapshot at
`data/latticevale/resource-burst-state.json`; partial changes are recovered
or stopped for review. Every repair stops the timer, restores the static
Compose baseline when possible (including when a new user-owned Compose
override is detected), and then revalidates canonical state.
Both the installer verifier and read-only audit distinguish a verified dynamic
snapshot from genuine unexplained Docker drift.

**Fail-safe:** Missing systemd support before activation leaves static Compose
ceilings in place. Missing Docker access, an invalid policy identity, changed
container ownership, incomplete essential telemetry, or a user-owned
resource/behavior-changing `compose.override.yaml` suppresses borrowing. The
only admitted override is one whose full resolved Compose model differs from
the canonical model solely in Hermes's `image` and optional `pull_policy`.
The installer also checks that eligibility as the selected normal WSL user
before enabling the timer; the controller rechecks Docker Compose's complete
merge/interpolation output on every activation. No override file is modified. Previously applied
limits remain inside the verified aggregate envelope until an owner-run repair
or an explicit restoration returns them to the canonical Compose baseline.
User-supplied service/resource overrides retain final precedence and suppress
automatic rebalancing for that stack. Unverified or unsupported Compose model
resolution also leaves the verified static fallback active. If the controller cannot safely execute
one Docker change, it attempts the inverse transaction and keeps a recovery
journal for the next activation. The Docker engine and QMD/model floors remain
otherwise unchanged.

To return an active installation to the canonical static quotas during a
manual diagnostic, pause the timer and restore the verified baseline as the
normal Linux owner: `sudo systemctl stop latticevale-resource-burst.timer
latticevale-resource-burst.service`, then
`python3 ~/hermes-stack/resource-burst-controller.py --restore --stack
~/hermes-stack`. The next normal installer repair reconciles the policy and
reactivates the timer when eligible.

**Operational verification:** After applying the source hotfix through
LatticeVale's Resume / repair installer flow, inspect:

```
systemctl status latticevale-resource-burst.timer --no-pager
journalctl -u latticevale-resource-burst.service --no-pager -n 50
python3 ~/hermes-stack/resource-burst-controller.py --verify --stack ~/hermes-stack
```

A missing/inactive timer before first activation means *static fallback*,
not a failed stack. Once dynamic limits have been applied, the last verified
limits remain bounded until a verified restore or repair completes. The
runtime controller requires a live Windows/WSL/Docker validation on the
actual host before a throughput improvement can be claimed. Source/fixture
checks prove calculation and transaction invariants, not Windows performance.


## Applying this changed-files-only source overlay

Apply this ZIP **directly over the extracted complete LatticeVale v14.6.6
repository tree**, allowing the matching files to be overwritten. The full
replacement files include the prior demand-matched changes, so there is **no
requirement to revert any previous hotfix first**. Keep the `Lattice-Vale/`
directory structure and all unchanged files. The package is designed for the
current 14.6.6 source and the previous 14.6.6 source plus its hotfix overlay.
The accompanying `installer/SOURCE-SHA256SUMS.txt` contains updated hashes
for the modified source and documentation. Run `installer/verify-release.ps1`
against the complete, merged tree before selecting the normal **Option 1 —
Resume / repair** installer flow. Take the offered safety backup before changes
that require rollback. Do not substitute Option 6: it forces broader managed
software refresh and is unnecessary for a source-policy reconciliation.

The ZIP is **not** a complete standalone release and must not be extracted
straight into a running WSL stack. After installation, verify timer activity,
controller journal, live Docker resource ceilings, and at least one workload
where a receiver actually borrows and relinquishes unused quota. Container
health and source tests alone do not establish measured performance gains.

## Policy v13 conserved CPU envelope

Policy v13 treats WSL-visible CPU as one conserved budget instead of giving every container an independent fraction of all CPUs. Approximately 10% is reserved for WSL/system scheduling. When DirectML text inference is selected, approximately 25% is reserved for its host-side worker and the remaining approximately 65% is the aggregate Docker envelope. Without DirectML, the Docker envelope is approximately 90%. Only enabled services receive quotas, and their summed ceilings must not exceed the Docker envelope. Memory remains independently derived from live WSL RAM, selected services, model requirements, and backend/GPU evidence; impossible combinations fail closed rather than overcommit critical floors.

## Single source of calculation

Resource policy v13 generation and verification consume the same canonical architecture functions. `configure-stack.sh` is a compatibility/orchestration layer; it must not independently reimplement host-memory budget, CPU-quota, service-memory, context, GPU-coordination, or runtime-tuning formulas.

The persisted policy includes at least:

- WSL-visible CPU and RAM;
- total host reserve;
- DirectML WSL-host reserve when selected;
- final container budget;
- managed Ollama selection/acceleration;
- Linux GPU topology and VRAM data where available;
- DirectML selected adapter plus bounded admission capacity/source/confidence;
- per-service/container ceilings;
- model/context/concurrency inputs;
- hardware and policy fingerprints.

`runtime-policy.json` wraps the validated persisted state with architecture/schema/provenance fingerprints.

## DirectML host reserve

DirectML runs on the WSL host, outside the Docker service memory budget. Its host reserve therefore remains valid even when Linux-native GPU enumeration is zero. The canonical calculation treats it independently from managed Ollama acceleration.

For the v14.6.6 bounded-burst hotfix, ordinary host headroom scales from live WSL RAM (10% when managed Ollama is selected, otherwise 13%) with bounded safety floors/caps. When DirectML is selected, the total host reserve is raised to the larger of that ordinary reserve and a DirectML reserve derived from about 28% of live WSL RAM. The DirectML path uses a 2 GiB floor when the allocation can afford it, clamps against very small VMs so at least a minimal container-planning remainder exists, and caps the DirectML reserve at 8 GiB on large systems. The calculation uses integer-MiB scaling rather than coarse percentage rounding or RAM-size tiers, so increasing WSL RAM cannot make the calculated container budget go backward at a boundary.

These values are ceilings/budget partitions, not a promise that every selected model can run on every machine. Service minima, model VRAM admission, current host `MemAvailable`, and the live DirectML model self-test are separate gates. If the selected topology cannot fit safely, LatticeVale refuses the plan or leaves DirectML unavailable according to the configured fallback policy rather than overcommitting RAM.

## CPU is supported

CPU mode is not an error sentinel. On systems without a usable GPU backend, the policy engine derives conservative CPU-safe context/concurrency/container limits while preserving the core stack where installer prerequisites are otherwise satisfied.

## Canonical CPU/service/tuning ownership

CPU quotas, service memory water-filling, context recommendations, GPU coordination, allocator tuning, and PostgreSQL/Synapse tuning are generated by the same canonical architecture library used by `runtime-policy.py`. `configure-stack.sh` only orchestrates those calls and emits their validated results.

## Matrix profile workload compatibility field

The persisted state key `MATRIX_PROFILE_GATEWAYS` is retained for policy-v13 compatibility, but under the current shared-multiplexer architecture it should be read as a count of Matrix-enabled secondary profile workload, not a claim that each profile owns an independent gateway process. Shared profiles still add adapter/session work inside Hermes and therefore remain a legitimate bounded pressure signal; explicit standalone profiles preserve their own runtime topology independently. Renaming the persisted key would create unnecessary policy-fingerprint churn, so schema 13 keeps the historical key while current documentation uses the corrected semantics.

## Verification invariants

The verifier recomputes and checks `RESERVE_MIB`, `DIRECTML_HOST_RESERVE_MIB`, and `BUDGET_MIB` from the same canonical function. It also verifies the policy fingerprint and generated runtime-policy document. Writer/verifier drift is release-blocking.

## User override

`compose.override.yaml` remains user-owned and is applied after installer-owned generated Compose policy. A resource-affecting or otherwise behavior-changing override stays authoritative and disables the burst controller. Only a *verified effective Hermes-image-only* override may retain adaptive borrowing: the controller compares complete resolved Compose models, removing solely `services.hermes.image` and `services.hermes.pull_policy` before an exact equality check. A Compose error or any additional difference falls back to static policy. The controller never modifies an override or assumes arbitrary YAML semantics are safe.

## Runtime health versus resource topology

Backend runtime-health records are diagnostic/transient evidence and carry a separate runtime-health fingerprint. A DirectML request falling back to Ollama does not change the resource-policy fingerprint when the configured DirectML host reserve, selected adapter/admission envelope, and fallback resource envelope are unchanged. Material hardware topology, durable user intent, or resource-relevant Ollama acceleration changes still invalidate and regenerate dependent policy. DirectML capacity is derived hardware state; a legacy saved `directmlVramMiB` is migration fallback only, not authoritative durable intent.


### 14.6.5 canonical fingerprint

The Windows Obsidian check now verifies an executable through registered Windows application locations, uninstall records, common installations, and optional Winget inventory. Confirmed installations are preserved; inconclusive evidence remains UNKNOWN rather than being treated as absent. Resource-policy source-option identity now selects durable resource-relevant inputs rather than transient repair/backup/Windows integration controls; unchanged legacy full-options hashes with valid document integrity are accepted for compatibility. Pre-migration shared-gateway live readiness now receives up to twelve checks separated by two seconds, preserving already converging processes. Windows storage display normalizes a drive's trailing colon. Added deterministic preservation fixtures; the live Windows/WSL end-to-end path still requires verification on its target host.

## Runtime OOM observations versus policy configuration (14.6.5)

The policy fingerprint establishes the resource configuration, not the absence of kernel OOM events. Docker's `State.OOMKilled` on a running container is an event flag scoped to that container lifecycle; the flag itself has no reliable event timestamp. `Resume / repair` verifies existing Compose and live memory/CPU limits and keeps valid allocations intact, but emits a separate warning if a selected running container retains the OOM marker. This is **not** proof of ongoing memory pressure or successful remediation. Reconcile actual memory metrics and more recent container evidence before electing to change resource sizes; unrelated transaction-only installer choices do not invalidate this policy.

## 14.6.5 QMD embedding memory correction

The canonical service planner now reserves a **1024 MiB minimum** for each selected QMD role: the MCP/search server and the separate background indexer/embedding worker. The indexer formerly had a 192 MiB floor, allowing allocations such as 304 MiB that repeatedly killed the CPU `embeddinggemma-300M-Q8_0.gguf` embedding process. The GGUF artifact itself is approximately 300 MB, exclusive of the loader, inference context, runtime, and indexing memory. QMD memory is charged to the existing conserved container budget; the planner refuses a topology it cannot safely fit, rather than reducing critical service floors or allocating imaginary RAM. No RAM threshold tied to a particular PC, silent backend switch, GPU/WSL host mutation, or QMD data reset was added. User-owned `compose.override.yaml` retains final precedence.

The unchanged canonical runtime-policy verifier recalculates per-service memory from the updated planner, so a same-version 14.6.5 Resume / repair detects an older undersized policy and marks infrastructure/reconcile pending for Docker to apply the new limits. Merely copying code does not change already-running container cgroups; Resume / repair is required to reconcile their memory ceilings. A previous `OOMKilled` flag cannot alone date a new OOM; the next `qmd embed` log and observed cgroup memory limit determine whether the increased allocation suffices. The 1024 MiB minima are protective resource floors, not a guarantee for all larger/custom models or every QMD search/query workload.
