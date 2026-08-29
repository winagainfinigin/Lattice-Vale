# Third-party notices

v14.5.0 adds no new third-party runtime dependency, binary, image, model, hosted service, or paid API requirement. Its new read-only planner/config-state reader/free-operation audit use only Python standard-library functionality and existing LatticeVale state/audit surfaces.

The v14.4.7 web-extraction change, v14.4.8 Hermes clean/repair maintenance, v14.4.81/v14.4.82 WSL recovery hotfixes, and v14.4.83 runtime-policy/sysctl/Ubuntu-Pro-option-removal patch add no redistributed third-party binary, image, package, or license. Local browser support uses the Chromium/Playwright runtime already provided by the separately obtained Hermes Agent image.

## v14.3.38 notice

The Kanban/skill reliability patch adds **no new third-party package, binary, image, model, or external service**. It uses the Hermes Agent plugin/tool interfaces already present in the pinned Hermes image and generates only LatticeVale-owned text configuration/plugin policy.

LatticeVale is an **unofficial** integration/installer project. It is not affiliated with, sponsored by, or endorsed by Nous Research, Microsoft, Canonical, Docker, Tailscale, The Matrix.org Foundation / Element, Obsidian, Ollama, SearXNG, Plastic Labs, QMD, Redis, Valkey, PostgreSQL, pgvector, or other integrated projects.

The repository `LICENSE` applies to LatticeVale's own original source/documentation and permits modification, forking, and redistribution of that LatticeVale material under MIT terms. Software downloaded, pulled, built at runtime, or copied from another upstream project remains governed by its respective upstream license, trademark rules, security policy, and terms. Modifying LatticeVale does not relicense those components, and LatticeVale does not bundle third-party application installers or container-image archives.

Names are used descriptively to identify compatibility/integration targets. See `SOURCES.md` for runtime acquisition locations and supply-chain boundaries.

## Network-use note for Honcho

Honcho upstream is licensed under **GNU AGPL-3.0**. LatticeVale does not modify or relicense Honcho; it fetches the audited upstream source commit and builds it locally. If you modify Honcho and make that modified version available for users to interact with over a network, AGPL-3.0 Section 13 may require offering those users the Corresponding Source of that modified version. Purely private/personal operation and unmodified upstream use can have different obligations. This is a project notice, not legal advice; review the upstream Honcho LICENSE and obtain legal advice for public/commercial deployments.
