> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

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

- Replaces the all-in-one `hermes setup` calls with `hermes model` for the default profile and `hermes -p <name> model` for secondary profiles. This keeps provider/model selection interactive while leaving Matrix, browser, search, memory, Dashboard, and other Foundry-managed integrations under installer control.
- Makes terminal messages explicitly identify **DEFAULT** versus **SECONDARY** profile model selection.
- Enables the Hermes `browser` toolset on managed profiles and defaults `browser.engine` to `auto` only when unset. Existing browser provider/backend choices are preserved; fresh installs add no cloud-browser credentials, so the browser source remains local.
- Retains the generated Matrix bot password in owner-only `secrets/matrix-bot.env` on new Matrix identities while continuing to authenticate Hermes with the access token. The password is never copied into the Hermes runtime `.env`.
- Adds `./manage.sh matrix-credentials` for deliberate secret display and improves `matrix-info` with the internal homeserver/user ID.
- Documents the exact answers that previously caused ambiguity: local browser vs Browser Use cloud, first/default vs second/secondary model setup, OpenCode Go selection, Matrix homeserver URL, bot user ID, access token, and bot-password retention behavior.


## RC6 - post-install startup/permission verification

- Treats Docker health `starting` and newly started selected containers as STARTING rather than immediately BROKEN.
- Adds `./manage.sh verify [seconds]` for bounded startup-aware verification (300 seconds by default).
- Adds failure details to the human-readable state audit so permission faults name the affected path.
- Sets SearXNG `FORCE_OWNERSHIP=false` so the upstream entrypoint does not take ownership of Foundry's bind-mounted config.
- Reconciles and verifies installer/user-owned writable roots again after containers have started; PostgreSQL/Ollama container-owned data remains excluded.
- Adds README post-install instructions for verification, dashboard/profile checks, chat tests, and first backup.
