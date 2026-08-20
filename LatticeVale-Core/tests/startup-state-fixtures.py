#!/usr/bin/env python3
from pathlib import Path
import tempfile, json, os, subprocess, datetime
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'stack/state-audit.py'

def make_stack(base: Path):
    s=base/'stack'; s.mkdir()
    for f in ['compose.yaml','configure-stack.sh','manage.sh']:
        (s/f).write_text('x\n')
    opts={
        'schema':13,'installerVersion':'13.12.1','dashboard':False,'multiAgent':False,'workers':[],
        'matrix':False,'searxng':False,'qmd':False,'honcho':False,'kanban':False,'tailscale':False,
        'hermesLocalAI':False,'hermesApiPort':8642
    }
    (s/'install-options.json').write_text(json.dumps(opts))
    (s/'.installer-state.json').write_text(json.dumps({'schema':1,'installerVersion':'13.12.1','status':'complete','currentStage':None,'stages':{}}))
    (s/'data/hermes').mkdir(parents=True)
    (s/'data/hermes/config.yaml').write_text('model:\n  default: test/model\n')
    (s/'data/hermes/.env').write_text('API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\nAPI_SERVER_PORT=8642\nAPI_SERVER_KEY=x\n')
    (s/'secrets').mkdir(); (s/'secrets/hermes-runtime.env').write_text('')
    for d in ['data','config','backups','logs','vendor','vault','workspace']:
        (s/d).mkdir(parents=True,exist_ok=True)
    return s

def make_docker(bin_dir: Path, age_seconds: int):
    started=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=age_seconds)).isoformat().replace('+00:00','Z')
    script=bin_dir/'docker'
    script.write_text(f'''#!/usr/bin/env bash
set -e
if [[ "$1" == compose && "$2" == config ]]; then exit 0; fi
if [[ "$1" == info ]]; then exit 0; fi
if [[ "$1" == ps ]]; then echo 'hermes-agent|Up'; exit 0; fi
if [[ "$1" == inspect ]]; then
  echo '{{"Running":true,"StartedAt":"{started}"}}'; exit 0
fi
if [[ "$1" == exec ]]; then exit 1; fi
exit 0
''')
    script.chmod(0o755)

def run_case(age):
    with tempfile.TemporaryDirectory() as td:
        t=Path(td); s=make_stack(t); b=t/'bin'; b.mkdir(); make_docker(b,age)
        env=os.environ.copy(); env['PATH']=str(b)+os.pathsep+env['PATH']
        p=subprocess.run(['python3',str(AUDIT),'--stack',str(s),'--json'],env=env,text=True,capture_output=True,timeout=20)
        assert p.returncode==0,(p.returncode,p.stdout,p.stderr)
        return json.loads(p.stdout)

fresh=run_case(5)
assert fresh['components']['hermes']['status']=='STARTING',fresh
assert fresh['components']['api']['status']=='STARTING',fresh
assert fresh['overall']=='STARTING',fresh
assert fresh['resumeFrom'] is None,fresh
old=run_case(601)
assert old['components']['hermes']['status']=='BROKEN',old
assert old['components']['api']['status']=='BROKEN',old
assert old['overall']=='NEEDS_REPAIR',old
print('STARTUP STATE FIXTURES: PASS')
