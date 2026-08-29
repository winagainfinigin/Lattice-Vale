# LatticeVale v14.4.85

> For an existing LatticeVale installation, launch the **full v14.4.85 release** and choose **Resume / repair installation** first. Use **Update / repair installer-managed software** only when you intentionally want to force this bundle's managed package/image/source refresh after the required safety backup. The separate patch ZIP is for overwriting a source checkout, not for layering files over a live installed stack.

### v14.4.85 — reconcile/readiness and maintenance reliability

v14.4.85 promotes the accumulated pre-release reliability candidate into a normal versioned release. It fixes startup-aware reconcile and post-gateway readiness ordering; verifies Synapse/Docker DNS from inside `hermes-agent`; waits boundedly for managed Ollama, Hermes API, Dashboard, and Matrix readiness after the final gateway lifecycle mutation; and reports the exact component that fails. Internal `reconcile` and `kanban_gateway` checkpoints remain revision 4 so existing v14.4.84 installs replay the corrected lifecycle during Resume / repair. It also makes Option 6 self-repairing with a bundle-owned pre-update safety-backup helper that does not depend on the installed `manage.sh`, preserves exact backup diagnostics, and makes Option 3 print a fresh Linux/Docker/Hermes plus Windows-side read-only verification report. The v14.4.84 WSL lifecycle/shortcut transport protections remain inherited unchanged.

The existing-stack menu was additionally audited end-to-end for Options 2, 4, and 5. Change-components now preserves secondary Matrix identity intent while removing disabled Matrix runtime credentials/stopping profile gateways, forces a real provider selection when leaving installer-owned Ollama, and normalizes only impossible dependent Tailscale exposures. Provider/profile reconfiguration now states its saved local-AI boundary explicitly. Advanced Matrix identity rebuild is gated on shared Matrix, preserves/reuses the existing human admin and secondary-profile identities/rooms, and uses a resumable transaction that backs up default-bot credentials/crypto state before persisting a unique replacement default device/bootstrap and retiring the old installer-owned default runtime identity.

### v14.4.84 Hotfix 1 — Matrix gateway startup readiness

If you already downloaded the initial public v14.4.84 release, use the **Hotfix 1 full release** and choose **Resume / repair installation**. The version remains 14.4.84. Hotfix 1 fixes a restart/startup race where Hermes gateways could start while Synapse/Docker DNS was not yet reachable from inside `hermes-agent`; the gateway process could remain running while Element messages stopped reaching the default or named Matrix profile. The hotfix waits for Synapse, verifies `synapse:8008` from inside the Hermes container, then reconciles the default and selected profile gateways. It also makes the state audit treat an internally unreachable Matrix backend as broken instead of reporting a false healthy gateway. Fresh installs use the same ordering automatically. Internal reconciliation checkpoint revisions are advanced so Resume / repair on an already-installed initial 14.4.84 copy cannot skip the hotfix.

LatticeVale is a source-visible **Windows + WSL2 installer, integration layer, and lifecycle manager for a self-hosted Hermes Agent stack**.

It installs into an **existing supported Ubuntu WSL2 distribution**, provisions Docker and Hermes, and can integrate Matrix, multi-profile Kanban orchestration, Honcho memory infrastructure, SearXNG, QMD indexing, Ollama/local AI, Obsidian, Windows lifecycle shortcuts, and Tailscale remote access.

LatticeVale is intentionally **recovery-aware and ownership-conscious**. It manages the Hermes stack without treating the user's WSL installation, Docker environment, Windows applications, Tailscale configuration, or persistent data as disposable.

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

- Hermes installation, configuration, gateways, providers/models, skills, and memory integration
- multi-profile Hermes with independent gateways and Matrix identities
- Kanban triage, decomposition, dispatch, review, dependencies, and concurrency controls
- Matrix/Synapse provisioning and cross-signing persistence
- Honcho local contextual-memory infrastructure
- SearXNG search plus keyless public-page extraction for Hermes research
- Hermes Local Browser / Chromium support using the runtime supplied by the pinned Hermes image
- QMD indexing, including optional Windows Obsidian vault access
- LatticeVale-managed or supported Windows-native Ollama integration
- adaptive Docker/WSL resource policy
- Windows/Tailscale relays and remote exposure
- coordinated Start / Shutdown behavior
- verification, audit, repair, update, backup, and controlled uninstall

