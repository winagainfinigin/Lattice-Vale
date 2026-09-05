v14.5.46 adds no redistributed third-party binary, model, or GPU driver. It may install/reuse the already-documented DirectML Ubuntu prerequisites and isolated PyTorch/DirectML environment when DirectML is selected, and may install/reuse the already-documented NVIDIA Container Toolkit when verified NVIDIA WSL acceleration is selected. AMD managed Ollama continues to use the separately pulled pinned ROCm image when the host exposes supported devices. Windows/vendor display drivers remain separately obtained and licensed.

v14.5.43 adds no new third-party runtime dependency, redistributed binary, image, model, hosted migration service, or telemetry. Universal repair migration uses only existing installer-owned files/state, backup/checkpoint logic, and the same managed dependency sources already documented below.

v14.5.42 adds no new third-party runtime dependency or redistributed binary. Its hardware-resource policy uses existing Ollama/Docker/WSL interfaces plus `nvidia-smi` or Linux AMD device/sysfs information when those acceleration paths are selected. Native Ollama remains separately installed and separately licensed.
Its canonical policy fingerprints/report, deterministic sharded test runner, patch round-trip verification, and release ZIP/hash verification use only first-party project code plus standard Git/Python/shell/ZIP/SHA-256 tooling already required for repository/release maintenance; no telemetry or additional runtime service is introduced.


v14.5.3 adds an **optional** DirectML path. LatticeVale does not redistribute DirectML, PyTorch, torchvision, Transformers, Safetensors, SentencePiece, or Hugging Face model weights. When selected, the installer creates an isolated environment and downloads `torch-directml==0.2.5.dev240914`, its `torch==2.4.1` / `torchvision==0.19.1` compatibility dependencies, and the listed Python/model dependencies from their upstream sources. Their upstream licenses apply independently. Ollama remains an independent required dependency for Honcho embeddings and fallback.

# Third-party notices

v14.5.2 adds no new third-party runtime dependency and changes no third-party pin; Option 7 is implemented entirely with existing first-party installer/helper logic and already-present system/Docker commands. v14.5.1 adds no new third-party runtime dependency and changes no third-party pin. It modifies only first-party adaptive memory/audit behavior. v14.5.0 added no new third-party runtime dependency, binary, image, model, hosted service, or paid API requirement. Its new read-only planner/config-state reader/free-operation audit use only Python standard-library functionality and existing LatticeVale state/audit surfaces.

The v14.4.7 web-extraction change, v14.4.8 Hermes clean/repair maintenance, v14.4.81/v14.4.82 WSL recovery hotfixes, and v14.4.83 runtime-policy/sysctl/Ubuntu-Pro-option-removal patch add no redistributed third-party binary, image, package, or license. Local browser support uses the Chromium/Playwright runtime already provided by the separately obtained Hermes Agent image.

## v14.3.38 notice

The Kanban/skill reliability patch adds **no new third-party package, binary, image, model, or external service**. It uses the Hermes Agent plugin/tool interfaces already present in the pinned Hermes image and generates only LatticeVale-owned text configuration/plugin policy.

LatticeVale is an **unofficial** integration/installer project. It is not affiliated with, sponsored by, or endorsed by Nous Research, Microsoft, Canonical, Docker, Tailscale, The Matrix.org Foundation / Element, Obsidian, Ollama, SearXNG, Plastic Labs, QMD, Redis, Valkey, PostgreSQL, pgvector, or other integrated projects.

The repository `LICENSE` applies to LatticeVale's own original source/documentation and permits modification, forking, and redistribution of that LatticeVale material under MIT terms. Software downloaded, pulled, built at runtime, or copied from another upstream project remains governed by its respective upstream license, trademark rules, security policy, and terms. Modifying LatticeVale does not relicense those components, and LatticeVale does not bundle third-party application installers or container-image archives.

Names are used descriptively to identify compatibility/integration targets. See `SOURCES.md` for runtime acquisition locations and supply-chain boundaries.

## Network-use note for Honcho

Honcho upstream is licensed under **GNU AGPL-3.0**. LatticeVale does not modify or relicense Honcho; it fetches the audited upstream source commit and builds it locally. If you modify Honcho and make that modified version available for users to interact with over a network, AGPL-3.0 Section 13 may require offering those users the Corresponding Source of that modified version. Purely private/personal operation and unmodified upstream use can have different obligations. This is a project notice, not legal advice; review the upstream Honcho LICENSE and obtain legal advice for public/commercial deployments.
