> **v14.6.0 architecture checklist:** canonical schema ownership, hardware/backend fingerprinting, backend selection, and resource-budget calculations must not be reimplemented in orchestration code; generated architecture state must be atomic and self-validating; DirectML/CUDA/ROCm/Vulkan/native-Windows/CPU capabilities remain independent; explicit GPU intent must not silently redirect; CPU fallback remains supported; read-only planning/diagnostics preserve user/application state; release-content policy and exact manifest coverage must remain reproducible.

> **Inherited v14.5.47 GPU/recovery checklist (historical behavior retained under current policy v12):** GPU recommendation must derive from Windows inventory + direct WSL capability probes; selected DirectML/NVIDIA WSL prerequisites must be reused/provisioned idempotently; AMD ROCm must remain gated by real devices; Vulkan must require DRM render devices plus runtime offload proof; Windows/vendor display drivers remain external; PowerShell source must not use `New-Object System.Collections.Generic...`; DirectML `/dev/dxg` admission must use the dedicated direct path probe/root retry and never the Ollama GPU parser;  the inherited policy-v11 GPU proof/fingerprint guarantees must remain preserved while current policy v12 owns adaptive CPU/RAM/GPU/service/model calculations and runtime proof; read-only planner/config-state code must never write installer/user state; `compose.override.yaml` remains opaque/user-owned; older recognized managed stacks migrate cumulatively through Resume / repair while same-version repair remains local-first; checkpoint revisions must stay shared with `checkpoint-metadata.json` plus fallback; and all inherited v14.4.85 preservation/readiness guarantees remain required.

> **v14.4.85 inherited quality checklist:** preserve all v14.4.3 RAM/uninstaller and earlier ownership boundaries; live metadata repair may ignore only entries that actually vanished; resource audit must use WSL/process-visible CPU count; and a version-only bundle bump must not force managed image/source rebuilds unless the managed-refresh revision/age/legacy-state gate or explicit Option 6 requires it. Direct public 14.4.2→14.4.85 repair must still converge through refresh revision 1→2 and resource policy v2/v3/v4→v5. Hermes clean/repair may fill only missing LatticeVale-managed web/browser defaults; explicit browser/provider/gateway/environment/timeout choices and user-owned `SOUL.md`/model policy must remain untouched.

## Summary

Describe the change, why it is needed, and which installer/runtime paths it affects.

## Compatibility scope

State whether the change affects clean install, Resume / repair, Change installed components, Verify-only, provider/profile reconfiguration, Advanced recovery, Update / repair, uninstall, or runtime `manage.sh` behavior.

For profile/Kanban changes, use arbitrary profile names in tests. Do not assume a particular Windows username, drive letter, WSL distro registration name, Linux username, model/provider, Matrix room, or secondary-profile name.

## Safety and release checklist

- [ ] Fresh-install behavior remains intentional and tested.
- [ ] Existing-stack Resume / repair adopts required migrations without requiring destructive rebuilds.
- [ ] Resource-policy planner, canonical state, generated Compose, `resource-policy-report.txt`, and audit agree; hardware/policy fingerprints are recomputed and verified rather than copied blindly.
- [ ] The deterministic regression result is exactly 142 PASS / 0 FAIL / 0 SKIP across all six shards with bytecode/cache/temp contamination rejected.
- [ ] Release changes that affect packaged artifacts prove the corrected v14.5.47→v14.6.0 repository-patch round-trip plus declarative release-content/source-manifest equivalence.
- [ ] Update / repair behavior remains bundle-pinned and preservation-first.
- [ ] Clean-host reset remains separate, dry-run-first, ownership-gated, and never automatic; normal uninstall does not become more destructive.
- [ ] Scheduled Task cleanup tolerates heterogeneous/non-Exec action types and never assumes `Execute`/`Arguments`/`WorkingDirectory` exist.
- [ ] Windows lifecycle shortcuts contain no targeted `wsl --terminate`; v14.4.85 repair detects legacy owned shortcut helpers, resets WSL/WslService transport, and rewrites them.
- [ ] Normal configuration/runtime code does not directly write global WSL `[wsl2] networkingMode`; v14.4.81+ bounded E_UNEXPECTED recovery may invoke only the audited helper without requiring elevation, global shutdown requires confirmation when unrelated/unknown running-distro state exists, and any mirrored→NAT change remains separately explicit, backed up, and reversible.
- [ ] Adaptive resource-policy changes derive from live WSL CPU/RAM, enabled service topology, model/context requirements, selected backend, and measured GPU topology; no fixed host-size/topology target is introduced. Host reserve, DirectML reserve, aggregate container budget, per-service memory/CPU ceilings, runtime tuning, and model admission are generated/validated through the canonical policy engine; impossible selected-service minimum sets fail safely; effective merged Compose limits are verified against live Docker `HostConfig.Memory`/`HostConfig.NanoCpus`; selected running `OOMKilled=true` containers are not reported healthy; Redis/Valkey overcommit remains narrowly managed; and user `compose.override.yaml` remains the final override layer.
- [ ] Ubuntu Pro is not reintroduced as a LatticeVale option; external Ubuntu Pro state remains untouched.
- [ ] Normal uninstall fails closed when runtime may still exist but Docker cannot be inspected, and retained unowned tasks/shortcuts keep any support files they still reference.
- [ ] Persistent user state is preserved unless the change is an explicitly documented destructive recovery action.
- [ ] User-owned Hermes profile configuration is not rewritten unless ownership is explicitly established.
- [ ] Valid user-created profile names remain usable as routing targets where supported.
- [ ] Kanban singleton dispatch, task dependencies, review flow, worker task binding, concurrency limits, and durable artifacts are not weakened.
- [ ] Normal/unbound gateway sessions cannot masquerade as claimed Kanban workers.
- [ ] Agent skill changes preserve explicit `skills.write_approval` choices and tool-loop hard stops.
- [ ] Tool validation errors change strategy instead of being hidden by larger retry ceilings.
- [ ] No real secrets, tokens, recovery keys, private backups, generated WSL data, or machine-specific state are included.
- [ ] No third-party installer/binary/image/archive was added to the repository.
- [ ] New downloads use an official upstream source and are documented in `docs/SOURCES.md`.
- [ ] Relevant deterministic fixtures were added or updated.
- [ ] All user-facing documentation affected by the change was updated, including `docs/Instructions.txt`, README/docs/support/security/release docs, and relevant detailed patch/integration notes.
- [ ] GitHub issue/PR/workflow metadata remains consistent with the current release behavior.
- [ ] Bash/Python/static tests pass, or any environment timeout/limitation is explicitly documented without being called a pass.
- [ ] PowerShell runtime source remains ASCII-safe and parses on Windows PowerShell 5.1 and PowerShell 7.
- [ ] `installer/SOURCE-SHA256SUMS.txt` was regenerated only after the final reviewed changes.
