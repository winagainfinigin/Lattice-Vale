# v14.4.6 adaptive resource fingerprint audit

v14.4.6 fixes a false-stale runtime-policy report found on a WSL instance configured for 4 processors on an 8-logical-CPU Windows host. The adaptive generator and `manage.sh` use `nproc`, which reflects CPUs available to the WSL process, but `state-audit.py` used Python `os.cpu_count()`, which can report a broader host/logical count. That made `.latticevale-resource-state` (`CPUS=4`) disagree with audit even when the live WSL CPU count and RAM fingerprint exactly matched. Audit now derives process-visible CPU count from `os.sched_getaffinity(0)`, falls back to `nproc`, and only then to `os.cpu_count()`. RAM comparison remains exact; this patch does not hide real WSL memory-allocation drift. v14.4.6 also removes bundle-version-only managed refresh: `INSTALLER_VERSION` remains provenance, while the 30-day gate, `MANAGED_REPAIR_REFRESH_REVISION`, missing legacy state, or explicit Option 6 determine whether package/image/source refresh runs. This preserves direct public 14.4.2→14.4.6 convergence through revision 1→2 and policy v2→v3 while avoiding redundant 14.4.5→14.4.6 rebuilds.

# v14.4.5 repair runtime-policy/update convergence audit

v14.4.5 fixes the repair-convergence gap found during a real v14.4.4 Resume / repair: adaptive resource policy v3 could remain `PARTIAL` because the generator lived in `prepare_config` while an older completed checkpoint allowed that stage to be skipped. Repair now performs an explicit uncheckpointed adaptive runtime-policy reconciliation, fingerprints policy v3 against current WSL CPU/RAM, verifies the RAM-specific overlay controls, marks infrastructure/full-stack reconciliation pending when the overlay changes, and fails final configuration rather than reporting success with stale runtime policy. v14.4.5 also briefly introduced bundle-version-driven managed refresh; v14.4.6 supersedes that trigger with the explicit refresh-revision/age/force model while preserving user-owned overrides.

v14.4.4's metadata-race hardening remains inherited: root-assisted reconciliation uses a `find -P -xdev` bounded walk, skips chmod on symlinks, tolerates only an operation failure whose exact path vanished, and remains fatal for still-existing entries.

v14.4.3 adaptive RAM policy v3 and preservation-first uninstaller hardening are inherited unchanged, including Honcho PostgreSQL `max_connections=200`, user-owned global WSL memory policy, final-layer `compose.override.yaml`, Docker-runtime fail-closed uninstall, and retained-task/shortcut support-file preservation.

## v14.4.2 documentation/release consistency audit

v14.4.2 updates documentation, current version/validation metadata, inherited regression compatibility, and release integrity data only. Installer and stack-runtime behavior remain unchanged from v14.4.1/v14.4.0; all inherited safety boundaries remain in force.

## v14.4.1 release-layout audit

v14.4.1 is a packaging/layout-only patch over the validated v14.4.0 runtime. Public entry points move to `../installer/`, substantive project documentation is consolidated under `../docs/`, and path resolution/tests/manifests are updated accordingly. No intended stack-runtime behavior is added; all inherited safety boundaries remain in force.

v14.3.43 adds defensive optional-property inspection for heterogeneous Windows Scheduled Task actions. The reset remains dry-run-first and ownership-gated; this follow-up does not broaden destructive scope.

v14.3.42 adds an explicit destructive-reset boundary without changing normal installer runtime behavior. The reset tool is dry-run-first, ownership-gated, never automatic, preserves shared Hyper-V/VMP/HNS/Tailscale/Obsidian state, and reserves WSL unregister/package removal for the explicit `-RemoveWslRuntime` path.

v14.3.41 adds a release invariant: normal installer/runtime code must not write or switch global WSL `[wsl2] networkingMode`. Existing externally configured mirrored mode may be observed/used if healthy; E_UNEXPECTED+mirrored recovery is isolated to the explicit Administrator repair helper, which backs up `.wslconfig` and tries NAT before broader component repair.

