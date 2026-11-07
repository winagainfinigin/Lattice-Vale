#!/usr/bin/env python3
"""14.6.5 preservation hotfix: deterministic source and canonical-input gates."""
from pathlib import Path
import importlib.util
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('arch', ROOT/'stack/latticevale_arch.py')
arch=importlib.util.module_from_spec(spec); spec.loader.exec_module(arch)
base={'dashboard':True,'matrix':True,'ollamaTextModel':'qwen3.5:4b','kanbanWorkerLimit':3,'profiles':[{'name':'assistant','gateway':'shared'}]}
p=arch.resource_options_projection(base)
assert p['dashboard'] is True
for key in ('mode','forceManagedUpdate','forceUpdate','skipBackup','skipAptUpdate','resume','repairOrigin','checkpointReset','windowsShortcuts','autoStart','backupChoice','universalRepairMigration'):
    altered={**base,key:True}
    assert arch.fingerprint(arch.resource_options_projection(altered))==arch.fingerprint(p),key
for key,value in [('localTextModel','qwen3.5:9b'),('dashboard',False),('matrix',False),('ollamaTextModel','qwen3.5:9b'),('kanbanWorkerLimit',4),('profiles',[{'name':'assistant','gateway':'standalone'}])]:
    changed={**base,key:value}
    assert arch.fingerprint(arch.resource_options_projection(changed))!=arch.fingerprint(p),key
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8-sig')
assert 'function Get-ObsidianInstallState' in ps
body=ps[ps.index('function Get-ObsidianInstallState'):ps.index('function Show-WindowsRecoveryAudit')]
for needle in ('CurrentVersion\\Uninstall','App Paths\\Obsidian.exe','Obsidian.exe','NOT_INSTALLED','UNKNOWN','CONFIGURED'):
    assert needle in body,needle
reconcile=ps[ps.index("if ($obsidian) {\n    Write-Step 'Installing selected Windows applications'"):]
assert "if ($appState.State -eq 'CONFIGURED')" in reconcile
assert "elseif ($appState.State -eq 'UNKNOWN')" in reconcile
assert "existingVolume.Drive.TrimEnd" in ps
for filename,kind in [('configure-stack.sh','configure'),('manage.sh','manage')]:
    source=(ROOT/'stack'/filename).read_text()
    assert 'wait_live_multiplex_gateway_'+kind+' 12' in source
    assert source.index('wait_live_multiplex_gateway_'+kind+' 12') < source.index('hermes gateway migrate --multiplex -y', source.index('wait_live_multiplex_gateway_'+kind+' 12'))
print('14.6.5 preservation hotfix fixtures passed')

# Same-version Windows follow-up: execute the shipped inline Python against
# isolated files, rather than accepting the presence of a method name as proof.
import base64, json, subprocess, tempfile
writer=ps[ps.index('function Set-InstallerWindowsState'):ps.index('function ConvertFrom-WslCliOutput')]
assert '[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))' in writer
assert "'python3' @('-c', $code" in writer
assert 'STATE_WRITE_ERROR:' in writer and 'EVENT_LOG_WARNING:' in writer
assert 'WINDOWS_STATE_WRITTEN' in writer and 'read-back confirmation' in writer
inline_code=writer.split("$code = @'\n",1)[1].split("\n'@",1)[0]
with tempfile.TemporaryDirectory() as td:
    state_path=Path(td)/'.installer-state.json'
    original={'schema':1,'installerVersion':'14.6.5','stages':{'matrix':{'status':'done'}},
        'windows':{'windowsApps':{'status':'PARTIAL'}}}
    state_path.write_text(json.dumps(original),encoding='utf-8')
    payload={'windowsApps':{'status':'CONFIGURED','detail':r'Obsidian at C:\Users\Example\Obsidian.exe'},
        'tailscale':{'status':'PASS','detail':'existing authentication retained'}}
    encoded=base64.b64encode(json.dumps(payload).encode('utf-8')).decode('ascii')
    def write():
        return subprocess.run([sys.executable,'-c',inline_code,str(state_path),encoded],text=True,capture_output=True)
    first=write()
    assert first.returncode==0,first.stderr
    assert 'WINDOWS_STATE_WRITTEN' in first.stdout
    saved=json.loads(state_path.read_text())
    assert saved['stages']==original['stages'] and saved['installerVersion']=='14.6.5'
    assert saved['windows']['windowsApps']==payload['windowsApps']
    assert saved['windows']['tailscale']==payload['tailscale']
    assert (Path(td)/'logs'/'installer-events.jsonl').is_file()
    assert not list(Path(td).glob('.installer-windows-*'))
    assert write().returncode==0   # repeated Resume is idempotent for Linux-stage identity
    assert json.loads(state_path.read_text())['stages']==original['stages']
    # Only the optional event log fails; the verified Windows state must persist.
    import shutil
    shutil.rmtree(Path(td)/'logs')
    (Path(td)/'logs').write_text('not a directory')
    second=write()
    assert second.returncode==0 and 'EVENT_LOG_WARNING:' in second.stdout
    assert json.loads(state_path.read_text())['windows']['windowsApps']==payload['windowsApps']
    # Bad existing metadata is not destroyed in an effort to clear stale hints.
    state_path.write_text('{invalid',encoding='utf-8')
    third=write()
    assert third.returncode!=0 and 'STATE_WRITE_ERROR:' in third.stderr
    assert state_path.read_text()=='{invalid'
    assert not list(Path(td).glob('.installer-windows-*'))

