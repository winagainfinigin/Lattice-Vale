#!/usr/bin/env python3
"""Offline regression tests for Option 1's conditional managed-update policy."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'linux/check-managed-updates.py'
assert source.is_file()
spec = importlib.util.spec_from_file_location('latticevale_check_updates', source)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def process(stdout: str = '', rc: int = 0, stderr: str = ''):
    return subprocess.CompletedProcess([], rc, stdout, stderr)

# No executable installs, Docker pulls or source checkout updates are performed
# by the conditional availability checker.
checker = source.read_text(encoding='utf-8')
assert 'apt-get' in checker and '"update", "-qq"' in checker
assert 'docker", "buildx", "imagetools", "inspect"' in checker
assert 'docker", "image", "inspect"' in checker
for operation in ['"pull"', '"checkout"', '"install", "-y"', '"upgrade", "-y"']:
    assert operation not in checker, operation
assert 'https://registry.npmjs.org/@tobilu%2Fqmd/latest' in checker
# Peeled annotated tags are needed to compare Honcho release commit SHAs.
assert '"ls-remote", "--tags"' in checker
assert '"--tags", "--refs"' not in checker
assert 'name.endswith("^{}")' in checker

with tempfile.TemporaryDirectory() as td:
    stack = Path(td)
    (stack / 'install-options.json').write_text(json.dumps({'matrix': False, 'searxng': False, 'qmd': False, 'honcho': False, 'ollamaBackend': 'windows-native'}))
    (stack / '.env').write_text('HERMES_IMAGE=nousresearch/hermes-agent:latest\nLATTICEVALE_HERMES_IMAGE_AUTO=nousresearch/hermes-agent:latest\n')
    digest = 'sha256:' + 'a' * 64
    changed = 'sha256:' + 'b' * 64
    responses = {
        'apt-get': process(),
        'apt-cache': process('  Installed: 1.0\n  Candidate: 1.0\n'),
        'docker': process(json.dumps(['docker.io/nousresearch/hermes-agent@'+digest])),
    }

    def current_cmd(args, timeout=30):
        if args[:3] == ['docker','buildx','imagetools']:
            return process(f'Name: docker.io/nousresearch/hermes-agent:latest\nDigest: {digest}\n')
        if args[0] == 'dpkg':
            return process(rc=1)
        return responses.get(args[0], process())

    with patch.object(mod,'command',side_effect=current_cmd):
        updates, errors = mod.check(stack)
        assert not updates and not errors, (updates, errors)
    with patch.object(mod,'command',side_effect=lambda args, timeout=30: process(f'Digest: {changed}\n') if args[:3]==['docker','buildx','imagetools'] else current_cmd(args,timeout)):
        updates, errors = mod.check(stack)
        assert updates == ['Newer managed Docker image digest: HERMES_IMAGE'] and not errors, (updates, errors)

    # An unavailable remote registry is UNKNOWN, not a made-up update.
    with patch.object(mod,'command',side_effect=lambda args, timeout=30: process(rc=1) if args[:3]==['docker','buildx','imagetools'] else current_cmd(args,timeout)):
        updates, errors = mod.check(stack)
        assert not updates and errors == ['Cannot verify registry digest: HERMES_IMAGE'], (updates, errors)

    # Explicit user-owned image overrides are never compared or silently updated.
    (stack / '.env').write_text('HERMES_IMAGE=example.local/private:1.2\nLATTICEVALE_HERMES_IMAGE_AUTO=nousresearch/hermes-agent:latest\n')
    with patch.object(mod,'command',side_effect=lambda args, timeout=30: process('  Installed: 1.0\n  Candidate: 1.0\n') if args[0]=='apt-cache' else process(rc=1) if args[0]=='dpkg' else process()):
        updates, errors=mod.check(stack)
        assert not updates and not errors, (updates, errors)

# APT checks compare candidate against installed; same candidate triggers no update.
with patch.object(mod,'command',side_effect=lambda args, timeout=30: process('  Installed: 1.0\n  Candidate: 2.0\n') if args[0]=='apt-cache' else process()):
    # dpkg returns success for a candidate that is greater.
    updates, errors=mod.latest_apt()
    assert len(updates)==len(mod.PACKAGES) and not errors

# Version-only 14.6.5/14.6.6 -> 14.6.7 remains a same-schema patch, not
# a forced cumulative migration. Older, structurally changed installs still migrate.
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
assert "($BundleVersion -eq '14.6.8' -and $optionVersion -in @('14.6.5','14.6.6','14.6.7')" in ps
assert "($stateVersion -eq '' -or $stateVersion -eq $optionVersion)" in ps
assert '$needsMigration = ($versionMismatch -and -not $maintenanceUpgrade)' in ps
assert "$installMode -eq 'resume' -and -not $forceManagedUpdate" in ps
assert "$options['forceManagedUpdate'] = $true" in ps
assert 'LATTICEVALE_MANAGED_UPDATE_STATUS=(available|none|unknown)' in ps
assert 'linux\\check-managed-updates.py' in ps
assert 'Option 6' in ps
# A fresh Option 1 availability check, not the former elapsed-days marker,
# determines whether the APT preflight offers a package-index refresh.
apt_preflight = ps.split("$aptRefreshProbeScript = @'", 1)[1].split("'@", 1)[0]
assert 'MANAGED_REPAIR_REFRESH_DAYS' not in apt_preflight
assert 'LAST_SUCCESS_EPOCH' not in apt_preflight

boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
assert 'now_epoch - last_refresh_epoch >= repair_refresh_interval_seconds' not in boot
assert 'No managed software refresh was requested or confirmed' in boot
assert 'repair_refresh_pending=true' in boot
assert '.repair-package-refresh-pending' in boot
assert 'force_managed_update' in boot
assert 'MANAGED_REPAIR_REFRESH_DAYS=30' in (ROOT/'compatibility.conf').read_text(encoding='utf-8')
assert (ROOT/'VERSION.txt').read_text().strip()=='14.6.8'
# The existing read-only state audit surfaces recorded (not fetched) latest-tag
# digests and must never print user-owned image refs containing credentials.
import importlib.util
with tempfile.TemporaryDirectory(prefix='lv-image-audit-') as tmp:
    from pathlib import Path
    audit_path=ROOT/'stack/state-audit.py'
    spec=importlib.util.spec_from_file_location('latticevale_state_audit_fixture', audit_path)
    audit_mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit_mod)
    inventory=Path(tmp)/'data/latticevale/managed-upstreams.json'
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({'images': {
        'HERMES_IMAGE': {'declaredRef': 'nousresearch/hermes-agent:latest',
                         'repoDigests': ['nousresearch/hermes-agent@sha256:' + 'a'*64]},
        'OLLAMA_IMAGE': {'declaredRef': 'ollama/ollama:latest', 'repoDigests': []},
        'SYNAPSE_IMAGE': {'declaredRef': 'user:secret@registry.invalid/synapse:latest',
                          'repoDigests': ['synapse@sha256:' + 'b'*64]},
        'POSTGRES_IMAGE': {'declaredRef': 'postgres:16-alpine', 'repoDigests': []},
    }}), encoding='utf-8')
    rows=audit_mod.recorded_floating_image_digests(Path(tmp))
    assert rows == ['HERMES_IMAGE=nousresearch/hermes-agent:latest digest=sha256:'+'a'*64,
                    'OLLAMA_IMAGE=ollama/ollama:latest digest=unavailable'], rows
    assert audit_mod.recorded_floating_image_digests(Path(tmp)/'not-present') == []

print('v14.6.6 conditional managed-update fixtures: PASS')
