> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.12.1

Quick repair-safety hotfix for the v13.12 Windows Tailscale / WSL-IP bridge migration.

- Keeps the v13.12 Windows-only Tailscale architecture unchanged.
- Existing managed installs still migrate through **Resume / repair installation**.
- If Matrix Tailscale HTTPS verification fails after Synapse `public_baseurl` was changed, the installer now rolls `public_baseurl` back to the local Matrix URL after removing the failed Serve rule.
- No Hermes profiles, Matrix identities/rooms/databases, Honcho data, Ollama models, QMD notes, or other persistent user data are intentionally rebuilt by this hotfix.
