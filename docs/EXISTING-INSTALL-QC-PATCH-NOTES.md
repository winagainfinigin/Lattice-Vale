# LatticeVale v14.3.39 — Existing-Install Quality Control

> Canonical release entry: `CHANGELOG.md` → `14.3.39` (2026-08-19).

## Scope

The final v14.3.38 archive was re-audited specifically for all six existing managed-stack installer choices: Resume / repair, Change installed components, Verify installation only, Reconfigure providers/profiles, Advanced recovery, and Update / repair installer-managed software.

The menu routing, saved-option reuse, scoped-change behavior, checkpoint controls, provider/profile force flags, Matrix recovery backup ordering, controlled-update backup ordering, persistent-data retention, and verify-only early exit were found structurally consistent.

## Defect found and corrected

Every mutating existing-stack mode enables preservation-first repair maintenance. That maintenance previously ran `docker image prune -f` and `docker builder prune` against the selected distro's Docker Engine. Docker Engine scope is broader than the LatticeVale Compose project, so an unrelated Docker project sharing that distro could lose dangling images or old BuildKit cache.

v14.3.39 removes both automatic global prune operations. Repair still:

- reports Docker disk usage with `docker system df`;
- clears bounded APT cache and stale LatticeVale staging directories;
- prunes only installer configuration snapshots whose LatticeVale ownership marker/name pattern is proven;
- caps installer event-log history;
- performs bounded PostgreSQL `VACUUM (ANALYZE)` maintenance;
- preserves Matrix/Postgres data, Hermes profile/session/memory state, QMD data, Ollama models, vault/workspace files, credentials, user backups, and unrelated Docker state.

Administrators who intentionally want Docker Engine-wide cleanup can perform it themselves after reviewing all workloads on that Engine. LatticeVale no longer performs such cleanup implicitly.

## No unrelated behavioral changes

No menu option, component pin, Matrix identity flow, profile behavior, Kanban policy, WSL networking policy, Tailscale mapping behavior, checkpoint revision, or update/repair pin logic was changed by this QC patch.
