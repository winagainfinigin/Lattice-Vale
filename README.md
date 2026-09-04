# LatticeVale v14.5.46

> For **any recognized older installer-managed LatticeVale installation**, launch the **full v14.5.46 release** and choose **Resume / repair installation**. v14.5.46 adds GPU-aware onboarding and prerequisite reuse/provisioning while inheriting v14.5.45 PowerShell compatibility, v14.5.44 DirectML preflight, v14.5.43 cumulative migration, and policy v11. No intermediate LatticeVale release is required.

> This is a repair-installer migration feature, not a universal Git diff. An unrecognized/corrupt stack is preserved and rejected rather than guessed as a fresh install; repair downgrades from a newer installed release are refused. The separate patch ZIP remains for source checkouts only.

### v14.5.46 — GPU-aware onboarding and prerequisite provisioning

v14.5.46 makes GPU acceleration part of the normal installer questionnaire instead of assuming users already know which WSL runtime path fits their hardware. The installer inventories recognized Windows AMD/NVIDIA/Intel/Qualcomm adapters, directly checks WSL DirectML and managed-Ollama GPU prerequisites, reports which installer-owned WSL components already exist, and marks the recommended local text backend/managed-Ollama acceleration option without removing explicit user choice.

The current v14.5.46 package also includes a same-version WSL/DirectML stability correction: Resume / repair can skip completed stages without losing later-stage helper functions; DirectML keeps bounded WSL-host RAM/CPU headroom and backs off safely to Ollama after repeated hard startup failures; and the optional persistent WSL lifetime policy applies both the distro-instance and VM idle-timeout controls while preserving unrelated `.wslconfig` settings.

For NVIDIA systems with working WSL `nvidia-smi`, managed Ollama NVIDIA acceleration is recommended and LatticeVale reuses or installs/configures the tested NVIDIA Container Toolkit. For AMD systems with real `/dev/kfd` + `/dev/dri`, managed Ollama ROCm is recommended and uses the pinned ROCm image. AMD/Intel/Qualcomm DirectX 12 systems with a healthy `/dev/dxg` + D3D12/DXCore bridge but no verified vendor-specific managed-Ollama path are steered toward DirectML; DirectML reuses its installer-owned venv when healthy or installs the missing Ubuntu base packages and rebuilds the pinned isolated environment. If no GPU path is verified, Ollama CPU-safe fallback remains the recommendation.

LatticeVale does not install or replace Windows/vendor display drivers and does not fabricate missing ROCm device nodes. Hardware detection is recommendation only; the existing runtime probes, DirectML tensor verification, model admission, policy-v11 VRAM budgeting, and `ollama ps` offload proof remain authoritative.

### v14.5.45 — PowerShell 7.6 generic-collection compatibility hotfix

v14.5.45 fixes a Windows installer crash that could occur after a successful DirectML preflight on affected PowerShell 7.6 builds: `Argument types do not match`. LatticeVale no longer constructs .NET generic collections through `New-Object`; installer, uninstall, repair/reset, and Windows relay paths use direct `.NET ::new()` constructors instead. Public helpers that return generic lists convert them explicitly with `.ToArray()` where appropriate, avoiding the problematic binder/coercion path.

This is a LatticeVale compatibility fix, not a user workaround. Users do not need to edit PowerShell source or downgrade PowerShell. v14.5.44's dedicated `/dev/dxg`/D3D12/DXCore DirectML preflight, v14.5.43 cumulative Resume / repair migration, policy v11, and all existing preservation/fallback rules are inherited unchanged.

### v14.5.44 — DirectML WSL preflight false-negative hotfix

v14.5.44 decouples DirectML selection from the managed-Ollama GPU prerequisite parser. The questionnaire now probes `/dev/dxg` with a direct read-only WSL `test -e`, retries as root after any normal-user miss/failure, and separately reports the WSL-projected `libd3d12.so`, `libd3d12core.so`, and `libdxcore.so` bridge libraries. A failed probe is explicitly distinguished from a confirmed missing GPU bridge, so a transient or user-context probe cannot be mislabeled as "DirectML unsupported."

