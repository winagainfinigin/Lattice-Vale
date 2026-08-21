# Runtime Sources and Supply-Chain Policy

## v14.4.6 source-policy note

v14.4.6 adds no third-party dependency, network source, or bundled binary. It uses Python's standard `os.sched_getaffinity()` when available and the already-required `nproc` utility as a fallback so audit CPU fingerprinting matches the existing resource generator.

## v14.4.5 source-policy note

v14.4.5 added no third-party runtime dependency or bundled binary; it changed repair convergence and introduced a temporary version-only trigger for the existing bounded managed package/image/source refresh. v14.4.6 supersedes that trigger: automatic refresh is now age/revision/legacy-state gated, while explicit Option 6 forces it. Docker Compose reconciliation still relies on documented Compose behavior that changed service configuration/image references cause affected containers to be recreated while mounted volumes are preserved.

## v14.4.4 source-policy note

v14.4.4 adds no third-party runtime dependency or bundled binary. The repair fix uses existing GNU/Linux tools already required by the Ubuntu bootstrap (`find`, `chown`, `chmod`, `mktemp`) and does not add a network, package, or binary source. v14.4.3 RAM-efficiency/uninstaller source policy remains unchanged.

## v14.4.2 source-policy note

v14.4.2 added no third-party runtime dependency or bundled binary. It updated documentation/version-validation metadata and regenerated the exact release manifest; dependency/source ownership remained unchanged from v14.4.1.

## v14.4.1 source-policy note

v14.4.1 adds no third-party runtime dependency or bundled binary. It reorganizes LatticeVale-owned source/documentation and moves the exact release manifest to `installer/SOURCE-SHA256SUMS.txt`; dependency/source ownership remains unchanged from v14.4.0.

## v14.4.0 source-policy note

v14.4.0 adds no third-party runtime dependency or bundled binary. It promotes the audited v14.3.43 runtime line unchanged and adds/updates documentation, release metadata, regression-version compatibility, and release integrity data.

## v14.3.43 source-policy note

v14.3.43 adds no third-party download, binary, package or runtime dependency. It changes only PowerShell Scheduled Task inspection plus regression/release documentation.

## v14.3.42 clean-host source-policy note

v14.3.42 adds no bundled third-party binary. The reset helper uses installed Windows/WSL/PowerShell/winget/Tailscale command surfaces when present and does not add a download source. Normal runtime acquisition pins are unchanged from v14.3.41.

## v14.3.41 WSL host-safety source-policy note

v14.3.41 adds no bundled binary dependency or new third-party source. Its runtime change removes the installer-side mirrored-networking fallback and strengthens the existing source-visible WSL repair helper. The inherited v14.3.39 runtime correction removes automatic engine-global Docker pruning from repair maintenance. v14.3.38 adds no bundled binary dependency. Its Kanban guard is generated as plain Python source inside the existing Hermes plugin surface, and its skill/agent policy is plain managed configuration/SOUL text. The implementation is aligned to the Hermes version pinned by this bundle and its documented Kanban, skills, and `pre_tool_call` hook contracts. A future Hermes pin change must re-run those compatibility fixtures rather than assuming hook/tool semantics are unchanged.

> **Audit patch 1:** the explicit WSL host repair helper uses only built-in Windows servicing/WSL commands. Its repair rationale was checked against Microsoft Learn WSL installation/troubleshooting and Windows-image repair documentation, plus current microsoft/WSL issue reports. No additional third-party binary is bundled or downloaded by the helper.

LatticeVale v14.4.6 remains distributed as source/configuration only. It does **not** redistribute third-party application installers, package archives, model blobs, or saved container images. Selected dependencies are obtained online at install/update time.

## Windows software

| Component | LatticeVale acquisition path | Official upstream |
|---|---|---|
| Tailscale | Transient download from `https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe` with Authenticode verification; `winget` ID `Tailscale.Tailscale` is fallback. The downloaded EXE is deleted after use. | `https://tailscale.com/download/windows` |
| Obsidian | `winget` exact package ID `Obsidian.Obsidian`; no installer is bundled. | `https://obsidian.md/download` |
| Ubuntu Pro for WSL | `winget` exact package ID `Canonical.UbuntuProforWSL`; no installer/package is bundled. | `https://documentation.ubuntu.com/pro-for-wsl/` |

## Ubuntu / Docker packages

Docker Engine and the Compose plugin are installed from Docker's official Ubuntu APT repository and signing key:

- `https://download.docker.com/linux/ubuntu`
- `https://download.docker.com/linux/ubuntu/gpg`

