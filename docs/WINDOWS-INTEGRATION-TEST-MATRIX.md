> **v14.5.1 resource-policy/OOM case:** on a full selected stack with ~9.7-10 GiB WSL-visible RAM and adaptive limits enabled, verify policy v9 gives Hermes >=1024 MiB, Honcho API >=512 MiB, and CPU-backed managed Ollama >=4608 MiB provisionally before model-aware sizing while aggregate generated ceilings remain <= the managed budget. Seed/observe Docker `OOMKilled=true` on a running selected container and verify `./manage.sh audit`, `verify`, and `repair --plan` no longer report the runtime as healthy/no-repair. Existing policy-v4 state must refresh through normal Resume / repair/start reconciliation without changing global WSL memory settings or user `compose.override.yaml`. For repair-path coverage, leave a pre-existing Hermes container at the v14.5.0 544 MiB limit while v9 desired files are present; the installer must not accept the checkpoint until Docker `HostConfig.Memory`/`HostConfig.NanoCpus` are reconciled to the generated/effective v9 values.

> **v14.5.0 WSL-native planner boundary:** verify `./manage.sh plan`, `repair --plan`, and `audit-free` run entirely inside the selected WSL distro, do not require a persistent Windows helper, and do not modify `install-options.json`, `.env`, `.installer-state.json`, `compose.override.yaml`, Matrix credentials, Docker volumes, or profiles. Confirm actual repair still requires the Windows installer.

> **v14.4.85 WSL lifecycle cases:** verify the shipped Shutdown launcher never target-terminates a distro. From an older installed helper that does contain targeted termination, choose Resume / repair and verify bounded global WSL shutdown + WslService reset/re-probe, then confirm the rewritten helper stops only the stack. Confirm other running distros require explicit global-shutdown consent and no distro/VHDX/HNS/vmcompute mutation occurs.

> **v14.4.83 runtime-policy / Redis-Valkey / Ubuntu-Pro-removal cases:** with a normal full-stack adaptive allocation near 10 GiB WSL RAM, verify policy v4 gives managed Ollama at least 4096 MiB when the aggregate budget permits while total generated limits remain within the existing container budget. Verify policy-v3 state is stale and converges during Resume / repair/start. With SearXNG or Honcho selected, verify `/etc/sysctl.d/99-latticevale-redis-valkey.conf` exists, is root-owned/mode 0644, and effective `vm.overcommit_memory=1` is reported healthy by audit. Verify fresh/change/repair questionnaires contain no Ubuntu Pro option, new `install-options.json` has no `ubuntuPro` key, and an externally installed Ubuntu Pro package/state is neither uninstalled nor modified. Verify completion commands target both selected distro and selected Linux user.

# Windows / WSL integration test matrix

> **v14.4.82 helper exit-code case:** reproduce a successful bounded WSL recovery where the child helper prints diagnostics and exits `0`. Verify the operator still sees those diagnostics, the wrapper returns one scalar integer `0` rather than an array of text plus `0`, and the installer immediately prints `Rechecking Ubuntu WSL2 eligibility after host recovery`. Confirm the recovered distro then follows the unchanged clean-vs-managed-repair storage rules.

> **v14.4.85 shortcut contract:** verify Start and Shut Down use direct WSL `--cd <stack> -- ./manage.sh start|stop`, return exit 0, and contain no nested `$manageCommand` / `bash -lc` launcher.
> **v14.4.85 repair/update precondition:** use **Shut Down LatticeVale** to stop the managed stack, but leave the selected WSL distro running. Do not use targeted `wsl --terminate`. For a legacy installer-owned helper, verify the repair run itself performs the bounded `wsl --shutdown` + `WslService` transport reset/re-probe before shortcut replacement.
> **v14.4.81 WSL launch-recovery cases:** on live Windows/Store-WSL, verify a registered selected Ubuntu distro that returns `Wsl/Service/E_UNEXPECTED` receives bounded same-run recovery. With no unrelated running distros, clean `wsl --shutdown` + retry may proceed automatically and successful launch must trigger a full eligibility re-probe. With another distro running, decline/accept the explicit shutdown confirmation and verify no configuration changes on decline. Also fixture/live-simulate failure of `wsl --list --running --quiet`; verify the installer treats running state as unknown and asks before global shutdown rather than assuming no other distro is active. For persistent E_UNEXPECTED with explicit `networkingMode=mirrored`, verify the separate NAT prompt is default-No, `.wslconfig` is backed up, only the networking-mode value changes, and the same distro is retested. Verify persistent E_UNEXPECTED without mirrored mode performs no network edit and no automatic DISM/feature repair. Verify an explicitly requested broken `-DistroName` gets recovery even when another distro is healthy. After successful recovery, confirm an existing managed stack with free space above the managed-repair floor is evaluated for Resume / repair, while a genuinely fresh install below the fresh reserve remains storage-blocked. Never unregister/recreate the distro or alter its VHDX during these cases.

