# Contributing

## v14.4.1 release-layout rule

Keep Git/GitHub metadata and conventional repository landing/legal files at repository root. Keep public PowerShell entry points and the release manifest under `installer/`, and substantive operator/release/security documentation under `docs/`. Any future file move must update launcher root resolution, clean-host release-root recognition, documentation, CI, and release-layout fixtures before regenerating the source manifest.

## v14.4.0 stable-release rule

Treat v14.4.0 as a runtime freeze of the audited v14.3.43 line. Documentation, tests, metadata, and manifests may reflect the stable promotion, but new runtime behavior belongs in a later version and must receive its own compatibility/regression review.

## v14.3.43 Scheduled Task compatibility rule

Windows Scheduled Task action collections are heterogeneous. Cleanup/audit code must inspect optional action properties defensively and must not assume every action is an Exec action. Missing properties are not evidence of ownership.

## v14.3.42 clean-host ownership rules

Changes to `Reset-LatticeVale-CleanHost.ps1` must remain capability/ownership based rather than machine-specific. Never hard-code a Windows username, drive, distro, Linux user, profile, model, room or tailnet. Destructive WSL reset must remain explicit; normal uninstall/repair stays preservation-first. Shared Windows virtualization/networking/applications must not be deleted merely because LatticeVale used them.

## v14.3.41 host-networking and inherited safety contribution rules

Do not add normal configuration/runtime code that directly writes global WSL `networkingMode`. Networking integrations must prove capability using the active topology and use scoped relays/firewall rules. The v14.4.81 preflight exception is narrowly defined: after a registered distro returns `WSL_HOST_E_UNEXPECTED`, the installer may invoke the audited helper in bounded `-LaunchRecoveryOnly` mode without elevation. Global shutdown must remain confirmation-gated when unrelated running distros are present or running-distro state cannot be verified. A mirrored→NAT change requires a separate explicit decision, backup, and same-distro retest. Deeper host repair remains explicit helper-only.

See `PATCH-NOTES.md` for the runtime invariants this release is protecting. For Hermes web/browser work, preserve explicit user provider/browser/gateway/environment/timeout choices; LatticeVale may fill only missing installer-managed defaults and must not manage `SOUL.md` or model policy.

Changes to managed Hermes profile policy must be tested on **arbitrary profile names and mixed ownership**. Never assume a secondary profile is named `assistant`; discover the real profile roster, edit only LatticeVale-managed configs, preserve valid user-created routing targets, and never automatically conscript an unrelated user-owned profile. Kanban changes must preserve worker task binding, dependency/decomposition behavior, singleton dispatch, and durable attachment semantics. Skill-policy changes must preserve explicit `skills.write_approval` choices on repair and must not weaken Hermes tool-loop hard stops as a substitute for correcting invalid tool arguments. Any migration must have both clean-install and existing-stack checkpoint coverage.

LatticeVale is MIT-licensed. Local modifications, private system-specific variants, public forks, and redistributed customized builds are permitted under that license. A downstream fork may intentionally target one machine or environment; upstream pull requests should remain portable across the documented supported baseline unless the change is explicitly adding and testing a new supported target.

When publishing a modified build, identify it as modified/downstream, preserve the MIT notice, regenerate `installer/SOURCE-SHA256SUMS.txt`, and do not include private machine state or credentials. Third-party components keep their own licenses; modifying an integrated upstream project is not the same as modifying LatticeVale itself.

Changes should preserve LatticeVale's two core guarantees: **clean installs stay functional** and **repair stays preservation-first**.

Before opening a pull request:

1. Do not add real credentials, tokens, Matrix recovery keys, WSL data, or user backups.
2. Keep installer logic readable; avoid encoded/obfuscated scripts and runtime `Invoke-Expression` patterns.
3. Keep shipped PowerShell runtime source (`.ps1`, `.psm1`, `.psd1`) ASCII-only so Windows PowerShell 5.1 never depends on UTF-8-without-BOM decoding.
4. Update tests for behavior changes rather than weakening old regressions to make a patch pass.
5. Run the static/regression suite and shell/Python syntax checks.
6. Document new persistent config fields and add a migration path for older `install-options.json` where needed. If support boundaries change, update `LatticeVale-Core/compatibility.conf`, requirements documentation, and compatibility fixtures together.
7. Treat Windows host, WSL host, `hermes-agent`, and other containers as distinct execution scopes.
8. Preserve unknown/manual Matrix identities/configuration unless ownership can be proven.
9. Keep destructive maintenance explicit and narrowly scoped.
10. Changes to Windows relays, WSL networking/firewall logic, or native Windows Ollama require fixture coverage **and** a documented target-system test plan based on `docs/WINDOWS-INTEGRATION-TEST-MATRIX.md`; do not treat static assertions as proof of live Windows behavior.

For security-sensitive findings, follow `docs/SECURITY.md` instead of opening a public exploit-detail issue.
