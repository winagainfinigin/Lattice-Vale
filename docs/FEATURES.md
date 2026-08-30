# LatticeVale v14.5.2 — Complete Features and Install Options Reference

> **v14.5.2:** adds the isolated Option 7 cleanup/reclaim maintenance path and low-space Verify/Cleanup recovery gate while retaining v14.5.1 adaptive resource policy v9, live CPU/RAM convergence, low-memory viability guards, and running-container OOM detection unchanged. The normal mutating reconciliation architecture remains unchanged.

> **v14.4.85:** retains the v14.4.84 WSL lifecycle repair and adds startup-aware reconcile/post-gateway readiness, a bundle-owned Option 6 pre-update safety backup with root-scoped archive access for container-owned state, and an explicit Option 3 read-only verification report.


## v14.5.0 read-only architecture boundary

- `install-options.json` remains authoritative for installer-selected options.
- `.env`, generated Compose policy, and generated Hermes/service configuration remain derived runtime files.
- `compose.override.yaml` remains user-owned, applies after generated policy, and is intentionally treated as opaque by the v14.5.0 planner.
- `.installer-state.json` remains advisory checkpoint/history state.
- `checkpoint-metadata.json` exposes the existing checkpoint revision numbers/descriptions to read-only tooling; it does not introduce a parallel migration engine.
- `latticevale_readonly.py`, `repair-plan.py`, and `audit-free.py` are read-only WSL-side tools. They do not write configuration or apply repair.
- Mutating repair remains `Install-LatticeVale.ps1` → existing WSL bootstrap/configure/reconcile path.
- Windows-side code remains for Windows-only host responsibilities: WSL selection/recovery, shortcuts/Task Scheduler, Windows Tailscale integration, and optional native-Windows Ollama bridging.

## Purpose and source basis

This file consolidates the **current, available LatticeVale v14.5.2 capabilities and installer choices** scattered across the release documentation. The source basis was the complete audited v14.3.43 runtime release tree promoted to v14.4.0 without runtime behavior changes: 61 Markdown/text documentation files (28 current/release documents and 33 explicitly archival v13 documents), plus the current installer/configuration source used to resolve historical or ambiguous documentation.

Historical v13 notes are treated as compatibility lineage only. A feature is described here as current only when it is retained by the v14.5.2 documentation/source. Superseded behavior is called out separately rather than presented as an available current option.

---

# 1. What LatticeVale is

LatticeVale is a preservation-first Windows + WSL2 installer and lifecycle manager for a self-hosted Hermes Agent stack. It deploys into an **already existing, working Ubuntu WSL2 distribution** and manages selected Linux/Docker services plus narrowly scoped Windows integrations.

The normal installer does **not** create, import, move, unregister, convert, or replace a WSL distribution. A separate clean-host reset utility exists for administrators who deliberately want a destructive WSL/LatticeVale reset.

Core managed layers include:

- Hermes Agent
- Docker Engine / CLI / containerd / Buildx / Compose inside the selected Ubuntu distro
- generated configuration, secrets files, permissions, health checks, staged checkpoints, backup/verify/lifecycle tooling
- optional Hermes Dashboard
- optional named Hermes profiles
- optional Hermes Kanban orchestration
- optional Matrix/Synapse messaging
- optional Windows Tailscale private access
- optional SearXNG + Valkey
- optional QMD indexing/MCP
- optional Windows Obsidian integration
- optional Honcho persistent memory
- optional managed WSL/Docker Ollama or integration with separately installed native Windows Ollama
- optional adaptive per-container CPU/RAM ceilings
- optional unattended Ubuntu security updates
- optional supported WSL service-lifetime policy
- optional Windows logon auto-start
- optional per-install Windows Start / Shut Down shortcuts

---

# 2. Supported installation envelope

## Windows

- Windows 10 or Windows 11
- x64 / AMD64
- build 19041 or newer
- Administrator access
- Windows PowerShell 5.1 or PowerShell 7.x supported by the release entry points

## WSL / Ubuntu

LatticeVale requires WSL to already be installed and functional.

Supported distributed Ubuntu targets:

- Ubuntu 22.04 WSL2
- Ubuntu 24.04 WSL2
- Ubuntu 26.04 WSL2
- amd64 / x86_64 distro architecture
- normal non-root sudo user
- Linux home under `/home/...`

## Storage

For a fresh install, the Windows volume backing the selected WSL distro must satisfy the compatibility policy:

- **more than 50 GiB total capacity**, and
- **at least 50 GiB free**

Existing installer-managed repair has a lower managed-repair threshold when the installer explicitly accepts it (10 GiB free in the current compatibility policy).

## Other prerequisites

- Internet access for selected packages, images, models, authentication, and integrations
- native Windows Ollama must already be installed separately if that backend is selected
- supported GPU acceleration requires the relevant live WSL/container prerequisites; Windows GPU presence by itself is not sufficient

---

# 3. Fresh-install questionnaire — every current user-facing choice

Fresh installs use the **explicit questionnaire**. Suggested choices are guidance; host/system-affecting Y/N, menu, numeric and Tailscale-port questions require explicit input rather than silently accepting a suggestion.

## 3.1 Select the existing Ubuntu WSL2 distro

v14.4.81 additionally handles the bounded host-level case where an existing registered distro is visible to WSL but fails to cold-launch with `Wsl/Service/E_UNEXPECTED`. If that distro is needed or explicitly requested, LatticeVale can restart WSL and retry it in the same installer run; a persistent failure on explicitly mirrored networking can receive an explicit backed-up NAT compatibility fallback. The distro itself is never recreated or rewritten.

LatticeVale inventories registered WSL distributions and checks:

- WSL2 version
- ability to launch
- Ubuntu release compatibility
- architecture
- host backing volume/storage eligibility
- Linux filesystem state
- available non-root Linux users

If only one eligible distro exists, the installer still explicitly asks whether to use it.

**Normal installer behavior:** never creates, imports, unregisters, moves or converts a distro.

## 3.2 Select the existing Linux user

Choose the existing non-root sudo user that will own the LatticeVale stack.

The stack is installed under that user's actual Linux home, normally:

`~/hermes-stack`

LatticeVale does not invent a Linux user/home path.

## 3.3 Hermes Dashboard

**Prompt:** Install Hermes Dashboard?

