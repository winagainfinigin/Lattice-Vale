> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13 release notes

## v13.16.6 — post-install integration reconciliation

v13.16.6 folds the post-install issues found during live use back into both **Fresh** and **Resume / repair**. Matrix-enabled default profiles now explicitly enable reaction controls and sender-scoped approval reactions (`MATRIX_REACTIONS=true`, `MATRIX_APPROVAL_REQUIRE_SENDER=true`) so supported Element approval prompts can expose clickable reaction actions without hand-editing runtime environment files.

Kanban-enabled installs now receive an installer-owned automatic-orchestration policy while preserving all SOUL content outside the marked Foundry block. Substantive work can route through native Kanban automatically, while simple requests stay direct. The default dispatcher is deliberately conservative after observed provider 429 exhaustion: 2 workers globally, 1 per profile, one auto-decomposition per tick, and a 30-second dispatcher interval. Clean/reconfigure can choose different worker caps; repair preserves saved valid caps and upgrades older installs to these defaults.

Windows Obsidian integration no longer tells native Windows Obsidian to open `\\wsl.localhost\...` as a vault. Foundry uses a Windows-local drive vault (auto-reusing one registered local Obsidian vault when unambiguous, otherwise the Windows Documents folder default), resolves its WSL `/mnt/<drive>/...` path, mounts that folder into Hermes/QMD as `/vault`, and non-destructively copies legacy stack-vault files into it without overwriting Windows-side files. The legacy WSL vault remains preserved as fallback data. Repair also detaches a legacy host-level mount at the exact Foundry vault target and backs up `/etc/fstab` before removing only matching bind entries, preventing earlier manual bind-mount guidance from conflicting with the new Compose mount.

QMD's built-in indexer now defaults to every 2 hours (7200 seconds). Repair migrates only the former Foundry 6-hour default, preserves deliberate custom intervals, and removes only the exact legacy `HERMES_QMD_REINDEX` crontab line previously recommended by Foundry so duplicate reindex loops are avoided.

All v13.16.1-v13.16.5 safety fixes remain in force: independent profile gateways, bounded Matrix recycle, advisory cross-signing log confirmation, non-fatal optional recovery-key handling, hidden Windows relay, and supported WSL service-instance lifetime.

## v13.16.5 — hidden Windows relay + WSL persistence reconciliation

v13.16.5 prevents the installer-owned Windows-native Tailscale relay from leaving a visible long-running PowerShell console by adding `-WindowStyle Hidden` to the scheduled relay process. Closing an unrelated terminal is therefore no longer capable of accidentally killing the relay simply because its console was visible.

When Tailscale Dashboard or Matrix exposure is selected, clean/reconfigure and Resume / repair runs also force the supported WSL `[general] instanceIdleTimeout=-1` service-instance lifetime policy even if an older saved install recorded `keepWslServicesRunning=false`. No polling loop, `sleep infinity`, or fake keepalive process is introduced.

## v13.16.4 — Matrix integration-stage false-failure fix

v13.16.4 fixes a shell-status regression shared by Fresh and Resume / repair installs. `apply_matrix_runtime_env` no longer returns failure merely because its last optional Matrix value is absent, and the one-time `MATRIX_RECOVERY_KEY_OUTPUT_FILE` setting is no longer copied back into Hermes runtime configuration after cross-signing bootstrap. Required Matrix settings remain enforced by the existing integration verifier. No Matrix identity, crypto state, credentials, room, profile, memory, session, or database data is recreated or deleted.

## v13.16.3 — simplified Matrix cross-signing completion

v13.16.3 keeps the bounded Hermes recycle from v13.16.2 but makes the final cross-signing confirmation tolerant again. The exact upstream `Matrix: cross-signing verified via recovery key` log line is no longer a fatal success criterion for either Fresh or Resume / repair installs. Once the retained recovery key is applied, one-time recovery-key output state is cleaned up, and Hermes restarts and becomes command-ready, Foundry checks briefly for the confirmation log. If it is missing or delayed, the installer reports a warning and continues. Matrix identity, crypto state, access token, room, and recovery material are preserved.


## v13.16.1 — profile gateway isolation hardening

v13.16.1 preserves the complete v13.16.0 clean/repair behavior and adds a deterministic
standalone-gateway invariant for every installer-managed Hermes profile. Foundry now
normalizes `gateway.multiplex_profiles` off in YAML, removes the container-wide
`GATEWAY_MULTIPLEX_PROFILES` opt-in, sanitizes clones, verifies the setting during
integration repair, and surfaces accidental multiplex enablement as a repair condition.
This is a Foundry-side mitigation for unresolved upstream multi-profile multiplexer bugs;
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
part of automatic cleanup. Foundry does not use `docker system prune`, `docker image prune
-a`, `docker volume prune`, broad container/network pruning, `VACUUM FULL`, Matrix/media
purges, or automatic WSL VHD compaction/sparse conversion.

All twelve Compose services now use Docker's bounded `local` logging driver with `20m`
max-size and five files, preventing new container logs from growing without limit. Repair
configuration snapshots also skip an already-pathological installer log tree rather than
duplicating it before cleanup. The state audit now reports logical WSL storage pressure
without misrepresenting that value as the physical Windows `ext4.vhdx` footprint.

## v13.15.0 — Matrix owner verification + standard Tailscale HTTPS

v13.15.0 keeps the user's normal launcher responsible for starting WSL/Hermes and does not add an artificial keepalive process. The optional WSL `[general] instanceIdleTimeout=-1` service-instance lifetime policy remains separate from startup, and full stack Windows-logon auto-start still defaults to No.

