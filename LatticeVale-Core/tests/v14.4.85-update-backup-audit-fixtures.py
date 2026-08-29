#!/usr/bin/env python3
from pathlib import Path
import os, subprocess, tempfile, textwrap, tarfile

ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text()
backup=ROOT/'linux/pre-update-safety-backup.sh'
backup_text=backup.read_text()

# Option 6 must not depend on the installed manage.sh it is trying to repair.
update_start=ps.index("if ($forceManagedUpdate) {")
update_end=ps.index("if ($repairMaintenance) {", update_start)
update=ps[update_start:update_end]
assert "pre-update-safety-backup.sh" in update
assert "./manage.sh backup" not in update
assert "cd \"$1\"" not in update
assert "Invoke-WslDirectCapture $DistroName 'root' $backupHelperLinux @($stackLinuxPath,[string]$selectedUid,[string]$selectedGid)" in update
assert "StdErr" in update and "StdOut" in update and "ExitCode" in update
assert "No installer-managed software refresh was started" in update

# Option 3 must print a fresh report after selection, not merely a completion sentence.
assert "function Show-LatticeValeReadOnlyVerification" in ps
verify_start=ps.index("            3 {\n                $installMode = 'verify'")
verify_end=ps.index("            4 {", verify_start)
verify=ps[verify_start:verify_end]
assert "Show-LatticeValeReadOnlyVerification" in verify
helper_start=ps.index("function Show-LatticeValeReadOnlyVerification")
helper_end=ps.index("function Ensure-WindowsTailscaleConnected", helper_start)
helper=ps[helper_start:helper_end]
for text in (
    'LatticeVale read-only verification results',
    '== Linux / Docker / Hermes state ==',
    'Show-WindowsRecoveryAudit',
    '== Verification result ==',
    'Linux overall state:',
    'No changes were made.',
):
    assert text in helper, text

# Backup helper must be bundle-owned, consistent, and self-restoring.
for text in (
    'This deliberately does not call the currently installed manage.sh',
    'pg_dump -U synapse -d synapse -Fc',
    'pg_dump -U honcho -d honcho -Fc',
    'docker compose stop --timeout 45',
    'docker compose start "${RUNNING_SERVICES[@]}"',
    'data/hermes', 'data/qmd', 'data/ollama', 'vault', 'workspace',
    'PREUPDATE_BACKUP_OK path=',
    'PREUPDATE_BACKUP_FAILED step=',
    'bundle-owned pre-update backup must run as WSL root',
    'chown -R "$OWNER_UID:$OWNER_GID"',
):
    assert text in backup_text, text
assert './manage.sh' not in '\n'.join(line for line in backup_text.splitlines() if not line.lstrip().startswith('#'))


def make_fake_docker(bin_dir: Path, fail_dump=False):
    # The production installer invokes this helper as WSL root. Fixture PATH supplies
    # a minimal id shim so the bundle-owned root-only contract can be tested without
    # requiring privileged GitHub runners.
    idshim=bin_dir/'id'
    idshim.write_text('#!/usr/bin/env bash\nif [[ "${1:-}" == "-u" ]]; then echo 0; else /usr/bin/id "$@"; fi\n')
    idshim.chmod(0o755)
    script=bin_dir/'docker'
    script.write_text(textwrap.dedent(f'''\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$FAKE_DOCKER_LOG"
        if [[ "${{1:-}}" == compose && "${{2:-}}" == version ]]; then exit 0; fi
        if [[ "${{1:-}}" == compose && "${{2:-}}" == config ]]; then exit 0; fi
        if [[ "${{1:-}}" == compose && "${{2:-}}" == ps && "${{3:-}}" == --services ]]; then
          printf 'synapse-db\\nhoncho-db\\nhermes\\n'
          exit 0
        fi
        if [[ "${{1:-}}" == compose && "${{2:-}}" == exec ]]; then
          service="${{4:-}}"
          if [[ {str(fail_dump).lower()} == true && "$service" == synapse-db ]]; then
            echo 'forced Synapse pg_dump failure for fixture' >&2
            exit 7
          fi
          printf 'PGDMPfixture-%s' "$service"
          exit 0
        fi
        if [[ "${{1:-}}" == compose && "${{2:-}}" == stop ]]; then exit 0; fi
        if [[ "${{1:-}}" == compose && "${{2:-}}" == start ]]; then exit 0; fi
        exit 0
    '''))
    script.chmod(0o755)

with tempfile.TemporaryDirectory(prefix='lv-hf2-backup-') as td:
    td=Path(td); stack=td/'hermes-stack'; bindir=td/'bin'; bindir.mkdir(); stack.mkdir()
    (stack/'compose.yaml').write_text('services: {}\n')
    (stack/'.env').write_text('SECRET=fixture\n')
    (stack/'install-options.json').write_text('{"matrix":true,"honcho":true}\n')
    for rel,content in (
        ('data/hermes/state.db','hermes'),('data/qmd/index.db','qmd'),
        ('data/ollama/models/model.bin','model'),('vault/note.md','vault'),('workspace/file.txt','workspace')
    ):
        p=stack/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content)
    log=td/'docker.log'; make_fake_docker(bindir)
    env=os.environ.copy(); env['PATH']=f"{bindir}:{env['PATH']}"; env['FAKE_DOCKER_LOG']=str(log)
    run=subprocess.run(['bash',str(backup),str(stack)],text=True,capture_output=True,env=env,timeout=30)
    assert run.returncode==0, run.stdout+'\n'+run.stderr
    assert 'PREUPDATE_BACKUP_OK path=' in run.stdout
    targets=sorted((stack/'backups').glob('pre-update-*'))
    assert len(targets)==1, targets
    target=targets[0]
    assert (target/'synapse.dump').read_bytes().startswith(b'PGDMP')
    assert (target/'honcho.dump').read_bytes().startswith(b'PGDMP')
    assert (target/'files.tar.gz').is_file()
    with tarfile.open(target/'files.tar.gz','r:gz') as tf:
        names=set(tf.getnames())
    for expected in ('.env','install-options.json','data/hermes','data/qmd','data/ollama','vault','workspace'):
        assert expected in names or any(n.startswith(expected.rstrip('/')+'/') for n in names), expected
    calls=log.read_text()
    assert 'compose stop --timeout 45 synapse-db honcho-db hermes' in calls
    assert 'compose start synapse-db honcho-db hermes' in calls

with tempfile.TemporaryDirectory(prefix='lv-hf2-backup-fail-') as td:
    td=Path(td); stack=td/'hermes-stack'; bindir=td/'bin'; bindir.mkdir(); stack.mkdir()
    (stack/'compose.yaml').write_text('services: {}\n')
    (stack/'install-options.json').write_text('{}\n')
    log=td/'docker.log'; make_fake_docker(bindir, fail_dump=True)
    env=os.environ.copy(); env['PATH']=f"{bindir}:{env['PATH']}"; env['FAKE_DOCKER_LOG']=str(log)
    run=subprocess.run(['bash',str(backup),str(stack)],text=True,capture_output=True,env=env,timeout=30)
    assert run.returncode==7, (run.returncode,run.stdout,run.stderr)
    assert 'forced Synapse pg_dump failure for fixture' in run.stderr
    assert 'PREUPDATE_BACKUP_FAILED step=dump-synapse-postgres exit=7' in run.stderr
    assert not list((stack/'backups').glob('*.partial'))

print('v14.4.85 UPDATE BACKUP + READ-ONLY AUDIT FIXTURES: PASS')
