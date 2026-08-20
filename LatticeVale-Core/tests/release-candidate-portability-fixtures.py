#!/usr/bin/env python3
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
boot=(root/'linux/bootstrap.sh').read_text(encoding='utf-8')
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
compose=(root/'stack/compose.yaml').read_text(encoding='utf-8')
manage=(root/'stack/manage.sh').read_text(encoding='utf-8')
audit=(root/'stack/state-audit.py').read_text(encoding='utf-8')
readme=(root/'README.md').read_text(encoding='utf-8')
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1'}

# PowerShell treats `$Name:` in expandable strings as a scoped-variable reference and
# raises a ParserError unless the variable is delimited. Reject accidental unbraced
# variable-colon interpolation except for known PowerShell scope/provider prefixes.
ps1=(root/'Install-LatticeVale.ps1').read_text()
relay_ps1=(root/'windows/LatticeVale-WslNativeRelay.ps1').read_text()
import re
_bad=[]
_allowed={'env','global','local','script','private','using','variable','function','alias'}
for _label,_source in (('installer',ps1),('native-relay',relay_ps1)):
    for _lineno,_line in enumerate(_source.splitlines(),1):
        for _m in re.finditer(r'\$([A-Za-z_][A-Za-z0-9_]*):', _line):
            if _m.group(1).lower() not in _allowed:
                _bad.append((_label,_lineno,_m.group(1),_line.strip()))
assert not _bad, f'invalid PowerShell variable-before-colon interpolation: {_bad}'
assert ps.startswith('#Requires -Version 5.1\n#Requires -RunAsAdministrator')

# Explicit conservative eligibility instead of assuming the user's machine shape.
for text in (
    'validated for Windows 10/11 client editions, not Windows Server',
    "if ($result.LinuxArchitecture -eq 'amd64')",
    'Assert-LinuxNativeHomeFilesystem',
    "@('9p','drvfs','fuseblk','ntfs','ntfs3','cifs','smb2','vfat','exfat')",
    'Docker Desktop WSL integration is currently supplying the Docker daemon',
    'working Docker daemon is already injected or custom-installed',
    'active rootless Docker daemon/socket was detected',
):
    assert text in ps, text
assert 'tzdata uidmap' in boot

# Persisted port data + fresh collision resolution on both sides of WSL.
port_matrix = [
    ('hermesApiPort','HERMES_API_HOST_PORT'),
    ('dashboardLocalPort','DASHBOARD_HOST_PORT'),
    ('matrixLocalPort','MATRIX_HOST_PORT'),
    ('searxngLocalPort','SEARXNG_HOST_PORT'),
    ('honchoLocalPort','HONCHO_HOST_PORT'),
]
for key, env_name in port_matrix:
    assert key in ps and key in cfg and key in audit
    assert env_name in compose
assert 'Test-WindowsTcpPortAvailable' in ps
assert 'Test-WslTcpPortAvailable' in ps
assert 'Resolve-LatticeValeLocalPort' in ps
assert 'reserve a collision-free host port unconditionally' in ps
assert 'Get-OptionTcpPort' in ps

# Published API must actually be enabled and authenticated by current Hermes.
for line in (
    'set_env data/hermes/.env API_SERVER_ENABLED true',
    'set_env data/hermes/.env API_SERVER_HOST 0.0.0.0',
    'set_env data/hermes/.env API_SERVER_PORT 8642',
    'API_SERVER_KEY',
):
    assert line in cfg
