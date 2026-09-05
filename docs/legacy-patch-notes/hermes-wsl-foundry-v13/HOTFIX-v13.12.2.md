> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.12.2

Runtime hang hardening for repair installs:

- Defers any global WSL networkingMode change/restart until all resumable Linux stack stages have completed successfully.
- Uses bounded `wsl --shutdown`, WSL readiness, and post-restart stack-start checks instead of assuming WSL is ready after a fixed two-second sleep.
- If WSL does not recover after a networking change, exits with preserved data and explicit reboot/resume guidance rather than hanging in later Docker/Ollama work.
- Adds hard outer timeouts around Docker image pulls/builds, Ollama model listing/pulling, and Honcho embedding verification.
- Explicitly unloads the embedding model after its compatibility check to reduce WSL memory pressure.
- Adds APT/curl network retries and timeouts for bootstrap downloads.
- Bounds WSL calls inside the scheduled Windows bridge refresher so a temporarily unhealthy WSL service cannot leave the task stuck indefinitely.
- Bounds the installer metadata write into WSL.
- Guards the long interactive WSL bootstrap with periodic bounded WSL health probes; repeated WSL-service failures terminate the current client cleanly with Resume/repair guidance instead of waiting forever.
- Adds finite timeouts to non-interactive Windows Tailscale inspection/configuration and optional Winget installs while leaving genuine Tailscale login/user-interactive setup un-timed.
- Keeps interactive Hermes provider/profile model wizards user-controlled rather than applying arbitrary short prompt timeouts.

No database, profile, model, vault, Matrix identity, or other persistent user data is intentionally removed by this hotfix.
