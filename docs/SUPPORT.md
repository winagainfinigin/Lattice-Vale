# Support

## v14.4.7 web search versus extraction

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

For design, migration, and diagnostic expectations see [`WEB-EXTRACTION-PATCH-NOTES.md`](WEB-EXTRACTION-PATCH-NOTES.md).

## Repair-install preparation

Before reproducing or repairing an existing-install problem with **Resume / repair** or **Update / repair**, fully stop the selected LatticeVale WSL distro before launching the Windows installer. If installed, use **Shut Down LatticeVale**; it stops the managed stack and terminates only the selected distro. Global `wsl --shutdown` is not required.

## v14.4.6 adaptive resource fingerprint support note

If `./manage.sh audit` reports `runtimePolicy PARTIAL` even though `.latticevale-resource-state` matches `nproc` and `/proc/meminfo`, use v14.4.6 or newer. Earlier v14.4.5 audit code could compare the saved WSL CPU fingerprint to `os.cpu_count()`, which may reflect the Windows host logical-CPU count instead of the processor set available to WSL. v14.4.6 aligns audit with the generator/manager CPU semantics. A real CPU or RAM allocation change still marks the policy stale and triggers normal regeneration.

## v14.4.5 repair runtime-policy / update support note

If `./manage.sh audit` reports `runtimePolicy PARTIAL` after an older repair, rerun Resume / repair with v14.4.5 or newer. The installer now treats adaptive policy convergence as an explicit repair step and will not report final success until the selected policy-v3 fingerprint and RAM controls verify. When that overlay changes, affected containers are reconciled through Compose so the settings become live.

v14.4.6 refines the managed-update trigger introduced in v14.4.5: a bundle-version change alone no longer forces package/image/source refresh. Resume / repair refreshes that layer when the 30-day gate is due, the managed-refresh policy revision changes, or valid legacy refresh state is missing. Use explicit **Update / repair installer-managed software** when you intentionally want to force the current bundle's managed refresh immediately. Public 14.4.2→14.4.7 still refreshes because the managed-refresh revision advances from 1 to 2; the additional v14.4.7 integrations migration does not itself force that refresh.

## v14.4.4 repair metadata-race support note

Implementation details: `REPAIR-METADATA-RACE-PATCH-NOTES.md`.

Resume / repair no longer fails merely because a live SQLite `*-shm`/`*-wal` sidecar or rotated log disappears during root-assisted ownership reconciliation. Rerun Resume / repair with v14.4.4; the bootstrap tolerates only paths that actually vanished and will still stop on a genuine ownership/permission error for an entry that remains present.

The v14.4.3 RAM-efficiency and uninstaller behavior remains current: adaptive policy v3 is still used, user `compose.override.yaml` remains authoritative, global WSL RAM/reclaim settings remain user-owned, and Docker-unavailable uninstall still fails closed when runtime may remain.

## v14.4.1 layout note

Public commands now use `installer\install.ps1`, `installer\verify-release.ps1`, and `installer\uninstall.ps1`. The runtime stack and repair semantics are inherited from v14.4.0; this patch only reorganizes the extracted release and updates path resolution.

## v14.4.0 stable support note

v14.4.0 is the stable promotion of the v14.3.43 runtime line. Use `FEATURES.md` for the complete current option inventory, `Instructions.txt` for procedures, and the retained v14.3.43 support note below for the Scheduled Task dry-run issue fixed in that runtime line.

## v14.3.43 clean-host dry-run note

If the clean-host reset dry run from v14.3.42 failed on a Scheduled Task action missing `Execute`, use v14.3.43. The failure occurs before destructive WSL removal; rerun the dry run and review every `WOULD:` line before using `-Execute`.

## v14.3.42 clean-host reset support

Use normal `installer/uninstall.ps1` for preservation-first removal. Use `tools\Reset-LatticeVale-CleanHost.ps1` only for an intentional fresh WSL/LatticeVale baseline. Always run it without `-Execute` first. `-RemoveWslRuntime` permanently removes every WSL distro registered to the current Windows user; shared Hyper-V/VirtualMachinePlatform, Tailscale, Obsidian and unrelated Windows networking remain outside its ownership boundary.

## v14.3.41 WSL cold-start recovery

If `wsl` or a selected distro fails with `Catastrophic failure` / `Wsl/Service/E_UNEXPECTED`, do not unregister it as a first step. Run the elevated `tools\Repair-LatticeVale-WslHost.ps1` helper. When mirrored networking is the active global setting, the helper now stops before DISM and offers the narrow backed-up NAT recovery first. After WSL launches again, rerun `installer/install.ps1` and choose **Resume / repair**.

## v14.3.40 inherited shared-Docker support note

All mutating existing-stack modes retain their prior repair/update semantics, but automatic maintenance no longer prunes Docker Engine-global images/build cache. If Docker disk usage is high, review `docker system df` and reclaim shared Docker state manually only if you intend to affect every project using that Engine.

## v14.3.38 Kanban / skill troubleshooting

Detailed v14.3.38 behavior and ownership boundaries are recorded in `KANBAN-SKILL-POLICY-PATCH-NOTES.md`.

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
- **Update / repair installer-managed software** is the controlled on-demand force-refresh mode. It requires a successful managed backup first, forces the current LatticeVale bundle's declared installer-owned package/image/source refresh immediately, and then runs the normal repair/verifier stages. Use it whenever you want a version-only bundle change to force managed component refresh before the age/revision gate is due.
- **Change installed components** changes feature selections; it is not the dedicated updater.
- `./manage.sh update` is an advanced upstream-refresh workflow and is not equivalent to the bundle-pinned Windows installer updater.

If **Update / repair** refuses to start because the pre-update backup cannot complete, run **Resume / repair installation** first and correct the reported health/backup problem. Do not delete the stack or its databases to get past the safeguard.


For v14.4.4 live repair metadata-race behavior, see `REPAIR-METADATA-RACE-PATCH-NOTES.md`.