- Suggested on fresh install: **Yes**
- Yes: enables the browser UI for profiles, chat, config, sessions and Kanban
- No: Hermes remains usable without the Dashboard
- Default local Dashboard port target: **9119**, with collision-aware allocation on fresh installs

## 3.4 Multiple Hermes profiles

**Prompt:** Create multiple Hermes profiles?

- Suggested: **Yes**
- No: only `default` is installer-managed
- Yes: create **1–8 additional profiles**

For every additional profile:

- name must be 1–32 characters
- lowercase letters, numbers, `_` and `-`
- first character must be alphanumeric
- name cannot be `default`
- name must be unique
- first fresh suggestion is `assistant`; later suggestions are `workerN`
- role description is user-supplied, maximum **240 characters**
- choose whether to clone the default provider/config or run independent Hermes provider/model setup for that profile

Named profiles are generic; LatticeVale does not require an `assistant`, `coder`, `researcher`, or other hard-coded secondary name.

## 3.5 Provider/model configuration

Hermes's provider setup remains the authority for provider/model credentials and choices.

For the default profile—and for named profiles that do not clone default config—the user can choose/configure the supported provider/model through Hermes setup.

LatticeVale preserves profile/provider settings on repair unless provider/profile reconfiguration is explicitly selected.

External provider availability, quota, authentication, region restrictions, pricing and deprecation remain outside LatticeVale's control.

## 3.6 Hermes Kanban

**Prompt:** Enable Hermes Kanban?

- Fresh suggestion: enabled when multi-profile mode is selected; otherwise disabled
- Existing cards are preserved when enablement/config changes

If enabled, choose:

### Global concurrency

- `max_in_progress`
- allowed range: **1–8**
- fresh suggestion: **2**

### Per-profile concurrency

- `max_in_progress_per_profile`
- allowed range: **1 through the selected global limit**
- fresh suggestion: **1**

Managed Kanban behavior includes:

- shared task board
- user-originated substantive/multi-step work can enter triage
- simple chat remains direct
- automatic decomposition
- automatic dispatch
- dependency-aware work
- creator-session wakeups/subscription behavior
- completed task results/attachments retention
- profile-aware routing
- real task-context requirements for worker lifecycle operations
- prevention/repair of literal fake `HERMES_KANBAN_TASK` placeholders when a real worker binding exists
- valid user-created profiles can remain routing targets without becoming installer-owned

Current managed defaults/policy include:

- dispatcher interval: **30 seconds**
- `auto_decompose: true`
- `auto_decompose_per_tick: 1`
- `auto_subscribe_on_create: true`
- gateway dispatch enabled
- review-dispatch behavior retained/initialized by managed policy
- orchestrator/default assignee preserved when valid, otherwise reconciled to valid installed profiles

The policy plugin is a correctness/context guard, **not a security sandbox**.

## 3.7 Agent-managed skill creation/writes

LatticeVale installs managed skill-authoring/recovery guidance for the default and installer-managed profiles.

Behavior includes:

- normalize human-facing names to valid skill slugs
- require complete/closed YAML frontmatter
- enforce current Hermes skill-description constraints
- view/load current skill state before patching when required
- treat validation errors as corrective data
- change strategy after repeated failures rather than repeating the same rejected operation
- verify successful writes
- keep Hermes tool-loop hard stops enabled

### Fresh skill-write approval behavior

For an installer-managed profile where the setting is absent, LatticeVale initializes:

`skills.write_approval: false`

Therefore fresh managed profiles can perform agent-managed skill writes **without a separate approval gate** unless the user changes that setting.

On repair/update/reconfigure, an explicit existing boolean choice is preserved.

Users who want a human approval boundary should explicitly enable Hermes skill-write approval.

## 3.8 Matrix / Synapse

**Prompt:** Install Matrix/Synapse?

- Fresh suggestion: **No**
- Installs a private self-hosted Matrix/Synapse service plus PostgreSQL
- local Synapse port target: **8008**, collision-aware on fresh install
- default Matrix identity remains `@hermes:hermes.local`
- managed rooms use encryption
- installer-managed room version is pinned/verified at **Matrix room version 10**

Managed Matrix state can include:

- Synapse configuration/database
- default Hermes bot identity
- bot token/device metadata
- stable E2EE state
- encrypted room
- allowlists
- reaction support
- sender-restricted approval/model-picker reactions
- recovery/cross-signing state

Current managed Matrix environment behavior includes:

- `MATRIX_REACTIONS=true`
- `MATRIX_APPROVAL_REQUIRE_SENDER=true`
- required E2EE topology for installer-managed rooms

### Named-profile Matrix identities

If Matrix and named profiles are enabled, each named profile can be given its own Matrix/Element bot and room.

Each selected Matrix-enabled named profile can receive:

- `@<profile>:hermes.local` account
- independent access token
- stable device ID
- E2EE/recovery state
- room/user allowlists
- its own encrypted room, or an explicitly adopted existing encrypted room when allowed
- its own independently supervised Hermes gateway

Profile Matrix routing follows the **actual profile name and verified model**, not a hard-coded `assistant` profile.

Existing unknown/manual Matrix identities are preserved unless installer ownership is proven.

Secondary profile activation can remain a protected `pending-manual` state and later be completed with:

`./manage.sh matrix-profile-finish <profile>`

Pending activation alone is not grounds to rebuild a valid identity.

## 3.9 Windows Tailscale private remote access

**Prompt:** Use Windows Tailscale for private remote access?

- Fresh suggestion: **No**
- Tailscale remains **Windows-native**, not a WSL/Docker service
- LatticeVale reuses a working Windows Tailscale installation when found

If Tailscale is requested but not installed:

**Prompt:** Install Tailscale for Windows if needed?

- suggested: Yes in that conditional path
- acquisition uses the official Windows client path with verification/fallback policy described in `SOURCES.md`
- if user declines, LatticeVale remote exposure is disabled and local stack installation continues

If Tailscale is installed but offline/unauthed, LatticeVale can explicitly offer normal login / `tailscale up` handling.

### Dashboard through Tailscale

Available only when Dashboard and Tailscale are selected.

- expose Dashboard privately through Windows Tailscale: Yes/No
- fresh suggestion: **No**
- suggested HTTPS port: **9443**
- user can select another valid TCP port

