# LatticeVale 14.4.1 stable promotion / compatibility lineage

## v14.4.1 release-layout patch

v14.4.1 reorganizes release files without changing the validated v14.4.0 stack runtime: public entry points and the exact source manifest move under `installer/`, substantive documentation moves under `docs/`, and conventional Git/GitHub landing/legal files remain at repository root. Launcher path resolution, clean-host release-root recognition, tests, CI, and manifest generation are updated for that layout.

## v14.4.0 stable promotion

v14.4.0 promotes the audited v14.3.43 runtime line to the stable milestone without intended runtime behavior changes. The promotion incorporates the final documentation audit, canonical `FEATURES.md`, release metadata/test compatibility updates, and a regenerated source manifest. The v14.3.43 defensive Scheduled Task action inspection remains the most recent runtime code correction.

This custom release starts from the supplied 14.3.30 bundle. Downstream patch identifiers 14.3.31 through 14.3.43 record this local regression/stability sequence and do not claim equivalence to separately supplied/upstream releases with matching numbers. The stable downstream release is now versioned `14.4.0`. It preserves the v14.3.41 host-safety behavior, adds the explicit clean-host reset boundary, and retains the change that removes the remaining normal-installer ability to create mirrored WSL networking; the explicit host-repair helper retains a reversible NAT recovery path.

Backported behavior:
- Kanban/skill policy migration is capability/profile-roster based, re-applies on clean and repair/update paths, preserves valid user-created routing targets, and does not edit user-owned profile configs.
- Skill-management recovery responds to Hermes validation errors instead of repeating malformed calls; tool-loop hard stops remain enabled.
- scoped existing-install Change mode that begins from saved settings;
- native Windows Ollama GPU/RAM residency warning;
- managed-Ollama repair accepts inactive/blank native relay transport without persisting a fake native transport;
- aggregate adaptive container-memory budgeting across enabled services, with CPU/RAM fingerprinting;
- resource refresh occurs only when limits are enabled and the WSL-visible fingerprint changes;
- secondary Matrix profiles are automatically retried, but a failed optional profile no longer aborts the entire stack start/repair;
- Kanban policy plugin forces model-driven task creation through triage and validates named profiles against the live Hermes profile roster; direct human CLI/dashboard actions remain outside this plugin hook.

The original 14.3.30 relay architecture remains the compatibility baseline. v14.3.32 first made networking capability-first; v14.3.41 further supersedes its mirrored fallback by making global WSL `networkingMode` host/user-owned and non-mutating during normal LatticeVale operation.
## Online compatibility audit (2026-08-19)

- Mirrored WSL networking remains an optimization, not a hard dependency. LatticeVale retains the 14.3.30 NAT/host-discovery and relay fallbacks because upstream WSL continues to have mirrored-networking regressions involving Docker-published ports and loopback connectivity.
- Secondary Matrix activation, per-profile gateway reconciliation, and per-profile cross-signing/recovery-key completion are best-effort across every retry path. Failure of an optional profile must not abort the core stack or destroy its existing identity/room state.
- Adaptive resource refresh now treats a missing/corrupt `.latticevale-resource-state` as stale state and regenerates it instead of risking an early `set -e` exit.
- The Kanban plugin is described as a runtime guard only on Hermes execution surfaces that actually invoke plugin `pre_tool_call`; prompt policy remains the fallback.
- The Hermes image remains pinned to v2026.8.16 for baseline stability. Newer upstream Hermes releases are intentionally not folded into this backport without a separate compatibility pass.


## Online audit follow-up: WSL cold-start preflight

A repair-install failure observed on Store/MSIX WSL 2.7.12 exposed an overly aggressive
preflight assumption: the first read-only distro probe was allowed only the normal 15-second
probe window. Existing server distros may need longer during a cold start while init/systemd
and Docker restore services. The preflight now retries only the idempotent `/etc/os-release`
read with an extended 45-120 second cold-start window before declaring the distro unresponsive.
It does not automatically terminate WSL and does not retry mutating commands.

Host free space below the fresh-install reserve is also reported as DEFERRED while the distro
is unresponsive, because the installer cannot inspect the existing managed stack until Linux
starts. Once responsive, the existing 10 GiB managed-repair exception is evaluated normally.
This avoids presenting a 50 GiB fresh-install requirement as a second root cause for an otherwise
valid repair installation.