> **v14.4.8 maintenance web/browser cases (inheriting v14.4.7 extraction):** with SearXNG selected and no explicit extraction provider or browser selection, verify default and installer-managed profiles retain `web.search_backend: searxng`, gain `web.extract_backend: latticevale-local`, load the `latticevale-web-extract` provider, select Hermes Local Browser / Chromium, and use `auxiliary.web_extract.timeout: 360`. Verify private/loopback extraction targets are rejected. Repeat with explicit Firecrawl/Tavily/Exa/Parallel/custom extraction and with explicit Browserbase/Browser Use/Camofox/CDP/gateway/custom browser selections and explicit timeouts; confirm LatticeVale preserves them. Resume / repair from an older integrations checkpoint must advance to revision 4 and adopt only missing installer-owned defaults without forcing managed package/image refresh. For live search testing, distinguish a transport/provider failure from a successful JSON response with zero results caused by upstream engine CAPTCHA/429/suspension; an isolated zero-result response must not be counted as proof of a broken local installation. The known-URL `web_extract` test remains independent and should still succeed for an ordinary public text page.
> **v14.4.6 resource-fingerprint/update-trigger cases:** configure/fixture a WSL-visible processor count lower than the host logical-CPU count (for example WSL=4, host/Python `os.cpu_count()`=8). Generate policy v3 with `CPUS=4`, verify `./manage.sh audit` remains `runtimePolicy CONFIGURED`, and verify a real WSL CPU or RAM allocation change still marks it stale. Also verify 14.4.5-style refresh state at revision 2 remains local-first across the 14.4.6 version-only bump, while 14.4.2-style revision-1 state triggers the required bounded managed refresh and policy-v2→v3 migration.
> **v14.4.5 repair/runtime-policy cases (inherited):** with adaptive limits enabled, verify a clean install writes the current policy; a repair from stale/missing policy regenerates it even when `prepare_config` is already complete; changed overlays force Compose reconciliation before success; and `manage.sh restart` reconciles a freshly regenerated policy before restarting. v14.4.6 supersedes the temporary version-only managed-refresh trigger; v14.4.8 retains that behavior and the inherited v14.4.6 refresh fixtures remain authoritative. `compose.override.yaml` must remain last. Inherited v14.4.4 metadata-race and v14.4.3 uninstall-preservation cases remain required.
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
- Legacy targeted-termination regression: prove the old helper contains `wsl --terminate <distro>`, run v14.4.85 Resume / repair, verify the bounded host transport reset succeeds, then verify the rewritten shutdown helper contains no targeted termination and normal relay/firewall ownership remains correct.
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

> **v14.5.1 policy-v9 hardware/topology matrix:** test 1/2/4/8/16+ WSL-visible CPUs and multiple RAM/service-selection shapes. CPU quotas must scale from `nproc` and live `HostConfig.NanoCpus` must match effective Compose. Full-stack low-RAM shapes that cannot meet defined minima must be rejected rather than proportionally compressed, while lighter service selections must remain valid when their own minima fit.

> **v14.5.1 public option-topology case:** exercise 0-8 additional profiles, Matrix-enabled/disabled profiles, Kanban concurrency 1-8, managed CPU/GPU/native-Windows Ollama, optional Matrix/search/QMD/Honcho selections, adaptive limits enabled/disabled, and Windows/root startup-helper paths. The common default+one-secondary/<=3-worker topology must retain the proven 1024 MiB Hermes baseline; additional persistent Matrix gateways add 192 MiB each beyond the first and Kanban slots above 3 add 96 MiB each, capped at a 4096 MiB Hermes topology floor. The startup helper must evaluate current CPU/RAM/topology when it runs, not embed install-time values.