### Matrix through Tailscale

Available only when Matrix and Tailscale are selected.

- expose Matrix privately through Windows Tailscale: Yes/No
- fresh suggestion: **No**
- suggested HTTPS port: **443**
- user can select another valid TCP port distinct from another selected Serve listener

LatticeVale uses **Tailscale Serve**, not public Funnel.

Windows loopback relay ports normally target:

- Dashboard bridge: **19119**
- Matrix bridge: **18008**

Fresh allocation reclaims only proven stale LatticeVale-owned bridge state and otherwise uses a safe available port rather than killing an unknown listener.

Existing Tailscale rules are preserved unless they are proven matching/owned or the user explicitly accepts adoption/replacement of the exact conflicting Serve listener.

Tailnet ACLs/grants/tags/device policy remain the user's responsibility.

## 3.10 SearXNG + Valkey

**Prompt:** Install SearXNG + Valkey?

- Fresh suggestion: **Yes**
- installs self-hosted SearXNG plus Valkey
- Hermes managed web configuration switches its search backend to SearXNG when selected
- v14.4.7 pairs that search backend with the keyless `latticevale-local` public-page extractor unless an explicit extraction/shared provider is already configured
- fresh and repair-managed profiles use Hermes Local Browser / Chromium only when no explicit browser backend/provider, gateway route, or recognized browser environment selection already owns that choice
- a missing `auxiliary.web_extract.timeout` is filled with `360`; an explicit timeout is preserved
- these are installer/runtime defaults only; LatticeVale does not manage `SOUL.md`, prompts, or model policy
- local port target: **8888**, collision-aware on fresh install
- upstream engine availability remains external: a locally healthy SearXNG request can occasionally return zero usable results when search engines rate-limit, CAPTCHA, or suspend automated traffic
- a zero-result search alone is therefore not proof that LatticeVale, Hermes, SearXNG, or Valkey is broken; known public URLs can still be read independently through `web_extract`
- removing/disabling the feature removes the managed active service selection while preserving appropriate persistent state

## 3.11 QMD

**Prompt:** Install QMD?

- Fresh suggestion: **No**
- installs QMD plus its indexer service
- exposes local Markdown/note retrieval to Hermes through MCP
- managed Hermes MCP endpoint: `http://qmd:8181/mcp`
- current managed MCP timeout: 30 seconds
- built-in QMD indexing default: **7200 seconds / 2 hours**
- an explicit user-set non-default QMD index interval is preserved
- legacy duplicate `HERMES_QMD_REINDEX` cron guidance is removed by current reconciliation

QMD can operate without Windows Obsidian by using the Linux stack vault manually.

## 3.12 Windows Obsidian integration

**Prompt:** Install/configure Obsidian for Windows?

- fresh suggestion follows QMD selection: suggested Yes when QMD is selected, otherwise No
- Obsidian can be installed through WinGet using exact package ID `Obsidian.Obsidian`
- if WinGet is unavailable or install fails, the Linux stack can still complete with the Windows add-on marked partial

If Obsidian is selected, the installer requires an explicit **Windows-local drive path** for the vault.

Accepted design:

- normal Windows local drive path such as `D:\Documents\Obsidian Vault`
- converted through the selected distro's actual Windows-drive mount root
- verified as Windows-backed storage
- mounted into Hermes/QMD as `/vault`

Not accepted for the managed vault path:

- `\\wsl.localhost\...`
- `\\wsl$\...`
- SMB/UNC/network paths

The vault is treated as user data and is preserved by normal uninstall/purge semantics described by the release.

## 3.13 Honcho persistent memory

**Prompt:** Install fully self-hosted Honcho memory?

- Fresh suggestion: **No**
- adds a persistent memory layer to Hermes
- managed Hermes memory provider is set to Honcho when selected
- local Honcho health/API port target: **8000**, collision-aware on fresh install

Honcho selection adds:

- Honcho API
- Honcho deriver
- PostgreSQL/pgvector database
- Redis
- local LLM path through the selected Ollama backend
- local embedding model path

Honcho persistent state is preservation-first across normal repair/update.

The current stack uses 1536-dimensional vectors for the managed embedding configuration.

Honcho is upstream AGPL-3.0 software and retains its upstream license obligations.

## 3.14 Use Ollama as the default Hermes AI provider

**Prompt:** Use Ollama as the default Hermes AI provider?

- Fresh suggestion: **Yes**
- Yes: Hermes default profile is configured around the selected local Ollama backend/model path
- No: Hermes retains upstream interactive provider setup for an external/other provider

Ollama configuration is also required when Honcho is selected, even if Ollama is not the main Hermes provider.

## 3.15 Ollama backend ownership

When Honcho or Hermes local AI is enabled, the installer explicitly asks where Ollama should run.

### Option A — native Windows Ollama

Native Windows Ollama:

- must already be installed separately
- is not installed or updated by LatticeVale
- remains Windows-owned
- must have a working Windows-local API
- must have a safe WSL access/relay path verified before LatticeVale accepts it
- can be explicitly started/rechecked by setup if installed but stopped
- can have missing selected models pulled through its native API
- keeps models in the Windows Ollama model store
- owns its own Windows GPU/CPU backend selection

The preferred integration uses narrowly scoped/private relay paths. Current normal installer flows do **not** set or switch WSL `networkingMode`.

If safer private/localhost paths cannot verify, an explicit direct-WSL fallback can be offered with narrowly scoped firewall/bind handling. LatticeVale does not silently switch to the managed backend.

### Option B — LatticeVale-managed WSL/Docker Ollama

LatticeVale can:

- deploy the managed Ollama container
- store models inside the selected WSL distro
- pull selected models
- configure/verify selected acceleration policy
- integrate it with Hermes and/or Honcho

### Backend suggestion

The suggestion is capability/state-aware:

- safely verified native Windows Ollama may be suggested when available
- otherwise managed WSL/Docker Ollama is suggested
- user selection remains explicit

## 3.16 Local Ollama text model

Shown when Honcho or Hermes local Ollama is selected.

- fresh suggestion: `qwen3.5:4b`
- user can enter another valid Ollama model/tag
- missing selected models are pulled through the selected backend when supported

## 3.17 Honcho embedding model

Shown when Honcho is selected.

