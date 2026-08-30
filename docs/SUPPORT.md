# Support

## v14.5.1 adaptive CPU/RAM / OOM support note

Current v14.5.1 resource policy v9 derives CPU ceilings from processors actually visible inside WSL, verifies effective Compose `cpus` against Docker `HostConfig.NanoCpus`, and gives CPU-backed managed Ollama a 4608 MiB provisional floor before model artifacts are measurable, then a model/context-aware floor after download after a measured policy-v6 4128 MiB ceiling produced sustained `memory.max` pressure. Effective Compose `mem_limit` is verified against `HostConfig.Memory` in the same pass. If WSL CPU/RAM allocation or Matrix-profile/Kanban topology changes, or policy-v8-or-older state is present, adaptive state becomes stale and is regenerated.

Policy v9 does not promise that every selected component set can run inside every RAM size. It is feature-aware: only enabled services contribute to the minimum, but if that minimum cannot fit inside the post-reserve container budget, LatticeVale fails the adaptive plan with an actionable message instead of generating tiny hard ceilings. Increase WSL-visible RAM, deselect optional components, use native-Windows Ollama where appropriate, or disable adaptive container ceilings.

If `./manage.sh audit`, `verify`, or `repair --plan` reports `runtimePolicy PARTIAL` because a selected running container has Docker `OOMKilled=true`, use the full v14.5.1 release and choose **Resume / repair installation**. Policy v9 intentionally treats policy-v8-or-older resource fingerprints or changed hardware/topology fingerprints as stale and recalculates/reconciles the generated Compose CPU/RAM ceilings without deleting volumes, changing profiles/providers, rotating Matrix identity, or taking ownership of global WSL memory settings. On a normal full ~10 GiB CPU-backed managed-Ollama stack, Hermes should receive at least a 1024 MiB preferred ceiling, Honcho API at least 512 MiB, and Ollama at least 4608 MiB while the aggregate budget remains bounded. User `compose.override.yaml` remains final/authoritative.

## v14.4.82: WSL recovered but installer still says no eligible distro

If the installer prints `WSL launch recovered after wsl --shutdown` and then warns that the bounded helper exited with a long block of helper text ending in `0`, that is the v14.4.81 return-channel bug. Use v14.4.82. The WSL recovery itself succeeded; v14.4.82 keeps the helper output visible but returns only exit code `0`, causing the installer to re-probe the same distro and continue through normal eligibility. For an existing installer-managed stack, the existing 10 GiB Resume / repair free-space floor is then evaluated normally; this hotfix does not lower the 50 GiB true fresh-install reserve.

## v14.4.81 WSL `E_UNEXPECTED` launch recovery

If preflight can enumerate a registered Ubuntu WSL2 distro but launch fails with **`Wsl/Service/E_UNEXPECTED` / `Catastrophic failure`**, do **not** unregister the distro or delete/replace its VHDX. v14.4.81 can handle the safe-first part during the same installer run when that distro is required or explicitly selected:

1. LatticeVale detects other currently running WSL distros. If any would be interrupted, it asks before continuing. If WSL cannot report the running-distro list reliably, LatticeVale also asks before using global `wsl --shutdown`.
2. The bounded helper runs `wsl --shutdown`, waits for WSL to settle, and retests the **same registered distro**.
3. If the same error persists and `%UserProfile%\.wslconfig` explicitly selects `networkingMode=mirrored`, LatticeVale can offer an explicit backed-up switch of **only** that key to `nat`, followed by another shutdown/retry.
4. On success, the installer re-runs the complete distro eligibility check and continues in the same run if all ordinary requirements are satisfied.
5. If bounded recovery fails, normal installation stops without automatically running DISM or changing Windows optional features. Use the printed elevated `tools\Repair-LatticeVale-WslHost.ps1` command only when deeper host repair is intended.

