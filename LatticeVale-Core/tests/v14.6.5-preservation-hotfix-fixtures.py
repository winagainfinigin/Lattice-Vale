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
