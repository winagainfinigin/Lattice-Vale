> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.1 storage-repair hotfix

This hotfix fixes a preflight deadlock in v13: after a successful partial install consumed Docker/model space, a rerun could fall below the 50 GiB fresh-install free-space reserve and be blocked before the installer had a chance to detect the managed stack and offer Resume / repair.

Policy after this hotfix:
- Fresh/unmanaged installs: unchanged; host partition must be over 50 GiB total and have at least 50 GiB free.
- Existing installer-managed Hermes stack: Resume / repair is allowed with at least 10 GiB host-partition free space.
- The total-partition requirement remains unchanged.
- Below 10 GiB free, repair remains blocked to avoid worsening a critically low-space system.

No Linux stack schema/checkpoint version is changed because this is a Windows preflight-only hotfix.
