#!/usr/bin/env python3
from pathlib import Path
import base64, datetime, json, os, re, subprocess, tempfile, textwrap

ROOT=Path(__file__).resolve().parents[1]
PS=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
BOOT=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
CFG=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
MANAGE=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
RELAY=(ROOT/'windows/LatticeVale-WslNativeRelay.ps1').read_text(encoding='utf-8')
AUDIT=ROOT/'stack/state-audit.py'
version=(ROOT/'VERSION.txt').read_text().strip()
assert version in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}

# The bug that produced '/vault': managed stack path must be initialized before repair call.
assign=PS.index('$stackLinuxPath = "$($linuxHome.TrimEnd(\'/\'))/hermes-stack"')
call=PS.index('Repair-LegacyObsidianStackVaultMount $DistroName $stackLinuxPath $obsidianVaultWslPath')
assert assign < call, (assign,call)
repair=PS[PS.index('function Repair-LegacyObsidianStackVaultMount'):PS.index('\nfunction Get-OptionTcpPort')]
assert 'managed Linux stack path is invalid or empty' in repair
assert 'ExpectedSourcePath' in repair
assert 'src == source && dest == target && bind' in repair
assert "base64 -d | bash -s --" in repair

# Exercise the exact fstab rewrite with a path containing a space. It must remove only
# the selected LatticeVale source+target bind and preserve an unrelated bind.
m=re.search(r"\$cleanupShell = @'\n(.*?)\n'@", repair, re.S)
assert m, 'cleanup shell not found'
cleanup=m.group(1)
with tempfile.TemporaryDirectory() as td:
    fstab=Path(td)/'fstab'
    fstab.write_text(
        '# test\n'
        '/mnt/d/Libraries/Documents/Obsidian\\040Vault /home/testuser/hermes-stack/vault none bind 0 0\n'
        '/mnt/e/Other\\040Vault /home/testuser/other-vault none bind 0 0\n', encoding='utf-8')
    target=base64.b64encode(b'/home/testuser/hermes-stack/vault').decode()
    source=base64.b64encode(b'/mnt/d/Libraries/Documents/Obsidian Vault').decode()
    bindir=Path(td)/'bin'; bindir.mkdir()
    findmnt=bindir/'findmnt'
    findmnt.write_text('#!/bin/sh\nprintf \'9p\\n\'\n', encoding='utf-8')
    findmnt.chmod(0o755)
    env=os.environ.copy(); env['PATH']=str(bindir)+os.pathsep+env.get('PATH','')
    p=subprocess.run(['bash','-s','--',target,source,str(fstab)],input=cleanup,text=True,capture_output=True,timeout=15,env=env)
    assert p.returncode==0,(p.stdout,p.stderr)
    out=fstab.read_text()
    assert 'hermes-stack/vault' not in out
    assert '/mnt/e/Other\\040Vault /home/testuser/other-vault' in out
    assert Path(str(fstab)+'.latticevale-v14.1.3.bak').is_file()

# WSL compatibility fallback may happen only for a CLI-level rejection of `--`, not
# every Linux non-zero status (which could duplicate mutating commands).
cap=PS[PS.index('function Invoke-WslDirectCapture'):PS.index('\nfunction Get-WslOsRelease')]
assert 'Test-WslCliRejectedArgumentSeparator $attempt' in cap
assert cap.index('if (-not (Test-WslCliRejectedArgumentSeparator $attempt))') < cap.index('$legacyArgs =')
assert 'Text = $attempt.StdOut' in cap
assert 'windows subsystem for linux' in PS.lower()
assert 'function Test-WslCliRejectedArgumentSeparator' in RELAY
relay_call=RELAY[RELAY.index('function Invoke-WslDistroCommand'):RELAY.index('\nfunction Test-WslDistroRunning')]
assert 'Test-WslCliRejectedArgumentSeparator $probe' in relay_call

