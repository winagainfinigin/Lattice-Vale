> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.13.0

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

- Replaces the v13.12 `netsh portproxy` runtime bridge with `windows/Hermes-WslNativeRelay.ps1`.
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
- Sets stable bot device ID `MATRIX_DEVICE_ID=HERMES_FOUNDRY_BOT`.
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
