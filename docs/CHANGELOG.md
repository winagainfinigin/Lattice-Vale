# Changelog

## 14.4.83 - 2026-08-27

- Advances adaptive container resource policy from v3 to **v4**. The aggregate WSL-visible container budget and host/kernel/Docker reserve remain unchanged, but managed Ollama now receives up to a 4096 MiB protected minimum when enough budget remains after the established minima for all other enabled services. Constrained allocations continue to scale coherently instead of consuming the non-container reserve.
- Makes policy v4 a clean-install and repair/start convergence requirement. Existing adaptive policy-v3 state is detected as stale by `configure-stack.sh`, `manage.sh`, the root stack-start helper, and `state-audit.py`, then regenerated through the existing preservation-first Compose reconciliation path.
- Adds a root-owned `/etc/sysctl.d/99-latticevale-redis-valkey.conf` prerequisite for selected LatticeVale-managed SearXNG/Valkey or Honcho/Redis workloads and applies/verifies `vm.overcommit_memory=1` on both clean install and Resume / repair. Disabling those services does not destructively reset a sysctl value that another application may also use.
- Removes the Ubuntu Pro for WSL option from the installer questionnaire, persisted LatticeVale options, Windows add-on installation/audit flow, current documentation, and regression expectations. Existing external Ubuntu Pro packages/attachment/state are deliberately left untouched.
- Fixes installer completion and README verification/audit/status commands to specify both the selected WSL distro and selected Linux user before resolving `$HOME/hermes-stack`.
- Adds `v14.4.83-runtime-policy-overcommit-ubuntu-pro-fixtures.py` and updates release identity/manifest coverage without changing unrelated service pins, Hermes model/prompt policy, Tailscale topology, WSL distro ownership, or clean/repair storage thresholds.

## 14.4.82 - 2026-08-21

- Fixes the v14.4.81 bounded WSL recovery wrapper so helper diagnostics are displayed through `Out-Host` instead of being returned through the function success stream. The caller now receives only the scalar native process exit code.
- A successful `wsl --shutdown` recovery (`exit 0`) now follows the already-designed same-run path: re-probe the same registered distro, then apply the unchanged Ubuntu/architecture/storage/managed-stack eligibility rules.
- Preserves the v14.4.81 safety boundary and storage contract: no distro/VHDX mutation, no automatic DISM/feature repair, 50 GiB free for a true fresh install, and 10 GiB free for a confirmed existing installer-managed Resume / repair.
- Adds `v14.4.82-wsl-helper-exitcode-fixtures.py`; no service, image, package, dependency, Hermes policy, networking policy, or integration revision changes.

## 14.4.81 - 2026-08-21

- Fixes the WSL preflight dead end where a registered Ubuntu WSL2 distro reports `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure`: when that distro is required or explicitly selected, the installer can invoke a bounded preservation-first host recovery and then fully re-probe eligibility in the same run.
- Recovery first performs a bounded `wsl --shutdown`, waits for WSL to settle, and re-tests the same distro without changing registration, the VHDX, Windows features, or `.wslconfig`.
- If `E_UNEXPECTED` persists **and** `.wslconfig` explicitly selects mirrored networking, the installer can offer an explicit default-No NAT compatibility recovery. The helper backs up `.wslconfig`, changes only `[wsl2] networkingMode` to `nat`, preserves unrelated settings, restarts WSL, and retests the same distro.
- The bounded shutdown/re-probe path can run from the normal installer without elevation; the normal installer does not automatically escalate into DISM or Windows-feature mutation. Deeper host repair remains an explicit Administrator-helper action.
- Other running WSL distros are detected before the global shutdown step; the user must explicitly approve temporarily stopping them. If running-distro enumeration itself fails, LatticeVale treats the state as unknown and asks before global shutdown rather than assuming no unrelated distro is active. An explicitly requested broken `-DistroName` receives recovery even when another registered distro is healthy.
- After a successful WSL recovery, the installer re-runs normal Ubuntu/version/architecture/storage/managed-stack checks. Fresh-install and managed-repair storage thresholds are unchanged.
- Adds `v14.4.81-wsl-launch-recovery-fixtures.py` and updates current release/test/documentation identity without adding any runtime service, image, package, API key, port, model-policy change, or third-party dependency.

## 14.4.8 - 2026-08-21

- Fresh and repaired installer-managed Hermes profiles fill the free Local Browser / Chromium choice only when no explicit browser backend/provider, gateway route, or recognized browser environment selection already exists; missing `auxiliary.web_extract.timeout` becomes `360`, while explicit browser/provider/timeout choices remain user-owned. This does not modify `SOUL.md`, prompts, or model policy.
- Advances the installer-owned integrations checkpoint from revision 3 to 4 for that reliability migration without advancing the managed package/image/source refresh revision or forcing a version-only managed refresh.
- Fixes the Linux static audit so a missing ordering marker produces an ordinary audit failure instead of an uncaught substring exception.
- Normalizes release-manifest path handling so the strict source-manifest verifier resolves portable manifest paths consistently across supported PowerShell environments while retaining missing-file, coverage, encoding, and hash validation.
- Consolidates the current v14.x one-off patch-note documents into [`PATCH-NOTES.md`](PATCH-NOTES.md), updates the current documentation set and official troubleshooting links, and leaves the v13 archive intact.
- Inherits v14.4.7's SearXNG + bounded `latticevale-local` extraction design unchanged; no new service, image, package, paid provider, API key, listener, resource reservation, or user-policy ownership is introduced.

## 14.4.7 - 2026-08-21

- Fixes the default Hermes web-research integration gap: SearXNG remains the keyless `web_search` backend while managed profiles receive a generated `latticevale-local` `web_extract` provider for public HTTP(S) text content.
- Adds no container, image, package, API key, listener, Windows networking change, or resource reservation. This avoids the substantial service/resource footprint of self-hosted extraction stacks while retaining the existing stable SearXNG topology.
- Preserves explicit user `web.backend` / `web.extract_backend` choices. The local extractor is selected only when the effective shared/extract choice is empty or SearXNG.
- Hardens local extraction against SSRF-style access: non-HTTP(S), credential-bearing, loopback/private/link-local/reserved/non-global destinations are rejected; each redirect is revalidated; environment proxy inheritance is disabled; redirect, response-byte, timeout, and output sizes are bounded.
- The original extraction change advanced the installer-owned integrations checkpoint from 2 to 3 so Resume / repair could migrate existing managed profiles without forcing package/image/source refresh; v14.4.8 advances it again to 4 for the missing browser/timeout defaults.
- Adds `v14.4.7-web-extraction-fixtures.py` and documents the implementation/security/migration contract in [`PATCH-NOTES.md`](PATCH-NOTES.md).
- Clarifies repair/update preparation across current documentation: fully stop the selected LatticeVale WSL distro before launching Option 1 Resume / repair or Option 6 Update / repair. When installed, **Shut Down LatticeVale** is the recommended method because it stops the managed stack and terminates only that distro; global `wsl --shutdown` is not required.
- Documents the remaining SearXNG operational boundary: external engines may temporarily rate-limit/CAPTCHA/suspend automated requests, so a successful `web_search` call can return zero results without indicating a broken LatticeVale installation. Known public URLs remain independently readable through v14.4.7 `web_extract`; support/test guidance now distinguishes upstream empty-result conditions from local provider/service failures.

## 14.4.6 - 2026-08-20

- Fixes `state-audit.py` adaptive-resource CPU fingerprinting on processor-limited WSL instances.
- Uses process-visible CPU affinity (`os.sched_getaffinity(0)`) first, then `nproc`, matching the CPU semantics used by the policy-v3 generator and `manage.sh` refresh path.
- Prevents false `runtimePolicy PARTIAL` / `NEEDS_REPAIR` when the Windows host exposes more logical CPUs than WSL is configured to use.
- Keeps RAM fingerprint comparison exact; the observed failure reproduced with identical saved/live RAM and was CPU-count divergence, not memory jitter.
- Refines v14.4.5 managed-update behavior so a bundle-version change alone no longer forces APT refreshes, image pulls, or QMD/Honcho rebuilds. Automatic Resume / repair refresh is controlled by the 30-day gate, `MANAGED_REPAIR_REFRESH_REVISION`, missing legacy refresh state, or explicit Option 6.
- Keeps `INSTALLER_VERSION` in successful/pending refresh markers for provenance, but a pending marker at the current refresh revision can resume across a version-only bundle change without repeating completed root package work. A revision mismatch still reruns the bounded root phase.
- Preserves direct public 14.4.2→14.4.6 upgrade behavior: 14.4.2 uses refresh revision 1/resource policy v2, while 14.4.6 uses revision 2/policy v3, so Option 1 performs the required cumulative managed refresh and RAM-policy reconciliation. A recently refreshed 14.4.5→14.4.6 upgrade remains local-first unless another real trigger applies.
- Adds deterministic regression coverage for both the CPU-count mismatch and the 14.4.2-vs-14.4.5 upgrade-trigger distinction.
- Inherits v14.4.5 runtime-policy convergence and all prior preservation boundaries.

## 14.4.5 - 2026-08-20

- Fixes Resume / repair leaving adaptive RAM/resource policy v3 `PARTIAL` when an older completed `prepare_config` checkpoint caused the policy generator to be skipped.
- Adds an explicit uncheckpointed repair-time runtime-policy reconciliation that verifies the policy-v3 CPU/RAM fingerprint and RAM-specific allocator, Synapse-cache, and PostgreSQL-buffer controls.
- When the adaptive overlay changes, marks infrastructure and complete-stack reconciliation pending so Compose recreates affected containers and the new limits/environment/commands become live rather than merely existing on disk.
- Adds a final fail-closed runtime-policy verification so configuration cannot report success while the selected adaptive policy is still stale or incomplete.
- Corrects `manage.sh` startup refresh to compare against policy version 3 rather than the obsolete policy-version-2 constant.
- Improves managed component repair semantics: Resume / repair from a different LatticeVale bundle now triggers the bounded installer-owned package/image/source refresh immediately, while repeated repairs on the same bundle remain local-first until the periodic refresh window/policy requires an update. Explicit user-owned image/source and `compose.override.yaml` values remain preserved.
- Advances managed repair refresh-policy revision to 2 and adds v14.4.5 regression coverage for runtime-policy convergence, live-container reconciliation, bundle-version-driven component refresh, and override ordering.
- Makes interrupted managed-refresh markers bundle-aware, so resuming an old pending refresh with a newer bundle safely reruns the bounded root package phase instead of assuming the older bundle already satisfied it.
- **Superseded in v14.4.6:** the version-only refresh predicate from this historical release is replaced by the explicit refresh-revision/age/force model; the v14.4.5 runtime-policy convergence remains current.
- Makes `./manage.sh restart` reconcile Compose when its pre-restart adaptive-policy refresh changed the overlay, preventing a regenerated RAM policy from remaining file-only until a later `up`.
- Retains v14.4.4 live metadata-race hardening and all v14.4.3 RAM/uninstaller preservation behavior.

## 14.4.4 - 2026-08-20

- Fixes Resume / repair aborts caused by transient SQLite WAL/SHM or rotated-log entries disappearing while bootstrap ownership/permission reconciliation is running.
- Replaces the live-tree recursive `chown -R`/`chmod -R` metadata repair with a mount-bounded, symlink-safe snapshot walk that tolerates a failure only when that exact entry has vanished; real ownership/permission failures remain fatal.
- Keeps clean installs unchanged while making existing-stack repair safe when Hermes or another selected service is still writing installer-owned user-data trees.
- Adds deterministic regression coverage for the observed `kanban.db-shm` disappearance race and for fail-closed handling of a still-existing entry whose ownership cannot be changed.
- Advances current release metadata, documentation, CI checks, and the exact source manifest to v14.4.4.

## 14.4.3 - 2026-08-20

- Adds adaptive resource policy v3 for lower avoidable RAM pressure while preserving active-work headroom. WSL-visible memory reserves are increased on constrained hosts, long-lived glibc/Python services receive bounded `MALLOC_ARENA_MAX`, Synapse receives RAM-scaled `SYNAPSE_CACHE_FACTOR`, and managed PostgreSQL stores receive RAM-scaled `shared_buffers`.
- Preserves Honcho PostgreSQL's existing `max_connections=200`; the RAM patch changes only its buffer tuning.
- Applies policy v3 directly on clean installs and migrates enabled older adaptive overlays on repair/start when policy revision or WSL-visible CPU/RAM changes. User `compose.override.yaml` remains the final override layer.
- Deliberately does not write global WSL `memory` or `autoMemoryReclaim` settings; those remain host/user-owned.
- Hardens normal uninstall so it refuses a partial removal when Docker runtime may still exist but the Docker daemon is unavailable.
- Preserves stack-specific shortcut/task helper/config files when an unremoved Windows shortcut or scheduled task still references them, rather than breaking retained state after an ownership check fails.
- Restores installer-owned `OLLAMA_HOST` with an environment-change broadcast, tightens firewall-removal ownership checks, reads uninstall metadata through the root WSL context, supports nonstandard normal Linux home paths when checking for other LatticeVale stacks, and removes the shared dockerd log only when no other recognizable stack remains.
- Updates current documentation, release checks, regression compatibility, and source integrity data for v14.4.3.

## 14.4.2 - 2026-08-20

- Documentation/release-consistency patch over v14.4.1; installer and stack-runtime behavior are unchanged.
- Aligns current-release documentation and regression expectations with the actual `Lattice-Vale` package folder name.
- Advances release/version metadata and inherited regression compatibility to v14.4.2.
- Regenerates the exact source manifest for the updated release tree.

## 14.4.1 - Release-root organization

- Packaging/layout-only patch over the validated v14.4.0 runtime; no intended stack-runtime behavior change.
- Moves public PowerShell entry points and the exact source manifest into `installer/`: `installer/install.ps1`, `installer/uninstall.ps1`, `installer/verify-release.ps1`, and `installer/SOURCE-SHA256SUMS.txt`.
- Consolidates project/operator documentation under `docs/`, while preserving conventional repository metadata (`.gitattributes`, `.gitignore`, `.github/`, the GitHub landing `README.md`, and `LICENSE`) at repository root.
- Updates entry-point path resolution so launchers find `LatticeVale-Core/` and `tools/` from their new `installer/` location and continue verifying the complete extracted release tree.
- Updates clean-host source recognition, WSL-host repair guidance, CI/tests, and all affected documentation for the new layout.
- Adds release-layout regression coverage so future packaging changes cannot silently break the launchers or manifest root.
- Corrects remaining documentation references that still described pre-v14.4.1 root-level entry points, manifest locations, or clean-host source recognition; no runtime behavior changes.

## 14.4.0 - 2026-08-20

Stable promotion of the audited v14.3.43 runtime line. No intended runtime behavior changes.

- Promotes the current stabilization line to the `14.4.0` stable milestone after a successful real-host fresh clean install and a successful v14.3.42 -> v14.3.43 repair/upgrade validation.
- Adds `FEATURES.md` as the canonical consolidated reference for current features, prerequisites, fresh-install choices, existing-install modes, optional integrations, ports, ownership boundaries, and maintenance/recovery options.
- Corrects the clean-host reset documentation so `-RemoveWslRuntime` is explicit about unregistering **all current-user WSL distributions**.
- Corrects fresh-install storage documentation to require both **over 50 GiB total backing-volume capacity** and **at least 50 GiB free**.
- Documents adaptive container CPU/RAM ceilings and timezone as real questionnaire choices.
- Clarifies that an explicit Windows vault path is required by Obsidian integration, not QMD alone.
- Makes the fresh managed-profile `skills.write_approval: false` default prominent while retaining the rule that repair/update preserves an explicit existing choice.
- Enumerates the current Change installed components scopes and Advanced recovery actions in `Instructions.txt`.
- Reduces duplicated patch chronology in the primary README and networking notes so current operator information is easier to find.
- Updates release/version metadata, CI expectations, regression-version compatibility, and source manifest for the stable package.

## 14.3.43 - 2026-08-19

Clean-host Scheduled Task action compatibility correction.

- Fixes `tools/Reset-LatticeVale-CleanHost.ps1` aborting during dry-run when Windows contains a Scheduled Task action type that does not expose Exec-only `Execute`, `Arguments`, or `WorkingDirectory` properties.
- Scheduled Task ownership discovery now reads action properties defensively through `PSObject.Properties`, supporting heterogeneous Task Scheduler actions without weakening ownership checks or deleting unknown tasks.
- Preserves the v14.3.42 destructive boundary: dry-run first, explicit `-Execute` plus `CLEAN-RESET`, no automatic invocation, no Hyper-V/VMP/HNS teardown, no global Tailscale Serve reset, and no standalone `%USERPROFILE%\.hermes` deletion.
- Adds `v14.3.43-scheduled-task-action-compat-fixtures.py` so direct Exec-only property dereferences cannot regress into the clean-host scanner.
- Normal install, Resume / repair, component changes, provider/profile reconfiguration, Advanced recovery, Update / repair, runtime and conservative uninstall code are unchanged.

## 14.3.42 - 2026-08-19

- Adds `tools/Reset-LatticeVale-CleanHost.ps1`, an explicit Administrator-only, dry-run-first utility for users intentionally preparing a machine for a completely fresh WSL + LatticeVale installation. Normal install/repair/update/uninstall behavior is unchanged and never invokes this destructive tool automatically.
- Clean-host reset requires `-Execute` plus exact `CLEAN-RESET` confirmation. `-RemoveWslRuntime` permanently unregisters every WSL distro registered to the current Windows user, removes former registered distro storage, removes global `.wslconfig*` state, and attempts to uninstall the Store/MSI WSL app through `Microsoft.WSL`.
- Windows cleanup is ownership-gated: only LatticeVale/explicit legacy pre-LatticeVale Foundry tasks, relay/helper processes, firewall rules, shortcuts/recent links, AppData/helpers and known PATH entries are eligible. Tailscale Serve is disabled only when the existing listener still references a known LatticeVale bridge backend.
- Shared infrastructure is intentionally preserved: Hyper-V, HypervisorPlatform, VirtualMachinePlatform, HNS networks, Windows Tailscale, Obsidian, unrelated firewall/network state, and standalone `%USERPROFILE%\.hermes` are not removed by the clean-host tool.
- Adds `v14.3.42-clean-host-reset-fixtures.py` and the original detailed clean-host implementation note (now preserved in `PATCH-NOTES.md`); updates Instructions/Description/README/Support/Security/Release/Audit/GitHub metadata to distinguish conservative uninstall from intentional host reset.
- The change is audit-driven: a real host audit showed retained mirrored `.wslconfig`, LatticeVale relay task/process state, legacy pre-LatticeVale Foundry/PATH residue, root shortcuts and registered custom-location WSL storage while also confirming independently installed Tailscale/Obsidian and shared Hyper-V/HNS state that must not be indiscriminately removed.

## 14.3.41 - 2026-08-19

WSL cold-start host-safety and global-networking ownership correction.

Detailed implementation/audit notes: `PATCH-NOTES.md`.

- Removes the remaining normal-installer ability to create, switch, or reapply global WSL `[wsl2] networkingMode=mirrored`. Clean install, Resume / repair, Change components, provider/profile reconfiguration, Advanced recovery, and Update / repair now treat WSL networking mode as host/user-owned.
- Continues to support an already-working externally configured mirrored topology without mutating `.wslconfig`; its saved ownership is recorded as `user-existing-mirrored` rather than installer-owned. NAT/default/VirtioProxy-capable paths remain supported through dynamic/scoped relays and exact firewall rules.
- Removes the native-Windows-Ollama mirrored-mode remediation prompt/fallback. If a safe native-Ollama bridge cannot be verified under the active non-mirrored topology, the installer may use its explicit scoped direct-Ollama fallback or the LatticeVale-managed WSL/Docker Ollama backend instead of changing the global WSL architecture.
- Strengthens `tools/Repair-LatticeVale-WslHost.ps1`: when the selected registered distro fails with `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure` while `.wslconfig` explicitly selects mirrored mode, the helper detects that condition before DISM/feature mutation. With explicit `-ApplyNatFallback`, it backs up `.wslconfig`, changes only `networkingMode` to NAT, preserves unrelated `[wsl2]` and `[general]` settings, performs a bounded WSL shutdown/retry, and retests the same registered distro.
- If the NAT recovery does not restore launch, the helper preserves the backup and continues broader host diagnostics instead of assuming mirrored networking was the sole cause. It never unregisters/imports/moves/converts/deletes a distro or edits its VHDX.
- Retains the independently supported `[general] instanceIdleTimeout=-1` service-lifetime policy; v14.3.41 specifically removes LatticeVale ownership of `networkingMode`, not all documented `.wslconfig` management.
- Updates current instructions, capability description, security/support/release/source/contributor docs, native-Ollama integration guidance, Windows integration test matrix, issue/PR templates, CI release identity checks, and version-aware networking regressions. Historical notes remain historical and are explicitly superseded where they describe the old mirrored fallback.
- Adds `v14.3.41-wsl-host-safety-fixtures.py` to enforce the non-mutating normal-installer boundary, externally-owned mirrored semantics, safe-first helper ordering, and distro/VHDX preservation rules.
- This correction addresses a real migration hazard from earlier downstream builds that could leave global mirrored networking configured. `E_UNEXPECTED` remains a generic WSL host error, so v14.3.41 does not claim mirrored mode is the only possible cause.

## 14.3.40 - Documentation separation and post-install settings guide

- Documentation-only release; no installer/runtime behavior changed from v14.3.39.
- Rewrote `Installer Description.txt` as a plain-language capability and post-install decision guide explaining what LatticeVale configures automatically and which provider/model, profile, Kanban, approvals, skills, Matrix/Element, Tailscale, Ollama, resource, vault, memory, Windows-integration, and update-policy settings may still require user decisions.
- Rewrote `Instructions.txt` as the procedural operator guide for prerequisites, clean install, all existing-install modes, verification, everyday management, provider/profile reconfiguration, Matrix completion, Kanban/skills operation, Ollama, backup/update, troubleshooting, security checks, and uninstall.
- The two documents now intentionally cross-reference rather than duplicate each other: Description = what/why/settings; Instructions = how/when/commands.

## 14.3.39 - 2026-08-19

Existing-install quality-control and shared-Docker preservation release.

- Audits all six existing managed-stack installer choices end-to-end at the source/fixture level: Resume / repair, scoped component changes, verify-only, provider/profile reconfiguration, Advanced recovery, and controlled Update / repair.
- Removes automatic `docker image prune -f` and `docker builder prune` from mutating repair maintenance. Those commands operate at Docker Engine scope and could remove dangling images or old BuildKit cache belonging to unrelated projects that share the selected WSL distro.
- Repair continues to report Docker storage usage, clean bounded APT/LatticeVale staging residue, retain/prune only proven installer configuration snapshots, cap installer event history, and perform the existing preservation-first database maintenance. No automatic volume/container/network/all-unused-image prune is introduced.
- Adds a dedicated v14.3.39 existing-install QC regression covering the six-mode routing, verify-only early exit, scoped-change preservation contract, Matrix recovery backup ordering, mandatory Update / repair backup ordering, persistent-data retention when components are disabled, and the prohibition on engine-global Docker pruning.
- No other installer mode, checkpoint, Matrix, profile, Kanban, networking, update-pin, or component behavior was changed by this QC patch.
- Current bundle/release identity is `14.3.39`.

## 14.3.38 - 2026-08-19

Kanban / skill-management reliability and portability release.

Detailed implementation/audit notes: `PATCH-NOTES.md`.

