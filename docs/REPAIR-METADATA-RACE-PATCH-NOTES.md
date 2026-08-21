# LatticeVale v14.4.4 repair metadata-race hardening

## Problem

During Resume / repair, `linux/bootstrap.sh` normalizes ownership and write permissions on installer-managed user-data trees. In v14.4.3 this used recursive `chown`/`chmod`. If a live SQLite sidecar such as `data/hermes/kanban.db-shm` disappeared while that traversal was in progress, GNU `chown` returned non-zero and `set -e` aborted the entire bootstrap even though the disappearance was normal runtime behavior.

The observed failure was:

```text
chown: changing ownership of '.../data/hermes/kanban.db-shm': No such file or directory
Bootstrap failed
```

## v14.4.4 behavior

`repair_user_tree` now:

- rejects a managed root that is a symlink or mountpoint as before;
- snapshots the current tree with `find -P -xdev -ignore_readdir_race`;
- applies ownership one entry at a time with `chown -h`;
- skips `chmod` for symlinks and never follows them;
- tolerates a failed metadata operation only when the exact entry no longer exists;
- remains fail-closed when the entry still exists, preserving detection of real permission or ownership problems;
- does not cross nested mount boundaries.

This makes repair compatible with live SQLite WAL/SHM churn and log rotation without converting genuine filesystem errors into success.

## Install-path impact

Clean installs continue through the same bootstrap and receive the same safe metadata walker, but normally have little or no pre-existing live state to reconcile. Resume / repair is the path that materially benefits because existing Hermes services may still be active when root-assisted ownership reconciliation begins.

No WSL distribution ownership, Docker-global cleanup policy, user `compose.override.yaml`, persistent database ownership boundary, networking policy, RAM policy, or uninstaller behavior is changed by v14.4.4.

See `CHANGELOG.md` for canonical release history.
