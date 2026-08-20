# Security Policy

## v14.4.1 release-layout security posture

v14.4.1 changes release organization, not runtime privilege/network behavior. `installer/install.ps1`, `installer/uninstall.ps1`, and `installer/verify-release.ps1` resolve the repository root explicitly and continue verifying the complete extracted release tree. Git/GitHub metadata and `LICENSE` remain at repository root; substantive documentation is under `docs/`.

## v14.4.0 stable security posture

v14.4.0 introduces no new runtime privilege, network, secret-handling, or destructive behavior relative to the audited v14.3.43 line. It promotes that runtime unchanged while making the documented prerequisites, automatic skill-write default, and clean-host destructive scope easier to discover.

## v14.3.43 Scheduled Task ownership hardening

The clean-host reset now tolerates heterogeneous Scheduled Task action types without treating missing Exec-only properties as errors. Ownership still requires LatticeVale/explicit legacy Foundry evidence; non-owned tasks are skipped.

## v14.3.42 clean-host destructive boundary

The clean-host reset utility is intentionally separate from normal uninstall and is never invoked automatically. It is dry-run by default, requires Administrator rights plus exact `CLEAN-RESET` confirmation, validates source-tree deletion targets, and removes Windows integrations only when LatticeVale/explicit legacy Foundry ownership can be established. It does not disable shared Hyper-V/HypervisorPlatform/VirtualMachinePlatform/HNS infrastructure or use global Tailscale Serve reset.

## v14.3.41 WSL host-networking boundary

Normal LatticeVale installer flows do not write `[wsl2] networkingMode`. An existing working mirrored configuration is treated as host/user-owned. The explicit WSL host-repair helper may change mirrored to NAT only as a backed-up recovery action after the exact launch-failure condition is detected or the administrator requests `-ApplyNatFallback`; it never unregisters, imports, moves, or edits a distro VHDX.

## v14.3.40 documentation note / inherited shared-Docker boundary

Automatic LatticeVale repair/update does not prune Docker Engine-global dangling images or BuildKit cache. The selected distro may host unrelated Docker projects, so global Docker cleanup is left to an explicit administrator action outside LatticeVale. LatticeVale continues to clean only state whose installer ownership can be proven.

## v14.3.38 Kanban / skill-policy boundary

The `latticevale-kanban-policy` plugin is a **correctness/context guard, not a sandbox or authorization boundary**. It blocks or shallow-repairs predictable model-generated Kanban argument mistakes, but operating-system/container permissions remain the security boundary. LatticeVale keeps Hermes tool-loop hard stops enabled and does not raise retry ceilings to work around invalid `skill_manage` calls. Existing explicit `skills.write_approval` choices are preserved during repair/update. The policy edits only LatticeVale-managed profile configuration; valid user-created profiles may remain routing targets without their config files becoming installer-owned.

When automatic Kanban decomposition/dispatch is enabled, a triage card can fan out into ready work and dispatcher workers can exercise whatever tools their assigned Hermes profile is allowed to use. Treat task titles, bodies, attachments, linked source material, and externally supplied instructions as agent input with real side effects; the v14.3.38 context guard does not make untrusted task content safe. Likewise, `skills.write_approval: false` permits agent-managed skill writes without a separate approval gate. Users who want an approval boundary for skill changes should explicitly enable Hermes skill write approval; LatticeVale preserves that explicit choice on later repair/update runs.

## Supported release

Security fixes are targeted at the current **v14.x** line. Older bundles are useful for historical comparison but should not be treated as the preferred security baseline.

## Reporting a vulnerability

For a public GitHub repository, enable **Private vulnerability reporting** and use GitHub's **Report a vulnerability** flow for sensitive reports. Do not post passwords, Matrix recovery keys, access tokens, Tailscale credentials, API keys, or private logs in a public issue.

If private reporting is not enabled, contact the repository maintainer privately using the contact method published on the repository profile before disclosing exploit details publicly.

## Review-before-run model

LatticeVale is intentionally source-visible:

- no compiled installer executable is required;
- no included Python bytecode is shipped;
- no Base64/encoded PowerShell installer payload is used;
- no `Invoke-Expression` bootstrap is required;
- no `curl | bash` installer entry point is used;
- the main Windows, Linux, Docker, and audit logic is readable in the repository.

Run `installer\verify-release.ps1` to verify every extracted release file except the manifest itself against `installer\SOURCE-SHA256SUMS.txt`. For GitHub releases, separately compare the downloaded ZIP's SHA-256 with the checksum published on the release page. An in-archive manifest detects accidental/extracted-file changes but is not a substitute for an externally published release checksum or code signing.

## PowerShell execution policy

