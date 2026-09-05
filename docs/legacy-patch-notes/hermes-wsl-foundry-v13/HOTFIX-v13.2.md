> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.2 PowerShell HOME-collision hotfix

Fixes a Resume / repair crash on Windows PowerShell/PowerShell 7 caused by helper-function parameters named `$Home`. PowerShell variable names are case-insensitive, so `$Home` collides with the built-in read-only `$HOME` automatic variable.

The affected helper parameters are now named `$LinuxHome`. Linux `$HOME` references embedded inside Bash command strings are intentionally unchanged.

This hotfix includes the v13.1 storage-repair changes and does not change Linux stack/checkpoint schema version v13.
