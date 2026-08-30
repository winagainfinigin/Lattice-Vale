> **v14.5.1 current release:** `VERSION.txt` must be 14.5.1. Run `LatticeVale-Core/tests/v14.5.1-resource-policy-oom-fixtures.py`, `LatticeVale-Core/tests/v14.5.1-adaptive-hardware-matrix-fixtures.py`, `LatticeVale-Core/tests/v14.5.1-option-topology-resource-fixtures.py`, `LatticeVale-Core/tests/v14.5.1-model-aware-ollama-honcho-fixtures.py`, `LatticeVale-Core/tests/v14.5.1-delayed-gateway-reconcile-fixtures.py`, the v14.5.0 planner/foundation inheritance fixtures, inherited v14.4.85 reconcile/readiness/update-backup fixtures, and the full deterministic suite. Verify policy v9 gives a normal ~10 GiB full stack >=1024 MiB Hermes, >=512 MiB Honcho API, and >=model-aware CPU-backed managed Ollama while total generated ceilings remain within the managed budget. Verify a selected running container with Docker `OOMKilled=true` makes the audit require repair instead of reporting `HEALTHY`. Also seed a v14.5.0-style running Hermes container at 544 MiB while desired state is v9/1040 MiB: reconcile verification must reject the stale live `HostConfig.Memory`/`HostConfig.NanoCpus`, apply Compose, and pass only after the live ceiling matches. Retain v14.5.0's read-only planner contract: `./manage.sh plan` and `./manage.sh repair --plan` do not mutate managed or user-owned configuration, `compose.override.yaml` remains opaque/user-owned, and `./manage.sh audit-free` remains advisory.

> **v14.4.84 Hotfix 1:** keep `VERSION.txt` at 14.4.84. Run `LatticeVale-Core/tests/v14.4.84-hotfix1-matrix-gateway-readiness-fixtures.py` in addition to the existing v14.4.84 WSL shortcut fixture. Verify fresh install and Resume / repair both order Synapse readiness before Matrix gateway reconciliation, prove `synapse:8008` from inside `hermes-agent`, and advance the reconcile/gateway checkpoint revisions so initial-v14.4.84 installs execute the hotfix on same-version repair.

# Release checklist

## v14.5.1 current release / inherited WSL lifecycle checks

Run `LatticeVale-Core/tests/v14.4.84-wsl-shortcut-transport-fixtures.py` plus the full deterministic suite. The v14.4.84 fixture also verifies fresh-install shortcut creation uses schema 4 and the direct WSL `--cd` helper on first install, without depending on repair-only legacy-helper detection. Confirm the shipped shutdown launcher contains no targeted `wsl --terminate`; legacy owned-helper detection is exact/ownership-gated; mutating existing-stack repair performs bounded `wsl --shutdown` + `WslService` reset/re-probe before shortcut rewrite; the launch-recovery helper resets WslService after clean shutdown when elevated; no automatic HNS/vmcompute restart or distro/VHDX mutation is introduced; and the root README explicitly says the full v14.5.1 release is the version to install first.

## v14.4.83 Hotfix 2 public entry points

The canonical public Windows launchers in the release root are `installer/Install-LatticeVale.ps1` and `installer/Uninstall-LatticeVale.ps1`; `installer/verify-release.ps1` remains the release verifier. Lowercase `installer/install.ps1` and `installer/uninstall.ps1` remain packaged only for backward compatibility. All five launcher/verifier files are covered by `installer/SOURCE-SHA256SUMS.txt`.


## v14.4.82 WSL recovery return-value hotfix checks