- Keeps the proven shared-board dispatcher, singleton lock, dependency graph, triage/decomposition, cross-profile worker execution, review flow, and durable artifact handling intact; the live audit showed those mechanisms functioning end-to-end.
- Adds `latticevale-kanban-policy` v1.2.0 for installer-managed gateway profiles. Current Hermes `pre_tool_call` shallow argument modification is used only for deterministic repairs: unbound root `kanban_create` calls are normalized to `triage=true`, and a literal `HERMES_KANBAN_TASK` argument is replaced only when the process has a real bound task.
- Blocks ambiguous or unsafe task-context mistakes: worker lifecycle operations without a claimed task, cross-task worker lifecycle calls, missing task IDs for task-scoped reads/comments in normal sessions, missing assignees, and invented/nonexistent profile assignees.
- Discovers the complete real Hermes profile roster for routing validation. Valid routing to user-created profiles is preserved, but LatticeVale edits only the default profile and profiles recorded in `.installer-managed-profiles`; fallback automatic assignment never conscripts an unrelated user-owned profile merely because it exists.
- Adds managed Kanban guidance to prefer completed task results and durable attachments over transient scratch workspaces and to answer substantive result requests from the produced artifacts unless the user explicitly requests board/status mechanics.
- Adds managed skill-authoring/recovery guidance: normalize human skill names to valid slugs; generate closed YAML frontmatter; keep descriptions within the active Hermes budget; `skill_view` before patching existing skills; treat validation errors as corrective data; change strategy after repeated failures; verify successful writes; never weaken the tool-loop hard stop to force progress.
- Preserves explicit existing `skills.write_approval` booleans on repair/update; fresh managed profiles receive the Hermes automatic-write default only when the setting is absent.
- Advances the `integrations` checkpoint revision to 2 so the policy is applied on clean installs and automatically re-applied by Resume / repair, Change components, Reconfigure providers/profiles, Advanced recovery, and Update / repair after upgrading an older managed stack.
- Adds arbitrary-profile regression coverage proving a user-owned profile can remain orchestrator without being rewritten, while installer-managed profiles share the same canonical routing and concurrency policy.
- Documents the security boundary explicitly: automatic Kanban fan-out can execute assigned-profile tools, and automatic skill writes remain real agent capabilities; the v14.3.38 context guard corrects task context but is not a sandbox for untrusted task content.
- Updates all shipped user, support, security, release, source, contributor, integration-test, and historical patch-note documentation for the v14.3.38 policy migration.
- Current bundle/release identity is `14.3.38`.

## 14.3.37 - 2026-08-19

Controlled installer-managed update / repair release.

- Clarifies that ordinary Resume / repair is local-first between refresh windows but may update the installer-owned package/image/source layer when the 30-day refresh is due, an older stack lacks a refresh marker, or the managed-refresh policy revision changes.
- Adds a sixth existing-stack choice: **Update / repair installer-managed software**. It reuses saved choices, requires a successful pre-update `manage.sh backup`, bypasses the periodic gate, forces this bundle's managed package/image/source refresh, and then runs the normal staged repair/live verifiers.
- The controlled updater aligns fixed component pins with the versions declared by the LatticeVale bundle being run; installer-owned SearXNG/Ollama pins and the audited Honcho commit advance only across proven ownership boundaries. Persistent application state and explicit custom overrides are preserved. Separately owned native Windows Ollama is not updated.
- Distinguishes the Windows bundle updater from `./manage.sh update`, which remains an advanced upstream refresh of currently configured references and may advance Honcho to repository `HEAD`.
- Install option schema advances to 19 with the transient `forceManagedUpdate` control flag excluded from checkpoint identity so choosing Update / repair does not redefine the saved stack configuration.
- Documents the exact distinction between ordinary Resume / repair, controlled Update / repair, Change installed components, and the advanced `./manage.sh update` path in the user, support, technical, and release-maintainer documentation.
- Repairs stale regression fixtures for the current selection-dependent adaptive-resource overlay, current Kanban policy wording, and current secondary Matrix cross-signing warning semantics; the canonical static audit now invokes the dedicated v14.3.37 updater regression.
- Current bundle/release identity is `14.3.37`.

## 14.3.36 - 2026-08-19

Matrix installer-transaction follow-up to v14.3.35.

- Permit the narrowly scoped `manage.sh matrix-profile-finish <profile>` recovery command during an active installer transaction before the final `.configured` marker exists, while keeping ordinary management commands blocked until configuration completes.
- A protected `pending-manual` Matrix profile no longer performs live room-version queries that require membership before the bot has joined its invite. Pending state still requires installer-managed identity/token/room metadata and Matrix authentication; completed profiles retain strict live room-version and membership verification.
- Fixes the repair failure where the installer warned that profile activation was safely pending, then immediately failed `matrix_profiles` verification anyway.
- Current bundle/release identity is `14.3.36`.

## 14.3.35 - 2026-08-19

Matrix resilience patch.

- Secondary/profile Matrix provisioning may remain explicitly `pending-manual` after identity, token, encrypted-room, runtime-environment, and authentication resources verify, without aborting the whole clean install or Resume / repair.
- Pending secondary profiles are retried by repair/start lifecycle paths and remain visibly pending rather than being reported fully healthy.
- Hermes' normal named-profile gateway lifecycle command remains first choice; when that command fails and the exact `/run/service/gateway-<profile>` s6 slot is proven to exist, LatticeVale may activate only that exact slot with `s6-svc -U`.
- Secondary Matrix cross-signing/recovery-key persistence has explicit pending/complete state; preserved legacy default identities may retain the installer's existing pending marker without blocking unrelated repair work, while fresh identities remain strict.

## 14.3.34 - 2026-08-19

Cross-system compatibility and stale Windows bridge-port reclamation patch.

- WSL command parsing separates successful STDOUT from STDERR so update/startup notices cannot become phantom distro names.
- Repair no longer assumes a literal `Ubuntu-24.04` registration name; distro identity is verified from Linux and ambiguous multi-distro systems require explicit selection.
- Custom local fixed-volume and volume-GUID WSL storage layouts are normalized without drive-letter-only assumptions.
- Before bridge-port allocation, LatticeVale proves ownership of old installer-managed relay tasks/processes, stops only those exact owned relays, waits for release, and retries canonical Dashboard/Matrix ports `19119`/`18008`. Unknown listeners are preserved and still force safe alternate ports.

## 14.3.33 - 2026-08-19

Functional WSL preflight patch.

- Modern Store/MSI WSL2 is judged by bounded `wsl.exe` enumeration, WSL2-version detection, and an actual distro-launch probe rather than treating the legacy `Microsoft-Windows-Subsystem-Linux` optional-feature state as authoritative.
- `VirtualMachinePlatform` and other Windows feature states remain diagnostics; functional WSL2 launch evidence controls whether installation may proceed.
- `tools/Repair-LatticeVale-WslHost.ps1` probes the selected distro first and performs no DISM/feature/networking mutation when WSL already launches.

## 14.3.32 - 2026-08-19

WSL networking-safety patch.

- Native Windows Ollama + Windows Tailscale networking becomes capability-first rather than mode-first.
- A verified NAT/private-relay path is preserved; an already-working mirrored topology remains supported.
- Changing global `.wslconfig` to mirrored is an explicit default-No fallback only after the current topology cannot verify the required native-Ollama path.
- A normal install/repair no longer changes global WSL networking or runs `wsl --shutdown` merely because both integrations are selected.

## 14.3.31 - 2026-08-19

WSL host-audit and preservation-first regression patch.

- Add functional host diagnostics for WSL service failures such as `Wsl/Service/E_UNEXPECTED`, component-store state, `.wslconfig`, virtualization services, and existing distro storage.
- Add a separate preservation-first WSL host-repair helper; normal LatticeVale installation remains prohibited from unregistering, importing, moving, recreating, or directly modifying distro VHDX storage.
- Correct stale regression assertions in the supplied custom v14.3.30 backport test set so the audit matches the runtime behavior the baseline actually ships.

## 14.3.30 - 2026-08-18

- Centralized WSL networking policy when native Windows Ollama and Windows-host Tailscale remote exposure are enabled together. The selected/live mode and an ownership label are stored once in `install-options.json` and mirrored into native-Ollama/Tailscale metadata for repair and diagnostics instead of letting the two integrations independently request conflicting `.wslconfig` changes.
- Mirrored networking is now the recommended shared topology on supported Windows/WSL systems. Native Ollama keeps its verified Windows-localhost path, while the existing Windows Tailscale loopback relay forwards to WSL-published Dashboard/Matrix services through `127.0.0.1`; no Tailscale container, second tailnet node, or additional relay transport was added.
- NAT remains a supported explicit compatibility override. In NAT/other non-mirrored modes the same Windows relay continues to use bounded WSL-IPv4 discovery and live target refresh rather than hard-coded VM addresses.
- The Windows Tailscale relay now records its target mode/address, detects live NAT/mirrored transitions after a cached backend fails, switches between localhost and WSL-IPv4 targeting, and avoids waking an intentionally stopped distro unless stack auto-start/recovery was explicitly enabled.
- Dashboard/Matrix WSL host bindings remain loopback-only under the mirrored shared policy; only the NAT compatibility path broadens selected Tailscale backend binds so Windows can reach the WSL VM address.
- `state-audit.py` now reports saved/live WSL networking drift and degrades Tailscale status when selected Dashboard, Matrix, or native-Ollama/model dependencies are unhealthy instead of reporting remote exposure as configured solely because metadata exists.
- Fixed the v14.3.30 relay live-mode probe to invoke `wslinfo --networking-mode` through the bounded WSL helper with the correct argument shape; a regression now rejects the malformed positional invocation.
- Retains v14.3.29 native-Ollama relay readiness/model validation and uninstaller discovery fixes, plus v14.3.26 relay supervision/hardening.

## 14.3.29 - 2026-08-18

- Fixed uninstaller stack discovery again by removing its dependency on a large multiline Bash program serialized through `wsl.exe`. Account discovery now reads `getent passwd` directly and checks stack paths/markers through separately-argumented `wsl.exe` calls (`test`/`find`), so a probe/quoting failure cannot silently become a false “no stack found” result. A proven stack is no longer rejected solely because the distribution uses a nonstandard primary GID; destructive deletion still requires the exact selected account home, ownership markers, explicit purge confirmation, and symlink/mount safety gates.
- Fixed native Windows Ollama model validation treating a calculated Docker bridge URL as a verified relay. Native model operations now establish/recover the supervised WSL relay first, require a real `/api/version` response before `/api/tags`, `/api/pull`, or embedding validation, and perform one bounded forced relay restart if an apparently-live relay remains unhealthy.
- An alive-but-unhealthy native-Ollama relay supervisor or existing systemd relay service is now restarted instead of being trusted merely because its process/service is still active. Relay diagnostics are surfaced when readiness fails.
- Model discovery distinguishes “model absent” from “native Ollama relay unavailable,” preventing a relay outage from being mislabeled as a missing model/download requirement.
- Retains all v14.3.28 uninstaller path/purge safety and v14.3.26 relay stabilization behavior.

## 14.3.28 - 2026-08-18

- Expanded the uninstaller's ownership discovery to recognize completed, installer-state recovery, backup-recoverable, and safely staged partial runtimes instead of requiring final-install markers only.
- Added read-only candidate diagnostics and tightened full-purge path validation to the selected account's exact `$HOME/hermes-stack` while retaining symlink, mountpoint, nested-mount, and explicit `PURGE` safeguards.
- Retains the v14.3.27 single-distro menu fix and all v14.3.26 relay stabilization behavior.

## 14.3.27 - 2026-08-18

- Fixed the uninstaller's single-distro fallback selection. When no installer-shaped candidate was detected and WSL reported exactly one registered distro, PowerShell previously collapsed the one-item fallback collection to a scalar string; indexing choice 1 therefore returned only the first character (for example `U`) instead of the full distro name.
- The distro menu now explicitly preserves both candidate and fallback choices as arrays before indexing. Multiple-distro behavior and explicit `-DistroName` usage are unchanged.
- Retains all v14.3.26 native-Ollama relay stabilization/hardening and the restored legacy patch-note archive.

## 14.3.26 - 2026-08-18

- Stabilization/hardening release for native Windows Ollama and Windows relay plumbing; no new backend choice was added and managed WSL/Docker Ollama remains the simpler baseline.
- The WSL-local native-Ollama relay now has a watchdog supervisor, topology re-discovery, automatic worker restart, useful failure logging, a 64-connection ceiling, bounded upstream-connect/idle timeouts, and health-triggered rebuilds. When systemd is already active in the selected WSL distro, bootstrap installs an installer-owned `latticevale-native-ollama-relay.service` with `Restart=on-failure`; LatticeVale does not enable systemd or modify `/etc/wsl.conf` for this feature.
- The Windows native-service relay now refreshes the selected distro IPv4 and Windows WSL-host address while running, updates installer-owned Windows/Hyper-V firewall rules when topology changes, republishes the current host address, and rebuilds listeners only when necessary. It first checks `wsl --list --running --quiet`, so a stopped distro is not awakened merely for relay refresh.
- Both Windows C# TCP relays now cap active connections at 64, apply a 5-second upstream-connect timeout and a two-hour session backstop, record bounded relay events, and explicitly await/observe both copy directions after shutdown instead of abandoning the losing `Task.WhenAny` branch.
- The Windows native-service relay retains `Profile Any` only with its exact installer-owned local/remote WSL address and port scoping. Documentation now explains that changing the profile mechanically can break WSL virtual-interface scenarios; the security boundary is the exact WSL address/port ownership check, not profile classification alone.
- Added explicit documentation that the Windows relay scripts and environment-change broadcast use readable in-memory C# compiled with PowerShell `Add-Type`; this can trigger AV/EDR heuristics on managed machines even though no downloaded binary payload is executed.
- Added a repeatable live Windows/WSL integration matrix covering NAT, mirrored mode, WSL restart/IP churn, sleep/wake, native Ollama stopped/running, firewall/Hyper-V firewall, Tailscale, startup/shutdown shortcuts, and relay recovery. Release guidance now forbids claiming these paths as end-to-end tested unless that exact release was exercised on target Windows systems.
- Uninstall now removes the installer-owned native-Ollama systemd unit when it belongs to the selected stack; shared/system WSL configuration remains preserved.

## 14.3.25 - 2026-08-18

- Windows **Start LatticeVale** shortcuts now start native Windows Ollama when `windows-native` is the selected backend and its local API is not already running. The shortcut probes the configured API first, preserves an already-running Ollama process, starts the recorded custom Windows service when applicable or launches the recorded tray application when needed, waits boundedly for `/api/version`, and never stops native Ollama from the LatticeVale Shutdown shortcut.
- Shortcut configuration now records the detected native Ollama application/CLI paths and local API endpoint at install/repair time. A detected custom Windows service is preserved as the service-owned path; otherwise the normal tray app remains preferred, and the CLI `ollama serve` fallback is used only when no tray-app path was recorded and no Ollama-named process is already running.
- Fixed secondary Matrix profile post-stage verification for the intentional `pending-manual` state. An invited profile is no longer required to read normal room state before it joins; the verifier instead checks its live token identity, installer-recorded room-version policy, invite/join visibility through `/sync`, and that the exact profile gateway remains stopped. Completed profiles retain joined-room and live room-version verification.
- Retains v14.3.24 native-Ollama model pulling/embedding validation and all v14.3.23 public customization/GitHub-readiness documentation.

## 14.3.24 - 2026-08-18

- Fixed native Windows Ollama/Honcho model validation ordering: the native embedding compatibility check no longer launches a temporary Honcho container on `hermes-backend` before that Compose network exists.
- Native Windows Ollama model discovery remains API-driven through `/api/tags`; missing selected models are pulled automatically through `/api/pull`, so users do not need to pre-download selected models manually.
- Native Honcho embedding validation now calls the already-verified native Ollama OpenAI-compatible `/v1/embeddings` endpoint directly from WSL and requires an actual 1536-element vector before infrastructure proceeds.
- Managed WSL/Docker Ollama retains its container-based embedding verification on the real Compose backend network.
- Added a post-pull model-list verification so a reported pull completion is not accepted unless the selected backend actually lists the requested model afterward.
- Retains v14.3.23 documentation permitting MIT-licensed modification/forking/system-specific customization and its GitHub publication guidance; requirements text now also calls out free space for native Ollama's Windows model store when LatticeVale must pull selected models.

## 14.3.23 - 2026-08-18

- Documentation/public-release clarification only; no v14.3.22 installer/runtime behavior was removed.
- Explicitly documents that LatticeVale's MIT license permits inspection, modification, system-specific customization, forking, publication, and redistribution when the MIT notice is preserved.
- Adds downstream-fork guidance: label modified builds, regenerate the source manifest, keep secrets/runtime state out of Git, and update `compatibility.conf` plus tests instead of bypassing safety preflights when changing platform support.
- Aligns requirements documentation with the existing executable preflight: x64/AMD64 Windows build 19041+ and an amd64/x86_64 Ubuntu 22.04/24.04/26.04 WSL2 distro.
- Expands GitHub release guidance for secret scanning, machine-specific private state, modified-build labeling, and requirements/compatibility-policy consistency.

## 14.3.22 - 2026-08-18

- Native Windows Ollama WSL verification now treats a successful `/api/version` response from the selected distro as authoritative end-to-end proof. The probe invokes `curl` directly through `wsl.exe` with a direct Python fallback instead of relying on nested shell/heredoc serialization.
- A currently working direct WSL-to-Windows Ollama path is detected before synthetic relay probes. If the running tray process is reachable but no persistent non-loopback User/Machine `OLLAMA_HOST` is present, LatticeVale offers to persist and firewall-scope the working path without restarting Ollama.
- Native Ollama restart handling now stops the tray app before its managed server child, repeats until the Ollama process tree is gone, waits for the Ollama TCP port to be released, and refuses to launch a duplicate server onto an occupied port. The CLI `ollama serve` fallback is used only after a failed tray launch and only after the tray/process tree has fully exited.
- Direct-access remediation restarts Ollama only when the selected distro cannot already reach the real API after the environment/firewall change. A successful WSL `/api/version` response takes precedence over listener-introspection diagnostics.
- WSL host-address discovery remains topology-driven: NAT uses discovered route/WSL-adapter candidates, mirrored mode can use localhost, and no machine-specific subnet, adapter index, username, or host address is hard-coded.
- The Windows Obsidian vault-folder question no longer proposes or accepts a suggested path. Users who enable Windows Obsidian must enter an explicit Windows-local drive path.

## 14.3.21 - 2026-08-18

- Added a first-party `uninstall.ps1` entry point with release-manifest verification and an administrator-only core `Uninstall-LatticeVale.ps1`.
- Safe uninstall stops/removes the selected Compose runtime plus provably installer-owned scheduled tasks, desktop shortcuts, native-relay firewall/Hyper-V firewall state, Tailscale Serve mappings when they still match recorded LatticeVale backends, direct-native-Ollama environment state when still installer-owned, and installer-owned Linux host helpers.
- Safe uninstall preserves `~/hermes-stack` for reinstall/recovery and clears stale Windows-integration metadata instead of deleting user/service data.
- Full purge requires typing `PURGE` and deletes only a validated non-symlink, non-mountpoint `/home/<user>/hermes-stack` tree. External Windows-backed Obsidian vaults are never deleted.
- The uninstaller never unregisters WSL and deliberately preserves shared/general prerequisites and applications: Docker Engine/packages, Ubuntu prerequisite packages, Ubuntu Pro attachment, GPU runtime/toolkit, native Windows Ollama, Windows Tailscale, and Obsidian.
- Global `.wslconfig` is not silently reverted. If LatticeVale-created backups are present, the uninstaller can optionally restore the newest backup after an explicit warning and confirmation.

## 14.3.20 - 2026-08-18

- Native Windows Ollama connectivity now prefers a consent-gated **mirrored WSL localhost fallback** before exposing Ollama with `OLLAMA_HOST=0.0.0.0`. This addresses systems where WSL NAT cannot reach even an installer-owned temporary Windows listener.
- On Windows 11 22H2+, LatticeVale can back up `%UserProfile%\.wslconfig`, change only `[wsl2] networkingMode=mirrored`, run `wsl --shutdown`, wait for the selected distro to return, and require both `wslinfo --networking-mode` = `mirrored` and a verified native Ollama localhost `/api/version` path before accepting the change.
- If mirrored verification fails after LatticeVale changed `.wslconfig`, the previous file is restored and WSL is restarted back to the prior networking configuration. If `.wslconfig` already requested mirrored mode but it had not yet been applied, LatticeVale can explicitly restart WSL without rewriting the file.
- The existing direct `0.0.0.0`/scoped-firewall fallback remains available only after mirrored mode is declined, unsupported, or fails verification. `OLLAMA_ORIGINS` remains unchanged.
- Mirrored-mode remediation does not restart Ollama or change its bind setting; Ollama can remain on its default Windows loopback listener.

## 14.3.19 - 2026-08-18

- Fixed native Windows Ollama recovery after Ollama updates or environment changes: resumed/elevated installer processes now launch Ollama with the current persisted User/Machine `OLLAMA_HOST` instead of a stale inherited process value.
- Native Ollama start/restart now clears stale Ollama-named app/server processes after explicit user consent, retries the normal tray application first, and falls back to the documented `ollama serve` CLI path only when the GUI launch does not restore the API.
- Direct WSL access no longer treats a loopback API response as proof that `OLLAMA_HOST=0.0.0.0` was applied; it waits for a real non-loopback listener before verification.
- Windows Firewall rules for native Ollama direct access now use the exact Windows-host address plus the selected distro's current IPv4 source address(es), avoiding fragile interface-alias/program coupling while remaining narrower than a LAN-wide port rule.
- Added narrowly scoped WSL Hyper-V outbound firewall rules when the modern Hyper-V firewall cmdlets are available. This is applied to both the preferred private Windows relay and the direct-Ollama fallback, with installer-owned cleanup; LatticeVale does not change WSL's global firewall defaults.
- Clarified NAT/mirrored diagnostics: typing `networkingMode=mirrored` inside Ubuntu is only a shell variable and does not change WSL networking.

## 14.3.18 - 2026-08-18

- Added an explicit `wsl-host-relay` fallback for native Windows Ollama when the existing private `windows-gateway-relay` and verified `wsl-localhost-relay` transports cannot be established even though the Windows-local Ollama API is healthy. The safer private transports remain first choice.
- With explicit consent, normal Windows tray-app installs persist `OLLAMA_HOST=0.0.0.0:<verified-port>` at **User** scope, matching Ollama's documented Windows environment model; a detected custom Windows service uses **Machine** scope. LatticeVale broadcasts the environment change and relaunches the tray app/CLI server or restarts the detected service so the new bind is actually consumed.
- Added an installer-owned Windows Firewall rule scoped to the selected Ollama TCP port, the WSL-facing interface (or exact host address fallback), and `LocalSubnet4`, with Profile Any so Windows Public profiles are covered without creating a second broad inbound allowance. The selected WSL distro must then pass `/api/version`, and Windows must show a non-loopback listener before the fallback is accepted.
- `OLLAMA_ORIGINS=*` is deliberately **not** set. Ollama documents `OLLAMA_ORIGINS` as additional browser/CORS-origin configuration; Hermes and Honcho use ordinary server-side HTTP and do not need a wildcard browser origin policy.
- Direct-fallback state records the previous `OLLAMA_HOST`, its scope, and the exact firewall rule. Switching away removes only installer-owned firewall state and restores the prior environment value only if the configured value has not subsequently been changed by the user.
- The WSL side does not append a dynamic Windows host address to `~/.bashrc`. The WSL-local native-Ollama relay re-discovers the current default-route Windows gateway each time it starts, falls back to the previously verified address only when necessary, verifies `/api/version`, and binds its container-facing listener only to Docker's host-gateway IPv4.
- Extended native-relay target validation to permit a private non-loopback IPv4 only under the explicit `--allow-private-target` fallback flag; the default relay policy remains IPv4 loopback-only.
- Added deterministic v14.3.18 regression coverage for consent gating, User-vs-Machine environment scope, tray/service restart behavior, firewall scoping, WSL verification, rollback ownership, dynamic NAT gateway discovery, CORS non-mutation, and lifecycle support for the new transport.


## 14.3.17 - 2026-08-18