The documented command is:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1
```

This starts a separate Windows PowerShell process whose execution-policy override exists only for that process. It does **not** change the user's or machine's stored execution policy. `Bypass` removes execution-policy blocking/warnings for that child process; it does **not** prove the script is safe. Inspect the source and verify hashes first.

Enterprise Group Policy can still override the process-level policy. Do not weaken domain/organization policy to install LatticeVale without authorization.

## Optional Windows desktop shortcuts

When selected, LatticeVale creates current-user `.lnk` files plus a small JSON config under `%LOCALAPPDATA%\LatticeVale`. The executable logic remains the repository's readable `LatticeVale-Core\windows\LatticeVale-Shortcut.ps1`; no hidden binary launcher is generated.

The shortcut invokes Windows PowerShell with `-ExecutionPolicy Bypass` **for that child process only**. Start is bound to the selected distro/Linux user/stack and ultimately uses `manage.sh start`, so it follows the saved install options. Shut Down checks that the target distro is already running, requests `manage.sh stop`, then uses `wsl.exe --terminate <that-distro>`; it does not use global `wsl --shutdown`.

LatticeVale will update/remove only shortcut files it can prove point to its own helper and the exact generated config. A same-name unowned shortcut is preserved and reported as partial Windows follow-up.

## Privilege boundary

The installer performs privileged system administration by design. Depending on selected features it can:

- run as Windows Administrator;
- invoke WSL as root for distro-level setup/repair;
- install/manage rootful Docker Engine inside the selected Ubuntu WSL distro;
- create/reconcile Docker containers, networks, files, packages, services, and scheduled Windows integration;
- update WSL lifetime configuration when explicitly selected;
- configure Windows-native Tailscale Serve integration when selected.

Do not run it on a machine where you do not trust the reviewed source.

### Modified/downstream builds

The MIT license permits local modifications and forks, but any modification can change LatticeVale's security assumptions. A downstream maintainer is responsible for reviewing new commands, download sources, firewall/network exposure, privilege use, and secret handling introduced by that fork. Clearly identify redistributed customized builds as modified and regenerate their source manifest rather than reusing an official release hash.

## Secrets

LatticeVale stores runtime credentials under the managed WSL stack with restrictive permissions (normally `0600` files inside `0700` secret directories). It avoids printing raw tokens/recovery keys in normal status output.

v14.3.2 secondary Matrix provisioning does **not** keep the human Matrix admin password as a long-lived management credential. A one-time `0600` handoff can exist only while an interrupted clean/resume run still needs to finish profile provisioning; the profile stage removes it on exit. Profile bot tokens/passwords and E2EE recovery material remain persistent because the bots need them across restarts/repairs.

Backups can contain credentials. `./manage.sh backup` prints a reminder after each archive is created. Protect the WSL distro, the Windows account, exported backups, and any copied installer-state archives accordingly; encrypt or otherwise protect backups before copying them to cloud storage or another system. LatticeVale intentionally does not invent its own backup-encryption format or password-management scheme.

## Network exposure

Defaults and intended boundaries include:

- Dashboard and Matrix host ports are loopback/local unless remote exposure is explicitly selected.
- QMD's API remains Docker-network-local.
- Tailscale integration uses the **Windows** Tailscale client and private **Serve**, not public Funnel, for the managed remote-access design.
- Synapse public registration remains disabled.
- Matrix room access is restricted with explicit users/rooms and E2EE where LatticeVale manages the room.
- Named Matrix-enabled Hermes profiles use separate bot credentials rather than sharing the default bot token.
- New secondary profiles are never created with the upstream credential-copying `--clone` path. LatticeVale creates them without messaging credentials, stops the profile gateway, verifies it is not running, and only then copies the safe provider/model/config subset.

Review any manual port, firewall, reverse-proxy, or Tailscale changes made outside LatticeVale separately.

## Optional GPU runtime changes

NVIDIA acceleration can require installing **NVIDIA Container Toolkit** inside the selected WSL distro and allowing `nvidia-ctk` to update Docker runtime configuration. LatticeVale obtains repository metadata/key material only from NVIDIA's documented `nvidia.github.io/libnvidia-container` endpoints, backs up pre-existing repository/key and Docker daemon configuration, verifies the resulting NVIDIA runtime, and restores prior configuration when runtime setup fails. A complete installed toolkit newer than LatticeVale's tested pin is preserved rather than downgraded; inconsistent mixed newer/older toolkit package states fail closed for manual reconciliation. It does **not** install a Linux NVIDIA display driver inside WSL.

AMD/ROCm acceleration does not install host GPU drivers. It is enabled only when WSL already exposes the required `/dev/kfd` and `/dev/dri` devices; the generated Compose overlay passes those devices and their discovered numeric access groups to Ollama. GPU device access intentionally grants that container more hardware access than CPU-only mode. Select **CPU only** if that access is not desired.

## Container resource ceilings

Adaptive resource limits are persisted installer policy. They are **per-container CPU/RAM ceilings**, not an aggregate WSL VM limit and not reservations. A user-maintained `compose.override.yaml` is merged last and can intentionally override LatticeVale-generated ceilings. Use Windows/WSL global resource controls separately when a hard VM-wide ceiling is required.

## Supply-chain boundary

LatticeVale itself is inspectable source, but selected installation features download third-party software, container images, Git sources, Ubuntu packages, and local AI models. The installer pins important components where practical. Repair performs a bounded periodic refresh of installer-owned prerequisite/Docker packages and selected managed images/builds, while blanket OS-wide and broader upstream source updates remain explicit operations. Upstream compromise and registry/package risks cannot be eliminated by this project.

Before publishing releases, maintainers should:

1. publish the ZIP SHA-256 in the GitHub release notes;
2. keep GitHub secret scanning/security features enabled where available;
3. review dependency/image changes separately from repair-only changes;
4. rerun the full regression/static suite;
5. inspect the generated release tree for unexpected binary/bytecode files;
6. avoid committing real credentials, generated WSL data, or backup archives.

## PowerShell `Add-Type` / AV-EDR visibility

LatticeVale contains readable C# source embedded in its PowerShell relay helpers and environment-change helper and compiles that source in memory with PowerShell `Add-Type`. No compiled relay binary is downloaded or shipped, but in-memory compilation is also used by legitimate administration tools and by some living-off-the-land techniques, so antivirus/EDR products can flag or block it. On organization-managed endpoints, review the exact source and obtain administrator/security approval rather than weakening endpoint protection. A blocked relay should fail as an integration problem; users can choose managed WSL/Docker Ollama instead of creating an AV exclusion.

## Optional native Windows Ollama bridge

Native Windows Ollama is external/user-owned software: LatticeVale does not install or update the Windows application. The questionnaire explicitly distinguishes it from LatticeVale-managed WSL/Docker Ollama, which LatticeVale can install and maintain.

When a running Windows Ollama API is detected, native linking is **not** enabled solely because the process exists. LatticeVale also probes the selected WSL distro for its current Windows-host route and proves that Windows can bind the reported interface. If that topology cannot be verified, the native backend is not offered.

When explicitly selected, LatticeVale copies an installer-owned PowerShell relay under the current user's `%LOCALAPPDATA%\LatticeVale` directory and registers an installer-owned scheduled task. The relay targets only the Windows-local Ollama endpoint that LatticeVale actually verified (normally `127.0.0.1:11434`, or a loopback `OLLAMA_HOST` override), listens only on the detected Windows-host interface used by that WSL instance, and creates an exact-port Windows Firewall rule restricted to the selected WSL IPv4. It never binds `0.0.0.0`, changes `OLLAMA_HOST`, or makes the native Ollama listener LAN-wide. The relay refreshes its WSL/Windows addresses while running, updates only its installer-owned exact-address firewall rules when topology changes, and rebuilds listeners when required. It first checks whether the selected distro is already running so monitoring does not wake a deliberately stopped WSL instance.

The Windows relay firewall rule uses `Profile Any` because WSL/Hyper-V virtual traffic can inherit host profile behavior that is not stable across machines. The rule is still constrained to the exact installer-owned WSL source address, Windows WSL-host destination address, protocol, and port; Hyper-V firewall rules are likewise port/address scoped when supported. LatticeVale does not change WSL global firewall defaults.

Native Windows Ollama itself remains user/upstream-owned: LatticeVale does not install it, update it, change its model directory, choose its GPU backend, or alter its native startup policy. LatticeVale may call the local Ollama API to verify the runtime, list models, unload a selected model after an embedding compatibility check, and pull a missing model tag that the user selected in the questionnaire.

## Preservation-first repair

Resume / repair must not solve configuration problems by deleting persistent user state. In particular it should preserve profiles, memories, sessions, Matrix rooms/messages, Matrix crypto/E2EE state, databases, Docker volumes, Ollama models, vault/workspace files, and credentials unless the user explicitly selects a destructive recovery action.

If the installer cannot prove ownership of a Matrix identity/configuration, it stops rather than resetting or adopting it silently.

## Known testing boundary

Static/container tests cannot fully emulate Windows Task Scheduler, a real WSL VM lifetime, Windows Tailscale, or live Element clients. Release notes should distinguish those untested integration boundaries from deterministic/source-level validation.

## Global WSL configuration changes

If a selected option requires changing `.wslconfig`, applying that change requires the global `wsl --shutdown` operation. LatticeVale checks for other running WSL distros and asks for explicit confirmation before it writes the global configuration when unrelated distros would be stopped. Declining leaves the global setting unchanged and the repair can be rerun later.
