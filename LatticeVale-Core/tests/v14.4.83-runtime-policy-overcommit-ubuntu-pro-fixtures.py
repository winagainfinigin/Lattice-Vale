#!/usr/bin/env python3
"""v14.4.83 targeted runtime-policy, sysctl, Ubuntu-Pro-removal, and command regressions."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
VERSION = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert VERSION in {'14.4.84','14.4.85','14.5.0'}, VERSION

cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
manage = (ROOT / 'stack/manage.sh').read_text(encoding='utf-8')
boot = (ROOT / 'linux/bootstrap.sh').read_text(encoding='utf-8')
assert 'prereq_packages=(ca-certificates curl git gnupg jq openssl procps python3 python3-yaml sudo tzdata uidmap)' in boot
audit = (ROOT / 'stack/state-audit.py').read_text(encoding='utf-8')
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
root_readme = (REPO / 'README.md').read_text(encoding='utf-8')
features = (REPO / 'docs/FEATURES.md').read_text(encoding='utf-8')
instructions = (REPO / 'docs/Instructions.txt').read_text(encoding='utf-8')

# v4 must converge through every clean/repair/start/audit path that owns the overlay.
assert "printf 'POLICY_VERSION=4\\nCPUS=%s" in cfg
assert 'saved_version" == 4' in cfg
assert 'saved_version" != 4' in manage
assert r'\$saved_version" != 4' in boot
assert 'values.get("POLICY_VERSION") != "4"' in audit
assert 'run_uncheckpointed_repair_step repair_runtime_policy' in cfg
assert 'state_mark infrastructure pending' in cfg and 'state_mark reconcile pending' in cfg

# Execute the exact embedded planner at the observed full-stack ~10 GiB shape.
start = cfg.index("import sys\nbudget=int(sys.argv[1])", cfg.index("<<'PY_RESOURCE_PLAN'"))
end = cfg.index('\nPY_RESOURCE_PLAN', start)
planner = cfg[start:end]
required_services = ('hermes','synapse-db','synapse','searxng-valkey','searxng','qmd','qmd-indexer','honcho-db','honcho-redis','honcho-api','honcho-deriver','ollama')
observed_alloc = None
for budget in (2048, 3072, 4096, 5120, 6144, 7460, 8192, 12288):
    r = subprocess.run([sys.executable, '-c', planner, str(budget), 'true', 'true', 'true', 'true', 'true'], text=True, capture_output=True, timeout=10)
    assert r.returncode == 0, r.stderr
    alloc = {}
    for line in r.stdout.splitlines():
        k, v = line.split('=', 1)
        alloc[k] = int(v)
    assert sum(alloc.values()) <= budget, (sum(alloc.values()), budget, alloc)
    for required in required_services:
        assert required in alloc and alloc[required] > 0, (required, budget, alloc)
    if budget == 7460:
        observed_alloc = alloc
assert observed_alloc is not None
assert observed_alloc['ollama'] >= 4096, observed_alloc

# Redis/Valkey sysctl is selected-workload-only, persistent, idempotent, and audited.
for token in (
    "redis_like = d.get('searxng',False) is True or d.get('honcho',False) is True",
    'if [[ "$redis_like_required" == true ]]; then',
    'overcommit_file=/etc/sysctl.d/99-latticevale-redis-valkey.conf',
    'vm.overcommit_memory = 1',
    'chmod 0644 "$overcommit_file"',
    'sysctl -w vm.overcommit_memory=1',
    'sysctl -n vm.overcommit_memory',
):
    assert token in boot, token
assert 'redis_like_enabled' in audit and 'vm.overcommit_memory is not 1' in audit

# Ubuntu Pro is removed from all active ownership surfaces without destructive cleanup.
for text in (ps, cfg):
    assert 'ubuntuPro' not in text
assert 'Install Ubuntu Pro for WSL?' not in ps
assert 'Canonical.UbuntuProforWSL' not in ps
for destructive in ('pro detach', 'apt purge ubuntu-advantage', 'apt-get purge ubuntu-advantage'):
    assert destructive not in (ps + boot + cfg).lower()
assert '## 3.20 Ubuntu Pro for WSL' not in features
assert 'Ubuntu Pro integration removed' in root_readme

# Clean/change/repair current prompts and persisted options omit Ubuntu Pro.
assert 'Runtime/Windows policy: container limits, updates, WSL lifetime, auto-start, shortcuts, timezone' in ps
assert 'ubuntuPro = $ubuntuPro' not in ps

# Completion/docs must target selected Linux user so $HOME resolves correctly.
for verb in ('verify','audit','status'):
    expected = f'wsl -d $DistroName -u $linuxUser -- bash -lc'
    assert expected in ps
    assert f'./manage.sh {verb}' in ps
assert '$LinuxUser = Read-Host "Enter the Linux user selected for LatticeVale"' in root_readme
assert 'wsl -d $Distro -u $LinuxUser -- bash -lc' in root_readme
assert 'wsl -d <DISTRO> -u <LINUX_USER> -- bash -lc' in instructions
assert 'wsl -d <your-distro-name> -- bash -lc' not in instructions

print('v14.4.83 runtime-policy/overcommit/Ubuntu-Pro-removal fixtures: PASS')
