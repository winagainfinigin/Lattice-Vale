# LatticeVale v14.4.84 — Technical README

- v14.4.84 Hotfix 1 repairs Matrix gateway startup readiness by waiting for Synapse/Docker DNS inside hermes-agent before default/named gateway reconciliation; state audit detects false-running Matrix gateways. Fresh and repair paths are both covered; VERSION remains 14.4.84.
- v14.4.84 fixes the Windows lifecycle shortcut launcher and WSL transport interaction: Start/Shut Down use direct WSL `--cd` lifecycle execution instead of the older nested `bash -lc` wrapper that could return exit 127; Shut Down now stops only the managed stack and never calls targeted `wsl --terminate`; mutating repair detects the exact legacy installer-owned helper, performs a bounded `wsl --shutdown` + `WslService` reset/re-probe, then rewrites shortcut state. The launch-recovery helper likewise resets `WslService` after a clean shutdown when elevated. Distro registration/VHDX and unrelated host state remain preserved.
- v14.4.83 retains the v14.4.82 WSL helper return-channel fix and advances only the managed runtime prerequisites: adaptive policy v4 provides additional protected Ollama headroom within the existing aggregate WSL budget, selected Redis/Valkey workloads persist `vm.overcommit_memory=1`, and the Ubuntu Pro integration is removed: LatticeVale no longer offers or manages Ubuntu Pro for WSL. Existing external Ubuntu Pro state is preserved.
- v14.4.81 closes the registered-distro `Wsl/Service/E_UNEXPECTED` preflight dead end without weakening ownership boundaries. If the failed distro is required or explicitly selected, the Windows installer can invoke the release WSL host-repair helper in bounded `-LaunchRecoveryOnly` mode: clean global WSL shutdown/retry first, then an explicit backed-up mirrored→NAT compatibility fallback only when the error persists. On success it fully re-probes distro eligibility in the same run; on failure it does not automatically escalate into DISM/feature mutation. The bounded helper mode is usable without elevation, while deeper component/feature repair remains an explicit Administrator action. Distro registration/VHDX are unchanged, as are the 50 GiB fresh-install and 10 GiB managed-repair free-space thresholds.
- v14.4.8 formalizes the conservative clean/repair reliability maintenance: missing installer-managed Hermes browser selection becomes Local Browser / Chromium and a missing extraction timeout becomes 360 seconds, while explicit browser/provider/gateway/environment/timeout choices remain authoritative. The integrations checkpoint advances 3→4 without advancing the managed package/image refresh gate. The Linux static audit and release-manifest path handling are hardened, and current v14.x patch documentation is consolidated. LatticeVale does not modify `SOUL.md` or model policy for this behavior.
- v14.4.7 pairs LatticeVale-managed SearXNG search with a generated keyless `latticevale-local` public-page extraction provider for Hermes. The provider is an additive Hermes user plugin inside existing persistent profile data, adds no service/image/package/API key, blocks non-public network targets, revalidates redirects, and bounds fetch/output sizes. Explicit user-selected extract/shared providers remain authoritative. The original extraction migration advanced the integrations checkpoint 2→3. SearXNG discovery still depends on external search engines: a successful local `web_search` call may temporarily return zero results when those engines rate-limit, CAPTCHA, or suspend automated requests. That is an upstream availability condition, not by itself a failed LatticeVale integration; known public URLs remain independently readable through `web_extract`.
- v14.4.6 fixes a WSL CPU-fingerprint audit mismatch and refines managed-refresh triggering. Adaptive resource generation/start use `nproc` semantics, while the audit previously used `os.cpu_count()` and could see the Windows host logical-CPU total despite a lower WSL processor allocation. Audit now uses process-visible CPU affinity first, then `nproc`; RAM fingerprinting remains exact. Resume / repair no longer treats a bundle-version change alone as a reason to pull/rebuild managed components. Managed package/image/source refresh is driven by the 30-day gate, `MANAGED_REPAIR_REFRESH_REVISION`, missing legacy state, or explicit Option 6. Public 14.4.2→14.4.6 still refreshes because the revision advances 1→2; 14.4.5→14.4.6 stays local-first when its recent revision-2 refresh is already complete.
- v14.4.5 introduced repair convergence for adaptive RAM policy v3: Resume / repair explicitly regenerates a stale/missing policy-v3 overlay even when `prepare_config` was checkpointed complete, forces affected containers through Compose reconciliation, and refuses final success while that policy remains stale. Its version-only managed-refresh trigger is superseded by v14.4.6's explicit refresh-revision/age/force model. v14.4.4 live metadata-race and v14.4.3 preservation/RAM hardening remain inherited.
- v14.4.2 is the documentation/release-consistency patch over v14.4.1 that aligned package-layout documentation and integrity metadata.
- v14.4.1 is a packaging/layout patch over the stable promotion of the audited v14.3.43 runtime line. Runtime behavior is intentionally unchanged; the promotion applies the documentation audit, adds the canonical `../docs/FEATURES.md`, updates release/test metadata, and regenerates release integrity data.
- v14.3.43 fixes only the explicit clean-host reset Scheduled Task scanner so heterogeneous/non-Exec task actions cannot abort dry-run ownership discovery under StrictMode; normal installer/runtime behavior is unchanged.

