# LatticeVale v14.4.6

> **Main Release — v14.4.6**
> Current recommended release and cumulative upgrade target from the public **v14.4.2 Main Release**.

LatticeVale is a source-visible **Windows + WSL2 installer, integration layer, and lifecycle manager for a self-hosted Hermes Agent stack**.

It installs into an **existing supported Ubuntu WSL2 distribution**, provisions Docker and Hermes, and can integrate Matrix, multi-profile Kanban orchestration, memory/Honcho, SearXNG, QMD indexing, Ollama/local AI, Obsidian, Windows lifecycle shortcuts, and Tailscale remote access.

LatticeVale is intentionally **recovery-aware and ownership-conscious**: it manages the Hermes stack without treating the user's entire WSL installation, Docker environment, Windows applications, Tailscale configuration, or personal data as disposable.

---

## What it manages

A typical installation includes:

```text
Windows 11
├─ LatticeVale installer/lifecycle tooling
├─ Start / Shutdown shortcuts
├─ optional Tailscale integration
├─ optional Obsidian integration
└─ WSL2 Ubuntu
   └─ ~/hermes-stack
      ├─ Docker Engine / Compose
      ├─ Hermes Agent
      │  ├─ API + Dashboard
      │  ├─ default + optional additional profiles
      │  └─ Kanban orchestration
      ├─ Matrix / Synapse + PostgreSQL
      ├─ SearXNG + Valkey
      ├─ QMD + indexer
      ├─ Honcho + PostgreSQL/pgvector + Redis
      └─ optional managed Ollama