Persistent Hermes profiles, sessions, memory, Matrix state, Honcho data, Ollama models, QMD data, credentials, backups, Obsidian data, and explicit Compose overrides are preserved during normal repair and update operations.

---

## v14.4.84 — WSL shutdown lifecycle and host-transport repair

v14.4.84 fixes a LatticeVale-created Windows shortcut behavior that could trigger a current WSL 2.7.x hvsocket/session failure. The pre-v14.4.84 **Shut Down LatticeVale** shortcut stopped the managed stack and then ran targeted `wsl.exe --terminate <distro>`. On affected Windows/WSL builds, targeted termination can leave the distro reported as **Running** while every new WSL session fails with `Wsl/Service/E_UNEXPECTED` and the Linux journal records `UtilAcceptVsock ... accept4 failed 110`.

v14.4.84 changes the lifecycle contract:

- **Start/Shut Down now invoke `manage.sh` directly through WSL `--cd` instead of the older nested `bash -lc` positional-argument wrapper that could return exit 127 (`./manage.sh: No such file or directory`).**
- **Shut Down LatticeVale stops the managed LatticeVale stack only. It no longer terminates the WSL distro.**
- The shortcut never substitutes global `wsl --shutdown`; users who intentionally want to stop all WSL2 distros may run that Microsoft command separately with awareness of its global impact.
- Existing-install **Resume / repair** detects the exact installer-owned legacy shortcut helper containing targeted `wsl --terminate` behavior. When found, it cleanly stops the managed stack, performs a bounded global WSL shutdown (with confirmation if other distros are running), restarts `WslService`, verifies the same registered distro can create a new session, and then replaces the legacy shortcut helper/configuration.
- The bounded WSL launch-recovery helper also restarts `WslService` after its clean WSL shutdown when elevation is available, so stale Windows-side session transport is discarded before the same distro is re-probed.
- This repair does **not** unregister/import/move/convert/recreate the distro, edit/delete its VHDX, automatically restart HNS/vmcompute, or change `.wslconfig` networking settings as part of the legacy-shortcut migration.
- Shortcut configuration schema advances to 4 so repair can distinguish and replace older/broken lifecycle helpers and verify the direct WSL `--cd` launcher contract.
- **Fresh installs use the same corrected schema-4 helper immediately:** when Windows shortcuts are selected, the installer copies the fixed launcher and creates Start/Shut Down shortcuts during the normal final Windows reconciliation; no legacy-helper detection or repair-only migration is required.

This release retains the v14.4.83 resource-policy v4, Redis/Valkey overcommit, Ubuntu-Pro-removal, and canonical launcher fixes.

---

## v14.4.83 Hotfix 2 — public launcher correction