- v14.3.42 adds a separate dry-run-first clean-host reset utility for intentional fresh WSL/LatticeVale rebuilds; normal installer/uninstaller behavior remains preservation-first. It removes only proven LatticeVale/explicit legacy Foundry Windows state, gates all-distro WSL removal behind an explicit switch/confirmation, and preserves shared Hyper-V/VMP/HNS/Tailscale/Obsidian state.
- v14.3.41 added the WSL cold-start host-safety boundary: normal configuration flows do not contain a mirrored-networking writer/fallback; existing mirrored mode is consumed only when already healthy and recorded as external/user-owned. v14.4.81 preserves that boundary while allowing the installer to invoke the explicit host-repair helper in bounded launch-recovery mode after E_UNEXPECTED, with a separate user-approved backed-up mirrored→NAT fallback before any deeper repair. v14.3.40 changed documentation only. The inherited v14.3.39 existing-install QC removes automatic engine-global Docker image/build-cache pruning from repair maintenance; Docker disk usage remains visible, while automatic cleanup is limited to proven LatticeVale-owned disposable state so unrelated projects sharing the distro are preserved.
- v14.3.38 adds a profile-roster-aware Kanban task-context plugin and managed skill-authoring/recovery policy. It applies on clean install and is migration-reapplied on every mutating existing-stack path via the integrations checkpoint revision. Valid user-created routing targets remain valid but are never rewritten by LatticeVale; only default and installer-managed profiles receive generated policy/config. Root task creation can be shallow-normalized to triage, bound placeholder task IDs can be repaired, ambiguous worker lifecycle misuse is blocked, durable completed-task artifacts are preferred, and skill validation errors trigger correction/strategy changes without weakening hard stops.
- v14.3.37 keeps `install-options.json` as the canonical shared WSL networking policy for native Windows Ollama + Windows-host Tailscale, but makes that policy capability-first: verified NAT/private relay is preserved, existing mirrored mode is supported, and a global mirrored switch is explicit/default-No only after the current topology fails verification. It also hardens functional WSL preflight, reclaims stale installer-owned Windows bridge ports, makes secondary Matrix pending activation/cross-signing genuinely resumable rather than stage-fatal, and adds a controlled installer-managed Update / repair mode that forces the current bundle's declared software refresh after a required backup.

- v14.3.29 removes the remaining serialized multiline-shell dependency from uninstall discovery: it reads `getent passwd` directly through WSL and probes ownership markers with separately passed `test`/`find` arguments. Native Windows Ollama model validation now uses a health-checked relay endpoint; calculating Docker's host-gateway address alone is not considered readiness.
- v14.3.28 fixes uninstaller discovery as well as the one-item distro menu: completed, installer-state, backup-recoverable, and staged partial LatticeVale stacks are recognized using the installer's recovery evidence, while destructive purge remains restricted to the selected user's exact `$HOME/hermes-stack` with symlink/mount safeguards.
- v14.3.26 hardens the optional native-Windows-Ollama transport without adding another topology: the Windows native-service relay now refreshes WSL/host addresses and exact firewall rules while running, and the WSL-local relay is supervised by systemd when systemd is already active or by an internal watchdog fallback otherwise.
- Both Windows relay implementations and the Python WSL-local relay now use bounded connection concurrency and timeouts. Relay failures/topology changes are logged instead of being silently swallowed, and C# bidirectional copy tasks are fully observed after shutdown.
- Native Windows Ollama is an advanced integration across Windows, WSL, Docker, and firewall boundaries. The managed WSL/Docker backend remains the lower-complexity baseline. See `../docs/NATIVE-OLLAMA-INTEGRATION.md` and `../docs/WINDOWS-INTEGRATION-TEST-MATRIX.md`.
- v14.3.25 makes installer-created Windows **Start LatticeVale** shortcuts native-Ollama-aware: they probe the saved Windows-local `/api/version` endpoint first, start a recorded custom Ollama service when applicable or the recorded tray app only when needed, wait for API readiness before WSL startup, and never stop the user-owned Windows Ollama app on LatticeVale shutdown.
- v14.3.25 also fixes `matrix_profiles` live verification for intentionally `pending-manual` profiles. The verifier no longer asks an invite-only bot token for normal room state before join; it validates token identity, stored managed-room version, `/sync` invite/join visibility, and the stopped gateway. Completed profiles retain live room-state/join checks.
- v14.3.23 is documentation/public-release clarification only: the MIT customization/forking rights and exact x64/AMD64 + amd64/x86_64 supported-bundle boundary are now explicit. No v14.3.22 runtime behavior was removed.
- v14.3.22 makes native Ollama WSL `/api/version` success authoritative, stabilizes already-working direct paths without unnecessary restarts, and prevents duplicate tray/server launches by waiting for the old process tree and listener to exit. The Obsidian vault prompt now has no suggested location.
- v14.3.21 added `../installer/uninstall.ps1` + `Uninstall-LatticeVale.ps1`. Safe uninstall removes only provably installer-owned Windows tasks/shortcuts/firewall/relay state and Linux host helpers while preserving the distro and shared prerequisites. Full purge additionally deletes only the validated `/home/<user>/hermes-stack` tree after an exact `PURGE` confirmation.
- A preserve-data uninstall removes stale `.tailscale-info` / `.windows-native-info` integration metadata and writes `.latticevale-uninstalled` so retained data is clearly identified. Global `.wslconfig` backups are only offered for optional manual restoration; the uninstaller does not silently overwrite later user changes.
- v14.3.20 native-Ollama fallback order is `windows-gateway-relay` -> verified mirrored `wsl-localhost-relay` (explicit global WSL change when needed) -> direct `wsl-host-relay`. The mirrored step backs up/restores `.wslconfig`, restarts WSL, and must verify both active mirrored mode and `/api/version`; it never changes `OLLAMA_HOST`.

