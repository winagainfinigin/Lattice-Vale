# LatticeVale v14.3.33 detailed functional-WSL-preflight notes

> **v14.3.41 networking supersession note:** The v14.3.33 functional-preflight behavior remains, but its statement that mirrored networking remains an installer fallback is historical. Current v14.3.41 normal installer flows never write or switch global `networkingMode`; only an already-working host/user mirrored configuration may be consumed.


> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `KANBAN-SKILL-POLICY-PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.33` (2026-08-19). This file retains detailed implementation/audit context.


This patch fixes a false-negative WSL prerequisite check introduced by the downstream audit patch.

- `Microsoft-Windows-Subsystem-Linux=Disabled` is no longer fatal by itself. Modern Store/MSI WSL2 may be usable while the legacy/inbox WSL1 component is disabled.
- `VirtualMachinePlatform` feature state is retained as diagnostic context, but functional WSL2/distro probes decide whether installation can continue.
- The installer now detects modern WSL, enumerates registered distros with bounded probes, verifies WSL2, and actually launches the selected Ubuntu distro before treating WSL as usable.
- The host repair helper now tests the existing distro before DISM or feature mutation. If the distro already launches, it exits without changing Windows.
- On modern Store/MSI WSL, the helper will not automatically enable the legacy/inbox WSL1 optional component merely because it reports Disabled.
- Existing preservation guarantees remain: no unregister/import/move/VHDX mutation.

This patch is intentionally compatible with the preceding network-safety patch: NAT remains preferred when it works, mirrored networking remains an explicit fallback, and no global WSL restart occurs merely because native Ollama plus Tailscale were selected.
