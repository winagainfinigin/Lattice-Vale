# Current v14.x patch notes

## v14.4.83 resource/runtime reliability patch

The broad WSL warning/error audit showed two LatticeVale-owned runtime issues: managed Ollama was repeatedly cgroup-OOM-killed at the generated ~2.9 GiB ceiling on a roughly 10 GiB WSL VM, and both Honcho Redis and SearXNG Valkey repeatedly warned that Linux memory overcommit was disabled. The same audit also showed a noisy `wsl-pro.service` bridge even though Ubuntu Pro for WSL was not part of the desired LatticeVale configuration.

### Adaptive policy v4

Policy v4 preserves the v14.4.3-v14.4.6 aggregate budget/reserve model and existing service minima/caps. When managed Ollama is selected, the planner now computes its preferred minimum from the budget remaining after all other enabled-service minima, with a bounded target between 2048 and 4096 MiB and a 256 MiB margin. On the observed full-stack ~10 GiB WSL allocation this yields a 4096 MiB Ollama floor instead of the previous ~2944 MiB ceiling, while the aggregate generated limits still remain inside the same container budget. Constrained hosts continue through the existing proportional scaling path rather than consuming the WSL/kernel/Docker reserve.

`POLICY_VERSION=4` is enforced by clean generation, the uncheckpointed Resume / repair verifier, `manage.sh` start/restart refresh, the root stack-start helper, and `state-audit.py`. Existing adaptive policy-v3 installations therefore converge automatically without a version-only managed image/source refresh.

### Redis / Valkey overcommit prerequisite

When either SearXNG/Valkey or Honcho/Redis is selected, the root bootstrap idempotently writes `/etc/sysctl.d/99-latticevale-redis-valkey.conf` containing `vm.overcommit_memory = 1`, applies the effective value, and fails the root prerequisite stage if the value cannot be verified. The read-only state audit reports a repairable policy issue when an enabled Redis/Valkey workload sees a different effective value. If those workloads are later disabled, LatticeVale does not force-reset the kernel setting or delete external sysctl state because another application may also depend on it.

### Ubuntu Pro option removal

The current LatticeVale installer no longer prompts for Ubuntu Pro, stores an `ubuntuPro` option, installs `Canonical.UbuntuProforWSL`, or audits that Windows add-on. Current documentation and tests no longer present Ubuntu Pro as a LatticeVale option. The migration is intentionally non-destructive: pre-existing Ubuntu Pro packages, attachments, tokens, services, or externally managed state are not purged or detached.

### Post-install command correction

The installer and root README now include the selected Linux user in Windows `wsl` commands and resolve the stack from that account's `$HOME`. This avoids running `manage.sh` against the wrong home directory when the selected LatticeVale account is not the distro's default user.

# Consolidated Patch Notes

`CHANGELOG.md` is the canonical version history. This file preserves the more detailed implementation, audit, migration, and compatibility notes that were previously split across many one-off v14.x patch-note files. Historical v13 notes remain under `legacy-patch-notes/`.

## v14.4.82 WSL recovery return-value hotfix

The v14.4.81 helper wrapper invoked a child PowerShell process directly and then returned `$LASTEXITCODE`. In PowerShell, success-stream output emitted by the child process also becomes output from the wrapper function. Because the helper prints diagnostics, the caller's `$exitCode` variable could therefore contain diagnostic strings plus the final integer `0` rather than one scalar integer. The recovery itself could succeed, but the caller would miss `if ($exitCode -eq 0)` and fall through to the generic no-eligible-distro failure.

v14.4.82 pipes the child helper's normal output to `Out-Host`, captures `$LASTEXITCODE` immediately afterward, and returns only that integer. The helper remains fully visible to the operator, while success now enters the existing post-recovery distro re-probe. The WSL recovery order, NAT fallback conditions, ownership rules, and 50 GiB fresh / 10 GiB managed-repair storage thresholds are unchanged.

## v14.4.81 WSL launch-recovery hotfix — bounded `E_UNEXPECTED` recovery

### Problem

On some current Windows/Store-WSL systems, `wsl --list` and registration metadata remain available while launching an otherwise valid Ubuntu WSL2 distro returns `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure`. Earlier LatticeVale releases classified the distro as ineligible and directed the user to the separate WSL host-repair helper, so a recoverable WSL-host cold-start failure always terminated the installer run.

### Fix

v14.4.81 keeps the existing ownership boundary but connects the safe subset of that helper to preflight:

1. Recovery is considered only for an existing registered distro carrying the `WSL_HOST_E_UNEXPECTED` blocker and only when no eligible path exists **or** that broken distro was explicitly requested.
2. Before any global WSL restart, other running distros are detected; if unrelated distros are running, the user must explicitly approve stopping them. If WSL cannot reliably enumerate running distros during the fault, LatticeVale treats that state as unknown and also requires explicit approval instead of assuming the host is clear.
3. The helper runs bounded `wsl --shutdown`, waits eight seconds for WSL/HNS to settle, and re-tests the same distro with a bounded launch probe.
4. If that succeeds, no host configuration was changed. The installer performs a full fresh eligibility probe and may continue in the same run.
5. If the same E_UNEXPECTED persists and `.wslconfig` explicitly selects mirrored networking, the helper returns a distinct result so the installer can offer a second explicit choice: back up `.wslconfig`, change only `[wsl2] networkingMode` to `nat`, restart WSL, and retest.
6. The bounded shutdown/re-probe and user-profile `.wslconfig` fallback do not require elevation, so they can run from the normal installer. If bounded recovery still fails, the installer stops; it does not automatically run DISM or mutate Windows feature state. The deeper component/feature-repair phase remains an explicit Administrator action.

### Preservation and scope

The recovery never unregisters, imports, converts, moves, recreates, or deletes a distro and never edits its VHDX. The NAT fallback preserves unrelated `.wslconfig` keys and creates a timestamped backup first. NAT is not forced merely because mirrored mode exists; it is offered only when the launch failure survives a clean WSL restart and is still classified as E_UNEXPECTED. This matters because `E_UNEXPECTED` is a generic WSL host error and can have causes unrelated to networking.

v14.4.81 does not alter the v14.4.8 Hermes browser/web reconciliation, integration checkpoint, component pins, managed refresh revision, container/resource policy, or user/model configuration. It also leaves the established storage thresholds unchanged: after WSL recovery, ordinary clean-versus-managed-repair storage checks run normally.

### Upstream basis

Microsoft documents `.wslconfig` as global WSL2 configuration, NAT as the default networking mode, and `wsl --shutdown` as the fast path for restarting WSL. Reports in Microsoft's official `microsoft/WSL` issue tracker on Windows build 26200 document this same `E_UNEXPECTED` / catastrophic-failure class and cases where `wsl --shutdown` restores launch/session creation. See <https://learn.microsoft.com/windows/wsl/wsl-config>, <https://learn.microsoft.com/windows/wsl/troubleshooting>, <https://github.com/microsoft/WSL/issues/14014>, and <https://github.com/microsoft/WSL/issues/14193>.

## v14.4.8 maintenance patch — Hermes clean/repair reliability, CI portability, and documentation consolidation

v14.4.8 stays within LatticeVale-owned setup and reconciliation behavior. It does not write `SOUL.md`, alter prompts/model policy, or take ownership of user-selected Hermes providers.

- Fresh installer-managed Hermes profiles use Hermes's free local Chromium browser only when no explicit browser backend/provider, browser gateway route, or recognized Hermes browser environment selection already indicates another choice.
- Resume / repair applies the same missing-default repair while preserving explicit Browserbase, Browser Use, Camofox, CDP, gateway/custom provider, executable-path, credential, and timeout choices.
- Missing `auxiliary.web_extract.timeout` is filled with Hermes's documented 360-second default; explicit values are preserved.
- SearXNG remains the LatticeVale-managed search backend and `latticevale-local` remains the managed extraction backend. No additional search service, browser service, API key, or paid dependency is introduced.
- The integrations checkpoint advances from revision 3 to revision 4 so an existing managed stack can adopt these installer-owned defaults on the next mutating reconciliation without forcing the managed package/image/source refresh gate.
- The Linux static audit now reports a normal failed invariant when an expected installer marker is absent instead of throwing an uncaught substring exception.
- Release-manifest path resolution is normalized so Windows-style manifest paths resolve consistently across supported PowerShell environments while retaining strict missing-file/hash validation.
- Current v14.x one-off patch-note files are consolidated into this document; canonical GitHub/community documents remain separate and the v13 legacy archive is unchanged.

