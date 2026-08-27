# LatticeVale v14.4.83 — Stable

> **v14.4.83:** retains the v14.4.82 WSL recovery fix and adds a narrow runtime reliability migration: adaptive resource policy v4 protects managed Ollama from the observed ~3 GiB cgroup ceiling when the existing aggregate budget can safely provide more headroom; selected Redis/Valkey workloads receive a persistent `vm.overcommit_memory=1` prerequisite; and the LatticeVale-owned Ubuntu Pro option is removed without uninstalling external Ubuntu Pro state. See [`PATCH-NOTES.md`](PATCH-NOTES.md) and [`SUPPORT.md`](SUPPORT.md).

**Unofficial, inspectable Windows + WSL2 installer and lifecycle manager for a self-hosted Hermes Agent stack.**

LatticeVale deploys and repairs Hermes Agent inside an **existing supported Ubuntu WSL2 distro** using Docker Engine/Compose. Optional integrations include the Hermes Dashboard, named profiles, Kanban orchestration, Matrix/Synapse, SearXNG, QMD/Obsidian, Honcho memory, managed or native-Windows Ollama, private Windows Tailscale access, adaptive container resource ceilings, Ubuntu/WSL maintenance policy, and Windows lifecycle helpers.

**v14.4.6 corrects adaptive-resource audit fingerprinting when WSL is processor-limited below the Windows host and avoids version-only managed refreshes.** The audit now uses the process-visible CPU set, matching the `nproc` semantics used to generate and refresh policy v3. Resume / repair no longer pulls/rebuilds managed components merely because `VERSION.txt` changed; refresh is driven by the managed-refresh revision, 30-day age gate, missing legacy state, or explicit Option 6. This means 14.4.5→14.4.6 can apply the audit fix without rebuilding healthy images, while 14.4.2→14.4.6 still adopts the cumulative component/runtime changes because its refresh revision and adaptive-policy version are older.

**v14.4.5 introduced the current repair-convergence mechanics over v14.4.4.** It makes adaptive RAM policy v3 an explicit repair obligation instead of relying on a possibly completed `prepare_config` checkpoint, reconciles changed Compose resource policy into running containers, and prevents final success while runtime policy is stale. v14.4.83 retains those mechanics and migrates enabled policy-v3 state to policy v4, v14.4.8's Hermes/web maintenance, and v14.4.6's replacement of the version-only component-refresh trigger with the managed-refresh revision/age/explicit-force model.

For detailed history, use `CHANGELOG.md`. Detailed implementation/audit notes for the v14.x patch line are consolidated in `PATCH-NOTES.md`; the v13 archive remains under `legacy-patch-notes/`.

### Release layout (v14.4.1+)

The extracted release root is intentionally kept clean:

- `installer/` — public PowerShell entry points and `SOURCE-SHA256SUMS.txt`;
- `docs/` — operator, security, release, feature, support, and patch documentation;
- `LatticeVale-Core/` — installer/runtime implementation;
- `tools/` — maintenance/release helper scripts;
- `.github/`, `.gitattributes`, `.gitignore` — Git/GitHub metadata kept at repository root;
- `README.md` and `LICENSE` — conventional GitHub landing/legal files kept at repository root.

Run public entry points from the repository root using `./installer/...` as shown below.

### Inherited v14.4.3 RAM-efficiency policy

When adaptive container resource limits are enabled, policy v4:

- derives ceilings from CPU/RAM actually visible inside WSL while reserving 30% on <=6 GiB, 25% on <=12 GiB, 20% on <=24 GiB, and 15% above that, with bounded reserve floors/caps;
- applies `MALLOC_ARENA_MAX` to long-lived glibc/Python services to limit allocator arena growth;
- lowers Synapse's supported `SYNAPSE_CACHE_FACTOR` on smaller WSL VMs;
- uses 64 MiB PostgreSQL `shared_buffers` on <=12 GiB WSL VMs and 128 MiB above that while preserving Honcho PostgreSQL's existing `max_connections=200`;
- keeps user `compose.override.yaml` last and authoritative.

