#!/usr/bin/env python3
"""Deterministically regenerate/check the danger-zone function index from shipped source.

This scans declarations only; it does not execute or rewrite installer code.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / 'docs/FUNCTION-INDEX.md'
SOURCES = (
    ('LatticeVale-Core/Install-LatticeVale.ps1', re.compile(r'^\s*function\s+([A-Za-z][\w-]*)\b')),
    ('LatticeVale-Core/stack/configure-stack.sh', re.compile(r'^\s*(?:function\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*\(\)\s*\{')),
)
SAFETY = '''## Safety-critical areas

- **WSL registration and Linux account selection:** verify exact owned distro/user; never unregister, import, migrate, or alter VHDX during ordinary repair.
- **Uninstaller and clean-host reset:** refuse deletion without demonstrated ownership; inspect selected paths, Docker labels, scheduled tasks, and backup state.
- **Backup/restore and repair staging:** preserve user settings, PostgreSQL, Matrix identities, profiles, Ollama artifacts, Compose overrides, and Obsidian mounts.
- **Docker Compose/resources:** obey per-container ownership, bounded leases, cgroup headroom, and total memory/CPU envelopes before updates.
- **Tailscale, firewall, reverse proxies:** avoid exposing beyond explicit localhost/Serve scopes; check actual selected ACL/route ownership.
- **Windows process invocation:** use argument arrays, no command injection; parse with PowerShell 5.1 and 7 on Windows.
'''


def render() -> str:
    version = (REPO / 'LatticeVale-Core/VERSION.txt').read_text(encoding='ascii').strip()
    sections = [
        f'# LatticeVale {version} function and danger-zone index',
        '',
        'Generated from the current monolith source by `tools/Generate-FunctionIndex.py`.',
        '**Documentation only**; line numbers are references, not API contracts. No code is moved.',
        '',
        SAFETY.rstrip(),
        '',
        '## Function indices',
        '',
    ]
    for rel, regex in SOURCES:
        lines = (REPO / rel).read_text(encoding='utf-8').splitlines()
        functions = [(lineno, match.group(1)) for lineno, line in enumerate(lines, 1)
                     if (match := regex.match(line))]
        if not functions:
            raise ValueError(f'No function declarations found in {rel}')
        sections.extend([
            f'### `{rel}` ({len(functions)} detected functions; {len(lines)} lines)',
            '',
            '| Line | Function |',
            '| ---: | --- |',
            *(f'| {lineno} | `{name}` |' for lineno, name in functions),
            '',
        ])
    return '\n'.join(sections).rstrip() + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if the index is absent or stale; write nothing')
    args = parser.parse_args()
    expected = render()
    actual = OUTPUT.read_text(encoding='utf-8') if OUTPUT.exists() else None
    if args.check:
        if actual != expected:
            print(f'STALE FUNCTION INDEX: run python tools/Generate-FunctionIndex.py', file=sys.stderr)
            return 1
        print('Function index matches current source')
        return 0
    OUTPUT.write_text(expected, encoding='utf-8', newline='\n')
    print(f'Updated {OUTPUT.relative_to(REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
