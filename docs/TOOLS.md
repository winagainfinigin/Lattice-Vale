
## Resource explanation (read-only)

From a configured installed WSL stack run `./manage.sh resources --explain`
for a human-readable view or `./manage.sh resources --json` for JSON. The
controller validates Docker project/ownership, its policy fingerprint and
persisted transaction before returning observed limits and cgroup charges.
Timer status, currently visible WSL RAM, host pressure and the last recorded
decision are reported separately. Historical decision codes are **not** proof
that a fresh workload will borrow resources. No changes are made.

The manual disposable-stack qualification supports
`--exercise-hermes-cpu`; it creates bounded CPU demand inside the selected
Compose Hermes service, observes fresh controller decisions, and records
whether the same borrower later relinquished capacity. A normal health PASS
is independent of a resource `not-demonstrated` result. This command must not
be run against a production stack.


# Optional Hermes audit tools

The repository includes two opt-in, read-only audit helpers under `tools/`. They read stack/container metadata and write a local report; they do not change Docker services, databases, WSL configuration, or installer state.

## Kanban card export

Run `python3 tools/hermes_kanban_export.py` from WSL with Docker access. The default output is `Hermes-Kanban-All-Cards.txt` on the detected Windows Desktop. Use `--output /path/to/report.txt` to select a location.

By default the export includes card descriptions/results and worker summaries after redacting common credential patterns, while omitting comment bodies, worker errors, workspace paths, and attachment paths. Include sensitive categories only when needed:

```text
python3 tools/hermes_kanban_export.py --include-comments --include-worker-errors --include-paths
```

Do not share a full export without checking the report; redaction is pattern-based and cannot identify every secret. Attachment contents are never embedded.

## Structure audit

Run `python3 tools/hermes_structure_audit.py`. It detects the Desktop when available and otherwise saves to the WSL home directory. `--output /path/to/report.txt` selects an exact report path. By default, it probes only the current Windows/WSL user for a destination and redacts host paths and directory-entry names in the saved report. `--include-paths` includes full paths and directory names; `--include-all-profiles` searches other Windows profiles for a destination folder.

The report contains container mount and schema metadata, not database rows. Review it before sharing because hostnames, service topology, and file names may still be sensitive when those options are enabled.

## Automated runtime qualification

The manual Windows/WSL qualification workflow is documented in [the integration matrix](WINDOWS-INTEGRATION-TEST-MATRIX.md). It is separate from these audit utilities and must run only against a disposable stack.


## Deterministic function index

After changing `LatticeVale-Core/Install-LatticeVale.ps1` or `LatticeVale-Core/stack/configure-stack.sh`, run `python tools/Generate-FunctionIndex.py` from the repository root. This regenerates `docs/FUNCTION-INDEX.md` from actual function declarations and line numbers, without executing installer code. `python tools/Generate-FunctionIndex.py --check` is read-only and exits nonzero on staleness. The 14.7.0 regression fixture executes both the passing check and a deliberately stale temporary copy.

## Disposable live qualification report

`LatticeVale-Core/tests/live-qualification.py` requires the existing exact disposable-stack marker; ordinary CI and production stacks must not run this probe. The script now writes an atomic JSON failure report containing `failedStep` and `failureType` for errors raised after valid CLI parsing; it reads `docker compose` service/container evidence for the selected marked project rather than engine-wide stats or a hard-coded Hermes container name. `passCriteria` identifies the prior health/verification gates. CPU pressure and watchdog signal counts are measurements only, **not** pass/fail thresholds. A success still requires full disposable-stack qualification on Windows/WSL/Docker.