- Fixed a native Windows Ollama NAT false-negative where WSL itself reports a normal `default via <Windows-host-IP> dev <interface>` route, but LatticeVale's machine-readable probe could still return empty because the route/address query was wrapped in `bash -lc` plus `awk` and then serialized through the Windows `wsl.exe` command line.
- WSL networking-mode, IPv4-address, and default-route discovery now invoke `wslinfo`/`ip` directly through `wsl.exe` and parse stdout in PowerShell. No shell pipeline is used for those machine-readable probes. Multiple default routes are handled and every `via` candidate is functionally verified before acceptance.
- The long-lived Windows native-service relay uses the same direct route parser after WSL restarts, so setup and runtime cannot disagree because one path still depends on the older shell/awk probe.
- Fixed a related Windows argument-quoting defect in the relay helper: backslashes are now counted by character code exactly as in the core native-process helper, preventing future quoted-argument corruption for values containing Windows path separators.
- Retains v14.3.16's Windows WSL/Hyper-V adapter fallback and bounded Ollama folder scan. No WSL subnet, adapter name, user IP, or Ollama path from the diagnostic fixture is hard-coded; the fixture represents the generic current WSL NAT shape.
- Expanded `Instructions.txt` to state explicitly that native mode keeps Ollama and GPU execution on Windows; WSL/Docker only reaches its HTTP API through LatticeVale's verified private bridge. Installing Ollama inside WSL is not required for native mode.

## 14.3.16 - 2026-08-18

- Fixed native Windows Ollama being rejected on WSL NAT installations where `wslinfo` reports `nat` but the WSL default route contains no usable Windows-host next hop. The route remains the first discovery method; LatticeVale now falls back to Windows WSL/Hyper-V virtual-adapter IPv4 addresses that match the selected distro subnet.
- Candidate adapter addresses are proved before use with a temporary random-port Windows listener and temporary WSL-scoped firewall rule; the selected distro must complete a TCP connection. The temporary listener/rule are removed immediately afterward.
- The verified native-gateway host IPv4 is persisted in schema 18 so Linux configure/start/manage paths do not independently re-assume `ip route`. The Windows relay helper independently retains route-first plus WSL/Hyper-V-adapter rediscovery and republishes its current host IPv4 into the managed stack on each start so later WSL NAT address changes can be consumed by boot and `manage.sh`.
- Added a bounded native-Ollama folder fallback under conventional Windows application roots. Only Ollama-named immediate child directories and their direct `bin` child are checked; LatticeVale does not recursively scan whole drives, arbitrary folders, mounted volumes, or user documents.
- Added deterministic v14.3.16 regression coverage for NAT adapter fallback, bounded native-app scanning, host-address persistence/refresh, schema 18 validation, and the retained native/managed Ollama isolation guarantees.

## 14.3.15 - 2026-08-18

- Fixed native Windows Ollama being rejected on WSL topologies that legitimately do not expose Windows as the IPv4 default-route gateway. Current Microsoft WSL networking supports a Windows/WSL localhost path in mirrored mode, while current WSL can also use NAT or VirtioProxy depending on configuration/fallback.
- Native relay capability now queries `wslinfo --networking-mode` when available for diagnostics and proves the usable path functionally: first the existing NAT-style Windows-host gateway relay, then direct WSL access to the already-verified Windows Ollama loopback API. No topology label alone is trusted as sufficient.
- Added a `wsl-localhost-relay` transport for a verified localhost path. A small installer-owned Python relay binds only Docker's WSL host-gateway IPv4 and forwards only to Windows IPv4 loopback, allowing bridge-mode Hermes/Honcho containers to use native Ollama without a Windows NAT gateway, `0.0.0.0` listener, `OLLAMA_HOST` change, or managed Ollama image.
- Persisted native relay metadata records transport, verified target address, and target port. Configure, repair, auto-start, `manage.sh`, state audit, model pulls, and container routing consume that common state rather than independently assuming the WSL default route points to Windows.
- VirtioProxy/other unsupported topologies now receive mode-specific diagnostics when neither a gateway path nor localhost path can be verified. LatticeVale does not automatically change global WSL networking merely to enable native Ollama.
- Added a conflict guard for the optional Tailscale NAT migration: if native Ollama currently depends on a verified WSL-localhost transport, setup cannot later switch WSL to NAT and silently invalidate that path. The user must explicitly keep the current topology or stop before the global change.
- Added deterministic v14.3.15 topology/relay coverage while retaining v14.3.14 questionnaire remediation, v14.3.13 PowerShell encoding hardening, v14.3.12 backend isolation, and all prior repair/Matrix/WSL safeguards.

## 14.3.14 — 2026-08-18

- Fixed the native Windows Ollama backend menu conflating two independent failures: an installed-but-not-running/API-ready Ollama instance and a healthy Ollama API whose Windows-to-WSL relay path could not be verified.
- The questionnaire now states plainly that native Windows Ollama must be running before LatticeVale can use its local API. Installation detection still works while Ollama is stopped.
- Selecting the native backend now performs an immediate re-detection. If Ollama is installed but stopped, LatticeVale offers to start only that already-installed copy, re-checks `/api/version`, and then re-runs the WSL relay capability probe.
- If the API is healthy but the relay is unavailable, the installer reports the exact relay failure and explicitly notes that reopening Ollama will not fix that condition. Native selection remains unavailable until both checks pass, and no managed WSL/Docker fallback is selected silently.
- Added deterministic v14.3.14 questionnaire regression coverage while retaining v14.3.13 PowerShell source-encoding hardening and all earlier Ollama/repair/Matrix/WSL behavior.

## 14.3.13 — 2026-08-18

- Fixed a Windows PowerShell 5.1 parser failure caused by UTF-8-without-BOM em dashes in `Install-LatticeVale.ps1`. On legacy Windows PowerShell decoding, the UTF-8 byte sequence could become mojibake containing a smart-quote byte and terminate a quoted string early.
- Converted every shipped PowerShell runtime source file to an ASCII-only source policy. The release currently contains no non-ASCII bytes in `.ps1`, `.psm1`, or `.psd1` source.
- Added release-verifier enforcement so encoding-sensitive PowerShell source is rejected before the core installer is invoked, producing a clear release-integrity error instead of a later parser failure.
- Changed Windows CI PowerShell parsing from a hard-coded script list to dynamic discovery of every shipped PowerShell source file, with an explicit ASCII-byte guard before parsing under Windows PowerShell 5.1 and PowerShell 7.
- Added deterministic v14.3.13 PowerShell source-encoding regression coverage while retaining the v14.3.12 explicit Ollama backend split and all prior repair/Matrix/WSL compatibility behavior.

## 14.3.12 — 2026-08-18

- Replaced the ambiguous Ollama Y/N/backend flow with an explicit runtime-location decision whenever Honcho or Hermes local Ollama is selected: reuse verified native Windows Ollama, or install/manage Ollama inside WSL/Docker.
- Native Windows Ollama availability is shown before the runtime choice. Installed-but-stopped native Ollama can still be explicitly started and re-probed; if the native API/WSL relay is not usable, selecting native explains the failure and re-prompts instead of silently falling back to managed WSL Ollama.
- Native mode now explicitly guarantees that the managed `local-ai` Compose profile is inactive, new WSL `data/ollama` model storage is not created, and installer/update image pulls are scoped to selected services so `ollama/ollama` cannot be downloaded as a side effect. Existing old `data/ollama` directories are preserved rather than destructively removed.
- Managed mode now states plainly that LatticeVale will download/start the managed Ollama image and store its models inside the selected Ubuntu distro.
- Retains v14.3.11 native-install discovery, v14.3.10 aged repair convergence, and all prior repair/Matrix/profile/WSL preservation behavior.

## 14.3.11 — 2026-08-18

- Fixed native Windows Ollama being reported as unavailable when it was installed outside the default path, absent from the elevated process PATH, configured with a loopback `OLLAMA_HOST` override, or installed but not currently serving its API.
- Split native Ollama discovery into independent `Installed`, `ApiReady`, and WSL-relay readiness facts. Standard/persisted PATHs, official default locations, Add/Remove Programs metadata (including custom `/DIR` installs), and running-process executable paths are inspected.
- When an existing native installation is detected but stopped, the questionnaire explicitly offers to launch that existing application (or the documented `ollama serve` CLI path) and then re-probes it. LatticeVale still does not install, update, reconfigure, or alter native Ollama startup policy.
- Loopback `OLLAMA_HOST` overrides are recognized. The installer-owned WSL relay now targets the exact local address/port that passed `/api/version`, instead of assuming `127.0.0.1:11434`. Non-loopback listeners are recognized as configuration but are not adopted as the private relay target.
- Added v14.3.11 native-Ollama discovery regression coverage while retaining v14.3.10 managed-refresh behavior and all prior v14.3.x compatibility/repair invariants.

## 14.3.10 — 2026-08-18

- Same-version questionnaire clarity follow-up: fresh-install explicit prompts now display suggested Y/N choices, menu selections, numeric values, model/path suggestions, and TCP ports while still requiring explicit input for host/system-affecting settings. Tailscale HTTPS suggestions are Dashboard **9443** and Matrix **443**; suggestions never override detected/saved state or make blank Enter an implicit selection.
- Restored age-based convergence for recognized managed repairs. A successful repair refresh is now age-gated by `MANAGED_REPAIR_REFRESH_DAYS=30`; legacy managed stacks without a refresh marker perform one adoption refresh regardless of which older LatticeVale version created them. `MANAGED_REPAIR_REFRESH_REVISION=1` also provides an explicit package-policy epoch that future releases can bump to force one immediate convergence refresh without making every ordinary version bump an implicit dependency update.
- Due refreshes update APT metadata and upgrade/install only the LatticeVale prerequisite package set plus the official Docker Engine/CLI/containerd/Buildx/Compose packages. LatticeVale does **not** run a blanket `apt upgrade`, `full-upgrade`, or `dist-upgrade`, so unrelated Ubuntu packages remain administrator-owned.
- A pending managed refresh bypasses the ordinary local-image fast path and refreshes the currently selected installer-owned Compose images/builds and Hermes image before the refresh is considered complete. Explicit custom image/source overrides remain preserved.
- NVIDIA Container Toolkit readiness is re-evaluated during a due refresh when NVIDIA support is selected; a complete newer toolkit remains preserved rather than downgraded.
- Refresh state is interruption-safe: root package work creates a protected pending marker, Resume completes the image/build half without repeating completed root package work, and the success timestamp is written only after infrastructure/Hermes profile verification. Pre-repair configuration snapshots now include both refresh-state markers so rollback/recovery does not lose the age/policy bookkeeping.
- Added ownership markers for SearXNG and Honcho so future aged repairs can advance LatticeVale-managed defaults/source without overwriting user overrides; ambiguous legacy/custom values remain preserved. The existing Ollama ownership marker continues to protect custom `OLLAMA_IMAGE` values.
- Corrected stale documentation left by the v14.3.9 history consolidation and updated older repair/image wording to reflect the periodic managed-refresh policy.
- Re-audited the consolidated patch history against the retained regression suite; historical fixtures were updated only where prompt/status text intentionally changed, while the underlying preservation, Matrix, gateway, WSL, vault, and recovery invariants remain enforced.
- Added deterministic v14.3.10 aged-repair package-refresh coverage while retaining the preservation-first/local-first behavior between refresh windows and all prior v14.3.x regressions.

## 14.3.9 — 2026-08-17

- Changed secondary-profile Matrix setup to a **provision-now, activate-later** model. LatticeVale creates/verifies the independent Matrix account, encrypted room, v10 room policy, invitation, access token/device identity, and protected profile environment, but does not make the overall installer depend on Hermes consuming the invite during installation.
- New/resumed secondary Matrix resources are recorded as `pending-manual`; the exact profile gateway is left stopped and later installer stages skip profile cross-signing/gateway startup until the user explicitly finishes that optional integration.
- Repairs detect the v14.3.8 edge where a profile was marked `complete` before it actually joined, preserve the existing bot/token/device/room, and reclassify only that bookkeeping state to `pending-manual`.
- Added `./manage.sh matrix-profile-finish <profile>` as the explicit completion path. It uses installer-held protected state, verifies Matrix and the exact profile gateway, waits boundedly for the existing invite to be accepted, captures/persists the E2EE recovery key, and only then marks the profile complete. Failed attempts stop the exact profile gateway and leave state retryable.
- Added `MATRIX-SECONDARY-PROFILES.txt` in the managed WSL stack as a non-secret handoff file containing profile/user/room/version/status plus the exact finish command. Ordinary `start`, `restart`, and `update` skip profiles still marked `pending-manual`.
- State audit treats a deliberately pending secondary Matrix profile as **CONFIGURED**, not broken, so an optional Hermes-side Matrix activation cannot make an otherwise healthy LatticeVale install fail.
- Consolidated all historical version-specific `AUDIT-v*`, `HOTFIX-v*`, and `RELEASE-NOTES-v13.md` documents into this single `CHANGELOG.md`. General audit/security/release-process documents remain separate.

## 14.3.8 — 2026-08-17

- Fixed secondary-profile Matrix provisioning repeatedly waiting for a room join after the installer-managed Synapse Client-Server API became unavailable. Matrix bootstrap/profile stages now explicitly start `synapse-db` + `synapse` and verify both `/health` and `/_matrix/client/versions` before provisioning.
- Matrix room-join waits are bounded and health-aware. After three consecutive Client-Server API failures the exact affected profile gateway is quiesced; LatticeVale then performs one bounded automatic Synapse restart/retry before preserving resumable state and stopping cleanly.
- Pinned all **LatticeVale-created** Matrix rooms to room version **10** and set installer-managed Synapse `default_room_version` to `10`. Room creation explicitly sends `room_version: "10"` and verifies the actual `m.room.create` state afterward rather than inheriting an ambient/default room version.
- Added preservation-first migration for LatticeVale-managed rooms created by older releases at another room version (including v11): Matrix rooms are never downgraded in place. Repair backs up installer metadata, preserves the old room and existing bot identity/token, creates a replacement private encrypted v10 room, and switches only installer-owned routing. Explicitly adopted user-owned existing rooms are not silently replaced.
- Revalidates Matrix after interactive admin-password entry so a long prompt cannot leave later profile operations assuming Synapse stayed online.
- Added deterministic v14.3.8 Matrix-online/v10 regression coverage while retaining all v14.3.1–v14.3.7 hotfixes.

## 14.3.7 — 2026-08-17

- Fixed new Hermes profile setup aborting after `profile create` when `hermes -p <profile> gateway stop/status` did not reliably reflect the exact supervised process. Credential handoff now keys off `/command/s6-svstat /run/service/gateway-<profile>` instead of profile CLI status text.
- Added a bounded, profile-scoped quiesce path: request the normal Hermes stop first, then request `s6-svc -d` only for the exact named service, and only if necessary TERM/KILL the PID freshly reported by that same service. No `pkill`, `killall`, all-profile stop, or process-name matching is used.
- Matrix profile verification and later `manage.sh` start/restart reconciliation now use the same exact s6 service state, avoiding cross-profile `gateway status` false positives.
- Resume / repair preserves a profile directory already created by the interrupted v14.3.6 run and continues provider/Matrix provisioning after the exact service is safe for credential writes.
- Expanded release validation so the Windows CI parser list and Linux static PowerShell compatibility/runtime-variable scans cover all eight shipped `.ps1` files, including the native Windows service relay added in v14.3.5. The opaque-runtime-source CI grep now excludes regression fixtures that intentionally contain forbidden-token literals as negative tests; the compiled-artifact scan still covers the full tree.
- Added deterministic v14.3.7 exact-profile s6 lifecycle regression coverage while retaining all prior v14.3.x hotfixes.

## 14.3.6 — 2026-08-17

- Fixed first Matrix bootstrap aborting immediately after the repeated admin-password prompt with `matrix_bootstrap` exit 2. The stage attempted to read `MATRIX_DEVICE_ID` from `secrets/matrix-bot.env` before that optional file exists; under `set -Eeuo pipefail`, the missing-file `sed` status propagated through `head` and terminated the stage.
- Added a pipefail-safe optional env-file reader and use it for first-run/repair state that may legitimately be absent. A missing optional state file now returns an empty value so the documented fallback device ID is applied.
- Hardened the unstable-room-version fallback so an empty filtered capability list reaches the installer's explicit diagnostic instead of being preempted by `pipefail`. `manage.sh` optional `.env` reads are also safe during incomplete installs.
- Resume / repair reuses the one-time `secrets/matrix-bootstrap.env` written before the v14.3.5 failure, so already-created Matrix users are verified and provisioning continues instead of replacing their identity.
- Added deterministic v14.3.6 first-bootstrap/pipefail regression coverage while retaining all prior v14.3.x hotfixes.

## 14.3.5 — 2026-08-17

- Fixed Resume / repair reaching `prepare_config` with a saved forced Ollama GPU policy that is not actually usable inside the selected Ubuntu distro. LatticeVale now probes the selected distro before bootstrap and explicitly asks whether to switch the managed policy to Auto, CPU, or stop without changing the saved choice.
- Fresh/reconfigure questionnaires now show selected-distro GPU readiness and reject forced NVIDIA/AMD selections whose required WSL/device prerequisites are not currently verified. Windows GPU presence is never treated as proof that the corresponding Docker path works inside WSL.
- AMD Docker/ROCm readiness for the currently managed Ollama path requires x86_64 plus `/dev/kfd` and `/dev/dri`; `/dev/dxg` by itself is reported but is not assumed to satisfy that container path. NVIDIA forced mode requires `/dev/dxg` plus a working WSL `nvidia-smi` probe before selection.
- Preserved `explicit` questionnaire mode when loading v14.3.4+ saved install state. Linux-side forced-GPU checks remain in place as defense in depth if device/runtime state changes after the Windows-side probe.
- Added an optional **native Windows Ollama** backend. It is offered only when the Windows localhost API is already running *and* the selected WSL distro exposes a Windows-host interface that LatticeVale can safely bind for a WSL-only relay. LatticeVale does not install, update, rebind, or reconfigure native Ollama.
- The native backend can pull missing user-selected model tags through Ollama's `/api/pull` API, keeping those models in native Windows Ollama storage and allowing Windows Ollama to retain ownership of its GPU/Vulkan/ROCm backend. Hermes/Honcho are routed to the verified relay without starting the managed WSL Ollama container.
- Added an installer-owned Windows native-service relay that binds only the detected Windows-host interface for the selected WSL instance and creates an exact-port firewall allowance scoped to that WSL IPv4. Relay startup/restart refreshes the address after WSL networking churn; it never changes `OLLAMA_HOST` or opens native Ollama on all Windows interfaces.
- Added deterministic v14.3.5 GPU-prerequisite/repair and native-Windows-Ollama regression coverage while retaining the v14.3.4 host/vault, v14.3.3 Matrix-room, v14.3.2 native-process, and v14.3.1 StrictMode hotfixes.

## 14.3.4 — 2026-08-17

- Removed the default-heavy Quick Setup path for fresh installs. Fresh installs now use an explicit questionnaire: optional host/system-affecting Y/N, numeric, menu, and Tailscale-port choices require input instead of accepting invented defaults. Existing saved LatticeVale choices remain reusable during repair/change flows.
- Stopped guessing machine-specific state: the installer explicitly confirms a sole eligible Ubuntu distro/user, uses the selected user's actual passwd home for shortcuts, never invents an Obsidian Documents-folder vault, and reuses the detected Ubuntu timezone when no saved timezone exists.
- Stopped silently forcing global WSL `instanceIdleTimeout=-1` when remote Tailscale exposure is selected. LatticeVale now warns and preserves the explicit/saved lifetime policy. Global WSL networking changes also require an explicit confirmation.
- Fixed `prepare_config` failing with `chmod: changing permissions of 'vault': Operation not permitted` when `~/hermes-stack/vault` is a stale bind mount/symlink or Windows-backed path. Known legacy Obsidian targets are detected before bootstrap, detachment requires explicit consent, source data is never deleted, exact legacy fstab entries are removed only when source+target match, and the local vault directory is recreated with the selected Ubuntu UID/GID. The Linux stage refuses to chmod through a remaining symlink/mountpoint.
- Extended schema-16 questionnaire validation to retain legacy `quick`/`custom` values while accepting the new `explicit` mode. Added deterministic v14.3.4 regression coverage.

## 14.3.3 — 2026-08-17

- Fixed fresh/custom Matrix profile setup asking for an existing Matrix room ID before Matrix/Synapse had been installed. Existing-room adoption is now offered only when an installer-managed Synapse deployment is already present; otherwise LatticeVale records `roomMode = create` and creates the encrypted profile room later during Matrix provisioning.
- Added deterministic v14.3.3 regression coverage. v14.3.2 native-process/WSL handling and v14.3.1 StrictMode startup fixes remain unchanged.

## 14.3.2 — 2026-08-17

- Fixed a Windows PowerShell/WSL preflight false negative where `wsl --list --quiet` could return a valid distro name while `Start-Process -PassThru -NoNewWindow` exposed an unavailable/null `ExitCode`, causing `Invoke-NativeProcessCapture` to mark the call unsuccessful.
- Replaced exit-code-sensitive `Start-Process -PassThru` usage in the bounded capture helper, passthrough helper, interactive WSL installer launcher, and Windows-native WSL relay with directly owned `System.Diagnostics.Process` instances.
- Bounded capture/relay paths drain stdout and stderr concurrently before exit evaluation to avoid redirected-pipe deadlocks while preserving existing timeouts, separated stdout/stderr, and binary stdin staging.
- Added deterministic v14.3.2 regression coverage. v14.3.1 StrictMode/cache startup hardening and all v14.3.0 installation/repair behavior remain in place.

## 14.3.1 — 2026-08-17

- Fixed the documented `install.ps1` launch path under Windows PowerShell 5.1: dot-sourcing `tools/ReleaseManifest.ps1` previously leaked StrictMode 2.0 into the core installer. StrictMode is now scoped to the verifier functions, and the core lazy `$script:HermesCompatibility` cache is also initialized defensively before preflight reads it. This is a startup-only compatibility fix; installation, repair, and saved-state behavior are otherwise unchanged.
- Added a deterministic regression fixture for the StrictMode/cache initialization path and retained the full v14.3.0 regression baseline.

## 14.3.0 — 2026-08-17

- Added Quick vs Custom fresh-install questionnaire modes backed by one schema-16 saved configuration. Quick uses conservative defaults and asks only the core local-Ollama vs upstream-provider choice; Custom retains the full existing questionnaire.
- Hardened NVIDIA Container Toolkit setup so a complete installed toolkit newer than the tested `1.20.0-1` package set is preserved instead of downgraded. Mixed newer/older toolkit states fail closed for manual reconciliation, and `--allow-downgrades` is no longer used.
- Added offline configured-image pin date/age visibility to `manage.sh status` (and therefore successful `verify`) without network checks or automatic update decisions.
- Added read-only hardware/resource diagnostics: visible WSL CPU/RAM, resource policy, detected NVIDIA/AMD VRAM when available, soft model-artifact/VRAM pressure warnings, and actual loaded-model `ollama ps` CPU/GPU evidence when available.
- Added a concise hardware/resource summary at install finalization with a pointer to `manage.sh status` for runtime offload evidence.
- Added a post-backup reminder that archives can contain credentials and should be stored securely/encrypted when copied elsewhere; no new encryption dependency or key-management path was introduced.
- Bumped persisted option schema to 16 for `questionnaireMode` while preserving older schema acceptance and preservation-first repair semantics.
- Added v14.3 deterministic safety/usability regression coverage while retaining all prior v13/v14 fixtures and lifecycle simulations.

## 14.2.1