The policy is applied on clean install and regenerated on repair/start when an older resource-policy revision or changed WSL CPU/RAM fingerprint is detected. LatticeVale does not set a global WSL memory cap or `autoMemoryReclaim`; current WSL memory-reclaim behavior remains host/user-owned.

### Inherited v14.4.3 uninstall hardening

Normal uninstall now refuses to continue if stack metadata indicates Docker runtime may still exist but the Docker daemon cannot be inspected. This avoids deleting Windows integration/state while restartable containers are left behind. It also preserves stack-specific helpers/configs still referenced by a retained task or shortcut, restores installer-owned `OLLAMA_HOST` state with a Windows environment-change broadcast, and removes shared Linux dockerd logging only when no other recognizable LatticeVale stack remains in the distro.

## Major capabilities

- Hermes Agent with the default profile plus optional named profiles and profile-specific provider/model choices.
- Optional Kanban orchestration with triage, profile-aware dispatch, concurrency controls, review, and durable task results.
- Agent-managed reusable skills. Fresh installer-managed profiles default `skills.write_approval` to `false` when no explicit setting exists, allowing automatic skill writes; repair/update preserves an explicit existing choice.
- Optional Matrix/Synapse with PostgreSQL, encrypted managed rooms, and optional dedicated profile Matrix identities/rooms.
- Optional SearXNG, QMD, Windows-local Obsidian integration, Honcho memory, and Hermes Dashboard.
- Managed WSL/Docker Ollama or integration with a separately installed native Windows Ollama backend.
- Optional Auto/CPU/NVIDIA/AMD-ROCm managed-Ollama acceleration when prerequisites are verified.
- Optional adaptive per-container CPU/RAM ceilings based on WSL-visible resources.
- Optional Windows Tailscale Serve exposure for selected private services; public Funnel is not the managed path.
- Preservation-first Resume/repair, scoped component changes, read-only verification, provider/profile reconfiguration, advanced recovery, controlled bundle-aligned update/repair, backup, and lifecycle tooling.
- Separate dry-run-first clean-host reset tooling for an intentionally destructive WSL/LatticeVale rebuild.

See **`FEATURES.md`** for the complete current feature and installer-option reference, **`Instructions.txt`** for procedures, **`Installer Description.txt`** for capability/configuration explanations, and **`SECURITY.md`** for trust and privilege boundaries.

### GPU acceleration and resource ceilings

When **LatticeVale-managed WSL/Docker Ollama** is selected, LatticeVale can use **Auto**, **CPU**, **NVIDIA**, or **AMD/ROCm** acceleration. v14.3.5 probes the **selected Ubuntu distro** before a forced GPU mode is accepted; Windows GPU presence alone is not treated as container readiness. Auto enables an accelerator only after its WSL/Docker prerequisites pass and otherwise falls back to CPU. Forced NVIDIA requires `/dev/dxg` plus a working WSL `nvidia-smi` probe before selection and may then install/configure the tested NVIDIA Container Toolkit 1.20.0 package set; a complete newer toolkit is preserved. The managed Ollama Docker AMD/ROCm path requires x86_64 plus `/dev/kfd` and `/dev/dri`; `/dev/dxg` alone is not assumed to satisfy that path. On repair, an unusable saved forced mode is explicitly reconciled before bootstrap.

**Native Windows Ollama is an optional advanced integration.** It crosses Windows/WSL/Docker networking and firewall boundaries; users who prefer the smallest integration surface should select LatticeVale-managed WSL/Docker Ollama instead. See `NATIVE-OLLAMA-INTEGRATION.md` and `WINDOWS-INTEGRATION-TEST-MATRIX.md`.

