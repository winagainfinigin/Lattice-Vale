# LatticeVale v14.4.82

> **Patch Release — v14.4.82**
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
- SearXNG search plus keyless public-page extraction for Hermes research
- QMD indexing, including optional Windows Obsidian vault access
- LatticeVale-managed or supported Windows-native Ollama integration
- adaptive Docker/WSL RAM policy
- Windows/Tailscale relays and remote exposure
- coordinated Start / Shutdown behavior
- verification, audit, repair, update, backup, and controlled uninstall

Persistent Hermes profiles, sessions, memory, Matrix state, Honcho data, Ollama models, QMD data, credentials, backups, Obsidian data, and explicit Compose overrides are preserved during normal repair and update operations.

## v14.4.82 WSL recovery return-value hotfix

v14.4.82 fixes a PowerShell return-channel bug in the v14.4.81 bounded WSL launch recovery. The recovery helper could successfully restore WSL after `wsl --shutdown`, but its diagnostic text and native exit code were both emitted through the function success stream. The installer therefore captured an array instead of the scalar exit code `0`, misreported the helper output as an exit code, skipped the post-recovery distro re-probe, and ended with `No eligible existing Ubuntu WSL2 distro was found.`

The hotfix keeps helper diagnostics visible with `Out-Host` while returning only the scalar native process exit code. A successful recovery now immediately re-runs the existing Ubuntu/architecture/storage/managed-stack eligibility checks in the same installer run. No WSL ownership boundary, networking policy, Hermes behavior, service, dependency, or storage threshold changes: fresh installs still require the normal 50 GiB free reserve, while confirmed installer-managed Resume / repair remains eligible at the existing 10 GiB free floor.

## v14.4.81 WSL launch-recovery hotfix

v14.4.81 fixes a preflight dead end seen when a correctly registered Ubuntu WSL2 distro cannot cold-launch and `wsl.exe` returns **`Wsl/Service/E_UNEXPECTED` / `Catastrophic failure`**. When the affected distro is the only path forward—or is explicitly selected with `-DistroName`—the installer can now run a bounded, preservation-first recovery and re-probe the same distro **in the same installer run**.

The recovery order is deliberately narrow: first use Microsoft's non-destructive `wsl --shutdown` restart path and retry the existing distro. The bounded shutdown/re-probe path does not require elevation; if unrelated running distros are detected—or WSL cannot reliably report the running-distro list—the installer asks before using the global shutdown. If the same `E_UNEXPECTED` persists and `%UserProfile%\.wslconfig` explicitly selects `networkingMode=mirrored`, LatticeVale can then offer an **explicit** compatibility fallback that backs up `.wslconfig`, changes only `networkingMode` to `nat` (the WSL default), restarts WSL, and tests the same registered distro again. The normal installer does not unregister/import/convert/move/recreate a distro, edit its VHDX, or automatically escalate into DISM/Windows-feature repair. If the bounded recovery is insufficient, the existing Administrator repair helper remains the explicit deeper-repair path.

This hotfix does **not** lower the existing storage prerequisites. After WSL recovers, LatticeVale re-runs the normal Ubuntu, architecture, storage, and managed-stack eligibility checks. An existing installer-managed stack can still qualify for Resume / repair with **at least 10 GiB free**, while a genuinely fresh install must still satisfy the normal **50 GiB free** fresh-install reserve on a host partition over 50 GiB total.

See [`docs/SUPPORT.md`](docs/SUPPORT.md) for recovery guidance and official Microsoft WSL references, and [`docs/PATCH-NOTES.md`](docs/PATCH-NOTES.md) for the implementation boundary.

## v14.4.8 maintenance patch

v14.4.8 packages the validated maintenance work on top of v14.4.7. The v14.4.7 web-extraction design remains intact: SearXNG is the local, keyless `web_search` backend and `latticevale-local` provides bounded keyless `web_extract` for public HTTP(S) text pages. v14.4.8 additionally makes clean/repair reconciliation fill Hermes Local Browser / Chromium and a 360-second auxiliary extraction timeout only when those installer-managed defaults are missing, while preserving explicit user browser/provider/timeout choices. It also carries the Linux static-audit and release-manifest portability fixes and the consolidated current v14.x documentation. No new service, image, daemon, port, API key, package install, paid dependency, or resource reservation is introduced.

A healthy local SearXNG/Hermes integration can still occasionally return **zero search results** when upstream search engines rate-limit, CAPTCHA, or temporarily suspend automated requests. That condition is external to LatticeVale and does not by itself mean the installation needs repair. Retry later or broaden the query; when an authoritative URL is already known, Hermes can use `web_extract` directly without depending on search discovery. A repair investigation is warranted when the local SearXNG API/provider configuration itself fails, not merely because one successful search call returned an empty result set.