The detailed v14.4.7 extraction design and prior v14.x implementation notes follow below.

## Archived source: `WEB-EXTRACTION-PATCH-NOTES.md`

### v14.4.7 Web Extraction Patch Notes

#### Problem

A v14.4.6 installation with SearXNG could perform Hermes `web_search`, but Hermes `web_extract` failed because the pinned Hermes SearXNG provider is intentionally search-only. Both default and installer-managed profiles could therefore discover URLs while being unable to read ordinary web pages unless the user independently configured another extraction provider.

#### Design

v14.4.7 keeps the existing SearXNG + Valkey topology unchanged and adds a LatticeVale-owned Hermes web-provider plugin keyed `web/latticevale-web-extract` (manifest name `latticevale-web-extract`). It registers the provider name `latticevale-local` for extraction only.

When SearXNG is selected, LatticeVale sets `web.search_backend: searxng` as before. If `web.backend` is empty/SearXNG and `web.extract_backend` is empty/SearXNG/LatticeVale-local, it sets `web.extract_backend: latticevale-local`. An explicit Firecrawl, Tavily, Exa, Parallel, or custom shared/extract provider remains untouched.

The plugin is generated inside each applicable LatticeVale-managed Hermes home and enabled through that profile's normal `plugins.enabled` list. It uses the web-provider API already shipped in Hermes Agent v0.20.2 / v2026.8.16. No Hermes source tree is patched in place.

#### Stability

The patch deliberately does **not** add self-hosted Firecrawl or another extraction service. No Compose service, image, database, queue, browser process, port, systemd unit, Windows task, WSL networking setting, CPU/RAM limit, model, package installation, or API credential is added. Existing SearXNG, QMD, Honcho, Matrix, Ollama, Kanban, Tailscale, Obsidian and resource-policy behavior is inherited.

The integrations checkpoint revision advances from 2 to 3. Resume / repair therefore reconciles the new managed-profile integration, but this does not advance `MANAGED_REPAIR_REFRESH_REVISION` and does not by itself force package/image/source refresh. Before that repair run, fully stop the selected LatticeVale WSL distro; if installed, **Shut Down LatticeVale** is the recommended method because it stops the managed stack and terminates only that distro.

#### Network and content safety

`latticevale-local` is for ordinary public web documents, not arbitrary network retrieval. It:

- accepts only HTTP and HTTPS;
- rejects embedded URL credentials;
- resolves the destination and rejects any loopback/private/link-local/reserved/non-global address;
- revalidates every redirect destination;
- disables environment-proxy inheritance for its HTTP client;
- caps redirects at 5;
- caps each response body at 2,000,000 bytes;
- uses bounded connect/request timeouts;
- accepts text-oriented MIME types only;
- strips script/style/noscript/template/SVG/canvas content from HTML text extraction;
- caps returned text and reports per-URL errors without crashing the provider.

This is intentionally not an authenticated browser, JavaScript renderer, file downloader, or local-network client. Sites that require JavaScript, login state, anti-bot challenges, or a full browser can still require a separately configured browser/extraction provider.

#### Search-result availability

The v14.4.7 extraction fix does not change how external search engines treat SearXNG traffic. SearXNG is hosted locally, but discovery still depends on upstream engines that can independently rate-limit, CAPTCHA, suspend, or refuse automated requests. Hermes can therefore receive a successful `web_search` response containing zero results even while the local SearXNG JSON API and provider wiring are healthy.

This is not, by itself, a LatticeVale repair condition. Retry later or broaden the query, inspect SearXNG's reported unresponsive engines when diagnosing repeated failures, and use `web_extract` directly when a trusted public URL is already known. Installation repair is appropriate when the local search/provider path itself is broken or the v14.4.7 extraction path cannot read ordinary known public pages.

#### Upgrade behavior

- **Fresh install:** applicable managed profiles receive SearXNG search + LatticeVale local extraction.
- **v14.4.6 repair/resume:** integrations revision 3 applies the same pairing without a forced managed refresh.
- **Explicit extraction provider already configured:** preserved.
- **SearXNG deselected:** LatticeVale removes only its own SearXNG search selection and local extraction selection/plugin; unrelated web-provider configuration remains.

#### Verification

Release regression coverage includes the v14.4.7 fixture, inherited fixtures, aggregate static audit, Python/shell syntax checks, mocked resume simulations, and complete source-manifest verification. Live target-system validation remains distinct from static fixture coverage; see `WINDOWS-INTEGRATION-TEST-MATRIX.md`.

---

## Archived source: `RESOURCE-FINGERPRINT-AUDIT-PATCH-NOTES.md`

### LatticeVale v14.4.6 — Adaptive Resource Fingerprint Audit Fix

#### Problem

A real v14.4.5 repair correctly generated adaptive RAM/resource policy v3 with `CPUS=4` and `MEM_MIB=9946`, then reconciled the full Compose stack. Immediately afterward, `./manage.sh audit` still reported `runtimePolicy PARTIAL` even though `nproc`, `/proc/meminfo`, and `.latticevale-resource-state` all matched. A normal `./manage.sh restart` did not clear the condition.

#### Root cause

The generator, verifier in `configure-stack.sh`, and `manage.sh` refresh path use `nproc`, which reports processors available to the WSL process. `state-audit.py` instead used `os.cpu_count()`. On a Windows host exposing 8 logical CPUs with WSL limited to 4 processors, Python can report 8 while `nproc` and the generated fingerprint correctly report 4. Audit therefore compared two different CPU concepts and falsely declared the policy stale.

#### Fix

`state-audit.py` now determines adaptive-policy CPU count in this order:

1. `len(os.sched_getaffinity(0))` — process-visible CPU affinity, matching Linux scheduler availability;
2. `nproc` — the same effective source already used by LatticeVale's generator/manager;
3. `os.cpu_count()` — last-resort fallback only.

RAM comparison remains exact. No tolerance is added because the reproduced failure showed identical live/saved RAM; hiding memory drift would be unnecessary and could mask a real `.wslconfig` allocation change.

#### Repair behavior

No new repair stage is required. v14.4.5 already correctly regenerates stale policy v3 and forces affected containers through Compose reconciliation. v14.4.6 corrects only the read-only post-repair audit so it evaluates the generated fingerprint using the same CPU semantics.

#### Managed-refresh trigger refinement

v14.4.6 also narrows the automatic component-refresh trigger introduced in v14.4.5. A change in LatticeVale's display/release version alone no longer forces APT refreshes, image pulls, or QMD/Honcho rebuilds. Resume / repair refreshes the managed package/image/source layer only when the 30-day age gate is due, `MANAGED_REPAIR_REFRESH_REVISION` changes, a legacy install has no valid refresh state, or Windows installer Option 6 explicitly forces it. The recorded `INSTALLER_VERSION` remains useful provenance but is not itself a refresh predicate.

This is deliberately compatible with the public v14.4.2 baseline. v14.4.2 uses managed-refresh revision 1 and adaptive resource policy v2; v14.4.6 uses managed-refresh revision 2 and adaptive resource policy v3. Therefore a direct 14.4.2→14.4.6 Resume / repair still performs the bounded managed component refresh and RAM-policy migration required by the cumulative patch set. By contrast, a recently refreshed v14.4.5 install already at revision 2/policy v3 can adopt the 14.4.6 audit fix without rebuilding healthy images solely because the bundle version changed.

Pending refresh markers still record their origin bundle. If their policy revision matches the current revision, repair resumes the pending user-level image/build/source phase without repeating completed root package work; if the revision differs, the bounded root phase is rerun.

#### Regression coverage

The v14.4.6 fixture reproduces `os.cpu_count()=8` with process affinity=4 and requires the audit helper to return 4. It also verifies fallback to `nproc` and then `os.cpu_count()` when affinity/nproc are unavailable. Inherited repair/runtime-update and RAM-policy fixtures remain required.

---

## Archived source: `REPAIR-RUNTIME-POLICY-UPDATE-PATCH-NOTES.md`

### LatticeVale v14.4.5 — Repair Runtime-Policy and Managed-Update Convergence

> **Current-release note (v14.4.81):** The runtime-policy convergence mechanics below remain current. v14.4.6 superseded v14.4.5's bundle-version-only managed-refresh trigger; v14.4.8 retained that managed-refresh policy while advancing the integrations checkpoint for browser/timeout reliability, and v14.4.81 leaves both policies unchanged while adding only bounded WSL launch recovery. Current Resume / repair refreshes package/image/source state when the periodic age gate is due, `MANAGED_REPAIR_REFRESH_REVISION` changes, valid legacy refresh state is missing, or Option 6 explicitly forces refresh. `INSTALLER_VERSION` remains marker provenance only.

