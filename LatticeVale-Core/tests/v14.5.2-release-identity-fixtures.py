#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
assert (REPO/'README.md').read_text(encoding='utf-8').startswith(f'# LatticeVale v{version}\n')
assert (ROOT/'README.md').read_text(encoding='utf-8').startswith(f'# LatticeVale v{version} — Technical README\n')
assert (REPO/'docs/README.md').read_text(encoding='utf-8').startswith(f'# LatticeVale v{version} — Stable\n')
assert (REPO/'docs/Instructions.txt').read_text(encoding='utf-8').startswith(f'LATTICEVALE v{version} — INSTRUCTIONS\n')
assert (REPO/'docs/Installer Description.txt').read_text(encoding='utf-8').startswith(f'LATTICEVALE v{version} — INSTALLER DESCRIPTION\n')
assert (REPO/'docs/FEATURES.md').read_text(encoding='utf-8').startswith(f'# LatticeVale v{version} — Complete Features and Install Options Reference\n')
changelog=(REPO/'docs/CHANGELOG.md').read_text(encoding='utf-8'); assert '## 14.5.2 - 2026-08-29' in changelog
assert '## 14.5.1 - 2026-08-29' in changelog
patch=(REPO/'docs/PATCH-NOTES.md').read_text(encoding='utf-8'); assert '## v14.5.2 — cleanup / reclaim disk space maintenance release' in patch
root=(REPO/'README.md').read_text(encoding='utf-8'); assert '| **v14.5.2** | Release |' in root if version in {'14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'} else '| **v14.5.2** | **Current install release** |' in root
assert '| **v14.5.1** | Release |' in root
assert (ROOT/'tests/v14.5.2-option7-cleanup-fixtures.py').is_file()
print('v14.5.2 CUMULATIVE RELEASE IDENTITY FIXTURES: PASS')
