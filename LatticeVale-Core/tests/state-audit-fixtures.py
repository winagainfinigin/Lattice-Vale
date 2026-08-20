#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, tempfile

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'stack/state-audit.py'

def run(stack):
    p=subprocess.run(['python3',str(AUDIT),'--stack',str(stack),'--json','--offline'],text=True,capture_output=True,check=True)
    return json.loads(p.stdout)

def write_model(path, model='test/model'):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(f'model:\n  default: {model}\n',encoding='utf-8')

with tempfile.TemporaryDirectory() as td:
    s=Path(td)
    for f in ('compose.yaml','configure-stack.sh','manage.sh'):
        (s/f).write_text('x\n')
    opts={'dashboard':False,'multiAgent':True,'workers':[{'name':'coder'}],'kanban':False,'matrix':False,'searxng':False,'qmd':False,'honcho':False,'tailscale':False}
    (s/'install-options.json').write_text(json.dumps(opts))
    write_model(s/'data/hermes/config.yaml')
    write_model(s/'data/hermes/profiles/coder/config.yaml')
    # Deliberately lie in the checkpoint file: a missing Docker runtime and missing .env
    # must still produce NEEDS_REPAIR because actual state wins.
    (s/'.installer-state.json').write_text(json.dumps({'schema':1,'installerVersion':'v12','status':'complete','currentStage':None,'stages':{'reconcile':{'status':'done'}}}))
    r=run(s)
    assert r['components']['hermes']['status'] in ('CONFIGURED','RUNNING')
    assert r['profiles'][0]['status']=='CONFIGURED'
    assert r['components']['docker']['status'] in ('NOT_INSTALLED','CONFIGURED','BROKEN')
    assert r['overall']=='NEEDS_REPAIR', r

with tempfile.TemporaryDirectory() as td:
    s=Path(td)
    for f in ('compose.yaml','configure-stack.sh','manage.sh'):
        (s/f).write_text('x\n')
    (s/'install-options.json').write_text(json.dumps({'dashboard':False,'multiAgent':False,'workers':[],'matrix':True,'searxng':False,'qmd':False,'honcho':False,'kanban':False,'tailscale':False}))
    write_model(s/'data/hermes/config.yaml')
    (s/'.installer-state.json').write_text(json.dumps({'schema':1,'installerVersion':'v12','status':'failed','currentStage':'matrix_bootstrap','lastErrorStage':'matrix_bootstrap','stages':{'matrix_bootstrap':{'status':'broken'}}}))
    r=run(s)
    assert r['components']['matrix']['status']=='PARTIAL'
    assert r['resumeFrom']=='matrix_bootstrap'
    assert r['lastRunStatus']=='failed'

# Every resumable stage can be represented as the interruption/resume point. The audit must
# report the recorded in-progress/broken stage rather than inventing a later stage.
stages=['prepare_config','infrastructure','matrix_bootstrap','provider_setup','profiles','matrix_profiles','matrix_cross_signing','matrix_profile_cross_signing','integrations','reconcile','kanban_gateway','finalize']
for stage in stages:
    with tempfile.TemporaryDirectory() as td:
        s=Path(td)
        for f in ('compose.yaml','configure-stack.sh','manage.sh'):
            (s/f).write_text('x\n')
        (s/'install-options.json').write_text(json.dumps({'dashboard':False,'multiAgent':False,'workers':[],'matrix':False,'searxng':False,'qmd':False,'honcho':False,'kanban':False,'tailscale':False}))
        write_model(s/'data/hermes/config.yaml')
        (s/'.installer-state.json').write_text(json.dumps({'schema':1,'installerVersion':'v12','status':'failed','currentStage':stage,'lastErrorStage':stage,'stages':{stage:{'status':'broken'}}}))
        r=run(s)
        assert r['resumeFrom']==stage, (stage,r['resumeFrom'])



# A legacy options schema is explicitly classified OUTDATED so migration/repair is visible.
with tempfile.TemporaryDirectory() as td:
    s=Path(td)
    for f in ('compose.yaml','configure-stack.sh','manage.sh'):
        (s/f).write_text('x\n')
    (s/'install-options.json').write_text(json.dumps({'schema':5,'dashboard':False,'multiAgent':False,'workers':[],'matrix':False,'searxng':False,'qmd':False,'honcho':False,'kanban':False,'tailscale':False}))
    write_model(s/'data/hermes/config.yaml')
    r=run(s)
    assert r['components']['stack']['status']=='OUTDATED', r['components']['stack']
    assert r['overall']=='NEEDS_REPAIR'


# Exact v13.x hotfix versions are current metadata, while an options/state mismatch
# must force repair. This prevents the old literal-"v13" audit bug.
with tempfile.TemporaryDirectory() as td:
    s=Path(td)
    for f in ('compose.yaml','configure-stack.sh','manage.sh'):
        (s/f).write_text('x\n')
    opts={'schema':13,'installerVersion':'13.12.1','dashboard':False,'multiAgent':False,'workers':[],'matrix':False,'searxng':False,'qmd':False,'honcho':False,'kanban':False,'tailscale':False,'hermesApiPort':8642}
    (s/'install-options.json').write_text(json.dumps(opts))
    write_model(s/'data/hermes/config.yaml')
    (s/'secrets').mkdir(parents=True,exist_ok=True)
    (s/'secrets/hermes-runtime.env').write_text('')
    (s/'data/hermes/.env').write_text('API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\nAPI_SERVER_PORT=8642\nAPI_SERVER_KEY=0123456789abcdef0123456789abcdef\n')
    (s/'.installer-state.json').write_text(json.dumps({'schema':2,'installerVersion':'13.12.1','status':'complete','currentStage':None,'stages':{}}))
    r=run(s)
    assert r['components']['stack']['status']=='CONFIGURED', r['components']['stack']

    (s/'.installer-state.json').write_text(json.dumps({'schema':2,'installerVersion':'13.9-hotfix','status':'complete','currentStage':None,'stages':{}}))
    r=run(s)
    assert r['components']['stack']['status']=='OUTDATED', r['components']['stack']

print('STATE AUDIT FIXTURES: PASS')
print('- actual state overrides a lying complete checkpoint')
print('- interrupted Matrix stage is reported as the resume point')
print('- all twelve resumable stages preserve their recorded interruption point')