#### Problem observed

A real Resume / repair from v14.4.4 completed successfully while `./manage.sh audit` still reported `runtimePolicy PARTIAL`. The adaptive RAM-policy generator lived inside `stage_prepare_config`, but the existing install already had a completed/current `prepare_config` checkpoint. Repair therefore skipped the action that generated policy v3.

A second issue existed in the startup helper: `manage.sh` still compared the persisted resource-policy version against `2` even though the generator writes policy version `3`.

The repair/update audit also showed that the periodic managed-refresh marker tracked time and refresh-policy revision but did not use the recorded installer bundle version as a refresh trigger. That meant a normal Resume / repair from a newer bundle could remain local-first until the age window elapsed unless the user explicitly chose Update / repair.

#### v14.4.5 behavior

- Repair has an explicit, uncheckpointed `repair_runtime_policy` reconciliation step.
- Adaptive policy verification requires policy version 3, current WSL-visible CPU/RAM fingerprint, `compose.latticevale.yaml` participation in `COMPOSE_FILE`, `MALLOC_ARENA_MAX`, selected Synapse cache tuning, and selected managed PostgreSQL `shared_buffers`; Honcho retains `max_connections=200`.
- If the overlay is regenerated, `infrastructure` and `reconcile` are marked pending. This ensures Compose applies changed limits/environment/commands to live containers instead of merely leaving a correct YAML file on disk.
- Final configuration fails rather than marking installer state complete if the adaptive policy is still stale/incomplete.
- `manage.sh` compares against policy version 3.
- v14.4.5 originally treated a different recorded installer bundle version as a managed-refresh trigger. **This specific trigger is superseded by v14.4.6**; current automatic refresh uses the periodic age gate, managed-refresh revision, or missing legacy state.
- v14.4.81 retains v14.4.6's local-first behavior whenever the periodic age gate is fresh and the managed-refresh revision is already current, regardless of a version-only bundle change. Explicit Update / repair still forces the current bundle's managed refresh immediately.
- Interrupted refresh markers record bundle version for provenance. v14.4.8 retains v14.4.6's rule: a pending refresh resumes without repeating completed root package work when its managed-refresh revision matches; a revision mismatch reruns the bounded root phase. A version-only difference does not force repetition.
- `./manage.sh restart` detects when its adaptive resource refresh regenerated the overlay and runs Compose reconciliation before the requested restart, so changed RAM/environment/command settings cannot remain disk-only.
- Explicit user-owned image/source refs and `compose.override.yaml` remain preserved; the latter remains the last Compose layer.

#### Component-update semantics

Resume / repair is not an unrestricted `latest` updater. When its age/revision/legacy-state trigger requires a managed refresh, it converges installer-owned surfaces to the versions/channels/pins declared by that bundle. Named Ubuntu prerequisite/Docker packages are refreshed through APT's targeted install path, selected registry images are pulled through Compose/Docker, QMD/Honcho buildable services are rebuilt with pull enabled, and the Hermes image is pulled when the managed refresh is pending. Unrelated Ubuntu packages and user-owned custom refs are not broadly upgraded.

#### Validation

`tests/v14.4.5-repair-runtime-policy-update-fixtures.py` asserts the explicit repair step, final fail-closed gate, live-container reconciliation checkpointing, policy-v3 startup comparison, managed component refresh paths, and user override ordering. v14.4.8 retains v14.4.6's removal of the historical version-only trigger; `v14.4.6-upgrade-refresh-gating-fixtures.py` remains the inherited guard for the 14.4.2 revision-1 and 14.4.5 revision-2 refresh paths. Inherited v14.4.3 RAM/uninstaller and v14.4.4 metadata-race fixtures remain required.

---

## Archived source: `REPAIR-METADATA-RACE-PATCH-NOTES.md`

### LatticeVale v14.4.4 repair metadata-race hardening

#### Problem

During Resume / repair, `linux/bootstrap.sh` normalizes ownership and write permissions on installer-managed user-data trees. In v14.4.3 this used recursive `chown`/`chmod`. If a live SQLite sidecar such as `data/hermes/kanban.db-shm` disappeared while that traversal was in progress, GNU `chown` returned non-zero and `set -e` aborted the entire bootstrap even though the disappearance was normal runtime behavior.

The observed failure was:

```text
chown: changing ownership of '.../data/hermes/kanban.db-shm': No such file or directory
Bootstrap failed
```

#### v14.4.4 behavior

`repair_user_tree` now:

- rejects a managed root that is a symlink or mountpoint as before;
- snapshots the current tree with `find -P -xdev -ignore_readdir_race`;
- applies ownership one entry at a time with `chown -h`;
- skips `chmod` for symlinks and never follows them;
- tolerates a failed metadata operation only when the exact entry no longer exists;
- remains fail-closed when the entry still exists, preserving detection of real permission or ownership problems;
- does not cross nested mount boundaries.

This makes repair compatible with live SQLite WAL/SHM churn and log rotation without converting genuine filesystem errors into success.

#### Install-path impact

Clean installs continue through the same bootstrap and receive the same safe metadata walker, but normally have little or no pre-existing live state to reconcile. Resume / repair is the path that materially benefits because existing Hermes services may still be active when root-assisted ownership reconciliation begins.

No WSL distribution ownership, Docker-global cleanup policy, user `compose.override.yaml`, persistent database ownership boundary, networking policy, RAM policy, or uninstaller behavior is changed by v14.4.4.

See `CHANGELOG.md` for canonical release history.

---

## Archived source: `RAM-UNINSTALL-HARDENING-PATCH-NOTES.md`

### LatticeVale v14.4.3 RAM-efficiency and uninstaller hardening

#### Scope

v14.4.3 is a targeted runtime/maintenance patch over v14.4.2. It does not add services or dependencies.

#### Adaptive resource policy v3

When `containerResourceLimits` is enabled, the generated installer-owned Compose overlay now:

- reserves more WSL/Docker/host headroom on smaller WSL VMs;
- constrains glibc allocator arena growth in long-lived Python/glibc services with `MALLOC_ARENA_MAX`;
- uses a lower supported Synapse cache factor on constrained hosts;
- uses 64 MiB PostgreSQL `shared_buffers` on <=12 GiB WSL VMs and 128 MiB above that;
- preserves Honcho PostgreSQL `max_connections=200`;
- keeps user `compose.override.yaml` as the final override layer.

The policy is generated during ordinary configuration on a clean install. Existing installs with adaptive limits enabled are regenerated when the saved policy revision is older than v3 or WSL-visible CPU/RAM changes, so repair/start adopts the new policy without deleting application data.

LatticeVale deliberately does not write global WSL `memory` or `autoMemoryReclaim` for this feature. Current host-wide WSL resource/reclaim policy remains user/Windows-owned.

#### Normal-uninstaller fixes

The preservation-first uninstaller now:

1. reads selected-stack metadata using root WSL context and aborts if required metadata cannot be read safely;
2. detects evidence that Docker runtime may still exist and refuses partial uninstall/purge if the Docker daemon cannot be inspected;
3. preserves modified/unowned scheduled tasks and shortcuts as before, but now also preserves helper/config files that those retained objects still reference;
4. checks ordinary LatticeVale firewall ownership before same-name firewall removal;
5. restores installer-owned `OLLAMA_HOST` only when the current value still matches the recorded installer value and broadcasts `WM_SETTINGCHANGE` after restoration;
6. recognizes normal users with nonstandard absolute home paths when deciding whether distro-level helper/policy/log state is shared;
7. removes `/var/log/hermes-dockerd.log` only when no other recognizable LatticeVale stack remains in the distro.

The uninstaller still does not unregister WSL, uninstall Docker, remove unrelated Docker state, uninstall native Windows Ollama/Tailscale/Obsidian, or delete an external Windows-backed Obsidian vault.

#### Clean versus repair adoption

- **Clean install:** the current `configure-stack.sh` writes policy v3 before normal Compose validation/reconciliation.
- **Repair/update:** the bundle replaces installer-owned runtime scripts while preserving data/config; normal reconciliation writes the current overlay, and the generated startup helper additionally refreshes any enabled adaptive policy whose revision/resource fingerprint is stale.
- **User overrides:** `compose.override.yaml` remains listed after `compose.latticevale.yaml`, so user policy wins.

