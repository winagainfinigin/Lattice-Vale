#!/usr/bin/env python3
"""Patch QMD v2.5.3's compiled MCP HTTP listener for Docker inter-container use.

v2.5.3 hardcodes localhost and has no --host flag. The surrounding Compose model
publishes no QMD port to the Windows host, so changing only the listen address is
used to let Hermes reach QMD by Docker service name. Fail closed on layout drift.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-qmd-bind.py QMD_PACKAGE_ROOT")

root = Path(sys.argv[1])
if not root.is_dir():
    raise SystemExit(f"QMD package root not found: {root}")

needles = (
    ('httpServer.listen(port, "localhost"', 'httpServer.listen(port, "0.0.0.0"'),
    ("httpServer.listen(port, 'localhost'", "httpServer.listen(port, '0.0.0.0'"),
)
changed = 0
changed_files: list[Path] = []
for path in root.rglob("*"):
    if not path.is_file() or path.suffix not in {".js", ".mjs", ".cjs"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    new = text
    for old, replacement in needles:
        occurrences = new.count(old)
        if occurrences:
            new = new.replace(old, replacement)
            changed += occurrences
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed_files.append(path)

if changed != 1 or len(changed_files) != 1:
    raise SystemExit(
        f"Expected exactly one QMD localhost HTTP listen binding to patch; "
        f"found {changed} occurrence(s) in {len(changed_files)} file(s)."
    )

print(f"Patched QMD MCP HTTP listener for Docker networking: {changed_files[0]}")
