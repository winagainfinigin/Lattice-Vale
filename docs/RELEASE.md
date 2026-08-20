# Release checklist

## v14.4.1 release-layout checks

Confirm the repository root contains only conventional repository files (`.gitattributes`, `.gitignore`, `README.md`, `LICENSE`) plus directories; public entry points and `SOURCE-SHA256SUMS.txt` are under `installer/`; substantive documentation is under `docs/`; the moved launchers resolve `LatticeVale-Core/` and `tools/` from the parent release root; clean-host source recognition accepts the new layout; the exact manifest covers the entire extracted release; and a freshly extracted ZIP passes `installer/verify-release.ps1`. No stack-runtime source should change solely for this packaging patch.

## v14.4.0 stable-promotion release checks

Confirm the runtime/configuration source remains behaviorally unchanged from the audited v14.3.43 line except for version/test/release metadata. Confirm all documentation-audit corrections are present, `FEATURES.md` is included and cross-linked, the exact source manifest is regenerated after final edits, the final ZIP has one top-level `LatticeVale` folder, and the external ZIP SHA-256 is published with the release.

## v14.3.43 release checks

Verify the clean-host scanner handles Exec and non-Exec Scheduled Task actions under StrictMode, never directly dereferences action-type-specific fields, and keeps all v14.3.42 destructive/preservation boundaries unchanged.

## v14.3.42 clean-host reset release checks

Verify the clean-host reset remains opt-in/dry-run-first; normal install/uninstall must not invoke it. Verify WSL unregister/package removal is gated by `-RemoveWslRuntime`, legacy Foundry cleanup by `-RemoveLegacyHermesFoundry`, source deletion by validation plus `-DeleteLatticeValeSource`, and Tailscale cleanup by matching known bridge backends. Verify no code disables Hyper-V/HypervisorPlatform/VirtualMachinePlatform or directly deletes HNS networks.

## v14.3.41 WSL host-safety release checks

Release-specific implementation context is in `WSL-HOST-SAFETY-PATCH-NOTES.md`, `EXISTING-INSTALL-QC-PATCH-NOTES.md`, `KANBAN-SKILL-POLICY-PATCH-NOTES.md`, and the v14.3.41 `CHANGELOG.md` entry; `CHANGELOG.md` remains canonical for version history. For repair/update releases, verify that automatic maintenance does not prune Docker Engine-global images/build cache that may belong to unrelated projects.

For Kanban/skill-policy releases, verify both a fresh install and an older managed stack whose `integrations` checkpoint is already complete. Confirm that the migration re-runs without changing user-owned profile configs; valid external profile names remain valid routing targets; fallback automatic assignment selects only a managed profile or the configured orchestrator; explicit `skills.write_approval` is preserved; worker task-context guards do not interfere with dispatcher-created workers; and completed artifacts remain discoverable through durable task attachments. Regression fixtures must use non-machine-specific usernames, paths, profile names, and model identifiers.

LatticeVale releases are source-only. Do not add vendor installers, saved container images, model blobs, binary packages, generated secrets, WSL data, or runtime backups to a release.

Before publishing a release:

1. Review `CHANGELOG.md`, `SECURITY.md`, `SOURCES.md`, `CONTRIBUTING.md`, and `LatticeVale-Core/AUDIT.md`. `CHANGELOG.md` is the canonical version history. Detailed downstream audit/implementation notes may remain in `*PATCH-NOTES.md`, but they must point back to the canonical release entry and must not define a conflicting version identity. Confirm requirements text still matches `LatticeVale-Core/compatibility.conf`.
2. Confirm `LatticeVale-Core/VERSION.txt` matches the intended tag.
3. Run the Linux regression/static suite or let GitHub Actions do so.
4. Parse every PowerShell entry point on Windows (the GitHub Actions Windows job does this).
5. Run `tools\New-SourceManifest.ps1` **after all source/documentation edits are final**.
6. Run `installer\verify-release.ps1` and confirm every manifest entry verifies.
7. Scan the release tree for unexpected `.exe`, `.msi`, `.dll`, package/archive, bytecode, credential, data, backup files, private keys, access tokens, and machine-specific private state. If publishing on GitHub, enable secret scanning/push protection where available.
8. Create the versioned release ZIP from the reviewed tree without adding generated third-party installers or images. The ZIP filename may contain the release version, but the archive must contain exactly one top-level folder named `LatticeVale` (never a versioned root-folder name).
9. Extract that ZIP into a fresh directory and rerun source-manifest/static validation against the extracted copy.
10. Recheck all installer-managed update pins/channels against the versions this release intends to support: Hermes, Matrix/Synapse, QMD, the audited Honcho commit, SearXNG, managed Ollama, default Ollama models/capabilities, Docker package policy, and the pinned NVIDIA Container Toolkit package set. Record deliberate version changes in `SOURCES.md`/`CHANGELOG.md`. A newer release must change the corresponding bundle pin/source reference if **Update / repair installer-managed software** is expected to move an existing stack to that newer component version. For native Ollama, verify both missing-model `/api/pull` behavior and pre-infrastructure embedding validation without assuming a Compose network already exists.
11. For changes to native Windows Ollama, Windows relays, WSL networking, firewall handling, or startup/shutdown integration, execute `docs/WINDOWS-INTEGRATION-TEST-MATRIX.md` on representative real Windows + WSL systems. Record which rows were actually exercised; fixtures/static assertions do not count as end-to-end execution.
    For v14.3.41+ specifically, verify normal installer runtime contains no path that writes `[wsl2] networkingMode`, verify a healthy externally configured mirrored topology remains usable without mutation, and verify the host-repair helper performs its backed-up NAT recovery before DISM when `E_UNEXPECTED` and mirrored mode coincide.
12. If GPU acceleration is claimed as live-tested, smoke-test the exact release on representative supported NVIDIA and/or AMD WSL hardware. Device-node/runtime detection in fixtures is not a substitute for vendor hardware compatibility.
13. Exercise adaptive limits on at least one constrained and one larger WSL VM when changing the resource policy.
14. When changing an installer-managed component version or updater behavior, test **Update / repair installer-managed software** against an existing managed stack. Confirm the mandatory pre-update backup completes before refresh, the declared bundle pins are applied, persistent Matrix/Postgres/Hermes/QMD/Honcho/Ollama data is preserved, and an interrupted managed refresh can be continued by Resume / repair. Do not claim automatic rollback: the pre-update backup is a recovery asset, while normal stage verification still determines success.
15. Publish the final ZIP SHA-256 in the GitHub release notes.
16. If the release is a downstream/customized build, label it clearly as modified, preserve the MIT notice, document system-specific assumptions, and do not reuse upstream release hashes for changed content.

Do not claim Windows/WSL/Tailscale/Element/GPU end-to-end testing unless that exact release was actually exercised on those live platforms.