Hotfix 2 corrects the documented public Windows entry-point filenames without changing the v14.4.83 runtime/resource policy. The primary repository/release commands are now:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\Install-LatticeVale.ps1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\Uninstall-LatticeVale.ps1
```

The lowercase `installer\install.ps1` and `installer\uninstall.ps1` launchers remain shipped and manifest-verified for backward compatibility with existing automation, but current documentation and helper guidance use the canonical `Install-LatticeVale.ps1` / `Uninstall-LatticeVale.ps1` names. `installer\verify-release.ps1` is unchanged.

---

## v14.4.83 resource/runtime repair patch

v14.4.83 is a narrow reliability patch based on real WSL runtime evidence. It preserves the existing LatticeVale architecture and ownership boundaries while correcting three managed behaviors:

- **Adaptive resource policy v4:** managed WSL/Docker Ollama receives additional protected memory headroom when the existing aggregate container budget can safely support it. The overall WSL-visible container budget and non-container reserve remain bounded; LatticeVale still does not write global WSL `memory` or `autoMemoryReclaim` settings.
- **Redis/Valkey prerequisite:** clean install and Resume / repair persistently ensure `vm.overcommit_memory=1` through the root-owned `/etc/sysctl.d/99-latticevale-redis-valkey.conf` drop-in whenever LatticeVale-managed SearXNG/Valkey or Honcho/Redis is selected. The effective value is verified by the state-aware audit.
- **Ubuntu Pro integration removed:** LatticeVale no longer offers, stores, installs, verifies, or manages Ubuntu Pro for WSL. Existing Ubuntu Pro packages, attachment, or external configuration are not uninstalled or altered by this migration.

Policy v4 is a repair/start migration. Existing adaptive policy-v3 installations are regenerated through the existing uncheckpointed runtime-policy reconciliation path, and affected containers are reconciled through Compose before repair can report success.

The installer completion output and this README now use the **selected Linux user explicitly** for `manage.sh` commands. This avoids accidentally resolving `~` to the wrong WSL account on distros whose default user differs from the account selected for LatticeVale.

---

## v14.4.82 hotfix

v14.4.82 fixes a Windows PowerShell return-channel bug in the bounded WSL launch recovery introduced in v14.4.81.

The v14.4.81 recovery helper could successfully recover a distro after:

```powershell
wsl --shutdown
```

while simultaneously writing diagnostic text to the PowerShell success stream. The installer could therefore capture both the helper's console output and its native exit code instead of receiving the scalar exit code `0`.

This caused a successful recovery to be treated as unsuccessful and prevented the installer from immediately re-probing the recovered distro.

v14.4.82 separates those channels:

- helper diagnostics remain visible to the user;
- the installer receives only the native process exit code;
- exit code `0` triggers a fresh probe of the same registered distro;
- normal Ubuntu, architecture, user, storage, and existing-installation eligibility checks then run again;
- a recognized installer-managed installation can continue through the existing **10 GiB Resume / repair storage floor**;
- a true clean installation continues to require the existing **50 GiB free-space reserve**.

No distro is recreated, imported, moved, converted, unregistered, or replaced by this recovery.

---

## v14.4.81 WSL launch recovery

v14.4.81 added bounded recovery for WSL host/service launch failures such as:

```text
Catastrophic failure
Error code: Wsl/Service/E_UNEXPECTED
```

When this failure prevents an otherwise registered distro from launching, LatticeVale can:

1. verify whether stopping WSL could affect other running distributions;
2. perform a clean `wsl --shutdown` recovery when safe or explicitly approved;
3. wait for WSL to settle;
4. re-probe the same registered distro;
5. continue the installer in the same run if the distro becomes healthy.

If persistent `E_UNEXPECTED` coincides with an explicitly configured global mirrored-networking mode, LatticeVale can separately offer the existing backed-up NAT fallback.

Normal LatticeVale configuration does **not** create, reapply, or require mirrored mode.

The bounded recovery does not:

- unregister the distro;
- import or recreate the distro;
- move or convert the distro;
- modify or delete its VHDX;
- automatically run DISM;
- automatically enable or disable Windows features;
- silently change global WSL networking.

Deeper Windows/WSL component repair remains an explicit operation through the included repair helper.

---

## v14.4.7 web extraction and Hermes reliability

v14.4.7 closed the default Hermes research gap present in the v14.4.6 stack.

SearXNG remains the local, keyless `web_search` backend while LatticeVale supplies a small keyless `web_extract` provider for public HTTP(S) text pages.

The provider runs inside the existing Hermes container and adds no additional:

- service
- image
- daemon
- port
- API key
- package installation
- resource reservation

For installer-managed profiles using the LatticeVale defaults, the normal free web-research stack is:

```text
Search:      SearXNG
Extraction:  LatticeVale local extraction provider
Browser:     Hermes Local Browser / Chromium
```

A missing Hermes auxiliary web-extraction timeout is repaired to the supported `360` second default.

Explicit user/provider choices remain authoritative. LatticeVale does not replace deliberately configured Browserbase, Browser Use, Camofox, CDP, browser-gateway, custom browser/provider, credential, or explicit timeout settings merely to enforce its defaults.

LatticeVale also does **not** modify `SOUL.md`, prompts, model policy, or other user-owned AI behavior as part of this integration repair.

### Search availability

A healthy local SearXNG/Hermes integration can occasionally return **zero search results** when upstream search engines rate-limit, CAPTCHA, suspend, or otherwise limit automated requests.

That condition is external to LatticeVale and does not by itself mean the installation needs repair.

When an authoritative URL is already known, Hermes can use `web_extract` independently of search discovery.

Repair investigation is appropriate when the local SearXNG API/provider path itself fails, rather than merely because one successful search request returned an empty result set.

### Extraction safety

The LatticeVale extraction provider:

- supports public HTTP(S) text-oriented resources;
- rejects credential-bearing URLs;
- rejects private/internal targets through Hermes URL-safety handling;
- keeps cloud-metadata targets blocked;
- revalidates redirects;
- uses Hermes's SSRF-safe HTTP client;
- guards connect-time DNS resolution;
- bounds downloaded and returned content.

See [docs/PATCH-NOTES.md](docs/PATCH-NOTES.md) for detailed implementation and historical patch notes.

---

## Lifecycle management

LatticeVale is not only an installer. It manages the ongoing lifecycle of the stack, including:

- fresh installation
- configuration and reconfiguration
- startup and shutdown
- status reporting
- health verification
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
3. repair the smallest necessary managed layer;
4. reconcile affected configuration and services;
5. verify the resulting state.

Completed installer checkpoints are not blindly trusted when live verification shows that managed state has drifted or failed.

---

## Resume / repair

**Option 1 — Resume / repair installation** is the normal upgrade and repair path.

It:

- reuses existing component selections;
- preserves persistent state;
- repairs incomplete or stale managed stages;
- applies required release migrations;
- regenerates stale runtime policy;
- reconciles affected containers where necessary;
- refreshes the managed package/image/source layer only when its normal refresh conditions require it.

A new LatticeVale bundle version alone does not automatically require a complete Docker image or source refresh.

### Storage requirements

LatticeVale intentionally distinguishes clean installs from existing managed repairs:

```text
Fresh installation:
  host partition > 50 GiB total
  at least 50 GiB free

