> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.16.4 hotfix

## Matrix integration-stage false failure

Applies to both **Fresh** and **Resume / repair** installs.

The `apply_matrix_runtime_env` helper previously inherited the exit status of its final optional key check. After v13.16.3 removed the one-time `MATRIX_RECOVERY_KEY_OUTPUT_FILE` setting, a healthy Matrix configuration could therefore make the helper return exit code 1 and abort the `integrations` stage even though nothing was broken. Older Matrix identities without a retained recovery key could hit the same class of false failure.

v13.16.4 makes the helper explicitly return success after copying all present runtime values, excludes the one-time recovery-key output variable from runtime propagation, and leaves required-key enforcement to the existing live integration verifier. Persistent Matrix identity and E2EE state are unchanged.