### v14.3.24 native Windows Ollama model validation

- Native Windows Ollama models do not need to be pre-downloaded. After the native API/relay is verified, LatticeVale uses Ollama's model-list API to detect selected models and the pull API to fetch missing selections into the native Windows Ollama model store.
- Honcho embedding compatibility is validated directly from WSL against the verified native Ollama OpenAI-compatible endpoint before Honcho's Compose network is created. This prevents fresh/resumed native-Ollama installs from failing with `network hermes-backend not found` during pre-infrastructure model validation.
- Managed WSL/Docker Ollama retains the existing Honcho-image validation on `hermes-backend`, because starting the managed Ollama Compose service creates the required project networks.

### v14.3.18 native Windows Ollama direct-WSL fallback

- The existing `windows-gateway-relay` and `wsl-localhost-relay` remain preferred and keep native Ollama on loopback.
- If both fail while the native Windows API itself is healthy, the questionnaire can explicitly offer `wsl-host-relay`. The normal tray app gets User-scope `OLLAMA_HOST=0.0.0.0:<port>`; a detected Windows service gets Machine scope. Ollama is then relaunched/restarted and verified.
- The installer-owned Windows Firewall rule is restricted to the WSL-facing interface (or its exact host address fallback), `LocalSubnet4`, the selected Ollama TCP port, and all Windows network profiles so Public-profile hosts do not need a second broad rule.
- `OLLAMA_ORIGINS` is not changed. It is a browser-origin/CORS setting and is not needed by Hermes/Honcho's server-side Ollama requests.
- Previous environment/firewall state is recorded and restored only when it is still installer-owned; later manual `OLLAMA_HOST` changes are preserved.
- Containers never consume the Windows NAT address directly. `native-ollama-relay.sh` discovers the current WSL default-route gateway at start and exposes the verified target only through Docker's WSL host-gateway interface. No `~/.bashrc` mutation is required.

This directory contains the complete inspectable installer implementation. The recommended public entry point is `../installer/Install-LatticeVale.ps1`, which verifies `../installer/SOURCE-SHA256SUMS.txt` and then invokes the core `Install-LatticeVale.ps1`. The older `../installer/install.ps1` launcher remains included for backward compatibility.

## v14.3.17 changes

- Machine-readable WSL networking discovery now invokes `wslinfo` and `ip` directly through `wsl.exe`; route/address parsing happens in PowerShell instead of nested `bash -lc`/`awk` probes.
- Standard NAT output of the form `default via <Windows-host-IP> dev <interface>` is parsed generically, with support for multiple default routes. Candidates still require the existing WSL-scoped TCP proof before they are accepted.
- The long-lived Windows native-service relay uses the same direct route parser after WSL restarts, while the v14.3.16 WSL/Hyper-V adapter fallback remains intact.
- Corrected backslash accounting in the relay's Windows argv serializer to match the already-hardened core helper.
- Native Windows Ollama remains entirely on Windows for model execution/GPU ownership; WSL/Docker only reaches its API through the verified relay. No WSL Ollama installation is required for native mode.

## v14.3.16 changes

- NAT native-Ollama bridging no longer depends solely on the WSL default-route next hop. The Windows-side installer can correlate WSL/Hyper-V virtual-adapter IPv4 addresses with the selected distro subnet and validates the candidate using a temporary WSL-scoped TCP probe.
- The selected Windows-host address is persisted for native gateway transport and reused by configure/start/manage paths, while the Windows relay helper independently retains adapter-based rediscovery for restart resilience.
- Native Ollama application discovery adds a bounded one-level scan of standard application roots for Ollama-named folders; no whole-drive/user-data recursive scan is performed.

## v14.3.16 changes

- Native Windows Ollama relay capability no longer assumes WSL must expose Windows as the IPv4 default-route gateway. Setup queries the current WSL networking mode when `wslinfo` is available and proves the actual path end to end.
- The existing NAT-style Windows scheduled relay remains available when a Windows-host gateway can be verified. When WSL can directly reach the already-verified Windows Ollama API through IPv4 localhost, LatticeVale selects a separate `wsl-localhost-relay` transport.
- The preferred `wsl-localhost-relay` binds only Docker's local host-gateway interface and forwards only to the verified Windows IPv4-loopback Ollama endpoint. It never binds the relay itself to `0.0.0.0` or changes `OLLAMA_HOST`. The v14.3.18 `wsl-host-relay` fallback is separate and requires explicit consent plus a scoped Windows firewall rule.
- Configure, startup, `manage.sh`, state audit, repair, and model-pull paths consume the persisted transport instead of independently assuming a NAT gateway.
- VirtioProxy/other unsupported topologies receive mode-specific diagnostics when neither gateway nor localhost access can be verified; LatticeVale does not automatically change global WSL networking for Ollama.
- A requested Tailscale NAT migration cannot silently invalidate a native Ollama localhost transport; setup requires an explicit conflict decision before changing global WSL networking.

