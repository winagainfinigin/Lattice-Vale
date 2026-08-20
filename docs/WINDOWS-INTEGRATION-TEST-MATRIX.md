# Windows / WSL integration test matrix
> **v14.4.2 documentation/release consistency patch:** runtime behavior remains unchanged; release validation additionally confirms current version metadata, the `Lattice-Vale` package-root contract, inherited regression compatibility, and exact manifest verification.
> **v14.4.1 release-layout patch:** runtime behavior remains inherited unchanged from v14.4.0/v14.3.43. In addition to the Windows cases below, release validation must confirm the moved `installer/` entry points resolve the parent release root and the complete source manifest verifies after fresh extraction.

> **v14.3.43 clean-host reset cases:** dry run must enumerate only provably owned LatticeVale/explicit legacy Foundry Windows state; `-RemoveWslRuntime` must be required before any distro unregister/WSL-package removal; root-level fixed-drive shortcuts must be ownership-checked; unrelated Tailscale Serve listeners, Hyper-V/VMP/HNS infrastructure, firewall rules, Obsidian and standalone `.hermes` state must survive. After an intentional reset/reboot, reinstall WSL and verify a fresh supported Ubuntu distro boots before beginning a new LatticeVale install.

> **v14.3.41 required WSL host-safety cases:** (1) normal clean/repair/update paths on NAT/default must not modify `[wsl2] networkingMode`; (2) an already-working externally configured mirrored host remains usable without `.wslconfig` mutation; (3) after reproducing/fixture-simulating `E_UNEXPECTED` with mirrored configured, the explicit host-repair path backs up `.wslconfig`, changes only `networkingMode` to NAT, and retests before DISM/feature mutation.

This is a **target-system** checklist. Passing static/fixture tests is not equivalent to executing these rows on Windows. Release notes must identify which rows were actually exercised if they claim live integration coverage.


## Clean-host reset / Scheduled Task compatibility

- Run the reset utility without `-Execute` on a Windows host containing ordinary Exec tasks plus at least one non-Exec/COM-handler Scheduled Task action. Dry run must complete without StrictMode/property errors.
- Confirm LatticeVale/legacy Foundry tasks are reported only when task name/path or available action metadata proves ownership; unrelated non-Exec tasks remain untouched.
- Repeat with `Set-StrictMode -Version Latest` active in the caller to ensure missing action-type-specific properties remain harmless.

## Baseline capture

Record: Windows build, WSL version, selected distro/version, `wslinfo --networking-mode`, Docker version, Ollama version/backend, Tailscale version if used, Windows Firewall profile(s), Hyper-V firewall availability/policy, VPN/endpoint-security presence, and whether systemd is already active inside WSL.

## Native Windows Ollama

For each applicable networking mode (at minimum NAT and mirrored on supported Windows versions):

- Ollama already running: installer detects and verifies without duplicate process/server startup.
- Ollama stopped: installer/Start shortcut launches exactly one normal app/service path and reaches `/api/version`.
- Selected model present and selected model missing: `/api/tags` detection and `/api/pull`/post-pull verification succeed.
- WSL `wsl --terminate <distro>` / later restart: relay observes address changes and recovers without stale firewall ownership.
- Global `wsl --shutdown` / later restart: no stale relay state; Start path recovers.
- Sleep/wake: relay and HTTP path recover or produce actionable logs.
- Ollama quit/relaunch while stack remains up: relay reports target loss and recovers when Ollama returns.
- Docker daemon restart: WSL-local relay re-discovers Docker host-gateway if it changes.
- Relay worker forced exit: supervisor restarts it; if systemd is active, the systemd unit also recovers supervisor failure.
- More than 64 simultaneous relay connections: excess connections are rejected/bounded without runaway process/thread growth.

## Firewall / endpoint security

- Windows Firewall enabled on Private profile.
- Windows Firewall enabled on Public profile.
- Hyper-V firewall present with default policy unchanged; installer-owned exact rules are sufficient.
- Change WSL IPv4 while relay remains alive: old installer-owned rules are replaced with new exact-address rules.
- If AV/EDR blocks PowerShell `Add-Type`, failure is visible/actionable and the installer does not advise disabling security controls.

## Tailscale interaction

