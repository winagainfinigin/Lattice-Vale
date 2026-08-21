from pathlib import Path
import json
import os
import re
import sys
import tempfile
import yaml

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}, version
configure=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')

# Repair/update adoption: the integrations revision advances whenever an installer-owned
# integration needs migration without touching unrelated checkpoints.
assert ("integrations) printf '3'" in configure) if version == '14.4.7' else ("integrations) printf '2'" in configure)

# Routing is discovered, not machine/profile-name hard-coded. Valid user-created
# profiles remain valid routing targets, while fallback automatic assignment only
# opts into LatticeVale-managed profiles.
assert "all_profiles=sorted(child.name for child in profiles_dir.iterdir()" in configure
assert "candidates=[n for n in names if n in known and n != canonical_orchestrator]" in configure
assert "'assistant' if 'assistant' in known" not in configure
assert "kanban['review_dispatch']=canonical_review" in configure

# Skill authoring/recovery policy.
assert 'HERMES_SKILL_MANAGEMENT_POLICY_START' in configure
assert "skills_cfg.setdefault('write_approval',False)" in configure
assert 'Never repeat an identical failing `skill_manage` request' in configure
assert 'read the complete requested input before authoring' in configure
assert 'If Hermes says the current SKILL.md was not loaded, call `skill_view`' in configure
assert "guard['warnings_enabled']=True" in configure
assert "warn.setdefault('same_tool_failure',3)" in configure
assert "hard.setdefault('same_tool_failure',8)" in configure

# Kanban task-context policy and current Hermes shallow argument-rewrite support.
assert 'version: "1.2.0"' in configure
assert '"action": "modify"' in configure
assert '_guard_kanban_tool' in configure
assert '_modify' in configure
assert 'HERMES_KANBAN_TASK' in configure
assert 'Scratch workspaces may be removed after completion' in configure
assert 'substantive task results/artifacts' in configure

# Exercise the stage-integrations config rewrite in an arbitrary profile topology.
# A user-owned profile can remain orchestrator; LatticeVale does not edit it or
# conscript it as automatic assignee fallback.
stage_start=configure.index('stage_integrations() {')
py_start=configure.index("python3 - install-options.json data/hermes .installer-managed-profiles <<'PY'", stage_start)
py_start=configure.index('\n', py_start)+1
py_end=configure.index('\nPY\n', py_start)
stage_code=configure[py_start:py_end]

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    root=td/'hermes'
    (root/'profiles'/'worker-blue').mkdir(parents=True)
    (root/'profiles'/'external-red').mkdir(parents=True)
    root_cfg={
        'model': {'default':'example/root'},
        'toolsets':['hermes-cli'],
        'kanban': {
            'orchestrator_profile':'external-red',
            'default_assignee':'worker-blue',
            'review_dispatch':False,
        },
        'skills': {'write_approval': True},
    }
    worker_cfg={'model':{'default':'example/worker'},'toolsets':['hermes-cli']}
    external_cfg={'model':{'default':'example/external'},'custom':{'owned_by':'user'}}
    (root/'config.yaml').write_text(yaml.safe_dump(root_cfg,sort_keys=False),encoding='utf-8')
    (root/'profiles'/'worker-blue'/'config.yaml').write_text(yaml.safe_dump(worker_cfg,sort_keys=False),encoding='utf-8')
    ext_path=root/'profiles'/'external-red'/'config.yaml'
    ext_path.write_text(yaml.safe_dump(external_cfg,sort_keys=False),encoding='utf-8')
    external_before=ext_path.read_text(encoding='utf-8')
    managed=td/'managed.txt'; managed.write_text('worker-blue\n',encoding='utf-8')
    opts=td/'opts.json'; opts.write_text(json.dumps({
        'kanban':True,'dashboard':False,'searxng':False,'qmd':False,'honcho':False,
        'kanbanMaxInProgress':3,'kanbanMaxInProgressPerProfile':2,
    }),encoding='utf-8')
    old_argv=sys.argv
    try:
        sys.argv=['stage-integrations',str(opts),str(root),str(managed)]
        exec(compile(stage_code,'<stage-integrations-config>','exec'),{})
    finally:
        sys.argv=old_argv
    new_root=yaml.safe_load((root/'config.yaml').read_text(encoding='utf-8'))
    new_worker=yaml.safe_load((root/'profiles'/'worker-blue'/'config.yaml').read_text(encoding='utf-8'))
    assert new_root['kanban']['orchestrator_profile']=='external-red'
    assert new_worker['kanban']['orchestrator_profile']=='external-red'
    assert new_root['kanban']['default_assignee']=='worker-blue'
    assert new_worker['kanban']['default_assignee']=='worker-blue'
    assert new_root['kanban']['review_dispatch'] is False
    assert new_worker['kanban']['review_dispatch'] is False
    assert new_root['skills']['write_approval'] is True, 'explicit approval gate must survive repair/update'
    assert new_worker['skills']['write_approval'] is False, 'fresh managed profile gets Hermes automatic-write default'
    assert ext_path.read_text(encoding='utf-8') == external_before, 'user-owned profile must not be rewritten'

