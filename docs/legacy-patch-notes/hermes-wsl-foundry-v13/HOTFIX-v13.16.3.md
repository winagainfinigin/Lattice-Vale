> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.16.3 — Simplified Matrix Cross-Signing Completion

v13.16.3 simplifies the Matrix cross-signing stage for both Fresh and Resume / repair installs.

The installer no longer treats absence of the exact upstream log message `Matrix: cross-signing verified via recovery key` as a fatal error after Hermes has successfully reloaded the retained recovery key. That log is now a short, bounded advisory check.

A successful stage requires the installer-managed recovery key to be persisted into the Hermes runtime environment, the one-time recovery-key output setting/file to be removed, and the Hermes container to recycle and become command-ready. If the explicit upstream confirmation log is absent or delayed, Foundry emits a warning and continues.

This restores the more tolerant behavior of older Foundry releases without deleting Matrix crypto state, rotating the Matrix bot identity, or weakening the existing bounded Hermes restart protection added in v13.16.2.