- Inherited v14.3.39 existing-install QC: all six managed-stack menu paths were traced through Windows selection, saved-option handling, Linux checkpoint controls, component disable/reconcile behavior, recovery backups, and update backup ordering. One shared-Docker compatibility defect was found and corrected: mutating repair modes no longer run engine-global `docker image prune` or `docker builder prune`; automatic cleanup is restricted to proven LatticeVale-owned disposable state.
- v14.3.38 Kanban/skill policy audit: the shared board, singleton dispatcher lock, dependency/decomposition flow, cross-profile workers, and durable completion artifacts are preserved. The new plugin handles only model-facing context errors. It discovers all real profiles for routing validation, modifies only installer-managed profiles, shallow-repairs only deterministic arguments, blocks ambiguous worker lifecycle misuse, and retains hard-stop guardrails. The integrations checkpoint revision forces adoption on clean and repair/update paths without requiring a software refresh.
- v14.3.37 retains the v14.3.30 shared `install-options.json` policy architecture but makes WSL networking capability-first: a verified NAT/private-relay path is preserved, an already-working mirrored topology is supported, and switching global `.wslconfig` to mirrored is an explicit default-No fallback rather than the recommended automatic direction.
- Controlled Update / repair is explicit and preservation-first: it is available only for an existing installer-managed stack, requires the installed managed backup command to succeed before refresh, bypasses the normal age gate for that run, and then uses the same ownership-aware package/image/source convergence plus live stage verifiers as repair. It does not reinterpret separately owned native Windows Ollama or unproven custom image/source overrides as installer-owned.
- WSL host prerequisite decisions are functional-first on modern Store/MSI WSL2. Optional-feature state remains diagnostic; bounded enumeration, WSL2 version, and an actual selected-distro launch probe decide whether the installer may proceed. The explicit host-repair helper probes before mutation and preserves distro registration/VHDX ownership.
- Compatibility hardening separates successful WSL STDOUT from diagnostic STDERR, supports arbitrary registered Ubuntu distro names after Linux identity verification, and normalizes supported local fixed-volume/volume-GUID storage without drive-letter-only assumptions.
- Installer-owned stale Dashboard/Matrix Windows relay tasks/processes are proven by exact script/config ownership and stopped before bridge-port allocation so canonical ports `19119`/`18008` can be reclaimed. Unknown listeners remain untouched.
- Secondary Matrix profile provisioning/cross-signing may remain explicitly pending and retryable without making the whole clean install or Resume/repair stage fail after resources have already been safely provisioned. Exact-profile gateway recovery is restricted to the proven `/run/service/gateway-<profile>` s6 slot. Fresh required Matrix identity/recovery-key transactions remain strict.
- v14.3.38 release-build validation ran all 94 `tests/*-fixtures.py` regressions individually with zero failures, plus Bash syntax, Python AST parsing without bytecode, PowerShell ASCII/LF source-policy checks, GitHub/YAML parsing, and the 12-service Compose parse. The aggregate `static-audit.py` and long interruption simulations remain CI/target-environment checks when a constrained build runner cannot complete them within its execution window; a timeout is not recorded as a pass.

- v14.3.29 replaces fragile uninstall discovery shell serialization with direct WSL account/path probes and makes native Ollama model validation establish and verify the relay before any model API call. An alive-but-unhealthy relay is actively restarted once and model absence is distinguished from relay unavailability.
- v14.3.28 retains the v14.3.26 stabilization behavior, corrects the uninstaller single-item distro menu defect, and aligns uninstall stack discovery with installer Resume/repair evidence so interrupted/partial installs are not falsely reported as absent.

## Retained v14.3.26 stabilization audit

This release treats the native-Windows-Ollama subsystem as an advanced optional integration and focuses on failure containment rather than adding topology branches. Static/fixture validation cannot emulate Windows Task Scheduler, Hyper-V firewall, real WSL IP churn, sleep/wake, VPN software, or endpoint security. Those boundaries remain target-system tests and are enumerated in `../docs/WINDOWS-INTEGRATION-TEST-MATRIX.md`.

Hardening in this release: continuous Windows-relay topology refresh without waking a stopped distro; exact installer-owned firewall-rule reconciliation after address changes; WSL-local watchdog recovery with systemd supervision only when systemd is already active; bounded 64-connection relay concurrency; connect/session/idle timeouts; bounded relay diagnostics; and explicit observation of both directions of C# stream-copy tasks. The use of PowerShell `Add-Type` remains source-visible and is documented as an AV/EDR compatibility consideration rather than hidden or bypassed.

# v13.16.0 Audit — Comprehensive Repair + Aged-Install Maintenance

## Repair-only scope