Other Ubuntu packages come from the selected distro's configured APT sources. LatticeVale does not bundle `.deb` packages.

## Container images

Compose references are pulled online from their upstream registries when a clean install/update actually needs them; no image tarballs are in the repository:

| Compose image | Registry/upstream reference |
|---|---|
| `nousresearch/hermes-agent:v2026.8.16` | `https://hub.docker.com/r/nousresearch/hermes-agent` / `https://github.com/NousResearch/hermes-agent` |
| `matrixdotorg/synapse:v1.158.0` | `https://hub.docker.com/r/matrixdotorg/synapse` / `https://github.com/element-hq/synapse` |
| `postgres:16-alpine` | `https://hub.docker.com/_/postgres` |
| `valkey/valkey:8-alpine` | `https://hub.docker.com/r/valkey/valkey` / `https://github.com/valkey-io/valkey` |
| `searxng/searxng:2026.8.17-374939b88` | `https://hub.docker.com/r/searxng/searxng` / `https://github.com/searxng/searxng` |
| `ollama/ollama:0.32.14` | `https://hub.docker.com/r/ollama/ollama` / `https://github.com/ollama/ollama` |
| `ollama/ollama:0.32.14-rocm` (AMD/ROCm mode) | `https://hub.docker.com/r/ollama/ollama` / `https://github.com/ollama/ollama` |
| `pgvector/pgvector:pg15` | `https://hub.docker.com/r/pgvector/pgvector` / `https://github.com/pgvector/pgvector` |
| `redis:8-alpine` | `https://hub.docker.com/_/redis` |
| QMD build base `node:24-bookworm-slim` | `https://hub.docker.com/_/node` |

LatticeVale's distributed defaults do not use floating `latest` tags for Ollama or SearXNG. Resume / repair preserves explicit image/source overrides and refreshes installer-owned package/image/source state only when the 30-day gate is due, the managed-refresh policy revision changes, valid legacy state is missing, or explicit Update / repair forces it. A bundle-version change alone stays local-first. The Windows **Update / repair installer-managed software** choice forces the current bundle-aligned managed refresh after a required backup. `./manage.sh update` remains a separate advanced upstream-refresh workflow and is not the bundle-pinned updater.

## Optional NVIDIA GPU runtime

When NVIDIA acceleration is selected (or Auto detects WSL NVIDIA support and the runtime is missing), LatticeVale may install NVIDIA Container Toolkit from NVIDIA's official APT metadata only:

- `https://nvidia.github.io/libnvidia-container/gpgkey`
- `https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list`

LatticeVale pins the complete NVIDIA Container Toolkit 1.20.0 Debian package set (`nvidia-container-toolkit`, `nvidia-container-toolkit-base`, `libnvidia-container-tools`, and `libnvidia-container1`, each `1.20.0-1`) from that official repository for the v14.3.2 release (unchanged from v14.3.0). If a complete installed toolkit is already newer than that pin, LatticeVale preserves it and verifies the runtime instead of downgrading. If package state is mixed (some newer than the pin while other toolkit components are missing/older), installation fails closed rather than forcing a downgrade. The installer runs NVIDIA's documented `nvidia-ctk runtime configure --runtime=docker`, backs up an existing Docker daemon configuration before changing it, verifies the NVIDIA runtime afterward, and restores the prior daemon configuration if verification fails. It does not install a Linux NVIDIA display driver inside WSL.

## Source-built / package-installed components

Honcho is fetched from the official Plastic Labs GitHub repository (`https://github.com/plastic-labs/honcho.git`) and checked out at the LatticeVale-tested commit `444897975c95393b0d48024470ece03c025d3aa4`. Ordinary repair reuses the existing checkout. During a due periodic managed refresh—or an explicit Windows Update / repair run—LatticeVale advances it to the commit audited by the current bundle only when the checkout's origin and recorded `LATTICEVALE_HONCHO_SOURCE_AUTO` marker prove that the source is installer-owned; custom/ambiguous legacy checkouts are preserved. QMD is built from published package `@tobilu/qmd@2.5.3`, with upstream source at `https://github.com/tobi/qmd`.

## Local AI models

When the managed backend is selected, the WSL/Docker Ollama runtime pulls the user-selected model tags online. When a verified **native Windows Ollama** backend is selected, LatticeVale first lists the native store through `/api/tags` and requests a missing selected model through that running native Ollama server's `/api/pull` API; users do not need to pre-download the selected models manually. The model files remain in native Ollama's Windows-managed model store. Honcho's selected embedding model is capability-checked against Ollama's OpenAI-compatible `/v1/embeddings` endpoint with `dimensions=1536`; the native path performs that check directly through the already-verified WSL relay before Honcho's Compose network exists. LatticeVale does not ship, install, update, or reconfigure native Windows Ollama. Model blobs are never shipped in the LatticeVale ZIP/repository.

