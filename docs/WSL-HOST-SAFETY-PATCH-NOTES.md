# LatticeVale v14.3.41 detailed WSL host-safety notes

> Canonical release entry: `CHANGELOG.md` -> `14.3.41` (2026-08-19).

## Why this correction exists

Earlier downstream LatticeVale networking compatibility work could explicitly switch the global `%USERPROFILE%\.wslconfig` `[wsl2] networkingMode` to `mirrored` after user consent when native Windows Ollama and/or Windows Tailscale integration could not verify another path. Later releases became NAT/capability-first, but an already configured mirrored value was still preserved and treated as a valid shared topology.

A global `.wslconfig` setting applies to WSL2 at the host level, not to one LatticeVale distro. A topology that appears healthy during an installation can also be exercised differently after a full Windows/WSL restart. Current Microsoft WSL documentation keeps NAT as the default mode and documents other networking modes as host-level configuration. Current microsoft/WSL issue reports also show mirrored-networking regressions on Windows 11 build 26200, including `E_UNEXPECTED`/catastrophic-failure cases. Those reports are evidence for a compatibility risk, not proof that every `E_UNEXPECTED` has the same cause.

The v14.3.41 policy is therefore ownership-based: normal LatticeVale operation does not choose the global WSL networking architecture.

## Normal installer/runtime behavior

`LatticeVale-Core/Install-LatticeVale.ps1` no longer contains a normal-runtime function that writes `[wsl2] networkingMode` or a native-Ollama mirrored-mode fallback. This applies to clean install and every mutating existing-install mode.

- Default/NAT/VirtioProxy-capable networking remains supported with dynamic topology discovery, scoped relays, and exact firewall rules.
- If the user/host already has mirrored mode configured and the distro launches successfully, LatticeVale may consume that working topology without rewriting `.wslconfig`. The saved owner is `user-existing-mirrored`.
- Native Windows Ollama no longer causes LatticeVale to propose a global mirrored switch. If the current topology cannot verify a safe bridge, the remaining choices are the explicit scoped direct-Ollama compatibility path (where supported/accepted) or LatticeVale-managed WSL/Docker Ollama.
- LatticeVale may still manage the separately supported `[general] instanceIdleTimeout=-1` setting when the user selects persistent WSL services. That setting is not a networking-mode choice and is kept separate from this correction.

## Explicit host recovery helper

`tools/Repair-LatticeVale-WslHost.ps1` remains an explicit Administrator-only recovery tool. It is intentionally outside normal installation because a broken WSL host cannot provide the Linux probes required for safe stack repair.

When the selected registered distro fails its no-op launch probe with `Wsl/Service/E_UNEXPECTED` / `Catastrophic failure` and `.wslconfig` explicitly selects `mirrored`, the helper now handles that condition before DISM or Windows-feature mutation:

1. without `-ApplyNatFallback`, it reports the condition and exits without changing the host;
2. with `-ApplyNatFallback`, it backs up the current `.wslconfig`;
3. it changes only `[wsl2] networkingMode` to `nat`, preserving processor, memory, `[general]`, comments/other unrelated settings as represented by the line-preserving editor;
4. it performs `wsl --shutdown`;
5. it retests the exact same registered distro with `true`;
6. if launch succeeds, it stops and tells the operator to rerun LatticeVale;
7. if launch still fails, the backup is retained and broader host diagnostics may continue.

The helper never unregisters, imports, converts, deletes, compacts, mounts, edits, or moves a distro/VHDX. With multiple registered distros it requires an exact `-DistroName`; with exactly one it may auto-select that registration.

## Preservation and compatibility boundary

This release does not hard-code a Windows user, drive letter, WSL registration name, Linux user, profile name, model/provider, Matrix room, or storage location. The recovery operates on the current Windows user's global `.wslconfig` and an explicitly selected/exactly auto-selected registered distro.

Changing mirrored to NAT can alter networking expectations for other WSL2 workloads because `.wslconfig` is global. That is why the change remains explicit, backed up, and confined to the repair helper rather than being silently applied by clean/repair/update installer modes.

## Validation contract

Release regression coverage must prove:

- normal installer source has no mirrored-networking writer/fallback;
- normal modes can observe a healthy externally configured mirrored topology without claiming ownership;
- shared native-Ollama/Tailscale installer-owned policy records a non-mirrored topology;
- `E_UNEXPECTED` + mirrored is tested before DISM in the explicit helper;
- NAT recovery is opt-in, backed up, bounded, and retests the same registration;
- no distro registration/VHDX destructive operation exists in the helper;
- historical fixtures continue to describe historical behavior without reintroducing it into the current release branch.

## Primary-source basis reviewed

- Microsoft Learn: WSL networking and `.wslconfig` configuration.
- microsoft/WSL issue tracker: current Windows 11 build-26200 mirrored-networking and `E_UNEXPECTED` reports.
- microsoft/WSL source/discussions for the independently retained instance-idle lifetime setting.

The issue evidence is used conservatively: it supports removing LatticeVale's dependency on mirrored networking, but `E_UNEXPECTED` is treated as a general host error if the narrow NAT recovery does not solve it.
