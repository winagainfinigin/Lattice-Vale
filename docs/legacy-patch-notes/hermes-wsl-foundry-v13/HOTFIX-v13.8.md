> **Historical documentation:** This retained v13 document is audit/compatibility history, not current operating guidance. For LatticeVale v14.4.0 installation, repair, update, security, Kanban/skill policy, and compatibility instructions, use the repository-root `Instructions.txt`, `README.md`, `SECURITY.md`, and `CHANGELOG.md`. Do not apply a historical workaround over a newer managed policy unless current documentation explicitly directs you to do so.

# v13.8 hotfix

Fixes profile provider/model setup failing with:

```
cannot attach stdin to a TTY-enabled container because stdin is not a terminal
```

`bootstrap.sh` already supplies a PTY with `runuser --pty`, but `stage_profiles`
was reading its worker loop from a `jq` process substitution. That redirected the
loop body stdin away from the PTY and into a pipe. v13.8 materializes the worker
JSON with Bash `mapfile` before entering the loop, so each interactive
`docker exec -it ... setup` inherits the PTY as intended. Existing profiles and
provider data are preserved; incomplete profile setup resumes on rerun.