Alternatively, if native Windows Ollama is installed, LatticeVale detects the installation separately from its runtime state. If the local API is stopped, setup clearly states that native Ollama must be running, and selecting the native option can explicitly launch that existing installation and re-probe it. Once a Windows-local API and a safe relay topology are both verified, the questionnaire offers **native Windows Ollama**. The selected models do **not** need to be downloaded manually first: LatticeVale queries Ollama's model list, pulls missing selected models through the native API when needed, verifies the requested embedding capability directly through that already-verified API path, and routes Hermes/Honcho to it. It does **not** install/update native Ollama or choose its Windows GPU backend. Its preferred private transports do not change `OLLAMA_HOST`; only the explicitly accepted v14.3.18 direct-WSL fallback changes that bind setting, with installer-owned firewall scoping and rollback. Native Ollama therefore retains its own Windows GPU/Vulkan/ROCm behavior and Windows model store. If either the API or relay path is not verified, this option is not offered.

`./manage.sh status` reports detected VRAM/loaded-model evidence for the managed backend; native mode instead reports the reachable Windows Ollama runtime as externally owned.
The configured image **pin age** shown by status/verify remains an offline visibility signal and does not itself query upstream registries. Periodic repair refreshes are driven by the installer-managed refresh timestamp, not by that displayed pin-age value.

New installs can enable adaptive Docker CPU/RAM ceilings derived from the resources visible to WSL. These are **per-container ceilings**, not reservations or a global cap on aggregate WSL memory use; Windows/WSL global resource policy remains separate. Repairs of pre-v14.2 installs default to their prior unrestricted behavior, and a user-maintained `compose.override.yaml` is merged last so deliberate local overrides win.

## Security and review before running

This project intentionally ships as **plain-text PowerShell, Bash, Python, YAML, and configuration files**. The release contains no compiled installer executable, no Python bytecode, no encoded PowerShell payload, and no `curl | bash` bootstrap path. You can inspect every installer action before execution.

Recommended review flow:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\verify-release.ps1
```

Then inspect at minimum:

- `installer\install.ps1`
- `LatticeVale-Core\Install-LatticeVale.ps1`
- `LatticeVale-Core\linux\bootstrap.sh`
- `LatticeVale-Core\stack\configure-stack.sh`
- `LatticeVale-Core\stack\compose.yaml`
- `docs\SECURITY.md`

`installer\SOURCE-SHA256SUMS.txt` records hashes for every shipped release file except the manifest itself. For a GitHub release, also compare the **ZIP SHA-256** shown on the release page with `Get-FileHash` before extracting/running it.

The supported launch command uses a **single isolated child PowerShell process** with an execution-policy override:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1
```

`-ExecutionPolicy Bypass` applies only to that spawned `powershell.exe` process; it does not change LocalMachine or CurrentUser policy. It is a convenience for running reviewed unsigned source, **not** a trust or malware-verification mechanism. Review the files and hashes first.

See [SECURITY.md](SECURITY.md) for privileges, network exposure, secret handling, supply-chain boundaries, and vulnerability reporting.

### Evidence and release-history note

Current LatticeVale release history is consolidated in `CHANGELOG.md`. The original granular pre-LatticeVale v13 patch notes from the v13.16.6 bundle are also preserved verbatim under `docs/legacy-patch-notes/hermes-wsl-foundry-v13/` as an explicitly archival reference. That history is **not** a substitute for an independently verifiable Git commit/release history. Claims about prior live troubleshooting come from the project handoff/history that produced this source bundle and should be treated as project-reported unless independently reproduced. The current release should be judged by its inspectable source, reproducible tests, published hashes, CI results, and real-platform smoke testing.

## Requirements

- Windows 10/11 **x64/AMD64**, build 19041+
- Windows PowerShell 5.1 or PowerShell 7.x
- Microsoft WSL already installed and working
- Existing Ubuntu **22.04, 24.04, or 26.04** distro running as **WSL2**
- Selected Ubuntu distro architecture must be **amd64/x86_64** for the distributed LatticeVale bundle
- Normal non-root Ubuntu user with sudo access and Linux home under `/home/...`
- Windows Administrator access
- Internet access for packages/images/models selected during installation
- If native Windows Ollama is selected, enough free space in its Windows model store for any selected models that are not already present; LatticeVale can pull those missing models automatically through the native Ollama API
- Fresh installs: the Windows volume backing the chosen WSL distro must be **over 50 GiB total capacity and have at least 50 GiB free**