---

## Archived source: `DOCUMENTATION-AUDIT-v14.4.0.md`

### LatticeVale v14.4.0 documentation audit and v14.4.1 layout follow-up

#### Scope

The v14.4.0 stable promotion was prepared from the audited v14.3.43 runtime tree. The documentation audit reviewed the complete Markdown/text documentation set, including current operator/release documents and the explicitly archival pre-LatticeVale v13 patch-note collection. Ambiguous or historical claims were cross-checked against the current installer/configuration source before being treated as current behavior.

v14.4.0 intentionally does **not** introduce new runtime stack behavior. It promotes the tested v14.3.43 runtime line and applies documentation, version/test metadata, and release-integrity changes.

#### v14.4.1 layout follow-up

v14.4.1 later moved substantive documentation under `docs/` and public entry points plus the source manifest under `installer/`. References below to files being at repository root describe the v14.4.0 audit state at the time of that remediation; current locations include `docs/FEATURES.md`, `docs/Instructions.txt`, `docs/Installer Description.txt`, `docs/CHANGELOG.md`, `docs/SECURITY.md`, `docs/SOURCES.md`, `docs/THIRD-PARTY-NOTICES.md`, `docs/RELEASE.md`, and `installer/SOURCE-SHA256SUMS.txt`. The repository-root `README.md` and `LICENSE` remain at root.

#### Remediated findings

| Finding | v14.4.0 remediation |
| --- | --- |
| Clean-host reset opening understated destructive WSL scope | `Instructions.txt` now states up front that `-RemoveWslRuntime` unregisters **all WSL distributions registered to the current Windows user**. |
| Fresh storage requirement was incomplete in primary docs | README and Instructions now state both conditions: backing volume **over 50 GiB total capacity** and **at least 50 GiB free**. |
| README questionnaire omitted resource ceilings and timezone | Both choices are now explicitly listed. |
| Instructions incorrectly coupled QMD-only use to a Windows Obsidian vault path | Instructions now state that the explicit Windows-local vault path is required by **Obsidian integration**; QMD alone does not require it. |
| Automatic skill-writing default was not prominent | README, Instructions, Installer Description, and `FEATURES.md` now state that fresh managed profiles default `skills.write_approval` to `false` when absent and that repair/update preserves an explicit existing choice. |
| Change-installed-components scopes were not enumerated | Instructions now lists all current scope categories. |
| Advanced-recovery actions were not enumerated | Instructions now lists all current recovery actions. |
| No canonical complete feature/options inventory | Added root `FEATURES.md` and cross-linked it from primary documentation. |
| README contained duplicated/overlong patch chronology | Primary README now leads with stable current capabilities and points detailed history to `CHANGELOG.md`/patch notes. |
| Networking patch notes duplicated v14.3.41 supersession wording | Duplicate notice collapsed while retaining the historical warning. |

#### Stable-release validation evidence

Before the v14.4.0 promotion, the v14.3.43 runtime line was exercised successfully through:

- a real-host fresh clean installation producing a working stack;
- a real-host repair/upgrade from v14.3.42 to v14.3.43 producing a working stack.

For the v14.4.0 packaging tree, inherited high-risk regression fixtures plus the new documentation-audit fixture are rerun after the version/documentation changes, followed by source syntax/static checks, release-manifest regeneration, ZIP integrity checking, and manifest verification against a freshly extracted copy.

This evidence does not imply that every future Windows build, WSL release, GPU driver, AI provider, Matrix client, Tailscale policy, or upstream dependency has been end-to-end tested. Those remain integration boundaries documented in the primary security/release material.

#### Documentation roles after remediation

- `README.md` — concise project overview, requirements, quick start, current highlights.
- `FEATURES.md` — canonical complete current features/install-options reference.
- `Instructions.txt` — procedural install, repair, operation, recovery, and reset guide.
- `Installer Description.txt` — plain-language capability/configuration guide.
- `CHANGELOG.md` — canonical version history.
- `SECURITY.md` — privilege, trust, network, secret, destructive-action, and supply-chain boundaries.
- `SOURCES.md` / `THIRD-PARTY-NOTICES.md` — upstream/source and redistribution boundaries.
- `RELEASE.md` — release engineering checklist.
- `PATCH-NOTES.md` — consolidated detailed implementation lineage from the former one-off v14.x patch-note files.
- `docs/legacy-patch-notes/hermes-wsl-foundry-v13/` — explicitly archival historical material only.

---

## Archived source: `BACKPORT-NOTES.md`

### LatticeVale 14.4.2 stable promotion / compatibility lineage

#### v14.4.2 documentation/release consistency patch

v14.4.2 preserves the v14.4.1 package layout and validated v14.4.0 stack runtime while correcting current-release documentation, version/validation metadata, regression compatibility, and release integrity data. No installer or stack-runtime behavior changes are introduced.

#### v14.4.1 release-layout patch

v14.4.1 reorganizes release files without changing the validated v14.4.0 stack runtime: public entry points and the exact source manifest move under `installer/`, substantive documentation moves under `docs/`, and conventional Git/GitHub landing/legal files remain at repository root. Launcher path resolution, clean-host release-root recognition, tests, CI, and manifest generation are updated for that layout.

#### v14.4.0 stable promotion

v14.4.0 promotes the audited v14.3.43 runtime line to the stable milestone without intended runtime behavior changes. The promotion incorporates the final documentation audit, canonical `FEATURES.md`, release metadata/test compatibility updates, and a regenerated source manifest. The v14.3.43 defensive Scheduled Task action inspection remains the most recent runtime code correction.

This custom release starts from the supplied 14.3.30 bundle. Downstream patch identifiers 14.3.31 through 14.3.43 record this local regression/stability sequence and do not claim equivalence to separately supplied/upstream releases with matching numbers. The stable downstream runtime milestone was versioned `14.4.0`; v14.4.1 is the later layout-only patch. The runtime preserves the v14.3.41 host-safety behavior, adds the explicit clean-host reset boundary, and retains the change that removes the remaining normal-installer ability to create mirrored WSL networking; the explicit host-repair helper retains a reversible NAT recovery path.

Backported behavior:
- Kanban/skill policy migration is capability/profile-roster based, re-applies on clean and repair/update paths, preserves valid user-created routing targets, and does not edit user-owned profile configs.
- Skill-management recovery responds to Hermes validation errors instead of repeating malformed calls; tool-loop hard stops remain enabled.
- scoped existing-install Change mode that begins from saved settings;
- native Windows Ollama GPU/RAM residency warning;
- managed-Ollama repair accepts inactive/blank native relay transport without persisting a fake native transport;
- aggregate adaptive container-memory budgeting across enabled services, with CPU/RAM fingerprinting;
- resource refresh occurs only when limits are enabled and the WSL-visible fingerprint changes;
- secondary Matrix profiles are automatically retried, but a failed optional profile no longer aborts the entire stack start/repair;
- Kanban policy plugin forces model-driven task creation through triage and validates named profiles against the live Hermes profile roster; direct human CLI/dashboard actions remain outside this plugin hook.

The original 14.3.30 relay architecture remains the compatibility baseline. v14.3.32 first made networking capability-first; v14.3.41 further supersedes its mirrored fallback by making global WSL `networkingMode` host/user-owned and non-mutating during normal LatticeVale operation.
#### Online compatibility audit (2026-08-19)

- Mirrored WSL networking remains an optimization, not a hard dependency. LatticeVale retains the 14.3.30 NAT/host-discovery and relay fallbacks because upstream WSL continues to have mirrored-networking regressions involving Docker-published ports and loopback connectivity.
- Secondary Matrix activation, per-profile gateway reconciliation, and per-profile cross-signing/recovery-key completion are best-effort across every retry path. Failure of an optional profile must not abort the core stack or destroy its existing identity/room state.
- Adaptive resource refresh now treats a missing/corrupt `.latticevale-resource-state` as stale state and regenerates it instead of risking an early `set -e` exit.
- The Kanban plugin is described as a runtime guard only on Hermes execution surfaces that actually invoke plugin `pre_tool_call`; prompt policy remains the fallback.
- The Hermes image remains pinned to v2026.8.16 for baseline stability. Newer upstream Hermes releases are intentionally not folded into this backport without a separate compatibility pass.


#### Online audit follow-up: WSL cold-start preflight

