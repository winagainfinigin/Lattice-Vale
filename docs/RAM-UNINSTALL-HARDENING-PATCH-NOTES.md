# LatticeVale v14.4.3 RAM-efficiency and uninstaller hardening

## Scope

v14.4.3 is a targeted runtime/maintenance patch over v14.4.2. It does not add services or dependencies.

## Adaptive resource policy v3

When `containerResourceLimits` is enabled, the generated installer-owned Compose overlay now:

- reserves more WSL/Docker/host headroom on smaller WSL VMs;
- constrains glibc allocator arena growth in long-lived Python/glibc services with `MALLOC_ARENA_MAX`;
- uses a lower supported Synapse cache factor on constrained hosts;
- uses 64 MiB PostgreSQL `shared_buffers` on <=12 GiB WSL VMs and 128 MiB above that;
- preserves Honcho PostgreSQL `max_connections=200`;
- keeps user `compose.override.yaml` as the final override layer.

The policy is generated during ordinary configuration on a clean install. Existing installs with adaptive limits enabled are regenerated when the saved policy revision is older than v3 or WSL-visible CPU/RAM changes, so repair/start adopts the new policy without deleting application data.

LatticeVale deliberately does not write global WSL `memory` or `autoMemoryReclaim` for this feature. Current host-wide WSL resource/reclaim policy remains user/Windows-owned.

## Normal-uninstaller fixes

The preservation-first uninstaller now:

1. reads selected-stack metadata using root WSL context and aborts if required metadata cannot be read safely;
2. detects evidence that Docker runtime may still exist and refuses partial uninstall/purge if the Docker daemon cannot be inspected;
3. preserves modified/unowned scheduled tasks and shortcuts as before, but now also preserves helper/config files that those retained objects still reference;
4. checks ordinary LatticeVale firewall ownership before same-name firewall removal;
5. restores installer-owned `OLLAMA_HOST` only when the current value still matches the recorded installer value and broadcasts `WM_SETTINGCHANGE` after restoration;
6. recognizes normal users with nonstandard absolute home paths when deciding whether distro-level helper/policy/log state is shared;
7. removes `/var/log/hermes-dockerd.log` only when no other recognizable LatticeVale stack remains in the distro.

The uninstaller still does not unregister WSL, uninstall Docker, remove unrelated Docker state, uninstall native Windows Ollama/Tailscale/Obsidian, or delete an external Windows-backed Obsidian vault.

## Clean versus repair adoption

- **Clean install:** the current `configure-stack.sh` writes policy v3 before normal Compose validation/reconciliation.
- **Repair/update:** the bundle replaces installer-owned runtime scripts while preserving data/config; normal reconciliation writes the current overlay, and the generated startup helper additionally refreshes any enabled adaptive policy whose revision/resource fingerprint is stale.
- **User overrides:** `compose.override.yaml` remains listed after `compose.latticevale.yaml`, so user policy wins.
