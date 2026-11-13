# LatticeVale 14.6.7 Diagnostics (inherited 14.6.6 checks)

## 14.6.7 resource-rebind and Element/Adlice diagnostics (2026-11-13)

**Read-only WSL:** From the selected user account, `python3 ~/hermes-stack/resource-burst-controller.py --verify --stack ~/hermes-stack`. Inspect `journalctl -u latticevale-resource-burst.service --no-pager -n 50` and `docker compose config --format json` from `~/hermes-stack`. If the error mentions `replacement allocation exceeds canonical memory envelope`, compare the sum of *live* Docker `HostConfig.Memory` limits with `BUDGET_MIB` in `.latticevale-resource-state`, and compare each container's ID and limit against `data/latticevale/resource-burst-state.json`; inspect replacement ownership labels and cgroup `memory.current`. In the recorded regression 10,528 MiB live exceeded 10,512 MiB canonical by 16 MiB after Honcho DB returned to its 208-MiB canonical ceiling. `docker stats` differs from charged cgroup usage and does not establish safe reduction. Do not paste credentials, raw environment files or complete private snapshots into reports.

**Read-only Windows Element:** From the repository root, `powershell.exe -NoLogo -NoProfile -File .\tools\Audit-LatticeVale-Element-Adlice.ps1`. Review file paths, version, Authenticode status, SHA-256, and running Element executable locations. Separately collect the **exact** Adlice detection name, flagged path, and scanner version. The helper does not clear malware alerts or set antivirus exclusions. Do not label a detection false positive without verifying the specific flagged artifact.

**Confidence boundary:** A passing source manifest validates files, a passing `--verify` checks a current controller snapshot, healthy Docker containers check a different layer, and a complete Windows/WSL/Element integration pass is a further independent result. See [Testing](TESTING.md) and [Security](SECURITY.md).

> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.

> **v14.6.6 Tailscale correction (carried forward from the v14.6.5 corrective overlay):** Dashboard and Matrix remote HTTPS may validate over IPv4, IPv6, or both. Certificate validation and direct-IP/no-proxy testing remain enabled. Windows listener enumeration is advisory when an authenticated HTTPS path and the selected application checks succeed; successful Serve mappings are retained rather than removed after a listener-only false-negative.


