> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.15.0 — Matrix Trust + Tailscale Remote Access

## Fixed / changed

- Keeps startup ownership simple: the user's launcher or `./manage.sh start` starts WSL/Hermes. No fake `sleep infinity`, ping/poll keepalive, or hidden full-stack startup is added.
- Retains the supported Store/MSIX WSL 2.5.4+ `[general] instanceIdleTimeout=-1` service-instance lifetime option as a separate policy from startup.
- Changes the Foundry Matrix Tailscale Serve default from HTTPS `8448` to standard HTTPS `443`, producing `https://<node>.<tailnet>.ts.net` for Element/Element X.
- Resume / repair migrates the old installer-owned Matrix default `8448` mapping to `443`; deliberately customized ports are preserved.
- Keeps Matrix private to the Tailscale tailnet. Foundry continues to use **Tailscale Serve**, not public Funnel.
- Registers the Windows-native relay at Windows logon whenever Tailscale exposure is configured so the Serve backend listener is present even before WSL starts.
- Keeps that relay strictly passive unless full stack auto-start was explicitly selected: it does not wake/start WSL, does not run the stack-start helper, and does not keep WSL alive.
- Makes the relay use direct TCP checks against its cached WSL target before spawning any WSL discovery command; when the backend is down it waits for the user's launcher.
- Fresh Matrix installs request Hermes's one-time generated recovery key through `MATRIX_RECOVERY_KEY_OUTPUT_FILE`, capture it into the installer's `0600` secret store, persist it as `MATRIX_RECOVERY_KEY`, delete the one-time file, restart Hermes, and verify owner cross-signing.
- Preserves `MATRIX_E2EE_MODE=required`, stable device ID `HERMES_FOUNDRY_BOT`, encrypted room creation, stable/default room-version negotiation, and `server_name=hermes.local`.
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