# Execute the generated plugin source itself with arbitrary profile names.
m=re.search(r"code='''(.*?)'''\nfor home in homes:", configure, re.S)
assert m, 'generated Kanban plugin source not found'
code=m.group(1)
ns={}
exec(compile(code,'<latticevale-kanban-policy>','exec'),ns)

def check_block(result, needle):
    assert isinstance(result,dict) and result.get('action')=='block', result
    assert needle.lower() in result.get('message','').lower(), result

def check_modify(result, expected):
    assert isinstance(result,dict) and result.get('action')=='modify', result
    assert result.get('args') == expected, result

with tempfile.TemporaryDirectory() as td:
    home=Path(td)/'hermes-home'
    (home/'profiles'/'worker-blue').mkdir(parents=True)
    (home/'profiles'/'review-green').mkdir(parents=True)
    (home/'profiles'/'worker-blue'/'config.yaml').write_text('model: {}\n')
    (home/'profiles'/'review-green'/'config.yaml').write_text('model: {}\n')
    (home/'config.yaml').write_text(yaml.safe_dump({'kanban':{'orchestrator_profile':'review-green'}}))
    old_home=os.environ.get('HERMES_HOME'); old_task=os.environ.get('HERMES_KANBAN_TASK')
    os.environ['HERMES_HOME']=str(home)
    os.environ.pop('HERMES_KANBAN_TASK',None)
    try:
        guard=ns['_guard_kanban_tool']
        # Normal/orchestrator root work is repaired to triage rather than needlessly failed.
        check_modify(guard('kanban_create',{'title':'x','assignee':'worker-blue','triage':False}), {'triage':True})
        assert guard('kanban_create',{'title':'x','assignee':'worker-blue','triage':True}) is None
        check_block(guard('kanban_create',{'title':'x','assignee':'invented-role','triage':True}), 'installed profiles')
        check_block(guard('kanban_create',{'title':'x','triage':True}), 'configured orchestrator')
        check_block(guard('kanban_show',{}), 'no bound worker task')
        check_block(guard('kanban_complete',{'summary':'done'}), 'claimed-worker')
        check_block(guard('kanban_comment',{'task_id':'$HERMES_KANBAN_TASK','body':'x'}), 'no bound worker task')
        assert guard('kanban_comment',{'task_id':'t_real','body':'x'}) is None

        # Dispatcher worker context: placeholder text is deterministically replaced with
        # the real binding, same-task lifecycle calls are allowed, cross-task completion
        # is blocked, and worker-created child cards are not forced back through triage.
        os.environ['HERMES_KANBAN_TASK']='t_bound'
        check_modify(guard('kanban_show',{'task_id':'$HERMES_KANBAN_TASK'}), {'task_id':'t_bound'})
        assert guard('kanban_show',{}) is None
        assert guard('kanban_complete',{'summary':'done'}) is None
        check_block(guard('kanban_complete',{'task_id':'t_other','summary':'done'}), 'different task id')
        assert guard('kanban_create',{'title':'child','assignee':'worker-blue','triage':False}) is None
    finally:
        if old_home is None: os.environ.pop('HERMES_HOME',None)
        else: os.environ['HERMES_HOME']=old_home
        if old_task is None: os.environ.pop('HERMES_KANBAN_TASK',None)
        else: os.environ['HERMES_KANBAN_TASK']=old_task

print('v14.3.38 Kanban/skill policy fixtures: PASS')