LatticeVale **does not install, import, unregister, convert, move, or repair WSL itself**. Fix a broken WSL installation separately before running LatticeVale. If a selected option needs a global `.wslconfig` change, LatticeVale detects other running WSL distros and asks before performing the required global WSL shutdown.

## Local customization and forks

LatticeVale's own source and documentation are released under the **MIT License**. You may inspect, copy, modify, fork, publish, redistribute, and adapt the installer for your own system or environment, subject to the MIT license notice requirements. System-specific forks are allowed; the published compatibility policy is the tested baseline for the official bundle, not a restriction on what you may change in your own copy.

If you customize the installer:

- Clearly identify the build as modified/downstream when sharing it; do not represent a changed bundle as an unmodified official LatticeVale release.
- Keep secrets, generated WSL data, backups, tokens, recovery keys, and machine-specific private state out of source control.
- If you change a file covered by `installer\SOURCE-SHA256SUMS.txt`, regenerate the manifest with `tools\New-SourceManifest.ps1` after all edits and run `installer/verify-release.ps1` before distribution.
- If you expand OS/version/architecture support, update `LatticeVale-Core/compatibility.conf` and the related tests instead of merely bypassing a preflight blocker. Verify every affected container image, package source, networking path, and GPU/runtime assumption for the new target.
- Third-party software fetched or built by LatticeVale retains its own license and terms. The MIT license for LatticeVale does not relicense those projects; see `THIRD-PARTY-NOTICES.md`.

Upstream contributions should remain portable and preservation-first, but a private or downstream fork may intentionally contain system-specific defaults as long as the maintainer understands and documents the resulting compatibility boundary.

## Quick start

1. Download the versioned release ZIP from GitHub and extract it. The ZIP filename may include the release version, but its single top-level folder is always named `Lattice-Vale`.
2. Open the extracted `LatticeVale` folder.
3. Optionally verify source hashes:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\verify-release.ps1
```

4. Open **PowerShell as Administrator** in that folder and run:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1
```