On Resume / repair, when the installer-owned DirectML virtual environment already exists, v14.5.44 also performs a real `torch_directml.device()` tensor addition as an additional execution signal. Fresh installs are not blocked merely because that venv has not been created yet. AMD, NVIDIA, Intel, and Qualcomm DirectX 12 adapters remain eligible; Ollama fallback, policy v11, v14.5.43 universal repair migration, and v14.5.4 VRAM admission remain unchanged.

### v14.5.43 — cumulative universal Resume / repair migration

v14.5.43 turns the current full installer into the cumulative migration engine for prior recognized LatticeVale-managed stacks. Managed-stack ownership must first be proven by current or retained historical installer markers. Resume / repair then compares saved installer version/schema with the bundle, rejects newer-than-bundle downgrade attempts or unsupported future schemas, and treats older/versionless recognized formats as migration candidates. A migration forces the same bundle-owned verified rollback backup used by controlled Update / repair before installer-managed software is refreshed.

The migration installs the current bundle-owned management layer, replays stale checkpoint revisions through the existing preservation-first verifiers, refreshes the current declared package/image/source layer, and performs the uncheckpointed resource-policy-v11 reconciliation. Existing Hermes profiles/provider settings, Matrix identities/rooms, Honcho databases/memories, QMD/SearXNG data, Ollama models, DirectML selections, vault/workspace content, user overrides, and recoverable installer choices remain preservation-first. Historical managed Ollama state that predates an acceleration field is normalized to explicit CPU ownership during migration rather than silently opting the installation into GPU execution; GPU Auto/forced modes remain an explicit later choice.

Same-version Resume / repair remains local-first: v14.5.43 does **not** turn every routine repair into an image/source refresh. Migration provenance fields are excluded from checkpoint fingerprints so a completed one-time migration does not replay solely because it remembers its origin.

### v14.5.42 — hardware-aware resource policy v11

v14.5.42 completes the hardware-resource work that followed v14.5.4. Managed Ollama now profiles WSL RAM as compact (<=8 GiB), balanced (>8-16 GiB), or large (>16 GiB), and CPU capacity as compact (<=4), balanced (5-8), or high (>8). Compact CPU-backed Ollama uses a 4096-token automatic context and a 4096 MiB provisional floor; downloaded model size and context remain authoritative and can raise the floor or reject an impossible topology.

NVIDIA CUDA and supported AMD/ROCm managed-Ollama paths now inventory individual GPUs (count, smallest, largest, and aggregate VRAM) instead of treating all VRAM as one interchangeable pool. The planner accounts for Ollama's single-GPU-first / multi-GPU-spread behavior, uses the smaller RAM/usable-VRAM context recommendation, reduces managed Ollama CPU quota when GPU-backed, and persists GPU topology in the adaptive fingerprint so repair/start can recalculate after hardware changes.

When DirectML and managed Ollama target the same GPU vendor, v14.5.42 coordinates their VRAM envelopes instead of allowing both backends to assume most of the same adapter. `OLLAMA_GPU_OVERHEAD` is generated as an installer-owned per-GPU reserve and `DIRECTML_VRAM_LIMIT_PCT` is reduced when required, including heterogeneous multi-GPU layouts. DirectML no longer silently raises a low policy-selected percentage to a 1 GiB budget: if the resulting envelope is below its safe minimum, DirectML admission fails closed and Ollama remains available.

GPU device presence is not accepted as proof of acceleration. After the selected managed Ollama text model is loaded, LatticeVale performs a bounded `ollama ps` PROCESSOR check. Auto-selected GPU acceleration that actually executes on CPU is fingerprinted and re-budgeted as CPU; explicitly forced NVIDIA/AMD acceleration that executes on CPU fails installation rather than retaining GPU-sized assumptions. A changed driver/kernel/VRAM fingerprint allows Auto to retry acceleration later.

