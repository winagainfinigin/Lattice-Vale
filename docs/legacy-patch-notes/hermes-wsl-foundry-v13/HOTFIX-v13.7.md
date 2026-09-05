> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.7 hotfix

Fixes Windows-to-WSL staging permissions for the existing-install audit.

`Invoke-BundledStackAudit` created `/tmp/hermes-audit-...` as root with the default
0755 permissions, then attempted to copy `state-audit.py` into that directory via
`\\wsl.localhost`. Windows therefore could read/traverse the directory but could not
create the file, causing `Copy-Item: Access ... is denied` before recovery could run.

v13.7 grants 0777 only to the random, short-lived audit staging directory, matching
the already-existing main bootstrap staging policy. The directory is always removed
by the function's `finally` cleanup. Installed Hermes data and persistent permissions
are unchanged.
