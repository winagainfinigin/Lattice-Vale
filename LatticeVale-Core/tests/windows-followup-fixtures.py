#!/usr/bin/env python3
from pathlib import Path
import tempfile, json, os, subprocess, datetime, socket, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'stack/state-audit.py'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *args): pass

def free_port():
    s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p

def make_stack(base: Path, age_seconds: int, api_port: int, hermes_exec_ok: bool):
    s=base/'stack'; s.mkdir()
    for f in ['compose.yaml','configure-stack.sh','manage.sh']:
        (s/f).write_text('x\n')
    opts={
        'schema':13,'installerVersion':'13.12.1','dashboard':False,'multiAgent':False,'workers':[],
        'matrix':False,'searxng':False,'qmd':False,'honcho':False,'kanban':False,'tailscale':True,
        'hermesLocalAI':False,'hermesApiPort':api_port
    }
    (s/'install-options.json').write_text(json.dumps(opts))
    (s/'.installer-state.json').write_text(json.dumps({
        'schema':1,'installerVersion':'13.12.1','status':'complete','currentStage':None,'stages':{},
        'windows':{
            'tailscale':{'status':'PARTIAL','detail':'One or more requested Windows Tailscale Serve mappings were not completed.'},
            'autoStart':{'status':'CONFIGURED','detail':'Scheduled task present.'},
            'windowsApps':{'status':'PARTIAL','detail':'One or more optional Windows apps require follow-up.'},
        }
    }))
    (s/'data/hermes').mkdir(parents=True)
    (s/'data/hermes/config.yaml').write_text('model:\n  default: test/model\n')
    (s/'data/hermes/.env').write_text(f'API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\nAPI_SERVER_PORT={api_port}\nAPI_SERVER_KEY=x\n')
    (s/'secrets').mkdir(); (s/'secrets/hermes-runtime.env').write_text('')
    for d in ['data','config','backups','logs','vendor','vault','workspace']:
        (s/d).mkdir(parents=True,exist_ok=True)
    started=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=age_seconds)).isoformat().replace('+00:00','Z')
    b=base/'bin'; b.mkdir()
    docker=b/'docker'
    exec_body="echo 'Hermes Agent vtest'; exit 0" if hermes_exec_ok else 'exit 1'
    docker.write_text(f'''#!/usr/bin/env bash
set -e
if [[ "$1" == compose && "$2" == config ]]; then exit 0; fi
if [[ "$1" == info ]]; then exit 0; fi
if [[ "$1" == ps ]]; then echo 'hermes-agent|Up'; exit 0; fi
if [[ "$1" == inspect ]]; then echo '{{"Running":true,"StartedAt":"{started}"}}'; exit 0; fi
if [[ "$1" == exec ]]; then {exec_body}; fi
exit 0
''')
    docker.chmod(0o755)
    return s,b

def audit(age, api_server=False, hermes_exec_ok=False):
    with tempfile.TemporaryDirectory() as td:
        base=Path(td); port=free_port(); s,b=make_stack(base,age,port,hermes_exec_ok)
        server=None
        if api_server:
            server=HTTPServer(('127.0.0.1',port),Handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
        env=os.environ.copy(); env['PATH']=str(b)+os.pathsep+env['PATH']
        try:
            p=subprocess.run(['python3',str(AUDIT),'--stack',str(s),'--json'],env=env,text=True,capture_output=True,timeout=20)
            assert p.returncode==0,(p.returncode,p.stdout,p.stderr)
            return json.loads(p.stdout)
        finally:
            if server: server.shutdown(); server.server_close()

fresh=audit(5)
assert fresh['components']['tailscale']['status']=='PARTIAL',fresh
assert fresh['overall']=='STARTING',fresh
assert fresh['resumeFrom'] is None,fresh
assert {x['name'] for x in fresh['windowsFollowup']} >= {'tailscale','windowsApps'},fresh

healthy=audit(601,api_server=True,hermes_exec_ok=True)
assert healthy['components']['hermes']['status']=='RUNNING',healthy
assert healthy['components']['api']['status']=='RUNNING',healthy
assert healthy['components']['tailscale']['status']=='PARTIAL',healthy
assert healthy['overall']=='HEALTHY',healthy
assert healthy['resumeFrom'] is None,healthy
assert {x['name'] for x in healthy['windowsFollowup']} >= {'tailscale','windowsApps'},healthy
print('WINDOWS FOLLOW-UP FIXTURES: PASS')
