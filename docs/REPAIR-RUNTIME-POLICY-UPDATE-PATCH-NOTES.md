# LatticeVale v14.4.5 — Repair Runtime-Policy and Managed-Update Convergence

> **Current-release note (v14.4.6):** The runtime-policy convergence mechanics below remain current, but v14.4.6 supersedes v14.4.5's bundle-version-only managed-refresh trigger. Current Resume / repair refreshes package/image/source state when the periodic age gate is due, `MANAGED_REPAIR_REFRESH_REVISION` changes, valid legacy refresh state is missing, or Option 6 explicitly forces refresh. `INSTALLER_VERSION` remains marker provenance only.

## Problem observed

A real Resume / repair from v14.4.4 completed successfully while `./manage.sh audit` still reported `runtimePolicy PARTIAL`. The adaptive RAM-policy generator lived inside `stage_prepare_config`, but the existing install already had a completed/current `prepare_config` checkpoint. Repair therefore skipped the action that generated policy v3.

A second issue existed in the startup helper: `manage.sh` still compared the persisted resource-policy version against `2` even though the generator writes policy version `3`.

The repair/update audit also showed that the periodic managed-refresh marker tracked time and refresh-policy revision but did not use the recorded installer bundle version as a refresh trigger. That meant a normal Resume / repair from a newer bundle could remain local-first until the age window elapsed unless the user explicitly chose Update / repair.

## v14.4.5 behavior

- Repair has an explicit, uncheckpointed `repair_runtime_policy` reconciliation step.
- Adaptive policy verification requires policy version 3, current WSL-visible CPU/RAM fingerprint, `compose.latticevale.yaml` participation in `COMPOSE_FILE`, `MALLOC_ARENA_MAX`, selected Synapse cache tuning, and selected managed PostgreSQL `shared_buffers`; Honcho retains `max_connections=200`.
- If the overlay is regenerated, `infrastructure` and `reconcile` are marked pending. This ensures Compose applies changed limits/environment/commands to live containers instead of merely leaving a correct YAML file on disk.
- Final configuration fails rather than marking installer state complete if the adaptive policy is still stale/incomplete.
- `manage.sh` compares against policy version 3.
- v14.4.5 originally treated a different recorded installer bundle version as a managed-refresh trigger. **This specific trigger is superseded by v14.4.6**; current automatic refresh uses the periodic age gate, managed-refresh revision, or missing legacy state.
- Current v14.4.6 behavior is local-first whenever the periodic age gate is fresh and the managed-refresh revision is already current, regardless of a version-only bundle change. Explicit Update / repair still forces the current bundle's managed refresh immediately.
- Interrupted refresh markers record bundle version for provenance. In v14.4.6, a pending refresh resumes without repeating completed root package work when its managed-refresh revision matches; a revision mismatch reruns the bounded root phase. A version-only difference does not force repetition.
- `./manage.sh restart` detects when its adaptive resource refresh regenerated the overlay and runs Compose reconciliation before the requested restart, so changed RAM/environment/command settings cannot remain disk-only.
- Explicit user-owned image/source refs and `compose.override.yaml` remain preserved; the latter remains the last Compose layer.

## Component-update semantics

Resume / repair is not an unrestricted `latest` updater. When its age/revision/legacy-state trigger requires a managed refresh, it converges installer-owned surfaces to the versions/channels/pins declared by that bundle. Named Ubuntu prerequisite/Docker packages are refreshed through APT's targeted install path, selected registry images are pulled through Compose/Docker, QMD/Honcho buildable services are rebuilt with pull enabled, and the Hermes image is pulled when the managed refresh is pending. Unrelated Ubuntu packages and user-owned custom refs are not broadly upgraded.

## Validation

`tests/v14.4.5-repair-runtime-policy-update-fixtures.py` asserts the explicit repair step, final fail-closed gate, live-container reconciliation checkpointing, policy-v3 startup comparison, managed component refresh paths, and user override ordering. Under v14.4.6 it also verifies that the historical version-only trigger is no longer active; `v14.4.6-upgrade-refresh-gating-fixtures.py` covers the current 14.4.2→14.4.6 and 14.4.5→14.4.6 gates. Inherited v14.4.3 RAM/uninstaller and v14.4.4 metadata-race fixtures remain required.
