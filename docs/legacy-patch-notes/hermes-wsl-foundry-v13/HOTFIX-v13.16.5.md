> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.16.5 hotfix

This hotfix addresses two related symptoms where Hermes appeared to require an open PowerShell/terminal window to remain available.

1. The long-running Windows-native Tailscale relay scheduled task now starts PowerShell with `-WindowStyle Hidden`. The relay remains a Task Scheduler-managed background process with no user-facing console to close.
2. If Tailscale Dashboard or Matrix exposure is selected, Foundry reconciles old saved installs to WSL's supported `[general] instanceIdleTimeout=-1` policy so the Ubuntu service instance remains running after the launching terminal exits.

The patch does not add a fake keepalive loop or `sleep infinity`, and it does not change persistent Hermes/Matrix data.
