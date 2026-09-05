> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.16.6 hotfix

This release folds the remaining post-v13.16.5 operational fixes into both Fresh and Resume / repair.

## Obsidian / QMD

- Windows Obsidian uses a Windows-native vault instead of the WSL UNC stack path.
- If Obsidian has exactly one registered local vault, repair reuses it. Otherwise the default is the current Windows Documents known folder plus `Obsidian Vault`, so redirected Documents folders are respected.
- Foundry translates the Windows vault with `wslpath` and mounts it directly into Hermes/QMD as `/vault` through Compose.
- Legacy `~/hermes-stack/vault` files are copied non-destructively into the Windows vault during repair; existing Windows files are never overwritten and the legacy source is preserved.
- Repair detaches only an old host-level mount at the exact `~/hermes-stack/vault` target and backs up `/etc/fstab` before removing matching `bind` entries, so earlier manual bind-mount guidance cannot conflict with the direct Compose mount.
- QMD built-in indexing now defaults to every 2 hours (7200 seconds), replacing the old 6-hour default.
- The exact legacy `HERMES_QMD_REINDEX` cron entry previously recommended during troubleshooting is removed to prevent duplicate indexing.

## Matrix / Element approvals

- Matrix-enabled installs explicitly set `MATRIX_REACTIONS=true`.
- Approval/model-picker reactions are restricted to the original requester with `MATRIX_APPROVAL_REQUIRE_SENDER=true`.
- Repair reconciles both settings into the existing default profile without rebuilding Matrix identity.

## Kanban / multi-agent

- Kanban configures gateway dispatch, automatic decomposition, creator-session wakeups, and a narrowly managed SOUL policy block so substantive direct-user requests can delegate without special trigger prefixes while simple requests remain direct.
- Default concurrency is 2 workers globally and 1 per profile to reduce provider-rate-limit bursts while still allowing two-profile parallelism.
- Clean/reconfigure can choose different caps; Resume / repair reuses saved caps or migrates older installs to the 2/1 defaults.
- Automatic decomposition is limited to one triage task per tick; dispatcher interval is 30 seconds.

## Preserved earlier fixes

v13.16.1-v13.16.5 behavior remains: standalone per-profile gateways, bounded Matrix recycle, advisory cross-signing confirmation, safe optional recovery-key handling, hidden Windows relay, and supported WSL instance lifetime policy.
