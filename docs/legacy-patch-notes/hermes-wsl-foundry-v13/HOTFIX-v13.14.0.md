> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.14.0 Hotfix — Clean-Install Lifecycle

## Fixed

- Corrects `/usr/local/sbin/hermes-stack-start` so root invocation always starts the selected user's exact stack directory rather than `/root/hermes-stack`.
- Adds an explicit WSL 2.5.4+ service-instance lifetime option using `[general] instanceIdleTimeout=-1`, preserving and backing up unrelated `.wslconfig` content.
- Validates WSL persistence across a 75-second no-command window after applying the lifetime policy.
- Defaults fresh full-stack Windows-logon auto-start to No.
- Separates relay persistence from stack auto-start: on-demand relay tasks are triggerless/passive; auto-start mode alone receives a logon trigger and WSL/stack recovery permission.
- Makes `./manage.sh start`, `stop`, and `restart` coordinate the Windows relay task when Tailscale exposure is configured.
- Adds clean-install lifecycle regression fixtures, including direct helper generation with `HOME=/root`.

## Unchanged by design

- No Tailscale installation inside WSL.
- No return to `netsh portproxy` as the runtime Tailscale transport.
- Matrix `server_name` remains `hermes.local`.
- Synapse remains pinned to stable `v1.158.0`.
- Hermes Agent is pinned to stable `v2026.8.16` (v0.20.2), released August 16, 2026.
- The installer still requires an existing eligible Ubuntu WSL2 distro and does not create/import/unregister/convert/repair WSL distributions.