Native Windows Ollama remains externally owned. LatticeVale recommends one loaded model, one parallel request, conservative keep-alive, and documents `OLLAMA_GPU_OVERHEAD`, but does not silently change global Windows Ollama settings. Intel/Vulkan is not introduced as a managed WSL Ollama acceleration mode in this patch; DirectML remains the broader optional DX12 path.

### v14.5.42 — canonical policy + release integrity

Resource policy v11 is finalized once into a canonical installer-owned policy object. Generated Compose CPU/RAM limits, `.latticevale-resource-state`, audit expectations, and the human-readable `resource-policy-report.txt` consume that same finalized object instead of independently recalculating ceilings. The state records separate hardware and policy SHA-256 fingerprints, so audit/repair can distinguish a hardware/topology change from policy/configuration drift. The report contains no credentials and records the RAM/CPU profile, acceleration/offload status, GPU topology, DirectML/Ollama coordination, context/model floor, and generated service ceilings.

Release qualification is deterministic and contamination-checked. The authoritative suite contains exactly 135 fixtures in six numbered shards; bytecode/cache/temp artifacts are rejected before and after test execution. Packaging is accepted only after the exact v14.5.4 parent can reproduce the qualified v14.5.42 tree through its patch, the reconstructed v14.5.2 parent can reproduce the same tree through the combined patch, and a freshly extracted release ZIP matches the qualified source tree and source manifest byte-for-byte.

### v14.5.4 — DirectML VRAM guard + 16 GB-class RAM efficiency

v14.5.4 makes DirectML GPU-memory safety a LatticeVale responsibility rather than an end-user tuning task. `torch-directml` does not expose a stable allocator-level VRAM quota, so LatticeVale enforces the strongest portable boundary available: before any model is moved to the DirectML device, the gateway requires measurable dedicated VRAM and proves that exact fp16 parameter bytes plus a conservative activation/runtime reserve and KV-cache estimate fit inside 75% of the detected adapter memory. The effective context is automatically reduced in 256-token steps when needed; if even a 1024-token context cannot fit, DirectML is rejected and the request goes through Ollama instead. Runtime OOM/operator failures retain the same automatic fallback.

The release also targets ordinary 16 GB Windows PCs. On WSL allocations up to 12 GiB, resource policy v10 keeps the real-world-proven 1 GiB Hermes floor but tightens supporting database/cache/indexer minima and useful ceilings. DirectML's host-memory requirement now acts as a floor on the existing non-container reserve instead of being added on top of it, eliminating several GiB of double-counted headroom on common 8-12 GiB WSL VMs. DirectML model loading uses Transformers' low-CPU-memory path; managed Ollama uses a 4096-token emergency-fallback context and `0s` keep-alive while DirectML is primary, so the fallback/embedding model does not remain resident unnecessarily. Model-aware post-download checks still raise the Ollama floor or refuse the plan when an actually selected model cannot fit.

### v14.5.3 — experimental DirectML hybrid local-AI backend

v14.5.3 adds a shared OpenAI-compatible text gateway on the WSL host for PyTorch DirectML. Hermes and every Honcho text-generation section use that gateway only when the user explicitly selects DirectML; Honcho embeddings continue to use Ollama directly so the existing 1536-dimensional pgvector store remains compatible. The gateway performs a real DirectML tensor probe, uses a conservative default `Qwen/Qwen2.5-1.5B-Instruct` model, serializes generation to bound memory spikes, and automatically retries failed text requests through the configured managed-WSL or native-Windows Ollama backend. Existing v14.5.2 installs default to `localTextBackend=ollama` during repair unless the user deliberately changes the backend.