# Resume uses local state before network/update-like actions.
assert 'docker compose up -d --pull never --no-build' in CFG
infra=CFG[CFG.index('stage_infrastructure()'):CFG.index('\nstage_matrix_bootstrap()')]
assert infra.index('start_existing_infrastructure_for_repair') < infra.index('docker compose pull --ignore-buildable')
provider=CFG[CFG.index('stage_provider_setup()'):CFG.index('\nstage_profiles()')]
if version in {'14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}:
    assert 'repair_maintenance_enabled && ! repair_package_refresh_pending && docker image inspect "$hermes_image"' in provider
    assert 'repair_package_refresh_pending' in provider
else:
    assert 'repair_maintenance_enabled && docker image inspect "$hermes_image"' in provider
assert 'no implicit pull' in provider
assert 'installing only missing official Docker packages' in BOOT
assert '"${missing_docker_packages[@]}"' in BOOT
assert "-name 'pre-*'" in CFG and "^pre-[A-Za-z0-9._-]+-[0-9]{8}T[0-9]{6}Z$" in CFG
assert 'install -d -m 0700 "$target"' in MANAGE
assert 'if [[ "$obsidian_selected" != true ]]; then\n  repair_user_tree vault' in BOOT


# Ordinary lifecycle/start paths must never turn into implicit dependency updates. In
# particular, Compose treats :latest specially under its default pull policy, and this
# bundle intentionally contains selected latest-tag services.
assert 'searxng/searxng:2026.8.17-374939b88' in (ROOT/'stack/compose.yaml').read_text(encoding='utf-8')
assert 'ollama/ollama:0.32.14' in (ROOT/'stack/compose.yaml').read_text(encoding='utf-8')
assert 'docker compose up -d --pull never --no-build' in BOOT
case_root=MANAGE.index('case "$cmd" in')
start_pos=MANAGE.index('  start)', case_root)
stop_pos=MANAGE.index('  stop)', start_pos)
start_case=MANAGE[start_pos:stop_pos]
assert 'ensure_docker_for_user' in start_case
assert 'docker compose up -d --pull never --no-build' in start_case
assert 'start_selected_matrix_profile_gateways' in start_case
assert 'docker compose up -d --pull never --no-build --remove-orphans' in CFG

# Local-first recovery is bounded by one wall-clock deadline and uses cheap Docker
# state/health probes. It must not loop the expensive full infrastructure verifier.
local_repair=CFG[CFG.index('start_existing_infrastructure_for_repair()'):CFG.index('\nstage_infrastructure()')]
assert 'service_ready_for_local_repair' in local_repair
assert '+ 120' in local_repair
assert local_repair.count('verify_infrastructure') == 1
assert 'while (( $(date +%s) < deadline ))' in local_repair

# Informational repair sizing must be bounded and must not traverse a selected external
# Obsidian vault. Bootstrap log sizing is likewise advisory and bounded.
storage_report=CFG[CFG.index('show_repair_storage_report()'):CFG.index('\nprune_old_installer_config_backups()')]
assert 'timeout --foreground --kill-after=2s 8s du -skx .' in storage_report
assert '[[ "$(opt_bool obsidian)" == true ]] || report_paths+=(vault)' in storage_report
assert 'timeout --foreground --kill-after=2s 10s du -shx --' in storage_report
assert 'timeout --foreground --kill-after=2s 10s du -skx -- "$stack_dir/logs"' in BOOT

# Per-stage revision bumps are explicit migrations, not ordinary repair. A live/healthy
# pre-migration runtime must not let local-first recovery silently mark a newer epoch done.
assert 'state_stage_revision_stale()' in CFG
assert 'RUN_STAGE_MIGRATION_REQUIRED=true' in CFG
if version in {'14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}:
    assert 'repair_maintenance_enabled && ! repair_package_refresh_pending && [[ "${RUN_STAGE_MIGRATION_REQUIRED:-false}" != true ]]' in infra
else:
    assert 'repair_maintenance_enabled && [[ "${RUN_STAGE_MIGRATION_REQUIRED:-false}" != true ]]' in infra

# Retention may delete only a proven installer snapshot, never a user folder that merely
# happens to match the pre-<name>-timestamp naming convention.
retention=CFG[CFG.index('prune_old_installer_config_backups()'):CFG.index('\ncap_installer_event_log()')]
assert '[[ -f "$d/installer-config.tar.gz" && ! -L "$d/installer-config.tar.gz" ]] || continue' in retention

# State audit: an explicitly stopped LatticeVale container is STOPPED, not BROKEN; a real
# nonzero runtime exit remains a repair condition.
def stack_fixture(base: Path):
    s=base/'stack'; s.mkdir()
    for f in ('compose.yaml','configure-stack.sh','manage.sh'):
        (s/f).write_text('x\n')
    opts={'schema':13,'installerVersion':'13.16.11','dashboard':False,'multiAgent':False,'workers':[],
          'matrix':False,'searxng':False,'qmd':False,'honcho':False,'kanban':False,'tailscale':False,
          'hermesLocalAI':False,'hermesApiPort':8642}
    (s/'install-options.json').write_text(json.dumps(opts))
    (s/'.installer-state.json').write_text(json.dumps({'schema':1,'installerVersion':'13.16.11','status':'complete','currentStage':None,'stages':{}}))
    (s/'data/hermes').mkdir(parents=True); (s/'data/hermes/config.yaml').write_text('model:\n  default: test/model\n')
    (s/'data/hermes/.env').write_text('API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\nAPI_SERVER_PORT=8642\nAPI_SERVER_KEY=x\n')
    (s/'secrets').mkdir(); (s/'secrets/hermes-runtime.env').write_text('')
    for d in ('config','backups','logs','vendor','vault','workspace','data/qmd','data/synapse','data/searxng-valkey','data/honcho-redis'):
        (s/d).mkdir(parents=True,exist_ok=True)
    return s

def run_audit(exit_code: int):
    with tempfile.TemporaryDirectory() as td:
        t=Path(td); s=stack_fixture(t); b=t/'bin'; b.mkdir()
        docker=b/'docker'
        state={'Running':False,'Status':'exited','ExitCode':exit_code,'OOMKilled':False,'Error':'','StartedAt':'0001-01-01T00:00:00Z'}
        docker.write_text(textwrap.dedent(f'''\
            #!/usr/bin/env bash
            if [[ "$1" == compose && "$2" == config ]]; then exit 0; fi
            if [[ "$1" == info ]]; then exit 0; fi
            if [[ "$1" == ps && "$2" == -a ]]; then echo 'hermes-agent|Exited'; exit 0; fi
            if [[ "$1" == inspect ]]; then
              printf '%s\\n%s\\n' '{json.dumps(state)}' 'unless-stopped'; exit 0
            fi
            if [[ "$1" == exec ]]; then exit 1; fi
            exit 0
        ''')); docker.chmod(0o755)
        env=os.environ.copy(); env['PATH']=str(b)+os.pathsep+env['PATH']
        p=subprocess.run(['python3',str(AUDIT),'--stack',str(s),'--json'],env=env,text=True,capture_output=True,timeout=20)
        assert p.returncode==0,(p.stdout,p.stderr)
        return json.loads(p.stdout)

stopped=run_audit(143)
assert stopped['components']['hermes']['status']=='STOPPED',stopped
assert stopped['components']['api']['status']=='STOPPED',stopped
assert stopped['overall']=='STOPPED',stopped
assert stopped['resumeFrom'] is None,stopped
failed=run_audit(1)
assert failed['components']['hermes']['status']=='BROKEN',failed
assert failed['overall']=='NEEDS_REPAIR',failed


# A partially stopped selected runtime is not a healthy intentional full-stack stop.
def run_partial_stop_audit():
    with tempfile.TemporaryDirectory() as td:
        t=Path(td); s=stack_fixture(t)
        opts=json.loads((s/'install-options.json').read_text())
        opts['qmd']=True
        (s/'install-options.json').write_text(json.dumps(opts))
        # QMD's configured marker is the data directory, already created by stack_fixture.
        b=t/'bin'; b.mkdir(); docker=b/'docker'
        running={'Running':True,'Status':'running','ExitCode':0,'OOMKilled':False,'Error':'','StartedAt':'2020-01-01T00:00:00Z'}
        stopped_state={'Running':False,'Status':'exited','ExitCode':143,'OOMKilled':False,'Error':'','StartedAt':'2020-01-01T00:00:00Z'}
        running_json=json.dumps(running)
        stopped_json=json.dumps(stopped_state)
        script="""#!/usr/bin/env bash
if [[ "$1" == compose && "$2" == config ]]; then exit 0; fi
if [[ "$1" == info ]]; then exit 0; fi
if [[ "$1" == ps && "$2" == -a ]]; then
  printf '%s\\n' 'hermes-agent|Up' 'hermes-qmd|Exited (143)' 'hermes-qmd-indexer|Up'; exit 0
fi
if [[ "$1" == inspect ]]; then
  name="${@: -1}"
  if [[ "$name" == hermes-qmd ]]; then st='__STOPPED__'; else st='__RUNNING__'; fi
  printf '%s\\n%s\\n' "$st" 'unless-stopped'; exit 0
fi
if [[ "$1" == exec && "$4" == hermes-agent ]]; then exit 0; fi
if [[ "$1" == exec && "$2" == hermes-qmd ]]; then exit 1; fi
exit 0
""".replace('__STOPPED__',stopped_json).replace('__RUNNING__',running_json)
        docker.write_text(script); docker.chmod(0o755)
        env=os.environ.copy(); env['PATH']=str(b)+os.pathsep+env['PATH']
        p=subprocess.run(['python3',str(AUDIT),'--stack',str(s),'--json'],env=env,text=True,capture_output=True,timeout=20)
        assert p.returncode==0,(p.stdout,p.stderr)
        report=json.loads(p.stdout)
        assert report['components']['qmd']['status']=='STOPPED',report
        assert report['overall']=='NEEDS_REPAIR',report
        assert any('stopped while the rest of the stack is active' in n for n in report['notes']),report

run_partial_stop_audit()

print('V13.16.11 FULL REPAIR AUDIT FIXTURES: PASS')