- fresh suggestion: `qwen3-embedding:4b`
- expected to support the stack's 1536-dimensional embedding configuration
- user can enter another syntactically valid model/tag, subject to later capability validation

## 3.18 Managed Ollama acceleration

Shown only for the managed WSL/Docker Ollama backend.

Choices:

1. **Auto-detect supported acceleration; CPU fallback** — fresh suggestion
2. **CPU only**
3. **NVIDIA GPU**
4. **AMD GPU via ROCm**

### NVIDIA gate

A forced NVIDIA selection is accepted only after the selected WSL distro verifies the required NVIDIA WSL path, including `/dev/dxg` and working `nvidia-smi`. LatticeVale may configure the tested NVIDIA Container Toolkit package set when needed.

### AMD/ROCm gate

The distributed Docker Ollama AMD path requires:

- x86_64
- `/dev/kfd`
- `/dev/dri`

`/dev/dxg` alone is not treated as AMD/ROCm container readiness.

### Auto

Auto uses a supported accelerator only after its live prerequisites pass; otherwise it falls back to CPU.

Saved forced modes that become invalid after hardware/driver changes are reconciled explicitly during repair rather than silently accepted.

## 3.19 Adaptive per-container CPU/RAM ceilings

**Prompt:** Apply adaptive CPU/RAM ceilings to LatticeVale containers?

- Fresh suggestion: **Yes**

When enabled LatticeVale:

- measures CPU/RAM actually visible inside WSL
- reserves WSL/Docker/Windows-facing headroom with larger reserves on smaller WSL VMs
- computes a safe managed container memory budget
- assigns ceilings only to enabled services
- applies conservative allocator tuning (`MALLOC_ARENA_MAX`) to long-lived glibc/Python services
- scales Synapse's supported `SYNAPSE_CACHE_FACTOR` down on constrained WSL VMs
- uses 64 MiB PostgreSQL `shared_buffers` on <=12 GiB WSL VMs and 128 MiB above that, while retaining Honcho PostgreSQL `max_connections=200`
- recalculates when relevant WSL-visible resources change or an older adaptive-policy revision must be migrated

Current policy v9 retains a bounded host-headroom schedule while addressing both observed failures: policy-v4 Hermes starvation and policy-v6 CPU-backed Ollama `memory.max` pressure. It additionally makes the Hermes share topology-aware for public multi-profile/Kanban configurations. It reserves 30% of WSL-visible RAM on <=6 GiB; on >6-12 GiB it uses 10% when CPU-backed managed Ollama is selected and 20% otherwise; >12-24 GiB uses 20%; and >24 GiB uses 15%, with bounded minimum/maximum reserve values. Policy v9 gives Hermes a 1024 MiB common-topology minimum, Honcho API 512 MiB, and CPU-backed managed Ollama a 4608 MiB provisional floor before model artifacts are measurable, then a model/context-aware floor after download. The 1024 MiB Hermes baseline covers the default gateway plus up to one secondary Matrix gateway and Kanban concurrency up to 3; each additional persistent secondary Matrix gateway adds 192 MiB and each Kanban slot above 3 adds 96 MiB, capped at 4096 MiB. Hermes CPU normally uses about 75% of WSL-visible CPUs but gains bounded ceiling headroom toward 100% as that topology pressure increases. The minimum calculation is service-aware: lighter selections can fit smaller WSL allocations, but if the selected set cannot meet its defined hard minima, policy v9 refuses to generate the overlay instead of proportionally crushing every service. These are **ceilings, not reservations**, and are not a global WSL memory cap.

Clean installs generate policy v9 before first container creation and verify the resulting live Docker CPU and memory ceilings. The resource fingerprint includes Matrix-enabled secondary gateway count, Kanban concurrency, and the derived Hermes topology floor. The generated root/Windows-start helper evaluates current CPU, RAM, enabled-limit state, profile topology, and Kanban concurrency at helper runtime so auto-start paths do not retain an install-time resource snapshot. Resume / repair and managed start-time resource reconciliation migrate enabled older policies, and final reconciliation compares effective merged Compose `mem_limit` and `cpus` with each selected container's live Docker `HostConfig.Memory` and `HostConfig.NanoCpus`. A running selected container with Docker `OOMKilled=true` is reported as a repairable runtime-policy degradation rather than accepted as healthy.

LatticeVale does not set global WSL `memory` or `autoMemoryReclaim` for this feature. Those are host/user-owned WSL policies. A user `compose.override.yaml` is applied last and remains authoritative; live-limit verification therefore checks the effective merged Compose value rather than blindly enforcing the generated base value.

## 3.21 Unattended Ubuntu security updates

**Prompt:** Enable unattended Ubuntu security updates?

- Fresh suggestion: **Yes**
- configures managed unattended eligible Ubuntu security updates
- No leaves Ubuntu updates manual

LatticeVale's own controlled updater is separate from general Ubuntu unattended security updates.

## 3.22 WSL service lifetime policy

Available only when the installed Store/MSIX WSL version supports the managed policy (current code checks the supported WSL 2.5.4+ path).

**Prompt:** Prevent WSL from auto-shutting down this running server instance?

When enabled:

- manages `[general] instanceIdleTimeout=-1`
- is a WSL service-instance lifetime policy
- is not a fake keepalive loop
- is not Windows logon auto-start
- does not itself start the stack

The fresh suggestion is context-sensitive (notably whether persistent Matrix/Tailscale service availability was selected).

This is one of the limited global `.wslconfig`-related policies; current LatticeVale does **not** use it to set WSL networking mode.

## 3.23 Windows logon auto-start

**Prompt:** Start the stack automatically at Windows logon?

- Fresh suggestion: **No**
- creates an installer-owned scheduled task when enabled
- starts the selected distro/stack after sign-in through the managed startup path

The small Windows relay used for selected integrations is separate and is designed not to wake WSL unless full-stack auto-start is enabled.

## 3.24 Windows Start / Shut Down desktop shortcuts

**Prompt:** Create Windows desktop shortcuts to start and shut down this LatticeVale install?

- Fresh suggestion: **No**
- shortcuts are bound to the exact selected distro, Linux user and stack

### Start LatticeVale

- launches the selected distro
- ensures Docker availability
- runs managed stack startup according to saved install options

