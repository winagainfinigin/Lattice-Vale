# Support

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

- **Resume / repair installation** is preservation-first. It repairs incomplete or stale stages and may perform the targeted managed package/image/source refresh when LatticeVale's periodic refresh window or policy revision requires it. It is **not** a promise to move every component to a newer upstream release on every run.
- **Update / repair installer-managed software** is the controlled on-demand updater. It requires a successful managed backup first, forces the current LatticeVale bundle's declared installer-owned package/image/source refresh immediately, and then runs the normal repair/verifier stages. Use this option after replacing the installer with a newer LatticeVale ZIP when the goal is to adopt that release's tested Hermes, Matrix/Synapse, QMD, Honcho, SearXNG, managed Ollama, Docker-package, or related installer-owned pins.
- **Change installed components** changes feature selections; it is not the dedicated updater.
- `./manage.sh update` is an advanced upstream-refresh workflow and is not equivalent to the bundle-pinned Windows installer updater.

If **Update / repair** refuses to start because the pre-update backup cannot complete, run **Resume / repair installation** first and correct the reported health/backup problem. Do not delete the stack or its databases to get past the safeguard.