The DirectML environment is kept outside the Hermes/Honcho Python environments and uses pinned compatibility dependencies. Startup, repair, update, verification, backup, state audit, Windows autostart, and safe uninstall all understand the new host-side gateway. DirectML never replaces Ollama entirely: Ollama remains required for Honcho embeddings and provides the failure fallback.

### v14.5.2 — cleanup / reclaim disk space maintenance release

v14.5.2 adds a seventh existing-install maintenance option without broadening normal repair/update behavior. The user explicitly chooses one, several, or all bounded cleanup categories and confirms before deletion. Cleanup is limited to LatticeVale-owned Option 6 pre-update backups proven by exact metadata, stale LatticeVale staging residue, APT package-download cache, Docker dangling images, Docker dangling default-builder cache, and WSL root TRIM. It does not stop/remove containers, prune networks or volumes, delete tagged images/configured models, touch persistent Hermes/Matrix/Honcho/QMD/vault/workspace/credential state, or manipulate the WSL VHDX.

A recognized managed stack may enter **Option 3 — Verify installation only** or **Option 7 — Cleanup / reclaim disk space** when the host partition is below the ordinary managed-repair free-space floor. Mutating Options 1/2/4/5/6 remain blocked until the normal floor is restored, and fresh/unrecognized stacks do not inherit the exception.

### v14.5.1 — adaptive CPU/RAM/OOM reliability patch

v14.5.1 corrects adaptive resource-policy failures found by real full-stack WSL audits. Policy v4 could protect managed Ollama so aggressively that the central `hermes-agent` container received only 544 MiB on a roughly 9.7 GiB WSL VM, causing repeated cgroup OOM kills even while WSL still had multiple GiB available. The initial v14.5.1 policy-v6 balance fixed Hermes but left CPU-backed managed Ollama at only 4128 MiB; a subsequent live run held Ollama at ~98% of that hard ceiling and recorded more than 15,000 cgroup `memory.max` pressure events. That release's final resource policy **v9** kept the bounded aggregate-budget model and user-owned `compose.override.yaml`, preserves the 1024 MiB Hermes and 512 MiB Honcho API preferred floors, and gives CPU-backed managed Ollama a real **4608 MiB viability floor**. On >6-12 GiB WSL allocations with CPU-backed managed Ollama selected, v9 uses a 10% non-container reserve; other >6-24 GiB shapes retain 20%, <=6 GiB remains 30%, and >24 GiB remains 15%. Policy v9 is topology-aware for public multi-profile setups: its 1024 MiB Hermes baseline covers the default gateway plus up to one secondary Matrix gateway and Kanban concurrency up to 3; each additional persistent secondary Matrix gateway adds 192 MiB to the Hermes minimum and each Kanban slot above 3 adds 96 MiB, capped at a 4096 MiB topology floor. Hermes CPU keeps the ordinary ~75% ceiling for common topology but can rise toward 100% of WSL-visible CPUs under additional gateway/worker pressure.

`state-audit.py`, `./manage.sh verify`, and the v14.5 read-only planner now treat a running selected container with Docker `OOMKilled=true` as a repairable runtime-policy problem instead of allowing recovered endpoints to produce a false `HEALTHY` result. Existing policy-v2/v3/v4/v5/v6/v7/v8 fingerprints automatically become stale and are regenerated/reconciled by normal Resume / repair or the existing start-time resource refresh. The policy fingerprint also persists each generated service ceiling, and final reconciliation compares those values with Docker's live `HostConfig.Memory`; an existing v14.5.0 container that still has the old 544 MiB Hermes cgroup cannot be accepted merely because the current YAML/state files were rewritten. LatticeVale still does not write global WSL `memory` or `autoMemoryReclaim` settings.

### v14.5.0 — read-only planning foundation

