#!/usr/bin/env python3
from pathlib import Path
import re, yaml
ROOT=Path(__file__).resolve().parents[1]
configure=(ROOT/'stack/configure-stack.sh').read_text()
compose_text=(ROOT/'stack/compose.yaml').read_text()
compose=yaml.safe_load(compose_text)
ps1=(ROOT/'Install-LatticeVale.ps1').read_text()
dockerfile=(ROOT/'stack/Dockerfile.qmd').read_text()
manage=(ROOT/'stack/manage.sh').read_text()
state_audit=(ROOT/'stack/state-audit.py').read_text()
patcher=(ROOT/'stack/patch-qmd-bind.py').read_text()

assert 'INSTALLER_VERSION="$(opt_text installerVersion)"' in configure
assert 'installerVersion = $bundleVersion' in ps1
hash_section=configure[configure.index('OPTIONS_HASH='):configure.index('CURRENT_STAGE="startup"')]
assert "payload=json.dumps({'options':d}" in hash_section
assert "{'installerVersion':ver,'options':d}" not in hash_section
assert 'checkpoint_revision()' in configure
assert 'state_stage_legacy_adoptable()' in configure
assert 'resume_adoption_allowed()' in configure
assert 'QMD_VERSION=2.5.3' in configure
assert 'ARG QMD_VERSION=2.5.3' in dockerfile
assert '${QMD_VERSION:-2.5.3}' in compose_text
assert '${QMD_VERSION:-latest}' not in compose_text
assert r'mkdir -p \"$$HOME\"' in compose_text
assert '--host 0.0.0.0' not in compose_text
assert 'COPY patch-qmd-bind.py /tmp/patch-qmd-bind.py' in dockerfile
assert 'Expected exactly one QMD localhost HTTP listen binding to patch' in patcher
assert 'httpServer.listen(port, \"0.0.0.0\"' in patcher
assert '--no-cache qmd' not in configure
assert 'docker compose up -d --pull never --no-build --no-deps qmd' in configure
assert 'qmd_health_ok' in configure
assert 'qmd_quarantine_index' in configure
assert 'data/qmd/cache/index.sqlite' in configure
assert "database.*malformed|schema' <<<\"$logs\"; then" in configure
assert 'mv data/qmd/cache/models' not in configure
assert 'quote_env_key_literal secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH' in configure
qmd=compose['services']['qmd']; idx=compose['services']['qmd-indexer']
assert 'ports' not in qmd or not qmd.get('ports')
for svc in (qmd,idx):
    env=svc['environment']
    assert env['HOME']=='/tmp/qmd-home'
    assert env['QMD_CONFIG_DIR']=='/home/node/.config/qmd'
    assert env['XDG_CACHE_HOME']=='/home/node/.cache'
    assert env['INDEX_PATH']=='/home/node/.cache/qmd/index.sqlite'
assert 'Convert-LinuxPathToWslUnc' in ps1
assert 'Existing installer-managed LatticeVale stack found for Ubuntu user' in ps1
assert 'Get-LatticeValeScheduledTaskName' in ps1
assert "$nativeArch -ne 'X64'" in ps1
assert "Reusing installer-owned self-hosted Honcho source commit" in configure
assert "Preserving custom/legacy Honcho source commit" in configure
assert "Periodic repair refresh: reconciling installer-owned Honcho source" in configure
assert "git -C vendor/honcho fetch --depth 1 origin HEAD" not in configure
assert "api.github.com/repos/plastic-labs/honcho/releases/latest" not in manage
assert "git -C vendor/honcho fetch --depth 1 origin HEAD" in manage
assert '("qmd", "qmd", "hermes-qmd", None' in state_audit
assert '["docker", "exec", "hermes-qmd", "curl"' in state_audit
print('V13 RECOVERY HARDENING FIXTURES: PASS')
print('- installer-version changes no longer invalidate every healthy checkpoint; stage revisions target migrations')
print('- QMD is pinned, Docker-internal only, independently started, diagnosed, and backup-first repaired')
print('- dashboard scrypt hash is protected from Compose $ interpolation')
print('- QMD runtime and final UNC path support non-default users/homes')
