> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.12

## Windows Tailscale / WSL2 bridge fix

This release preserves the v13 stack and data layout while changing Windows Tailscale exposure for Dashboard and Matrix.

### Why

Windows Tailscale Serve can return HTTP 502 when it directly proxies a service reached through WSL2 Windows-localhost forwarding. Local Windows access can still work, which makes the failure easy to misdiagnose as a Matrix problem.

### New path

For each selected remote service:

1. the Docker service is bound to the WSL VM interface only when its Tailscale exposure is selected;
2. Foundry discovers the current reachable WSL IPv4;
3. Windows IP Helper is enabled/started when required;
4. an installer-owned `netsh interface portproxy` rule maps a dedicated Windows loopback bridge port to the WSL IPv4/service port;
5. Windows Tailscale Serve proxies to that Windows loopback bridge;
6. a Windows Scheduled Task periodically refreshes the bridge if WSL receives a different NAT IPv4.

Default bridge ports are 19119 for Dashboard and 18008 for Matrix. They are changed automatically if unavailable.

### Existing installations

Rerunning the installer migrates legacy installer-owned direct Serve rules through the normal repair/reconciliation path. Matrix identities, rooms, PostgreSQL data, Hermes profiles, models, notes, Honcho state, and other persistent data are preserved.

If global `.wslconfig` explicitly uses `networkingMode=mirrored`, Foundry offers to back it up and change only that setting to `networkingMode=nat`. Because `.wslconfig` is global to WSL2, the change requires explicit confirmation.

### Matrix identity

Remote access changes only Synapse `public_baseurl`. It does not change `server_name=hermes.local` or Hermes's Docker-internal `MATRIX_HOMESERVER=http://synapse:8008`.
