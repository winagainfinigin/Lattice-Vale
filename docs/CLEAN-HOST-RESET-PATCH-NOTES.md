# v14.3.42 Clean-host reset patch notes

## v14.3.43 Scheduled Task compatibility follow-up

A real Windows dry run exposed a portability bug in v14.3.42: Task Scheduler action collections are heterogeneous, but the reset scanner dereferenced Exec-only `Execute`, `Arguments`, and `WorkingDirectory` fields on every action. v14.3.43 replaces those direct dereferences with optional-property inspection and includes common Exec/COM-handler metadata only when present. Unknown/non-owned tasks remain untouched. No destructive scope was broadened.


## Purpose

This release adds a deliberately separate clean-host reset path for administrators who want to destroy an existing WSL/LatticeVale environment and rebuild from a fresh WSL installation. It does not make normal uninstall, repair or update more destructive.

## Ownership boundary

The reset utility removes Windows objects only when their names/actions/paths prove LatticeVale ownership, or when the administrator explicitly selects legacy pre-LatticeVale Foundry cleanup. It preserves independently installed Windows Tailscale and Obsidian, shared Hyper-V/HypervisorPlatform/VirtualMachinePlatform/HNS infrastructure, unrelated firewall/HNS state, and standalone `%USERPROFILE%\.hermes`.

## WSL reset

`-RemoveWslRuntime` is intentionally broad and destructive: it enumerates all WSL distros registered for the current Windows user, requires explicit confirmation before execution, unregisters them, removes former registered distro storage, removes `.wslconfig*`, and attempts to uninstall the Store/MSI `Microsoft.WSL` package. It does not disable shared Windows virtualization features or manually delete HNS networks.

## Tailscale

The tool never uses `tailscale serve reset`. It inspects current Serve JSON and disables a specific HTTPS listener only when the current configuration still references a known LatticeVale bridge backend, preserving unrelated tailnet services.

## Release rule

The utility is dry-run by default, never invoked automatically, and source-tree deletion requires a recognizable LatticeVale release root (`installer/install.ps1` + `LatticeVale-Core/VERSION.txt`) and refuses filesystem roots.