## v14.3.14 changes

- Native Windows Ollama questionnaire status now separates installation discovery, local API readiness, and WSL relay readiness instead of collapsing them into one unavailable state.
- Native Ollama must be running before its local API can be used. Choosing the native backend re-detects the Windows installation, offers to start an installed-but-stopped copy with explicit consent, re-probes `/api/version`, then re-runs the WSL relay capability check.
- If the API is healthy but the relay check fails, setup prints that relay reason and explicitly states that reopening Ollama will not fix a networking-topology failure.
- Native backend selection still never silently falls back to managed WSL/Docker Ollama.

## v14.3.13 changes

- Removed all non-ASCII punctuation from shipped PowerShell runtime source so Windows PowerShell 5.1 never has to infer Unicode encoding for `.ps1` files.
- Release-manifest verification now rejects any shipped `.ps1`, `.psm1`, or `.psd1` containing bytes outside ASCII before the core installer is invoked.
- Windows CI now discovers every shipped PowerShell source file dynamically, enforces the same byte-safety rule, and parses every file under both Windows PowerShell 5.1 and PowerShell 7.
- Added deterministic regression coverage for the exact UTF-8-no-BOM / Windows PowerShell 5.1 parser failure class.

## v14.3.12 changes

- Ollama-dependent setup now asks directly where Ollama should run: verified native Windows Ollama, or LatticeVale-managed WSL/Docker Ollama.
- Native mode is never silently substituted with managed mode if detection/API/relay validation fails; the user must explicitly choose another backend or correct native availability.
- Native mode excludes the `local-ai` Compose profile, does not create new `data/ollama` model storage, and update/pull paths are scoped to selected services so the managed Ollama image cannot be pulled as an unrelated side effect.
- Existing repair/resume backend selections remain preservation-first; explicit backend selection is used for fresh/component-change questionnaires.

## v14.3.11 changes

- Native Windows Ollama installation discovery no longer depends on one fixed binary path or an already-responsive `127.0.0.1:11434` API. Detection checks current/persisted PATH scopes, standard locations, Add/Remove Programs metadata for custom `/DIR` installs, and running process executable paths.
- `Installed`, native API readiness, and WSL relay readiness are tracked independently. An installed-but-stopped copy is reported as installed rather than absent.
- When an installed copy is stopped, the questionnaire can explicitly launch the existing Ollama app (or `ollama serve` when only the CLI is available) and re-probe it without installing/updating/reconfiguring Ollama or changing its startup policy.
- Loopback `OLLAMA_HOST` overrides are probed, and the installer-owned relay targets the exact verified local address/port rather than hard-coding `127.0.0.1:11434`. Non-loopback host configuration is recognized but is not adopted as the relay target.

## v14.3.10 changes

- Recognized managed repairs use a 30-day targeted package/image refresh interval plus an explicit managed-refresh policy revision. Legacy stacks without a valid refresh marker refresh once on adoption, and a revision change forces an immediate bounded pass when package/image/source policy changes. A bundle-version change alone does not force refresh; this prevents audit/docs-only releases from rebuilding healthy components.
- Due refreshes update APT metadata and only LatticeVale prerequisite + official Docker packages; no blanket Ubuntu upgrade is performed.
- A pending refresh forces current installer-owned config/image pins, selected infrastructure pulls/builds, Hermes image pull, and Hermes profile/container replay even when the old runtime is healthy.
- Root package and user-level image refresh are interruption-safe phases; a pending marker lets Resume finish the latter without repeating the former, and success is timestamped only after infrastructure/Hermes verification.
- Existing custom image/source overrides and complete newer NVIDIA Container Toolkit installs remain preserved.

## v14.3.9 changes

- Secondary-profile Matrix resources are provisioned deterministically, then left `pending-manual` instead of making install success depend on Hermes consuming the invite.
- `./manage.sh matrix-profile-finish <profile>` is the explicit bounded completion command; ordinary lifecycle operations skip pending profiles.
- v14.3.8 `complete` records whose bot never joined are preserved and reclassified to `pending-manual` without identity/token/room replacement.
- `MATRIX-SECONDARY-PROFILES.txt` provides a non-secret instance-specific handoff.
- All historical patch/version notes are consolidated into `../docs/CHANGELOG.md`; versioned audit/hotfix files were removed.

## v14.3.8 changes

