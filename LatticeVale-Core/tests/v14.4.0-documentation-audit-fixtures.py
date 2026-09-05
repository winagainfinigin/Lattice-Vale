#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CORE=ROOT/'LatticeVale-Core'
version=(CORE/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}, version
readme=(ROOT/'docs/README.md').read_text(encoding='utf-8')
inst=(ROOT/'docs/Instructions.txt').read_text(encoding='utf-8')
desc=(ROOT/'docs/Installer Description.txt').read_text(encoding='utf-8')
features=(ROOT/'docs/FEATURES.md').read_text(encoding='utf-8')
assert readme.startswith(f'# LatticeVale v{version}')
assert inst.startswith(f'LATTICEVALE v{version} — INSTRUCTIONS')
assert desc.startswith(f'LATTICEVALE v{version} — INSTALLER DESCRIPTION')
assert 'over 50 GiB total capacity' in readme and 'at least 50 GiB free' in readme
assert 'over 50 GiB total capacity' in inst and 'at least 50 GiB free' in inst
assert 'adaptive per-container CPU/RAM ceilings' in readme
assert 'container timezone' in readme
assert 'QMD can be used without Obsidian' in inst
assert 'skills.write_approval` to `false`' in readme
assert 'skills.write_approval` to `false`' in desc
assert 'Optional components: Dashboard, SearXNG, QMD, Obsidian' in inst
assert 'Reset checkpoints and reverify/reconcile every stage' in inst
assert 'ALL WSL distributions registered to the current Windows user' in inst
assert features.startswith(f'# LatticeVale v{version}')
assert 'Complete Features and Install Options Reference' in features
print('v14.4.0 documentation audit fixtures: PASS')
