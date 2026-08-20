# LatticeVale v14.4.1 documentation audit and remediation record

## Scope

The v14.4.0 stable promotion was prepared from the audited v14.3.43 runtime tree. The documentation audit reviewed the complete Markdown/text documentation set, including current operator/release documents and the explicitly archival pre-LatticeVale v13 patch-note collection. Ambiguous or historical claims were cross-checked against the current installer/configuration source before being treated as current behavior.

v14.4.0 intentionally does **not** introduce new runtime stack behavior. It promotes the tested v14.3.43 runtime line and applies documentation, version/test metadata, and release-integrity changes.

## Remediated findings

| Finding | v14.4.0 remediation |
| --- | --- |
| Clean-host reset opening understated destructive WSL scope | `Instructions.txt` now states up front that `-RemoveWslRuntime` unregisters **all WSL distributions registered to the current Windows user**. |
| Fresh storage requirement was incomplete in primary docs | README and Instructions now state both conditions: backing volume **over 50 GiB total capacity** and **at least 50 GiB free**. |
| README questionnaire omitted resource ceilings and timezone | Both choices are now explicitly listed. |
| Instructions incorrectly coupled QMD-only use to a Windows Obsidian vault path | Instructions now state that the explicit Windows-local vault path is required by **Obsidian integration**; QMD alone does not require it. |
| Automatic skill-writing default was not prominent | README, Instructions, Installer Description, and `FEATURES.md` now state that fresh managed profiles default `skills.write_approval` to `false` when absent and that repair/update preserves an explicit existing choice. |
| Change-installed-components scopes were not enumerated | Instructions now lists all current scope categories. |
| Advanced-recovery actions were not enumerated | Instructions now lists all current recovery actions. |
| No canonical complete feature/options inventory | Added root `FEATURES.md` and cross-linked it from primary documentation. |
| README contained duplicated/overlong patch chronology | Primary README now leads with stable current capabilities and points detailed history to `CHANGELOG.md`/patch notes. |
| Networking patch notes duplicated v14.3.41 supersession wording | Duplicate notice collapsed while retaining the historical warning. |

## Stable-release validation evidence

Before the v14.4.0 promotion, the v14.3.43 runtime line was exercised successfully through:

- a real-host fresh clean installation producing a working stack;
- a real-host repair/upgrade from v14.3.42 to v14.3.43 producing a working stack.

For the v14.4.0 packaging tree, inherited high-risk regression fixtures plus the new documentation-audit fixture are rerun after the version/documentation changes, followed by source syntax/static checks, release-manifest regeneration, ZIP integrity checking, and manifest verification against a freshly extracted copy.

This evidence does not imply that every future Windows build, WSL release, GPU driver, AI provider, Matrix client, Tailscale policy, or upstream dependency has been end-to-end tested. Those remain integration boundaries documented in the primary security/release material.

## Documentation roles after remediation

- `README.md` — concise project overview, requirements, quick start, current highlights.
- `FEATURES.md` — canonical complete current features/install-options reference.
- `Instructions.txt` — procedural install, repair, operation, recovery, and reset guide.
- `Installer Description.txt` — plain-language capability/configuration guide.
- `CHANGELOG.md` — canonical version history.
- `SECURITY.md` — privilege, trust, network, secret, destructive-action, and supply-chain boundaries.
- `SOURCES.md` / `THIRD-PARTY-NOTICES.md` — upstream/source and redistribution boundaries.
- `RELEASE.md` — release engineering checklist.
- `BACKPORT-NOTES.md` and `*PATCH-NOTES.md` — detailed implementation lineage.
- `docs/legacy-patch-notes/hermes-wsl-foundry-v13/` — explicitly archival historical material only.