- Matrix provisioning explicitly starts `synapse-db` + `synapse` and requires both `/health` and `/_matrix/client/versions` before bootstrap/profile room operations.
- Secondary/default bot join polling is bounded and health-aware. A sustained Matrix outage triggers one automatic installer-managed Synapse restart/retry; a second failure stops cleanly with resumable identity/room state instead of looping.
- LatticeVale-created rooms are pinned to Matrix room version `10`, Synapse `default_room_version` is pinned to `10`, and actual room creation is verified from `m.room.create` state.
- Older installer-managed non-v10 rooms are never downgraded in place. Repair backs up installer metadata, preserves the prior room and bot identity/token, and creates a replacement encrypted v10 room. Explicitly adopted existing rooms remain user-owned and are not silently replaced.
- Matrix readiness is rechecked after interactive admin authentication so provisioning does not assume the service stayed online while waiting for user input.

## v14.3.7 changes

- Named-profile gateway safety checks use the exact `/run/service/gateway-<profile>` s6 slot instead of parsing `hermes ... gateway status` text.
- New-profile credential handoff uses a bounded exact-slot quiesce helper: Hermes stop, exact `s6-svc -d`, then exact-PID TERM/KILL only if the same named service remains alive.
- Matrix profile runtime verification uses the same exact s6 state, preventing cross-profile status false positives.
- `manage.sh` start/restart reconciliation uses the exact named s6 service too, so the same status ambiguity cannot reappear after installation.
- Existing profile directories from an interrupted v14.3.6 run are preserved and resumed.
- Release CI/static validation discovers and validates all shipped PowerShell files, including `LatticeVale-WindowsNativeServiceRelay.ps1`.

## v14.3.6 changes

- First Matrix bootstrap now reads not-yet-created bot state with a pipefail-safe optional env reader, preventing the exit-2 abort immediately after admin password confirmation.
- Resume / repair reuses the one-time Matrix bootstrap credential handoff if the prior run stopped before bot state was written.
- Optional state reads in `manage.sh` and the stable-room capability fallback are hardened against the same strict-shell failure class.

## v14.3.5 changes

- Before bootstrap, LatticeVale probes GPU prerequisites inside the selected Ubuntu distro instead of inferring them from Windows hardware.
- Resume / repair with an unavailable saved forced `amd`/`nvidia` Ollama policy now asks explicitly for Auto, CPU, or stop-without-changing-state; it does not proceed to a predictable `prepare_config` failure.
- Fresh/reconfigure setup labels unavailable forced GPU choices and refuses them until the selected distro passes the corresponding probe. Auto remains the non-forcing policy and may resolve to CPU.
- The currently managed AMD Ollama Docker path requires x86_64 + `/dev/kfd` + `/dev/dri`; `/dev/dxg` alone is surfaced diagnostically but is not treated as equivalent container readiness. NVIDIA selection requires `/dev/dxg` + working WSL `nvidia-smi`; Docker runtime verification/configuration still occurs later.
- `explicit` questionnaire mode is preserved when v14.3.4+ saved state is loaded. Linux forced-mode validation remains the final defense if GPU state changes after the Windows-side probe.
- If native Windows Ollama is already running, LatticeVale probes both `127.0.0.1:11434/api/version` and the selected distro's current Windows-host route before offering `ollamaBackend=windows-native`. The relay binds only that Windows-host interface, scopes its firewall rule to the selected WSL IPv4, and self-tests from WSL before bootstrap continues.
- Native mode disables the managed `local-ai` Compose profile, maps `windows.host` into Hermes/Honcho, refreshes the relay before consumer startup, and pulls missing selected model tags through `/api/pull`. Native Ollama's install/update/runtime/GPU settings remain outside LatticeVale ownership.

## v14.3.4 changes

- Fresh installs use an explicit questionnaire instead of the v14.3.0 Quick Setup defaults for host/system-affecting choices. Saved settings may still be reused during repair/change operations.
- Single eligible distro/user selections are explicitly confirmed; Linux home paths and Ubuntu timezone are detected rather than guessed; no fallback Obsidian Documents-folder vault is invented.
- Global WSL lifetime/network changes are never silently forced. Remote Tailscale exposure warns when the selected lifetime policy may make endpoints transient.
- Legacy `~/hermes-stack/vault` mount/symlink state is inspected before bootstrap. Detachment requires explicit consent and never deletes source data; the managed local vault directory is recreated with the selected UID/GID. `configure-stack.sh` refuses to `chmod` through a remaining symlink or mountpoint.
- Schema 16 accepts `explicit` while retaining legacy `quick` and `custom` saved values.

## v14.3.3 changes

- Fresh Matrix setup no longer offers an existing secondary-profile room unless an installer-managed Synapse deployment is already present.
- When Matrix is not yet provisioned, the installer records `roomMode = create` and creates the private encrypted profile room later in the normal Matrix provisioning stage.
- v14.3.2 native-process/WSL and v14.3.1 StrictMode fixes are retained.

### Retained v14.3.2 native-process changes

