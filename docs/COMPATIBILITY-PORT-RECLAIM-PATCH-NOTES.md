# LatticeVale v14.3.34 detailed compatibility + stale bridge-port notes

> **v14.3.41 networking supersession note:** The compatibility/port-reclaim behavior remains, but the historical mirrored-fallback wording below no longer describes current networking ownership. v14.3.41 normal installer flows do not create or switch global mirrored mode.


> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `KANBAN-SKILL-POLICY-PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.34` (2026-08-19). This file retains detailed implementation/audit context.


This patch is built on the functional-WSL-preflight and network-safety patches.

## Supported envelope

The bundle intentionally remains limited to the combinations its application/container stack validates end-to-end:

- Windows 10/11 client, build 19041 or newer.
- x64/AMD64 Windows.
- An existing, working WSL2 distribution whose `/etc/os-release` identifies Ubuntu 22.04, 24.04, or 26.04 and whose package architecture is amd64.
- Windows PowerShell 5.1 or PowerShell 7 for the installer; relay tasks self-test available PowerShell engines before registration.

Unsupported operating systems, WSL1, non-Ubuntu distributions, and unverified CPU/image architectures fail before the stack is mutated rather than being guessed compatible.

## Compatibility hardening

- Successful `wsl.exe` enumeration/version probes now parse STDOUT only. STDERR remains diagnostic, preventing WSL update/startup notices from becoming phantom distro names.
- Optional Windows WSL feature-state metadata stays advisory; actual WSL2 version and distro-launch probes decide usability.
- The WSL host-repair helper no longer defaults to `Ubuntu-24.04`. It auto-selects only when exactly one distro is registered, otherwise it requires `-DistroName` explicitly.
- WSL registry `BasePath` normalization preserves extended volume-GUID paths instead of corrupting them by stripping `\\?\` unconditionally.
- Storage resolution prefers `Get-Volume -FilePath` when available, allowing local fixed volumes mounted through a directory/volume GUID as well as ordinary drive letters; older systems retain the Win32_LogicalDisk fallback.
- Existing NAT/mirrored networking policy remains capability-first: working NAT is preserved, existing mirrored mode is supported, and switching to mirrored stays explicit and transactional.

## Stale LatticeVale Windows bridge ports

Older/repaired installs could leave the current Windows-native relay running while a new install selected bridge ports. The running LatticeVale listener made its own canonical port appear foreign, producing warnings such as:

- `Dashboard Windows bridge port 19119 is unavailable. Using 19120 instead.`
- `Matrix Windows bridge port 18008 is unavailable. Using 18009 instead.`

The installer now:

1. proves current relay ownership from the exact scheduled-task script AND config paths;
2. stops that verified task before bridge-port allocation;
3. removes only orphaned PowerShell relay processes whose command lines contain both exact installer-owned paths;
4. waits for verified old ports to release;
5. tries canonical `19119` and `18008` first again;
6. uses a prior/alternate port only if the canonical port is still genuinely unavailable.

No process is killed merely because it owns a TCP port. Same-name tasks that cannot be proven LatticeVale-owned are preserved, and unknown listeners still force a safe alternate port.
