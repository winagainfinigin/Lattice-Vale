from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'LatticeVale-Core'
version = (CORE / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1'}, version

readme = (ROOT / 'docs/README.md').read_text(encoding='utf-8')
contrib = (ROOT / 'docs/CONTRIBUTING.md').read_text(encoding='utf-8')
desc = (ROOT / 'docs/Installer Description.txt').read_text(encoding='utf-8')
instructions = (ROOT / 'docs/Instructions.txt').read_text(encoding='utf-8')
support = (ROOT / 'docs/SUPPORT.md').read_text(encoding='utf-8')
third = (ROOT / 'docs/THIRD-PARTY-NOTICES.md').read_text(encoding='utf-8')
compat = (CORE / 'compatibility.conf').read_text(encoding='utf-8')

for text in (readme, contrib, desc, instructions):
    lower = text.lower()
    assert 'mit' in lower
    assert 'modif' in lower
    assert 'fork' in lower

assert 'x64/AMD64' in readme
assert 'amd64/x86_64' in readme
assert 'x64/AMD64' in desc
assert 'amd64/x86_64' in desc
assert 'x64/AMD64' in instructions
assert 'amd64/x86_64' in instructions
assert 'SUPPORTED_UBUNTU_VERSIONS="22.04 24.04 26.04"' in compat
assert 'MIN_WINDOWS_BUILD=19041' in compat
assert 'modified' in support.lower()
assert 'own original source/documentation' in third
assert 'third-party' in third.lower()

print('v14.3.23 public customization/docs fixtures: PASS')