To target a distro explicitly:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1 -DistroName Ubuntu-24.04
```

`installer/install.ps1` verifies the included source manifest by default, then invokes the full readable installer at `LatticeVale-Core\Install-LatticeVale.ps1`.

## What the installer asks

A fresh install uses an **explicit questionnaire**. LatticeVale does not silently choose optional host/system-affecting settings: Y/N, numeric, menu, and Tailscale-port choices require input. **Suggested values are guidance only** and are shown inline for applicable questions; pressing Enter alone does not select a suggested host/system choice. For Tailscale HTTPS exposure the standard suggestions are **9443 for Dashboard** and **443 for Matrix**. Where machine state can be safely detected (for example the Ubuntu distro timezone), it is shown and may be accepted rather than guessed. Existing saved LatticeVale choices remain reusable during Resume / repair or Change installed components.

The saved questionnaire records the desired system state so clean install and later repair use the same intent. Choices include:

Before the Honcho/local-AI questions, the installer now states the Ollama ownership boundary explicitly: **managed WSL/Docker Ollama can be installed by LatticeVale**, while **native Windows Ollama must already be installed on Windows**; if it is installed but stopped, setup can explicitly launch that existing copy before deciding whether it can be offered. LatticeVale never installs or updates the native Windows application.


- Dashboard
- named Hermes profiles and role descriptions
- whether each profile clones the default provider/model or selects its own
- Kanban and concurrency limits
- Matrix/Synapse
- whether each named profile gets its **own Matrix bot/room**
- Windows Tailscale remote exposure
- SearXNG
- QMD
- **Windows-local Obsidian vault path**
- Honcho / local Hermes AI
- Ollama backend ownership (managed WSL/Docker or verified existing native Windows Ollama when available)
- Ollama text/embedding model choices and managed acceleration policy
- optional adaptive per-container CPU/RAM ceilings
- unattended updates
- WSL service lifetime policy
- optional Windows logon startup
- optional per-install Windows **Start / Shut Down desktop shortcuts**
- container timezone

If a profile is named `coder`, `researcher`, or anything else valid, Matrix provisioning follows **that exact profile**, not a hard-coded `assistant` name. Its Matrix gateway starts only after that profile's actual configured model is verified, whether the model was cloned from `default` or selected independently.

## Clean install, Resume / repair, and Update / repair

**v14.3.38 integration-policy migration:** clean installs write the current managed Kanban/skill policy immediately. Existing managed stacks re-run the integrations stage on the next mutating installer run even if an older integrations checkpoint was complete. This migration edits only the default profile plus profiles recorded as LatticeVale-managed; user-created profile configuration files are not rewritten, although valid user-created profile names remain eligible routing targets.

**Fresh install** creates a new LatticeVale-managed stack in the chosen user's Linux home.

Before starting a Windows **Resume / repair** or **Update / repair** install, fully stop the selected LatticeVale WSL distro. If the Windows lifecycle shortcuts are installed, use **Shut Down LatticeVale**: it stops the managed stack and then terminates only the selected distro. Global `wsl --shutdown` is not required.

**Resume / repair** is preservation-first, but it is not guaranteed to be update-free. It reconciles generated configuration, ownership, Compose state, selected services, Matrix/Tailscale integration, bounded maintenance, and health checks while preserving persistent application state. Between managed refresh windows it remains local-first and prefers already-installed images/builds. Every 30 days—and once when an older managed stack first adopts the managed-refresh policy, or when that policy revision changes—it performs a targeted refresh of LatticeVale-owned prerequisite/Docker packages and selected installer-owned image/build/source state. Explicit user-owned overrides and unrelated Ubuntu packages remain untouched.

**Update / repair installer-managed software** is the controlled on-demand updater for an existing managed stack. Choose it from the Windows installer's existing-stack menu when you want to apply the software versions/channels declared by the LatticeVale bundle you are currently running **now**, without waiting for the periodic repair window. It first requires a successful `./manage.sh backup`, then forces the managed refresh and runs the normal repair/verifier sequence. This is the recommended way to use a newer LatticeVale release as an updater.

The controlled updater covers the installer-managed layer: LatticeVale prerequisite packages; Docker Engine/CLI/containerd/Buildx/Compose packages; selected Compose images such as Hermes and Matrix/Synapse; installer-owned SearXNG and managed-Ollama pins; QMD's bundle-declared build version; the audited Honcho commit when its checkout is proven installer-owned; and the supporting selected image references declared by the bundle. Fixed version pins advance only when the newer LatticeVale bundle declares a new pin. Floating major/channel references are refreshed within the reference already declared by the bundle. Persistent Matrix/Honcho databases, Hermes profiles/memory/sessions, credentials, Ollama models, vault/workspace files, and explicit custom image/source overrides are preserved. Separately owned **native Windows Ollama is not updated by LatticeVale**.

`./manage.sh update` remains a separate **advanced upstream-refresh** command. It pulls the currently configured image references and may advance Honcho to the repository's current `HEAD`; it does not change fixed Hermes/Synapse version tags to whatever a newer LatticeVale release tested. Use the Windows **Update / repair installer-managed software** option for reproducible bundle-aligned updates.

## Profile-specific Matrix

When Matrix and named profiles are enabled, each selected Matrix-enabled profile can receive:

- its own `@<profile>:hermes.local` account
- its own access token and stable device ID
- its own encrypted room or an explicitly adopted existing encrypted room
- installer-created rooms pinned and verified at Matrix room version **10**
- its own E2EE/recovery state
- its own room/user allowlists
- its own independently supervised Hermes Docker/s6 gateway

The default `@hermes:hermes.local` identity is preserved. If an older LatticeVale release created a managed room at another version, Resume / repair preserves that room and creates a replacement encrypted v10 room; it does not attempt an in-place downgrade. LatticeVale does not use an invented `matrix2` configuration namespace and keeps `gateway.multiplex_profiles: false` for the managed topology.

## Obsidian/QMD

When Obsidian is selected, the installer asks for the **Windows-local vault path during the initial questionnaire**. The selected Windows drive path is translated through WSL's configured Windows-drive mount root (normally `/mnt`, but custom `wsl.conf` roots are supported), verified as Windows-backed storage with `findmnt`, and mounted into Hermes/QMD as `/vault`.

Do not point native Windows Obsidian at `\\wsl.localhost\...` for this LatticeVale vault design.

## Everyday management

If the optional Windows shortcuts are selected, LatticeVale creates two current-user desktop shortcuts named for the chosen distro/Linux user:

- **Start LatticeVale** — starts that distro, ensures Docker is available, then runs `./manage.sh start`, so only the services selected for that exact LatticeVale install are started.
- **Shut Down LatticeVale** — if that distro is running, runs `./manage.sh stop` (including its managed Windows relay) and then terminates **only that distro**. It never uses global `wsl --shutdown`.

The shortcut launcher is plain-text source at `LatticeVale-Core\windows\LatticeVale-Shortcut.ps1`; the installer copies it to the current user's `%LOCALAPPDATA%\LatticeVale` when the feature is enabled. Same-name shortcuts that are not provably LatticeVale-owned are left untouched.

From Ubuntu WSL:

```bash
cd ~/hermes-stack
./manage.sh start
./manage.sh stop
./manage.sh restart
./manage.sh verify
./manage.sh profiles
./manage.sh matrix-info
```

`./manage.sh status` and successful `verify` output include the configured image pins with the **LatticeVale pin date/age** (offline visibility only—no update check), plus a hardware/resource summary. When Ollama is selected, that summary includes GPU VRAM when it can be measured, a soft fit warning when the model artifact is already close to detected VRAM, and the `ollama ps` loaded-model runtime line when available.

`./manage.sh backup` creates a local backup with restrictive permissions and now reminds you that the archive may contain API keys, Matrix credentials, and other sensitive state. Encrypt or otherwise protect copies before putting them in cloud storage or on another system.

The Dashboard normally remains on `http://localhost:9119`. Matrix/Synapse is local unless the Windows Tailscale exposure option is enabled.