- Replaced exit-code-sensitive `Start-Process -PassThru` paths with directly owned `System.Diagnostics.Process` objects. The bounded capture helper, passthrough helper, interactive WSL installer launcher, and native WSL relay no longer depend on host-specific `Start-Process` process-wrapper state.
- Fixes a preflight false negative where `wsl --list --quiet` returned a valid distro name such as `Ubuntu-24.04`, but an unavailable/null `ExitCode` caused the result to be treated as failure.
- Redirected stdout/stderr are drained concurrently before process completion to preserve bounded execution without pipe-buffer deadlocks.
- Added a deterministic v14.3.2 regression guard; no install-state schema, WSL ownership policy, Docker/service topology, repair semantics, or user data handling changed.

## v14.3.1 changes

- Fixed startup under the documented `../installer/install.ps1` launcher: the dot-sourced source-manifest verifier no longer leaks StrictMode 2.0 into the core installer, and the core installer initializes its lazy compatibility cache defensively before preflight reads it.
- Added a deterministic regression guard for this exact StrictMode/cache initialization failure. No install-state schema, clean-install, repair, WSL, Docker, or service behavior changed.

## v14.3.0 changes

- Added Quick-vs-Custom fresh-install questionnaire modes backed by the same saved option schema; Quick uses conservative defaults and asks only the core AI-provider choice.
- NVIDIA toolkit setup now preserves a complete installed toolkit newer than the tested 1.20.0-1 set and fails closed on mixed newer/older package state instead of allowing an automatic downgrade.
- `manage.sh status`/successful `verify` now show offline image-pin age, hardware/resource context, advisory VRAM pressure, and loaded-model `ollama ps` CPU/GPU evidence when available.
- `manage.sh backup` prints a sensitive-backup/encryption reminder without adding a new crypto dependency or secret-handling surface.

- Added persisted Ollama acceleration policy: Auto, CPU, NVIDIA, or AMD/ROCm. Auto falls back to CPU when acceleration prerequisites cannot be verified; forced GPU modes fail closed.
- Adaptive per-service CPU/RAM ceilings are optional and `compose.override.yaml` remains the final user override layer. Policy v4 retains the v14.4.5 reserve, allocator, Synapse-cache, and PostgreSQL tuning while increasing managed Ollama's protected minimum when the same aggregate budget safely permits it. Repair/start automatically migrates enabled older policy overlays.
- Replaced floating Ollama/SearXNG defaults with tested versioned image tags while preserving explicit image choices on ordinary repair.
- Consolidated release path-safety/source-manifest verification into repository-root `tools/ReleaseManifest.ps1`, shared by the launcher, verifier, and manifest generator.
- Added explicit Honcho AGPL-3.0 network-use guidance to `../docs/THIRD-PARTY-NOTICES.md`.
- Per-profile Matrix intent is stored inside each installer-selected worker/profile object.
- Any valid user-selected profile name can receive a matching `@<profile>:hermes.local` identity and dedicated encrypted room.
- Matrix provisioning is ordered after profile/model configuration; both cloned and independently selected profile models are verified before a profile gateway starts.
- Secondary profiles use independent Matrix credentials/device/recovery state and independently supervised Docker/s6 gateways.
- `gateway.multiplex_profiles` stays disabled for the LatticeVale-managed topology.
- The initial questionnaire asks for the Windows-local Obsidian vault path when Obsidian is selected.
- Resume / repair migrates older worker definitions conservatively; it does not create new secondary Matrix identities without explicit user intent.
- The human Matrix admin password is no longer stored as a long-lived profile-management secret.
- Administrator-managed Synapse registration settings are preserved; LatticeVale removes only registration state it can prove it created.
- Public-release files now include a security policy, source-hash verification, CI validation, and organized public entry points under `../installer/`.
- Optional Windows Start/Shutdown shortcuts are generated per distro/Linux user and dispatch through `manage.sh`, so they follow that install's saved component/profile choices.

See `../docs/CHANGELOG.md` for all patch/version history and `AUDIT.md` for general audit invariants.

## Architecture

```text
Windows Administrator PowerShell
  -> Install-LatticeVale.ps1
  -> existing Ubuntu WSL2 distro
       -> /home/<user>/hermes-stack
       -> rootful Docker Engine + Compose
            -> hermes-agent
            -> Synapse + PostgreSQL
            -> Dashboard
            -> SearXNG + Valkey
            -> QMD
            -> Honcho + PostgreSQL/pgvector + Redis
            -> Ollama
```

Windows Tailscale integration stays Windows-native. The managed design does not install Tailscale inside WSL, does not use `netsh portproxy` as the active Matrix bridge, and does not use public Funnel as the default.

## Supported WSL boundary and release requirements

LatticeVale requires an existing working WSL2 Ubuntu distro. It does not install/import/unregister/convert/move/repair WSL distros. The executable compatibility policy is centralized in `compatibility.conf`. The distributed release currently requires x64/AMD64 Windows (build 19041+) and an amd64/x86_64 Ubuntu 22.04, 24.04, or 26.04 WSL2 distro. A normal non-root Linux user with sudo access, Windows Administrator access, Internet access for selected downloads, and the documented clean-install storage reserve are also required.

## Customization / downstream forks

The LatticeVale source and documentation are MIT-licensed and may be modified or forked for a specific system. The official compatibility policy is a tested baseline, not a technical prohibition on downstream changes. If a fork expands or narrows the target platform, change `compatibility.conf`, tests, and documentation together; do not merely suppress preflight blockers. Regenerate the repository source manifest after edits, clearly identify redistributed builds as modified, and keep generated credentials/runtime state out of source control. Third-party dependencies keep their upstream licenses.

