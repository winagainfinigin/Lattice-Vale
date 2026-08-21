# LatticeVale v14.4.6 — Adaptive Resource Fingerprint Audit Fix

## Problem

A real v14.4.5 repair correctly generated adaptive RAM/resource policy v3 with `CPUS=4` and `MEM_MIB=9946`, then reconciled the full Compose stack. Immediately afterward, `./manage.sh audit` still reported `runtimePolicy PARTIAL` even though `nproc`, `/proc/meminfo`, and `.latticevale-resource-state` all matched. A normal `./manage.sh restart` did not clear the condition.

## Root cause

The generator, verifier in `configure-stack.sh`, and `manage.sh` refresh path use `nproc`, which reports processors available to the WSL process. `state-audit.py` instead used `os.cpu_count()`. On a Windows host exposing 8 logical CPUs with WSL limited to 4 processors, Python can report 8 while `nproc` and the generated fingerprint correctly report 4. Audit therefore compared two different CPU concepts and falsely declared the policy stale.

## Fix

`state-audit.py` now determines adaptive-policy CPU count in this order:

1. `len(os.sched_getaffinity(0))` — process-visible CPU affinity, matching Linux scheduler availability;
2. `nproc` — the same effective source already used by LatticeVale's generator/manager;
3. `os.cpu_count()` — last-resort fallback only.

RAM comparison remains exact. No tolerance is added because the reproduced failure showed identical live/saved RAM; hiding memory drift would be unnecessary and could mask a real `.wslconfig` allocation change.

## Repair behavior

No new repair stage is required. v14.4.5 already correctly regenerates stale policy v3 and forces affected containers through Compose reconciliation. v14.4.6 corrects only the read-only post-repair audit so it evaluates the generated fingerprint using the same CPU semantics.

## Managed-refresh trigger refinement

v14.4.6 also narrows the automatic component-refresh trigger introduced in v14.4.5. A change in LatticeVale's display/release version alone no longer forces APT refreshes, image pulls, or QMD/Honcho rebuilds. Resume / repair refreshes the managed package/image/source layer only when the 30-day age gate is due, `MANAGED_REPAIR_REFRESH_REVISION` changes, a legacy install has no valid refresh state, or Windows installer Option 6 explicitly forces it. The recorded `INSTALLER_VERSION` remains useful provenance but is not itself a refresh predicate.

This is deliberately compatible with the public v14.4.2 baseline. v14.4.2 uses managed-refresh revision 1 and adaptive resource policy v2; v14.4.6 uses managed-refresh revision 2 and adaptive resource policy v3. Therefore a direct 14.4.2→14.4.6 Resume / repair still performs the bounded managed component refresh and RAM-policy migration required by the cumulative patch set. By contrast, a recently refreshed v14.4.5 install already at revision 2/policy v3 can adopt the 14.4.6 audit fix without rebuilding healthy images solely because the bundle version changed.

Pending refresh markers still record their origin bundle. If their policy revision matches the current revision, repair resumes the pending user-level image/build/source phase without repeating completed root package work; if the revision differs, the bounded root phase is rerun.

## Regression coverage

The v14.4.6 fixture reproduces `os.cpu_count()=8` with process affinity=4 and requires the audit helper to return 4. It also verifies fallback to `nproc` and then `os.cpu_count()` when affinity/nproc are unavailable. Inherited repair/runtime-update and RAM-policy fixtures remain required.
