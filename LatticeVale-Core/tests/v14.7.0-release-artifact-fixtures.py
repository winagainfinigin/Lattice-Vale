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