v13.16.0 keeps the v13.15 clean-install stages and options intact. `repairMaintenance` is
false for fresh installs and is enabled only for an already installer-managed stack in
Resume/change/reconfigure/advanced repair modes. The maintenance functions run outside
normal stage checkpoints so a same-version repair can still address newly accumulated
cache/log/database drift.

## Storage and age behavior

Repair reports WSL-root free space, total stack footprint, the largest persistent LatticeVale
paths, and Docker daemon storage usage before cleanup. Automatic reclamation is limited to
APT cache/stale LatticeVale staging, Docker dangling images, unused Docker build cache older
than 30 days, superseded installer `pre-v*` configuration snapshots beyond the newest
eight, and an oversized installer event-history file. User-created backups and persistent
application/model/database/crypto data are excluded. If safe cleanup still leaves less
than 2 GiB logically free inside WSL, the repair fails safely rather than deleting
intentional data.

All twelve Compose services merge the same bounded Docker `local` logging policy
(`max-size=20m`, `max-file=5`). This prevents future unbounded default json-file log
growth while keeping normal Docker log access.

## Database maintenance

When selected database containers are running, repair invokes bounded PostgreSQL `VACUUM
(ANALYZE)` for Synapse and Honcho. Failures warn and do not trigger destructive fallback.
There is no `VACUUM FULL`, retention purge, database recreation, or Matrix/Honcho data
deletion in this maintenance path.

## WSL VHD boundary

The installer audits Linux-visible logical space but does not claim that this equals the
physical Windows `ext4.vhdx` size. v13.16.0 intentionally does not automate VHD sparse
conversion, compaction, relocation, or destructive resizing. The existing Windows
host-partition repair reserve remains a prerequisite because logical cleanup inside WSL
does not guarantee immediate host-file shrinkage.

## Validation

- Clean-install stage/order regression coverage retained.
- Dedicated v13.16 repair-maintenance fixture: pass.
- Bash syntax: pass.
- Python compilation: pass.
- Compose YAML parse with 12 services and bounded local logging: pass.
- Deterministic/static suite: **39/39 pass** before packaging (excluding the two
  historical environment-dependent interruption simulations).

---

## Retained v13.15.0 audit history

# v13.15.0 Audit — Matrix Trust + Tailscale Remote Access

## Evidence basis

This release follows the successful v13.14.0 clean install and `./manage.sh verify` HEALTHY result, plus live evidence that the on-demand/triggerless Windows relay could be absent while Synapse itself remained healthy. It also incorporates the observed Element warning that Hermes messages were encrypted by a device not verified by its owner.

## Startup / WSL lifetime boundary

No fake Linux keepalive process is added. The user's launcher or `./manage.sh start` owns starting WSL/Hermes. The existing Store/MSIX WSL 2.5.4+ `[general] instanceIdleTimeout=-1` option remains a supported WSL service-instance lifetime policy and is still separate from Windows logon startup.

The Windows-native Tailscale relay is different from the stack: it is inexpensive Windows user-space plumbing and is registered at logon whenever remote exposure is selected. In on-demand mode it binds its localhost ports but cannot wake WSL or call the stack-start helper. It waits for the user-started backend and prefers direct TCP health checks against its cached WSL target before any WSL discovery.

## Tailscale remote Matrix design

Tailscale remains Windows-native and Matrix remains tailnet-only. LatticeVale uses Tailscale Serve with `--bg`, not Funnel. Matrix's installer default is standard HTTPS 443, giving clients `https://<node>.<tailnet>.ts.net`; Dashboard remains 9443. Resume / repair removes only the old installer-owned 8448 Matrix mapping when migrating that historical default to 443, while preserving intentionally customized ports and unrelated Serve configuration.

The Matrix `server_name` remains `hermes.local`; only Synapse `public_baseurl` follows the working Tailscale client URL. The proven Windows-native relay remains necessary because the prior Windows `netsh portproxy` path could be locally reachable yet return HTTP 502 when used as the Tailscale Serve backend.

## Matrix E2EE / device trust

Hermes's current Matrix documentation recommends `MATRIX_RECOVERY_KEY` when cross-signing is enabled. It states that Hermes imports the cross-signing keys from secure secret storage and signs its current device on startup. Hermes also supports `MATRIX_RECOVERY_KEY_OUTPUT_FILE` for a newly bootstrapped one-time recovery key, created with mode 0600 and not overwritten.

