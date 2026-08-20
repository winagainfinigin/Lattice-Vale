> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.5 hotfix

Fixes WSL bootstrap staging for the QMD bind patch helper. v13.4 validated that
`stack/patch-qmd-bind.py` existed in the extracted bundle but omitted it from the
files copied into the temporary WSL staging directory. `bootstrap.sh` therefore
failed when installing that file. v13.5 stages the helper with the rest of the
stack bundle.
