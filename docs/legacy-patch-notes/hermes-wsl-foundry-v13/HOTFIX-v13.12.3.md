> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.12.3

Runtime stability hotfix for low-memory WSL/Ollama installations.

- Replaces the unconditional 65,536-token Ollama context with a conservative context selected from memory visible inside WSL (8K on <10 GiB, 16K on <18 GiB, 32K on <34 GiB, otherwise 64K).
- Migrates the old installer-owned 65,536 default on repair while preserving clearly user-overridden context values.
- Limits Ollama to one resident model and one parallel request, with a 30-second keep-alive.
- Temporarily stops existing Hermes/Honcho model consumers during model validation.
- Restarts Ollama immediately before Honcho embedding validation so only the embedding model is resident.
- Keeps the 4-minute embedding safety timeout and unloads the embedding model afterward.
- Raises the parent WSL heartbeat failure threshold so the embedding operation's own bounded timeout gets a chance to finish before the parent treats heavy model loading as a dead WSL VM.
- Preserves the v13.12.2 Windows-only Tailscale/WSL bridge design and all existing persistent data.
