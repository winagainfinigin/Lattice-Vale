# LatticeVale v14.4.2

LatticeVale is a source-visible Windows + WSL2 installer and lifecycle manager for a self-hosted Hermes Agent stack with optional Matrix, Kanban, memory, search, local AI, indexing, and Windows/Tailscale integrations.

**v14.4.2 is a documentation and release-layout consistency patch over v14.4.1.** Installer and runtime behavior are intentionally unchanged. Release documentation and regression expectations now match the actual `Lattice-Vale` package folder structure, and the source manifest has been regenerated for the updated files.

Release entry points remain organized under [`installer/`](installer/), while project documentation is consolidated under [`docs/`](docs/). Git/repository metadata and the project license remain at repository root where GitHub and Git expect them.

## Start here

* [Complete project documentation](docs/README.md)
* [Installation instructions](docs/Instructions.txt)
* [Complete features/options reference](docs/FEATURES.md)
* [Installer description](docs/Installer%20Description.txt)
* [Security policy](docs/SECURITY.md)
* [Release history](docs/CHANGELOG.md)
* [License](LICENSE)

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
