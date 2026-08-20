> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.13.2

## Problem

v13.13.1 could still finish the entire Linux stack and then fail the persistent Windows-native Tailscale relay with `LastTaskResult=1`. The task's first responsibility was to discover the WSL VM IPv4 itself. Task Scheduler/WSL execution is known to be context-sensitive, and the installer had already proven the Linux services healthy but did not pass their directly reachable WSL address into the relay. Diagnostics could also quote an old `native-relay.log` left by the manual troubleshooting relay.

A relay failure then caused Matrix `public_baseurl` reconciliation to call `docker compose restart synapse` even when the desired localhost URL was already present, producing a second avoidable readiness warning.

## Fix

- Parent installer discovers and verifies the WSL NAT IPv4 before relay task startup.
- The verified IP is seeded into relay configuration and used first.
- Relay IP refresh tries `eth0` plus `hostname -I` and both supported WSL invocation forms.
- Relay task runs as the interactive user without unnecessary elevation.
- Current relay diagnostics use a fresh log; prior log is retained separately.
- Synapse public URL updates are no-op when unchanged; changed URLs receive a 120-second readiness window.

These changes are used by both clean install and Resume/repair.