- Hardened root bootstrap option handling: root-affecting booleans/acceleration are structurally parsed after Python is available instead of inferred from regex matches inside JSON text.
- Pinned the complete NVIDIA Container Toolkit 1.20.0 package set together to avoid mixed toolkit/library dependency versions.
- Added `LATTICEVALE_OLLAMA_IMAGE_AUTO` ownership tracking so same-policy repairs preserve deliberate custom `OLLAMA_IMAGE` overrides; an explicit acceleration-policy change may still switch the installer-managed standard/ROCm image as required.
- Extended runtime audit/tests for custom Ollama image ownership and the stricter bootstrap parser.
- Hardened the shared source-manifest verifier for release trees extracted directly at a filesystem root (for example `C:\\`), avoiding accidental PowerShell drive-relative path semantics.
- Added executable regression coverage for both custom-image preservation and installer-owned CPU→AMD image switching, not only static source assertions.


## 14.2.0 — 2026-08-17

- Added explicit Ollama acceleration policy (`auto`, CPU, NVIDIA, AMD/ROCm). Auto mode safely falls back to CPU; NVIDIA setup uses the pinned `nvidia-container-toolkit=1.20.0-1` package from NVIDIA's official Container Toolkit repository only when GPU use is selected and a WSL NVIDIA device is detected. No Linux NVIDIA display driver is installed.
- Added adaptive per-service CPU/RAM ceilings for new installs, with existing pre-14.2 repairs preserving unrestricted behavior unless already opted in. User `compose.override.yaml` remains last and authoritative.
- Pinned Ollama and SearXNG release defaults instead of floating `latest` tags; `.env` remains an explicit override surface.
- Consolidated portable-path and exact source-manifest validation into `tools/ReleaseManifest.ps1`; the launcher, standalone verifier, and manifest generator now consume the same path-safety implementation.
- Manifest regeneration writes LF bytes explicitly even under Windows PowerShell, preventing the generator itself from reintroducing CRLF into the source-only release tree.
- Legacy repair warns when it preserves an explicitly configured floating image tag rather than silently changing it; repair remains distinct from update.
- Expanded Honcho AGPL-3.0 network-use guidance, GPU privilege-boundary documentation, resource-limit scope, and release reproducibility documentation.

## 14.1.3 — 2026-08-17

- Fixed GitHub/Windows source-manifest portability: all hashed source and text files are now forced to LF in `.gitattributes`, preventing a normal Windows Git checkout from changing exact bytes and failing `SOURCE-SHA256SUMS.txt` verification.
- Added a regression guard that rejects any future `eol=crlf` rule in the release tree.
- Normalized the shipped reviewable source tree itself to LF and added a byte-level regression check, preventing a manifest from being generated against pre-normalized CRLF files.
- Completed the runtime rebrand for project-level status/warning text; upstream component names remain only where they identify the actual dependency, profile, API, or service.
- Fresh SearXNG configuration now uses `LatticeVale Search`; repair migrates only the exact historical installer-default title and leaves custom instance names unchanged.
- Aligned the public-release regression suite with the stricter portable-path, case-collision, reserved-device-name, and file/directory reparse-point checks in the release manifest verifier/generator.
- Preserved the v14.1.2 custom-WSL-automount relay fix and all earlier clean/repair compatibility behavior.
- Re-ran the complete deterministic, interruption/resume, packaged-copy, syntax, Compose, branding, source-only, and manifest validation set for the final release.

## 14.1.2 — 2026-08-17

- Fixed Windows relay task control on eligible WSL installations that use a custom Windows-drive automount root. `manage.sh` no longer assumes `schtasks.exe` lives at `/mnt/c/Windows/System32`; it resolves the Windows path through `wslpath` when the executable is not already available through WSL interop PATH.
- Added a regression guard against reintroducing hard-coded `/mnt/c/Windows/System32/schtasks.exe` fallback logic.
- Re-ran the complete deterministic and interruption/resume validation set after the portability patch.

## 14.1.1 — 2026-08-17

- Renamed the project from its former product-associated name to **LatticeVale** across release documentation, installer UI, project-owned scripts, shortcuts, scheduled tasks, and public repository metadata. Upstream dependency names remain only where technically required.
- Added backward-compatible migration/recognition for legacy project-owned Windows tasks, shortcuts, relay artifacts, backup markers, and Matrix/E2EE identifiers so existing installations are not broken by the rebrand.
- Fixed Obsidian vault conversion on eligible WSL installations that use a custom Windows-drive automount root instead of `/mnt`; the installer now validates the translated path by its actual Windows-backed filesystem type.
- Improved Windows Tailscale Serve reconciliation by inspecting both `serve status --json` and `serve get-config --all`, with compatibility fallback for clients that do not expose the newer full-config command.
- Hardened release verification so the source manifest must match the release tree exactly: duplicate entries, missing files, unexpected unmanifested files, and hash mismatches all fail verification.
- Hardened manifest handling further against path traversal/root escapes, Windows case-colliding entries, alternate-data-stream style path ambiguity, and reparse-point release files.
- Added explicit Windows PowerShell 5.1 parsing alongside PowerShell 7 parsing in GitHub CI for every shipped PowerShell entry point.
- Added multi-WSL safety around global `.wslconfig` changes: if another distro is running, LatticeVale requires explicit confirmation before writing a change that will require global `wsl --shutdown`.
- Neutralized newly created installer staging, backup, task, shortcut, relay, and local-app-data names; legacy product-associated identifiers remain only in ownership-checked migration logic so older managed installs can be repaired without leaving duplicates.
- Preserved the v14.0 profile-specific Matrix/model topology, preservation-first repair semantics, source-only distribution policy, and optional per-install Windows Start/Shut Down shortcuts.

## 14.0 — 2026-08-17

- Added profile-name-agnostic secondary Matrix identities and encrypted rooms.
- Bound secondary Matrix provisioning to the exact profile and its verified configured model, for both cloned and independently selected model/provider setups.
- Replaced upstream profile `--clone` during LatticeVale-managed creation with a credential-safe clone: create empty, stop the auto-registered gateway, then copy provider/model/config/skills while excluding messaging and API-server credentials.
- Added separate profile Matrix credentials, device/recovery state, room allowlists, and supervised profile gateways.
- Added conservative repair migration for older named profiles with no prior Matrix intent.
- Added initial-questionnaire Windows Obsidian vault-path selection.
- Added optional current-user Start / Shut Down desktop shortcuts bound to the selected distro, Linux user, stack path, and saved LatticeVale component choices; shutdown terminates only the selected distro.
- Start/restart/update now actively reconcile only the Matrix-enabled profile gateways selected in `install-options.json`, while Kanban-only workers remain stopped.
- Direct Tailscale EXE downloads now require a valid Tailscale-identifiable Authenticode signature before execution and are deleted after the install attempt.
- Fixed an empty-optional-infrastructure edge case where a helper could return status 1 under inherited Bash `ERR` tracing despite a valid empty service selection.
- Hardened GitHub CI against its opaque-code scanner matching its own workflow regex and made text line endings deterministic across Windows/Linux checkouts for release-manifest verification.
- Preserved v13.16.10/11 Obsidian path/mount hardening.
- Preserved `gateway.multiplex_profiles: false` for the managed topology.
- Stopped retaining the human Matrix admin password as a long-lived v14 management secret.
- Preserved administrator-managed Synapse registration secrets rather than deleting them unconditionally.
- Added `install.ps1`, source-manifest verification, `SECURITY.md`, CI validation, contribution guidance, and GitHub issue templates.
- Kept the v13.16.11 preservation-first/local-first repair behavior as the baseline.

## 13.16.11 — prior confirmed baseline

- Full repair reliability audit.
- STOPPED vs BROKEN semantics.
- Local-first repair with `--pull never --no-build` before escalation.
- WSL stdout/stderr isolation.
- Obsidian legacy mount/path hardening.
- Safer backup/staging/recursive operations.
- 49 deterministic historical fixture suites at that milestone.

Detailed historical changes are consolidated below in this file.
---

## Consolidated detailed historical patch/audit notes

The following material was previously stored in separate version-specific files. It is retained here so patch/version notes have one canonical home.

The original pre-LatticeVale v13 patch-note files from the v13.16.6 bundle are also preserved verbatim under `docs/legacy-patch-notes/hermes-wsl-foundry-v13/` for granular historical auditing. Those files are archival; current behavior is defined by the current LatticeVale documentation and source.

### Former file: `LatticeVale-Core/RELEASE-NOTES-v13.md`

# LatticeVale v13 release notes

## v13.16.7 — repair checkpoint semantics + managed-options recovery

v13.16.7 fixes the repair behavior that could make a newer LatticeVale ZIP look like a clean/reinstall pass. Prior builds embedded `installerVersion` in the checkpoint fingerprint, so every completed stage became stale whenever the bundle version changed. The fingerprint now contains stable component selections only. Explicit per-stage revision numbers provide the release migration mechanism, allowing a future bundle to rerun only the stage whose managed behavior actually changed. Pre-v13.16.7 completed checkpoints are adopted during Resume / repair only after their live verifier succeeds.

Explicit **Reconfigure providers/profiles** requests now bypass completed provider/profile checkpoints, fixing the same-version case where the requested setup action could be skipped. Explicit Matrix identity rebuild likewise bypasses its checkpoint.

A recognized managed stack whose current `install-options.json` is missing/unreadable no longer falls through into fresh-install component selection. LatticeVale attempts read-only recovery from the newest valid installer-created `backups/pre-*/installer-config.tar.gz`; if no valid prior metadata exists, it stops and preserves the stack.

`./manage.sh update` remains the separate intentional broad upstream/component upgrade path. Repair maintenance, database preservation, Matrix/profile identity preservation, and all v13.16.6 integration behavior remain in force.

## v13.16.6 — post-install integration reconciliation

v13.16.6 folds the post-install issues found during live use back into both **Fresh** and **Resume / repair**. Matrix-enabled default profiles now explicitly enable reaction controls and sender-scoped approval reactions (`MATRIX_REACTIONS=true`, `MATRIX_APPROVAL_REQUIRE_SENDER=true`) so supported Element approval prompts can expose clickable reaction actions without hand-editing runtime environment files.

Kanban-enabled installs now receive an installer-owned automatic-orchestration policy while preserving all SOUL content outside the marked LatticeVale block. Substantive work can route through native Kanban automatically, while simple requests stay direct. The default dispatcher is deliberately conservative after observed provider 429 exhaustion: 2 workers globally, 1 per profile, one auto-decomposition per tick, and a 30-second dispatcher interval. Clean/reconfigure can choose different worker caps; repair preserves saved valid caps and upgrades older installs to these defaults.

Windows Obsidian integration no longer tells native Windows Obsidian to open `\\wsl.localhost\...` as a vault. LatticeVale uses a Windows-local drive vault (auto-reusing one registered local Obsidian vault when unambiguous, otherwise the Windows Documents folder default), resolves its WSL `/mnt/<drive>/...` path, mounts that folder into Hermes/QMD as `/vault`, and non-destructively copies legacy stack-vault files into it without overwriting Windows-side files. The legacy WSL vault remains preserved as fallback data. Repair also detaches a legacy host-level mount at the exact LatticeVale vault target and backs up `/etc/fstab` before removing only matching bind entries, preventing earlier manual bind-mount guidance from conflicting with the new Compose mount.

QMD's built-in indexer now defaults to every 2 hours (7200 seconds). Repair migrates only the former LatticeVale 6-hour default, preserves deliberate custom intervals, and removes only the exact legacy `HERMES_QMD_REINDEX` crontab line previously recommended by LatticeVale so duplicate reindex loops are avoided.

All v13.16.1-v13.16.5 safety fixes remain in force: independent profile gateways, bounded Matrix recycle, advisory cross-signing log confirmation, non-fatal optional recovery-key handling, hidden Windows relay, and supported WSL service-instance lifetime.

## v13.16.5 — hidden Windows relay + WSL persistence reconciliation

v13.16.5 prevents the installer-owned Windows-native Tailscale relay from leaving a visible long-running PowerShell console by adding `-WindowStyle Hidden` to the scheduled relay process. Closing an unrelated terminal is therefore no longer capable of accidentally killing the relay simply because its console was visible.

When Tailscale Dashboard or Matrix exposure is selected, clean/reconfigure and Resume / repair runs also force the supported WSL `[general] instanceIdleTimeout=-1` service-instance lifetime policy even if an older saved install recorded `keepWslServicesRunning=false`. No polling loop, `sleep infinity`, or fake keepalive process is introduced.

## v13.16.4 — Matrix integration-stage false-failure fix

v13.16.4 fixes a shell-status regression shared by Fresh and Resume / repair installs. `apply_matrix_runtime_env` no longer returns failure merely because its last optional Matrix value is absent, and the one-time `MATRIX_RECOVERY_KEY_OUTPUT_FILE` setting is no longer copied back into Hermes runtime configuration after cross-signing bootstrap. Required Matrix settings remain enforced by the existing integration verifier. No Matrix identity, crypto state, credentials, room, profile, memory, session, or database data is recreated or deleted.

## v13.16.3 — simplified Matrix cross-signing completion

v13.16.3 keeps the bounded Hermes recycle from v13.16.2 but makes the final cross-signing confirmation tolerant again. The exact upstream `Matrix: cross-signing verified via recovery key` log line is no longer a fatal success criterion for either Fresh or Resume / repair installs. Once the retained recovery key is applied, one-time recovery-key output state is cleaned up, and Hermes restarts and becomes command-ready, LatticeVale checks briefly for the confirmation log. If it is missing or delayed, the installer reports a warning and continues. Matrix identity, crypto state, access token, room, and recovery material are preserved.


## v13.16.1 — profile gateway isolation hardening

v13.16.1 preserves the complete v13.16.0 clean/repair behavior and adds a deterministic
standalone-gateway invariant for every installer-managed Hermes profile. LatticeVale now
normalizes `gateway.multiplex_profiles` off in YAML, removes the container-wide
`GATEWAY_MULTIPLEX_PROFILES` opt-in, sanitizes clones, verifies the setting during
integration repair, and surfaces accidental multiplex enablement as a repair condition.
This is a LatticeVale-side mitigation for unresolved upstream multi-profile multiplexer bugs;
no Hermes source code is monkey-patched and no profile/user data is discarded.
Validation: **40/40 deterministic/static fixtures pass** for v13.16.1; the same two historical environment-dependent lifecycle simulations remain outside that deterministic count.


## v13.16.0 — comprehensive repair + aged-install maintenance

v13.16.0 retains the full v13.15.0 clean-install behavior and adds a repair-only
maintenance layer for installer-managed stacks that have accumulated normal age/storage
drift. Managed Resume / repair runs now audit WSL logical free space, stack footprint and
Docker usage; clear disposable APT/staging residue; prune Docker dangling images; prune
only unused build cache older than 30 days; retain the newest eight installer-generated
pre-version configuration snapshots; cap oversized installer event history; and run
bounded normal PostgreSQL `VACUUM (ANALYZE)` for Synapse/Honcho when available.

Persistent Hermes profiles/memory/sessions, Matrix/Synapse/Postgres data, E2EE state, QMD
data, Ollama models, vault/workspace files, credentials and user-created backups are not
part of automatic cleanup. LatticeVale does not use `docker system prune`, `docker image prune
-a`, `docker volume prune`, broad container/network pruning, `VACUUM FULL`, Matrix/media
purges, or automatic WSL VHD compaction/sparse conversion.

All twelve Compose services now use Docker's bounded `local` logging driver with `20m`
max-size and five files, preventing new container logs from growing without limit. Repair
configuration snapshots also skip an already-pathological installer log tree rather than
duplicating it before cleanup. The state audit now reports logical WSL storage pressure
without misrepresenting that value as the physical Windows `ext4.vhdx` footprint.

## v13.15.0 — Matrix owner verification + standard Tailscale HTTPS

v13.15.0 keeps the user's normal launcher responsible for starting WSL/Hermes and does not add an artificial keepalive process. The optional WSL `[general] instanceIdleTimeout=-1` service-instance lifetime policy remains separate from startup, and full stack Windows-logon auto-start still defaults to No.

Private Matrix remote access remains on **Tailscale Serve** rather than Funnel, but the installer default moves from HTTPS 8448 to standard HTTPS 443. New installs therefore advertise `https://<node>.<tailnet>.ts.net` to Element/Element X. Resume / repair migrates only the old LatticeVale-owned 8448 default; custom ports remain custom. Dashboard stays on 9443.

The Windows-native relay is now registered at Windows logon whenever Tailscale exposure is selected, even when the stack itself is on-demand. This does not recreate stack auto-start: without explicit `autoStart`, the relay only binds the Windows localhost ports and waits. It checks the cached WSL target directly first, does not issue in-distro discovery commands while WSL is stopped, and reconnects after the user's launcher starts Hermes.

Fresh Matrix installs now retain Hermes's generated cross-signing recovery key. LatticeVale uses `MATRIX_RECOVERY_KEY_OUTPUT_FILE` for one-time `0600` output, stores the key as `MATRIX_RECOVERY_KEY`, removes the one-time file/setting, restarts Hermes, and verifies the `Matrix: cross-signing verified via recovery key` startup result. This complements the existing encrypted-room creation, required E2EE mode and stable `<legacy Matrix bot device ID>` device ID.

Repair preserves the existing Matrix account, room, token, device, crypto store and Synapse data. A legacy identity that already bootstrapped cross-signing but did not retain its recovery key is not destructively reset and no longer blocks unrelated Windows/Tailscale reconciliation.

# LatticeVale v13 — Resilient Recovery Release

## v13.14.0 — clean-install WSL lifecycle + on-demand startup hardening

v13.14.0 is based on a clean v13.13.4 install and the subsequent live troubleshooting handoff. It fixes the confirmed root-invocation stack helper defect by persisting the selected Linux user, home, and exact stack directory into `/usr/local/sbin/hermes-stack-start`; the helper passes the stack directory as an argument when it runs Compose as that non-root user, so root's `$HOME` cannot become `/root/hermes-stack`.

The release also separates WSL service lifetime from Windows logon auto-start. On Store/MSIX WSL 2.5.4+, the installer offers a global `[general] instanceIdleTimeout=-1` setting and performs a 75-second no-command persistence test after applying it. It intentionally does not force the separate `[wsl2] vmIdleTimeout`. Existing `.wslconfig` content is preserved and backed up before changes.

Fresh full-stack auto-start now defaults to No. When it is off, the Tailscale relay Scheduled Task is triggerless/passive and does not wake a stopped WSL distro; `./manage.sh start` launches the relay after the user intentionally starts Hermes, and `./manage.sh stop` ends it. If auto-start is explicitly enabled, the relay receives its logon trigger and stack-recovery permission.

Regression coverage now includes direct expansion of the shipped helper heredoc under `HOME=/root`, WSL lifetime policy checks, passive relay/no-hidden-autostart checks, and the existing PowerShell variable-before-colon scans.

The final online release audit also advances the clean-install Hermes image pin from `v2026.8.13` (v0.20.1) to the newly released stable `v2026.8.16` (v0.20.2). Synapse remains pinned to stable `v1.158.0`; `v1.159.0rc1` is still a prerelease.

## Why v13 exists

The reported v12 run completed substantial work but stopped in the `infrastructure` stage because `hermes-qmd` never became healthy. The existing v12 recovery system can detect the managed stack and offer **Resume / repair**, but simply rerunning v12 is not sufficient: it would retry the same moving QMD dependency, and old checkpoints could allow a later patch bundle to skip migrations whose component choices had not changed.

v13 is designed for both clean installs and interrupted/patch installs. It preserves existing persistent data, re-verifies live state, performs v13 migrations once, and resumes from the earliest stage that is actually incomplete or broken.

## v13 changes

- Installer-version-aware checkpoint fingerprints. A v12 -> v13 run rechecks/migrates each stage once; same-v13 reruns remain idempotent and use live verification before skipping work.
- QMD is pinned to published `2.5.3` instead of `latest` because the newer v2.6.3 line has a documented fresh-store MCP HTTP SQLite regression.
- QMD v2.5.3 hardcodes its HTTP listener to localhost and has no `--host` option. The Docker image now applies a fail-closed one-location patch to the compiled listener so Hermes can reach QMD from another container. No QMD port is published to Windows.
- QMD starts independently from the bulk infrastructure group, receives targeted diagnostics, and can reconstruct a derived SQLite index after preserving the old index under a timestamped backup when logs identify a SQLite/schema problem.
- QMD audit/status checks execute inside the container, matching the Docker-internal network design.
- Dashboard scrypt hashes are stored as single-quoted env-file literals so Docker Compose does not interpret `$...` fragments as interpolation variables.
- Existing self-hosted Honcho source is reused during installer repair rather than silently advancing to a new upstream commit. `./manage.sh update` remains the explicit opt-in path for updating Honcho.
- The old Honcho `releases/latest` lookup was removed from the explicit update path because upstream self-hosting is repository-based and the release endpoint is not a reliable source for this project.
- Recovery follows the Linux account that already owns the managed stack even if the distro's default user later changes.
- Linux home directories are discovered from `getent passwd`; final WSL UNC paths are no longer hardcoded to `/home/<user>`.
- Windows auto-start Scheduled Task names are scoped by Windows user and WSL distro, avoiding cross-user/cross-distro collisions. A current user's recognized legacy task is migrated safely.
- Distro-name handling accepts normal registered WSL names while rejecting control characters/double quotes used in command construction.
- This bundle explicitly treats x64/AMD64 Windows + Ubuntu WSL2 as eligible; ARM64 is rejected until every bundled image/dependency is validated end-to-end.
- The QMD patch helper is included in bundle completeness checks and in state audits when QMD is selected.

## Expected recovery for the reported interrupted install

Run the v13 installer against the same existing Ubuntu distro and managed stack and choose **Resume / repair**. Do not delete `~/hermes-stack`, unregister the distro, or remove Docker data first.

v13 will preserve the existing stack, invalidate only v12 checkpoint fingerprints, reuse the already-present Honcho source, keep downloaded Ollama data/models, rebuild/restart QMD under the pinned compatibility path, and continue through the remaining stages according to live verification.

## Validation performed before packaging

Passed in the build sandbox:

- compatibility policy fixtures;
- distro diagnostic regression fixtures;
- Hermes local-AI fixtures;
- Honcho local configuration fixtures;
- install-order fixtures;
- Ubuntu OS-release fixtures;
- recovery/checkpoint fixtures;
- self-hosting fixtures;
- state-audit fixtures;
- storage-policy fixtures;
- v13 recovery-hardening fixtures;
- WSL output/preflight fixtures;
- static audit of the 12-service Compose model;
- Bash syntax checks for shipped shell scripts;
- Python compile checks for shipped Python/tests;
- YAML parse of `compose.yaml`;
- isolated unit check of the fail-closed QMD listener patcher;
- the direct v13.14 helper-generation regression with `HOME=/root`;
- **37/37 deterministic/static Python regression fixtures** (excluding the two environment-dependent destructive/interruption simulations).

A real Windows/WSL/Docker runtime is not available in the build sandbox, so Windows PowerShell execution, WSL registry/BasePath queries, Scheduled Tasks, Winget, Windows Tailscale, container image building, and actual service startup still require the target Windows machine. The installer is intentionally recovery-safe so failures there remain resumable rather than requiring a clean reinstall.

## RC5 setup-scope clarification

The installer now uses Hermes's focused `model` command for AI provider/model selection instead of the all-in-one setup wizard. Installer-managed Matrix/browser/search/memory integrations are applied separately, secondary profile prompts are labeled explicitly, fresh profiles receive local browser tooling by default, and new Matrix bot identities retain their generated password in the owner-only secret file for explicit recovery/manual login use.


## RC6 post-install readiness and repairability

RC6 distinguishes normal container startup from persistent failure, adds a bounded `manage.sh verify` command, disables SearXNG's host-bind ownership takeover, and re-verifies user-writeable installer paths after services have actually started.

## v13.13.4 — native relay PowerShell parser hotfix

v13.13.4 fixes a deterministic parser failure caught by the v13.13.3 relay self-test. `LatticeVale-WslNativeRelay.ps1` logged errors with expandable strings containing `$DistroName:`. PowerShell treats an unbraced variable followed immediately by `:` as a scoped/provider-style variable reference, so both PowerShell 7 and Windows PowerShell 5.1 rejected the relay before it could run. The relay now uses `${DistroName}:` and regression coverage scans both shipped PowerShell entrypoints for the complete variable-before-colon bug class. This affects both fresh installs and Resume/repair runs.

