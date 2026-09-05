#!/usr/bin/env python3
"""v14.6.0 task-documentation and declarative-release-policy contract."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[2]
assert (ROOT/'LatticeVale-Core/VERSION.txt').read_text().strip()=='14.6.0'
for name in ('QUICKSTART.md','INSTALLATION.md','REPAIR.md','GPU-BACKENDS.md','TROUBLESHOOTING.md','DIAGNOSTICS.md','RESOURCE-POLICY.md','ARCHITECTURE.md','TESTING.md'):
    p=ROOT/'docs'/name
    assert p.is_file() and len(p.read_text())>250, name
policy=json.loads((ROOT/'LatticeVale-Core/release/release-content.json').read_text())
assert policy['schema']==1
assert 'docs/legacy-patch-notes/' in policy['repositoryOnlyPrefixes']
readme=(ROOT/'README.md').read_text()
for doc in ('QUICKSTART.md','REPAIR.md','GPU-BACKENDS.md','DIAGNOSTICS.md','RESOURCE-POLICY.md','ARCHITECTURE.md'):
    assert doc in readme
release=(ROOT/'docs/RELEASE.md').read_text()
assert 'repository-only' in release.lower() and '14.6.0' in release
contrib=(ROOT/'docs/CONTRIBUTING.md').read_text()
assert 'Do not duplicate install-options schema ceilings' in contrib
workflow=(ROOT/'.github/workflows/validate.yml').read_text()
assert '14.6.0' in workflow
print('v14.6.0 documentation/release fixtures: PASS')
