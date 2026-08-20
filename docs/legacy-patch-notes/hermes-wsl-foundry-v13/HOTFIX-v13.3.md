> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.3 PowerShell reserved-variable safety hotfix

This hotfix keeps all v13.1/v13.2 recovery changes and leaves the Linux stack/checkpoint schema at v13.

## Changes

- Renames the two remaining installer locals named `$args` to non-automatic names (`$actionArguments` and `$auditArguments`).
- Adds regression coverage that rejects writes to PowerShell automatic/read-only/constant variable names.
- Adds Bash regression coverage for assignments to shell variables reported read-only by the runtime.
- Retains the v13.2 `$HOME`/`$Home` collision fix and v13.1 managed-repair storage exception.