v14.5.0 is a deliberately small architectural release. It adds a WSL-native, standard-library Python reader for existing installer selections, derived runtime environment, checkpoint state, and the presence/hash of the user-owned `compose.override.yaml` without making any of those files a new write target. `./manage.sh repair --plan` (or `./manage.sh plan`) produces a read-only repair plan by combining the existing checkpoint/revision state with the existing `state-audit.py`; applying repair still requires the Windows installer **Resume / repair** path. The existing checkpoint engine is not replaced or made dependent on the new metadata: its current hardcoded revisions are mirrored in `checkpoint-metadata.json` for read-only tooling and CI verifies that the mirror stays synchronized.

The release also adds `./manage.sh audit-free`, which reports whether the current installation has an installer-declared free/local default Hermes path, separately identifies whether that AI path is fully WSL-native (managed Ollama), and separates optional Windows/external/proprietary integrations without promising that third-party free tiers will remain free. CI regression fixtures are now auto-discovered so adding a `tests/*-fixtures.py` file automatically adds it to the deterministic suite.

**WSL-native boundary:** all core LatticeVale runtime, state inspection, planning, Docker/Hermes lifecycle, and reconciliation remain inside the selected Ubuntu WSL2 distro. Windows PowerShell remains the bootstrap/host-integration layer for functionality that genuinely requires Windows APIs, including WSL registration/launch recovery, shortcuts/Task Scheduler, Windows Tailscale integration, and the optional native-Windows Ollama bridge. No persistent Windows helper is required for the normal managed WSL/Docker stack unless the user selected a Windows-host integration.

### v14.4.85 — reconcile/readiness and maintenance reliability

v14.4.85 promoted the accumulated pre-release reliability candidate into a normal versioned release. It fixed startup-aware reconcile and post-gateway readiness ordering; verified Synapse/Docker DNS from inside `hermes-agent`; waited boundedly for managed Ollama, Hermes API, Dashboard, and Matrix readiness after the final gateway lifecycle mutation; and reported the exact component that failed. It also made Option 6 self-repairing with a bundle-owned pre-update safety-backup helper and made Option 3 print a fresh Linux/Docker/Hermes plus Windows-side read-only verification report.

### v14.4.84 Hotfix 1 — Matrix gateway startup readiness

If you already downloaded the initial public v14.4.84 release, use the **Hotfix 1 full release** and choose **Resume / repair installation**. The version remains 14.4.84. Hotfix 1 fixes a restart/startup race where Hermes gateways could start while Synapse/Docker DNS was not yet reachable from inside `hermes-agent`; the gateway process could remain running while Element messages stopped reaching the default or named Matrix profile. The hotfix waits for Synapse, verifies `synapse:8008` from inside the Hermes container, then reconciles the default and selected profile gateways. It also makes the state audit treat an internally unreachable Matrix backend as broken instead of reporting a false healthy gateway. Fresh installs use the same ordering automatically. Internal reconciliation checkpoint revisions are advanced so Resume / repair on an already-installed initial 14.4.84 copy cannot skip the hotfix.

LatticeVale is an MIT-licensed **WSL2-native self-hosted Hermes Agent platform with a Windows bootstrap/host-integration layer**. Core runtime and lifecycle operation live inside the selected Ubuntu WSL2 distro; Windows-side code exists for bootstrap and integrations that genuinely require Windows APIs.

It installs into an **existing supported Ubuntu WSL2 distribution**, provisions Docker and Hermes, and can integrate Matrix, multi-profile Kanban orchestration, Honcho memory infrastructure, SearXNG, QMD indexing, Ollama/local AI, Obsidian, Windows lifecycle shortcuts, and Tailscale remote access.

A normal core installation is designed to remain usable without a required paid API, subscription, or proprietary hosted service. Optional external providers and Windows-host integrations may have their own licenses, accounts, or pricing; they are not requirements for the free/local managed path.

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

The lower repair threshold is used only after LatticeVale has confirmed an existing installer-managed installation. A recognized managed stack that has fallen below the normal repair free-space floor may still enter **Option 3 — Verify installation only** or **Option 7 — Cleanup / reclaim disk space**. Mutating repair/update modes remain blocked until the normal managed-repair floor is restored; this exception never applies to a fresh or unrecognized stack.

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

