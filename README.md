# LatticeVale v14.4.6

LatticeVale is a source-visible Windows + WSL2 installer and lifecycle manager for a self-hosted Hermes Agent stack with optional Matrix, Kanban, memory, search, local AI, indexing, and Windows/Tailscale integrations.

**v14.4.6 fixes adaptive-resource audit fingerprinting under WSL CPU limits and refines repair update triggering.** `state-audit.py` now measures the CPU set actually available to the WSL process (matching `nproc` and the resource-policy generator) instead of using the host/logical count returned by `os.cpu_count()`. A bundle-version change by itself no longer forces package/image/source refresh: Resume / repair refreshes that managed layer when the 30-day gate is due, when `MANAGED_REPAIR_REFRESH_REVISION` changes, when no valid refresh marker exists, or when Option 6 explicitly forces it. This lets 14.4.5→14.4.6 apply the audit fix without rebuilding healthy images, while public 14.4.2→14.4.6 still performs the required cumulative managed refresh because the refresh revision advances from 1 to 2 and adaptive policy advances from v2 to v3. v14.4.5 runtime-policy convergence, v14.4.4 metadata-race hardening, and v14.4.3 RAM/uninstaller fixes remain inherited.

**v14.4.5 introduced explicit Resume / repair runtime-policy convergence.** A stale adaptive RAM policy is regenerated even when an older `prepare_config` checkpoint is complete, affected containers are forced through Compose reconciliation so the limits/tuning become live, and final configuration cannot report success while adaptive policy is stale. v14.4.6 retains that behavior but supersedes v14.4.5's temporary bundle-version-only component-refresh trigger with the refresh-revision/age/explicit-force model described above.

Release entry points remain organized under [`installer/`](installer/), while project documentation is consolidated under [`docs/`](docs/). Git/repository metadata and the project license remain at repository root where GitHub and Git expect them.

## Start here

- [Complete project documentation](docs/README.md)
- [Installation instructions](docs/Instructions.txt)
- [Complete features/options reference](docs/FEATURES.md)
- [Installer description](docs/Installer%20Description.txt)
- [Security policy](docs/SECURITY.md)
- [Release history](docs/CHANGELOG.md)
- [v14.4.6 resource fingerprint audit notes](docs/RESOURCE-FINGERPRINT-AUDIT-PATCH-NOTES.md)
- [v14.4.5 repair runtime/update notes](docs/REPAIR-RUNTIME-POLICY-UPDATE-PATCH-NOTES.md)
- [v14.4.4 repair-race notes](docs/REPAIR-METADATA-RACE-PATCH-NOTES.md)
- [License](LICENSE)

Verify the extracted release from an Administrator PowerShell window:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\verify-release.ps1
```

Install:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1
```

Uninstall the managed stack:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\uninstall.ps1
```