## v13.13.3 — relay Scheduled Task engine/context hardening

v13.13.3 fixes a v13.13.2 run where the parent installer successfully resolved and verified the WSL NAT IPv4 but the persistent relay Scheduled Task exited immediately with `LastTaskResult=1` before the relay wrote its first startup line. LatticeVale now prefers PowerShell 7 (`pwsh.exe`) for the relay when available, matching the live-tested Windows relay configuration, and falls back to Windows PowerShell 5.1 only after the exact script/config passes a bounded self-test. The relay task runs as the interactive Windows identity at Highest run level and receives an explicit working directory.

The exact failed relay script/config is retained after a failed attempt (the dead task is still unregistered), so diagnostics inspect the current failed artifact instead of a stale manual relay. The self-test validates the relay configuration, listener availability, inline C# compilation, and seeded/reachable WSL backend before Task Scheduler is asked to keep the process alive.

## v13.13.2 — relay IP discovery and Matrix rollback hardening

v13.13.2 fixes a relay task failure observed after v13.13.1 had already completed the Linux stack and every Windows-local service probe. LatticeVale now resolves and directly verifies the WSL NAT IPv4 in the parent installer, seeds that address into the Windows-native relay, and lets the relay open its listeners from that proven address before it needs to invoke WSL itself. Later refresh uses both `eth0` and `hostname -I` plus compatible WSL command forms.

The persistent relay no longer requests an administrator runtime token, and relay logs are rotated at each reconciliation so stale troubleshooting output cannot be mistaken for the current failure. Matrix `public_baseurl` reconciliation is now idempotent and skips Synapse restart when the value is already correct; actual changes use a longer bounded readiness check.

## v13.13.1 — native relay startup stall hotfix

v13.13.1 fixes the installer appearing to freeze at `Creating Windows-native WSL relay for Tailscale` after the Linux stack and all Windows-local service checks had already succeeded. The v13.13.0 relay helper invoked the full installer-owned stack recovery helper before checking whether the WSL backends were already reachable; that fallback is allowed up to 900 seconds. The parent installer simultaneously waited up to 900 seconds without progress output.

The relay now probes the current WSL backend endpoints first for up to 15 seconds and invokes stack recovery only if that direct check fails. Installer-side relay verification is bounded to 120 seconds, prints a heartbeat every 10 seconds, exits early when the Scheduled Task terminates unexpectedly, and reports its `LastTaskResult` plus relay-log tail. Resume/repair also waits for a prior installer-owned relay task to stop before replacing its script/config, preventing stale relay mutex/listener races. Persistent logon-time recovery behavior remains intact.

The Hermes `SyntaxWarning` about `venv\Scripts` seen immediately before the Windows stage is an upstream Python warning emitted during Kanban initialization; it is not the source of this stall.

## v13.13.0 — native Tailscale relay + Matrix clean-install hardening

The final Windows troubleshooting pass proved that the Linux stack, WSL NAT address, Docker service bindings, and Windows-local `netsh portproxy` listeners could all be healthy while the Windows Tailscale daemon still returned HTTP 502 when Serve targeted those portproxy listeners. A normal Windows user-space localhost listener worked through the same Serve path. v13.13.0 therefore replaces portproxy as the runtime bridge with a persistent Windows-native TCP relay and retains portproxy code only for ownership-checked migration cleanup.

v13.13.0 also makes fresh Matrix rooms encrypted from creation, uses a stable Hermes Matrix device ID, negotiates a room version from Synapse's advertised capabilities, pins Synapse to stable `v1.158.0`, and lets Hermes auto-join the encrypted invitation only after its E2EE store initializes. This avoids both the Element "unencrypted room" warning and the known Hermes fresh-E2EE-store/already-joined edge case.

Windows add-on status now trusts live WinGet inventory, and the normal Windows logon startup path retries the stack startup helper rather than requiring a manual stack start after boot.

### Former file: `LatticeVale-Core/HOTFIX-v13.1.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.1 storage-repair hotfix

This hotfix fixes a preflight deadlock in v13: after a successful partial install consumed Docker/model space, a rerun could fall below the 50 GiB fresh-install free-space reserve and be blocked before the installer had a chance to detect the managed stack and offer Resume / repair.

Policy after this hotfix:
- Fresh/unmanaged installs: unchanged; host partition must be over 50 GiB total and have at least 50 GiB free.
- Existing installer-managed Hermes stack: Resume / repair is allowed with at least 10 GiB host-partition free space.
- The total-partition requirement remains unchanged.
- Below 10 GiB free, repair remains blocked to avoid worsening a critically low-space system.

No Linux stack schema/checkpoint version is changed because this is a Windows preflight-only hotfix.

### Former file: `LatticeVale-Core/HOTFIX-v13.2.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.2 PowerShell HOME-collision hotfix

Fixes a Resume / repair crash on Windows PowerShell/PowerShell 7 caused by helper-function parameters named `$Home`. PowerShell variable names are case-insensitive, so `$Home` collides with the built-in read-only `$HOME` automatic variable.

The affected helper parameters are now named `$LinuxHome`. Linux `$HOME` references embedded inside Bash command strings are intentionally unchanged.

This hotfix includes the v13.1 storage-repair changes and does not change Linux stack/checkpoint schema version v13.

### Former file: `LatticeVale-Core/HOTFIX-v13.3.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.3 PowerShell reserved-variable safety hotfix

This hotfix keeps all v13.1/v13.2 recovery changes and leaves the Linux stack/checkpoint schema at v13.

## Changes

- Renames the two remaining installer locals named `$args` to non-automatic names (`$actionArguments` and `$auditArguments`).
- Adds regression coverage that rejects writes to PowerShell automatic/read-only/constant variable names.
- Adds Bash regression coverage for assignments to shell variables reported read-only by the runtime.
- Retains the v13.2 `$HOME`/`$Home` collision fix and v13.1 managed-repair storage exception.

### Former file: `LatticeVale-Core/HOTFIX-v13.4.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.4 hotfix

- Trims leading/trailing whitespace from interactive timezone input before validation.
- Blank timezone input continues to use the saved/default timezone.
- Invalid timezone characters now reprompt instead of aborting the installer.
- Retains all v13.1-v13.3 recovery, storage, and runtime-variable safety fixes.

### Former file: `LatticeVale-Core/HOTFIX-v13.5.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.5 hotfix

Fixes WSL bootstrap staging for the QMD bind patch helper. v13.4 validated that
`stack/patch-qmd-bind.py` existed in the extracted bundle but omitted it from the
files copied into the temporary WSL staging directory. `bootstrap.sh` therefore
failed when installing that file. v13.5 stages the helper with the rest of the
stack bundle.

### Former file: `LatticeVale-Core/HOTFIX-v13.6.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# LatticeVale v13.6 hotfix

Fixes interactive Hermes provider/profile setup when the Windows installer invokes the Linux bootstrap through `wsl.exe`.

The bootstrap now runs `configure-stack.sh` through `runuser --pty`, creating a Linux pseudoterminal for the unprivileged Ubuntu user. This preserves the upstream Hermes `docker run -it ... setup` / `docker exec -it ... setup` behavior instead of disabling TTY allocation.

Recovery remains idempotent: profiles already created before an interruption are reused, and provider/model setup runs only when their model configuration is still incomplete.

### Former file: `LatticeVale-Core/HOTFIX-v13.7.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.7 hotfix

Fixes Windows-to-WSL staging permissions for the existing-install audit.

`Invoke-BundledStackAudit` created `/tmp/hermes-audit-...` as root with the default
0755 permissions, then attempted to copy `state-audit.py` into that directory via
`\\wsl.localhost`. Windows therefore could read/traverse the directory but could not
create the file, causing `Copy-Item: Access ... is denied` before recovery could run.

v13.7 grants 0777 only to the random, short-lived audit staging directory, matching
the already-existing main bootstrap staging policy. The directory is always removed
by the function's `finally` cleanup. Installed Hermes data and persistent permissions
are unchanged.

### Former file: `LatticeVale-Core/HOTFIX-v13.8.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.8 hotfix

Fixes profile provider/model setup failing with:

```
cannot attach stdin to a TTY-enabled container because stdin is not a terminal
```

`bootstrap.sh` already supplies a PTY with `runuser --pty`, but `stage_profiles`
was reading its worker loop from a `jq` process substitution. That redirected the
loop body stdin away from the PTY and into a pipe. v13.8 materializes the worker
JSON with Bash `mapfile` before entering the loop, so each interactive
`docker exec -it ... setup` inherits the PTY as intended. Existing profiles and
provider data are preserved; incomplete profile setup resumes on rerun.

### Former file: `LatticeVale-Core/HOTFIX-v13.9.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.9 hotfix — clean-install hardening

- Uses the selected Ubuntu account's actual primary UID/GID instead of assuming a same-named group.
- Carries the exact bundle version into installer state/checkpoint fingerprints so every hotfix can revalidate prior stages safely.
- Seals temporary WSL staging directories after Windows finishes copying and before root executes staged content.
- Retains all v13.1-v13.8 recovery, storage, variable-safety, timezone, QMD staging, PTY, and profile-loop fixes.

### Former file: `LatticeVale-Core/HOTFIX-v13.10.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.10 release-candidate portability audit

v13.10 is a full clean-install + repair portability pass over the v13.9 bundle.

- Corrects `state-audit.py` so exact v13.x hotfix versions are valid and mismatched option/state versions are reported as outdated.
- Rejects Windows Server, non-amd64 Ubuntu, Docker Desktop WSL integration, active rootless Docker, and unknown/custom injected Docker daemons before the installer modifies Docker packages.
- Requires a Hermes-compatible normal Linux user and verifies its real UID/GID, writable home, and Linux-native home filesystem.
- Makes five Windows-facing localhost ports installer state; fresh installs retain defaults when free and automatically select safe alternatives when occupied.
- Refuses to remove/reuse foreign Docker containers or networks that collide with the fixed Hermes Compose namespace.
- Uses the authoritative Windows identity for scheduled tasks.
- Makes Dashboard and Matrix username validation trim/re-prompt rather than aborting the run.
- Guarantees `tzdata` is present and validates IANA timezone names against installed zoneinfo.
- Uses current Tailscale Serve disable syntax.
- Pins all installer Docker operations to the distro-local `/var/run/docker.sock` so user Docker contexts cannot redirect mutations.
- Stops overwriting Ubuntu's generic `20auto-upgrades`; unattended-update policy uses an installer-owned APT file with conservative legacy cleanup.
- Enables the published Hermes API explicitly, generates/preserves a strong bearer key, keeps host exposure loopback-only, leaves browser CORS disabled by default, and verifies API health during reconciliation.
- Moves default Hermes `API_SERVER_*` configuration from the container-wide environment into `data/hermes/.env`, preserving the existing bearer key during migration so named profile gateways cannot inherit/collide on the default API port.
- Corrects fresh Matrix `public_baseurl` generation to use the selected Matrix host port rather than unrelated configuration input.
- Pins fresh-install Honcho source to audited commit `444897975c95393b0d48024470ece03c025d3aa4`; repairs reuse their existing checkout and `./manage.sh update` remains the explicit opt-in to advance.
- Retains all v13.1-v13.9 recovery, permission, staging, TTY, QMD, Honcho, and exact-checkpoint hardening.

- Declares PowerShell 5.1 as the minimum supported host shell so unsupported PowerShell versions fail before preflight.
- Treats persisted `install-options.json` as untrusted repair state and validates worker names, booleans, model tags, and TCP ports before they can influence paths or Docker commands.
- Rejects symbolic links at Hermes data ownership roots that current Hermes container startup recursively `chown`s, preventing a customized/partial stack from redirecting ownership changes outside the dedicated bind mount.
- Uses JSON + `jq` for existing Docker-network attachment inspection rather than a fragile Go-template newline construct.
- Detects an existing per-user/rootless Docker setup and refuses dual-daemon operation; this stack always targets the rootful local `/var/run/docker.sock` engine it owns.
- After Linux health checks pass, verifies each selected localhost-published service from Windows and warns instead of printing a misleading Windows URL when customized WSL networking prevents localhost forwarding.
- Backs up pre-existing Docker APT source/key files before normalizing an incomplete Docker installation to the official Docker CE repository.

### Former file: `LatticeVale-Core/HOTFIX-v13.11.md`

# v13.11 RC4 — release-candidate permission and portability hardening

- Makes repair discovery/root metadata readback resilient to an older run leaving `~/hermes-stack` or `install-options.json` root-owned.
- Reconciles ownership only on installer/user-owned writable trees using the selected user's real numeric UID/GID.
- Never recursively chowns PostgreSQL/Ollama data roots (`data/synapse-db`, `data/honcho-db`, `data/ollama`).
- Keeps private files/directories owner-writable (`0600`/`0700`) rather than making them read-only.
- Verifies required paths are writable by the selected Ubuntu user before configuration starts.
- Adds `permissions` as a mandatory state-audit component with exact failing paths.
- Adds a permanent permission-mode policy test that rejects owner-read-only chmod/install modes and unexpected Compose read-only mounts.
- Retains symlink guards around recursive ownership-repair roots.
- Pins Hermes to `nousresearch/hermes-agent:v2026.8.13` rather than the moving `latest` channel.
- Retains the v13.10 cross-machine safeguards: local rootful Docker ownership, Docker Desktop/rootless conflict rejection, Linux-native home validation, exact-version checkpoints, private WSL staging, TTY-safe profile setup, isolated APT policy, profile-local API settings, port/namespace collision protection, and Windows localhost verification.

- RC2 adds explicit file-level selected-user writeability verification and rejects symlink replacements for installer-owned support files before root-assisted repair writes.
- Centralizes the Windows build minimum and managed-repair free-space floor in `compatibility.conf` alongside the existing Ubuntu/storage/WSL probe policy, with boundary fixtures.

- RC3 fixes a PowerShell parser error in WSL staging diagnostics by delimiting a variable immediately followed by `:` and adds a regression check for the same interpolation pattern.

## RC4 - WSL stdin staging fix

- Replaced nested `bash -c` positional-argument staging with direct `dd of=<path>` over `wsl.exe` stdin.
- Applies the requested Linux mode with a separate root `chmod` call after transfer.
- Avoids the RC3 failure where the nested shell received an empty `$1` and attempted to redirect to an empty filename.
- Keeps the staging directory private (`0700`) throughout transfer.

## RC5 - scoped Hermes setup, local-browser defaults, and Matrix credential clarity

- Replaces the all-in-one `hermes setup` calls with `hermes model` for the default profile and `hermes -p <name> model` for secondary profiles. This keeps provider/model selection interactive while leaving Matrix, browser, search, memory, Dashboard, and other LatticeVale-managed integrations under installer control.
- Makes terminal messages explicitly identify **DEFAULT** versus **SECONDARY** profile model selection.
- Enables the Hermes `browser` toolset on managed profiles and defaults `browser.engine` to `auto` only when unset. Existing browser provider/backend choices are preserved; fresh installs add no cloud-browser credentials, so the browser source remains local.
- Retains the generated Matrix bot password in owner-only `secrets/matrix-bot.env` on new Matrix identities while continuing to authenticate Hermes with the access token. The password is never copied into the Hermes runtime `.env`.
- Adds `./manage.sh matrix-credentials` for deliberate secret display and improves `matrix-info` with the internal homeserver/user ID.
- Documents the exact answers that previously caused ambiguity: local browser vs Browser Use cloud, first/default vs second/secondary model setup, OpenCode Go selection, Matrix homeserver URL, bot user ID, access token, and bot-password retention behavior.


## RC6 - post-install startup/permission verification

- Treats Docker health `starting` and newly started selected containers as STARTING rather than immediately BROKEN.
- Adds `./manage.sh verify [seconds]` for bounded startup-aware verification (300 seconds by default).
- Adds failure details to the human-readable state audit so permission faults name the affected path.
- Sets SearXNG `FORCE_OWNERSHIP=false` so the upstream entrypoint does not take ownership of LatticeVale's bind-mounted config.
- Reconciles and verifies installer/user-owned writable roots again after containers have started; PostgreSQL/Ollama container-owned data remains excluded.
- Adds README post-install instructions for verification, dashboard/profile checks, chat tests, and first backup.

### Former file: `LatticeVale-Core/HOTFIX-v13.11-RC7.md`

> **LatticeVale historical compatibility document.** This file is retained for regression/history context.

# v13.11 RC7

Post-install verifier correction:

- Windows-only Tailscale/add-on/auto-start PARTIAL states no longer force the WSL-side audit to report `NEEDS_REPAIR`.
- `./manage.sh verify` now waits for Linux services that are still `STARTING` even when optional Windows follow-up remains.
- A healthy Linux stack can complete verification with an explicit Windows follow-up warning.
- Windows-side integration state remains authoritative in the PowerShell installer and is not silently marked healthy by WSL.

### Former file: `LatticeVale-Core/HOTFIX-v13.12.md`

# LatticeVale v13.12

## Windows Tailscale / WSL2 bridge fix

This release preserves the v13 stack and data layout while changing Windows Tailscale exposure for Dashboard and Matrix.

### Why

Windows Tailscale Serve can return HTTP 502 when it directly proxies a service reached through WSL2 Windows-localhost forwarding. Local Windows access can still work, which makes the failure easy to misdiagnose as a Matrix problem.

### New path

For each selected remote service:

1. the Docker service is bound to the WSL VM interface only when its Tailscale exposure is selected;
2. LatticeVale discovers the current reachable WSL IPv4;
3. Windows IP Helper is enabled/started when required;
4. an installer-owned `netsh interface portproxy` rule maps a dedicated Windows loopback bridge port to the WSL IPv4/service port;
5. Windows Tailscale Serve proxies to that Windows loopback bridge;
6. a Windows Scheduled Task periodically refreshes the bridge if WSL receives a different NAT IPv4.

Default bridge ports are 19119 for Dashboard and 18008 for Matrix. They are changed automatically if unavailable.

### Existing installations

Rerunning the installer migrates legacy installer-owned direct Serve rules through the normal repair/reconciliation path. Matrix identities, rooms, PostgreSQL data, Hermes profiles, models, notes, Honcho state, and other persistent data are preserved.

If global `.wslconfig` explicitly uses `networkingMode=mirrored`, LatticeVale offers to back it up and change only that setting to `networkingMode=nat`. Because `.wslconfig` is global to WSL2, the change requires explicit confirmation.

### Matrix identity

Remote access changes only Synapse `public_baseurl`. It does not change `server_name=hermes.local` or Hermes's Docker-internal `MATRIX_HOMESERVER=http://synapse:8008`.

### Former file: `LatticeVale-Core/HOTFIX-v13.12.1.md`

# LatticeVale v13.12.1

Quick repair-safety hotfix for the v13.12 Windows Tailscale / WSL-IP bridge migration.

- Keeps the v13.12 Windows-only Tailscale architecture unchanged.
- Existing managed installs still migrate through **Resume / repair installation**.
- If Matrix Tailscale HTTPS verification fails after Synapse `public_baseurl` was changed, the installer now rolls `public_baseurl` back to the local Matrix URL after removing the failed Serve rule.
- No Hermes profiles, Matrix identities/rooms/databases, Honcho data, Ollama models, QMD notes, or other persistent user data are intentionally rebuilt by this hotfix.

### Former file: `LatticeVale-Core/HOTFIX-v13.12.2.md`

# LatticeVale v13.12.2

Runtime hang hardening for repair installs:

- Defers any global WSL networkingMode change/restart until all resumable Linux stack stages have completed successfully.
- Uses bounded `wsl --shutdown`, WSL readiness, and post-restart stack-start checks instead of assuming WSL is ready after a fixed two-second sleep.
- If WSL does not recover after a networking change, exits with preserved data and explicit reboot/resume guidance rather than hanging in later Docker/Ollama work.
- Adds hard outer timeouts around Docker image pulls/builds, Ollama model listing/pulling, and Honcho embedding verification.
- Explicitly unloads the embedding model after its compatibility check to reduce WSL memory pressure.
- Adds APT/curl network retries and timeouts for bootstrap downloads.
- Bounds WSL calls inside the scheduled Windows bridge refresher so a temporarily unhealthy WSL service cannot leave the task stuck indefinitely.
- Bounds the installer metadata write into WSL.
- Guards the long interactive WSL bootstrap with periodic bounded WSL health probes; repeated WSL-service failures terminate the current client cleanly with Resume/repair guidance instead of waiting forever.
- Adds finite timeouts to non-interactive Windows Tailscale inspection/configuration and optional Winget installs while leaving genuine Tailscale login/user-interactive setup un-timed.
- Keeps interactive Hermes provider/profile model wizards user-controlled rather than applying arbitrary short prompt timeouts.

No database, profile, model, vault, Matrix identity, or other persistent user data is intentionally removed by this hotfix.

### Former file: `LatticeVale-Core/HOTFIX-v13.12.3.md`

# LatticeVale v13.12.3

Runtime stability hotfix for low-memory WSL/Ollama installations.

- Replaces the unconditional 65,536-token Ollama context with a conservative context selected from memory visible inside WSL (8K on <10 GiB, 16K on <18 GiB, 32K on <34 GiB, otherwise 64K).
- Migrates the old installer-owned 65,536 default on repair while preserving clearly user-overridden context values.
- Limits Ollama to one resident model and one parallel request, with a 30-second keep-alive.
- Temporarily stops existing Hermes/Honcho model consumers during model validation.
- Restarts Ollama immediately before Honcho embedding validation so only the embedding model is resident.
- Keeps the 4-minute embedding safety timeout and unloads the embedding model afterward.
- Raises the parent WSL heartbeat failure threshold so the embedding operation's own bounded timeout gets a chance to finish before the parent treats heavy model loading as a dead WSL VM.
- Preserves the v13.12.2 Windows-only Tailscale/WSL bridge design and all existing persistent data.

### Former file: `LatticeVale-Core/HOTFIX-v13.12.4.md`

# LatticeVale v13.12.4

Windows Tailscale/WSL bridge reliability hotfix.

- Fixes a repair-path false-success where the Windows bridge helper could exit successfully when `wsl --list --running` did not report the selected distro, leaving `lastWslIp` blank and causing both bridge probes to fail.
- Installer-triggered bridge refresh now explicitly starts/probes the selected WSL distro before discovering its NAT IPv4.
- The installer-owned recurring bridge task uses the same ensure-running behavior because a requested remote Tailscale service requires its WSL backend to be available.
- Bridge refresh is no longer accepted as successful unless a valid non-loopback IPv4 was persisted and every configured Windows loopback bridge port is actually reachable.
- Preserves the v13.12.3 low-memory Ollama policy and all existing stack/data/identity behavior.

### Former file: `LatticeVale-Core/HOTFIX-v13.13.0.md`

# LatticeVale v13.13.0

## Purpose

v13.13.0 converts the final live troubleshooting results from the August 15, 2026 Windows/WSL installation into installer-owned behavior so a clean install does not require the manual repair steps used during diagnosis.

## Live failures reproduced before this release

1. **Tailscale Serve -> WSL returned HTTP 502 through `netsh portproxy`.**
   - Dashboard and Matrix were healthy inside WSL.
   - Windows could reach the WSL NAT IPv4 directly.
   - Windows could reach `127.0.0.1:19119` / `127.0.0.1:18008` through portproxy.
   - Tailscale Serve still returned 502 through those listeners.
   - A native Windows localhost listener on the same host worked through Tailscale Serve.
   - This matches Tailscale's open Windows/WSL localhost-proxy issue #9228.

2. **The Hermes stack was not guaranteed to be running when Windows/Tailscale access was tested.**
   - The Windows logon task existed but had previously reported a nonzero result.
   - Manual testing initially failed until the stack was started.

3. **The installer-created Matrix room triggered Element's room-version warning.**
   - Element reported room version 11 as unstable according to the homeserver capabilities response.
   - Matrix specifies `m.room_versions` as the source clients should use for default/available room-version stability.