### Shut Down LatticeVale

- stops the selected LatticeVale services and managed relay
- intentionally leaves the selected WSL distro running
- never uses targeted `wsl --terminate`
- does not use global `wsl --shutdown`

Non-LatticeVale same-name shortcuts are not overwritten/removed without ownership proof.

## 3.25 Container timezone

The installer detects the Ubuntu timezone when possible.

- user can accept a detected/saved value
- otherwise an explicit IANA timezone name is required
- examples: `America/Los_Angeles`, `Europe/London`

Timezone is persisted as part of the managed installation intent.

## 3.26 Final confirmation

Before package/stack changes begin, the installer presents the selected distro/storage/component configuration and requires an explicit **Proceed with installation?** confirmation.

---

# 4. Conditional safety/ownership prompts

In addition to the normal questionnaire, LatticeVale can ask conditional questions when real existing state requires a decision.

These include:

- confirm the only eligible WSL distro
- confirm the only eligible Linux user
- allow replacement of conflicting distro-provided Docker/containerd packages while preserving Docker data directories
- reuse an existing unrecognized `~/hermes-stack` after preservation safeguards
- detach an exact legacy vault symlink without deleting its source
- detach an exact legacy installer-owned vault mount with fstab backup/preservation
- start/recover an already-installed native Windows Ollama so its API can be rechecked
- choose how repair should handle an unavailable previously selected native Ollama backend
- change an unavailable saved GPU acceleration mode
- adopt an existing exact-matching Tailscale Serve listener
- explicitly replace only an exact conflicting Tailscale Serve listener
- sign into/bring up an existing Windows Tailscale client
- make supported global WSL service-lifetime changes with global-impact awareness

These prompts are intended to prevent LatticeVale from silently taking ownership of unrelated state.

---

# 5. Existing-install menu — all seven modes

Lifecycle shortcuts in v14.4.84 invoke `./manage.sh start|stop` directly with WSL `--cd`; repair treats older/broken shortcut runtime contracts as drift and rewrites them. Before using **Resume / repair installation** or **Update / repair installer-managed software**, use **Shut Down LatticeVale** to stop the managed stack if the shortcut is available. Do not use targeted `wsl --terminate`. If v14.4.84 detects the installer-owned legacy targeted-termination helper, the repair run performs its own bounded global WSL shutdown + `WslService` transport reset before replacing the helper.

When a recognized installer-managed stack exists, LatticeVale offers seven top-level modes.

## 5.1 Resume / repair installation

Recommended for interrupted, incomplete, stale or unhealthy managed installations.

Behavior:

- reuses saved choices
- audits live state
- repairs/reconciles failed, incomplete or stale stages
- preserves persistent application/user data
- can apply required managed integration-policy migrations
- explicitly reconciles stale/missing adaptive runtime/RAM policy and applies changed Compose settings to live containers
- refreshes installer-owned package/image/source state when the 30-day gate is due, the managed-refresh policy revision changes, legacy refresh state is missing, or explicit Update / repair forces it
- performs the targeted periodic managed refresh when the 30-day gate is due or the refresh-policy revision changes
- does not blindly rerun unrelated healthy stages just because the installer version changed

Current periodic managed refresh window: **30 days**. `MANAGED_REPAIR_REFRESH_REVISION` is the explicit compatibility trigger for a release that requires immediate managed package/image/source convergence. A bundle-version change alone does not force a refresh.

Resume/repair is preservation-first but is not guaranteed to be update-free: it performs bounded installer-owned component refresh when the age/revision/legacy-state trigger applies, while preserving explicit user-owned overrides. Option 6 forces the current bundle's managed refresh immediately.

## 5.2 Change installed components

Keeps the existing stack and saved unselected settings while allowing selected scopes to change.

The exact change categories are:

1. **Optional components** — Dashboard, SearXNG, QMD, Obsidian
2. **Kanban** — enablement and concurrency limits
3. **Matrix + Tailscale** — Matrix service and Windows Tailscale exposure
4. **Local AI** — Honcho / Ollama backend / models
5. **Runtime/Windows policy** — adaptive container limits, updates, WSL lifetime, auto-start, shortcuts, timezone
6. **All categories**

Important preservation behavior:

- existing profiles are not recreated/renamed merely because another component changes
- provider credentials are preserved unless explicitly reconfigured
- Matrix identities/rooms are preserved when not explicitly targeted
- unselected ports/paths/settings are retained
- disabling a component does not deliberately delete its persistent data

## 5.3 Verify installation only

Read-only persistent-install audit.

- audits Linux/stack state
- live-audits relevant Windows integration state
- exits before normal mutating staging/bootstrap work
- makes no persistent stack/config changes

## 5.4 Reconfigure providers/profiles

Reruns the relevant Hermes provider/model/profile setup while retaining service/data selections. It intentionally operates within the saved component policy. If the default profile is selected for LatticeVale local Ollama, this option reapplies that local-AI default; use **Change installed components -> Local AI / Honcho / Ollama** to switch the default profile away from installer-owned Ollama.

Use for:

- provider authentication/model changes within the saved provider policy
- profile provider/model reconfiguration
- repairing provider/profile setup without rebuilding unrelated services

## 5.5 Advanced recovery

Exact actions:

1. **Reset installer checkpoints and re-verify/reconcile every stage** — persistent data preserved
2. **Rebuild only installer-owned Matrix bot/room identity** — narrow identity recovery path
3. **Rerun provider/profile setup and reset checkpoints**
4. **Return to read-only verification and exit**

Identity-changing Matrix recovery is intentionally narrow and uses preservation/backups for installer-owned state rather than deleting unknown/manual Matrix state. It requires shared Matrix to be enabled. The rebuild is transactional: the existing human Matrix admin and all secondary-profile identities/rooms are preserved, the current default-bot credentials and default Matrix crypto store are copied to a private recovery directory, a unique replacement default bot/device bootstrap is persisted, and only then are old installer-owned default runtime identity files retired. The replacement identity starts with a fresh crypto store; ordinary Resume / repair does not rotate or delete the existing Matrix identity/store.

## 5.6 Update / repair installer-managed software

Controlled, on-demand bundle-aligned updater.

Before refresh:

