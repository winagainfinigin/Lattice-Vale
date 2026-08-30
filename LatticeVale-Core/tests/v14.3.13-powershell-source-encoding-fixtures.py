#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT.parent
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1'}, version

ps_files = sorted(
    p for p in RELEASE_ROOT.rglob('*')
    if p.is_file() and p.suffix.lower() in {'.ps1', '.psm1', '.psd1'} and '.git' not in p.parts
)
assert ps_files, 'no PowerShell source found'
assert any(p.name == 'Finalize-LatticeVale-OverwritePatch.ps1' for p in ps_files), 'overwrite-patch finalizer is missing from PowerShell encoding coverage'
for path in ps_files:
    raw = path.read_bytes()
    bad = [(i, b) for i, b in enumerate(raw) if b > 0x7F]
    assert not bad, f'{path.relative_to(RELEASE_ROOT)} has non-ASCII byte 0x{bad[0][1]:02x} at offset {bad[0][0]}'
    # If the file is ASCII-only, Windows ANSI decoding and UTF-8 decoding are byte-for-byte equivalent.
    assert raw.decode('ascii') == raw.decode('utf-8')

manifest = (RELEASE_ROOT / 'tools' / 'ReleaseManifest.ps1').read_text(encoding='ascii')
assert 'Assert-LatticeValePowerShellSourceEncoding' in manifest
assert "@('.ps1','.psm1','.psd1')" in manifest
assert 'PowerShell source must be ASCII-only for Windows PowerShell 5.1 compatibility' in manifest

workflow = (RELEASE_ROOT / '.github' / 'workflows' / 'validate.yml').read_text(encoding='utf-8')
assert "Get-ChildItem -Path . -Recurse -File" in workflow
assert "@('.ps1','.psm1','.psd1')" in workflow
assert 'non-ASCII byte' in workflow
print('v14.3.13 PowerShell source encoding fixtures: PASS')
