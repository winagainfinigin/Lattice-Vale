#!/usr/bin/env python3
from pathlib import Path
import re

root=Path(__file__).resolve().parents[1]
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}

allowed={'env','global','local','script','private','using','variable','function','alias'}
bad=[]
for path in (root/'Install-LatticeVale.ps1', root/'windows/LatticeVale-WslNativeRelay.ps1'):
    text=path.read_text(encoding='utf-8')
    for lineno,line in enumerate(text.splitlines(),1):
        for match in re.finditer(r'\$([A-Za-z_][A-Za-z0-9_]*):',line):
            if match.group(1).lower() not in allowed:
                bad.append((path.name,lineno,match.group(1),line.strip()))
assert not bad, f'unbraced PowerShell variable-before-colon interpolation remains: {bad}'

relay=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
assert 'WSL wake failed for ${DistroName}: $($wake.Text)' in relay
assert 'Hermes stack start helper failed for ${DistroName}: $($start.Text)' in relay
assert 'WSL wake failed for $DistroName:' not in relay
assert 'Hermes stack start helper failed for $DistroName:' not in relay

print('v13.13.4 relay parser fixtures: PASS')
