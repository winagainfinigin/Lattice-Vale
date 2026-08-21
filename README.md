# LatticeVale v14.4.6

> **Main Release — v14.4.6**
> Current recommended release and cumulative upgrade target from the public **v14.4.2 Main Release**.

LatticeVale is a source-visible **Windows + WSL2 installer, integration layer, and lifecycle manager for a self-hosted Hermes Agent stack**.

It installs into an **existing supported Ubuntu WSL2 distribution**, provisions Docker and Hermes, and can integrate Matrix, multi-profile Kanban orchestration, memory/Honcho, SearXNG, QMD indexing, Ollama/local AI, Obsidian, Windows lifecycle shortcuts, and Tailscale remote access.

LatticeVale is intentionally **recovery-aware and ownership-conscious**: it manages the Hermes stack without treating the user's entire WSL installation, Docker environment, Windows applications, Tailscale configuration, or personal data as disposable.

---

## What it manages

A typical installation includes:

```text
Windows 11
├─ LatticeVale installer/lifecycle tooling
├─ Start / Shutdown shortcuts
├─ optional Tailscale integration
├─ optional Obsidian integration
└─ WSL2 Ubuntu
   └─ ~/hermes-stack
      ├─ Docker Engine / Compose
      ├─ Hermes Agent
      │  ├─ API + Dashboard
      │  ├─ default + optional additional profiles
      │  └─ Kanban orchestration
      ├─ Matrix / Synapse + PostgreSQL
      ├─ SearXNG + Valkey
      ├─ QMD + indexer
      ├─ Honcho + PostgreSQL/pgvector + Redis
      └─ optional managed Ollama
```

Depending on selected options, LatticeVale provides:

* Hermes installation, configuration, gateways, providers/models, skills and memory policy
* multi-profile Hermes with independent gateways and Matrix identities
* Kanban triage, decomposition, dispatch, review, dependencies, and concurrency controls
* Matrix/Synapse provisioning and cross-signing persistence
* Honcho local contextual-memory infrastructure
* SearXNG search
* QMD indexing, including optional Windows Obsidian vault access
* managed or supported Windows-native Ollama integration
* adaptive container/RAM policy
* Windows/Tailscale relays and remote exposure
* coordinated Start / Shutdown behavior
* verification, audit, repair, update, backup, and controlled uninstall

Persistent Hermes profiles, sessions, memory, Matrix state, Honcho data, Ollama models, QMD data, credentials, backups, Obsidian data, and explicit Compose overrides are preserved during normal repair/update operations.

---

## Lifecycle and repair model

LatticeVale is not just a one-time installer.

It supports:

* fresh installation
* configuration/reconfiguration
* startup and shutdown
* status/health verification
* state-aware audit
* Resume / repair
* release migrations
* controlled component refresh
* Windows integration repair
* backup/recovery workflows
* controlled uninstallation

It uses a live-state-first recovery model:

1. identify the failing component;
2. inspect live state and dependencies;
3. repair the smallest necessary layer;
4. reconcile affected configuration/services;
5. verify the resulting state.

Completed checkpoints are not blindly trusted if live verification shows drift or failure.

### Option 1 — Resume / repair

The normal upgrade/repair path.

It reuses existing choices, preserves persistent state, repairs stale or incomplete managed stages, regenerates stale runtime policy, performs required release migrations, and recreates/reconciles affected containers only when necessary.

It is intentionally **local-first** when the existing managed runtime is already current.

### Option 6 — Update / repair installer-managed software

Forces convergence of installer-managed:

* prerequisite packages
* Docker packages
* managed images/builds
* audited source dependencies
* installer-owned runtime layers

It then runs the normal repair/reconciliation flow while preserving persistent user/application data.

---

## Managed update policy

LatticeVale separates:

```text
LatticeVale version changed
```

from:

```text
managed runtime payload requires refresh
```

Option 1 refreshes managed packages/images/sources when:

* the periodic refresh window is due;
* `MANAGED_REPAIR_REFRESH_REVISION` changes;
* no valid refresh marker exists;
* a managed component genuinely requires reconciliation;
* a migration requires it; or
* Option 6 explicitly forces it.

A documentation, audit, or installer-only update therefore does not automatically rebuild a healthy stack.

---

## Adaptive RAM/resource policy

Current adaptive resource policy **v3** reduces unnecessary WSL/Docker memory pressure while preserving operational headroom.

It can apply:

* adaptive per-container memory ceilings
* WSL-aware memory budgeting
* reduced glibc allocator arenas
* Synapse cache tuning
* reduced PostgreSQL fixed `shared_buffers`
* controlled Ollama model residency
* `max-loaded-models=1`
* `parallel=1`
* short Ollama keep-alive

User `compose.override.yaml` remains authoritative and is applied after the generated resource overlay.

---

# Release history

## v14.4.1 — Patch Release

**Repository/release layout cleanup**

* moved public PowerShell launchers under `installer/`
* moved the exact source manifest under `installer/`
* consolidated documentation under `docs/`
* retained GitHub/Git metadata and `LICENSE` at repository root
* updated launcher resolution, CI, tests, and documentation paths
* no intended runtime behavior change

---

# v14.4.2 — MAIN RELEASE

**Public baseline**

The main public baseline for the later cumulative v14.4.x work.

* finalized the reorganized release layout
* aligned documentation, regression expectations, version metadata, and source manifest
* retained the validated runtime behavior
* serves as the supported direct cumulative source for v14.4.6

**Direct upgrade supported: `14.4.2 → 14.4.6`**

---

## v14.4.3 — Patch Release

**RAM efficiency + safer uninstall**

Introduced adaptive resource policy v3:

* adaptive container ceilings
* allocator tuning
* Synapse cache tuning
* PostgreSQL shared-buffer tuning
* improved Ollama idle/model residency behavior