## Repair-state authority

Repair checkpoints are recorded in `.installer-state.json`, but they never override live validation. **The state file is only a hint**: repair stages still verify the components they own and rerun required migrations when the installed release changes.

In v14.4.5, adaptive runtime/RAM policy is reconciled outside the old `prepare_config` checkpoint. If policy v4 is missing/stale or the WSL-visible CPU/RAM fingerprint changed, repair regenerates the installer-owned overlay, marks infrastructure/full-stack reconciliation pending, and requires a final live policy verification before declaring success.

Managed software refresh is policy-aware rather than version-number-driven. Normal Resume / repair runs the bounded installer-owned package/image/source refresh when the 30-day age gate is due, the `MANAGED_REPAIR_REFRESH_REVISION` changes, or a legacy install lacks valid refresh state. The marker still records the installer version for provenance, but a version change alone does not trigger another pull/build cycle. An interrupted refresh with the same refresh-policy revision resumes its user-level phase without repeating completed root package work; a revision mismatch reruns the bounded root phase. Explicit Update / repair always forces the current bundle's managed refresh.

## Uninstall

Open **PowerShell as Administrator** in the extracted LatticeVale folder and run:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\uninstall.ps1
```

The uninstaller verifies the same release source manifest as `installer/install.ps1`, then asks which existing LatticeVale WSL stack to remove. Its default mode stops/removes the runtime and installer-owned Windows integrations while preserving `~/hermes-stack` for a later reinstall/recovery. **Full purge** permanently deletes that stack directory only after you type `PURGE`.

The uninstaller never unregisters the WSL distro. It also preserves shared/general prerequisites and applications that may predate LatticeVale or be used elsewhere, including Docker Engine/packages, native Windows Ollama, Windows Tailscale, Obsidian, Ubuntu Pro, and unrelated Windows firewall/tasks/settings. A separately selected Windows-backed Obsidian vault is outside `~/hermes-stack` and is never deleted by the purge.

For an intentionally **clean WSL/LatticeVale rebuild**, use `tools\Reset-LatticeVale-CleanHost.ps1` instead of making `installer\uninstall.ps1` more destructive. The clean-host reset is dry-run by default and, only when explicitly selected, can remove proven LatticeVale/legacy Foundry Windows integrations, unregister WSL distributions, remove global `.wslconfig*` state, uninstall the Store/MSI WSL app, and delete a verified LatticeVale source tree. It does not disable shared Hyper-V/VirtualMachinePlatform infrastructure or uninstall Tailscale/Obsidian. See `Instructions.txt` before using it.

## Repository layout

```text
installer/
  install.ps1                       Friendly verified install/repair entry point
  uninstall.ps1                     Verified conservative uninstall/purge entry point
  verify-release.ps1                Read-only source hash verifier
  SOURCE-SHA256SUMS.txt             Exact release-tree manifest
