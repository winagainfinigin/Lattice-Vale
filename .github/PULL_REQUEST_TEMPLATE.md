> **v14.4.85 quality checklist:** preserve all v14.4.3 RAM/uninstaller and earlier ownership boundaries; live metadata repair may ignore only entries that actually vanished; resource audit must use WSL/process-visible CPU count; and a version-only bundle bump must not force managed image/source rebuilds unless the managed-refresh revision/age/legacy-state gate or explicit Option 6 requires it. Direct public 14.4.2→14.4.85 repair must still converge through refresh revision 1→2 and resource policy v2/v3→v4. Hermes clean/repair may fill only missing LatticeVale-managed web/browser defaults; explicit browser/provider/gateway/environment/timeout choices and user-owned `SOUL.md`/model policy must remain untouched.

## Summary

Describe the change, why it is needed, and which installer/runtime paths it affects.

## Compatibility scope

State whether the change affects clean install, Resume / repair, Change installed components, Verify-only, provider/profile reconfiguration, Advanced recovery, Update / repair, uninstall, or runtime `manage.sh` behavior.

For profile/Kanban changes, use arbitrary profile names in tests. Do not assume a particular Windows username, drive letter, WSL distro registration name, Linux username, model/provider, Matrix room, or secondary-profile name.

## Safety and release checklist

- [ ] Fresh-install behavior remains intentional and tested.
- [ ] Existing-stack Resume / repair adopts required migrations without requiring destructive rebuilds.
- [ ] Update / repair behavior remains bundle-pinned and preservation-first.
- [ ] Clean-host reset remains separate, dry-run-first, ownership-gated, and never automatic; normal uninstall does not become more destructive.
- [ ] Scheduled Task cleanup tolerates heterogeneous/non-Exec action types and never assumes `Execute`/`Arguments`/`WorkingDirectory` exist.
- [ ] Windows lifecycle shortcuts contain no targeted `wsl --terminate`; v14.4.85 repair detects legacy owned shortcut helpers, resets WSL/WslService transport, and rewrites them.
- [ ] Normal configuration/runtime code does not directly write global WSL `[wsl2] networkingMode`; v14.4.81+ bounded E_UNEXPECTED recovery may invoke only the audited helper without requiring elevation, global shutdown requires confirmation when unrelated/unknown running-distro state exists, and any mirrored→NAT change remains separately explicit, backed up, and reversible.
- [ ] RAM/resource-policy changes do not silently take ownership of global WSL `memory`/`autoMemoryReclaim`, generated limits remain inside the aggregate container budget, Redis/Valkey overcommit remains narrowly managed, and user `compose.override.yaml` remains the final override layer.
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