A repair-install failure observed on Store/MSIX WSL 2.7.12 exposed an overly aggressive
preflight assumption: the first read-only distro probe was allowed only the normal 15-second
probe window. Existing server distros may need longer during a cold start while init/systemd
and Docker restore services. The preflight now retries only the idempotent `/etc/os-release`
read with an extended 45-120 second cold-start window before declaring the distro unresponsive.
It does not automatically terminate WSL and does not retry mutating commands.

Host free space below the fresh-install reserve is also reported as DEFERRED while the distro
is unresponsive, because the installer cannot inspect the existing managed stack until Linux
starts. Once responsive, the existing 10 GiB managed-repair exception is evaluated normally.
This avoids presenting a 50 GiB fresh-install requirement as a second root cause for an otherwise
valid repair installation.

---

## Archived source: `CLEAN-HOST-RESET-PATCH-NOTES.md`

### v14.3.42 Clean-host reset patch notes

#### v14.3.43 Scheduled Task compatibility follow-up

A real Windows dry run exposed a portability bug in v14.3.42: Task Scheduler action collections are heterogeneous, but the reset scanner dereferenced Exec-only `Execute`, `Arguments`, and `WorkingDirectory` fields on every action. v14.3.43 replaces those direct dereferences with optional-property inspection and includes common Exec/COM-handler metadata only when present. Unknown/non-owned tasks remain untouched. No destructive scope was broadened.


#### Purpose

This release adds a deliberately separate clean-host reset path for administrators who want to destroy an existing WSL/LatticeVale environment and rebuild from a fresh WSL installation. It does not make normal uninstall, repair or update more destructive.

#### Ownership boundary

The reset utility removes Windows objects only when their names/actions/paths prove LatticeVale ownership, or when the administrator explicitly selects legacy pre-LatticeVale Foundry cleanup. It preserves independently installed Windows Tailscale and Obsidian, shared Hyper-V/HypervisorPlatform/VirtualMachinePlatform/HNS infrastructure, unrelated firewall/HNS state, and standalone `%USERPROFILE%\.hermes`.

#### WSL reset

`-RemoveWslRuntime` is intentionally broad and destructive: it enumerates all WSL distros registered for the current Windows user, requires explicit confirmation before execution, unregisters them, removes former registered distro storage, removes `.wslconfig*`, and attempts to uninstall the Store/MSI `Microsoft.WSL` package. It does not disable shared Windows virtualization features or manually delete HNS networks.

#### Tailscale

The tool never uses `tailscale serve reset`. It inspects current Serve JSON and disables a specific HTTPS listener only when the current configuration still references a known LatticeVale bridge backend, preserving unrelated tailnet services.

#### Release rule

The utility is dry-run by default, never invoked automatically, and source-tree deletion requires a recognizable LatticeVale release root (`installer/install.ps1` + `LatticeVale-Core/VERSION.txt`) and refuses filesystem roots.

---

## Archived source: `WSL-HOST-SAFETY-PATCH-NOTES.md`

### LatticeVale v14.3.41 detailed WSL host-safety notes

> Canonical release entry: `CHANGELOG.md` -> `14.3.41` (2026-08-19).

> **v14.4.81 supersession:** the v14.3.41 ownership rule remains authoritative for ordinary networking configuration, but v14.4.81 may invoke the same repair helper in bounded `-LaunchRecoveryOnly` mode from preflight. That safe-first mode does not require elevation; deeper DISM/feature repair still does. A mirrored→NAT edit remains separately explicit and backed up.

#### Why this correction exists

Earlier downstream LatticeVale networking compatibility work could explicitly switch the global `%USERPROFILE%\.wslconfig` `[wsl2] networkingMode` to `mirrored` after user consent when native Windows Ollama and/or Windows Tailscale integration could not verify another path. Later releases became NAT/capability-first, but an already configured mirrored value was still preserved and treated as a valid shared topology.

A global `.wslconfig` setting applies to WSL2 at the host level, not to one LatticeVale distro. A topology that appears healthy during an installation can also be exercised differently after a full Windows/WSL restart. Current Microsoft WSL documentation keeps NAT as the default mode and documents other networking modes as host-level configuration. Current microsoft/WSL issue reports show `E_UNEXPECTED` on Windows 11 build 26200; separate mirrored-networking regressions have also been reported. Together they justify conditional compatibility caution, not a claim that mirrored networking causes every `E_UNEXPECTED` failure.

The v14.3.41 policy is therefore ownership-based: normal LatticeVale operation does not choose the global WSL networking architecture.

#### Normal installer/runtime behavior

`LatticeVale-Core/Install-LatticeVale.ps1` no longer contains a normal-runtime function that writes `[wsl2] networkingMode` or a native-Ollama mirrored-mode fallback. This applies to clean install and every mutating existing-install mode.

- Default/NAT/VirtioProxy-capable networking remains supported with dynamic topology discovery, scoped relays, and exact firewall rules.
- If the user/host already has mirrored mode configured and the distro launches successfully, LatticeVale may consume that working topology without rewriting `.wslconfig`. The saved owner is `user-existing-mirrored`.
- Native Windows Ollama no longer causes LatticeVale to propose a global mirrored switch. If the current topology cannot verify a safe bridge, the remaining choices are the explicit scoped direct-Ollama compatibility path (where supported/accepted) or LatticeVale-managed WSL/Docker Ollama.
- LatticeVale may still manage the separately supported `[general] instanceIdleTimeout=-1` setting when the user selects persistent WSL services. That setting is not a networking-mode choice and is kept separate from this correction.

#### Explicit host recovery helper

`tools/Repair-LatticeVale-WslHost.ps1` remains the explicit host-recovery implementation. In v14.4.81 its bounded `-LaunchRecoveryOnly` subset can be invoked by preflight without elevation because it is limited to WSL shutdown/retry and the separately approved user-level `.wslconfig` NAT fallback. Deeper DISM/Windows-feature repair remains Administrator-only and outside normal installation.

When the selected registered distro fails its no-op launch probe with `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure` and `.wslconfig` explicitly selects `mirrored`, the helper now handles that condition before DISM or Windows-feature mutation:

1. without `-ApplyNatFallback`, it reports the condition and exits without changing the host;
2. with `-ApplyNatFallback`, it backs up the current `.wslconfig`;
3. it changes only `[wsl2] networkingMode` to `nat`, preserving processor, memory, `[general]`, comments/other unrelated settings as represented by the line-preserving editor;
4. it performs `wsl --shutdown`;
5. it retests the exact same registered distro with `true`;
6. if launch succeeds, it exits successfully; a v14.4.81 installer caller immediately re-runs the complete distro eligibility probe, while a manually invoked helper returns control to the operator;
7. if launch still fails, the backup is retained and broader host diagnostics may continue.

The helper never unregisters, imports, converts, deletes, compacts, mounts, edits, or moves a distro/VHDX. With multiple registered distros it requires an exact `-DistroName`; with exactly one it may auto-select that registration.

#### Preservation and compatibility boundary

This release does not hard-code a Windows user, drive letter, WSL registration name, Linux user, profile name, model/provider, Matrix room, or storage location. The recovery operates on the current Windows user's global `.wslconfig` and an explicitly selected/exactly auto-selected registered distro.

Changing mirrored to NAT can alter networking expectations for other WSL2 workloads because `.wslconfig` is global. That is why the change remains explicit and backed up. v14.4.81 may orchestrate this helper action only from the narrow persistent-E_UNEXPECTED preflight path after separate user approval; ordinary clean/repair/update feature configuration still does not silently change networking mode.

#### Validation contract

Release regression coverage must prove:

- normal installer source has no mirrored-networking writer/fallback;
- normal modes can observe a healthy externally configured mirrored topology without claiming ownership;
- shared native-Ollama/Tailscale installer-owned policy records a non-mirrored topology;
- `E_UNEXPECTED` + mirrored is tested before DISM in the explicit helper;
- NAT recovery is opt-in, backed up, bounded, and retests the same registration;
- no distro registration/VHDX destructive operation exists in the helper;
- historical fixtures continue to describe historical behavior without reintroducing it into the current release branch.

#### Primary-source basis reviewed

- Microsoft Learn: WSL networking and `.wslconfig` configuration.
- microsoft/WSL issue tracker: current Windows 11 build-26200 mirrored-networking and `E_UNEXPECTED` reports.
- microsoft/WSL source/discussions for the independently retained instance-idle lifetime setting.

The issue evidence is used conservatively: it supports removing LatticeVale's dependency on mirrored networking, but `E_UNEXPECTED` is treated as a general host error if the narrow NAT recovery does not solve it.

