> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.12.4

Windows Tailscale/WSL bridge reliability hotfix.

- Fixes a repair-path false-success where the Windows bridge helper could exit successfully when `wsl --list --running` did not report the selected distro, leaving `lastWslIp` blank and causing both bridge probes to fail.
- Installer-triggered bridge refresh now explicitly starts/probes the selected WSL distro before discovering its NAT IPv4.
- The installer-owned recurring bridge task uses the same ensure-running behavior because a requested remote Tailscale service requires its WSL backend to be available.
- Bridge refresh is no longer accepted as successful unless a valid non-loopback IPv4 was persisted and every configured Windows loopback bridge port is actually reachable.
- Preserves the v13.12.3 low-memory Ollama policy and all existing stack/data/identity behavior.