Fresh v13.15 Matrix bootstrap uses that supported path: the room is encrypted from creation, `MATRIX_E2EE_MODE=required`, the stable bot device remains `<legacy Matrix bot device ID>`, the one-time key is captured into installer secrets and removed from the one-time path, then Hermes is restarted and the cross-signing verification log is required.

Repair does not delete `crypto.db` or automatically rotate account/device/token/room state to obtain a missing legacy key. If an older identity already bootstrapped cross-signing and cannot emit a replacement key, the trust step is marked pending while unrelated repair proceeds.

## Validation

- Bash syntax: pass.
- Python compilation: pass.
- Compose YAML parse: pass.
- Deterministic/static fixture suite (excluding the two historical long-running interruption simulations): **38/38 pass** before packaging.
- Dedicated v13.15 Matrix/Tailscale fixture: pass.
- v13.14 root-HOME helper/lifecycle regression fixture updated for the new relay policy: pass.
- Static PowerShell variable-before-colon scanning remains enabled for both shipped PowerShell entrypoints.

The Linux build environment cannot faithfully execute Windows Task Scheduler, the real WSL VM lifecycle, Windows Tailscale, or Element clients; those remain target-system runtime checks.

---

## Retained v13.14.0 audit history

# v13.14.0 Audit — Clean-Install Lifecycle Hardening

## Evidence basis

The release is based on the clean v13.13.4 installation troubleshooting handoff plus a source audit of the exact v13.13.4 ZIP. The handoff proved that the stack itself could start and Synapse could return HTTP 200, while `/usr/local/sbin/hermes-stack-start` failed as root by attempting `/root/hermes-stack`. It also showed the distro stopping at roughly the one-minute boundary and the Tailscale relay becoming unavailable only after its WSL backend disappeared.

## Root-invocation helper defect

The v13.13.4 bootstrap generated the helper from an unquoted root-run heredoc. Inside that heredoc, the Compose command referenced `$HOME/hermes-stack`; generator-time expansion therefore used root's home. v13.14.0 persists the selected user's exact stack directory and passes it to `bash -c` as `$1` while Compose runs through `runuser`. A regression fixture expands the actual shipped heredoc with `HOME=/root` and rejects `/root/hermes-stack`.

## WSL lifetime policy

Current WSL distinguishes the distro/instance idle timeout (`[general] instanceIdleTimeout`) from the VM-level `[wsl2] vmIdleTimeout`. Store/MSIX WSL 2.5.4 introduced `general.instanceIdleTimeout`. v13.14.0 offers `instanceIdleTimeout=-1` only when that capability is present, preserves unrelated `.wslconfig` content, backs up an existing file before mutation, restarts WSL through `wsl --shutdown`, and performs a 75-second no-command persistence test. It does not force `vmIdleTimeout=-1`.

## Startup-policy separation

The user preference and failure evidence require service persistence without secretly restoring full stack startup at Windows sign-in. Fresh auto-start therefore defaults to No. The Tailscale relay receives an at-logon trigger and `-EnsureDistroRunning` only when full stack auto-start is selected. Otherwise it is registered triggerless/passive. The relay checks `wsl --list --running --quiet` before any in-distro IP probe, so its passive refresh path cannot wake a stopped distro. `manage.sh start/stop/restart` coordinates the triggerless relay through `schtasks.exe`.

## Online cross-checks retained

- Docker's current Ubuntu Engine instructions still support Ubuntu 22.04, 24.04, and 26.04 and the same official package set used by LatticeVale.
- Hermes Agent `v2026.8.16` / v0.20.2 is the latest stable Hermes release at final audit time, so clean installs are pinned to `nousresearch/hermes-agent:v2026.8.16`.
- Synapse v1.158.0 remains the latest stable release while v1.159.0rc1 is pre-release, so the Synapse stable pin is unchanged.
- Tailscale Serve's documented reverse-proxy model targets a service on the Windows host (for example `127.0.0.1`), consistent with retaining the proven Windows-native localhost relay.

## Validation scope

The bundle is validated with Bash syntax checks, Python compilation, Compose YAML parsing, deterministic/static regression fixtures, the direct helper-generation fixture, variable-before-colon scans for both PowerShell entrypoints, and ZIP integrity/hash verification. The Linux build environment cannot faithfully execute real Windows Task Scheduler, WSL VM lifecycle, Windows Tailscale, or a full destructive Windows/WSL clean install; those remain runtime validations for the target Windows system.

Historical patch/version audit details are consolidated in the `../docs/CHANGELOG.md`.