Existing installer-managed Resume / repair:
  at least 10 GiB free
```

The lower repair threshold is used only after LatticeVale has confirmed an existing installer-managed installation.

---

## Forced managed update

**Option 6 — Update / repair installer-managed software** explicitly forces convergence of the installer-managed software layer. Before refresh it creates a verified **bundle-owned** safety backup, so a stale or broken installed `manage.sh` cannot prevent the updater from repairing that same managed layer. The backup includes persistent configuration/data and running PostgreSQL dumps, briefly stops only the currently-running LatticeVale containers for a consistent filesystem snapshot, then restores them before refresh.

Depending on the enabled components, this can include:

- prerequisite packages
- Docker packages
- managed images and builds
- audited source dependencies
- installer-owned runtime layers

Persistent application data and explicit user configuration remain preserved.

Use Option 6 when an actual managed-software refresh is desired. It is not required merely because the LatticeVale bundle version changed.

---

## Verification and health checks

After installation or repair, use the exact WSL distribution name selected for LatticeVale. If needed, list registered distributions first, then set `$Distro` once for the commands below:

```powershell
wsl --list --verbose
$Distro = Read-Host "Enter the exact WSL distro name used by LatticeVale"
$LinuxUser = Read-Host "Enter the Linux user selected for LatticeVale"
wsl -d $Distro -u $LinuxUser -- bash -lc 'cd "$HOME/hermes-stack" && ./manage.sh verify'
```

A successful installation reports:

```text
LatticeVale verification: HEALTHY
```

For the detailed state-aware audit:

```powershell
wsl -d $Distro -u $LinuxUser -- bash -lc 'cd "$HOME/hermes-stack" && ./manage.sh audit'
```

For a status snapshot:

```powershell
wsl -d $Distro -u $LinuxUser -- bash -lc 'cd "$HOME/hermes-stack" && ./manage.sh status'
```

`manage.sh` belongs to the installed Linux stack and should therefore be invoked through WSL when running from Windows PowerShell.

---

## Adaptive RAM and resource policy

LatticeVale resource policy **v4** is designed to reduce unnecessary WSL/Docker memory pressure while retaining operational headroom.

Depending on the enabled services, it can apply:

- adaptive per-container memory ceilings
- WSL-aware memory budgeting
- reduced glibc allocator arenas
- Synapse cache tuning
- reduced PostgreSQL fixed `shared_buffers`
- protected managed-Ollama memory headroom within the aggregate WSL container budget
- controlled Ollama model residency
- bounded Ollama parallelism
- short Ollama model keep-alive behavior

Explicit user `compose.override.yaml` configuration remains authoritative and is applied after generated LatticeVale resource policy.

---

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

Managed refresh is instead controlled by actual runtime state, the managed-refresh policy/revision, periodic refresh conditions, required migrations, or an explicit forced update.

This allows:

- **v14.4.5 → v14.4.6:** the audit fix without unnecessarily rebuilding healthy managed images solely because the version changed.
- **v14.4.2 → current:** the required cumulative migrations from the older public baseline.

Intermediate v14.4.3–v14.4.6 installations are not required when upgrading from the supported public baseline through the normal Resume / repair path.

---

## Release history

| Version | Type | Primary change |
| --- | --- | --- |
| **v14.4.1** | Patch | Repository/release layout cleanup |
| **v14.4.2** | **Main Release** | Public v14.4.x baseline |
| **v14.4.3** | Patch | RAM efficiency and uninstaller hardening |
| **v14.4.4** | Patch | Repair-time SQLite/metadata race hardening |
| **v14.4.5** | Patch | Runtime-policy and repair convergence |
| **v14.4.6** | **Main Release** | CPU fingerprinting and managed-refresh refinement |
| **v14.4.7** | Patch | Keyless web extraction and conservative Hermes web/browser defaults |
| **v14.4.81** | Hotfix | Bounded same-run recovery for WSL `E_UNEXPECTED` launch failures |
| **v14.4.82** | Hotfix | Correct successful WSL-recovery exit-code handling |
| **v14.4.83** | Patch / Hotfix 2 | Ollama policy v4, Redis/Valkey overcommit prerequisite, Ubuntu Pro integration removal, canonical public launcher correction |
| **v14.4.84** | Release / Hotfix 1 | WSL lifecycle transport repair plus Matrix gateway startup-readiness hotfix |
| **v14.4.85** | **Current install release** | Startup-aware reconcile/post-gateway readiness, self-repairing pre-update backup, and explicit read-only verification output |

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

Files that genuinely disappear during live traversal are tolerated while actual permission, mount, ownership, and filesystem failures remain errors.

### v14.4.5

Added explicit runtime-policy convergence so stale adaptive configuration cannot be skipped merely because an older installer checkpoint is marked complete.

When required, LatticeVale regenerates the policy, invalidates affected repair state, reconciles Compose, and recreates affected containers so new runtime settings become live.

### v14.4.6 — Main Release

Includes the v14.4.3–v14.4.5 fixes plus corrected WSL CPU resource fingerprinting and refined managed-update triggering.

### v14.4.7

Added the keyless local public-page extraction provider and conservative Hermes Local Browser / extraction-timeout reconciliation.

### v14.4.81

Added bounded same-run recovery for WSL host/service `E_UNEXPECTED` launch failures while preserving distro registration, VHDX data, and the existing clean/repair storage policy.

### v14.4.82

Corrects the helper return-channel handling so a successful v14.4.81 WSL recovery is recognized as successful and the installer immediately re-probes the recovered distro.

### v14.4.83

Advances adaptive runtime policy to v4 with protected managed-Ollama headroom, persistently manages the Redis/Valkey `vm.overcommit_memory=1` prerequisite, removes the LatticeVale-owned Ubuntu Pro option/integration without uninstalling external state, and makes the documented/final `manage.sh` commands explicitly target the selected Linux user.

### v14.4.84

Removes targeted `wsl --terminate` from the Windows shutdown shortcut. Existing installations should use the full v14.4.84 release and choose **Resume / repair installation** so LatticeVale resets WSL/WslService transport when it detects its exact legacy unsafe shortcut helper, then rewrites the shortcut to stack-stop-only behavior.

### v14.4.85

Promotes the accumulated startup/reconcile and maintenance reliability fixes into a normal versioned release. Existing v14.4.84 installations should use the full v14.4.85 release and choose **Resume / repair installation** so internal lifecycle checkpoints replay the corrected gateway/readiness ordering without recreating persistent identities or data.

```text
v14.4.1   release-layout patch
    ↓
