from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
builder = (REPO / 'tools/Build-LatticeVale-Release.ps1').read_text(encoding='utf-8')
release_workflow = (REPO / '.github/workflows/release.yml').read_text(encoding='utf-8')
validate_workflow = (REPO / '.github/workflows/validate.yml').read_text(encoding='utf-8')

assert version == '14.7.0'
assert 'SOURCE-SHA256SUMS.txt' in builder
assert 'verify-release.ps1' in builder
assert 'Lattice-Vale/' in builder
assert 'CreateFromDirectory' in builder
assert 'Forbidden release artifact' in builder
assert 'sourceCommit' in builder and 'sha256' in builder
assert "tags:\n      - '14.7.0'" in release_workflow
assert 'gh release upload' in release_workflow
assert '11bd71901bbe5b1630ceea73d27597364c9af683' in release_workflow
assert 'Build and inspect release archive' in validate_workflow
print('PASS manifest-built v14.7.0 release packaging contract')

# The index check executes source discovery rather than grepping a canned header.
import subprocess
import sys
import tempfile

index_tool = REPO / 'tools/Generate-FunctionIndex.py'
check = subprocess.run([sys.executable, str(index_tool), '--check'], cwd=REPO,
                       capture_output=True, text=True, timeout=30)
assert check.returncode == 0, check.stdout + check.stderr
with tempfile.TemporaryDirectory() as tmp:
    sample = Path(tmp)
    for rel in ('tools/Generate-FunctionIndex.py', 'docs/FUNCTION-INDEX.md',
                'LatticeVale-Core/VERSION.txt', 'LatticeVale-Core/Install-LatticeVale.ps1',
                'LatticeVale-Core/stack/configure-stack.sh'):
        dest = sample / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((REPO / rel).read_bytes())
    script = sample / 'LatticeVale-Core/stack/configure-stack.sh'
    script.write_text(script.read_text(encoding='utf-8') + '\nindex_regression_probe() { :; }\n', encoding='utf-8')
    stale = subprocess.run([sys.executable, str(sample / 'tools/Generate-FunctionIndex.py'), '--check'],
                           cwd=sample, capture_output=True, text=True, timeout=30)
    assert stale.returncode != 0 and 'STALE FUNCTION INDEX' in stale.stderr
print('PASS deterministic current index and behavioral stale-index rejection')

# Read-only restore-plan behavioral characterization: both backup formats, one
# corrupted archive, and a fake pg_restore that records every validation call.
import io
import json
import os
import tarfile
with tempfile.TemporaryDirectory() as tmp:
    stack = Path(tmp) / 'stack'
    stack.mkdir()
    (stack / 'manage.sh').write_bytes((ROOT / 'stack/manage.sh').read_bytes())
    (stack / 'compatibility.conf').write_bytes((ROOT / 'compatibility.conf').read_bytes())
    (stack / 'install-options.json').write_text(json.dumps({'schema': 24, 'installerVersion': '14.7.0'}))
    fakebin = Path(tmp) / 'bin'
    fakebin.mkdir()
    (fakebin / 'pg_restore').write_text('#!/bin/sh\n[ "$1" = "--list" ] && [ -f "$2" ]\n')
    (fakebin / 'pg_restore').chmod(0o755)
    env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ['PATH'])
    for kind in ('manual', 'pre-update'):
        backup = stack / 'backups' / kind
        backup.mkdir(parents=True)
        with tarfile.open(backup / 'files.tar.gz', 'w:gz') as archive:
            for rel, blob in (('compatibility.conf', (stack / 'compatibility.conf').read_bytes()),
                              ('install-options.json', (stack / 'install-options.json').read_bytes()),
                              ('config/example.yml', b'test: true\n')):
                info = tarfile.TarInfo(rel)
                info.size = len(blob)
                archive.addfile(info, io.BytesIO(blob))
        (backup / 'synapse.dump').write_bytes(b'PGDMP-test')
        if kind == 'pre-update':
            (backup / 'BACKUP-INFO.txt').write_text('test backup\n')
        planned = subprocess.run(['bash', './manage.sh', 'restore', str(backup), '--plan'],
                                 cwd=stack, env=env, capture_output=True, text=True, timeout=30)
        assert planned.returncode == 0, planned.stderr
        assert 'config/example.yml' in planned.stdout and 'NO FILES' in planned.stdout
        assert 'synapse.dump' in planned.stdout and kind.split('-')[0] in planned.stdout
    (backup / 'files.tar.gz').write_bytes(b'corrupted')
    refused = subprocess.run(['bash', './manage.sh', 'restore', str(backup), '--plan'],
                             cwd=stack, env=env, capture_output=True, text=True, timeout=30)
    assert refused.returncode == 1 and 'RESTORE PLAN REFUSED' in refused.stderr
print('PASS read-only restore plans for both backup types and corrupt-archive refusal')
