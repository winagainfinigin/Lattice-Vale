#!/usr/bin/env python3
"""Deterministic v14.4.3 RAM-policy and uninstall-preservation regressions."""
from pathlib import Path
import json
import os
import pwd
import shutil
import subprocess
import tempfile
import yaml

root = Path(__file__).resolve().parents[1]
cs = (root / 'stack/configure-stack.sh').read_text(encoding='utf-8')
boot = (root / 'linux/bootstrap.sh').read_text(encoding='utf-8')
uninstall = (root / 'Uninstall-LatticeVale.ps1').read_text(encoding='utf-8')
version = (root / 'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}, version

# Clean + repair adoption must both converge on policy v3. The startup helper is the
# repair/cold-start migration backstop when a saved adaptive overlay is stale.
assert 'POLICY_VERSION=3' in cs
assert 'saved_version" != 3' in boot
assert './configure-stack.sh --refresh-resource-policy' in boot
assert "compose_files='compose.yaml'" in cs
assert "compose_files+=':compose.latticevale.yaml'" in cs
assert "compose_files+=':compose.override.yaml'" in cs
assert 'compose.override.yaml' in cs
assert 'max_connections=200' in cs
assert 'MALLOC_ARENA_MAX:' in cs
assert 'SYNAPSE_CACHE_FACTOR:' in cs
assert 'shared_buffers=%s' in cs

# No global WSL memory/reclaim writer belongs in the RAM-efficiency patch.
for source in (cs, boot):
    assert 'autoMemoryReclaim=' not in source


def run_refresh(mode: str, seed_v2: bool = False) -> Path:
    td = Path(tempfile.mkdtemp(prefix=f'lv-1443-{mode}-'))
    shutil.copy2(root / 'stack/configure-stack.sh', td / 'configure-stack.sh')
    options = {
        'schema': 19,
        'installerVersion': version,
        'installerMode': mode,
        'timezone': 'Etc/UTC',
        'containerResourceLimits': True,
        'matrix': True,
        'searxng': True,
        'qmd': True,
        'honcho': True,
        'hermesLocalAI': True,
        'ollamaBackend': 'managed',
        'ollamaAcceleration': 'cpu',
        'localTextModel': 'qwen3.5:4b',
        'localEmbeddingModel': 'qwen3-embedding:4b',
    }
    (td / 'install-options.json').write_text(json.dumps(options), encoding='utf-8')
    (td / 'compose.override.yaml').write_text(
        'services:\n  hermes:\n    environment:\n      USER_OVERRIDE_SENTINEL: "1"\n',
        encoding='utf-8',
    )
    if seed_v2:
        (td / '.latticevale-resource-state').write_text(
            'POLICY_VERSION=2\nCPUS=1\nMEM_MIB=4096\nRESERVE_MIB=1024\nBUDGET_MIB=3072\n',
            encoding='utf-8',
        )
    preexec = None
    if os.geteuid() == 0:
        # configure-stack.sh intentionally refuses root. Drop only the child process
        # to the conventional unprivileged nobody account so this fixture also works
        # in root-run build containers.
        nobody = pwd.getpwnam('nobody')
        td.chmod(0o777)
        (td / 'configure-stack.sh').chmod(0o755)
        for owned in (td / 'configure-stack.sh', td / 'install-options.json', td / 'compose.override.yaml', td / '.latticevale-resource-state'):
            if owned.exists():
                os.chown(owned, nobody.pw_uid, nobody.pw_gid)
        def drop_privileges():
            os.setgid(nobody.pw_gid)
            os.setuid(nobody.pw_uid)
        preexec = drop_privileges
    proc = subprocess.run(
        ['bash', str(td / 'configure-stack.sh'), '--refresh-resource-policy'],
        cwd=td,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        env={**os.environ, 'HOME': str(td)},
        preexec_fn=preexec,
    )
    assert proc.returncode == 0, proc.stdout
    assert (td / '.latticevale-resource-state').read_text(encoding='utf-8').startswith('POLICY_VERSION=3\n')
    env_line = next(x for x in (td / '.env').read_text(encoding='utf-8').splitlines() if x.startswith('COMPOSE_FILE='))
    assert env_line == 'COMPOSE_FILE=compose.yaml:compose.latticevale.yaml:compose.override.yaml', env_line
    overlay = yaml.safe_load((td / 'compose.latticevale.yaml').read_text(encoding='utf-8'))
    services = overlay['services']
    assert str(services['hermes']['environment']['MALLOC_ARENA_MAX']) in {'2', '4'}
    assert str(services['synapse']['environment']['SYNAPSE_CACHE_FACTOR']) in {'0.25', '0.35', '0.5', '0.50'}
    assert 'shared_buffers=' in ' '.join(map(str, services['synapse-db']['command']))
    honcho_cmd = ' '.join(map(str, services['honcho-db']['command']))
    assert 'shared_buffers=' in honcho_cmd
    assert 'max_connections=200' in honcho_cmd
    return td

clean = repair = None
try:
    clean = run_refresh('fresh', False)
    repair = run_refresh('repair', True)
finally:
    for td in (clean, repair):
        if td:
            shutil.rmtree(td, ignore_errors=True)

# Preservation-first uninstaller invariants.
assert 'function Test-AnyScheduledTaskReferencesPath' in uninstall
assert 'function Test-AnyDesktopShortcutReferencesPath' in uninstall
assert 'function Send-LatticeValeEnvironmentChanged' in uninstall
assert 'A desktop shortcut still references this stack-specific LatticeVale shortcut helper/config' in uninstall
assert 'A scheduled task still references' in uninstall
assert 'Refusing a partial uninstall/purge that could leave restartable containers behind' in uninstall
assert 'Start/repair Docker, then rerun the uninstaller.' in uninstall
assert "[string]$rule.Group -eq 'LatticeVale'" in uninstall
assert 'Send-LatticeValeEnvironmentChanged' in uninstall
assert 'getent passwd' in uninstall
assert 'rm -f /var/log/hermes-dockerd.log' in uninstall

# Runtime cleanup must happen before Windows integration removal, so a fail-closed
# Docker cleanup abort cannot leave a half-uninstalled Windows side.
assert uninstall.index('Stop-And-RemoveStack $DistroName $LinuxUser $stack $purge') < uninstall.index("Write-Step 'Removing installer-owned Windows integrations'")

# Normal uninstall must never cross the WSL registration boundary.
assert 'wsl --unregister' not in uninstall.lower()
assert "'--unregister'" not in uninstall.lower()

print('v14.4.3+ RAM/uninstaller fixtures: PASS')