Run `LatticeVale-Core/tests/v14.4.82-wsl-helper-exitcode-fixtures.py` and the inherited v14.4.81 WSL launch-recovery fixture. Confirm `Invoke-LatticeValeWslHostLaunchRecoveryHelper` routes child helper diagnostics through `Out-Host`, captures `[int]$LASTEXITCODE`, and returns only that scalar value. Confirm the caller still treats exit `0` as success and reaches `Rechecking Ubuntu WSL2 eligibility after host recovery`. Do not change the recovery strategy, NAT fallback boundary, distro/VHDX ownership, or the 50 GiB fresh / 10 GiB managed-repair storage thresholds.

## v14.4.81 WSL launch-recovery hotfix checks

Before packaging v14.4.81, confirm `VERSION.txt`, root/current documentation, issue metadata, CI identity checks, source manifest, repository archive, and release ZIP all identify **14.4.81**. Retain the v14.4.8 Hermes/web behavior and integration checkpoint revision 4 unchanged.

Run `tests/v14.4.81-wsl-launch-recovery-fixtures.py` plus the full deterministic suite. On a live Windows/WSL system, exercise the bounded path where a registered distro returns `Wsl/Service/E_UNEXPECTED`: verify clean `wsl --shutdown` recovery can continue the same installer run; verify other running distros require confirmation; verify persistent E_UNEXPECTED with explicitly mirrored `.wslconfig` offers a separate backed-up mirrored→NAT action; verify declining it changes nothing; verify persistent non-mirrored failure does not trigger an automatic network edit or DISM; and verify a successful recovery re-runs Ubuntu/architecture/storage/managed-stack eligibility rather than bypassing it. An explicitly requested broken `-DistroName` must receive this recovery even if another distro is healthy.

Confirm the core installer itself contains no direct `.wslconfig` networking writer and no distro unregister/import/convert/move/recreate/VHDX mutation. The normal installer may invoke the audited helper only in bounded `-LaunchRecoveryOnly` mode, which must remain usable without elevation; deeper DISM/Windows-feature repair remains a separate explicit Administrator action. Confirm the storage policy remains 50 GiB free for a fresh install and 10 GiB free for a confirmed existing installer-managed Resume / repair.

## v14.4.8 maintenance release checks

Before packaging, confirm the final release ZIP contains exactly one top-level folder named `Lattice-Vale`, then run `LatticeVale-Core/tests/v14.4.7-web-extraction-fixtures.py` as the inherited web/extraction regression in addition to the full deterministic regression suite. Confirm the local extractor is generated only for managed profiles whose effective `web.extract_backend` is `latticevale-local`; missing browser selection becomes Hermes Local Browser / Chromium only when no explicit browser/backend/gateway/environment selection owns the choice; missing `auxiliary.web_extract.timeout` becomes `360`; explicit provider/browser/timeout choices remain preserved; and the integrations checkpoint is revision 4. Confirm the complete source manifest is regenerated after all files are final. Confirm current-release identity is v14.5.1 in `VERSION.txt`, root/user docs, GitHub issue metadata, and validation workflow; confirm the current documentation set uses `PATCH-NOTES.md` rather than the removed one-off v14.x patch-note files. See [`PATCH-NOTES.md`](PATCH-NOTES.md).

For live v14.5.1 shortcut testing, verify both actions use direct WSL `--cd` lifecycle execution, return exit 0, and actually transition the stack. For existing-install repair testing, use **Shut Down LatticeVale** to stop the managed stack but leave the distro running. Confirm repair detects a legacy installer-owned targeted-termination helper, performs its bounded global WSL shutdown + `WslService` reset/re-probe, and rewrites the helper. Do not manually use `wsl --terminate <distro>` in this test path.


## v14.4.6 resource fingerprint checks

