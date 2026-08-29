#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
assert (ROOT/'VERSION.txt').read_text(encoding='ascii').strip() == '14.4.85'
assert (REPO/'README.md').read_text(encoding='utf-8').startswith('# LatticeVale v14.4.85\n')
assert (ROOT/'README.md').read_text(encoding='utf-8').startswith('# LatticeVale v14.4.85 — Technical README\n')
assert (REPO/'docs/README.md').read_text(encoding='utf-8').startswith('# LatticeVale v14.4.85 — Stable\n')
assert (REPO/'docs/Instructions.txt').read_text(encoding='utf-8').startswith('LATTICEVALE v14.4.85 — INSTRUCTIONS\n')
assert (REPO/'docs/Installer Description.txt').read_text(encoding='utf-8').startswith('LATTICEVALE v14.4.85 — INSTALLER DESCRIPTION\n')
assert (REPO/'docs/FEATURES.md').read_text(encoding='utf-8').startswith('# LatticeVale v14.4.85 — Complete Features and Install Options Reference\n')
chg=(REPO/'docs/CHANGELOG.md').read_text(encoding='utf-8')
assert '## 14.4.85 - 2026-08-28' in chg
patch=(REPO/'docs/PATCH-NOTES.md').read_text(encoding='utf-8')
assert '## v14.4.85 — startup-aware reconcile, post-gateway readiness, and maintenance reliability' in patch
issue=(REPO/'.github/ISSUE_TEMPLATE/bug_report.yml').read_text(encoding='utf-8')
assert 'placeholder: 14.4.85' in issue
workflow=(REPO/'.github/workflows/validate.yml').read_text(encoding='utf-8')
assert 'Current v14.4.85 release identity' in workflow
assert (REPO/'installer/PATCH-DELETE.txt').exists()
assert (REPO/'tools/Finalize-LatticeVale-OverwritePatch.ps1').exists()
assert "grep -q '^14.4.85$' LatticeVale-Core/VERSION.txt" in workflow
for obsolete in [
    'v14.4.84-hotfix2-reconcile-startup-fixtures.py',
    'v14.4.84-hotfix2-post-gateway-readiness-fixtures.py',
    'v14.4.84-hotfix2-update-backup-audit-fixtures.py',
]:
    assert not (ROOT/'tests'/obsolete).exists(), obsolete
for current in [
    'v14.4.85-reconcile-startup-fixtures.py',
    'v14.4.85-post-gateway-readiness-fixtures.py',
    'v14.4.85-update-backup-audit-fixtures.py',
]:
    assert (ROOT/'tests'/current).exists(), current
print('v14.4.85 RELEASE IDENTITY FIXTURES: PASS')