- the **bundle-owned pre-update safety backup** must succeed
- it runs independently of the currently installed `manage.sh`, so an outdated/broken management script cannot block its own repair
- the backup transaction runs as WSL root only while required to read container-owned persistent files, validates PostgreSQL dumps/archive output, restores the previously-running containers, and returns backup ownership to the selected Linux user

Then it forces the software versions/channels declared by the currently running LatticeVale bundle and continues through normal repair/verifiers.

Managed update scope can include:

- LatticeVale prerequisite packages
- Docker Engine/CLI/containerd/Buildx/Compose packages
- selected installer-managed Compose images
- Hermes image pin
- Matrix/Synapse image pin
- SearXNG managed pin
- managed Ollama pin
- QMD bundle-declared build version
- audited installer-owned Honcho source commit
- selected supporting image/source references

Preserved:

- Matrix/Synapse/Honcho databases
- Matrix crypto/E2EE state
- Hermes profiles, memory and sessions
- credentials
- Ollama models
- vault/workspace data
- explicit custom image/source overrides
- separately owned native Windows Ollama


## 5.7 Cleanup / reclaim disk space

Install-preserving, user-selected storage maintenance for a recognized managed stack. Cleanup is intentionally **not** part of automatic Resume / repair and exits immediately after the selected cleanup work.

The user may choose one, several, or **ALL** of these bounded categories before a final confirmation:

1. verified Option 6 `pre-update-*` backups whose metadata proves they belong to the current stack;
2. stale root-owned LatticeVale installer/audit staging plus incomplete pre-update `.partial` residue;
3. downloaded APT package archives only (`apt-get clean`);
4. Docker dangling images only (`docker image prune -f`; no `-a`);
5. Docker dangling default-builder cache only (`docker builder prune -f`; no `-a`/`--all`);
6. WSL root-filesystem TRIM (`fstrim -v /`) where supported.

Safety invariants are enforced both by the installer and the bundle-owned cleanup helper. The helper revalidates the managed stack before deletion. Option 7 does **not** stop/remove containers, prune networks/volumes, remove tagged images, remove configured models, touch Hermes/Matrix/Honcho/QMD databases/state, delete vault/workspace/credentials, delete unverified/user-created backups, or manipulate the WSL VHDX. The Docker daemon may be shared, so broad engine-global pruning commands such as `docker system prune` remain excluded.

Before any cleanup command runs, the helper snapshots protected installation identities. After cleanup it requires those pre-existing identities to remain present before reporting success: installer/config hashes, persistent LatticeVale roots, user/unverified backup entries, pre-existing Ollama model manifests, and—when Docker was available before cleanup—container, volume, network, and tagged-image identities. Mutable database/log contents are not hashed, so ordinary runtime writes do not create false failures.

A recognized managed installation that is below the ordinary managed-repair free-space requirement may still enter Option 3 Verify or Option 7 Cleanup. Options 1/2/4/5/6 remain storage-gated until enough host-partition space is available. A fresh or unrecognized stack cannot use that exception.

TRIM advertises already-freed filesystem blocks to the virtual-disk layer but is not treated as a promise that the Windows-visible VHDX file length will shrink immediately. The reported TRIM quantity is labeled as a logical discard range, not Windows host-partition space reclaimed. Windows-side VHDX compaction/move/resize remains outside Option 7.

---

# 6. Advanced management after installation

From `~/hermes-stack`, current documented management commands include:

- `./manage.sh start`
- `./manage.sh stop`
- `./manage.sh restart`
- `./manage.sh status`
- `./manage.sh verify`
- `./manage.sh audit`
- `./manage.sh plan [--offline]` — v14.5+ read-only repair plan
- `./manage.sh repair --plan [--offline]` — alias for the read-only plan; applying repair still uses the Windows installer
- `./manage.sh audit-free` — advisory free/local-path audit
- `./manage.sh profiles`
- `./manage.sh matrix-info`
- `./manage.sh matrix-profile-finish <profile>`
- `./manage.sh backup`
- `./manage.sh update` — advanced upstream refresh, distinct from controlled Windows Update/repair

Status/verify can report:

- configured image pins
- LatticeVale pin date/age as an offline visibility signal
- hardware/resource context
- GPU VRAM evidence when measurable
- model-fit advisory information
- loaded-model `ollama ps` evidence for managed Ollama when available

Backups are permission-restricted but may contain credentials/recovery material and should be protected as sensitive data.

---

# 7. Current Docker/Compose service inventory

The current Compose definition contains **12 services**:

1. `hermes`
2. `synapse-db`
3. `synapse`
4. `searxng-valkey`
5. `searxng`
6. `qmd`
7. `qmd-indexer`
8. `ollama`
9. `honcho-db`
10. `honcho-redis`
11. `honcho-api`
12. `honcho-deriver`

Services are activated according to selected Compose profiles/options; selecting every optional feature does not mean every service is mandatory for a minimal Hermes installation.

---

# 8. Current managed software/source pins documented by v14.5.2

The release's declared managed references include:

- Hermes Agent image: `nousresearch/hermes-agent:v2026.8.16`
- Matrix Synapse: `matrixdotorg/synapse:v1.158.0`
- Synapse PostgreSQL: PostgreSQL 16 Alpine line
- SearXNG managed release: `2026.8.17-374939b88`
- Valkey: 8 Alpine line
- QMD: `2.5.3`
- managed Ollama: `0.32.14` / corresponding ROCm image path when selected
- Honcho: pinned audited commit `444897975c95393b0d48024470ece03c025d3aa4`
- Honcho pgvector PostgreSQL image line: pg15-based
- Honcho Redis: Redis 8 Alpine line
- optional NVIDIA Container Toolkit tested package set: `1.20.0-1`
- fresh local Ollama text-model suggestion: `qwen3.5:4b`
- Honcho embedding-model suggestion: `qwen3-embedding:4b`

Exact current supply-chain references are maintained in `SOURCES.md`; this section is a feature reference, not a replacement for that source-policy file.

---

# 9. Default local ports and exposure behavior

Fresh local ports are collision-aware. Canonical starting ports are:

| Service / bridge | Canonical port |
|---|---:|
| Hermes API | 8642 |
| Dashboard | 9119 |
| Matrix/Synapse | 8008 |
| SearXNG | 8888 |
| Honcho API | 8000 |
| Windows Dashboard bridge | 19119 |
| Windows Matrix bridge | 18008 |
| Native Windows Ollama relay | 11435 |
| Tailscale Dashboard HTTPS suggestion | 9443 |
| Tailscale Matrix HTTPS suggestion | 443 |