4. **The installer-created Matrix room had E2EE disabled.**
   - Element warned that end-to-end encryption was not enabled.
   - Current Hermes supports Matrix E2EE modes and documents a stable `MATRIX_DEVICE_ID` as required for durable encryption identity.

5. **Fresh encrypted Matrix setup has an upstream Hermes edge case when the bot is already joined before a fresh crypto store initializes.**
   - Hermes issue #71067 documents silent inbound-message loss for a fresh E2EE state store when the bot was already joined to the encrypted room.

6. **Optional WinGet applications could be reported PARTIAL even when already installed/current.**
   - Live WinGet inventory is more authoritative than an install command's "no upgrade available" exit/result path.

## v13.13.0 changes

### Windows Tailscale bridge

- Replaces the v13.12 `netsh portproxy` runtime bridge with `windows/LatticeVale-WslNativeRelay.ps1`.
- The helper opens ordinary Windows `127.0.0.1` TCP listeners and forwards them to the current WSL NAT IPv4.
- Dashboard default path:
  - Tailscale HTTPS `9443`
  - Windows native relay `127.0.0.1:19119`
  - current WSL IPv4 `:9119`
- Matrix default path:
  - Tailscale HTTPS `8448`
  - Windows native relay `127.0.0.1:18008`
  - current WSL IPv4 `:8008`
- Relay runs as a long-running per-user/per-distro Scheduled Task with restart-on-failure settings and synchronous listener-bind failure detection.
- Relay starts/recovers the installer-owned Hermes stack when needed, waits for backend readiness, follows WSL IPv4 changes, and persists its last verified target.
- Installer verifies application HTTP through each localhost relay before configuring/adopting Tailscale Serve.
- Installer verifies final Tailscale HTTPS before declaring remote exposure configured.
- v13.12 portproxy handling remains only as ownership-checked migration cleanup.
- Exact compatible existing Tailscale Serve mappings can be adopted instead of being needlessly replaced.
- The exact manual relay task/script used during live troubleshooting is removed only when ownership is proven by its Scheduled Task action.

### Relay lifecycle fixes discovered during v13.13.0 validation

- Scheduled task and installer verification now allow up to 900 seconds for bounded stack recovery/relay readiness, matching the retry envelope of the Linux startup helper.
- Final Tailscale bookkeeping no longer rewrites bridge configuration in a way that stops the just-verified long-running relay.
- Relay helper avoids C# discard syntax that could depend on newer compiler language support under Windows PowerShell 5.1.
- HTTP validation bypasses system HTTP proxies so local/native relay tests are not distorted by proxy configuration.

### Stack startup

- `/usr/local/sbin/hermes-stack-start` performs Docker daemon recovery as root, then runs `docker compose up -d` as the selected Ubuntu user against the installer-owned local Docker socket, retrying up to three bounded attempts.
- The Windows logon task uses `IgnoreNew`, `StartWhenAvailable`, restart-on-failure, battery-safe settings, and a bounded 15-minute execution window; the installer immediately runs and verifies the exact task action before marking auto-start CONFIGURED.
- The post-`.wslconfig` WSL restart path gives the retrying startup helper a 900-second outer bound.

### Matrix / Element

- Pins Synapse to `matrixdotorg/synapse:v1.158.0`, the current stable Synapse release verified during the August 15, 2026 audit, instead of the moving `latest` tag.
- Before room creation, queries `/_matrix/client/v3/capabilities` and inspects `m.room_versions`.
- Uses the server default room version unless the server explicitly marks it unstable; if so, selects the newest numeric room version the server advertises as stable, then persists that stable version as Synapse `default_room_version` for future rooms.
- Creates the Hermes room with explicit `room_version` and encryption state from the first room state:
  - `m.room.encryption`
  - `m.megolm.v1.aes-sha2`
- Sets `MATRIX_E2EE_MODE=required`.
- Sets stable bot device ID `MATRIX_DEVICE_ID=<legacy Matrix bot device ID>`.
- After the pinned Hermes image is pulled and the core container is running, verifies `mautrix` + `olm` imports before the Matrix integration can be considered ready.
- Does not pre-join the bot with a raw Matrix `/join` request.
- Hermes starts with E2EE initialized and auto-joins the pending room invite.
- Reconciliation verifies the bot actually joined the installer-created room, the stable device exists on the homeserver, and the room still advertises `m.megolm.v1.aes-sha2` before Matrix is considered ready.

### Windows applications

- Checks live WinGet inventory before attempting installation.
- If Obsidian or Ubuntu Pro for WSL is already installed, it counts as CONFIGURED.
- Rechecks inventory after a bounded install attempt; install command exit status alone no longer creates a false PARTIAL result.

## Current upstream references checked for v13.13.0

- Tailscale Serve CLI/docs: https://tailscale.com/docs/features/tailscale-serve and https://tailscale.com/docs/reference/tailscale-cli/serve
- Tailscale Windows/WSL Serve 502 issue: https://github.com/tailscale/tailscale/issues/9228
- Microsoft WSL networking/NAT model: https://learn.microsoft.com/windows/wsl/networking
- Matrix Client-Server `m.room_versions` capabilities: https://spec.matrix.org/latest/client-server-api/#mroom_versions-capability
- Matrix room versions: https://spec.matrix.org/latest/rooms/
- Synapse releases: https://github.com/element-hq/synapse/releases
- Hermes Matrix setup/E2EE: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/matrix
- Hermes Matrix environment variables: https://hermes-agent.nousresearch.com/docs/reference/environment-variables
- Hermes E2EE fresh-store issue #71067: https://github.com/NousResearch/hermes-agent/issues/71067

## Validation

The v13.13.0 build passes all 32 deterministic/static fixtures that can be exercised reliably in the Linux build environment, including the new native-relay/Matrix regression fixture. The two end-to-end interruption/resume simulation wrappers are not counted as passes: they reject root execution, and an attempted unprivileged run did not complete within this container's bounded validation window. Their individual checkpoint/recovery invariants are covered by the deterministic recovery/stage-independence fixtures. Real Windows-only APIs (`wsl.exe`, Task Scheduler, WinGet, Tailscale for Windows) remain runtime validation boundaries; the native-relay transport itself was separately proven during the live Windows troubleshooting session that motivated this release.

### Additional consistency fix

- The Hermes-local-Ollama provider verifier now checks the memory-aware context actually persisted in `.env` instead of incorrectly requiring a legacy 64K minimum. This allows the intended 8192-token policy on an approximately 8 GiB WSL VM to verify successfully.

### Former file: `LatticeVale-Core/HOTFIX-v13.13.1.md`

# LatticeVale v13.13.1

## Purpose

v13.13.1 fixes a Windows Tailscale relay-stage stall observed after the Linux stack had already completed successfully and every Windows-local service probe returned OK.

## Root cause

The v13.13.0 native relay helper called `/usr/local/sbin/hermes-stack-start` **before** probing the already-running WSL backends. That recovery helper is intentionally allowed up to 900 seconds. At the same time, the parent installer waited up to 900 seconds for relay readiness without emitting progress. A healthy clean install or repair could therefore appear frozen at `Creating Windows-native WSL relay for Tailscale` even though Hermes, Dashboard, Matrix, SearXNG, and Honcho had just passed their localhost checks.

Repair reruns had a second edge case: a previous long-running relay task could still be stopping while its script/config were replaced, allowing a stale mutex/listener to make the new task exit immediately and the installer wait until timeout.

## Fixes

- Native relay now probes current WSL IPv4/backend reachability first for up to 15 seconds.
- Full Hermes stack recovery is fallback-only and runs only when the direct backend probe fails.
- Installer relay verification is reduced to a bounded 120-second startup window because this stage follows successful local service verification.
- Installer prints a heartbeat every 10 seconds while waiting, including Scheduled Task state.
- If the relay Scheduled Task exits before listeners are ready, the installer fails that optional Tailscale exposure immediately and prints `LastTaskResult` plus the relay log tail instead of silently waiting.
- Repair/resume runs explicitly wait for the previous installer-owned relay task to stop before replacing the relay script/config. If it cannot stop within 15 seconds, repair reports a direct actionable error rather than entering an ambiguous stall.
- Persistent relay recovery behavior remains intact for later Windows logons/WSL restarts: when backends are genuinely unavailable, the relay can still invoke the installer-owned stack startup helper and retry.
- The same code path is used by fresh installs and Resume/repair, so both receive the fix.

## Observed log that motivated the patch

The stall occurred only after:

- stack configuration complete;
- all five Windows localhost service probes returned OK;
- Obsidian was reconciled as already installed;
- Tailscale configuration entered `Creating Windows-native WSL relay for Tailscale`.

The preceding Hermes `SyntaxWarning` about `venv\Scripts` is emitted by upstream Hermes Python code during Kanban initialization and is not the cause of the relay-stage wait.

### Former file: `LatticeVale-Core/HOTFIX-v13.13.2.md`

# LatticeVale v13.13.2

## Problem

v13.13.1 could still finish the entire Linux stack and then fail the persistent Windows-native Tailscale relay with `LastTaskResult=1`. The task's first responsibility was to discover the WSL VM IPv4 itself. Task Scheduler/WSL execution is known to be context-sensitive, and the installer had already proven the Linux services healthy but did not pass their directly reachable WSL address into the relay. Diagnostics could also quote an old `native-relay.log` left by the manual troubleshooting relay.

A relay failure then caused Matrix `public_baseurl` reconciliation to call `docker compose restart synapse` even when the desired localhost URL was already present, producing a second avoidable readiness warning.

## Fix

- Parent installer discovers and verifies the WSL NAT IPv4 before relay task startup.
- The verified IP is seeded into relay configuration and used first.
- Relay IP refresh tries `eth0` plus `hostname -I` and both supported WSL invocation forms.
- Relay task runs as the interactive user without unnecessary elevation.
- Current relay diagnostics use a fresh log; prior log is retained separately.
- Synapse public URL updates are no-op when unchanged; changed URLs receive a 120-second readiness window.

These changes are used by both clean install and Resume/repair.

### Former file: `LatticeVale-Core/HOTFIX-v13.13.3.md`

# LatticeVale v13.13.3

## Relay Scheduled Task execution-context hotfix

A v13.13.2 repair proved the parent installer could resolve and verify the WSL NAT IPv4, but the newly registered relay Scheduled Task exited immediately with `LastTaskResult=1` before the relay emitted its first startup log line. The post-failure cleanup then deleted that exact relay script/config/task, leaving only an older manual relay file in `%LOCALAPPDATA%\LatticeVale` and making later diagnostics inspect the wrong artifact.

v13.13.3 changes the relay launch path to match the Windows configuration that was proven working during live troubleshooting:

- Prefer `pwsh.exe` (PowerShell 7) when installed.
- Fall back to Windows PowerShell 5.1 only if the exact relay script/config passes a bounded `-SelfTest` under that engine.
- Register the persistent relay task for the same interactive Windows identity at `Highest` run level.
- Set the Scheduled Task working directory explicitly.
- Log the selected PowerShell engine and exact relay task name.
- Add a relay `-SelfTest` mode that validates config, listener availability, C# relay compilation, and the seeded/reachable WSL backend without entering the long-running loop.
- Preserve the exact failed relay script/config after unregistering a dead task so a later audit cannot accidentally select a stale manual relay artifact.

The v13.13.2 parent-side WSL-IP seed, bounded relay verification, fresh-log rotation, and idempotent Synapse rollback remain intact. These changes apply to both clean installs and Resume / repair.

### Former file: `LatticeVale-Core/HOTFIX-v13.13.4.md`

# LatticeVale v13.13.4

## Native relay PowerShell parser hotfix

A live v13.13.3 repair run reached the Windows-native relay self-test and both PowerShell 7 and Windows PowerShell 5.1 rejected `LatticeVale-WslNativeRelay.ps1`. The relay contained expandable strings with `$DistroName:`. In PowerShell, a bare variable immediately followed by a colon is parsed as a scoped/provider variable reference unless the variable name is delimited.

v13.13.4 changes those strings to `${DistroName}:`, scans both the parent installer and native relay for the entire unbraced-variable-before-colon bug class, and adds a dedicated regression fixture.

This is a clean-install and Resume/repair fix. The failure occurs at parse time, so starting WSL or Hermes in advance cannot correct it.

### Former file: `LatticeVale-Core/HOTFIX-v13.14.0.md`

# LatticeVale v13.14.0 Hotfix — Clean-Install Lifecycle

## Fixed

- Corrects `/usr/local/sbin/hermes-stack-start` so root invocation always starts the selected user's exact stack directory rather than `/root/hermes-stack`.
- Adds an explicit WSL 2.5.4+ service-instance lifetime option using `[general] instanceIdleTimeout=-1`, preserving and backing up unrelated `.wslconfig` content.
- Validates WSL persistence across a 75-second no-command window after applying the lifetime policy.
- Defaults fresh full-stack Windows-logon auto-start to No.
- Separates relay persistence from stack auto-start: on-demand relay tasks are triggerless/passive; auto-start mode alone receives a logon trigger and WSL/stack recovery permission.
- Makes `./manage.sh start`, `stop`, and `restart` coordinate the Windows relay task when Tailscale exposure is configured.
- Adds clean-install lifecycle regression fixtures, including direct helper generation with `HOME=/root`.

## Unchanged by design

- No Tailscale installation inside WSL.
- No return to `netsh portproxy` as the runtime Tailscale transport.
- Matrix `server_name` remains `hermes.local`.
- Synapse remains pinned to stable `v1.158.0`.
- Hermes Agent is pinned to stable `v2026.8.16` (v0.20.2), released August 16, 2026.
- The installer still requires an existing eligible Ubuntu WSL2 distro and does not create/import/unregister/convert/repair WSL distributions.

### Former file: `LatticeVale-Core/HOTFIX-v13.15.0.md`

# LatticeVale v13.15.0 — Matrix Trust + Tailscale Remote Access

## Fixed / changed

- Keeps startup ownership simple: the user's launcher or `./manage.sh start` starts WSL/Hermes. No fake `sleep infinity`, ping/poll keepalive, or hidden full-stack startup is added.
- Retains the supported Store/MSIX WSL 2.5.4+ `[general] instanceIdleTimeout=-1` service-instance lifetime option as a separate policy from startup.
- Changes the LatticeVale Matrix Tailscale Serve default from HTTPS `8448` to standard HTTPS `443`, producing `https://<node>.<tailnet>.ts.net` for Element/Element X.
- Resume / repair migrates the old installer-owned Matrix default `8448` mapping to `443`; deliberately customized ports are preserved.
- Keeps Matrix private to the Tailscale tailnet. LatticeVale continues to use **Tailscale Serve**, not public Funnel.
- Registers the Windows-native relay at Windows logon whenever Tailscale exposure is configured so the Serve backend listener is present even before WSL starts.
- Keeps that relay strictly passive unless full stack auto-start was explicitly selected: it does not wake/start WSL, does not run the stack-start helper, and does not keep WSL alive.
- Makes the relay use direct TCP checks against its cached WSL target before spawning any WSL discovery command; when the backend is down it waits for the user's launcher.
- Fresh Matrix installs request Hermes's one-time generated recovery key through `MATRIX_RECOVERY_KEY_OUTPUT_FILE`, capture it into the installer's `0600` secret store, persist it as `MATRIX_RECOVERY_KEY`, delete the one-time file, restart Hermes, and verify owner cross-signing.
- Preserves `MATRIX_E2EE_MODE=required`, stable device ID `<legacy Matrix bot device ID>`, encrypted room creation, stable/default room-version negotiation, and `server_name=hermes.local`.
- Repair never deletes the Matrix crypto store just because a legacy recovery key is missing. Pre-v13.15 identities may defer cross-signing repair while Windows/Tailscale reconciliation continues; a retained bot recovery/security key can be supplied on a later Resume / repair.
- `./manage.sh matrix-credentials` can explicitly show the retained bot recovery key when the operator intentionally requests secrets.

## Unchanged by design

- Tailscale remains Windows-native only; nothing Tailscale-related runs inside WSL/Docker.
- Dashboard Tailscale HTTPS default remains `9443`.
- Matrix local Synapse port remains `8008`; Windows relay port remains `18008`.
- Matrix account IDs remain on `hermes.local` even though clients connect through the `*.ts.net` URL.
- Synapse remains pinned to `matrixdotorg/synapse:v1.158.0`.
- Hermes Agent remains pinned to `nousresearch/hermes-agent:v2026.8.16` (v0.20.2).
- The installer still deploys only into an existing eligible Ubuntu WSL2 distro.
- Full stack startup at Windows logon remains optional and defaults to No.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.0.md`

# LatticeVale v13.16.0 — Comprehensive Repair + Aged-Install Maintenance

v13.16.0 is an additive repair-hardening release. It does not remove any v13.15.0
clean-install capability.

## Added to managed Resume / repair

- Audit logical WSL free space, stack footprint, largest persistent paths and Docker
  storage usage.
- Clear disposable APT cache and stale interrupted LatticeVale staging before package work.
- Prune Docker dangling images and only unused build cache older than 30 days.
- Retain the eight newest installer-generated pre-version configuration snapshots.
- Bound installer event-history growth.
- Run bounded normal PostgreSQL `VACUUM (ANALYZE)` for Synapse/Honcho when available.
- Re-run these maintenance actions on every managed repair even when ordinary stage
  checkpoints are already complete.
- Report a hard low-space condition after safe cleanup instead of deleting user data.

## Preventive storage hardening

Every installer-managed Compose service now uses Docker's `local` log driver with
`max-size=20m` and `max-file=5`. Repair snapshots avoid duplicating an already oversized
installer-log directory.

## Explicit preservation boundary

Automatic repair does not delete Hermes profiles/memory/sessions, Matrix/Synapse/Postgres
data, Matrix E2EE/crypto state, Honcho memory, QMD data/source notes, Ollama models,
vault/workspace files, credentials or user-created backups. It does not run `docker
system prune`, `docker image prune -a`, `docker volume prune`, broad container/network
pruning, `VACUUM FULL`, or automatic WSL VHD compaction/sparse conversion.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.1.md`

# LatticeVale v13.16.1 — Profile Gateway Isolation Hardening

v13.16.1 is an additive safety release over v13.16.0. It preserves both clean-install
and Resume / repair workflows and does not change persistent profile, Matrix, database,
model, vault, or workspace data.

## Fix

LatticeVale now explicitly uses the upstream default **one gateway process per profile**
model and prevents accidental activation of `gateway.multiplex_profiles` in installer-managed
profiles. This avoids current upstream multiplexer defects involving per-profile credential
scope, Matrix adapter requirement checks, session/state isolation, port-binding inheritance,
and Docker/s6 gateway reconciliation.

Clean installs and repairs both normalize the default and installer-managed profile configs,
strip the container-level `GATEWAY_MULTIPLEX_PROFILES` opt-in, sanitize newly cloned profiles,
and verify/audit that multiplexing is off. A repair run preserves all profile data and only
normalizes this topology setting.

No fake Matrix credentials or in-place patches to the upstream Hermes Python package are used.
That keeps LatticeVale deterministic and avoids carrying a fragile fork of Hermes internals.

## Validation

- 40/40 deterministic/static Python fixtures pass (the two historical environment-dependent lifecycle simulations remain excluded from the deterministic count).
- Bash syntax passes for bootstrap/configure/manage scripts.
- Python compilation passes for shipped Python helpers/audit code.
- Compose YAML remains valid with the existing 12-service model.
- Existing v13.14 lifecycle, v13.15 Matrix/Tailscale, and v13.16 aged-repair regression suites all remain green.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.2.md`

# LatticeVale v13.16.2 — Bounded Matrix Cross-Signing Hermes Recycle

v13.16.2 fixes an installer hang that could occur in both clean and Resume / repair installs at `Secure and verify Matrix device cross-signing`, where Compose could remain on `Container hermes-agent Restarting`.

## Fix

The Matrix cross-signing stage no longer calls `docker compose restart hermes`. Both recovery-key bootstrap and recovery-key activation now use a bounded LatticeVale-owned Hermes recycle: verify Compose ownership, request a graceful stop with a 10-second Docker stop timeout, force-remove only `hermes-agent` if necessary, start the Hermes service cleanly with Compose, and wait a bounded 60 seconds for the Hermes CLI to become ready. Persistent state remains in the existing bind-mounted `./data/hermes`, `./vault`, and `./workspace` paths and is not deleted.

The stage also prints explicit bounded-wait messages so a normal key-generation or verification wait is not mistaken for a frozen installer.

## Scope

The same `stage_matrix_cross_signing` function is used by clean and repair workflows, so the fix applies to both. No Matrix account, access token, room, E2EE crypto database, profile, session, memory, model, database, vault, or workspace data is reset.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.3.md`

# LatticeVale v13.16.3 — Simplified Matrix Cross-Signing Completion

v13.16.3 simplifies the Matrix cross-signing stage for both Fresh and Resume / repair installs.

The installer no longer treats absence of the exact upstream log message `Matrix: cross-signing verified via recovery key` as a fatal error after Hermes has successfully reloaded the retained recovery key. That log is now a short, bounded advisory check.

A successful stage requires the installer-managed recovery key to be persisted into the Hermes runtime environment, the one-time recovery-key output setting/file to be removed, and the Hermes container to recycle and become command-ready. If the explicit upstream confirmation log is absent or delayed, LatticeVale emits a warning and continues.

This restores the more tolerant behavior of older LatticeVale releases without deleting Matrix crypto state, rotating the Matrix bot identity, or weakening the existing bounded Hermes restart protection added in v13.16.2.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.4.md`

# LatticeVale v13.16.4 hotfix

## Matrix integration-stage false failure

Applies to both **Fresh** and **Resume / repair** installs.

The `apply_matrix_runtime_env` helper previously inherited the exit status of its final optional key check. After v13.16.3 removed the one-time `MATRIX_RECOVERY_KEY_OUTPUT_FILE` setting, a healthy Matrix configuration could therefore make the helper return exit code 1 and abort the `integrations` stage even though nothing was broken. Older Matrix identities without a retained recovery key could hit the same class of false failure.

v13.16.4 makes the helper explicitly return success after copying all present runtime values, excludes the one-time recovery-key output variable from runtime propagation, and leaves required-key enforcement to the existing live integration verifier. Persistent Matrix identity and E2EE state are unchanged.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.5.md`

# LatticeVale v13.16.5 hotfix

This hotfix addresses two related symptoms where Hermes appeared to require an open PowerShell/terminal window to remain available.

1. The long-running Windows-native Tailscale relay scheduled task now starts PowerShell with `-WindowStyle Hidden`. The relay remains a Task Scheduler-managed background process with no user-facing console to close.
2. If Tailscale Dashboard or Matrix exposure is selected, LatticeVale reconciles old saved installs to WSL's supported `[general] instanceIdleTimeout=-1` policy so the Ubuntu service instance remains running after the launching terminal exits.

