# LatticeVale v14.3.31 detailed audit / WSL-host notes (patch 1 lineage)

## v14.3.43 clean-host audit finding

A real v14.3.42 dry run proved the scheduled-task audit path could fail on non-Exec action objects. v14.3.43 makes property collection action-type-safe while preserving conservative ownership matching.

> **v14.3.41 supersession note:** The explicit repair helper now checks the exact `E_UNEXPECTED` + mirrored condition before DISM and can perform the backed-up NAT recovery first. Normal installer flows no longer create mirrored mode.

> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `KANBAN-SKILL-POLICY-PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.31` (2026-08-19). This file retains detailed implementation/audit context.


This audit lineage began as a modified downstream build of the supplied LatticeVale v14.3.30 stability-backport package. It is now incorporated as downstream release `14.3.31`; the supplied v14.3.30 tree remains the compatibility baseline and version-aware regression fixtures preserve its intended behavior branches where appropriate. The modifications in this lineage are limited to WSL host preflight, diagnostics, an explicit repair helper, tests, and documentation.

## Why this patch exists

The supplied host audit showed a split state:

- Store/MSI WSL 2.7.12.0 was installed and the WSL, Hyper-V Host Compute, Host Network, and Hyper-V Host services were running.
- `VirtualMachinePlatform`, `HypervisorPlatform`, and Hyper-V were enabled.
- `Microsoft-Windows-Subsystem-Linux` was disabled.
- `Ubuntu-24.04` remained registered as WSL2 and its `G:\WSL\Ubuntu-24.04\ext4.vhdx` existed on a healthy NTFS volume.
- Direct distro probes (`cat /etc/os-release`, `uname`, and `true`) all failed with `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure`.
- DISM reported the Windows component store as repairable and the audit detected a pending file rename/reboot indicator.
- `%USERPROFILE%\.wslconfig` selected `networkingMode=mirrored`.

The original audit patch treated the Windows Subsystem for Linux optional-component state as a hard prerequisite. That was too strict for modern Store/MSI WSL2 and is superseded by `FUNCTIONAL-WSL-PREFLIGHT-PATCH-NOTES.md`: feature state is now diagnostic, while bounded WSL CLI, WSL2-version, and actual distro-launch probes are authoritative. Virtual Machine Platform remains relevant to WSL2, and Microsoft documents DISM `/RestoreHealth` for a repairable Windows image. The microsoft/WSL issue tracker also shows that `E_UNEXPECTED` is not single-cause and has occurred with mirrored networking and Windows 11 build regressions. Therefore the repair path does not assume one setting is the sole root cause.

## Changes

1. `LatticeVale-Core/Install-LatticeVale.ps1`
   - Records `Microsoft-Windows-Subsystem-Linux` as diagnostic context; the later functional-preflight patch no longer treats Disabled as fatal when modern WSL2 actually works.
   - Retains the existing `VirtualMachinePlatform` check, but moves it into the same host-prerequisite gate.
   - Stops with a precise message pointing to the explicit repair helper when either required Windows feature is disabled.
   - Recognizes `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure` as a host-WSL launch failure and reports `WSL_HOST_E_UNEXPECTED` rather than treating it as an ordinary distro-content failure.
   - Does not enable Windows features, run DISM, unregister/import/move a distro, or touch a VHDX.

2. `tools/Repair-LatticeVale-WslHost.ps1`
   - Must be run explicitly as Administrator.
   - Runs Microsoft DISM `RestoreHealth` by default because the supplied audit reported a repairable component store. Use `-SkipComponentStoreRepair` on subsequent validation runs.
   - Enables `Microsoft-Windows-Subsystem-Linux` and `VirtualMachinePlatform` only when needed, using `-NoRestart`.
   - Stops and requests a Windows restart when a feature changed or Windows already reports a pending reboot.
   - Tests the existing `Ubuntu-24.04` with the read-only/no-op Linux command `true`.
   - If `E_UNEXPECTED` persists, tries one `wsl --shutdown` recovery cycle.
   - If the error still persists and `.wslconfig` uses mirrored networking, it offers a separate `-ApplyNatFallback` path. That path backs up `.wslconfig`, changes only `[wsl2] networkingMode` to `nat`, preserves the other settings, shuts WSL down, and retests.
   - Never unregisters, imports, converts, deletes, mounts, compacts, or moves a distro/VHDX.