sh=(ROOT/'stack/configure-stack.sh').read_text()
assert 'report_unresolved_container_oom() {' in sh
assert 'if report_unresolved_container_oom; then' in sh
assert 'No running container was restarted merely to clear its OOM flag' in sh
assert sh.index('if report_unresolved_container_oom; then') < sh.index('state_finish\n')
assert "state_mark infrastructure pending 'adaptive runtime/RAM policy changed" in sh
assert 'if verify_adaptive_runtime_policy; then' in sh
assert "echo 'Adaptive runtime/RAM policy is already current.'" in sh
audit=(ROOT/'stack/state-audit.py').read_text()
assert 'event recency unknown' in audit
assert 'event timing and continuing pressure require separate runtime evidence' in audit
# Execute the exact Bash warning probe with mocked read-only docker inspection.
function=sh.split('report_unresolved_container_oom() {',1)[1].split('\n}\n',1)[0]
code='report_unresolved_container_oom() {'+function+'\n}\n'
code+='''
opt_bool() { [[ "$1" == qmd ]] && echo true || echo false; }
managed_ollama_enabled() { return 1; }
timeout() { printf '/hermes-qmd-indexer|true|%s\\n' "$MOCK_OOM"; }
report_unresolved_container_oom
'''

for value, expected in [('true',0),('false',1)]:
    result=subprocess.run(['bash','-c',code],capture_output=True,text=True,env={**__import__('os').environ,'MOCK_OOM':value})
    assert result.returncode==expected,(result.returncode,result.stderr)
    assert ('hermes-qmd-indexer records an OOM event' in result.stderr)==(expected==0)
print('14.6.5 Windows-state and OOM-observability regression fixtures passed')

# QMD CPU embedding/OOM corrective: test the canonical planner used both by the
# overlay generator and runtime-policy verifier, not a fixture-local allocator.
# 304 MiB repeatedly killed the default GGUF model on a live 12 GiB WSL host;
# the model artifact alone is about 300 MB, before runtime/context buffers.
from itertools import product
import hashlib

selected = {'matrix': True, 'searxng': True, 'qmd': True, 'honcho': True}
mem_mib = 11964
budget = arch.host_memory_budget(mem_mib, 'cpu', True, False)['containerBudgetMiB']

def plan(budget_mib, *, qmd=True, floor=5200):
    return arch.service_memory_plan(
        budget_mib, matrix=True, searxng=True, qmd=qmd, ollama=True,
        honcho=True, hermes_floor=1024, ollama_floor=floor,
    )

current = plan(budget)
assert budget < mem_mib and sum(current.values()) <= budget
assert current['qmd-indexer'] >= 1024 and current['qmd'] >= 1024, current
assert current['ollama'] >= 5200 and current['hermes'] >= 1024
assert set(current) == set(arch.SERVICE_ORDER)
assert 'qmd-indexer' not in plan(budget, qmd=False)
assert 'qmd' not in plan(budget, qmd=False)