Current default model references are upstream Ollama model tags, not bundled assets:

- `qwen3.5:4b` — selected local text-model default where local Hermes AI is enabled.
- `qwen3-embedding:4b` — selected Honcho embedding-model default; Ollama publishes this tag as an embedding model and supports user-defined output dimensions suitable for the stack's 1536-dimensional requirement.

Official references: `https://docs.ollama.com/api/tags`, `https://docs.ollama.com/api/pull`, `https://docs.ollama.com/api/openai-compatibility`, and `https://ollama.com/library/qwen3-embedding:4b`.

## WSL native-Ollama networking references

Native Windows Ollama relay selection follows current Microsoft WSL networking behavior rather than assuming one fixed route shape. Microsoft documents Windows/WSL localhost connectivity for mirrored networking and current `networkingMode` values including NAT, mirrored, and VirtioProxy. For NAT-style transport, LatticeVale first considers the Linux default-route next hop; if that is absent/unusable, it may consider IPv4 addresses on Windows WSL/Hyper-V virtual adapters that match the selected distro subnet, but accepts a fallback only after a temporary WSL-scoped TCP reachability probe. For mirrored/local transport, Docker's documented `host-gateway` mapping is used only as a container-to-WSL-host hop; an installer-owned WSL relay then forwards to the already-verified Windows IPv4-loopback Ollama API. Topology labels and adapter names are diagnostic/discovery hints, not sufficient proof by themselves.

- `https://learn.microsoft.com/windows/wsl/networking`
- `https://learn.microsoft.com/windows/wsl/wsl-config`
- `https://docs.docker.com/reference/cli/docker/container/run/` (`host-gateway` special value)

## RAM-efficiency implementation references

The v14.4.4 tuning policy was checked against the relevant upstream configuration surfaces:

- Microsoft WSL configuration and memory reclaim: `https://learn.microsoft.com/windows/wsl/wsl-config`
- PostgreSQL resource configuration / `shared_buffers`: `https://www.postgresql.org/docs/current/runtime-config-resource.html`
- Synapse configuration / cache-factor controls: `https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html`
- GNU libc memory-allocation tunables / arena limits: `https://sourceware.org/glibc/manual/latest/html_node/Memory-Allocation-Tunables.html`

These are configuration references only; LatticeVale does not download software from these documentation URLs.

## Repository/source rule

Public release auditing rejects compiled installers/binaries/bytecode and opaque bootstrap patterns. All LatticeVale executable logic—including the optional desktop shortcut launcher—is present as readable `.ps1`, `.sh`, `.py`, YAML, Dockerfile, or configuration source. See `.github/workflows/validate.yml`, `SECURITY.md`, `LatticeVale-Core/AUDIT.md`, and the consolidated `CHANGELOG.md`.

LatticeVale's MIT license permits downstream modification and redistribution of LatticeVale source/documentation. A customized repository should keep its changed source inspectable, regenerate `installer/SOURCE-SHA256SUMS.txt`, identify itself as modified, and separately respect the licenses/terms of every fetched or incorporated third-party component.

## Pinned image policy

LatticeVale release defaults use explicit upstream versioned image tags to reduce unreviewed drift. Versioned registry tags improve repeatability but are **not equivalent to immutable image digests** and may theoretically be republished upstream. Between refresh windows, repair does not advance pins merely because upstream has something newer. During the 30-day managed refresh or an explicit Windows Update / repair run, a LatticeVale release may advance only the bundle-declared defaults that are proven installer-owned by ownership markers; explicit `.env` overrides remain user-owned. Fixed tags advance to a different version only when the LatticeVale bundle itself declares a different tag; pulling a fixed tag is not treated as permission to follow arbitrary upstream releases. `installer/SOURCE-SHA256SUMS.txt` authenticates the complete shipped LatticeVale release tree except the manifest itself—it does not authenticate third-party registry contents or downloads fetched later at install/update time. NVIDIA Container Toolkit, when selected for supported NVIDIA GPU acceleration, is installed from NVIDIA's official `nvidia.github.io/libnvidia-container` APT repository.

## Uninstaller

`installer/uninstall.ps1` and `LatticeVale-Core/Uninstall-LatticeVale.ps1` are first-party LatticeVale source and use only Windows/WSL/PowerShell facilities already required by the installer; they add no third-party dependency.