## Main files

- `Install-LatticeVale.ps1` — Windows questionnaire, prerequisite checks, repair detection, state handoff, Windows integrations.
- `../tools/Reset-LatticeVale-CleanHost.ps1` — explicit Administrator-only, dry-run-first clean WSL/LatticeVale host reset; never invoked automatically.
- `Uninstall-LatticeVale.ps1` — conservative removal of installer-owned runtime/integrations, with preserve-data and explicitly confirmed full-purge modes. v14.4.5 retains the v14.4.4 behavior that aborts if runtime may remain while Docker is unavailable, preserves helper/config files referenced by retained tasks/shortcuts, broadcasts restored installer-owned `OLLAMA_HOST`, and avoids deleting shared distro-level state while another recognizable LatticeVale stack remains.
- `linux/bootstrap.sh` — WSL bootstrap/recovery entry.
- `stack/configure-stack.sh` — deterministic stack creation/reconciliation and staged repair logic.
- `stack/compose.yaml` — managed Compose topology.
- `stack/manage.sh` — lifecycle, verify, backup, update, profile/Matrix status.
- `stack/state-audit.py` — read-only structured state audit.
- `windows/LatticeVale-WslNativeRelay.ps1` — Windows-native relay for selected private Tailscale exposure.
- `windows/LatticeVale-WindowsNativeServiceRelay.ps1` — optional WSL-only relay to a verified native Windows Ollama API; no native Ollama reconfiguration.
- `windows/LatticeVale-Shortcut.ps1` — inspectable current-user Start/Shutdown shortcut launcher; shutdown stops the managed stack but intentionally leaves the selected WSL distro running.
- `tests/` — static and historical regression fixtures.

## Repair and update policy

For v14.4.84 existing-install repair, use **Shut Down LatticeVale** only to stop the managed stack; do not use targeted `wsl --terminate`. If the installer detects a legacy LatticeVale-owned shutdown helper, Resume / repair performs its own bounded `wsl --shutdown` + `WslService` transport reset before replacing that helper.

Resume / repair is broad reconciliation but preservation-first. It can repair generated config, permissions, helpers, Compose state, Matrix/Tailscale integration, bounded Docker/APT residue, log retention, database maintenance, and stale adaptive runtime/RAM policy. It does not routinely delete profiles, memories, sessions, Matrix state, databases, Docker volumes, models, or vault files. Managed package/image/source refresh occurs when the periodic refresh is due, the managed-refresh policy revision changes, legacy refresh state is missing, or explicit Update / repair forces it; a bundle-version change alone remains local-first. If adaptive policy is regenerated, Compose reconciliation is forced before repair can report success.

The Windows installer also exposes **Update / repair installer-managed software** for an existing managed stack. That mode requires a successful pre-update `manage.sh backup`, bypasses the age gate, forces the current bundle's managed refresh, and then executes the normal stage verifiers. It is the reproducible way to apply component-version changes shipped by a newer LatticeVale bundle. Fixed pins such as Hermes/Synapse only advance when the bundle declares a different pin; installer-owned SearXNG/Ollama pins and the audited Honcho commit advance only across proven ownership boundaries. Explicit user overrides and separately owned native Windows Ollama remain outside that updater.

`./manage.sh update` is intentionally different: it is an advanced upstream refresh of the **currently configured** references and may advance Honcho to repository `HEAD`. It is not the bundle-pinned update path.

## Matrix/profile rules

- Default Matrix identity remains separate from named profiles.
- Named Matrix-enabled profiles must have unique credentials.
- Matrix localpart follows the installer-selected profile name.
- A profile must have a real configured model before its Matrix gateway can start.
- No `matrix2`/`matrix3` pseudo-platform namespaces are generated.
- Existing unknown/manual profile Matrix config is not silently overwritten.
- Installer-created Matrix rooms use room version `10`; adopted existing rooms keep their owner-selected version.
- An older installer-managed non-v10 room is preserved and replaced with a managed encrypted v10 room rather than modified in place.
- E2EE recovery/device state is unique per profile.
- Managed secondary gateways use Hermes's Docker/s6 profile supervision.


## Windows Start/Shutdown shortcuts

The optional `windowsShortcuts` install option creates two current-user desktop `.lnk` files after the Linux stack and Windows integrations have reconciled. Their generated config records the exact WSL distro, selected Linux user, and managed stack path.

The Start action first checks native Windows Ollama when that backend is selected: if its recorded local API is already healthy it is left untouched; otherwise a recorded custom service is started when applicable or the recorded tray application is launched, and the API must become ready before WSL startup continues. It then invokes the installer-owned root `/usr/local/sbin/hermes-stack-start` helper to make Docker available without an interactive sudo prompt, followed by `./manage.sh start` as the selected Linux user. `manage.sh` reads `install-options.json`, so the shortcut automatically follows the services/profile gateways/Tailscale relay selected for that installation.

