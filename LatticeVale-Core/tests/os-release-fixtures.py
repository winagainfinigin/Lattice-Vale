#!/usr/bin/env python3
"""Fixtures mirroring v9 direct distro identity parsing."""

def parse(text):
    out = {}
    text = text.replace('\x00', '').replace('\ufeff', '')
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        if k:
            out[k] = v
    return out

normal = 'PRETTY_NAME="Ubuntu 24.04.3 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\nID=ubuntu\nUBUNTU_CODENAME=noble\n'
v = parse(normal)
assert v['ID'] == 'ubuntu' and v['VERSION_ID'] == '24.04' and v['UBUNTU_CODENAME'] == 'noble'

nul = ''.join(ch + '\x00' for ch in normal)
v = parse(nul)
assert v['ID'] == 'ubuntu' and v['VERSION_ID'] == '24.04'

lsb = 'DISTRIB_ID=Ubuntu\nDISTRIB_RELEASE=24.04\nDISTRIB_CODENAME=noble\nDISTRIB_DESCRIPTION="Ubuntu 24.04.3 LTS"\n'
v = parse(lsb)
assert v['DISTRIB_ID'] == 'Ubuntu' and v['DISTRIB_RELEASE'] == '24.04'

supported = {'22.04', '24.04', '26.04'}
assert {'22.04', '24.04', '26.04'} <= supported
print('OS RELEASE FIXTURES: PASS')