---

## Archived source: `EXISTING-INSTALL-QC-PATCH-NOTES.md`

### LatticeVale v14.3.39 — Existing-Install Quality Control

> Canonical release entry: `CHANGELOG.md` → `14.3.39` (2026-08-19).

#### Scope

The final v14.3.38 archive was re-audited specifically for all six existing managed-stack installer choices: Resume / repair, Change installed components, Verify installation only, Reconfigure providers/profiles, Advanced recovery, and Update / repair installer-managed software.

The menu routing, saved-option reuse, scoped-change behavior, checkpoint controls, provider/profile force flags, Matrix recovery backup ordering, controlled-update backup ordering, persistent-data retention, and verify-only early exit were found structurally consistent.

#### Defect found and corrected

Every mutating existing-stack mode enables preservation-first repair maintenance. That maintenance previously ran `docker image prune -f` and `docker builder prune` against the selected distro's Docker Engine. Docker Engine scope is broader than the LatticeVale Compose project, so an unrelated Docker project sharing that distro could lose dangling images or old BuildKit cache.

v14.3.39 removes both automatic global prune operations. Repair still:

- reports Docker disk usage with `docker system df`;
- clears bounded APT cache and stale LatticeVale staging directories;
- prunes only installer configuration snapshots whose LatticeVale ownership marker/name pattern is proven;
- caps installer event-log history;
- performs bounded PostgreSQL `VACUUM (ANALYZE)` maintenance;
- preserves Matrix/Postgres data, Hermes profile/session/memory state, QMD data, Ollama models, vault/workspace files, credentials, user backups, and unrelated Docker state.

Administrators who intentionally want Docker Engine-wide cleanup can perform it themselves after reviewing all workloads on that Engine. LatticeVale no longer performs such cleanup implicitly.

#### No unrelated behavioral changes

No menu option, component pin, Matrix identity flow, profile behavior, Kanban policy, WSL networking policy, Tailscale mapping behavior, checkpoint revision, or update/repair pin logic was changed by this QC patch.

---

## Archived source: `KANBAN-SKILL-POLICY-PATCH-NOTES.md`

### LatticeVale v14.3.38 — Kanban / Skill Policy Reliability

> Canonical release entry: `CHANGELOG.md` → `14.3.38` (2026-08-19). This file retains detailed implementation/audit context.

#### Why this patch exists

Live Hermes diagnostics showed two separate model-facing failure classes while the underlying services remained functional:

- ordinary gateway turns could see Kanban tools and call worker-scoped lifecycle operations without a real `HERMES_KANBAN_TASK`, or pass the shell-variable name literally;
- `skill_manage` could receive an invalid human-readable name, malformed/unclosed YAML frontmatter, an over-budget description, or a patch before the current `SKILL.md` had been loaded, and some models repeated the same rejected call until Hermes' normal tool-loop hard stop fired.

A subsequent end-to-end Kanban test also demonstrated that the core shared board, dispatcher locking, dependency graph, triage/decomposition, cross-profile workers, completion flow, and durable attachments work. v14.3.38 therefore **does not replace or simplify that machinery**.

#### Kanban policy

LatticeVale generates `latticevale-kanban-policy` v1.2.0 for installer-managed gateway profiles when Kanban is enabled. It uses Hermes `pre_tool_call` behavior conservatively:

- an unbound root `kanban_create` with a valid installed assignee is shallow-modified to `triage=true`;
- a literal `HERMES_KANBAN_TASK` task-id argument is shallow-replaced only when a real worker binding exists;
- missing/invented assignees are blocked with the discovered real profile roster;
- worker-only lifecycle operations require an actual bound worker task and cannot target a different task;
- task-scoped reads/comments from normal sessions require an explicit real task id;
- worker-created child cards are not recursively forced back through root triage.

The managed SOUL policy additionally tells agents to avoid duplicate cards, respect dependencies/concurrency/review flow, use durable task results/attachments after completion, and return substantive task results when that is what the user requested.

#### Profile portability / ownership

The installer discovers every real Hermes profile directory with a readable `config.yaml` for **routing validation**. LatticeVale still edits only:

- the default Hermes configuration it manages; and
- profile names recorded in `.installer-managed-profiles`.

A valid user-created profile may remain `orchestrator_profile` or `default_assignee` without becoming installer-owned. If a saved default assignee is stale, LatticeVale prefers another managed profile; otherwise it falls back to the valid orchestrator rather than conscripting an arbitrary external profile. No username, WSL distro name, Windows drive, model identifier, Matrix room, or secondary-profile name is hard-coded by this policy.

#### Skill authoring / recovery

Managed profiles receive an installer-owned SOUL block that instructs agents to:

- normalize human-readable names to valid skill slugs;
- generate a complete closed YAML frontmatter block;
- keep descriptions within the installed Hermes validation budget;
- use `create`, `patch`, `edit`, and `write_file` for their intended scopes;
- load the current skill with `skill_view` before patching an existing skill;
- read all requested source/input coverage before authoring;
- treat validation errors as corrective data and never repeat an identical rejected call;
- change strategy after two failures instead of weakening tool-loop hard stops;
- verify the resulting skill after a successful write.

Fresh managed profiles receive `skills.write_approval: false` only when the setting is absent. Existing explicit booleans are preserved during repair/update/reconfigure. With automatic decomposition/dispatch enabled, Kanban cards can cause workers to execute the tools available to their assigned profiles; the context guard is not a sandbox for untrusted task content. Users who require an approval boundary for agent-managed skill changes should explicitly enable `skills.write_approval`.

#### Clean and repair adoption

The `integrations` checkpoint revision advances to 2. Clean installs execute the policy normally. Existing managed stacks whose older integrations checkpoint is already complete re-run the stage on their next mutating LatticeVale operation, including Resume / repair, Change components, Reconfigure providers/profiles, Advanced recovery, and Update / repair. The migration does not require a component software refresh and does not delete existing Kanban cards or persistent skill data.

---

## Archived source: `UPDATE-REPAIR-PATCH-NOTES.md`

### LatticeVale v14.3.37 — Controlled Update / Repair

This release makes update behavior explicit and separates three operations that older documentation could blur together.

#### Resume / repair

Resume / repair remains preservation-first and local-first between refresh windows. It **may update installer-managed software** when the normal managed-refresh interval is due, when an older install has no refresh marker, or when LatticeVale changes the managed-refresh policy revision. It does not broadly upgrade unrelated Ubuntu packages.

#### Update / repair installer-managed software

A new existing-stack installer choice forces the current bundle's managed software refresh immediately. The mode:

- reuses saved component/profile choices;
- requires a successful `manage.sh backup` before refresh;
- bypasses the periodic age gate for that run;
- refreshes targeted Ubuntu prerequisites and the managed Docker package set;
- reconciles/pulls the component references declared by the bundle;
- rebuilds QMD and Honcho when selected;
- advances the audited Honcho source only when the checkout is proven installer-owned;
- preserves explicit custom image/source overrides where ownership is not proven;
- preserves application databases, identities, profiles, credentials, model data, vault/workspace files, and normal persistent state;
- does not install or update separately owned native Windows Ollama;
- finishes by running the normal staged repair/live verification path.

If the update is interrupted after the refresh marker is created, a later Resume / repair continues the pending managed refresh.

#### What “update” means

The controlled updater aligns an installation with **this LatticeVale bundle's declared references**, not arbitrary internet `latest` versions. A newer fixed Hermes or Synapse tag is adopted when a newer LatticeVale bundle declares it. Floating major/channel references may resolve to a newer digest within the configured reference when pulled.

`./manage.sh update` remains available as a separate advanced upstream-refresh workflow. It pulls the current configured references and may advance Honcho to repository `HEAD`; it should not be confused with the reproducible Windows installer update mode.

#### v14.3.38 integration-policy migration

The controlled software updater remains a v14.3.37 feature, but v14.3.38 also advances the **integrations checkpoint revision**. Therefore the Kanban/skill policy update does **not** require choosing the forced software updater: a normal mutating Resume / repair will re-run the integrations stage once after adopting v14.3.38. Change components, Reconfigure, Advanced recovery, and Update / repair also receive the same current policy. Fresh installs receive it during their first integrations stage. The migration preserves explicit skill-write approval and does not rewrite user-owned profile configs.

---

## Archived source: `MATRIX-RESILIENCE-PATCH-NOTES.md`