3. Regression coverage
   - Extends the WSL preflight decision fixture with the missing WSL optional-feature state.
   - Adds `v14.3.30-audit-wsl-host-preflight-fixtures.py` to verify the new preflight, explicit-helper boundary, E_UNEXPECTED classification, NAT backup path, and VHDX-preservation invariants.
   - Updates PowerShell source-count fixtures for the new readable helper.

4. Reconciles four stale validation assertions already failing in the supplied custom-backport ZIP
   - The untouched supplied tree failed its own `static-audit.py` because several tests still expected pre-backport command/text shapes.
   - The runtime source was already consistent with the top-of-changelog custom-backport description: adaptive resource refresh in `manage.sh start`, non-fatal/retryable secondary Matrix activation in v14.3.30, automatic Kanban policy wording, and the quoted Matrix finisher invocation.
   - This patch updates those assertions to the shipped/documented v14.3.30 backport behavior. It does not change those four runtime behaviors.


## Validation performed on the patched source tree

- `LatticeVale-Core/tests/static-audit.py`: PASS (the untouched supplied ZIP failed this audit before the stale assertions were reconciled).
- WSL preflight, distro diagnostic, stderr isolation, WSL network discovery, mirrored fallback, v14.3.30 shared-network policy, cold-start backport, and new audit-host fixtures: PASS.
- Runtime-variable safety and PowerShell ASCII/source-encoding fixtures: PASS.
- Release-candidate portability and public-customization fixtures: PASS.
- All shipped Bash runtime scripts: `bash -n` PASS.
- Every Python source file: AST parse PASS.
- `compose.yaml`: YAML parse PASS with 12 expected services.
- The final release manifest is regenerated after all edits and the ZIP is verified for exact manifest coverage before delivery.

Note: this Linux-based review environment cannot execute Windows PowerShell/WSL against the user's actual Windows host. The patch is therefore source/regression validated, while the final host-level proof is the helper's `wsl.exe -d Ubuntu-24.04 -u root -- true` probe on the audited PC after any required restart.

## Recommended order on the audited machine

From an elevated PowerShell window in the extracted patched folder:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName Ubuntu-24.04
```

If it reports a restart requirement, restart Windows. Then run the same command again with `-SkipComponentStoreRepair`.

If it reports that `E_UNEXPECTED` persists under mirrored networking, use the reversible compatibility fallback it prints, or run:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\tools\Repair-LatticeVale-WslHost.ps1 -DistroName Ubuntu-24.04 -SkipComponentStoreRepair -ApplyNatFallback
```

Only after the helper reports a passing WSL launch probe should `install.ps1` be rerun.

## Microsoft / primary-source references reviewed

- Microsoft Learn, WSL manual installation: `https://learn.microsoft.com/windows/wsl/install-manual`
- Microsoft Learn, WSL troubleshooting: `https://learn.microsoft.com/windows/wsl/troubleshooting`
- Microsoft Learn, WSL install: `https://learn.microsoft.com/windows/wsl/install`
- Microsoft Learn, repair a Windows image / DISM guidance: `https://learn.microsoft.com/windows-hardware/manufacture/desktop/repair-a-windows-image`
- microsoft/WSL releases (2.7.12): `https://github.com/microsoft/WSL/releases`
- microsoft/WSL issue tracker examples for `E_UNEXPECTED` / Windows 11 26200 / mirrored networking, including issues `#13454`, `#13714`, `#14193`, and the August 2026 build/update report `#41346`.

These issue reports demonstrate that `E_UNEXPECTED` is generic and can survive basic feature toggles; they are not treated as proof that the audited machine has the same underlying defect.