v14.4.2   MAIN RELEASE / public baseline
    ↓
v14.4.3   RAM + uninstall patch
    ↓
v14.4.4   repair-race patch
    ↓
v14.4.5   runtime-policy repair patch
    ↓
v14.4.6   MAIN RELEASE
    ↓
v14.4.7   web extraction + Hermes reliability
    ↓
v14.4.81  WSL E_UNEXPECTED recovery
    ↓
v14.4.82  WSL recovery return-channel hotfix
    ↓
v14.4.83  resource/runtime repair patch + Hotfix 2 launcher correction
    ↓
v14.4.84  WSL lifecycle transport repair + Matrix readiness Hotfix 1
    ↓
v14.4.85  reconcile/maintenance reliability / CURRENT INSTALL RELEASE
```

---

## Ownership and safety boundaries

LatticeVale does not automatically treat the following as disposable:

- the WSL distribution itself
- its VHDX
- unrelated Docker containers, images, volumes, or networks
- global WSL networking configuration
- Windows-native Ollama
- Windows Tailscale
- user-modified Windows shortcuts or scheduled tasks
- Obsidian vault contents
- unrelated user documents
- user-owned Hermes configuration
- persistent application data

Where ownership cannot be safely established, repair and uninstall behavior favors preservation rather than destructive guessing.

---

## Documentation

The repository includes detailed documentation beyond this README.

Start with:

- [docs/README.md](docs/README.md) — documentation index and project overview
- [docs/Instructions.txt](docs/Instructions.txt) — installation, upgrade, repair, and operating procedures
- [docs/FEATURES.md](docs/FEATURES.md) — supported components, options, integrations, and capabilities
- [docs/Installer Description.txt](docs/Installer%20Description.txt) — installer architecture, stages, ownership boundaries, and recovery behavior
- [docs/SUPPORT.md](docs/SUPPORT.md) — diagnostics, troubleshooting, official upstream resources, and recovery guidance
- [docs/SECURITY.md](docs/SECURITY.md) — trust boundaries, networking, secrets, exposure, and ownership policy
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — chronological release history
- [docs/PATCH-NOTES.md](docs/PATCH-NOTES.md) — consolidated detailed v14.x implementation and patch notes
- [docs/RELEASE.md](docs/RELEASE.md) — release validation, packaging, manifests, and maintainer requirements
- [docs/SOURCES.md](docs/SOURCES.md) — upstream source and dependency references
- [docs/THIRD-PARTY-NOTICES.md](docs/THIRD-PARTY-NOTICES.md) — third-party attribution and distribution boundaries
- [docs/WINDOWS-INTEGRATION-TEST-MATRIX.md](docs/WINDOWS-INTEGRATION-TEST-MATRIX.md) — Windows/WSL integration validation matrix

Historical one-off v14.x patch documents have been consolidated into `docs/PATCH-NOTES.md` to keep the repository easier to navigate while preserving their technical content.

**For exact behavior, use the shipped source, current documentation, compatibility metadata, source manifest, and regression tests as the authoritative reference.**

---

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

---

## Getting started

Start with:

1. [docs/README.md](docs/README.md)
2. [docs/Instructions.txt](docs/Instructions.txt)
3. [docs/FEATURES.md](docs/FEATURES.md)

### Install

From PowerShell at the repository or release root:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\Install-LatticeVale.ps1
```

LatticeVale requires an existing supported Ubuntu WSL2 distribution. It does not create, import, move, unregister, or convert one as part of normal installation.

### Verify release files

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\verify-release.ps1
```

This verifies the release/source package and checksum manifest. It is distinct from verifying the live installed stack.

### Verify or audit an installed stack

Use the exact WSL distribution name selected during LatticeVale installation. If you are unsure of its registered name, list the distributions first:

```powershell
wsl --list --verbose
$Distro = Read-Host "Enter the exact WSL distro name used by LatticeVale"
$LinuxUser = Read-Host "Enter the Linux user selected for LatticeVale"
wsl -d $Distro -u $LinuxUser -- bash -lc 'cd "$HOME/hermes-stack" && ./manage.sh verify'
```

For the detailed state-aware audit, reuse the same `$Distro` value:

```powershell
wsl -d $Distro -u $LinuxUser -- bash -lc 'cd "$HOME/hermes-stack" && ./manage.sh audit'
```

### Uninstall

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\Uninstall-LatticeVale.ps1
```

For an existing installation, the installer provides state-aware verification, Resume / repair, reconfiguration, advanced recovery, and managed-update options.

---

## License

LatticeVale is licensed under the MIT License.

See [LICENSE](LICENSE).
