# LatticeVale v14.4.6

> **Main Release — v14.4.6**  
> Current recommended release and cumulative upgrade target from the public **v14.4.2 Main Release**.

LatticeVale is a source-visible **Windows + WSL2 installer, integration layer, and lifecycle manager for a self-hosted Hermes Agent stack**.

It installs into an **existing supported Ubuntu WSL2 distribution**, provisions Docker and Hermes, and can integrate Matrix, multi-profile Kanban orchestration, memory/Honcho, SearXNG, QMD indexing, Ollama/local AI, Obsidian, Windows lifecycle shortcuts, and Tailscale remote access.

LatticeVale is intentionally **recovery-aware and ownership-conscious**. It manages the Hermes stack without treating the user's entire WSL installation, Docker environment, Windows applications, Tailscale configuration, or personal data as disposable.

## What LatticeVale manages

A typical installation looks like this:

```text
Windows 11
├─ LatticeVale installer and lifecycle tooling
├─ Start / Shutdown shortcuts
├─ optional Tailscale integration
├─ optional Obsidian integration
└─ WSL2
   └─ supported Ubuntu distribution
      ├─ Docker Engine / Compose
      └─ ~/hermes-stack
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

Depending on the selected installation options, LatticeVale can provide:

- Hermes installation, configuration, gateways, providers/models, skills, and memory policy
- multi-profile Hermes with independent gateways and Matrix identities
- Kanban triage, decomposition, dispatch, review, dependencies, and concurrency controls
- Matrix/Synapse provisioning and cross-signing persistence
- Honcho local contextual-memory infrastructure
- SearXNG search
- QMD indexing, including optional Windows Obsidian vault access
- LatticeVale-managed or supported Windows-native Ollama integration
- adaptive Docker/WSL RAM policy
- Windows/Tailscale relays and remote exposure
- coordinated Start / Shutdown behavior
- verification, audit, repair, update, backup, and controlled uninstall

Persistent Hermes profiles, sessions, memory, Matrix state, Honcho data, Ollama models, QMD data, credentials, backups, Obsidian data, and explicit Compose overrides are preserved during normal repair and update operations.

## Lifecycle management

LatticeVale is not only an installer. It manages the ongoing lifecycle of the stack, including:

- fresh installation
- configuration and reconfiguration
- startup and shutdown
- status and health verification
- state-aware auditing
- Resume / repair
- release migrations
- controlled component refresh
- Windows integration repair
- backup and recovery workflows
- controlled uninstallation

Its repair model is deliberately conservative:

1. inspect live state;
2. identify the failing or stale component;
3. repair the smallest necessary layer;
4. reconcile affected configuration and services;
5. verify the resulting state.

Completed installer checkpoints are not blindly trusted when live verification shows that the managed state has drifted or failed.

### Resume / repair

**Option 1 — Resume / repair installation** is the normal upgrade and repair path.

It reuses existing selections, preserves persistent state, repairs incomplete or stale managed stages, applies required release migrations, regenerates stale runtime policy, and reconciles affected containers when necessary.

A new LatticeVale version alone does not automatically require a complete Docker image or source refresh.

### Forced managed update

**Option 6 — Update / repair installer-managed software** explicitly forces convergence of the installer-managed software layer, including applicable:

- prerequisite packages
- Docker packages
- managed images and builds
- audited source dependencies
- installer-owned runtime layers

Persistent application data and user configuration remain preserved.

## Adaptive RAM and resource policy

LatticeVale resource policy **v3** is designed to reduce unnecessary WSL/Docker memory pressure while retaining operational headroom.

Depending on the enabled services, it can apply:

- adaptive per-container memory ceilings
- WSL-aware memory budgeting
- reduced glibc allocator arenas
- Synapse cache tuning
- reduced PostgreSQL fixed `shared_buffers`
- controlled Ollama model residency
- bounded Ollama parallelism
- short Ollama model keep-alive behavior

Explicit user `compose.override.yaml` configuration remains authoritative and is applied after the generated LatticeVale resource policy.

## v14.4.6 highlights

### Correct WSL CPU resource fingerprinting

Previous resource auditing could use `os.cpu_count()` and observe the Windows host's logical CPU count rather than the processor count actually available to WSL.

For example:

```text
Windows host:      8 CPUs
WSL allocation:    4 CPUs
nproc:             4
saved policy:      4
old audit result:  8
```

This could falsely mark a valid adaptive resource policy as stale.

v14.4.6 aligns resource auditing with the WSL-visible CPU allocation by preferring:

1. process-visible CPU affinity;
2. `nproc`;
3. `os.cpu_count()` only as a fallback.

### Refined repair/update triggering

v14.4.6 separates:

```text
LatticeVale version changed
```

from:

```text
managed runtime payload requires refresh
```

A bundle-version change by itself no longer forces package, image, build, or source refresh.

Managed refresh is instead controlled by actual runtime state, the managed refresh policy/revision, scheduled refresh conditions, required migrations, or an explicit forced update.

This allows:

- **v14.4.5 → v14.4.6:** apply the audit fix without unnecessarily rebuilding healthy managed images solely because the version changed.
- **v14.4.2 → v14.4.6:** perform the required cumulative migration because the managed refresh revision and adaptive resource policy advance from the v14.4.2 baseline.

Intermediate v14.4.3–v14.4.5 installations are not required.

## Release history

| Version | Type | Primary change |
| --- | --- | --- |
| **v14.4.1** | Patch | Repository/release layout cleanup |
| **v14.4.2** | **Main Release** | Public baseline |
| **v14.4.3** | Patch | RAM efficiency and uninstaller hardening |
| **v14.4.4** | Patch | Repair-time SQLite/metadata race hardening |
| **v14.4.5** | Patch | Runtime-policy and repair convergence |
| **v14.4.6** | **Main Release** | Current cumulative release |

### v14.4.1

Repository and release-layout cleanup, including organization of installer, documentation, release metadata, tests, and supporting files. No intended runtime behavior change.

### v14.4.2 — Main Release

Established the primary public v14.4.x baseline and finalized release-layout, documentation, version, regression, and source-manifest consistency.

### v14.4.3

Introduced adaptive resource policy v3 and additional RAM-efficiency tuning, including allocator, Synapse, PostgreSQL, and Ollama improvements. Also hardened uninstall behavior to better preserve modified, shared, or user-owned resources.

### v14.4.4

Hardened repair against transient SQLite files such as:

```text
kanban.db-shm
kanban.db-wal
```

Files that genuinely disappear during live traversal are tolerated while real permission, mount, ownership, and filesystem failures remain errors.

### v14.4.5

Added explicit runtime-policy convergence so stale adaptive configuration cannot be skipped merely because an older installer checkpoint is marked complete.

When required, LatticeVale regenerates the policy, invalidates affected repair state, reconciles Compose, and recreates affected containers so new runtime settings actually become live.

### v14.4.6 — Main Release

Current cumulative release. Includes the v14.4.3–v14.4.5 fixes plus corrected WSL CPU resource fingerprinting and refined managed-update triggering.

```text
v14.4.1  release-layout patch
    ↓
