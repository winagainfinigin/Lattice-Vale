> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.13.3

## Relay Scheduled Task execution-context hotfix

A v13.13.2 repair proved the parent installer could resolve and verify the WSL NAT IPv4, but the newly registered relay Scheduled Task exited immediately with `LastTaskResult=1` before the relay emitted its first startup log line. The post-failure cleanup then deleted that exact relay script/config/task, leaving only an older manual relay file in `%LOCALAPPDATA%\Hermes\Foundry` and making later diagnostics inspect the wrong artifact.

v13.13.3 changes the relay launch path to match the Windows configuration that was proven working during live troubleshooting:

- Prefer `pwsh.exe` (PowerShell 7) when installed.
- Fall back to Windows PowerShell 5.1 only if the exact relay script/config passes a bounded `-SelfTest` under that engine.
- Register the persistent relay task for the same interactive Windows identity at `Highest` run level.
- Set the Scheduled Task working directory explicitly.
- Log the selected PowerShell engine and exact relay task name.
- Add a relay `-SelfTest` mode that validates config, listener availability, C# relay compilation, and the seeded/reachable WSL backend without entering the long-running loop.
- Preserve the exact failed relay script/config after unregistering a dead task so a later audit cannot accidentally select a stale manual relay artifact.

The v13.13.2 parent-side WSL-IP seed, bounded relay verification, fresh-log rotation, and idempotent Synapse rollback remain intact. These changes apply to both clean installs and Resume / repair.
