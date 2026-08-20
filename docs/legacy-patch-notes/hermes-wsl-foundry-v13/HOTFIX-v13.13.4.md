> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# Hermes WSL Foundry v13.13.4

## Native relay PowerShell parser hotfix

A live v13.13.3 repair run reached the Windows-native relay self-test and both PowerShell 7 and Windows PowerShell 5.1 rejected `Hermes-WslNativeRelay.ps1`. The relay contained expandable strings with `$DistroName:`. In PowerShell, a bare variable immediately followed by a colon is parsed as a scoped/provider variable reference unless the variable name is delimited.

v13.13.4 changes those strings to `${DistroName}:`, scans both the parent installer and native relay for the entire unbraced-variable-before-colon bug class, and adds a dedicated regression fixture.

This is a clean-install and Resume/repair fix. The failure occurs at parse time, so starting WSL or Hermes in advance cannot correct it.
