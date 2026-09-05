> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.4 hotfix

- Trims leading/trailing whitespace from interactive timezone input before validation.
- Blank timezone input continues to use the saved/default timezone.
- Invalid timezone characters now reprompt instead of aborting the installer.
- Retains all v13.1-v13.3 recovery, storage, and runtime-variable safety fixes.
