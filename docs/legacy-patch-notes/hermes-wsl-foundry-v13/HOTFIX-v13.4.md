> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.4 hotfix

- Trims leading/trailing whitespace from interactive timezone input before validation.
- Blank timezone input continues to use the saved/default timezone.
- Invalid timezone characters now reprompt instead of aborting the installer.
- Retains all v13.1-v13.3 recovery, storage, and runtime-variable safety fixes.
