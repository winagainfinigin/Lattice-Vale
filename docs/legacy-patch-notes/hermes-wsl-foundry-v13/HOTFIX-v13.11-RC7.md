> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.11 RC7

Post-install verifier correction:

- Windows-only Tailscale/add-on/auto-start PARTIAL states no longer force the WSL-side audit to report `NEEDS_REPAIR`.
- `./manage.sh verify` now waits for Linux services that are still `STARTING` even when optional Windows follow-up remains.
- A healthy Linux stack can complete verification with an explicit Windows follow-up warning.
- Windows-side integration state remains authoritative in the PowerShell installer and is not silently marked healthy by WSL.
