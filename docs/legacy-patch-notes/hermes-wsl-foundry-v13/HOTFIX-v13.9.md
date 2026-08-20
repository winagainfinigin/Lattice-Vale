> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.9 hotfix — clean-install hardening

- Uses the selected Ubuntu account's actual primary UID/GID instead of assuming a same-named group.
- Carries the exact bundle version into installer state/checkpoint fingerprints so every hotfix can revalidate prior stages safely.
- Seals temporary WSL staging directories after Windows finishes copying and before root executes staged content.
- Retains all v13.1-v13.8 recovery, storage, variable-safety, timezone, QMD staging, PTY, and profile-loop fixes.
