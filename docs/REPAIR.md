# LatticeVale 14.6.6 Resume / Repair

> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.

> **v14.6.6 Tailscale correction (carried forward from the v14.6.5 corrective overlay):** Dashboard and Matrix remote HTTPS may validate over IPv4, IPv6, or both. Certificate validation and direct-IP/no-proxy testing remain enabled. Windows listener enumeration is advisory when an authenticated HTTPS path and the selected application checks succeed; successful Serve mappings are retained rather than removed after a listener-only false-negative.


> **v14.6.2 Hotfix:** fixes the original v14.6.2 Linux bootstrap staging typo that duplicated an `install -m 0644 ... \` command immediately before the `compatibility.conf` copy. The defect could stop Resume / repair or Update / repair with `install: target .../compatibility.conf: Not a directory`. The hotfix changes no schema, data layout, managed-update policy, database-major bounds, DirectML/PyTorch compatibility envelope, or explicit user overrides. Apply the hotfix and rerun the installer; no uninstall or data reset is required.


> **v14.6.6 update policy:** Existing-install Option 1 checks current supported Ubuntu/Docker package candidates, installer-owned Docker image registry digests, the QMD npm release, and the official Honcho stable tag on every run, without a 30-day delay. It performs the existing compatibility-bounded managed refresh only when an update/missing managed component is established; otherwise it uses the local-first recovery path. Remote errors are reported as unverified and do not trigger a speculative refresh. Option 6 remains the explicit forced refresh. Selected user overrides, database major limits, native Windows Ollama ownership, and persistent state remain preserved. The deprecated `MANAGED_REPAIR_REFRESH_DAYS` value is retained for older metadata compatibility but is not a refresh trigger.


## Schema 21/22 to schema 23 migration

Resume / repair accepts recognized schema-21, schema-22, and schema-23 managed state and normalizes it to schema 24 without resetting application data. Schema-23 state migrates to schema 24 without adding a user-facing Matrix relay-limit setting. Interim schema-24 `tailscaleMatrixMaxConnections` data is tolerated, ignored, and removed from newly written installer options. Older DirectML state that lacks `directmlFallbackPolicy` inherits its prior Ollama backend as the text fallback. Existing state without `useGpuAcceleration` preserves the historical GPU-enabled behavior; after the user explicitly disables GPU acceleration, repair preserves CPU-only operation. Policy v13 is regenerated from current WSL resources and enabled service topology.

## Use Option 1 for an existing installation

Launch the **full 14.6.6 release** and select **Resume / repair installation**. The repair engine proves managed ownership, reads historical installer metadata, creates the required rollback backup before managed-source refresh, stages the current management layer, migrates schemas, regenerates derived architecture state, and resumes from the earliest stale/incomplete dependency.

## Other mutating maintenance modes

Option 1 remains the recommended general repair path, but the cumulative migration prerequisite is shared by all mutating modes. On a recognized older stack, Options **2 (Change installed components)**, **4 (Reconfigure providers/profiles)**, **5 (Advanced recovery)**, and **6 (Update / repair installer-managed software)** also migrate the managed schema/layer first when required. Options **3** and **8** never migrate because they are read-only; Option **7** stays isolated cleanup and does not enter ordinary repair/migration stages.

## Repair dependency order

v14.6.5 retains the principal dependency chain introduced by v14.6.0 and hardened through v14.6.1:

1. durable `install-options.json` schema/migration;
2. Windows hardware snapshot;
3. live WSL hardware capabilities;
4. backend capabilities/health and adapter selection;
5. canonical runtime resource policy;
6. generated Compose/service configuration;
7. service/runtime verification;
8. Windows integrations.

A changed upstream layer invalidates only its dependent derived layers. Persistent application data and user-owned overrides are not treated as disposable derived state.

## Generated-state rule

A current LatticeVale component must accept the state generated by another current component. v14.6.6 retains the v14.6.0 canonical architecture and v14.6.2 managed-upstream policy and validates current options through the canonical schema implementation and validates resource-policy generation with the same canonical memory-budget API used by verification and state audit. Runtime backend health is tracked separately from policy topology: a safe DirectML-to-Ollama fallback does not make the just-generated policy stale unless a resource-relevant topology/acceleration fact actually changed.

Future schemas fail closed. Known historical schemas are migrated by the installer rather than accepted blindly.

## Safe repeated repair

Option 1 is designed to converge. Re-running it after a successful repair should normally verify healthy state or perform only newly stale work; it must not recreate persistent identities or databases merely because a derived hardware/policy fingerprint changed.

Runtime supervisor state is also repairable. If Hermes persistent profile state exists but an exact s6 gateway slot under `/run/hermes-service/gateway-*` is missing after container startup, Resume / repair waits boundedly for the upstream boot reconciler and then re-registers only that exact slot through Hermes' runtime service-manager API. Missing ephemeral s6 registration is not treated as a reason to delete/recreate the profile or fail an otherwise recoverable installation.

Hermes gateway migration runs at finalization and is reconciled at stack start. Before replaying migration, LatticeVale gives a just-started gateway a bounded settle window and proves whether the current default host gateway is already converged by checking its exact s6 PID, fresh `gateway_state.json`, the complete installer-managed non-standalone `served_profiles` set, and PID stability. A migration command timeout/nonzero result is accepted only after another bounded settle window proves that exact live convergence; the status alone is never treated as success. Matrix-enabled routes additionally require the correct runtime adapter to be connected (`matrix` on default/standalone gateways, `<profile>:matrix` on the shared host gateway). `.installer-gateway-multiplex-owned` records ownership but is not accepted as live-health proof; a missing marker can be restored after live convergence is proven, while a stale marker causes verification/migration recovery rather than a false healthy result. Already healthy connected gateways are preserved without unnecessary restart/remigration. LatticeVale records and restores only the temporary `gateway.standalone` values it sets during provisioning. A preexisting `gateway.standalone: true` remains a user choice and keeps its exact independent gateway. Because Hermes migration applies to the whole profile home, repair pauses migration when an active non-standalone gateway belongs to an unowned profile. Profiles, credentials, Matrix/E2EE state, data, and existing profile filesystem layout remain in place.


### 14.6.5 repeatable repair

The Windows Obsidian check now verifies an executable through registered Windows application locations, uninstall records, common installations, and optional Winget inventory. Confirmed installations are preserved; inconclusive evidence remains UNKNOWN rather than being treated as absent. Resource-policy source-option identity now selects durable resource-relevant inputs rather than transient repair/backup/Windows integration controls; unchanged legacy full-options hashes with valid document integrity are accepted for compatibility. Pre-migration shared-gateway live readiness now receives up to twelve checks separated by two seconds, preserving already converging processes. Windows storage display normalizes a drive's trailing colon. Added deterministic preservation fixtures; the live Windows/WSL end-to-end path still requires verification on its target host.

## Windows recovery hints and QMD OOM diagnostic follow-up (14.6.5)

Windows add-on/shortcut/Tailscale results are verified from live Windows state and written into `.installer-state.json` at the end of the installer run. The writer preserves all Linux-stage keys and commits only its Windows snapshot atomically. A `STATE_WRITE_ERROR` means the snapshot was not confirmed; an `EVENT_LOG_WARNING` means the state was successfully saved but the optional event log failed. This follow-up does not reauthenticate Tailscale or modify previously matching Serve routes.

An OOM marker (`Docker inspect .State.OOMKilled`) on an otherwise running `hermes-qmd-indexer` indicates a kill during the current container lifecycle but does not establish *when* it happened or whether memory exhaustion is continuing. Repair can correctly keep an unchanged resource-policy fingerprint and allocation while the OOM marker remains; an explicit unresolved-OOM warning and `./manage.sh audit` remain the appropriate health signals. Do not restart an otherwise healthy container or increase its memory ceiling solely to clear a marker. If the audit remains PARTIAL, examine actual container memory use/limits and recent memory events before adjusting policy.

### Runtime resource borrowing and repair

Resume / repair stops the optional `latticevale-resource-burst.timer`, restores
verified dynamic CPU/RAM limits to Compose baseline before normal repair, and
then reinstalls/re-enables the timer. If the controller reports a failed
restoration, inspect `data/latticevale/resource-burst-state.json` and the
live Docker limits; retain the existing backup and select the minimal
configuration reconciliation supported by the evidence. The controller is
inactive when a user Compose override changes anything beyond the verified
Hermes image/pull-policy selection. The bootstrap and controller both check
the effective Compose model; an image-only override remains eligible. See
`RESOURCE-POLICY.md`.