> **v14.6.2 Hotfix:** fixes the original v14.6.2 Linux bootstrap staging typo that duplicated an `install -m 0644 ... \` command immediately before the `compatibility.conf` copy. The defect could stop Resume / repair or Update / repair with `install: target .../compatibility.conf: Not a directory`. The hotfix changes no schema, data layout, managed-update policy, database-major bounds, DirectML/PyTorch compatibility envelope, or explicit user overrides. Apply the hotfix and rerun the installer; no uninstall or data reset is required.


> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.


## v14.6.6 CPU bottleneck and controller activation diagnostics

A missing `latticevale-resource-burst.timer` with an existing
`RESOURCE_BURST_STRATEGY=bounded-v14` and an image-only Compose override may
indicate an installer built before the image-only override/timer integration
fix. Deploy the updated complete source via Option 1, then verify the timer.
The controller's read-only `--check-override` uses the same effective Compose
model admission rule as its runtime check. Failure with an override means
static fallback is deliberately retained.

A saturated Ollama cgroup with `cpu.max` equivalent to 0.55 CPU can produce
~90% CPU PSI and 100% throttled periods even when WSL has four logical CPUs
and a low load average. New CPU weights scale from current WSL CPU count and
service/backend selections. The controller redistributes quotas **within**
the unchanged aggregate envelope despite CPU PSI; a genuinely saturated host
retains its additional DirectML CPU reserve. Check `docker inspect` NanoCpus,
`cpu.stat` deltas, `cpu.pressure`, workload throughput, and timer journal for
actual activation. `docker stats` alone cannot establish the root cause.

## v14.6.6 demand-matched CPU/RAM diagnostic follow-up

An idle container **can** temporarily donate quota, but the controller may
only reduce its hard cap when a receiver can actually accept that capacity.
CPU throttling is checked from **new per-cgroup** `nr_throttled` and
`nr_periods` deltas, not from Ollama's `PROCESSOR=100% CPU` label (which
means CPU-only placement, not saturation). New throttling can accelerate CPU
rebalancing despite normal cooldown, while memory rebalancing respects cooldown.

For memory cap reductions, `memory.current` supplies the full cgroup charge,
including file cache omitted from Docker's user-facing stats calculation.
Missing cgroup readings prohibit cap reductions, not all CPU balancing. Reclaim
from over-baseline memory also respects the live charged-memory floor. Older
OOMKilled markers do not prove a new OOM. Negative, missing, or reset throttling
deltas must not be interpreted as fresh throttling evidence.

Use `systemctl status latticevale-resource-burst.timer --no-pager`,
`journalctl -u latticevale-resource-burst.service --no-pager -n 50`, and
`python3 ~/hermes-stack/resource-burst-controller.py --verify --stack ~/hermes-stack`.
An inactive timer or a rejected Compose override means the **static fallback**;
passing snapshot verification does not prove that any transfer or performance
improvement occurred. For configured `compose.override.yaml`, only an effective
Hermes image/pull-policy difference is permitted; other changes disable dynamic
borrowing. Compare actual `docker inspect` ceilings and pressure before/after
a real workload to judge improvements. Unsupported/missing cgroup v2 telemetry
must not be repaired by weakening identity/fingerprint checks.

## Windows Tailscale remote-access diagnostics

A Tailscale-enabled install/repair writes a focused log at `%LOCALAPPDATA%\LatticeVale\logs\remote-access-YYYYMMDD-HHMMSS.log` when possible. It records prerequisite, preference, DNS, Serve/listener, Matrix client-path, mapping adoption/replacement, cleanup, and final-state diagnostics. It does not claim that a particular remote device was tested during installation.

Installer-owned `.tailscale-info` also records `TAILSCALE_IPV4`, `WINDOWS_DNS_STATUS`, and `REMOTE_VALIDATION_STATUS`. These are diagnostic history only; a saved `REMOTE_VALIDATION_STATUS=PASS` is never reused to claim a new run passed.


## Policy-13 diagnostics

Canonical diagnostics expose `gpuAccelerationEnabled`, `directmlFallbackPolicy`, fallback-enabled/fail-closed state, and the conserved CPU envelope. Resource-policy state includes `CPU_SYSTEM_HEADROOM_MILLI`, `CPU_DIRECTML_RESERVE_MILLI`, `CPU_DOCKER_ENVELOPE_MILLI`, and `CPU_DOCKER_ALLOCATED_MILLI`; audit rejects mismatched or overcommitted values.

v14.6.2 retains the v14.6.0 layered diagnostic model so one failed GPU API is not reported as "no GPU" for every backend.

## Installer diagnostics

An existing managed installation exposes **Diagnostics / compatibility test** as a read-only installer option. Windows-side diagnostics report Windows/WSL/GPU prerequisite state without changing the stack.

Option 8 stages the **current bundle's** `state-audit.py`, canonical architecture library, `compatibility.conf`, and a freshly generated Windows hardware snapshot into a temporary WSL directory. This prevents a pre-14.6 installed stack from being mislabeled merely because its old on-disk copy does not yet contain the current validator. The temporary files are removed afterward and do not migrate or repair the stack.

GPU diagnostics report memory **source and confidence** separately from backend health. `DML_VRAM_CAPACITY_UNAVAILABLE` means the DirectML route reached bounded model admission without a trustworthy runtime/canonical capacity; it is not equivalent to `DML_DXG_MISSING` or a missing GPU driver. A report of zero **Linux-native Ollama** GPU adapters is likewise not evidence that DirectML is unavailable when `/dev/dxg` and the WSL DirectX bridge are healthy.

## WSL commands

From `~/hermes-stack`:

```bash
./manage.sh diagnose
./manage.sh diagnose-gpu
./manage.sh diagnose-backends
./manage.sh diagnose-policy
./directml-gateway.sh diagnose
```

The architecture diagnostics can run after their canonical files are staged even if final `.configured` state has not yet been reached, making them useful during repair.

## Canonical documents

- `hardware-capabilities.json`: Windows snapshot + live WSL device/runtime topology.
- `backend-capabilities.json`: structural candidate capabilities, selected adapter, configured policy backend, active runtime backend, and reason codes.
- `backend-health.json`: transient runtime proof/failure tied to hardware fingerprint and represented by a separate runtime-health fingerprint.
- `runtime-policy.json`: canonical validated resource policy.

Diagnostics are derived state and must not contain user secrets. Do not publish unrelated application logs, backups, API keys, Matrix secrets, prompts, or credentials when filing a bug.

## Confidence levels

LatticeVale distinguishes static/source checks, deterministic fixtures, WSL integration, Docker integration, GPU/backend integration, and complete live Windows installer qualification. A passing static/fixture suite is strong regression evidence but is not represented as proof that every physical GPU/driver combination has been exercised live.


### 14.6.5 Obsidian diagnostics

The Windows Obsidian check now verifies an executable through registered Windows application locations, uninstall records, common installations, and optional Winget inventory. Confirmed installations are preserved; inconclusive evidence remains UNKNOWN rather than being treated as absent. Resource-policy source-option identity now selects durable resource-relevant inputs rather than transient repair/backup/Windows integration controls; unchanged legacy full-options hashes with valid document integrity are accepted for compatibility. Pre-migration shared-gateway live readiness now receives up to twelve checks separated by two seconds, preserving already converging processes. Windows storage display normalizes a drive's trailing colon. Added deterministic preservation fixtures; the live Windows/WSL end-to-end path still requires verification on its target host.

## 14.6.5 Windows state and OOM evidence

At the final Windows follow-up, `WINDOWS_STATE_WRITTEN` is the internal acknowledgement of an atomically saved and reread `.installer-state.json` Windows snapshot. A reported `STATE_WRITE_ERROR` means this acknowledgement failed and the diagnostic now includes the exit status and bounded error type/message; live state remains authoritative. A reported `EVENT_LOG_WARNING` means the snapshot was already persisted, but appending `logs/installer-events.jsonl` was unsuccessful. The two outcomes must not be conflated.

For QMD indexer OOM findings, compare `docker inspect` live `State.OOMKilled`, `State.StartedAt`, `HostConfig.Memory` and the current cgroup/memory usage against `./manage.sh audit`. The OOM flag establishes only that an event was recorded within the running container's current lifecycle; it does not provide event recency. An unchanged adaptive policy fingerprint is not evidence that such memory pressure was fixed.

### 14.6.5 QMD embedding CPU out-of-memory

A QMD indexer that reports `Indexed: ... unchanged` followed by `Run 'qmd embed' ... need vectors`, `Model: embeddinggemma-300M-Q8_0.gguf`, and `Killed` has **not** finished semantic embedding. An `OOMKilled=true` Docker flag together with repeatable killed embedding attempts is evidence of cgroup memory exhaustion. The 14.6.5 QMD resource correction raises both managed QMD-role minima; run normal Resume / repair to generate and apply a new Compose memory limit. Confirm the effective value with `docker inspect -f '{{.HostConfig.Memory}}' hermes-qmd-indexer` inside the selected WSL distro and check `docker logs --tail 100 hermes-qmd-indexer` for a later successful embed. Docker OOM markers without timestamps do not establish whether an event occurred before or after reconciliation. A user-owned Compose override can supersede installer allocations. Do not remove indexes, models, vault notes or authentication data just to recover from this memory ceiling.

### Bounded resource-burst diagnostics

A live Docker limit differing from Compose is valid only when
`resource-burst-controller.py --verify --stack ~/hermes-stack` confirms the
policy fingerprint, exact service ownership, container IDs, and transaction
snapshot. Otherwise the normal static policy mismatch remains reportable.
The timer and service journal distinguish static fallback, sustained demand,
contention-aware holds, and a safely applied rebalance. Read-only audits
verify the snapshot without mutating it. See `RESOURCE-POLICY.md`.

### 14.6.8 recorded floating image digest audit

The normal `state-audit.py` text output includes a `Floating image tags (recorded digests)` line; the existing JSON output contract is unchanged. These are **locally recorded** immutable registry digest references from `data/latticevale/managed-upstreams.json` for managed `:latest` image tags. Missing or malformed records print `unavailable` or are omitted; no remote registry request is made. This is provenance information, not proof of trust or a malware verdict.
