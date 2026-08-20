> **v14.4.2 quality checklist:** preserve the v14.3.40 documentation split, v14.3.39 shared-Docker/existing-install safety boundary, v14.3.38 Kanban/skill migration, the v14.3.41 rule that normal installer/runtime code never writes global WSL `networkingMode`.

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
- [ ] Normal installer/runtime code does not write global WSL `[wsl2] networkingMode`; host-global networking recovery remains explicit, backed up, and reversible.
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