The Shut Down action does not issue global `wsl --shutdown` and no longer issues targeted `wsl --terminate`. It checks `wsl --list --running`, returns successfully if that distro is already stopped, otherwise runs `./manage.sh stop` and leaves the distro running. Same-name shortcuts are overwritten/removed only when their target and arguments prove they are installer-owned for the exact generated configuration.

## Obsidian/QMD rule

Native Windows Obsidian uses a Windows-local drive vault. LatticeVale translates only the Windows drive root through WSL (so the distro's configured automount root is respected), appends the normalized relative path lexically to avoid canonicalizing through an existing legacy bind mount, and verifies the result is Windows-backed storage with `findmnt`. `/vault` is not recursively chowned/chmodded when it is Windows-backed.

## Validation

Run from this directory:

```bash
python3 tests/static-audit.py
bash -n linux/bootstrap.sh stack/configure-stack.sh stack/manage.sh stack/qmd-index-cycle.sh
python3 -m py_compile stack/state-audit.py stack/patch-qmd-bind.py tests/*.py
```

The top-level GitHub Actions workflow adds Windows PowerShell parser validation. Real Windows+WSL+Tailscale+Element lifecycle testing remains an integration requirement outside static/container fixtures.

## Existing WSL prerequisite

LatticeVale does **not** install or create WSL. It requires an existing **Ubuntu WSL2** distribution that is already installed, launches successfully, and is eligible for the installer. For the supported storage preflight, the selected distro must be backed by **OVER 50 GB total capacity** and report **at least 50 GB free** before a clean installation.

## Repair-state authority

Repair checkpoints are recorded in `.installer-state.json`, but they never override live validation. **The state file is only a hint**: repair stages still verify the components they own and rerun required migrations when the installed release changes.

## Canonical installation / repair order

v14.3.2 keeps the established default-profile ordering and adds secondary-profile Matrix only after each named profile is model-ready:

1. prepare installer-owned configuration and secrets;
2. start and verify selected supporting Docker infrastructure;
3. **bootstrap and verify Matrix before Hermes setup** for the default profile when Matrix is selected;
4. configure and verify the default Hermes provider/model;
5. create/repair each named secondary profile and finish that profile's cloned or independently selected model;
6. only then provision that same profile's optional Matrix identity/room and profile gateway;
7. reconcile optional services, health, Windows relay/Tailscale exposure, and final metadata.

This ordering prevents a secondary Matrix room from binding to an incompletely configured profile or to a default-model fallback.

Hermes provider/model selection therefore does **not** run before a selected Matrix homeserver for the default profile; secondary-profile Matrix provisioning is additionally delayed until that named profile has its own configured model.

## After the installer finishes

A successful run means the selected Linux stack passed its installation-time checks. From WSL, use:

```bash
cd ~/hermes-stack
./manage.sh verify
```

`verify` is the definitive readiness check; `./manage.sh status` is the quick snapshot and `./manage.sh audit` shows repair-oriented state. Windows-only Tailscale/relay or optional-app follow-ups remain separate from Linux stack health.

## Compatibility and setup notes

- Supported host scope includes **Windows 10/11 client** systems with the stack on a **Linux-native filesystem** inside the selected existing Ubuntu WSL2 distro. A **fresh/unmanaged install** is handled separately from **Resume / repair**.
- LatticeVale uses its own Docker Engine in WSL; do not mix this stack with **Docker Desktop WSL integration** for the same daemon/data path. See **Local ports and Docker namespace** below when troubleshooting conflicts.
- **Windows Tailscale** is an optional Windows-side integration. Ubuntu Pro is not a LatticeVale install/configuration option; any externally configured Ubuntu Pro state remains user-owned.
- **SearXNG itself is local**; its normal external search-engine requests remain network activity by design.
- Browser setup should choose **Local browser** rather than Browser Use cloud when the installer configures the local/self-hosted path.
- **Default profile:** uses the installer-selected provider/model and the default Matrix identity when Matrix is enabled.
- **Secondary profiles:** may clone the default provider/model or select an independent model. Optional Matrix provisioning is attached to that exact named profile only after its configured model verifies.
- **OpenCode Go:** when selected as a provider path, its model/provider setup remains profile-scoped rather than a Matrix-routing shortcut.
- Internal Matrix homeserver URL: `http://synapse:8008`; default bot identity: `@hermes:hermes.local`.
- `./manage.sh matrix-credentials` prints the retained default-bot credential summary; treat its output as sensitive.
- Multi-profile gateways keep `gateway.multiplex_profiles: false` and use the upstream **one-process-per-profile** supervision model. Matrix-enabled profiles receive independent credentials and gateway processes.

### Local ports and Docker namespace

LatticeVale binds only its documented host ports and uses the installer-owned Compose project/network. Existing unrelated containers and volumes are not treated as disposable repair targets.

## Historical repair baseline

The **v13.16.0 repair maintenance** design remains part of v14: bounded cleanup/logging/database maintenance is preservation-first, and later v13.16.x hardening remains the compatibility baseline rather than being replaced by the new profile-Matrix features.


Detailed v14.x implementation and audit history is consolidated in `../docs/PATCH-NOTES.md`; `../docs/CHANGELOG.md` remains canonical for release chronology.
