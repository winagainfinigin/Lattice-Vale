#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
lst=(REPO/'installer/PATCH-DELETE.txt').read_text(encoding='utf-8')
helper=(REPO/'tools/Finalize-LatticeVale-OverwritePatch.ps1').read_text(encoding='utf-8')
manifest=(REPO/'tools/ReleaseManifest.ps1').read_text(encoding='utf-8')
expected=[
 'LatticeVale-Core/tests/v14.4.84-hotfix2-reconcile-startup-fixtures.py',
 'LatticeVale-Core/tests/v14.4.84-hotfix2-post-gateway-readiness-fixtures.py',
 'LatticeVale-Core/tests/v14.4.84-hotfix2-update-backup-audit-fixtures.py',
]
for rel in expected:
    assert rel in lst, rel
    assert not (REPO/rel).exists(), rel
assert "[IO.Path]::IsPathRooted($rel)" in helper
assert "PATCH-DELETE path escapes repository root" in helper
assert "Remove-Item -LiteralPath $candidate -Force -Recurse" in helper
assert "Obsolete source file remains from an older overwrite patch" in manifest
assert "Finalize-LatticeVale-OverwritePatch.ps1" in manifest
print('v14.4.85 OVERWRITE PATCH CLEANUP FIXTURES: PASS')
