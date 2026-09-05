# LatticeVale 14.6.0 Installation

## Installation model

LatticeVale is a Windows-driven installer for an existing Ubuntu WSL2 distribution. Windows performs host discovery/integration; the selected Linux user owns the WSL stack; narrowly scoped root operations install system prerequisites and manage the installer-owned Docker Engine.

The installer preserves these boundaries:

- no automatic WSL distro creation/import/unregister/convert;
- no Windows display-driver installation or replacement;
- no implicit destructive reset of an existing managed stack;
- explicit confirmation before installation-changing actions;
- user-owned `compose.override.yaml` is applied last and remains opaque to the installer planner.

## 14.6.0 generated-state architecture

Durable user intent remains in `install-options.json`. Machine-derived state is generated separately under `data/latticevale/`:

- `windows-hardware.json` — installer-supplied Windows snapshot;
- `hardware-capabilities.json` — canonical Windows + live WSL hardware inventory;
- `backend-capabilities.json` — backend availability, health, selection, adapter identity, reason codes;
- `backend-health.json` — fingerprinted runtime proof/failure state;
- `runtime-policy.json` — canonical resource-policy document.

Generated files are fingerprinted and validated before being trusted. A repair may regenerate derived state when Windows/WSL hardware, driver/runtime state, options, or policy schema changes without rewriting durable user intent.

## Fresh install

Run `installer/Install-LatticeVale.ps1`, select an eligible existing Ubuntu distribution and Linux account, select components, review the summary, and explicitly confirm. The installer validates the selected distro again immediately before mutating it.

## Backend selection

GPU acceleration is selected by capability rather than vendor name alone. DirectML, CUDA, ROCm, and Vulkan are distinct capabilities and may coexist. CUDA/ROCm retain their vendor/runtime requirements, while DirectML may qualify any selectable DirectX 12 adapter that passes the actual WSL bridge/runtime checks. CPU remains a first-class fallback. Explicit adapter/backend preferences remain durable; if current hardware cannot satisfy them, effective runtime selection fails safely or falls back without silently rewriting the saved preference. Windows/WSL GPU projection and display drivers are prerequisites; LatticeVale manages the selected backend environment and safe admission/fallback above that boundary.

## Post-install verification

Run `./manage.sh verify` and `./manage.sh diagnose`. The diagnostic output states what was detected, what backend was selected, and why a candidate backend was rejected or deferred.
