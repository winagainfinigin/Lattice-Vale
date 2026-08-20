> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.13.1

## Purpose

v13.13.1 fixes a Windows Tailscale relay-stage stall observed after the Linux stack had already completed successfully and every Windows-local service probe returned OK.

## Root cause

The v13.13.0 native relay helper called `/usr/local/sbin/hermes-stack-start` **before** probing the already-running WSL backends. That recovery helper is intentionally allowed up to 900 seconds. At the same time, the parent installer waited up to 900 seconds for relay readiness without emitting progress. A healthy clean install or repair could therefore appear frozen at `Creating Windows-native WSL relay for Tailscale` even though Hermes, Dashboard, Matrix, SearXNG, and Honcho had just passed their localhost checks.

Repair reruns had a second edge case: a previous long-running relay task could still be stopping while its script/config were replaced, allowing a stale mutex/listener to make the new task exit immediately and the installer wait until timeout.

## Fixes

- Native relay now probes current WSL IPv4/backend reachability first for up to 15 seconds.
- Full Hermes stack recovery is fallback-only and runs only when the direct backend probe fails.
- Installer relay verification is reduced to a bounded 120-second startup window because this stage follows successful local service verification.
- Installer prints a heartbeat every 10 seconds while waiting, including Scheduled Task state.
- If the relay Scheduled Task exits before listeners are ready, the installer fails that optional Tailscale exposure immediately and prints `LastTaskResult` plus the relay log tail instead of silently waiting.
- Repair/resume runs explicitly wait for the previous installer-owned relay task to stop before replacing the relay script/config. If it cannot stop within 15 seconds, repair reports a direct actionable error rather than entering an ambiguous stall.
- Persistent relay recovery behavior remains intact for later Windows logons/WSL restarts: when backends are genuinely unavailable, the relay can still invoke the installer-owned stack startup helper and retry.
- The same code path is used by fresh installs and Resume/repair, so both receive the fix.

## Observed log that motivated the patch

The stall occurred only after:

- stack configuration complete;
- all five Windows localhost service probes returned OK;
- Obsidian was reconciled as already installed;
- Tailscale configuration entered `Creating Windows-native WSL relay for Tailscale`.

The preceding Hermes `SyntaxWarning` about `venv\Scripts` is emitted by upstream Hermes Python code during Kanban initialization and is not the cause of the relay-stage wait.
