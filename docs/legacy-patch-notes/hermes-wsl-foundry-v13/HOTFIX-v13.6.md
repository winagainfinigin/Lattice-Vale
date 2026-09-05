> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Docker Stack v13.6 hotfix

Fixes interactive Hermes provider/profile setup when the Windows installer invokes the Linux bootstrap through `wsl.exe`.

The bootstrap now runs `configure-stack.sh` through `runuser --pty`, creating a Linux pseudoterminal for the unprivileged Ubuntu user. This preserves the upstream Hermes `docker run -it ... setup` / `docker exec -it ... setup` behavior instead of disabling TTY allocation.

Recovery remains idempotent: profiles already created before an interruption are reused, and provider/model setup runs only when their model configuration is still incomplete.
