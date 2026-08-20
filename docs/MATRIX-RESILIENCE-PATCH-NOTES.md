# LatticeVale v14.3.35–v14.3.36 detailed Matrix-resilience notes

> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `KANBAN-SKILL-POLICY-PATCH-NOTES.md` without removing these guarantees.

> Canonical release entries: `CHANGELOG.md` → `14.3.35` and `14.3.36` (2026-08-19). This file retains detailed implementation/audit context.


This compatibility patch corrects resumable Matrix state handling for both clean installation and Resume / repair.

The initial Matrix-resilience work is downstream `14.3.35`; the installer-transaction/lifecycle-gate and pending-room-verification follow-up is downstream `14.3.36`.

## Corrected stage semantics

- A secondary/profile Matrix account whose identity, token, encrypted room, runtime environment, and Matrix authentication have been provisioned successfully may remain `pending-manual` when Hermes-side invite acceptance or recovery-key persistence is temporarily unavailable.
- `matrix_profiles` now treats that protected pending state as a valid provisioning result instead of warning that repair will continue and then immediately failing its own verifier.
- Pending secondary profiles force the relevant checkpoint back through retry logic on Resume / repair.
- Completed profile provisioning no longer depends on the profile gateway being live at the exact instant the resource-provisioning verifier runs. Runtime gateway health remains visible and is retried by lifecycle/state-audit paths.
- `matrix-profile-finish` is now explicitly allowed during the installer transaction before the final `.configured` marker exists. Previously the installer called this recovery command during clean install/repair while `manage.sh` rejected it with `The stack has not finished configuration.`
- A `pending-manual` bot is no longer required to query live Matrix room-version metadata before it has joined its invite. The protected installer room-version marker remains mandatory while pending; after activation reaches `complete`, the live room-version lookup is strict again.

## Exact profile gateway activation fallback

- LatticeVale still uses Hermes' normal named-profile gateway lifecycle command first.
- If that command fails while the exact profile-specific s6 service slot is proven to exist, LatticeVale falls back only to `/run/service/gateway-<profile>`.
- A stopped exact slot is activated with `s6-svc -U`, allowing a stale profile-specific persistent-down marker to be cleared without restarting or killing another profile/default gateway.
- Missing or ambiguous exact service slots fail safely; there is no profile-blind process kill/restart fallback.

## Cross-signing / E2EE persistence

- Secondary profile cross-signing now has explicit `pending` and `complete` state so a preserved but unfinished recovery-key transaction does not contradict its stage verifier.
- Resume / repair retries pending secondary cross-signing checkpoints.
- A preserved legacy default Matrix identity may remain in the installer's existing `.matrix-cross-signing-pending` state without blocking unrelated repair work. Fresh installer-managed default identities remain strict and must complete recovery-key persistence.

## Reporting

- Secondary Matrix handoff records now persist `Status: pending-manual` when activation is actually pending.
- Final summaries and state audit distinguish a protected/configured pending profile from a fully running profile.
- Normal stack start retries pending profile activation but does not make one secondary profile prevent the core stack from starting.

No Matrix identity, token, room, device, or crypto store is rotated merely because a retryable activation/cross-signing step is pending.