### LatticeVale v14.3.35–v14.3.36 detailed Matrix-resilience notes

> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `PATCH-NOTES.md` without removing these guarantees.

> Canonical release entries: `CHANGELOG.md` → `14.3.35` and `14.3.36` (2026-08-19). This file retains detailed implementation/audit context.


This compatibility patch corrects resumable Matrix state handling for both clean installation and Resume / repair.

The initial Matrix-resilience work is downstream `14.3.35`; the installer-transaction/lifecycle-gate and pending-room-verification follow-up is downstream `14.3.36`.

#### Corrected stage semantics

- A secondary/profile Matrix account whose identity, token, encrypted room, runtime environment, and Matrix authentication have been provisioned successfully may remain `pending-manual` when Hermes-side invite acceptance or recovery-key persistence is temporarily unavailable.
- `matrix_profiles` now treats that protected pending state as a valid provisioning result instead of warning that repair will continue and then immediately failing its own verifier.
- Pending secondary profiles force the relevant checkpoint back through retry logic on Resume / repair.
- Completed profile provisioning no longer depends on the profile gateway being live at the exact instant the resource-provisioning verifier runs. Runtime gateway health remains visible and is retried by lifecycle/state-audit paths.
- `matrix-profile-finish` is now explicitly allowed during the installer transaction before the final `.configured` marker exists. Previously the installer called this recovery command during clean install/repair while `manage.sh` rejected it with `The stack has not finished configuration.`
- A `pending-manual` bot is no longer required to query live Matrix room-version metadata before it has joined its invite. The protected installer room-version marker remains mandatory while pending; after activation reaches `complete`, the live room-version lookup is strict again.

#### Exact profile gateway activation fallback

- LatticeVale still uses Hermes' normal named-profile gateway lifecycle command first.
- If that command fails while the exact profile-specific s6 service slot is proven to exist, LatticeVale falls back only to `/run/service/gateway-<profile>`.
- A stopped exact slot is activated with `s6-svc -U`, allowing a stale profile-specific persistent-down marker to be cleared without restarting or killing another profile/default gateway.
- Missing or ambiguous exact service slots fail safely; there is no profile-blind process kill/restart fallback.

#### Cross-signing / E2EE persistence

- Secondary profile cross-signing now has explicit `pending` and `complete` state so a preserved but unfinished recovery-key transaction does not contradict its stage verifier.
- Resume / repair retries pending secondary cross-signing checkpoints.
- A preserved legacy default Matrix identity may remain in the installer's existing `.matrix-cross-signing-pending` state without blocking unrelated repair work. Fresh installer-managed default identities remain strict and must complete recovery-key persistence.

#### Reporting

- Secondary Matrix handoff records now persist `Status: pending-manual` when activation is actually pending.
- Final summaries and state audit distinguish a protected/configured pending profile from a fully running profile.
- Normal stack start retries pending profile activation but does not make one secondary profile prevent the core stack from starting.

No Matrix identity, token, room, device, or crypto store is rotated merely because a retryable activation/cross-signing step is pending.

---

## Archived source: `COMPATIBILITY-PORT-RECLAIM-PATCH-NOTES.md`

### LatticeVale v14.3.34 detailed compatibility + stale bridge-port notes

> **v14.3.41 networking supersession note:** The compatibility/port-reclaim behavior remains, but the historical mirrored-fallback wording below no longer describes current networking ownership. v14.3.41 normal installer flows do not create or switch global mirrored mode.


> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.34` (2026-08-19). This file retains detailed implementation/audit context.


This patch is built on the functional-WSL-preflight and network-safety patches.

#### Supported envelope

The bundle intentionally remains limited to the combinations its application/container stack validates end-to-end:

- Windows 10/11 client, build 19041 or newer.
- x64/AMD64 Windows.
- An existing, working WSL2 distribution whose `/etc/os-release` identifies Ubuntu 22.04, 24.04, or 26.04 and whose package architecture is amd64.
- Windows PowerShell 5.1 or PowerShell 7 for the installer; relay tasks self-test available PowerShell engines before registration.

Unsupported operating systems, WSL1, non-Ubuntu distributions, and unverified CPU/image architectures fail before the stack is mutated rather than being guessed compatible.

#### Compatibility hardening

- Successful `wsl.exe` enumeration/version probes now parse STDOUT only. STDERR remains diagnostic, preventing WSL update/startup notices from becoming phantom distro names.
- Optional Windows WSL feature-state metadata stays advisory; actual WSL2 version and distro-launch probes decide usability.
- The WSL host-repair helper no longer defaults to `Ubuntu-24.04`. It auto-selects only when exactly one distro is registered, otherwise it requires `-DistroName` explicitly.
- WSL registry `BasePath` normalization preserves extended volume-GUID paths instead of corrupting them by stripping `\\?\` unconditionally.
- Storage resolution prefers `Get-Volume -FilePath` when available, allowing local fixed volumes mounted through a directory/volume GUID as well as ordinary drive letters; older systems retain the Win32_LogicalDisk fallback.
- Existing NAT/mirrored networking policy remains capability-first: working NAT is preserved, existing mirrored mode is supported, and switching to mirrored stays explicit and transactional.

#### Stale LatticeVale Windows bridge ports

Older/repaired installs could leave the current Windows-native relay running while a new install selected bridge ports. The running LatticeVale listener made its own canonical port appear foreign, producing warnings such as:

- `Dashboard Windows bridge port 19119 is unavailable. Using 19120 instead.`
- `Matrix Windows bridge port 18008 is unavailable. Using 18009 instead.`

The installer now:

1. proves current relay ownership from the exact scheduled-task script AND config paths;
2. stops that verified task before bridge-port allocation;
3. removes only orphaned PowerShell relay processes whose command lines contain both exact installer-owned paths;
4. waits for verified old ports to release;
5. tries canonical `19119` and `18008` first again;
6. uses a prior/alternate port only if the canonical port is still genuinely unavailable.

No process is killed merely because it owns a TCP port. Same-name tasks that cannot be proven LatticeVale-owned are preserved, and unknown listeners still force a safe alternate port.

---

## Archived source: `FUNCTIONAL-WSL-PREFLIGHT-PATCH-NOTES.md`

### LatticeVale v14.3.33 detailed functional-WSL-preflight notes

> **v14.3.41 networking supersession note:** The v14.3.33 functional-preflight behavior remains, but its statement that mirrored networking remains an installer fallback is historical. Current v14.3.41 normal installer flows never write or switch global `networkingMode`; only an already-working host/user mirrored configuration may be consumed.


> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.33` (2026-08-19). This file retains detailed implementation/audit context.


This patch fixes a false-negative WSL prerequisite check introduced by the downstream audit patch.

- `Microsoft-Windows-Subsystem-Linux=Disabled` is no longer fatal by itself. Modern Store/MSI WSL2 may be usable while the legacy/inbox WSL1 component is disabled.
- `VirtualMachinePlatform` feature state is retained as diagnostic context, but functional WSL2/distro probes decide whether installation can continue.
- The installer now detects modern WSL, enumerates registered distros with bounded probes, verifies WSL2, and actually launches the selected Ubuntu distro before treating WSL as usable.
- The host repair helper now tests the existing distro before DISM or feature mutation. If the distro already launches, it exits without changing Windows.
- On modern Store/MSI WSL, the helper will not automatically enable the legacy/inbox WSL1 optional component merely because it reports Disabled.
- Existing preservation guarantees remain: no unregister/import/move/VHDX mutation.

This patch is intentionally compatible with the preceding network-safety patch: NAT remains preferred when it works, mirrored networking remains an explicit fallback, and no global WSL restart occurs merely because native Ollama plus Tailscale were selected.

---

## Archived source: `NETWORK-SAFETY-PATCH-NOTES.md`

### LatticeVale v14.3.32 detailed WSL networking-safety notes

> **v14.3.41 supersession note:** v14.3.41 preserves capability-first relay discovery but removes the explicit mirrored fallback described below. Normal installer flows no longer write `networkingMode`; already-working mirrored mode is external/user-owned. The remainder of this file is retained as historical v14.3.32 implementation context.

> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.32` (2026-08-19). This file retains detailed implementation/audit context.


This patch changes the v14.3.30 shared native-Windows-Ollama + Windows-Tailscale policy from mode-first to capability-first.

- A verified NAT/private-relay path is preserved. Selecting both features no longer proactively changes `%USERPROFILE%\.wslconfig`.
- Mirrored networking remains supported when it is already active.
- If the current topology cannot verify the native-Ollama bridge, mirrored mode can still be offered as an explicit fallback, but the prompt defaults to **No**.
- Only accepting that fallback can write `networkingMode=mirrored` and invoke global `wsl --shutdown`. The existing backup/verification/rollback transaction remains in place.
- The Windows Tailscale relay continues to use `127.0.0.1` in mirrored mode and dynamically refreshed WSL IPv4 in NAT mode.
- Runtime policy auditing now accepts either verified NAT or mirrored as the canonical shared topology.

This patch does not unregister, import, move, mount, compact, or edit the distro VHDX.

---

## Archived source: `AUDIT-PATCH-NOTES.md`

### LatticeVale v14.3.31 detailed audit / WSL-host notes (patch 1 lineage)

#### v14.3.43 clean-host audit finding

A real v14.3.42 dry run proved the scheduled-task audit path could fail on non-Exec action objects. v14.3.43 makes property collection action-type-safe while preserving conservative ownership matching.

> **v14.3.41 supersession note:** The explicit repair helper now checks the exact `E_UNEXPECTED` + mirrored condition before DISM and can perform the backed-up NAT recovery first. Normal installer flows no longer create mirrored mode.

> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.31` (2026-08-19). This file retains detailed implementation/audit context.


This audit lineage began as a modified downstream build of the supplied LatticeVale v14.3.30 stability-backport package. It is now incorporated as downstream release `14.3.31`; the supplied v14.3.30 tree remains the compatibility baseline and version-aware regression fixtures preserve its intended behavior branches where appropriate. The modifications in this lineage are limited to WSL host preflight, diagnostics, an explicit repair helper, tests, and documentation.

#### Why this patch exists

The supplied host audit showed a split state:

- Store/MSI WSL 2.7.12.0 was installed and the WSL, Hyper-V Host Compute, Host Network, and Hyper-V Host services were running.
- `VirtualMachinePlatform`, `HypervisorPlatform`, and Hyper-V were enabled.
- `Microsoft-Windows-Subsystem-Linux` was disabled.
- `Ubuntu-24.04` remained registered as WSL2 and its `G:\WSL\Ubuntu-24.04\ext4.vhdx` existed on a healthy NTFS volume.
- Direct distro probes (`cat /etc/os-release`, `uname`, and `true`) all failed with `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure`.
- DISM reported the Windows component store as repairable and the audit detected a pending file rename/reboot indicator.
- `%USERPROFILE%\.wslconfig` selected `networkingMode=mirrored`.

The original audit patch treated the Windows Subsystem for Linux optional-component state as a hard prerequisite. That was too strict for modern Store/MSI WSL2 and is superseded by `PATCH-NOTES.md`: feature state is now diagnostic, while bounded WSL CLI, WSL2-version, and actual distro-launch probes are authoritative. Virtual Machine Platform remains relevant to WSL2, and Microsoft documents DISM `/RestoreHealth` for a repairable Windows image. The microsoft/WSL issue tracker shows that `E_UNEXPECTED` is not single-cause, including reports on current Windows 11 builds, while mirrored-networking regressions are tracked separately. Therefore the repair path does not assume one setting is the sole root cause.

#### Changes

1. `LatticeVale-Core/Install-LatticeVale.ps1`
   - Records `Microsoft-Windows-Subsystem-Linux` as diagnostic context; the later functional-preflight patch no longer treats Disabled as fatal when modern WSL2 actually works.
   - Retains the existing `VirtualMachinePlatform` check, but moves it into the same host-prerequisite gate.
   - Stops with a precise message pointing to the explicit repair helper when either required Windows feature is disabled.
   - Recognizes `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure` as a host-WSL launch failure and reports `WSL_HOST_E_UNEXPECTED` rather than treating it as an ordinary distro-content failure.
   - Does not enable Windows features, run DISM, unregister/import/move a distro, or touch a VHDX.

2. `tools/Repair-LatticeVale-WslHost.ps1`
   - Must be run explicitly as Administrator.
   - Runs Microsoft DISM `RestoreHealth` by default because the supplied audit reported a repairable component store. Use `-SkipComponentStoreRepair` on subsequent validation runs.
   - Enables `Microsoft-Windows-Subsystem-Linux` and `VirtualMachinePlatform` only when needed, using `-NoRestart`.
   - Stops and requests a Windows restart when a feature changed or Windows already reports a pending reboot.
   - Tests the existing `Ubuntu-24.04` with the read-only/no-op Linux command `true`.
   - If `E_UNEXPECTED` persists, tries one `wsl --shutdown` recovery cycle.
   - If the error still persists and `.wslconfig` uses mirrored networking, it offers a separate `-ApplyNatFallback` path. That path backs up `.wslconfig`, changes only `[wsl2] networkingMode` to `nat`, preserves the other settings, shuts WSL down, and retests.
   - Never unregisters, imports, converts, deletes, mounts, compacts, or moves a distro/VHDX.

3. Regression coverage
   - Extends the WSL preflight decision fixture with the missing WSL optional-feature state.
   - Adds `v14.3.30-audit-wsl-host-preflight-fixtures.py` to verify the new preflight, explicit-helper boundary, E_UNEXPECTED classification, NAT backup path, and VHDX-preservation invariants.
   - Updates PowerShell source-count fixtures for the new readable helper.

4. Reconciles four stale validation assertions already failing in the supplied custom-backport ZIP
   - The untouched supplied tree failed its own `static-audit.py` because several tests still expected pre-backport command/text shapes.
   - The runtime source was already consistent with the top-of-changelog custom-backport description: adaptive resource refresh in `manage.sh start`, non-fatal/retryable secondary Matrix activation in v14.3.30, automatic Kanban policy wording, and the quoted Matrix finisher invocation.
   - This patch updates those assertions to the shipped/documented v14.3.30 backport behavior. It does not change those four runtime behaviors.


#### Validation performed on the patched source tree

- `LatticeVale-Core/tests/static-audit.py`: PASS (the untouched supplied ZIP failed this audit before the stale assertions were reconciled).
- WSL preflight, distro diagnostic, stderr isolation, WSL network discovery, mirrored fallback, v14.3.30 shared-network policy, cold-start backport, and new audit-host fixtures: PASS.
- Runtime-variable safety and PowerShell ASCII/source-encoding fixtures: PASS.
- Release-candidate portability and public-customization fixtures: PASS.
- All shipped Bash runtime scripts: `bash -n` PASS.
- Every Python source file: AST parse PASS.
- `compose.yaml`: YAML parse PASS with 12 expected services.
- The final release manifest is regenerated after all edits and the ZIP is verified for exact manifest coverage before delivery.

Note: this Linux-based review environment cannot execute Windows PowerShell/WSL against the user's actual Windows host. The patch is therefore source/regression validated, while the final host-level proof is the helper's `wsl.exe -d Ubuntu-24.04 -u root -- true` probe on the audited PC after any required restart.

#### Recommended order on the audited machine

From an elevated PowerShell window in the extracted patched folder:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName Ubuntu-24.04
```

If it reports a restart requirement, restart Windows. Then run the same command again with `-SkipComponentStoreRepair`.

If it reports that `E_UNEXPECTED` persists under mirrored networking, use the reversible compatibility fallback it prints, or run:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName Ubuntu-24.04 -SkipComponentStoreRepair -ApplyNatFallback
```

Only after the helper reports a passing WSL launch probe should `installer/install.ps1` be rerun.

#### Microsoft / primary-source references reviewed

- Microsoft Learn, WSL manual installation: `https://learn.microsoft.com/windows/wsl/install-manual`
- Microsoft Learn, WSL troubleshooting: `https://learn.microsoft.com/windows/wsl/troubleshooting`
- Microsoft Learn, WSL install: `https://learn.microsoft.com/windows/wsl/install`
- Microsoft Learn, repair a Windows image / DISM guidance: `https://learn.microsoft.com/windows-hardware/manufacture/desktop/repair-a-windows-image`
- microsoft/WSL releases (2.7.12): `https://github.com/microsoft/WSL/releases`
- microsoft/WSL issue tracker examples covering `E_UNEXPECTED`, current Windows 11 build regressions, and mirrored-networking compatibility reports. These are troubleshooting evidence only; v14.4.81 does not treat any one report as proof of a universal root cause.

These issue reports demonstrate that `E_UNEXPECTED` is generic and can survive basic feature toggles; they are not treated as proof that the audited machine has the same underlying defect.

---