docs/
  README.md                         Complete project documentation
  SECURITY.md                       Security model and reporting
  SOURCES.md                        Official runtime download/source inventory
  RELEASE.md                        Maintainer release/audit checklist
  SUPPORT.md                        Public support/reporting guidance
  PATCH-NOTES.md                    Consolidated detailed v14.x patch/audit notes
  Instructions.txt                  Full setup + everyday-use guide
  Installer Description.txt         Concise project description
LICENSE                             MIT license for LatticeVale source
tools/New-SourceManifest.ps1        Deterministic release-manifest generator
tools/Reset-LatticeVale-CleanHost.ps1 Explicit dry-run-first clean WSL/LatticeVale host reset
LatticeVale-Core/
  Install-LatticeVale.ps1           Main Windows installer
  linux/bootstrap.sh                WSL bootstrap/recovery entry
  stack/configure-stack.sh          Stack configuration/reconciliation
  stack/compose.yaml                Docker Compose model
  stack/manage.sh                   Lifecycle/backup/verify/update tool
  stack/state-audit.py              Read-only state audit
  windows/LatticeVale-Shortcut.ps1 Inspectable Start/Shutdown shortcut launcher
  windows/LatticeVale-WindowsNativeServiceRelay.ps1 Optional WSL-only bridge to verified native Windows services
  tests/                             Regression/static fixtures
  AUDIT.md                             General audit/security invariants
  (CHANGELOG.md is canonical history; PATCH-NOTES.md preserves detailed v14.x implementation notes)
```

## Validation

The repository includes retained historical regression fixtures plus v14.3.9 secondary-Matrix manual-handoff coverage, v14.3.8 Matrix online-order/room-v10 coverage, and all earlier v14.3.x safety regressions, along with Bash syntax checks, Python compilation/static audit, Compose parsing, and a GitHub Actions workflow that parses every shipped PowerShell entry point with both Windows PowerShell 5.1 and PowerShell 7.

Container/static tests cannot honestly prove Windows Task Scheduler, a real WSL kernel, Windows Tailscale, and live Matrix clients end-to-end. Those boundaries are called out rather than silently treated as tested.

## Project status and attribution

LatticeVale is **unofficial** and is not affiliated with or endorsed by Nous Research, Microsoft, Tailscale, Matrix.org/The Matrix.org Foundation, Canonical, Obsidian, or other integrated projects. Product names are used descriptively for compatibility.

Third-party components retain their own licenses and security policies. **Honcho is upstream AGPL-3.0 software**; operators who modify Honcho and make that modified version available for users to interact with over a network should review AGPL-3.0 Section 13 and the upstream license. LatticeVale does not relicense Honcho. See `THIRD-PARTY-NOTICES.md` and the technical README under `LatticeVale-Core`.

## Historical patch notes

The original granular pre-LatticeVale v13 patch notes from the v13.16.6 bundle are preserved verbatim under `docs/legacy-patch-notes/hermes-wsl-foundry-v13/`. They are archival and may describe superseded behavior; use the current documentation for current LatticeVale behavior.

