> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.9 hotfix — clean-install hardening

- Uses the selected Ubuntu account's actual primary UID/GID instead of assuming a same-named group.
- Carries the exact bundle version into installer state/checkpoint fingerprints so every hotfix can revalidate prior stages safely.
- Seals temporary WSL staging directories after Windows finishes copying and before root executes staged content.
- Retains all v13.1-v13.8 recovery, storage, variable-safety, timezone, QMD staging, PTY, and profile-loop fixes.