- Native Windows Ollama + Tailscale selected together from NAT with a verified private/gateway relay: NAT is preserved and no `.wslconfig` edit or global WSL restart is proposed; the Windows relay uses dynamic WSL-IPv4 targeting.
- Native Windows Ollama + Tailscale selected together from a default/NAT/VirtioProxy-capable topology where the native-Ollama bridge cannot be verified: no mirrored switch is offered; verify the scoped direct-Ollama compatibility path or choose the managed WSL/Docker Ollama backend.
- Native Windows Ollama + Tailscale selected together while externally configured mirrored mode is already healthy: no `.wslconfig` mutation is proposed; the topology is recorded as host/user-owned and the relay may use its mirrored-localhost target.
- Default/NAT retained: the installer-owned policy uses refreshed WSL IPv4/topology discovery rather than proposing a global networking-mode change.
- Externally change `.wslconfig` and restart WSL: after its cached backend fails, the existing Windows relay detects the live mode and switches target policy without spawning a new relay subsystem.
- `manage.sh status` / `verify` with a native-Ollama outage while Tailscale metadata remains present: remote exposure reports degraded dependency state rather than merely "configured".
- Saved shared mode differs from live `wslinfo --networking-mode`: status reports the drift and recommends Windows repair reconciliation.
- Tailscale disabled/not installed when not selected.
- Tailscale selected with native Ollama under NAT.
- Tailscale selected with native Ollama under mirrored networking.
- Tailscale relay target changes after WSL restart/IP churn and recovers.
- `manage.sh stop` / Shutdown shortcut does not leave a bridge claiming healthy service when WSL is intentionally stopped.

## Startup / shutdown

- Start shortcut with native Ollama already running.
- Start shortcut with native Ollama stopped.
- Start shortcut after WSL was terminated.
- Start shortcut after Windows sign-in when auto-start is enabled/disabled as configured.
- Shutdown shortcut stops LatticeVale/selected distro but leaves user-owned native Ollama running.
- Relaunch after shutdown verifies current topology rather than cached addresses.

## Repair / uninstall

- Resume/repair preserves models, Matrix/Honcho data, profiles, and existing user configuration.
- Switching away from WSL-local native Ollama disables/stops its relay without deleting shared WSL configuration.
- Uninstall removes only the installer-owned relay systemd unit/firewall/tasks/config and does not uninstall native Ollama, Docker, Tailscale, or unregister WSL.

## Failure evidence to retain

Sanitize and retain `logs/native-ollama-relay.log`, `%LOCALAPPDATA%\LatticeVale\windows-native-service-relay.log`, relevant scheduled-task result/state, `wslinfo --networking-mode`, WSL IPv4/routes, and exact installer-owned Windows/Hyper-V firewall rules. Do not attach tokens, Matrix secrets, private prompts, or model data.

## Kanban / skill policy migration (v14.3.38)

- Fresh install with Kanban enabled: every LatticeVale-managed profile receives the policy plugin/SOUL block and the shared routing/concurrency values; the board remains usable.
- Resume / repair from an older completed `integrations` checkpoint: revision migration re-applies policy without requiring Update / repair.
- Change components, Reconfigure, Advanced recovery, and Update / repair: current policy is applied consistently.
- Arbitrary profile names: routing is validated against the real on-disk Hermes profile roster; no `assistant`-name assumption is required.
- User-created profile configured as orchestrator: routing remains valid and its config file is byte-for-byte unchanged by the managed integration stage.
- Invalid/stale default assignee: fallback prefers a different LatticeVale-managed profile when available, otherwise the valid orchestrator; an unrelated user-owned profile is not automatically conscripted.
- Ordinary gateway turn: root `kanban_create` is normalized to triage; worker-only complete/block/heartbeat/review/attach operations without a real claim are rejected.
- Dispatcher worker with real `HERMES_KANBAN_TASK`: same-task lifecycle calls still work; a literal placeholder may be shallow-repaired to the real binding; cross-task completion is rejected.
- Completed task with deleted scratch workspace: task result and durable attachment remain the preferred retrieval path.
- Existing `skills.write_approval: true`: repair/update preserves it; a fresh managed profile with no explicit setting receives the automatic-write default.
- Skill validation failure: invalid slug/frontmatter/description/unloaded-skill errors change the next call rather than repeating until the tool-loop hard stop.