The patch does not add a fake keepalive loop or `sleep infinity`, and it does not change persistent Hermes/Matrix data.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.6.md`

# LatticeVale v13.16.6 hotfix

This release folds the remaining post-v13.16.5 operational fixes into both Fresh and Resume / repair.

## Obsidian / QMD

- Windows Obsidian uses a Windows-native vault instead of the WSL UNC stack path.
- If Obsidian has exactly one registered local vault, repair reuses it. Otherwise the default is the current Windows Documents known folder plus `Obsidian Vault`, so redirected Documents folders are respected.
- LatticeVale translates the Windows vault with `wslpath` and mounts it directly into Hermes/QMD as `/vault` through Compose.
- Legacy `~/hermes-stack/vault` files are copied non-destructively into the Windows vault during repair; existing Windows files are never overwritten and the legacy source is preserved.
- Repair detaches only an old host-level mount at the exact `~/hermes-stack/vault` target and backs up `/etc/fstab` before removing matching `bind` entries, so earlier manual bind-mount guidance cannot conflict with the direct Compose mount.
- QMD built-in indexing now defaults to every 2 hours (7200 seconds), replacing the old 6-hour default.
- The exact legacy `HERMES_QMD_REINDEX` cron entry previously recommended during troubleshooting is removed to prevent duplicate indexing.

## Matrix / Element approvals

- Matrix-enabled installs explicitly set `MATRIX_REACTIONS=true`.
- Approval/model-picker reactions are restricted to the original requester with `MATRIX_APPROVAL_REQUIRE_SENDER=true`.
- Repair reconciles both settings into the existing default profile without rebuilding Matrix identity.

## Kanban / multi-agent

- Kanban configures gateway dispatch, automatic decomposition, creator-session wakeups, and a narrowly managed SOUL policy block so substantive direct-user requests can delegate without special trigger prefixes while simple requests remain direct.
- Default concurrency is 2 workers globally and 1 per profile to reduce provider-rate-limit bursts while still allowing two-profile parallelism.
- Clean/reconfigure can choose different caps; Resume / repair reuses saved caps or migrates older installs to the 2/1 defaults.
- Automatic decomposition is limited to one triage task per tick; dispatcher interval is 30 seconds.

## Preserved earlier fixes

v13.16.1-v13.16.5 behavior remains: standalone per-profile gateways, bounded Matrix recycle, advisory cross-signing confirmation, safe optional recovery-key handling, hidden Windows relay, and supported WSL instance lifetime policy.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.7.md`

# v13.16.7 hotfix — repair semantics hardening

## Root cause

In v13.16.6 and earlier, `configure-stack.sh` included `installerVersion` in `OPTIONS_HASH`. Every newer LatticeVale ZIP therefore made all otherwise-complete stage checkpoints non-current. `run_stage` then replayed stage actions, including infrastructure pulls/builds and provider setup work. This made **Resume / repair** resemble a clean/reinstall or broad update pass.

A separate checkpoint interaction meant **Reconfigure providers/profiles** could be skipped on the same bundle version: its force flags were intentionally omitted from the stable options hash, but `run_stage` did not give those flags precedence over a healthy checkpoint.

Finally, a recognized managed stack could have a missing/unreadable `install-options.json`; the previous front end could continue into fresh-style option selection because parsed prior choices were unavailable.

## Fix

- Remove release-only/transient fields, including `installerVersion`, from checkpoint identity.
- Add explicit per-stage migration revisions. A future release increments only the stage whose behavior requires forced reconciliation.
- During Resume/Reconfigure, allow pre-v13.16.7 completed checkpoints to migrate only when the corresponding live verifier succeeds.
- Give explicit provider/profile/Matrix rebuild flags precedence over checkpoint skipping.
- Recover missing/unreadable managed install options from the newest valid installer-created pre-repair snapshot; fail closed if recovery is impossible.
- Keep `./manage.sh update` as the explicit broad upstream/component upgrade path.

## Data safety

No persistent Hermes, profile, Matrix, PostgreSQL, QMD, Ollama, Honcho, vault, workspace, session, memory, credential, or crypto data is intentionally deleted by this patch. Existing repair-maintenance safeguards remain unchanged.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.8.md`

# v13.16.8 hotfix

Repair metadata recovery now searches both LatticeVale pre-repair `installer-config.tar.gz` snapshots and ordinary `./manage.sh backup` `files.tar.gz` archives. A managed stack is also recognized from either backup type when the current `install-options.json` and state marker are unavailable. Recovered JSON must be a top-level object. If no valid persisted options exist, LatticeVale still fails closed rather than asking clean-install component questions.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.9.md`

# LatticeVale v13.16.9 hotfix

## Fixed

- Successful `wsl.exe` probes now expose stdout separately from stderr and feed only stdout to machine-readable callers.
- WSL startup diagnostics such as `/etc/fstab` mount warnings can no longer corrupt valid `install-options.json` or backup JSON reads.
- Failure paths still retain combined stdout/stderr for useful diagnostics.
- Existing legacy Obsidian `/etc/fstab` cleanup is now reachable even when the legacy entry itself produces a WSL startup warning.

## Why this mattered

In v13.16.8, `Invoke-NativeProcessCapture` merged stdout and stderr into one `Text` value. A successful `cat ~/hermes-stack/install-options.json` could therefore return valid JSON plus a WSL startup warning. `ConvertFrom-Json` then rejected the combined text, causing Resume / repair to falsely report that both the current options file and backup snapshots were unreadable.

### Former file: `LatticeVale-Core/HOTFIX-v13.16.10.md`

# LatticeVale v13.16.10 hotfix

Fixes Resume / repair when a legacy Obsidian bind mount causes `wslpath` to return the bind target instead of the underlying `/mnt/<drive>/...` source path. The converter now translates the Windows drive root only and appends the normalized relative path lexically, preserving validation while avoiding bind-mount canonicalization. The existing repair step then removes the obsolete LatticeVale `/etc/fstab` bind entry without deleting vault data.

### Former file: `LatticeVale-Core/AUDIT-v13.16.11.md`

# LatticeVale v13.16.11 repair reliability audit

Scope: Windows host installer, WSL command boundary, Linux bootstrap, Compose configuration, repair checkpoints, state audit/manage CLI, Obsidian migration, Windows Tailscale relay, backup/retention, permissions, package/image refresh, and destructive maintenance.

## Defects corrected

- **Pre-initialization crash:** `Repair-LegacyObsidianStackVaultMount` was called before `$stackLinuxPath` was assigned, reducing the target to `/vault`. Stack-path derivation now happens immediately after the selected Linux home is resolved, with an explicit absolute-path guard.
- **Duplicate WSL side effects:** the host installer and relay retried every failed Linux command using legacy WSL syntax. They now fall back only when `wsl.exe` itself explicitly rejects the `--` separator. Successful probes parse stdout only while preserving stderr diagnostics.
- **Stopped != broken:** the auditor/manage CLI distinguish intentionally stopped `restart: unless-stopped` containers (including normal 0/137/143 stop exit codes) from startup and runtime failure.
- **Repair != update:** repair first starts selected infrastructure from existing local images using `docker compose up --pull never --no-build`; only a genuinely unrecoverable/missing component enters targeted pull/build repair. Provider reconfiguration reuses an existing Hermes image rather than pulling it again.
- **APT/package churn:** a managed repair skips prerequisite APT work when requirements are already installed and installs only missing official Docker packages instead of upgrading the complete Docker package set.
- **Obsidian repair safety:** Windows vault paths are derived lexically from the WSL drive root to avoid bind-mount canonicalization; legacy `/etc/fstab` removal requires both the expected `/mnt/<drive>/...` source and managed stack-vault destination. Windows-vault data is never recursively chowned/chmodded by bootstrap repair.
- **Filesystem traversal hardening:** the stack root, backups, and managed config/data trees reject unsafe symlink/external-mount layouts before recursive repair or backup writes.
- **Backup retention bug:** current pre-repair snapshot names are `pre-<version>-<timestamp>`; retention previously searched only `pre-v*`. It now matches the actual name shape **and requires a real, non-symlinked `installer-config.tar.gz` marker** before an old directory can be pruned, preserving similarly named user folders.
- **Backup privacy:** `manage.sh backup` creates each backup directory as mode 0700 before dumps/archive files are written.
- **Stage-migration integrity:** per-stage revision bumps now bypass local-health recovery shortcuts. A future targeted migration cannot be silently marked complete merely because the pre-migration container is still healthy.

## Deliberately unchanged

- No `docker system prune`, volume prune, all-unused-image prune, or `VACUUM FULL` is used by Resume / repair.
- Persistent Hermes, Matrix/PostgreSQL, Honcho/PostgreSQL, Ollama model, QMD source-vault, workspace, and user backup data are not deleted by normal repair.
- `./manage.sh update` remains the explicit broad dependency refresh path.
- Windows Tailscale relay remains passive when auto-start is disabled: it checks `wsl --list --running` before any in-distro probe and does not intentionally wake a stopped distro.

### Former file: `LatticeVale-Core/AUDIT-v14.1.2.md`

# LatticeVale v14.1.2 audit

## Scope

v14.1.2 preserves the confirmed-working v13.16.11 clean/repair baseline and v14.0 profile/Matrix model while adding the LatticeVale rebrand, custom-WSL-automount-root-safe Obsidian path handling, fuller Tailscale Serve state inspection, and exact source-manifest coverage enforcement.

## Safety invariants

- Fresh and Resume / repair remain separate behaviors; repair is not an implicit broad update.
- Existing profiles, memories, sessions, models, databases, Docker volumes, Matrix rooms/messages/E2EE state, credentials, and Windows vault files are preservation-first.
- Secondary Matrix is opt-in per named profile. The Matrix localpart follows the exact installer-selected profile name; nothing is hard-coded to `assistant`.
- Matrix provisioning occurs only after that exact profile has a configured model, whether it cloned the default model/provider or completed independent model selection.
- Each Matrix-enabled profile receives its own Matrix identity, token, device/recovery state, room allowlist, and independently supervised Docker/s6 profile gateway. `gateway.multiplex_profiles` remains disabled.
- Unknown/manual profile Matrix configuration is never silently overwritten. Existing unowned Matrix users are not password-reset or adopted automatically.
- The human Matrix admin password is not stored long-term. A 0600 one-time handoff may exist only between default Matrix bootstrap and profile provisioning in the same interrupted/resumed installation, and the profile stage removes it on exit.
- Synapse public registration remains disabled. LatticeVale removes only a registration secret it can prove it created; administrator-managed registration settings are preserved.
- Shell cleanup for profile Matrix provisioning is scoped to a subshell, and Matrix room IDs are treated as data rather than emitted as unquoted shell source.
- The Windows Obsidian vault remains a Windows-local drive path. The drive root is translated through WSL rather than assuming `/mnt`, the relative path is appended lexically, and `findmnt` must identify the final path as Windows-backed storage.
- No compiled installer executable or opaque payload is required. Release scripts are plain text and reviewable before execution.
- Direct Tailscale installer fallback is downloaded only from the official package host, must pass Authenticode validation with a Tailscale-identifiable signer before execution, and is deleted afterward.
- An empty selected-infrastructure list is explicitly successful under Bash ERR tracing; no-optional-service installs cannot be falsely marked broken by a helper's final false conditional.
- `manage.sh start`, full restart, and explicit update reconcile only profile gateways whose profile objects have `matrix.enabled=true`; this makes the optional Windows Start shortcut restore the exact selected interactive profile topology while leaving Kanban-only workers stopped.
- GitHub source validation excludes its own scanner definition from opaque-command matching, and `.gitattributes` fixes release-manifest line endings across Windows/Linux checkouts.
- Tailscale Serve reconciliation inspects both `serve status --json` and `serve get-config --all`; clients that lack the newer full-config command fall back without making an unverified destructive change.
- Release verification requires exact manifest coverage, rejecting duplicate entries, missing files, unexpected files, and hash mismatches.
- New Windows task/shortcut/relay artifacts use LatticeVale-neutral names and paths; legacy identifiers are recognized only for ownership-proven migration of existing installs.
- A selected global `.wslconfig` change detects other running WSL distros and requires explicit confirmation before writing the change that will require global `wsl --shutdown`.

## Validation target

Release validation includes the retained deterministic fixture set plus v14.1.2 fixtures (currently 53 `*-fixtures.py` scripts), Bash syntax, Python compilation, Compose YAML parsing, static audit, source-manifest verification, Windows PowerShell 5.1 + PowerShell 7 parse validation in GitHub Actions, packaged-copy regression, and ZIP integrity. Real Windows Task Scheduler + WSL + Windows Tailscale + live Synapse/Hermes lifecycle behavior still requires a real Windows/WSL integration run and is not claimed by container-only/static testing.

## Windows desktop shortcut invariants

- Shortcut creation is optional and saved as `windowsShortcuts`. Legacy Resume defaults it to false when no explicit choice exists.
- Shortcut identity derives from the current Windows account + selected WSL distro + Linux user + managed stack path; launcher source contains no hard-coded local account/distro names.
- Start uses the installer-owned root startup helper and then `manage.sh start`, preserving selected service/profile behavior.
- Shutdown checks the selected distro is running, invokes `manage.sh stop`, then terminates only that distro; global `wsl --shutdown` is forbidden in the launcher.
- Same-name unowned `.lnk` files are preserved. Removal requires proof that target/arguments reference the LatticeVale helper and exact config.
- Launcher source is plain text and included in PowerShell parser/static regression coverage.

## Release audit results for the packaged v14.1.2 source tree

The release-candidate source tree was frozen and then validated again from a fresh extraction of the generated ZIP.

Executed successfully in the available Linux/container audit environment:

- 53 / 53 deterministic `tests/*-fixtures.py` scripts passed.
- `tests/static-audit.py` passed and retained the v13 existing-WSL/recovery invariants.
- v14.1.2 profile/Matrix/model/Obsidian fixtures passed.
- v14.1.2 optional Windows Start / Shut Down shortcut fixtures passed.
- v14.1.2 public-release/source-policy fixtures passed.
- Bash syntax checks passed for `linux/bootstrap.sh`, `stack/configure-stack.sh`, `stack/manage.sh`, and `stack/qmd-index-cycle.sh`.
- Python compilation passed for `stack/` and `tests/`.
- `stack/compose.yaml` parsed successfully with the expected 12 services.
- The release tree contained no bundled EXE/MSI/DLL/shared-object/package/archive/container-image/bytecode payloads covered by the public-release scan.
- `SOURCE-SHA256SUMS.txt` covered and verified every release file other than the manifest itself.
- ZIP structural integrity passed.
- The freshly extracted ZIP repeated the source-manifest, source-only, static, v14 targeted, Compose, Bash, Python, and 53-fixture checks successfully.

Additional completed lifecycle validation:

- `minimal-resume-simulation.py`: PASS.
- `interruption-resume-simulation.py`: PASS.

Not claimed as completed in this container-only audit:

- A local real Windows PowerShell 5.1 / PowerShell 7 parser run in this container. The included GitHub Actions Windows job performs both real Windows PowerShell 5.1 and PowerShell 7 AST parsing.
- A live Windows + Store/MSIX WSL2 + Ubuntu + Docker + Windows Tailscale + Element end-to-end installation/repair run.
- Actual Windows `.lnk` creation or Authenticode verification against a freshly downloaded Tailscale installer, because those require Windows.

The v13.16.11 baseline had already been exercised successfully on a real target system before the v14 changes. v14.1.2 intentionally retains those established clean/repair behaviors while adding opt-in features and additional verification. The public GitHub CI and a real Windows/WSL release smoke test remain the final platform-specific validation gates before describing a GitHub release as fully integration-tested.

### Former file: `LatticeVale-Core/AUDIT-v14.1.3.md`

# LatticeVale v14.1.3 audit

## Scope

v14.1.3 preserves the confirmed-working v13.16.11 clean/repair baseline and the v14 profile/Matrix model, incorporates the v14.1.1/14.1.2 portability fixes, and adds deterministic LF source checkout rules so exact-byte release-manifest verification remains valid across Windows and Linux Git checkouts.

## Safety invariants

- Fresh and Resume / repair remain separate behaviors; repair is not an implicit broad update.
- Existing profiles, memories, sessions, models, databases, Docker volumes, Matrix rooms/messages/E2EE state, credentials, and Windows vault files are preservation-first.
- Secondary Matrix is opt-in per named profile. The Matrix localpart follows the exact installer-selected profile name; nothing is hard-coded to `assistant`.
- Matrix provisioning occurs only after that exact profile has a configured model, whether it cloned the default model/provider or completed independent model selection.
- Each Matrix-enabled profile receives its own Matrix identity, token, device/recovery state, room allowlist, and independently supervised Docker/s6 profile gateway. `gateway.multiplex_profiles` remains disabled.
- Unknown/manual profile Matrix configuration is never silently overwritten. Existing unowned Matrix users are not password-reset or adopted automatically.
- The human Matrix admin password is not stored long-term. A 0600 one-time handoff may exist only between default Matrix bootstrap and profile provisioning in the same interrupted/resumed installation, and the profile stage removes it on exit.
- Synapse public registration remains disabled. LatticeVale removes only a registration secret it can prove it created; administrator-managed registration settings are preserved.
- Shell cleanup for profile Matrix provisioning is scoped to a subshell, and Matrix room IDs are treated as data rather than emitted as unquoted shell source.
- The Windows Obsidian vault remains a Windows-local drive path. The drive root is translated through WSL rather than assuming `/mnt`, the relative path is appended lexically, and `findmnt` must identify the final path as Windows-backed storage.
- No compiled installer executable or opaque payload is required. Release scripts are plain text and reviewable before execution.
- Direct Tailscale installer fallback is downloaded only from the official package host, must pass Authenticode validation with a Tailscale-identifiable signer before execution, and is deleted afterward.
- An empty selected-infrastructure list is explicitly successful under Bash ERR tracing; no-optional-service installs cannot be falsely marked broken by a helper's final false conditional.
- `manage.sh start`, full restart, and explicit update reconcile only profile gateways whose profile objects have `matrix.enabled=true`; this makes the optional Windows Start shortcut restore the exact selected interactive profile topology while leaving Kanban-only workers stopped.
- GitHub source validation excludes its own scanner definition from opaque-command matching, and `.gitattributes` fixes release-manifest line endings across Windows/Linux checkouts.
- Tailscale Serve reconciliation inspects both `serve status --json` and `serve get-config --all`; clients that lack the newer full-config command fall back without making an unverified destructive change.
- Release verification requires exact manifest coverage, rejecting duplicate entries, missing files, unexpected files, and hash mismatches.
- Git checkout rules force LF for all hashed text/source types; no release source type may force CRLF because `SOURCE-SHA256SUMS.txt` authenticates exact file bytes.
- The shipped reviewable source tree is byte-checked for CRLF before release; `.gitattributes` and the physical release bytes therefore agree before the exact-byte manifest is generated.
- New Windows task/shortcut/relay artifacts use LatticeVale-neutral names and paths; legacy identifiers are recognized only for ownership-proven migration of existing installs.
- Project-level installer/runtime messages identify the toolkit as LatticeVale; names such as Hermes Agent/API/profile remain only when they technically identify the upstream component being configured or inspected.
- Project-owned generated labels use LatticeVale; the SearXNG title migration changes only the exact former installer default and preserves administrator-customized instance names.
- A selected global `.wslconfig` change detects other running WSL distros and requires explicit confirmation before writing the change that will require global `wsl --shutdown`.

## Validation target

Release validation includes the retained deterministic fixture set plus v14.1.3 fixtures (currently 53 `*-fixtures.py` scripts), Bash syntax, Python compilation, Compose YAML parsing, static audit, source-manifest verification, Windows PowerShell 5.1 + PowerShell 7 parse validation in GitHub Actions, packaged-copy regression, and ZIP integrity. Real Windows Task Scheduler + WSL + Windows Tailscale + live Synapse/Hermes lifecycle behavior still requires a real Windows/WSL integration run and is not claimed by container-only/static testing.

## Windows desktop shortcut invariants

- Shortcut creation is optional and saved as `windowsShortcuts`. Legacy Resume defaults it to false when no explicit choice exists.
- Shortcut identity derives from the current Windows account + selected WSL distro + Linux user + managed stack path; launcher source contains no hard-coded local account/distro names.
- Start uses the installer-owned root startup helper and then `manage.sh start`, preserving selected service/profile behavior.
- Shutdown checks the selected distro is running, invokes `manage.sh stop`, then terminates only that distro; global `wsl --shutdown` is forbidden in the launcher.
- Same-name unowned `.lnk` files are preserved. Removal requires proof that target/arguments reference the LatticeVale helper and exact config.
- Launcher source is plain text and included in PowerShell parser/static regression coverage.

## Release audit results for the packaged v14.1.3 source tree

The release-candidate source tree was frozen and then validated again from a fresh extraction of the generated ZIP.

Executed successfully in the available Linux/container audit environment:

- 53 / 53 deterministic `tests/*-fixtures.py` scripts passed.
- `tests/static-audit.py` passed and retained the v13 existing-WSL/recovery invariants.
- v14.1.3 profile/Matrix/model/Obsidian fixtures passed.
- v14.1.3 optional Windows Start / Shut Down shortcut fixtures passed.
- v14.1.3 public-release/source-policy fixtures passed.
- Bash syntax checks passed for `linux/bootstrap.sh`, `stack/configure-stack.sh`, `stack/manage.sh`, and `stack/qmd-index-cycle.sh`.
- Python compilation passed for `stack/` and `tests/`.
- `stack/compose.yaml` parsed successfully with the expected 12 services.
- The release tree contained no bundled EXE/MSI/DLL/shared-object/package/archive/container-image/bytecode payloads covered by the public-release scan.
- `SOURCE-SHA256SUMS.txt` covered and verified every release file other than the manifest itself.
- ZIP structural integrity passed.
- The freshly extracted ZIP repeated the source-manifest, source-only, static, v14 targeted, Compose, Bash, Python, and 53-fixture checks successfully.

Additional completed lifecycle validation:

- `minimal-resume-simulation.py`: PASS.
- `interruption-resume-simulation.py`: PASS.

Not claimed as completed in this container-only audit:

- A local real Windows PowerShell 5.1 / PowerShell 7 parser run in this container. The included GitHub Actions Windows job performs both real Windows PowerShell 5.1 and PowerShell 7 AST parsing.
- A live Windows + Store/MSIX WSL2 + Ubuntu + Docker + Windows Tailscale + Element end-to-end installation/repair run.
- Actual Windows `.lnk` creation or Authenticode verification against a freshly downloaded Tailscale installer, because those require Windows.

The v13.16.11 baseline had already been exercised successfully on a real target system before the v14 changes. v14.1.3 intentionally retains those established clean/repair behaviors while adding opt-in features and additional verification. The public GitHub CI and a real Windows/WSL release smoke test remain the final platform-specific validation gates before describing a GitHub release as fully integration-tested.

### Former file: `LatticeVale-Core/AUDIT-v14.2.0.md`

# LatticeVale v14.2.0 audit notes

This release hardens local-AI execution and release reproducibility without changing the preservation-first clean/repair architecture.

## Changes under audit

- GPU policy is explicit and persisted. `auto` verifies supported runtime/device prerequisites and can fall back to CPU; forced NVIDIA/AMD modes fail closed if their prerequisites are absent.
- NVIDIA Container Toolkit setup pins `nvidia-container-toolkit=1.20.0-1` from NVIDIA's official repository and backs up pre-existing Docker daemon/repository configuration before `nvidia-ctk` changes Docker runtime configuration. No Linux NVIDIA display driver is installed.
- AMD/ROCm requires `/dev/kfd` and `/dev/dri`; numeric access groups are derived from the actual device nodes and added to the Ollama container, and the pinned ROCm Ollama image is used only after those checks.
- Adaptive container ceilings are enabled by default only when selected on new/reconfigured installs. Pre-v14.2 repair state defaults to unrestricted to avoid unexpectedly constraining a working installation. User `compose.override.yaml` is merged last. These are per-container ceilings; WSL-wide CPU/RAM policy remains separate.
- Fresh-install defaults are pinned to `ollama/ollama:0.32.14`, `ollama/ollama:0.32.14-rocm` for AMD, and `searxng/searxng:2026.8.17-374939b88`; explicit `.env` overrides remain supported. Legacy repair preserves an existing explicit image tag rather than silently turning repair into an update, and warns when that preserved tag is floating.
- Release manifest path/hash/exact-coverage logic is centralized in one inspectable PowerShell module shared by launcher and verifier. CI parses that shared module under both Windows PowerShell 5.1 and PowerShell 7.
- Honcho AGPL-3.0 network-use considerations are called out in third-party notices.

## Preservation rules

No normal repair deletes profiles, memories, sessions, Matrix identities/E2EE state, databases, Ollama models, QMD data, Obsidian vault files, credentials, Docker volumes, or user-created backups. Existing manual `compose.override.yaml` remains user-owned.

### Former file: `LatticeVale-Core/AUDIT-v14.2.1.md`

# LatticeVale v14.2.1 audit notes

