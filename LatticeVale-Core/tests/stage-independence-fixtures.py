#!/usr/bin/env python3
from pathlib import Path
import re

root=Path(__file__).resolve().parents[1]
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')

def stage_start(name):
    m=re.search(rf'(?m)^{re.escape(name)}\(\) [{{(]$', cfg)
    assert m, name
    return m.start()

def stage(name, next_name=None):
    start=stage_start(name)
    end=stage_start(next_name) if next_name else len(cfg)
    return cfg[start:end]

infra=stage('stage_infrastructure','stage_matrix_bootstrap')
matrix=stage('stage_matrix_bootstrap','stage_provider_setup')
provider=stage('stage_provider_setup','stage_profiles')
assert 'hermes_image=' not in infra
assert 'hermes_image=' not in matrix
assert 'local hermes_image' in provider
assert "sed -n 's/^HERMES_IMAGE=//p' .env" in provider
assert 'HERMES_IMAGE is missing from .env' in provider
assert 'docker pull "$hermes_image"' in provider

# Guard against the regression class: variables assigned by one stage should not be
# consumed by another unless they are known top-level configuration constants. This
# is deliberately conservative and ignores common loop/heredoc names.
stage_names=re.findall(r'(?m)^(stage_[A-Za-z0-9_]+)\(\) [{{(]$', cfg)
chunks={}
for i,name in enumerate(stage_names):
    start=stage_start(name)
    end=stage_start(stage_names[i+1]) if i+1<len(stage_names) else len(cfg)
    chunks[name]=cfg[start:end]
assigned={}
all_assigned={}
refs={}
for name,body in chunks.items():
    # Local/declare assignments cannot leak across a function or `( ... )` stage and
    # are therefore intentionally excluded from the cross-stage dependency check.
    local_names=set()
    for line in body.splitlines():
        m=re.match(r'\s*(?:local|declare)(?:\s+-[A-Za-z]+)*\s+(.+)$', line)
        if not m: continue
        for token in m.group(1).split():
            candidate=token.split('=',1)[0]
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', candidate): local_names.add(candidate)
    plain_assign=set(re.findall(r'(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)=', body))
    all_assigned[name]=plain_assign | local_names
    # A `( ... )` stage executes in a subshell, so even plain assignments cannot leak.
    is_subshell=bool(re.match(rf'(?m)^{re.escape(name)}\(\) \($', body))
    assigned[name]=set() if is_subshell else (plain_assign-local_names)
    refs[name]=set(re.findall(r'\$\{?([A-Za-z_][A-Za-z0-9_]*)', body))
# Known false positives from embedded Python heredocs / generic loop variables.
global_prefix=cfg[:cfg.index('stage_prepare_config() {')]
global_assign=set(re.findall(r'(?m)^([A-Za-z_][A-Za-z0-9_]*)=', global_prefix))
ignore={'f','name','peer','profiles','worker','current_name','requested_workers','p'} | global_assign
violations=[]
for origin,names in assigned.items():
    for var in names-ignore:
        # Referencing a same-named variable after assigning it inside the consumer
        # is independent state, not a dependency on the origin stage.
        consumers=[n for n,r in refs.items() if n!=origin and var in r and var not in all_assigned[n]]
        if consumers:
            violations.append((var,origin,consumers))
assert not violations, violations

print('STAGE INDEPENDENCE: PASS')
