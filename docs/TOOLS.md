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