v14.4.2  MAIN RELEASE / public baseline
    ↓
v14.4.3  RAM + uninstall patch
    ↓
v14.4.4  repair-race patch
    ↓
v14.4.5  runtime-policy repair patch
    ↓
v14.4.6  MAIN RELEASE / current release
```

## Ownership and safety boundaries

LatticeVale does not automatically treat the following as disposable:

- the WSL distribution itself
- unrelated Docker containers, images, volumes, or networks
- global WSL networking configuration
- Windows-native Ollama
- Windows Tailscale
- user-modified Windows shortcuts or tasks
- Obsidian vault contents
- unrelated user documents

Where ownership cannot be safely established, repair and uninstall behavior favors preservation rather than destructive guessing.

## Documentation

The repository includes detailed documentation beyond this README.

Key documentation includes:

- [`docs/README.md`](docs/README.md) — documentation index and project overview
- [`docs/Instructions.txt`](docs/Instructions.txt) — installation, upgrade, repair, and operating procedures
- [`docs/FEATURES.md`](docs/FEATURES.md) — supported components, options, integrations, and capabilities
- [`docs/Installer Description.txt`](docs/Installer%20Description.txt) — installer architecture, stages, ownership boundaries, and recovery behavior
- [`docs/SECURITY.md`](docs/SECURITY.md) — trust boundaries, networking, secrets, exposure, and ownership policy
- [`docs/SUPPORT.md`](docs/SUPPORT.md) — diagnostics, repair/recovery strategy, health states, and troubleshooting
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — detailed chronological development and release history
- [`docs/RELEASE.md`](docs/RELEASE.md) — release validation, packaging, manifests, and maintainer requirements

Version-specific technical documentation includes:

- [`docs/RESOURCE-FINGERPRINT-AUDIT-PATCH-NOTES.md`](docs/RESOURCE-FINGERPRINT-AUDIT-PATCH-NOTES.md) — v14.4.6
- [`docs/REPAIR-RUNTIME-POLICY-UPDATE-PATCH-NOTES.md`](docs/REPAIR-RUNTIME-POLICY-UPDATE-PATCH-NOTES.md) — v14.4.5
- [`docs/REPAIR-METADATA-RACE-PATCH-NOTES.md`](docs/REPAIR-METADATA-RACE-PATCH-NOTES.md) — v14.4.4

The included documentation contains substantially more installation, architecture, troubleshooting, compatibility, security, release-history, and implementation detail than this README.

**For exact behavior, use the documentation, shipped source, compatibility metadata, and regression tests as the authoritative reference.**

## Repository layout

```text
/
├─ .github/
├─ docs/
├─ installer/
├─ LatticeVale-Core/
├─ tools/
├─ .gitattributes
├─ .gitignore
├─ LICENSE
└─ README.md
```

## Getting started

Start with:

1. [`docs/README.md`](docs/README.md)
2. [`docs/Instructions.txt`](docs/Instructions.txt)
3. [`docs/FEATURES.md`](docs/FEATURES.md)

For an existing installation, the installer provides state-aware verification, Resume / repair, reconfiguration, advanced recovery, and managed-update options.

## License

See [`LICENSE`](LICENSE).
