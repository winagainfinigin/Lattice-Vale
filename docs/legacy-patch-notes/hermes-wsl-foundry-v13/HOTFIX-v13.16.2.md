> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.16.2 — Bounded Matrix Cross-Signing Hermes Recycle

v13.16.2 fixes an installer hang that could occur in both clean and Resume / repair installs at `Secure and verify Matrix device cross-signing`, where Compose could remain on `Container hermes-agent Restarting`.

## Fix

The Matrix cross-signing stage no longer calls `docker compose restart hermes`. Both recovery-key bootstrap and recovery-key activation now use a bounded Foundry-owned Hermes recycle: verify Compose ownership, request a graceful stop with a 10-second Docker stop timeout, force-remove only `hermes-agent` if necessary, start the Hermes service cleanly with Compose, and wait a bounded 60 seconds for the Hermes CLI to become ready. Persistent state remains in the existing bind-mounted `./data/hermes`, `./vault`, and `./workspace` paths and is not deleted.

The stage also prints explicit bounded-wait messages so a normal key-generation or verification wait is not mistaken for a frozen installer.

## Scope

The same `stage_matrix_cross_signing` function is used by clean and repair workflows, so the fix applies to both. No Matrix account, access token, room, E2EE crypto database, profile, session, memory, model, database, vault, or workspace data is reset.