Private Matrix remote access remains on **Tailscale Serve** rather than Funnel, but the installer default moves from HTTPS 8448 to standard HTTPS 443. New installs therefore advertise `https://<node>.<tailnet>.ts.net` to Element/Element X. Resume / repair migrates only the old Foundry-owned 8448 default; custom ports remain custom. Dashboard stays on 9443.

The Windows-native relay is now registered at Windows logon whenever Tailscale exposure is selected, even when the stack itself is on-demand. This does not recreate stack auto-start: without explicit `autoStart`, the relay only binds the Windows localhost ports and waits. It checks the cached WSL target directly first, does not issue in-distro discovery commands while WSL is stopped, and reconnects after the user's launcher starts Hermes.

Fresh Matrix installs now retain Hermes's generated cross-signing recovery key. Foundry uses `MATRIX_RECOVERY_KEY_OUTPUT_FILE` for one-time `0600` output, stores the key as `MATRIX_RECOVERY_KEY`, removes the one-time file/setting, restarts Hermes, and verifies the `Matrix: cross-signing verified via recovery key` startup result. This complements the existing encrypted-room creation, required E2EE mode and stable `HERMES_FOUNDRY_BOT` device ID.

Repair preserves the existing Matrix account, room, token, device, crypto store and Synapse data. A legacy identity that already bootstrapped cross-signing but did not retain its recovery key is not destructively reset and no longer blocks unrelated Windows/Tailscale reconciliation.

# Hermes WSL Docker Stack v13 — Resilient Recovery Release

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

v13.13.4 fixes a deterministic parser failure caught by the v13.13.3 relay self-test. `Hermes-WslNativeRelay.ps1` logged errors with expandable strings containing `$DistroName:`. PowerShell treats an unbraced variable followed immediately by `:` as a scoped/provider-style variable reference, so both PowerShell 7 and Windows PowerShell 5.1 rejected the relay before it could run. The relay now uses `${DistroName}:` and regression coverage scans both shipped PowerShell entrypoints for the complete variable-before-colon bug class. This affects both fresh installs and Resume/repair runs.

## v13.13.3 — relay Scheduled Task engine/context hardening

v13.13.3 fixes a v13.13.2 run where the parent installer successfully resolved and verified the WSL NAT IPv4 but the persistent relay Scheduled Task exited immediately with `LastTaskResult=1` before the relay wrote its first startup line. Foundry now prefers PowerShell 7 (`pwsh.exe`) for the relay when available, matching the live-tested Windows relay configuration, and falls back to Windows PowerShell 5.1 only after the exact script/config passes a bounded self-test. The relay task runs as the interactive Windows identity at Highest run level and receives an explicit working directory.

The exact failed relay script/config is retained after a failed attempt (the dead task is still unregistered), so diagnostics inspect the current failed artifact instead of a stale manual relay. The self-test validates the relay configuration, listener availability, inline C# compilation, and seeded/reachable WSL backend before Task Scheduler is asked to keep the process alive.

## v13.13.2 — relay IP discovery and Matrix rollback hardening

v13.13.2 fixes a relay task failure observed after v13.13.1 had already completed the Linux stack and every Windows-local service probe. Foundry now resolves and directly verifies the WSL NAT IPv4 in the parent installer, seeds that address into the Windows-native relay, and lets the relay open its listeners from that proven address before it needs to invoke WSL itself. Later refresh uses both `eth0` and `hostname -I` plus compatible WSL command forms.

The persistent relay no longer requests an administrator runtime token, and relay logs are rotated at each reconciliation so stale troubleshooting output cannot be mistaken for the current failure. Matrix `public_baseurl` reconciliation is now idempotent and skips Synapse restart when the value is already correct; actual changes use a longer bounded readiness check.

## v13.13.1 — native relay startup stall hotfix

v13.13.1 fixes the installer appearing to freeze at `Creating Windows-native WSL relay for Tailscale` after the Linux stack and all Windows-local service checks had already succeeded. The v13.13.0 relay helper invoked the full installer-owned stack recovery helper before checking whether the WSL backends were already reachable; that fallback is allowed up to 900 seconds. The parent installer simultaneously waited up to 900 seconds without progress output.

The relay now probes the current WSL backend endpoints first for up to 15 seconds and invokes stack recovery only if that direct check fails. Installer-side relay verification is bounded to 120 seconds, prints a heartbeat every 10 seconds, exits early when the Scheduled Task terminates unexpectedly, and reports its `LastTaskResult` plus relay-log tail. Resume/repair also waits for a prior installer-owned relay task to stop before replacing its script/config, preventing stale relay mutex/listener races. Persistent logon-time recovery behavior remains intact.

The Hermes `SyntaxWarning` about `venv\Scripts` seen immediately before the Windows stage is an upstream Python warning emitted during Kanban initialization; it is not the source of this stall.

## v13.13.0 — native Tailscale relay + Matrix clean-install hardening

The final Windows troubleshooting pass proved that the Linux stack, WSL NAT address, Docker service bindings, and Windows-local `netsh portproxy` listeners could all be healthy while the Windows Tailscale daemon still returned HTTP 502 when Serve targeted those portproxy listeners. A normal Windows user-space localhost listener worked through the same Serve path. v13.13.0 therefore replaces portproxy as the runtime bridge with a persistent Windows-native TCP relay and retains portproxy code only for ownership-checked migration cleanup.

v13.13.0 also makes fresh Matrix rooms encrypted from creation, uses a stable Hermes Matrix device ID, negotiates a room version from Synapse's advertised capabilities, pins Synapse to stable `v1.158.0`, and lets Hermes auto-join the encrypted invitation only after its E2EE store initializes. This avoids both the Element "unencrypted room" warning and the known Hermes fresh-E2EE-store/already-joined edge case.

Windows add-on status now trusts live WinGet inventory, and the normal Windows logon startup path retries the stack startup helper rather than requiring a manual stack start after boot.