Existing managed ports are preserved when possible. Unknown foreign listeners are not killed merely to reclaim a canonical port.

Host-published local services are intended to remain on loopback unless an explicitly selected private integration exposes them.

---

# 10. Windows-side integrations LatticeVale can install/manage

Depending on user choices, LatticeVale can manage:

- Windows Tailscale client installation/reuse
- exact Tailscale Serve listeners for selected services
- Windows native-service relays scoped to LatticeVale
- installer-owned Windows firewall / Hyper-V firewall rules for verified native-service paths
- Windows Obsidian installation through WinGet
- Windows-local Obsidian vault path integration
- Windows-logon LatticeVale startup task
- passive relay startup task when required by selected Windows integrations
- current-user Start / Shut Down desktop shortcuts
- limited supported global `.wslconfig` lifetime policy

Current normal configuration flows **do not set or switch `[wsl2] networkingMode`**. The narrow v14.4.81 launch-recovery path may invoke the explicit host-repair helper to change only mirrored→NAT after `E_UNEXPECTED` survives a clean WSL restart and the user separately approves that backed-up compatibility action.

---

# 11. WSL networking behavior

Current v14.4.85 policy:

- discover active topology
- preserve working NAT/default/VirtioProxy-capable paths
- use dynamic/scoped relay discovery where required
- if the user/host already has healthy mirrored networking, consume it non-mutatingly as externally owned
- never create or switch global `networkingMode=mirrored` from normal install, repair, Change, Reconfigure, Advanced recovery or Update/repair

The explicit host-repair helper is separate. For the exact `E_UNEXPECTED` + mirrored condition, it can optionally:

- back up `.wslconfig`
- change only networking mode to NAT
- `wsl --shutdown`
- retest the same distro
- retain the backup and escalate diagnostics if recovery fails

This is a narrowly scoped preflight recovery path, not a general stack/networking configuration feature. Deeper host repair remains separate.

---

# 12. Repair/maintenance features

Current managed repair can perform bounded maintenance while preserving user/application state.

Current behavior includes:

- storage/stack/Docker usage reporting
- cleanup of installer-owned staging/log/config-backup residue within documented bounds
- retention control for installer-generated snapshots/history
- bounded PostgreSQL `VACUUM (ANALYZE)` where applicable
- service/config/ownership reconciliation
- managed package/image/source refresh when due

Current repair specifically **does not** perform engine-global Docker image/build-cache pruning introduced in an older historical release. v14.3.39 removed that behavior to avoid touching unrelated Docker projects sharing the same engine.

Repair does not deliberately delete:

- Hermes profiles/memory/sessions
- Matrix/Synapse/Postgres data
- Matrix E2EE/crypto state
- Honcho memory
- QMD data/source notes
- Ollama models
- vault/workspace files
- credentials
- user-created backups
- unrelated Docker projects

---

# 13. Normal uninstall

`installer\Uninstall-LatticeVale.ps1` is intentionally conservative.

It can:

- stop/remove LatticeVale runtime state
- remove installer-owned Windows integrations
- optionally perform a full stack-directory purge after explicit `PURGE` confirmation

Before removing Windows integration state, v14.4.5 requires Docker runtime cleanup to be inspectable when stack metadata indicates runtime may still exist. If Docker is unavailable in that case, uninstall stops rather than performing a partial removal.

Ownership failures are preservation boundaries: a same-name task/shortcut that no longer proves LatticeVale ownership is left untouched, and helper/config files still referenced by retained tasks/shortcuts are also preserved. Installer-owned direct-Ollama `OLLAMA_HOST` restoration broadcasts the Windows environment change.

By default/policy it preserves shared prerequisites and externally/user-owned applications such as:

- WSL distro registration
- Docker Engine/packages
- native Windows Ollama
- Windows Tailscale
- Obsidian
- unrelated Windows firewall/tasks/settings

A separately selected Windows-backed Obsidian vault is outside `~/hermes-stack` and is not deleted by stack purge.

Normal uninstall does **not** unregister WSL.

---

# 14. Intentional clean-host reset

`tools\Reset-LatticeVale-CleanHost.ps1` is deliberately separate from normal uninstall.

Safety model:

- Administrator required
- dry-run by default
- prints `WOULD:` operations
- destructive execution requires `-Execute`
- exact `CLEAN-RESET` confirmation required
- v14.3.43 safely handles heterogeneous Windows Scheduled Task action types during ownership scanning

Optional clean-reset scopes include:

- proven LatticeVale Windows tasks/helpers/firewall/shortcut/PATH state
- explicitly selected legacy pre-LatticeVale Foundry cleanup
- disabling only Tailscale Serve listeners still proven to target known LatticeVale bridge backends
- `-RemoveWslRuntime`: **all WSL distributions registered to the current Windows user**, their former registered distro storage, `.wslconfig*`, and attempted Store/MSI Microsoft.WSL application removal
- `-DeleteLatticeValeSource` with an explicitly supplied verified source-tree path

The reset deliberately does **not** disable/remove:

- Hyper-V
- HypervisorPlatform
- VirtualMachinePlatform
- HNS infrastructure
- Windows Tailscale application
- Obsidian application merely because LatticeVale used it
- unrelated firewall/HNS state
- standalone `%USERPROFILE%\.hermes`

This utility is for an intentional fresh Windows-WSL/LatticeVale baseline, not ordinary repair.

---

# 15. Security and ownership features

LatticeVale's current design emphasizes ownership proof and preservation:

- source manifest verification before normal entry points
- readable/plain-text installer source
- PowerShell source encoding policy for Windows PowerShell 5.1 compatibility
- restrictive permissions for generated secrets/backup state
- loopback-first host publishing
- no normal public Tailscale Funnel exposure
- narrow adoption/replacement prompts for pre-existing Tailscale Serve listeners
- no arbitrary user-created profile config takeover
- no automatic unknown/manual Matrix identity deletion
- no engine-global Docker prune during automatic repair
- no normal global WSL networking-mode mutation
- exact per-install Windows task/shortcut/relay ownership checks
- tool-loop hard stops retained
- Kanban context guard treated as correctness—not authorization/security
- user `compose.override.yaml` remains authoritative and is considered user-owned

