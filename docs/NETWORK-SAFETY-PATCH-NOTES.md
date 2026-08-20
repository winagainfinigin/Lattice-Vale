# LatticeVale v14.3.32 detailed WSL networking-safety notes

> **v14.3.41 supersession note:** v14.3.41 preserves capability-first relay discovery but removes the explicit mirrored fallback described below. Normal installer flows no longer write `networkingMode`; already-working mirrored mode is external/user-owned. The remainder of this file is retained as historical v14.3.32 implementation context.

> **v14.3.38 retention note:** This historical patch remains part of the current compatibility baseline. v14.3.38 adds the Kanban/skill policy migration described in `KANBAN-SKILL-POLICY-PATCH-NOTES.md` without removing these guarantees.

> Canonical release entry: `CHANGELOG.md` → `14.3.32` (2026-08-19). This file retains detailed implementation/audit context.


This patch changes the v14.3.30 shared native-Windows-Ollama + Windows-Tailscale policy from mode-first to capability-first.

- A verified NAT/private-relay path is preserved. Selecting both features no longer proactively changes `%USERPROFILE%\.wslconfig`.
- Mirrored networking remains supported when it is already active.
- If the current topology cannot verify the native-Ollama bridge, mirrored mode can still be offered as an explicit fallback, but the prompt defaults to **No**.
- Only accepting that fallback can write `networkingMode=mirrored` and invoke global `wsl --shutdown`. The existing backup/verification/rollback transaction remains in place.
- The Windows Tailscale relay continues to use `127.0.0.1` in mirrored mode and dynamically refreshed WSL IPv4 in NAT mode.
- Runtime policy auditing now accepts either verified NAT or mirrored as the canonical shared topology.

This patch does not unregister, import, move, mount, compact, or edit the distro VHDX.