## Cleanup / reclaim disk space

**Option 7 — Cleanup / reclaim disk space** is an isolated, existing-install maintenance path. It asks which cleanup categories to run, supports selecting several or all of them, requires a final confirmation, then exits without entering normal install/repair/provider/update stages. It is also reachable for a recognized managed stack when the host partition is below the normal 10 GiB managed-repair free-space floor, so cleanup can recover enough physical storage for a subsequent repair.

The offered categories are deliberately bounded:

1. verified LatticeVale **Option 6 pre-update safety backups** for this exact stack;
2. stale root-owned LatticeVale installer/audit staging and incomplete `.partial` pre-update residue;
3. downloaded APT package archives (`apt-get clean` only);
4. Docker **dangling images only** (`docker image prune -f`, never `-a`);
5. Docker default-builder **dangling build cache only** (`docker builder prune -f`, never `--all`);
6. WSL root-filesystem TRIM (`fstrim -v /`) to expose already-freed ext4 blocks to the virtual-disk layer where supported.

Option 7 never removes/stops LatticeVale containers, Docker networks or volumes, tagged images, configured Ollama models, Hermes/Matrix/Honcho/QMD persistent state, databases, vault/workspace files, credentials, or user-created backups. It does not resize, move, mount, compact, or otherwise manipulate the WSL VHDX. Docker's engine may be shared with unrelated workloads, so LatticeVale intentionally does not expose `docker system prune`, container/network/volume prune, or `docker image prune -a` here. Build-cache cleanup can make a later rebuild slower but does not remove runtime state.

Deleting data inside WSL and running TRIM may not immediately reduce the Windows-visible VHDX file length on every WSL/storage configuration. VHDX compaction is therefore kept outside Option 7 rather than making a Windows storage mutation part of an install-preserving cleanup path.

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

LatticeVale resource policy **v11** keeps hard per-container ceilings and a bounded aggregate managed-container budget. It preserves the policy-v9 Hermes/Honcho correction for the policy-v4 544 MiB Hermes starvation failure and the model-aware safeguards added after policy-v6 CPU-backed Ollama pressure. On sufficiently sized hosts, Hermes retains a 1024 MiB preferred minimum and Honcho API a 512 MiB floor; CPU-backed managed Ollama now starts from a **4096 MiB provisional floor** before model artifacts are measurable, then uses model/context-aware sizing after download. Policy v11 also classifies WSL RAM/CPU shape, inventories eligible NVIDIA/AMD GPU topology, coordinates same-vendor Ollama/DirectML VRAM with per-GPU `OLLAMA_GPU_OVERHEAD`, and verifies post-load GPU offload before keeping GPU-sized resource assumptions. If the selected service set cannot meet its defined RAM/VRAM safety floors inside the managed budget, v11 refuses the unsafe plan and tells the user to increase WSL RAM, choose a smaller model, deselect components, use native-Windows Ollama where appropriate, or disable LatticeVale ceilings.

Depending on the enabled services, it can apply:

- adaptive per-container CPU and memory ceilings
- WSL-aware memory budgeting with 30% reserve on <=6 GiB; 10% on >6-12 GiB when CPU-backed managed Ollama is selected; 20% on other >6-24 GiB shapes; and 15% above 24 GiB, subject to reserve floors/caps
- reduced glibc allocator arenas
- Synapse cache tuning
- reduced PostgreSQL fixed `shared_buffers`
- protected managed-Ollama memory headroom within the aggregate WSL container budget, including a 4096 MiB provisional CPU-backed viability floor and model-aware post-download sizing
- RAM/CPU hardware profiles plus NVIDIA/AMD GPU topology metrics (count, minimum, maximum, aggregate VRAM)
- per-GPU `OLLAMA_GPU_OVERHEAD` and same-vendor DirectML/Ollama VRAM coordination
- bounded post-load `ollama ps` verification so Auto GPU fallback is re-budgeted as CPU and forced GPU modes fail closed when offload is not proven
- controlled Ollama model residency
- bounded Ollama parallelism
- short Ollama model keep-alive behavior
- OOM-aware runtime auditing for selected running containers
- live Docker CPU/RAM-ceiling verification during reconciliation so stale quotas cannot survive clean/repair convergence