Users remain responsible for provider keys, Matrix recovery/client trust, Tailscale ACLs/grants, profile tool permissions, approval settings, and the sensitivity of content exposed to agents/QMD/Honcho.

---

# 16. Features intentionally not provided by normal installation

Normal LatticeVale does not:

- install WSL itself
- create/import/move/unregister/convert WSL distros
- directly edit/compact/convert a WSL VHDX
- install or update native Windows Ollama
- choose external provider entitlement/region/quota for the user
- configure the user's tailnet ACL/grant policy
- make Kanban or agent tools a security sandbox
- delete unknown/manual Matrix state to make repair easier
- overwrite arbitrary user-created Hermes profile config
- run blanket Ubuntu upgrades as part of managed repair
- run engine-global Docker system/image/volume cleanup as automatic repair
- force mirrored WSL networking
- silently select a different Ollama backend when the chosen backend cannot verify

---

# 17. Documentation lineage / superseded historical behaviors

The retained v13 patch notes document how current behavior evolved. They are not current operator instructions.

Examples of superseded behavior that should **not** be interpreted as current features:

- historical automatic Docker dangling-image/build-cache pruning during repair — removed from automatic repair by v14.3.39
- historical explicit mirrored-network fallback that could write `networkingMode=mirrored` — removed from normal installer flows by v14.3.41
- historical guessed/default Obsidian vault locations — current fresh install requires an explicit Windows-local vault path when Obsidian is selected
- historical Quick Setup defaults for host/system-affecting choices — current fresh install uses explicit questionnaire semantics

Current primary documentation and current source take precedence over archived v13 notes.

---

# 18. Documentation files reviewed for this consolidation

## Current documentation set after v14.4.8 consolidation (retained by v14.4.85)

The v14.4.0 audit originally reviewed a larger set of one-off patch-note files. Those v14.x detailed notes are now preserved in `docs/PATCH-NOTES.md`; `docs/CHANGELOG.md` remains canonical for version history. Current user/maintainer documentation is intentionally split by purpose rather than by individual patch.

- repository-root `README.md`
- `docs/README.md`
- `docs/FEATURES.md`
- `docs/Instructions.txt`
- `docs/Installer Description.txt`
- `docs/SUPPORT.md`
- `docs/SECURITY.md`
- `docs/SOURCES.md`
- `docs/THIRD-PARTY-NOTICES.md`
- `docs/CHANGELOG.md`
- `docs/PATCH-NOTES.md`
- `docs/RELEASE.md`
- `docs/CONTRIBUTING.md`
- `docs/NATIVE-OLLAMA-INTEGRATION.md`
- `docs/WINDOWS-INTEGRATION-TEST-MATRIX.md`
- `LatticeVale-Core/README.md`
- `LatticeVale-Core/AUDIT.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

## Explicitly archival v13 documentation (33)

Every file under `docs/legacy-patch-notes/hermes-wsl-foundry-v13/` was included in the audit as historical/compatibility lineage:

- `HOTFIX-v13.1.md`
- `HOTFIX-v13.2.md`
- `HOTFIX-v13.3.md`
- `HOTFIX-v13.4.md`
- `HOTFIX-v13.5.md`
- `HOTFIX-v13.6.md`
- `HOTFIX-v13.7.md`
- `HOTFIX-v13.8.md`
- `HOTFIX-v13.9.md`
- `HOTFIX-v13.10.md`
- `HOTFIX-v13.11.md`
- `HOTFIX-v13.11-RC7.md`
- `HOTFIX-v13.12.md`
- `HOTFIX-v13.12.1.md`
- `HOTFIX-v13.12.2.md`
- `HOTFIX-v13.12.3.md`
- `HOTFIX-v13.12.4.md`
- `HOTFIX-v13.13.0.md`
- `HOTFIX-v13.13.1.md`
- `HOTFIX-v13.13.2.md`
- `HOTFIX-v13.13.3.md`
- `HOTFIX-v13.13.4.md`
- `HOTFIX-v13.14.0.md`
- `HOTFIX-v13.15.0.md`
- `HOTFIX-v13.16.0.md`
- `HOTFIX-v13.16.1.md`
- `HOTFIX-v13.16.2.md`
- `HOTFIX-v13.16.3.md`
- `HOTFIX-v13.16.4.md`
- `HOTFIX-v13.16.5.md`
- `HOTFIX-v13.16.6.md`
- `README.md`
- `RELEASE-NOTES-v13.md`

---

# 19. Recommended role for this file

If incorporated into a future LatticeVale release, this file should be the **canonical install-capability/options catalog** and should cross-reference rather than replace:

- repository-root `README.md` — short project overview / quick start
- `docs/Instructions.txt` — procedures and commands
- `docs/Installer Description.txt` — conceptual post-install/settings guide
- `docs/SECURITY.md` — trust/ownership/security model
- `docs/SOURCES.md` — exact runtime acquisition/source pins
- `docs/CHANGELOG.md` — historical version chronology

Keeping a single feature/options catalog would prevent current questionnaire choices from becoming scattered across several documents again.

### Policy v9 model-aware Ollama and Honcho timeout behavior

When LatticeVale-managed Ollama is selected, policy v9 fingerprints the installed text-model artifact size, Honcho embedding-model artifact size, persisted `OLLAMA_CONTEXT_LENGTH`, and the derived `OLLAMA_MODEL_FLOOR_MIB`. Before a clean install has downloaded models, CPU-backed Ollama uses the proven provisional floor; after downloads complete, LatticeVale performs a second bounded resource reconciliation before inference/embedding verification. Because managed Ollama is constrained to one loaded model, text and embedding artifact sizes are treated as alternative resident requirements rather than blindly summed. If the model-aware minimum plus the selected services cannot fit inside the managed budget, LatticeVale refuses the unsafe plan.

Self-hosted Honcho also receives an adaptive supported root request timeout. LatticeVale records ownership in a private sidecar and updates only the timeout value it previously owned; an explicit user timeout remains authoritative. `./manage.sh status` samples cgroup `memory.events` twice and distinguishes a historical lifetime `memory.max` count from new pressure during the sample window.
