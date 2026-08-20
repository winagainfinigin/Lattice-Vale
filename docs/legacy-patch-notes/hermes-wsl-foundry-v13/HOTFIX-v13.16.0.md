> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.16.0 — Comprehensive Repair + Aged-Install Maintenance

v13.16.0 is an additive repair-hardening release. It does not remove any v13.15.0
clean-install capability.

## Added to managed Resume / repair

- Audit logical WSL free space, stack footprint, largest persistent paths and Docker
  storage usage.
- Clear disposable APT cache and stale interrupted Foundry staging before package work.
- Prune Docker dangling images and only unused build cache older than 30 days.
- Retain the eight newest installer-generated pre-version configuration snapshots.
- Bound installer event-history growth.
- Run bounded normal PostgreSQL `VACUUM (ANALYZE)` for Synapse/Honcho when available.
- Re-run these maintenance actions on every managed repair even when ordinary stage
  checkpoints are already complete.
- Report a hard low-space condition after safe cleanup instead of deleting user data.

## Preventive storage hardening

Every installer-managed Compose service now uses Docker's `local` log driver with
`max-size=20m` and `max-file=5`. Repair snapshots avoid duplicating an already oversized
installer-log directory.

## Explicit preservation boundary

Automatic repair does not delete Hermes profiles/memory/sessions, Matrix/Synapse/Postgres
data, Matrix E2EE/crypto state, Honcho memory, QMD data/source notes, Ollama models,
vault/workspace files, credentials or user-created backups. It does not run `docker
system prune`, `docker image prune -a`, `docker volume prune`, broad container/network
pruning, `VACUUM FULL`, or automatic WSL VHD compaction/sparse conversion.