Also hardened uninstall behavior to preserve modified/unowned Windows resources, shared applications, Docker state, and configuration where ownership cannot safely be established.

---

## v14.4.4 — Patch Release

**Repair-time metadata race hardening**

Fixed repair failures caused by transient SQLite files such as:

```text
kanban.db-shm
kanban.db-wal
```

disappearing during ownership/permission traversal.

Files that genuinely vanish are tolerated; real filesystem, permission, mount, or ownership failures remain fatal.

---

## v14.4.5 — Patch Release

**Explicit runtime-policy convergence**

Fixed stale repair checkpoints preventing new adaptive RAM policy from becoming live.

When runtime policy changes, LatticeVale now:

* regenerates the policy;
* invalidates/reopens affected repair state;
* forces Compose reconciliation;
* recreates affected containers where required;
* prevents repair from reporting success while the managed runtime policy remains stale.

---

# v14.4.6 — MAIN RELEASE

**Current cumulative release**

v14.4.6 includes all v14.4.3–v14.4.5 fixes and adds two important corrections.

### Correct WSL CPU fingerprinting

The resource generator uses the CPU count actually available to WSL, but the old audit could use `os.cpu_count()` and see the Windows host's logical CPU count instead.

Example:

```text
Host CPUs:            8
WSL CPUs:             4
nproc:                4
saved policy CPUS:    4
old os.cpu_count():   8
```

This could falsely mark a correct resource policy as stale.

v14.4.6 now determines available CPUs using:

1. process CPU affinity;
2. `nproc`;
3. `os.cpu_count()` only as fallback.

### Refined repair-update triggering

A bundle-version change alone no longer forces package/image/source refresh.

This means:

* **14.4.5 → 14.4.6:** Option 1 applies the audit fix without rebuilding healthy QMD/Honcho images solely because the version changed.
* **14.4.2 → 14.4.6:** Option 1 still performs the required cumulative migration because managed refresh revision changes **1 → 2** and resource policy changes **v2 → v3**.

Intermediate v14.4.3–v14.4.5 installations are **not required**.

```text
14.4.1  layout patch
   ↓
14.4.2  MAIN RELEASE / public baseline
   ↓
14.4.3  RAM + uninstall patch
   ↓
14.4.4  repair-race patch
   ↓
14.4.5  runtime-policy repair patch
   ↓
14.4.6  MAIN RELEASE / current cumulative release
```

---

# Ownership and safety boundaries

Normal LatticeVale operations are designed to avoid destructive assumptions.

It does not treat these as automatically disposable:

* the WSL distribution itself
* unrelated Docker containers/images/volumes/networks
* global WSL networking configuration
* Windows-native Ollama
* Windows Tailscale
* user-modified Windows shortcuts/tasks
* Obsidian vault contents
* unrelated user documents

Where ownership cannot be safely proven, repair/uninstall behavior favors preservation.

---

# Included documentation

The repository includes detailed documentation for users and maintainers; this README is intentionally a condensed project overview.

### Core documentation

* [`docs/README.md`](docs/README.md) — documentation index and project overview
* [`docs/Instructions.txt`](docs/Instructions.txt) — installation, upgrade, repair, and operating procedures
* [`docs/FEATURES.md`](docs/FEATURES.md) — supported components, options, integrations, and capabilities
* [`docs/Installer Description.txt`](docs/Installer%20Description.txt) — installer architecture, ownership boundaries, stages, and recovery behavior
* [`docs/SECURITY.md`](docs/SECURITY.md) — trust boundaries, secrets, networking, exposure, Docker/Windows ownership, and security expectations
* [`docs/SUPPORT.md`](docs/SUPPORT.md) — diagnostics, repair/recovery strategy, health states, and troubleshooting
* [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — chronological release history
* [`docs/RELEASE.md`](docs/RELEASE.md) — maintainer release procedure, validation, packaging, manifests, and consistency requirements

### Version-specific technical notes

* [`docs/RESOURCE-FINGERPRINT-AUDIT-PATCH-NOTES.md`](docs/RESOURCE-FINGERPRINT-AUDIT-PATCH-NOTES.md) — v14.4.6 CPU/resource audit and update-trigger changes
* [`docs/REPAIR-RUNTIME-POLICY-UPDATE-PATCH-NOTES.md`](docs/REPAIR-RUNTIME-POLICY-UPDATE-PATCH-NOTES.md) — v14.4.5 runtime-policy/repair convergence
* [`docs/REPAIR-METADATA-RACE-PATCH-NOTES.md`](docs/REPAIR-METADATA-RACE-PATCH-NOTES.md) — v14.4.4 SQLite/metadata race fix

The repository also includes regression tests and validation tooling covering release layout, installation/repair semantics, resource policy, update gating, CPU fingerprinting, SQLite races, uninstall preservation, source-manifest integrity, portability, and documentation/version consistency.

For implementation details beyond this overview, **use the included documentation and source as the authoritative reference.**

---

# Repository layout

```text
/
├─ installer/            public install/uninstall/verification entry points
├─ docs/                 user/operator/maintainer documentation
├─ LatticeVale-Core/     runtime and stack implementation
├─ tools/                supporting release/maintenance tooling
├─ README.md
└─ LICENSE
```

---

# Verify

From an Administrator PowerShell window at the extracted release root:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\verify-release.ps1
```

# Install / upgrade / repair

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1
```

For most existing installations use:

```text
Option 1 — Resume / repair installation
```

To deliberately force the managed software layer to refresh:

```text
Option 6 — Update / repair installer-managed software
```

# Uninstall

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\uninstall.ps1
```

The uninstaller targets LatticeVale-managed state while preserving unrelated/user-owned resources wherever ownership cannot safely be established.
