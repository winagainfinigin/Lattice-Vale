> **Archived v13 documentation:** retained for repository history only. Current supported documentation is for LatticeVale v14.6.0 under `docs/` and the repository root; this historical text is not current installation or repair guidance.

> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes Foundry v13.16.1 — Profile Gateway Isolation Hardening

v13.16.1 is an additive safety release over v13.16.0. It preserves both clean-install
and Resume / repair workflows and does not change persistent profile, Matrix, database,
model, vault, or workspace data.

## Fix

Hermes Foundry now explicitly uses the upstream default **one gateway process per profile**
model and prevents accidental activation of `gateway.multiplex_profiles` in installer-managed
profiles. This avoids current upstream multiplexer defects involving per-profile credential
scope, Matrix adapter requirement checks, session/state isolation, port-binding inheritance,
and Docker/s6 gateway reconciliation.

Clean installs and repairs both normalize the default and installer-managed profile configs,
strip the container-level `GATEWAY_MULTIPLEX_PROFILES` opt-in, sanitize newly cloned profiles,
and verify/audit that multiplexing is off. A repair run preserves all profile data and only
normalizes this topology setting.

No fake Matrix credentials or in-place patches to the upstream Hermes Python package are used.
That keeps Foundry deterministic and avoids carrying a fragile fork of Hermes internals.

## Validation

- 40/40 deterministic/static Python fixtures pass (the two historical environment-dependent lifecycle simulations remain excluded from the deterministic count).
- Bash syntax passes for bootstrap/configure/manage scripts.
- Python compilation passes for shipped Python helpers/audit code.
- Compose YAML remains valid with the existing 12-service model.
- Existing v13.14 lifecycle, v13.15 Matrix/Tailscale, and v13.16 aged-repair regression suites all remain green.
