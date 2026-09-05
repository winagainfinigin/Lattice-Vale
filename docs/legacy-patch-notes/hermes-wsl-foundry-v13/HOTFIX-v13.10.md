> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.10 release-candidate portability audit

v13.10 is a full clean-install + repair portability pass over the v13.9 bundle.

- Corrects `state-audit.py` so exact v13.x hotfix versions are valid and mismatched option/state versions are reported as outdated.
- Rejects Windows Server, non-amd64 Ubuntu, Docker Desktop WSL integration, active rootless Docker, and unknown/custom injected Docker daemons before the installer modifies Docker packages.
- Requires a Hermes-compatible normal Linux user and verifies its real UID/GID, writable home, and Linux-native home filesystem.
- Makes five Windows-facing localhost ports installer state; fresh installs retain defaults when free and automatically select safe alternatives when occupied.
- Refuses to remove/reuse foreign Docker containers or networks that collide with the fixed Hermes Compose namespace.
- Uses the authoritative Windows identity for scheduled tasks.
- Makes Dashboard and Matrix username validation trim/re-prompt rather than aborting the run.
- Guarantees `tzdata` is present and validates IANA timezone names against installed zoneinfo.
- Uses current Tailscale Serve disable syntax.
- Pins all installer Docker operations to the distro-local `/var/run/docker.sock` so user Docker contexts cannot redirect mutations.
- Stops overwriting Ubuntu's generic `20auto-upgrades`; unattended-update policy uses an installer-owned APT file with conservative legacy cleanup.
- Enables the published Hermes API explicitly, generates/preserves a strong bearer key, keeps host exposure loopback-only, leaves browser CORS disabled by default, and verifies API health during reconciliation.
- Moves default Hermes `API_SERVER_*` configuration from the container-wide environment into `data/hermes/.env`, preserving the existing bearer key during migration so named profile gateways cannot inherit/collide on the default API port.
- Corrects fresh Matrix `public_baseurl` generation to use the selected Matrix host port rather than unrelated configuration input.
- Pins fresh-install Honcho source to audited commit `444897975c95393b0d48024470ece03c025d3aa4`; repairs reuse their existing checkout and `./manage.sh update` remains the explicit opt-in to advance.
- Retains all v13.1-v13.9 recovery, permission, staging, TTY, QMD, Honcho, and exact-checkpoint hardening.

- Declares PowerShell 5.1 as the minimum supported host shell so unsupported PowerShell versions fail before preflight.
- Treats persisted `install-options.json` as untrusted repair state and validates worker names, booleans, model tags, and TCP ports before they can influence paths or Docker commands.
- Rejects symbolic links at Hermes data ownership roots that current Hermes container startup recursively `chown`s, preventing a customized/partial stack from redirecting ownership changes outside the dedicated bind mount.
- Uses JSON + `jq` for existing Docker-network attachment inspection rather than a fragile Go-template newline construct.
- Detects an existing per-user/rootless Docker setup and refuses dual-daemon operation; this stack always targets the rootful local `/var/run/docker.sock` engine it owns.
- After Linux health checks pass, verifies each selected localhost-published service from Windows and warns instead of printing a misleading Windows URL when customized WSL networking prevents localhost forwarding.
- Backs up pre-existing Docker APT source/key files before normalizing an incomplete Docker installation to the official Docker CE repository.