assert '127.0.0.1:${HERMES_API_HOST_PORT:-8642}:8642' in compose
assert 'wait_http Hermes-API http://127.0.0.1:${HERMES_API_HOST_PORT}/health 60' in cfg
assert 'check_http Hermes-API http://127.0.0.1:${HERMES_API_HOST_PORT}/health' in manage
assert 'API_SERVER_CORS_ORIGINS' in cfg and 'remove_env_keys data/hermes/.env API_SERVER_CORS_ORIGINS' in cfg
assert 'remove_env_keys secrets/hermes-runtime.env API_SERVER_ENABLED API_SERVER_HOST API_SERVER_PORT API_SERVER_KEY' in cfg
assert 'HONCHO_SOURCE_COMMIT=444897975c95393b0d48024470ece03c025d3aa4' in cfg
assert 'HERMES_IMAGE=nousresearch/hermes-agent:v2026.8.16' in cfg
assert 'nousresearch/hermes-agent:v2026.8.16' in compose
assert 'nousresearch/hermes-agent:latest' not in cfg
assert 'git -C vendor/honcho fetch --depth 1 origin "$HONCHO_SOURCE_COMMIT"' in cfg

# Exact patch-version state must not be treated as pre-v13; mismatch is repair-worthy.
assert 'version_major' in audit
assert 'legacy_state = state_major is not None and state_major < 13' in audit
assert 'version_mismatch' in audit
assert 'installer options/state versions differ' in audit

# Fixed Compose names cannot delete unrelated resources.
assert 'assert_docker_namespace_safe' in cfg
assert 'com.docker.compose.project.working_dir' in cfg
assert "if [[ \"$project\" != hermesstack" in cfg
assert 'Refusing to reuse a foreign network.' in cfg

# Fresh Matrix config must use selected Matrix host port, not a database secret.
assert 'python3 - "$synapse_db_password" "$registration_secret" "$MATRIX_HOST_PORT"' in cfg
assert "cfg['public_baseurl']=f'http://localhost:{int(sys.argv[3])}/'" in cfg
assert 'while true; do\n      read -r -p "Matrix admin username' in cfg

# TTY regression and special-variable safety remain in place.
assert 'runuser --pty -u "$linux_user"' in boot
assert 'mapfile -t requested_workers' in cfg
assert "mapfile -t requested_workers < <(jq -c '.workers[]?' install-options.json)" in cfg
for forbidden in ('$Home =', '$args ='):
    assert forbidden not in ps



# Pre-existing Docker repository configuration is backed up before normalization.
assert 'repo_stamp="$(date -u +%Y%m%dT%H%M%SZ)"' in boot
assert '"$existing.latticevale-pre-$repo_stamp.bak"' in boot

# Persisted repair state is validated before it can become a path/model/port input.
for text in (
    'Persisted installer options validated.',
    "name_re=re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')",
    "model_re=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$')",
    'assert_hermes_chown_targets_safe',
    'Current Hermes container startup recursively changes ownership at this path',
):
    assert text in cfg, text
assert "jq -r '.[0].Containers // {} | keys[]'" in cfg


# Reject dual-daemon/rootless ambiguity and verify Windows-facing WSL localhost access.
for text in (
    'Get-ExistingRootlessDockerRuntimeInfo',
    '/run/user/$uid/docker.sock',
    'Rootless Docker is already',
    'Verifying Windows localhost access to WSL services',
    'healthy inside WSL but Windows cannot currently reach',
):
    assert text in ps, text

# Documentation must describe the actual conservative boundary.
for text in ('Windows 10/11 client', 'Linux-native filesystem', 'Docker Desktop WSL integration', 'fresh/unmanaged install', 'Resume / repair', 'Local ports and Docker namespace'):
    assert text in readme


# Bundle staging must not depend on the WSL UNC provider being writable.
for text in (
    'function Copy-LocalFileToWslRoot',
    'RedirectStandardInput',
    'Stage through wsl.exe stdin',
):
    assert text in ps, text
assert 'chmod -R 0777' not in ps

# Provider repair must be stage-independent.
provider=cfg[cfg.index('stage_provider_setup() {'):cfg.index('stage_profiles() {')]
assert 'local hermes_image' in provider
assert "sed -n 's/^HERMES_IMAGE=//p' .env" in provider

print('RELEASE CANDIDATE PORTABILITY: PASS')