Clean installs generate policy v11 before first container creation. Existing adaptive policy-v2 through policy-v10 installs regenerate through normal Resume / repair or managed start-time resource reconciliation. Policy v11 fingerprints WSL-visible CPU/RAM profile, Matrix-enabled secondary gateway count, Kanban concurrency, the derived Hermes topology floor, selected Ollama acceleration, and managed-GPU topology/coordination values; hardware or runtime-fallback changes therefore invalidate stale generated ceilings instead of carrying them forward. Final reconciliation compares effective merged Compose `mem_limit`/`cpus` with Docker's live `HostConfig.Memory`/`HostConfig.NanoCpus`. Explicit user `compose.override.yaml` configuration remains authoritative and is applied after generated LatticeVale resource policy. LatticeVale does not write global WSL `memory` or `autoMemoryReclaim` settings. Generated root/Windows-start helpers evaluate current CPU, RAM, enabled-limit state, profile topology, Kanban concurrency, and acceleration state when the helper runs rather than freezing install-time values.

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
| **v14.4.85** | Release | Startup-aware reconcile/post-gateway readiness, self-repairing pre-update backup, and explicit read-only verification output |
| **v14.5.0** | Release | Read-only WSL-native repair planning/config-state foundation and free/local-path audit |
| **v14.5.1** | Release | Adaptive resource policy v9, OOM-aware health, low-RAM viability guards, and live Docker CPU/RAM convergence for clean/repair |
| **v14.5.2** | Release | Install-preserving Option 7 cleanup/reclaim path plus low-space Verify/Cleanup recovery gate; v14.5.1 runtime policy inherited unchanged |
| **v14.5.3** | Release | Experimental DirectML hybrid text backend with Ollama fallback/embeddings, host-RAM reserve, and lifecycle integration |
| **v14.5.4** | Release | DirectML VRAM admission guard, low-CPU-memory loading, and <=12 GiB WSL resource-policy v10 |
| **v14.5.42** | Release | Hardware-aware resource policy v11, multi-GPU/shared-VRAM coordination, and runtime managed-Ollama GPU-offload proof |
| **v14.5.43** | Prior install release | Universal cumulative Resume / repair migration for recognized older managed installs; policy v11 retained |
| **v14.5.44** | Prior install release | DirectML `/dev/dxg` preflight + root retry/library diagnostics; v14.5.43 universal repair and policy v11 retained |
| **v14.5.45** | Prior install release | PowerShell 7.6 generic-collection compatibility hotfix; v14.5.44 DirectML preflight retained |
| **v14.5.46** | **Current install release** | GPU-aware backend recommendation plus selected-path prerequisite reuse/provisioning; all v14.5.42-v14.5.45 safety and repair behavior retained |

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

Policy v9 also closes the last model-selection generalization gap for the public repository. Managed Ollama no longer assumes every local model has the same RAM requirement: once the selected text/embedding manifests exist, the allocator fingerprints their artifact sizes and the persisted context length, derives a larger CPU/GPU-aware floor when necessary, and performs a second bounded reconciliation after model download. The text and embedding sizes are not summed because LatticeVale constrains managed Ollama to one loaded model. If the model-aware minimum plus enabled services cannot fit, installation/repair fails with an actionable resource message. Self-hosted Honcho now receives an adaptive supported request timeout while preserving explicit user timeout values, and `./manage.sh status` distinguishes historical `memory.max` counters from new pressure by sampling deltas.