# Across enabled combinations, neither worker nor MCP service can shrink under
# their model-aware floor; tiny budgets fail closed rather than stealing RAM.
for matrix, searxng, qmd, honcho in product((False, True), repeat=4):
    opts = dict(matrix=matrix, searxng=searxng, qmd=qmd, honcho=honcho)
    allocation = arch.service_memory_plan(16384, ollama=False,
        hermes_floor=1024, ollama_floor=0, **opts)
    assert sum(allocation.values()) <= 16384
    if qmd:
        assert allocation['qmd-indexer'] >= 1024 and allocation['qmd'] >= 1024
    else:
        assert 'qmd-indexer' not in allocation and 'qmd' not in allocation

# The minimum-capacity full-stack shape must reject one MiB less than the
# canonical sum of service minima, while conserving CPU/Ollama priorities.
low, high = 384, budget
while low < high:
    mid = (low + high) // 2
    try:
        plan(mid)
    except ValueError:
        low = mid + 1
    else:
        high = mid
threshold = low
assert threshold > 384 and sum(plan(threshold).values()) <= threshold
try:
    plan(threshold - 1)
except ValueError as exc:
    assert 'cannot safely fit selected services' in str(exc)
else:
    raise AssertionError('QMD workload floors were bypassed by the planner')
previous = None
for extra in (0, 137, 971, 2997):
    allocation = plan(threshold + extra)
    if previous:
        assert all(allocation[k] >= previous[k] for k in allocation)
    previous = allocation

# In-place same-version repair must reject the old allocation rather than
# accepting an obsolete policy only because its SHA-256 fingerprint is valid.
# The canonical validator, not a separate shell-only test, owns this decision.
compat = arch.parse_compatibility(ROOT / 'compatibility.conf')
memory = arch.host_memory_budget(mem_mib, 'cpu', True, False)
state = {
    'POLICY_VERSION': '13', 'RESOURCE_POLICY_MODE': 'adaptive',
    'MEM_MIB': str(mem_mib), 'CPUS': '8', 'OLLAMA_ACCELERATION': 'cpu',
    'MANAGED_OLLAMA_SELECTED': 'true', 'DIRECTML_SELECTED': 'false',
    'RESERVE_MIB': str(memory['reserveMiB']),
    'DIRECTML_HOST_RESERVE_MIB': str(memory['directmlHostReserveMiB']),
    'BUDGET_MIB': str(memory['containerBudgetMiB']),
    'HERMES_MIN_MIB': '1024', 'MATRIX_PROFILE_GATEWAYS': '1',
    'KANBAN_CONCURRENCY': '3', 'OLLAMA_MODEL_FLOOR_MIB': '5200',
}
for service, amount in current.items():
    state['LIMIT_' + service.upper().replace('-', '_') + '_MIB'] = str(amount)

def seal(payload):
    material = ''.join(f'{k}={v}\n' for k, v in sorted(payload.items()) if k != 'POLICY_FINGERPRINT')
    payload['POLICY_FINGERPRINT'] = hashlib.sha256(material.encode()).hexdigest()
    return payload

valid = arch.validate_runtime_policy_state(seal(state.copy()), compat, options=selected)
assert valid['services']['qmd-indexer'] >= 1024
old = state.copy()
old['LIMIT_QMD_INDEXER_MIB'] = '304'
try:
    arch.validate_runtime_policy_state(seal(old), compat, options=selected)
except ValueError as exc:
    assert 'service memory plan mismatch' in str(exc)
else:
    raise AssertionError('same-version verifier accepted undersized QMD indexer')

sh = (ROOT/'stack/configure-stack.sh').read_text()
assert 'runtime-policy.py service-plan' in sh
assert 'runtime-policy.py verify' in sh
assert 'state_mark infrastructure pending' in sh and 'state_mark reconcile pending' in sh
assert 'QMD adaptive memory ceilings:' in sh
print('14.6.5 QMD adaptive memory/repair regression fixtures passed')
