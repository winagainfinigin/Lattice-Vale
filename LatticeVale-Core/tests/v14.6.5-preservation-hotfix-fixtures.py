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