- Verify a fixture where `os.cpu_count()` reports 8 but `os.sched_getaffinity(0)` exposes 4 returns 4 from the audit CPU helper.
- Verify the helper falls back to `nproc` when affinity is unavailable and only then to `os.cpu_count()`.
- Verify state audit no longer uses `os.cpu_count()` directly for the adaptive resource fingerprint.
- Verify CPU/RAM fingerprint comparison remains exact and policy v9/Compose CPU/RAM controls remain current, including topology-aware Hermes/Honcho floors, protected managed-Ollama headroom, and the Redis/Valkey overcommit audit. Test 0-8 additional profiles, Kanban concurrency 1-8, adaptive-limits-off, native-Windows vs managed Ollama, and runtime-evaluated root startup helper behavior.
- Re-run inherited v14.4.5 repair/runtime-update, v14.4.4 metadata-race, and v14.4.3 RAM/uninstaller fixtures.

## v14.4.5 repair runtime-policy / managed-update checks

Implementation context: `PATCH-NOTES.md`.

Test a managed v14.4.4-style install whose adaptive resource fingerprint/overlay is missing or policy-v2 while `prepare_config` is already checkpointed complete. Resume / repair must regenerate policy v9, retain `compose.override.yaml` as the final layer, mark runtime reconciliation pending, and apply the changed Compose configuration to running containers before final success. A post-run `./manage.sh audit` must report `runtimePolicy CONFIGURED`.

Test both refresh-revision upgrade and version-only upgrade paths. From a public 14.4.2-style marker (`POLICY_REVISION=1`), v14.4.82 (which retains `MANAGED_REPAIR_REFRESH_REVISION=2`) must trigger the bounded installer-owned package/image/source refresh even when the age window is not due. From a fresh 14.4.5-style marker (`POLICY_REVISION=2`) with a different recorded installer version, ordinary v14.4.82 Resume / repair must remain local-first and must not pull/rebuild solely because `VERSION.txt` changed. Explicit Option 6 must still force refresh. Verify custom/unowned SearXNG/Ollama/Honcho refs remain preserved and successful refresh markers record current provenance.

Also seed an interrupted `.repair-package-refresh-pending` marker from an older bundle and resume under the current bundle. The bounded root package phase must rerun once and rewrite the pending marker with the current bundle version before user-level refresh continues. Seed the current bundle/version instead and confirm the completed root phase is not needlessly repeated. Exercise `./manage.sh restart` with a stale resource fingerprint and confirm Compose reconciliation occurs after overlay regeneration.

## v14.4.4 live metadata-repair race checks

Implementation context: `PATCH-NOTES.md`.

Confirm a Resume / repair can reconcile `data/hermes` while a SQLite-style `*-shm`/`*-wal` entry disappears between enumeration and metadata update. Confirm the vanished entry is treated as transient, but a `chown` or `chmod` failure for an entry that still exists remains fatal. Confirm the walker does not follow nested symlinks or cross nested mount boundaries, clean-install behavior remains unchanged, and all inherited v14.4.3 RAM/uninstaller regressions still pass.

## v14.4.3 RAM-efficiency / uninstall-hardening inherited checks

Implementation context: `PATCH-NOTES.md`.

Verify the inherited v14.4.3 behavior remains intact: a clean adaptive install generates resource policy v9, an existing policy-v2/v3/v4/v5/v6/v7/v8 adaptive install regenerates to v9 on repair/start, the WSL-visible resource fingerprint is persisted, `compose.override.yaml` remains last, and Honcho PostgreSQL retains `max_connections=200`. Verify LatticeVale does not write global WSL `memory` or `autoMemoryReclaim` settings for this feature.

Exercise/fixture the preservation-first uninstaller cases: (1) Docker runtime evidence + unavailable Docker daemon aborts before Windows integration cleanup; (2) modified/unowned same-name tasks or shortcuts remain untouched and their referenced support files remain present; (3) installer-owned `OLLAMA_HOST` restore broadcasts `WM_SETTINGCHANGE`; (4) non-LatticeVale same-name firewall state is preserved; (5) another recognizable stack prevents removal of shared distro-level dockerd logging/policy state. Regenerate `installer/SOURCE-SHA256SUMS.txt` only after all release files are final and verify the complete extracted tree.

## v14.4.2 documentation/release consistency checks