The migration is preservation-first. If a managed profile already names an explicit extract-capable/shared backend such as Firecrawl, Tavily, Exa, Parallel, or another custom provider, LatticeVale leaves that choice intact. The original v14.4.7 extraction migration and the v14.4.8 reliability migration advance only the installer-owned integrations checkpoint, so existing managed installs can adopt the required integration state without forcing a managed image/package refresh solely because the bundle version changed. By default, Hermes URL-safety policy rejects private/internal targets; cloud-metadata targets remain blocked even when a user explicitly enables Hermes private-URL access. Credential-bearing URLs are rejected, redirects are revalidated, connect-time DNS rebinding is guarded by Hermes's own SSRF-safe client, and downloads/output are bounded.

See [`docs/PATCH-NOTES.md`](docs/PATCH-NOTES.md) for the consolidated v14.x implementation and migration notes.

For installer-managed Hermes profiles, a fresh install or Resume / repair selects Hermes's free local Chromium browser only when no explicit browser backend/provider, browser gateway route, or recognized Hermes browser environment selection already indicates another choice. Existing explicit choices are preserved. If `auxiliary.web_extract.timeout` is missing, LatticeVale fills Hermes's documented fresh-install default of `360` seconds. SearXNG remains the managed search backend and `latticevale-local` remains the managed extraction backend. This is installer/runtime reconciliation only; LatticeVale does not change `SOUL.md`, prompts, or model policy for this behavior. See [`docs/SUPPORT.md`](docs/SUPPORT.md) for official upstream troubleshooting links.

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

Before launching a repair install, fully stop the selected LatticeVale WSL distro. If the Windows lifecycle shortcuts are installed, **Shut Down LatticeVale** is the recommended preparation step: it stops the managed LatticeVale stack and then terminates only the selected distro. A global `wsl --shutdown` is not required.

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

Intermediate v14.4.3–v14.4.8 installations are not required when upgrading from the supported v14.4.2 public baseline to v14.4.82 through normal Resume / repair.

## Release history

- **v14.4.82 — WSL recovery return-value hotfix:** fixes successful helper output/exit-code isolation so same-run re-probe actually occurs.
- **v14.4.81 — WSL launch-recovery hotfix:** adds bounded in-run recovery for registered distros blocked by `Wsl/Service/E_UNEXPECTED`, with explicit backed-up NAT fallback only for persistent mirrored-networking cases.
- **v14.4.8 — Maintenance release:** formalizes conservative Hermes clean/repair web-browser defaults, the two CI portability fixes, and the current documentation consolidation without adding services or taking ownership of user policy.
- **v14.4.7 — Web extraction:** added bounded keyless public-page extraction while keeping SearXNG as the managed search backend.

| Version | Type | Primary change |
| --- | --- | --- |
| **v14.4.1** | Patch | Repository/release layout cleanup |
| **v14.4.2** | **Main Release** | Public baseline |
| **v14.4.3** | Patch | RAM efficiency and uninstaller hardening |
| **v14.4.4** | Patch | Repair-time SQLite/metadata race hardening |
| **v14.4.5** | Patch | Runtime-policy and repair convergence |
| **v14.4.6** | **Main Release** | Prior cumulative main release |
| **v14.4.7** | Patch | Keyless web extraction |
| **v14.4.8** | Patch | Conservative Hermes clean/repair reliability + CI portability + documentation consolidation |
| **v14.4.81** | Patch | Preservation-first WSL `E_UNEXPECTED` launch recovery |
| **v14.4.82** | **Current Release** | Successful WSL recovery now returns a scalar exit code and continues same-run eligibility re-probe |

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

Prior cumulative main release. Includes the v14.4.3–v14.4.5 fixes plus corrected WSL CPU resource fingerprinting and refined managed-update triggering.

### v14.4.7

Added the bounded keyless `latticevale-local` public-page extraction provider while retaining SearXNG as the managed search backend and preserving explicit extraction-provider choices.

### v14.4.8

Formalizes the conservative Hermes clean/repair reliability follow-up: Local Browser / Chromium and the 360-second extraction timeout are filled only when missing, explicit user choices remain authoritative, CI path handling is hardened, and current v14.x patch documentation is consolidated. No new service, paid provider, API key, or user-policy ownership is introduced.

### v14.4.81

Adds bounded same-run recovery for a registered WSL distro that fails preflight with `Wsl/Service/E_UNEXPECTED`: clean WSL shutdown/retry first, then an explicit backed-up NAT fallback only when mirrored networking is configured and the failure persists. The distro/VHDX remain preserved and deeper Windows repair is not automatic.

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
v14.4.6  MAIN RELEASE / prior cumulative main release
    ↓
v14.4.7  web-extraction patch
    ↓
v14.4.8  maintenance release
    ↓
v14.4.81 WSL launch-recovery hotfix
    ↓
v14.4.82 WSL recovery return-value hotfix / current recommended release
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

Detailed version-specific implementation and audit notes are consolidated in [`docs/PATCH-NOTES.md`](docs/PATCH-NOTES.md). `docs/CHANGELOG.md` remains the canonical chronological release history.

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

### Install

From an Administrator PowerShell window at the repository/release root:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1
```

### Verify release

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\verify-release.ps1
```

### Uninstall

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\uninstall.ps1
```

For an existing installation, the installer provides state-aware verification, Resume / repair, reconfiguration, advanced recovery, and managed-update options.

## License

See [`LICENSE`](LICENSE).