This maintenance release follows the v14.2.0 GPU/resource/reproducibility hardening with two repair-safety corrections discovered during the final audit.

## Corrections

- Root bootstrap no longer infers `repairMaintenance`, `obsidian`, local-AI selection, or acceleration policy by regex matching raw JSON. Existing managed filesystem state selects repair-safe package behavior before Python is guaranteed; once Python is available, root-affecting options are parsed structurally and type-checked before GPU/runtime actions.
- NVIDIA Container Toolkit installation pins all four packages from the 1.20.0 unified release (`nvidia-container-toolkit`, `nvidia-container-toolkit-base`, `libnvidia-container-tools`, `libnvidia-container1`) to `1.20.0-1`.
- Installer-owned Ollama image selection is tracked with `LATTICEVALE_OLLAMA_IMAGE_AUTO`. Repair preserves a deliberate custom `OLLAMA_IMAGE` when acceleration policy is unchanged; changing acceleration explicitly may switch the installer-managed standard/ROCm image.
- Runtime audit distinguishes a preserved custom Ollama image override from a broken installer-managed AMD image. Service health remains authoritative for whether a custom image actually works.
- The shared release-manifest verifier preserves filesystem-root semantics (for example `C:\\` instead of drive-relative `C:`) while retaining traversal, case-collision, reserved-name, reparse-point, and exact-coverage checks.
- The v14.2.1 hardening fixture executes the Ollama image-ownership branch to prove that same-policy custom overrides survive and an explicit installer-managed acceleration change can select the ROCm image.

## Preservation rules

No normal repair deletes profiles, memories, sessions, Matrix identities/E2EE state, databases, Ollama models, QMD data, Obsidian vault files, credentials, Docker volumes, or user-created backups. Existing manual `compose.override.yaml` remains user-owned and is merged last.

### Former file: `LatticeVale-Core/AUDIT-v14.3.0.md`

# LatticeVale v14.3.0 Audit Notes

## Scope

v14.3.0 is a conservative usability/safety release on top of v14.2.1. It does not replace the existing clean-install or preservation-first Resume/repair architecture. The new behavior is limited to questionnaire UX, NVIDIA toolkit version handling, offline pin visibility, advisory GPU/VRAM diagnostics, and backup-sensitivity messaging.

## Safety invariants

- A complete installed NVIDIA Container Toolkit newer than LatticeVale's tested `1.20.0-1` package set is preserved; v14.3.0 does not automatically downgrade it.
- If NVIDIA toolkit packages are in a mixed state where at least one component is newer than the tested pin while another is missing/older, GPU setup fails closed with guidance rather than forcing a downgrade or silently mixing package versions.
- The tested NVIDIA package set is installed only when all installed components are at or below the tested pin; no `--allow-downgrades` permission is used.
- Fresh installs offer Quick or Custom questionnaire modes, but both serialize the same schema-16 `install-options.json` structure. Resume/repair continues to reuse persisted intent instead of changing component choices silently.
- Quick setup does not enable Matrix, Tailscale exposure, extra profiles, Honcho/QMD/Obsidian, Windows auto-start, desktop shortcuts, or global WSL lifetime changes without explicit later reconfiguration. It enables the Dashboard, SearXNG, adaptive resource ceilings, unattended security updates, and asks only the core local-vs-upstream Hermes provider choice.
- Image-pin age output is calculated entirely offline from the LatticeVale pin date. It is informational only and never claims that a newer upstream release exists.
- VRAM-fit output is advisory only. Model artifact size is not treated as a complete memory requirement because quantization, context length, KV cache, multi-GPU behavior, and partial CPU/GPU offload affect real memory use.
- When the selected model is actually loaded, `manage.sh status` surfaces the `ollama ps` runtime line so CPU/GPU offload evidence is distinguished from pre-load estimates.
- `manage.sh backup` keeps the existing backup implementation and permissions; v14.3.0 adds only a reminder that backup archives can contain secrets and should be encrypted/protected when copied elsewhere. No new encryption format, key store, dependency, or password-handling path is introduced.
- Existing v14.2 image pins, adaptive resource policy, profile-specific Matrix behavior, Obsidian path safety, Tailscale/relay architecture, source-only release policy, and preservation-first repair behavior remain in force.

## Prerequisite/test-environment note

`jq` remains a real Ubuntu prerequisite installed by `linux/bootstrap.sh`. An offline test sandbox that omits `jq` can use a fixture-local shim for simulation only; production logic is not weakened or duplicated merely to accommodate such a sandbox.

## Validation targets

Release validation must retain all historical deterministic fixtures and add v14.3 coverage for:

- schema 16 and Quick/Custom questionnaire source invariants;
- no automatic NVIDIA downgrade permission;
- complete-newer/mixed-newer toolkit handling strings and package comparison logic;
- offline image-pin date/age visibility;
- NVIDIA/AMD VRAM probes and soft warning wording;
- `ollama ps` loaded-model evidence;
- backup sensitivity/encryption reminder;
- final hardware/resource summary output.

The two interruption/resume simulations remain required after deterministic fixtures pass. The final ZIP must be extracted and the deterministic/lifecycle audit repeated against the packaged copy.

### Former file: `LatticeVale-Core/AUDIT-v14.3.1.md`

# LatticeVale v14.3.1 Audit Notes

## Scope

v14.3.1 is a narrow Windows PowerShell startup compatibility hotfix on top of v14.3.0. The `installer/install.ps1` dot-sources `tools/ReleaseManifest.ps1`. That verifier previously enabled StrictMode 2.0 at dot-source scope, so the setting leaked into the caller and its child installer. The first resulting failure was a read of the lazy script-scoped `HermesCompatibility` cache before the variable had been created, which causes Windows PowerShell 5.1 to throw during preflight.

## Fix

`tools/ReleaseManifest.ps1` now enables StrictMode 2.0 inside each verifier function rather than at dot-source scope, preserving strict verifier execution without changing the caller's mode. `Install-LatticeVale.ps1` also initializes `$script:HermesCompatibility = $null` during script startup, before any preflight code can read it. `Get-LatticeValeCompatibility` retains the same lazy-load/cache behavior after initialization.

## Safety invariants

- No installation option, saved-state schema, WSL policy, Docker configuration, service topology, credential handling, repair behavior, or update behavior changed.
- Source verification still runs before the core installer. StrictMode remains enabled while verifier functions execute, but it no longer leaks into the caller. The defensive cache initialization also keeps the core installer safe if a different caller deliberately invokes it under StrictMode.
- The v14.3.0 safety/usability invariants remain applicable.

## Regression target

Release validation must assert that verifier StrictMode is function-scoped rather than dot-source-scoped and that the script-scoped compatibility cache is initialized before `Get-LatticeValeCompatibility` can read it, while retaining all historical deterministic fixtures and PowerShell 5.1/7 parser checks.

### Former file: `LatticeVale-Core/AUDIT-v14.3.2.md`

# LatticeVale v14.3.2 Audit Notes

## Scope

v14.3.2 is a narrow Windows native-process compatibility hotfix on top of v14.3.1. A real install launched with Windows PowerShell 5.1 reached WSL preflight, `wsl --list --quiet` produced the valid distro name `Ubuntu-24.04`, but the bounded process helper still returned `Success = $false`. The helper used `Start-Process -PassThru -NoNewWindow` and evaluated the returned process object's `ExitCode`. PowerShell has documented `Start-Process -PassThru`/`-NoNewWindow` cases where `ExitCode` is unavailable/null on the returned wrapper; PowerShell 7.5 specifically included an upstream fix for that class of behavior.

## Fix

Exit-code-sensitive native process paths now create `System.Diagnostics.ProcessStartInfo` and `System.Diagnostics.Process` directly. This gives LatticeVale ownership of the process object/native handle rather than relying on a `Start-Process` wrapper. The change covers:

- `Invoke-NativeProcessCapture`
- `Invoke-NativeProcessPassthrough`
- the guarded interactive WSL installer process
- `windows/LatticeVale-WslNativeRelay.ps1` bounded WSL calls

The capture/relay paths start asynchronous reads for stdout and stderr before waiting for process completion, preserving bounded timeouts while avoiding pipe-buffer deadlocks. `Invoke-NativeProcessCapture` still supports exact file-byte stdin staging through `StandardInput.BaseStream` for WSL `dd` operations. Existing output normalization, separated stdout/stderr, timeout semantics, and nonzero-exit failure behavior are retained.

## Compatibility rationale

The implementation uses APIs available to Windows PowerShell 5.1's .NET Framework runtime (`System.Diagnostics.Process`, `ProcessStartInfo`, `WaitForExit`, redirected standard streams, and `ReadToEndAsync`) and APIs also supported by PowerShell 7. No PowerShell-7-only syntax was introduced. The existing Windows argument-quoting helper remains in use, so argv construction is unchanged.

Microsoft documentation states that `Process.ExitCode` is valid after the directly associated process exits, and its standard-stream documentation warns that redirected stdout/stderr must be drained in a way that avoids mutual pipe-buffer deadlock. PowerShell's own 7.5 release notes document a fix to `Start-Process -PassThru` ensuring `ExitCode` is accessible for the returned Process object; v14.3.2 avoids depending on that host/cmdlet behavior entirely.

## Safety invariants

- No WSL installation/import/unregister/convert/repair behavior was added.
- A genuine WSL timeout or nonzero exit still fails closed during preflight.
- No questionnaire, saved-state schema, Docker configuration, service topology, port, credential, Matrix, Tailscale, Ollama, Obsidian, backup, repair, or update policy changed.
- v14.3.1 StrictMode/cache startup hardening remains unchanged.
- v14.3.0 safety/usability invariants remain applicable.

## Regression target

Release validation must ensure no exit-code-sensitive installer/relay path reintroduces `Start-Process -PassThru`; bounded native-process paths must use directly owned `System.Diagnostics.Process` objects, preserve timeout handling, and concurrently drain redirected stdout/stderr. Historical deterministic fixtures and PowerShell 5.1/7 parser checks remain required.

### Former file: `LatticeVale-Core/AUDIT-v14.3.3.md`

# LatticeVale v14.3.3 Audit Notes

v14.3.3 fixes questionnaire ordering for secondary-profile Matrix rooms. On a fresh install, Matrix/Synapse has not been provisioned yet, so no local Matrix room ID can exist. The installer previously offered `roomMode = existing` immediately after the user enabled a profile Matrix bot, which could strand the questionnaire at a required `!room:server` prompt before Synapse existed.

## Invariants

- `roomMode = existing` is offered only when LatticeVale can prove an installer-managed Synapse deployment already exists by finding the managed Synapse `homeserver.yaml` in the selected managed stack.
- Fresh/unrecognized installs fail closed to `roomMode = create`; they never require a room ID that cannot exist yet.
- The optional room name is still collected during the questionnaire, but the actual private encrypted room is created later by the existing Matrix provisioning stage after Synapse and the default Matrix identity are ready.
- Existing managed installations retain the ability to adopt an existing encrypted room.
- No Matrix credentials, identities, room IDs, Docker topology, WSL ownership rules, or repair semantics were otherwise changed.
- v14.3.2 native-process exit-code handling and v14.3.1 StrictMode startup hardening remain unchanged.

### Former file: `LatticeVale-Core/AUDIT-v14.3.4.md`

# LatticeVale v14.3.4 audit note

## Scope

v14.3.4 is a preservation-focused hotfix for two issues observed on real Windows/WSL installs: fresh-install host settings being inferred from defaults, and `prepare_config` attempting `chmod 0750 vault` when the managed vault path was an external/Windows-backed target.

## Invariants

- Fresh installs set `questionnaireMode = explicit`; the old Quick Setup path is not offered.
- Y/N, numeric, menu, and Tailscale-port questionnaire choices require explicit input during a fresh install.
- Existing saved LatticeVale settings remain reusable on repair/change flows.
- A sole eligible Ubuntu distro and sole normal Ubuntu user are detected but still explicitly confirmed.
- Windows shortcuts use the selected user's actual passwd home; no `/home/<name>` fallback is invented.
- No Windows Documents-folder Obsidian vault is fabricated when none is registered.
- Container timezone reuses a saved value or the selected distro's detected IANA timezone; if neither is available the user must enter one.
- Remote Tailscale exposure never silently changes global WSL lifetime policy. Global WSL networking changes require explicit confirmation.
- `~/hermes-stack/vault` is never recursively owned or chmodded through a symlink/mountpoint. Known legacy Obsidian targets are inspected before bootstrap; detachment requires explicit consent and source files are never deleted.
- Exact legacy fstab cleanup remains source+target matched and retains the historical `.latticevale-v14.1.3.bak` recovery filename.
- After reconciliation, the local managed vault directory is recreated with the selected Ubuntu UID/GID and mode 0750.
- Linux `stage_prepare_config` independently refuses to chmod a remaining vault symlink/mountpoint.
- Schema 16 accepts `explicit` while retaining `quick` and `custom` for older saved installations.

## WSL permission rationale

Microsoft documents that Windows files exposed through WSL/DrvFS have permission behavior governed by Windows permissions and DrvFS metadata/mount options. A Linux `chmod` cannot be assumed to behave like it does on the distro's native Linux filesystem. LatticeVale therefore treats an external/Windows-backed vault as data to mount into containers, not as an installer-owned Linux tree to chmod/chown.

References:
- https://learn.microsoft.com/windows/wsl/file-permissions
- https://learn.microsoft.com/windows/wsl/wsl-config

## Regression coverage

`tests/v14.3.4-explicit-host-vault-fixtures.py` verifies the explicit fresh-install policy, detected-path/timezone handling, non-forced WSL lifetime behavior, legacy vault reconciliation hooks, and the Linux mount/symlink chmod guard. Retained v13/v14 fixtures continue to cover recovery, Matrix, WSL process handling, permission repair, relay behavior, and release portability.

### Former file: `LatticeVale-Core/AUDIT-v14.3.5.md`

# LatticeVale v14.3.5 audit note

Reviewed: 2026-08-17

v14.3.5 is a preservation-focused hotfix for a real Resume / repair failure where saved `ollamaAcceleration=amd` reached Linux `prepare_config` even though the selected WSL distro did not expose `/dev/kfd` and `/dev/dri`. The result was a deterministic configuration abort rather than a recoverable questionnaire decision. The same release also adds an optional native-Windows-Ollama path for cases where Windows can provide a usable native GPU backend while the selected WSL/Docker GPU path cannot.

## Invariants

1. **Selected-distro capability, not Windows hardware inference.** `Install-LatticeVale.ps1` probes the selected Ubuntu distro for the device/runtime evidence used by LatticeVale's Ollama paths. The Windows GPU model is not used as proof of WSL/Docker support.
2. **AMD forced mode precondition.** The currently managed Ollama Docker ROCm path is accepted only on x86_64 when `/dev/kfd` exists and `/dev/dri` exists in the selected distro. `/dev/dxg` is reported diagnostically but is not treated as an equivalent prerequisite for this existing container path.
3. **NVIDIA forced mode precondition.** Forced NVIDIA selection requires `/dev/dxg` and a successful WSL `nvidia-smi -L` probe before the questionnaire accepts it. NVIDIA Container Toolkit installation/runtime verification remains a later bootstrap responsibility.
4. **Repair does not guess.** If saved forced `amd` or `nvidia` state no longer passes the probe, Resume / repair explicitly offers: change managed policy to Auto, change it to CPU, or stop without changing the saved policy. There is no silent fallback.
5. **Fresh/reconfigure does not accept known-unavailable forced modes.** The menu labels unavailable forced GPU choices and loops until a currently admissible choice is made. Auto remains available and may resolve to CPU.
6. **Linux remains fail-closed.** `configure-stack.sh` retains forced-mode validation. If device/runtime state disappears after the PowerShell probe, configuration does not emit a knowingly invalid GPU overlay.
7. **Prior hotfixes retained.** v14.3.4 explicit host-state/vault handling, v14.3.3 Matrix room ordering, v14.3.2 native process handling, and v14.3.1 StrictMode startup behavior remain unchanged.

## Native Windows Ollama invariants

1. **Detection is not consent.** A Windows localhost Ollama API is detected read-only. Native mode is offered only after the selected WSL distro also exposes a non-loopback Windows-host route that Windows can actually bind.
2. **No native reconfiguration.** LatticeVale does not install/update native Ollama, mutate `OLLAMA_HOST`, change its model directory, or select its Windows GPU backend.
3. **Narrow relay ownership.** The installer-owned relay targets `127.0.0.1:11434`, listens only on the verified Windows-host interface, and creates an exact-port firewall rule whose remote address is the selected WSL IPv4. It does not bind all Windows interfaces.
4. **Pre-bootstrap self-test.** The relay is verified from the selected WSL distro before Linux stack bootstrap proceeds. The probe works with Python, curl, or Bash `/dev/tcp`, so a fresh distro is not assumed to already contain a particular HTTP client.
5. **No duplicate managed Ollama.** `ollamaBackend=windows-native` omits the `local-ai` Compose profile and removes an old managed `hermes-ollama` container while preserving its data. Hermes and Honcho use the `windows.host` relay mapping.
6. **Model pull stays native.** Missing user-selected model tags are requested through native Ollama's `/api/pull`; model files stay in the Windows Ollama store instead of being copied into WSL's managed Ollama store.
7. **Address churn is recoverable.** LatticeVale's start/restart helper restarts the relay and refreshes `WINDOWS_HOST_IP` before consumers start after WSL address changes.
8. **Fail closed.** If the native API or relay topology disappears on repair, LatticeVale asks whether to use managed Auto, managed CPU, or stop. It does not silently replace the saved backend.

## Regression coverage

`tests/v14.3.5-gpu-prerequisite-repair-fixtures.py` verifies the selected-distro probes, repair reconciliation choices, fresh/reconfigure rejection of unavailable forced modes, and retained Linux fail-closed check. `tests/v14.3.5-native-windows-ollama-fixtures.py` verifies detection/consent gating, narrow relay/firewall scope, native `/api/pull`, managed-container suppression, dynamic Hermes/Honcho routing, GPU-toolkit isolation, and relay refresh behavior. Existing v14.3.4 and historical fixtures continue to cover host-state explicitness, vault recovery, WSL/native process behavior, Matrix ordering, recovery, permissions, and release portability.

### Former file: `LatticeVale-Core/AUDIT-v14.3.6.md`

# LatticeVale v14.3.6 audit note

## Scope

v14.3.6 is a preservation-focused Matrix bootstrap hotfix. On the first Matrix identity run, `secrets/matrix-bot.env` is intentionally absent until after account login/room provisioning. v14.3.5 attempted to read `MATRIX_DEVICE_ID` from that missing file with a `sed | head` command substitution while `set -Eeuo pipefail` was active. `sed` returned status 2 for the missing file, `pipefail` propagated it, and the stage aborted before the fallback `LATTICEVALE_BOT` device ID could run.

## Fix invariants

- Optional installer state is read through `read_env_file_value_optional`, which returns success with an empty value when the file/key does not exist.
- The first Matrix bootstrap therefore reaches the existing `LATTICEVALE_BOT` fallback and proceeds to login/room creation.
- Existing one-time `secrets/matrix-bootstrap.env` state remains the resume source after an interrupted bootstrap; no replacement Matrix identity is invented.
- The room-capability fallback cannot be preempted by `pipefail` when the filtered stable-version list is empty; the explicit diagnostic runs instead.
- `manage.sh` tolerates an absent `.env` during incomplete installation/repair rather than failing during a read-only default lookup.

## Regression

`tests/v14.3.6-matrix-first-bootstrap-pipefail-fixtures.py` executes the optional env reader under `set -Eeuo pipefail`, verifies a missing file produces an empty successful lookup, verifies values containing `=` and CRLF are preserved correctly, and asserts the first Matrix device-ID read no longer uses the unsafe missing-file pipeline. Historical v14.3.x fixtures remain retained.

### Former file: `LatticeVale-Core/AUDIT-v14.3.7.md`

# LatticeVale v14.3.7 audit note

## Scope

v14.3.7 is a preservation-focused Hermes named-profile gateway lifecycle hotfix. A v14.3.6 run could successfully create a profile and then abort because the installer parsed `hermes -p <name> gateway status` and saw `running` after requesting stop. Upstream Hermes Docker uses one s6 slot per profile and exposes `/command/s6-svstat /run/service/gateway-<name>` as raw supervisor state; current upstream issue reports also document cross-profile status false positives and dynamic-s6 stop races.

## Invariants

- Credential handoff is gated by the exact `/run/service/gateway-<profile>` service state, not another profile's status.
- Normal `hermes -p <profile> gateway stop` remains the first action so Hermes can persist its intended stopped state.
- If necessary, LatticeVale requests `s6-svc -d` only for the same exact profile service.
- A final fallback may signal only the service PID freshly reported by that exact `s6-svstat` result. PID state is re-read before KILL escalation so a recycled/unrelated PID is never intentionally targeted.
- `pkill`, `killall`, all-profile gateway stop, and process-name matching are not used.
- Matrix profile runtime verification and later `manage.sh` start/restart reconciliation use the same exact s6 service truth.
- Existing named-profile files created before the v14.3.6 abort are preserved on Resume / repair.
- Release validation covers all eight shipped PowerShell files under the CI parser lists/static lexical/runtime-variable checks; the native Windows service relay is no longer omitted. Runtime opaque-token grep excludes regression fixtures that deliberately embed forbidden strings as negative tests, while compiled-artifact scanning remains tree-wide.

## Regression coverage

`tests/v14.3.7-profile-gateway-s6-fixtures.py` verifies source ordering and exact-service scoping across installer and `manage.sh`, rejects global kill patterns, and executes the quiesce helper against a fake Docker CLI for both a normal stop and a simulated dynamic-s6 stop race. Historical v14.3.x fixtures remain retained.

### Former file: `LatticeVale-Core/AUDIT-v14.3.8.md`

# LatticeVale v14.3.8 audit notes

## Scope

v14.3.8 is a preservation-first Matrix reliability/room-version hotfix layered on v14.3.7. It does not replace the existing Hermes profile, WSL, native-process, vault, GPU, or native-Windows-Ollama hardening.

## Matrix online-order invariants

- `stage_matrix_bootstrap` and `stage_matrix_profiles` start only the installer-managed `synapse-db` and `synapse` services and require both Synapse `/health` and the Matrix Client-Server `/_matrix/client/versions` endpoint before provisioning.
- Readiness is rechecked after interactive admin-password entry.
- Room-join polling is bounded. Three consecutive Matrix API-health failures return a distinct outage result instead of continuing the join loop.
- On a profile join outage, LatticeVale stops only that exact profile gateway, restarts its managed Synapse services, and retries that profile once. If the bounded recovery fails, identity/room state is preserved for Resume / repair.
- Default-bot reconciliation applies the same one-retry Matrix recovery boundary.

## Room-version invariants

- `LATTICEVALE_MATRIX_ROOM_VERSION=10` is the installer-managed room policy.
- Installer-managed Synapse configuration pins `default_room_version: 10`.
- Every LatticeVale-created default, profile, and migration-replacement room sends an explicit `room_version: "10"` in `createRoom` and then verifies the actual `m.room.create` room version.
- LatticeVale checks the server room-version capability before creating managed v10 rooms.
- Existing explicitly adopted user-owned rooms are not silently replaced or rewritten.
- Existing LatticeVale-managed non-v10 rooms are not downgraded in place. Repair backs up installer metadata, preserves the prior room, creates a replacement encrypted v10 room, and keeps the existing Matrix bot identity/token/device state.

## Regression coverage

`tests/v14.3.8-matrix-v10-online-order-fixtures.py` verifies the fixed v10 policy, Client-Server readiness ordering, preserved-room migration markers, absence of raw pre-E2EE `/join` calls, and executable bounded join behavior for both Matrix-offline and joined cases.

The broader deterministic/static suite retains all prior v14.3.1–v14.3.7 hotfix fixtures. Real Windows/WSL/Element behavior remains a platform smoke-test boundary and is not represented as proven by Linux-only fixture execution.