Confirm current-release version metadata and documentation identify v14.4.2; inherited regression fixtures accept v14.4.2 without changing runtime expectations; the package root remains `Lattice-Vale`; the exact manifest covers the entire extracted release; and a freshly extracted ZIP passes `installer/verify-release.ps1`. Installer/runtime source must remain unchanged for this patch.

## v14.4.1 release-layout checks

Confirm the repository root contains only conventional repository files (`.gitattributes`, `.gitignore`, `README.md`, `LICENSE`) plus directories; public entry points and `SOURCE-SHA256SUMS.txt` are under `installer/`; substantive documentation is under `docs/`; the moved launchers resolve `LatticeVale-Core/` and `tools/` from the parent release root; clean-host source recognition accepts the new layout; the exact manifest covers the entire extracted release; and a freshly extracted ZIP passes `installer/verify-release.ps1`. No stack-runtime source should change solely for this packaging patch.

## v14.4.0 stable-promotion release checks

Confirm the runtime/configuration source remains behaviorally unchanged from the audited v14.3.43 line except for version/test/release metadata. Confirm all documentation-audit corrections are present, `FEATURES.md` is included and cross-linked, the exact source manifest is regenerated after final edits, the final ZIP has one top-level `Lattice-Vale` folder, and the external ZIP SHA-256 is published with the release.

## v14.3.43 release checks

Verify the clean-host scanner handles Exec and non-Exec Scheduled Task actions under StrictMode, never directly dereferences action-type-specific fields, and keeps all v14.3.42 destructive/preservation boundaries unchanged.

## v14.3.42 clean-host reset release checks

Verify the clean-host reset remains opt-in/dry-run-first; normal install/uninstall must not invoke it. Verify WSL unregister/package removal is gated by `-RemoveWslRuntime`, legacy Foundry cleanup by `-RemoveLegacyHermesFoundry`, source deletion by validation plus `-DeleteLatticeValeSource`, and Tailscale cleanup by matching known bridge backends. Verify no code disables Hyper-V/HypervisorPlatform/VirtualMachinePlatform or directly deletes HNS networks.

## v14.3.41 WSL host-safety release checks

Release-specific implementation context is consolidated in `PATCH-NOTES.md`, with the v14.3.41 `CHANGELOG.md` entry remaining canonical for version chronology. For repair/update releases, verify that automatic maintenance does not prune Docker Engine-global images/build cache that may belong to unrelated projects.

For Kanban/skill-policy releases, verify both a fresh install and an older managed stack whose `integrations` checkpoint is already complete. Confirm that the migration re-runs without changing user-owned profile configs; valid external profile names remain valid routing targets; fallback automatic assignment selects only a managed profile or the configured orchestrator; explicit `skills.write_approval` is preserved; worker task-context guards do not interfere with dispatcher-created workers; and completed artifacts remain discoverable through durable task attachments. Regression fixtures must use non-machine-specific usernames, paths, profile names, and model identifiers.

LatticeVale releases are source-only. Do not add vendor installers, saved container images, model blobs, binary packages, generated secrets, WSL data, or runtime backups to a release.

Before publishing a release:

1. Review `CHANGELOG.md`, `SECURITY.md`, `SOURCES.md`, `CONTRIBUTING.md`, and `LatticeVale-Core/AUDIT.md`. `CHANGELOG.md` is the canonical version history. Detailed downstream audit/implementation notes are consolidated in `PATCH-NOTES.md`; they must point back to the canonical release entry and must not define a conflicting version identity. Confirm requirements text still matches `LatticeVale-Core/compatibility.conf`.
2. Confirm `LatticeVale-Core/VERSION.txt` matches the intended tag.
3. Run the Linux regression/static suite or let GitHub Actions do so.
4. Parse every PowerShell entry point on Windows (the GitHub Actions Windows job does this).
5. Run `tools\New-SourceManifest.ps1` **after all source/documentation edits are final**.
6. Run `installer\verify-release.ps1` and confirm every manifest entry verifies.
7. Scan the release tree for unexpected `.exe`, `.msi`, `.dll`, package/archive, bytecode, credential, data, backup files, private keys, access tokens, and machine-specific private state. If publishing on GitHub, enable secret scanning/push protection where available.
8. Create the versioned release ZIP from the reviewed tree without adding generated third-party installers or images. The ZIP filename may contain the release version, but the archive must contain exactly one top-level folder named `Lattice-Vale` (never a versioned root-folder name).
9. Extract that ZIP into a fresh directory and rerun source-manifest/static validation against the extracted copy.
10. Recheck all installer-managed update pins/channels against the versions this release intends to support: Hermes, Matrix/Synapse, QMD, the audited Honcho commit, SearXNG, managed Ollama, default Ollama models/capabilities, Docker package policy, and the pinned NVIDIA Container Toolkit package set. Record deliberate version changes in `SOURCES.md`/`CHANGELOG.md`. A newer release must change the corresponding bundle pin/source reference if **Update / repair installer-managed software** is expected to move an existing stack to that newer component version. For native Ollama, verify both missing-model `/api/pull` behavior and pre-infrastructure embedding validation without assuming a Compose network already exists.
11. For changes to native Windows Ollama, Windows relays, WSL networking, firewall handling, startup/shutdown integration, or Hermes web-provider behavior, execute `docs/WINDOWS-INTEGRATION-TEST-MATRIX.md` on representative real Windows + WSL systems. Record which rows were actually exercised; fixtures/static assertions do not count as end-to-end execution. When validating SearXNG, distinguish local HTTP/provider failure from a successful search response that contains zero results because upstream engines are temporarily CAPTCHA/rate-limit/suspension blocked. Do not classify a single empty successful search as a release regression; validate the local JSON API/provider wiring separately and validate known-URL extraction independently.
    For the v14.3.41 ownership rule, verify normal configuration/runtime source contains no direct writer for `[wsl2] networkingMode` and that a healthy externally configured mirrored topology remains usable without mutation. For v14.4.81+, additionally verify that only the bounded WSL launch-recovery helper can offer a backed-up mirrored-to-NAT fallback after persistent `E_UNEXPECTED`, with explicit user approval, before any deeper DISM/feature repair.
12. If GPU acceleration is claimed as live-tested, smoke-test the exact release on representative supported NVIDIA and/or AMD WSL hardware. Device-node/runtime detection in fixtures is not a substitute for vendor hardware compatibility.
13. Exercise adaptive limits on at least one constrained and one larger WSL VM when changing the resource policy.
14. When changing an installer-managed component version or updater behavior, test **Update / repair installer-managed software** against an existing managed stack. Confirm the mandatory pre-update backup completes before refresh, the declared bundle pins are applied, persistent Matrix/Postgres/Hermes/QMD/Honcho/Ollama data is preserved, and an interrupted managed refresh can be continued by Resume / repair. Do not claim automatic rollback: the pre-update backup is a recovery asset, while normal stage verification still determines success.
15. Publish the final ZIP SHA-256 in the GitHub release notes.
16. If the release is a downstream/customized build, label it clearly as modified, preserve the MIT notice, document system-specific assumptions, and do not reuse upstream release hashes for changed content.

Do not claim Windows/WSL/Tailscale/Element/GPU end-to-end testing unless that exact release was actually exercised on those live platforms.

### Source overwrite patch cleanup

When applying an overwrite patch on top of a development/intermediate checkout, extract the patch and then run `pwsh ./tools/Finalize-LatticeVale-OverwritePatch.ps1` from the repository root before release verification. This removes obsolete source files listed in `installer/PATCH-DELETE.txt` that ZIP extraction cannot delete by itself. Clean release archives are unaffected; missing paths are ignored.