Microsoft documents `wsl --shutdown` as the fast WSL restart path and documents NAT as the default WSL networking mode. `E_UNEXPECTED` is a generic host failure, so the mirrored→NAT action is deliberately conditional rather than treated as a universal fix. Official references: [WSL configuration](https://learn.microsoft.com/windows/wsl/wsl-config) · [WSL troubleshooting](https://learn.microsoft.com/windows/wsl/troubleshooting).

The existing storage policy is unchanged. After WSL responds, a previously managed LatticeVale stack may Resume / repair with **at least 10 GiB free**; a genuinely fresh installation still requires **at least 50 GiB free** on a host partition over 50 GiB total.

## v14.4.8 Hermes web-research troubleshooting

With SearXNG selected, `web_search` should resolve through SearXNG and `web_extract` should resolve through `latticevale-local` unless you deliberately configured another extract-capable/shared provider.

These are separate capabilities:

- `web_search` asks the local SearXNG service to query external search engines.
- `web_extract` reads a known public HTTP(S) URL through LatticeVale's local extractor.
- Browser automation is a separate optional Hermes capability and is not required for ordinary `web_search` + public-page extraction.

A successful `web_search` call can still return **zero results** when SearXNG's upstream engines temporarily rate-limit, CAPTCHA, suspend, or otherwise refuse automated traffic. That can happen even while the SearXNG container, Valkey, JSON search API, Hermes provider configuration, and network path are all healthy. A zero-result response by itself is therefore **not** a reason to run LatticeVale repair.

For a successful search call with no usable results:

1. retry later, especially after engine suspension/rate-limit windows have expired;
2. broaden or simplify an unusually narrow query;
3. inspect SearXNG's `unresponsive_engines` response/logs to distinguish upstream blocking from a local service failure;
4. if the authoritative URL is already known, use `web_extract` directly instead of relying on search discovery.

Investigate the LatticeVale installation when the local SearXNG API itself fails, Hermes cannot resolve/use the configured SearXNG provider, managed profiles lose the expected web configuration, Valkey/SearXNG is unhealthy, or known public URLs consistently cannot be extracted after v14.4.7. Do not try to solve upstream CAPTCHA/429 behavior by repeatedly hammering blocked engines or by treating every empty result set as installation corruption.

For design, migration, and diagnostic expectations see [`PATCH-NOTES.md`](PATCH-NOTES.md).

## Official upstream troubleshooting links

For a managed stack, start in the LatticeVale stack directory with `./manage.sh status`, then `./manage.sh verify`; use `./manage.sh audit` when repair-oriented state is needed. If those checks isolate an upstream component, use that project's official documentation rather than deleting LatticeVale data or Docker volumes.

| Component | LatticeVale use | Official help |
| --- | --- | --- |
| LatticeVale | Installer, lifecycle, repair, and Windows/WSL integration | [Repository](https://github.com/winagainfinigin/Lattice-Vale) · [Issues](https://github.com/winagainfinigin/Lattice-Vale/issues) |
| Hermes Agent | Agent runtime, profiles, tools, browser, and web providers | [Docs](https://hermes-agent.nousresearch.com/docs/) · [FAQ/troubleshooting](https://hermes-agent.nousresearch.com/docs/reference/faq) · [Web search/extract](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search) · [Browser automation](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser/) |
| WSL2 | Windows host for the selected Ubuntu distro | [Microsoft WSL docs](https://learn.microsoft.com/windows/wsl/) · [WSL configuration](https://learn.microsoft.com/windows/wsl/wsl-config) · [WSL troubleshooting](https://learn.microsoft.com/windows/wsl/troubleshooting) |
| Ubuntu | Linux distribution used inside WSL | [Ubuntu Server documentation](https://ubuntu.com/server/docs/) |
| Docker Engine / Compose | Runs the managed Linux services | [Docker Engine](https://docs.docker.com/engine/) · [Compose](https://docs.docker.com/compose/) · [Container logs](https://docs.docker.com/engine/logging/) |
| SearXNG | Free self-hosted Hermes search backend | [Admin docs](https://docs.searxng.org/admin/) · [Search API](https://docs.searxng.org/dev/search_api.html) |
| Valkey | SearXNG cache/state service | [Valkey documentation](https://valkey.io/topics/) |
| Matrix Synapse | Optional Matrix homeserver and Hermes messaging identities | [Synapse documentation](https://element-hq.github.io/synapse/latest/) |
| PostgreSQL | Database used by Synapse and Honcho | [PostgreSQL documentation](https://www.postgresql.org/docs/) |
| pgvector | PostgreSQL vector extension used by the optional Honcho database | [pgvector repository/docs](https://github.com/pgvector/pgvector) |
| Redis | Cache/state service used by optional Honcho | [Redis documentation](https://redis.io/docs/latest/) |
| QMD | Optional local Markdown/Obsidian indexing and retrieval | [QMD repository/docs](https://github.com/tobi/qmd) — `qmd doctor` is the upstream diagnostic command |
| Honcho | Optional self-hosted contextual-memory service | [Honcho repository/docs](https://github.com/plastic-labs/honcho) |
| Ollama | Optional local model runtime, either managed in Linux or integrated with native Windows Ollama | [Ollama docs](https://docs.ollama.com/) · [Troubleshooting](https://docs.ollama.com/troubleshooting) · [Windows](https://docs.ollama.com/windows) |
| Tailscale | Optional Windows-host remote access to selected LatticeVale services | [Troubleshooting](https://tailscale.com/docs/reference/troubleshooting) · [CLI diagnostics](https://tailscale.com/docs/reference/tailscale-cli) |
| Obsidian | Optional Windows-native vault integrated with QMD/Hermes | [Obsidian Help](https://obsidian.md/help/) |
| PowerShell | Windows installer, verification, repair, and relay scripts | [Microsoft PowerShell documentation](https://learn.microsoft.com/powershell/) |
| Playwright / Chromium | Browser runtime underlying the local-browser path in the pinned Hermes environment | [Playwright browser documentation](https://playwright.dev/docs/browsers) · [Hermes browser automation](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser/) |

For the normal free LatticeVale-managed Hermes research path, the intended split is:

```text
Search:      SearXNG
Extraction:  LatticeVale local extraction provider
Browser:     Hermes Local Browser / Chromium
```

Fresh install and Resume / repair fill the local browser choice only when no explicit browser backend/provider, browser gateway route, or recognized Hermes browser environment selection already indicates another selection. They also fill `auxiliary.web_extract.timeout: 360` only when that timeout is missing. Deliberate cloud/custom browser choices and explicit timeout values remain user-owned. This is runtime setup/reconciliation only; LatticeVale does not change `SOUL.md`, prompts, or model policy.

For browser-specific problems, check the managed Hermes profile's `browser` configuration and the Hermes container logs before changing providers. For SearXNG or extraction problems, first distinguish search from extraction: SearXNG is search-only, while `latticevale-local` handles known public HTTP(S) pages.

## Repair-install preparation

v14.4.85 retains the direct WSL `--cd` lifecycle shortcut execution introduced in v14.4.84 for `manage.sh start|stop`; schema-3/broken helpers are repair drift and are rewritten by Resume / repair. Before reproducing or repairing an existing-install problem with **Resume / repair** or **Update / repair**, stop the managed stack with **Shut Down LatticeVale** if available, but do not target-terminate the distro. v14.4.85 repair automatically detects the older installer-owned targeted-termination helper and performs a bounded `wsl --shutdown` + `WslService` transport reset before replacing it.

## v14.4.84 WSL lifecycle support note

If an installation previously used the pre-v14.4.84 **Shut Down LatticeVale** shortcut and later shows `Wsl/Service/E_UNEXPECTED` while the distro still reports `Running`, use the full v14.4.85 release and choose **Resume / repair installation**. The repair recognizes only the exact installer-owned legacy helper containing targeted termination, performs bounded `wsl --shutdown` + `WslService` reset/re-probe, then replaces the shortcut. Do not unregister/recreate the distro or delete its VHDX as a first response.

## v14.4.6 adaptive resource fingerprint support note

If `./manage.sh audit` reports `runtimePolicy PARTIAL` even though `.latticevale-resource-state` matches `nproc` and `/proc/meminfo`, use v14.4.6 or newer. Earlier v14.4.5 audit code could compare the saved WSL CPU fingerprint to `os.cpu_count()`, which may reflect the Windows host logical-CPU count instead of the processor set available to WSL. v14.4.6 aligns audit with the generator/manager CPU semantics. A real CPU or RAM allocation change still marks the policy stale and triggers normal regeneration.

## v14.4.5 repair runtime-policy / update support note

If `./manage.sh audit` reports `runtimePolicy PARTIAL` after an older repair, rerun Resume / repair with v14.4.5 or newer. The installer now treats adaptive policy convergence as an explicit repair step and will not report final success until the selected policy-v3 fingerprint and RAM controls verify. When that overlay changes, affected containers are reconciled through Compose so the settings become live.

v14.4.6 refines the managed-update trigger introduced in v14.4.5: a bundle-version change alone no longer forces package/image/source refresh. Resume / repair refreshes that layer when the 30-day gate is due, the managed-refresh policy revision changes, or valid legacy refresh state is missing. Use explicit **Update / repair installer-managed software** when you intentionally want to force the current bundle's managed refresh immediately. Public 14.4.2→14.4.84 still refreshes because the managed-refresh revision advances from 1 to 2. The v14.4.7 extraction migration and v14.4.8 browser/timeout integration migration do not by themselves force that package/image/source refresh.

## v14.4.4 repair metadata-race support note

Implementation details: `PATCH-NOTES.md`.

Resume / repair no longer fails merely because a live SQLite `*-shm`/`*-wal` sidecar or rotated log disappears during root-assisted ownership reconciliation. Rerun Resume / repair with v14.4.4; the bootstrap tolerates only paths that actually vanished and will still stop on a genuine ownership/permission error for an entry that remains present.

The v14.4.3 RAM-efficiency and uninstaller behavior remains inherited. v14.4.84 historically retained policy v4; the current v14.5.1 resource policy is v9. Its Hermes floor and CPU ceiling adapt to persistent secondary Matrix gateways and high Kanban concurrency, and generated startup helpers probe current resources/topology at runtime. User `compose.override.yaml` remains authoritative, global WSL RAM/reclaim settings remain user-owned, and Docker-unavailable uninstall still fails closed when runtime may remain.

## v14.4.1 layout note

v14.4.1 introduced the `installer/` public-launcher layout with lowercase `install.ps1` / `uninstall.ps1`. v14.4.83 Hotfix 2 made `installer\Install-LatticeVale.ps1` and `installer\Uninstall-LatticeVale.ps1` the canonical documented commands while retaining the lowercase launchers for backward compatibility; `installer\verify-release.ps1` is unchanged. This naming correction does not change runtime stack or repair semantics.

## v14.4.0 stable support note

v14.4.0 is the stable promotion of the v14.3.43 runtime line. Use `FEATURES.md` for the complete current option inventory, `Instructions.txt` for procedures, and the retained v14.3.43 support note below for the Scheduled Task dry-run issue fixed in that runtime line.

## v14.3.43 clean-host dry-run note

If the clean-host reset dry run from v14.3.42 failed on a Scheduled Task action missing `Execute`, use v14.3.43. The failure occurs before destructive WSL removal; rerun the dry run and review every `WOULD:` line before using `-Execute`.

## v14.3.42 clean-host reset support

Use normal `installer/Uninstall-LatticeVale.ps1` for preservation-first removal. Use `tools\Reset-LatticeVale-CleanHost.ps1` only for an intentional fresh WSL/LatticeVale baseline. Always run it without `-Execute` first. `-RemoveWslRuntime` permanently removes every WSL distro registered to the current Windows user; shared Hyper-V/VirtualMachinePlatform, Tailscale, Obsidian and unrelated Windows networking remain outside its ownership boundary.

## v14.3.41 WSL cold-start recovery

This historical helper behavior remains available, but **v14.4.81+ attempts the bounded shutdown/re-probe recovery in the normal installer first**. If that same-run recovery cannot restore WSL, use the printed `tools\Repair-LatticeVale-WslHost.ps1` command from an **elevated** PowerShell window for deeper DISM/Windows-feature repair. Do not unregister the distro or replace its VHDX as an early recovery step.

## v14.3.40 inherited shared-Docker support note

All mutating existing-stack modes retain their prior repair/update semantics, but automatic maintenance no longer prunes Docker Engine-global images/build cache. If Docker disk usage is high, review `docker system df` and reclaim shared Docker state manually only if you intend to affect every project using that Engine.

## v14.3.38 Kanban / skill troubleshooting

Detailed v14.3.38 behavior and ownership boundaries are recorded in `PATCH-NOTES.md`.

On a v14.3.38 clean install or after any mutating repair/update path, the integrations stage should re-apply the managed Kanban/skill policy. `task_id is required` in an ordinary chat usually means a model attempted a worker-scoped operation without a dispatcher claim; do not set a fake task ID or literal `$HERMES_KANBAN_TASK`. A dispatched worker should inherit a real binding and normally omit the task id. Unknown-assignee errors should be resolved against the live profile roster, not by inventing profile names. For completed work, inspect task results/attachments before transient `kanban/workspaces` paths.

For `skill_manage`, validation errors about invalid names, unclosed frontmatter, description budget, or an unloaded current `SKILL.md` are corrective instructions. Normalize the slug, close frontmatter, shorten the description, or call `skill_view` before a patch; repeated identical failures should change strategy rather than increasing the hard-stop threshold. Repair/update preserves an explicit existing `skills.write_approval` choice. If automatic Kanban dispatch or automatic skill writing is enabled, remember that these are real agent capabilities with the profile's available tools, not a sandbox for untrusted task/prompt content.

Use GitHub Issues for reproducible LatticeVale installer, repair, documentation, or compatibility problems. Include the LatticeVale version, Windows/PowerShell version, WSL/Ubuntu version and architecture, install mode, selected relevant features, and sanitized output.

Modified/forked builds are permitted under the MIT license. For an issue involving a customized build, disclose that it is modified and summarize the relevant changes or provide a minimal diff. When practical, reproduce the issue against an unmodified release so maintainers can distinguish an upstream LatticeVale defect from a downstream customization.

Do **not** post passwords, API keys, Matrix access tokens/recovery keys, private backup contents, or other credentials. Security-sensitive reports should follow `docs/SECURITY.md` instead of a public issue.

Questions about Hermes Agent itself, Matrix/Synapse, Tailscale, Docker, Obsidian, QMD, Honcho, Ollama, Ubuntu, or other upstream products may need to be reported to their respective upstream projects when the issue is not caused by LatticeVale integration logic.

For native Windows Ollama/relay reports, include sanitized `native-ollama-relay.log` / `windows-native-service-relay.log` output, the active `wslinfo --networking-mode`, and whether the failure followed WSL restart, sleep/wake, VPN/firewall changes, or an Ollama restart. Do not post tokens or private model prompts.

## Repair versus software update

For an existing installer-managed stack, include which existing-stack action you selected:

- **Resume / repair installation** is preservation-first. It repairs incomplete/stale stages and stale adaptive runtime policy. It performs the bounded installer-owned package/image/source refresh when the periodic refresh window is due, the refresh-policy revision changed, or valid legacy refresh state is missing. A bundle-version change alone remains local-first. It converges only through explicit managed-refresh triggers; it is **not** a blanket move to arbitrary newer upstream releases.
- **Update / repair installer-managed software** is the controlled on-demand force-refresh mode. It requires a successful verified bundle-owned pre-update safety backup first (independent of the installed `manage.sh`), forces the current LatticeVale bundle's declared installer-owned package/image/source refresh immediately, and then runs the normal repair/verifier stages. Use it whenever you want a version-only bundle change to force managed component refresh before the age/revision gate is due.
- **Change installed components** changes feature selections; it is not the dedicated updater.
- `./manage.sh update` is an advanced upstream-refresh workflow and is not equivalent to the bundle-pinned Windows installer updater.

If **Update / repair** refuses to start because the pre-update backup cannot complete, run **Resume / repair installation** first and correct the reported health/backup problem. Do not delete the stack or its databases to get past the safeguard.


For v14.4.4 live repair metadata-race behavior, see `PATCH-NOTES.md`.

### Policy v9 model/timeout diagnostics

For managed Ollama, `.latticevale-resource-state` records `OLLAMA_TEXT_ARTIFACT_MIB`, `OLLAMA_EMBED_ARTIFACT_MIB`, `OLLAMA_CONTEXT_LENGTH`, and `OLLAMA_MODEL_FLOOR_MIB`. A model download or user context change therefore makes the policy fingerprint stale and triggers normal bounded reconciliation. `./manage.sh status` reports cgroup pressure using a two-sample delta: a lifetime `memory.max` count that is not increasing is historical information, while new `memory.max`, `oom`, or `oom_kill` events indicate current pressure. Honcho timeout defaults are LatticeVale-owned only when the corresponding `.latticevale-timeout-auto` sidecar proves ownership; editing the JSON timeout makes it user-owned and it is preserved.
