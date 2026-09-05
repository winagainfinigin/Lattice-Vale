> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For current LatticeVale installation, repair, update, security, Kanban/skill policy, and compatibility guidance, use the repository-root `README.md` plus `docs/Instructions.txt`, `docs/SECURITY.md`, and `docs/CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.5 hotfix

Fixes WSL bootstrap staging for the QMD bind patch helper. v13.4 validated that
`stack/patch-qmd-bind.py` existed in the extracted bundle but omitted it from the
files copied into the temporary WSL staging directory. `bootstrap.sh` therefore
failed when installing that file. v13.5 stages the helper with the rest of the
stack bundle.
