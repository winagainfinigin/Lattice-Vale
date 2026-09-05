#!/usr/bin/env python3
"""v14.5.47 GPU-recovery regressions preserved through the 14.6 architecture."""
from pathlib import Path
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.5.47','14.6.0'}, version
sys.path.insert(0,str(ROOT/'stack'))
from latticevale_arch import (  # noqa:E402
    classify_backends, fingerprint, host_memory_budget, parse_compatibility, validate_install_options
)
compat=parse_compatibility(ROOT/'compatibility.conf')
assert int(compat['INSTALL_OPTIONS_SCHEMA']) >= 21
assert int(compat['MANAGED_REPAIR_REFRESH_REVISION']) >= 3

ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
for token in ('MESA_D3D12_DEFAULT_ADAPTER_NAME','directmlVramMiB','Get-LatticeValeDxDiagGpuMemoryMap',
              'WindowsBuildSupported',"'vulkan'",'VulkanDockerReady','/dev/dri/renderD*',
              'Get-LatticeValeGpuStableId','gpuPreferenceId','gpuPreferencePnpDeviceId',
              'HardwareInformation.qwMemorySize','MatchingDeviceId','SharedMemoryMiB',
              'MemoryConfidence','Get-LatticeValeWindowsHardwareSnapshot','windows-hardware.json',
              '--windows-snapshot','latticevale_arch.py'):
    assert token in ps, token

sh=(ROOT/'stack/directml-gateway.sh').read_text(encoding='utf-8')
for token in ('MESA_D3D12_DEFAULT_ADAPTER_NAME','directml_runtime_fingerprint','reconcile_force_fallback',
              'LATTICEVALE_DIRECTML_VRAM_MIB','diagnose)'):
    assert token in sh, token
assert 'VERSION=14.6.0' in sh

py=(ROOT/'stack/directml-gateway.py').read_text(encoding='utf-8')
for token in ('VERSION = "14.6.0"','DECLARED_VRAM_MIB','DECLARED_VRAM_SOURCE','DECLARED_VRAM_CONFIDENCE','vram_source','canonical:'):
    assert token in py, token

cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
for token in ('vulkan)','OLLAMA_VULKAN','/dev/dri:/dev/dri','vulkan_dri_runtime_ready','ollama ps'):
    assert token in cfg, token
# The schema crash fixed in 14.5.47 cannot recur: schema ownership is canonical and
# current consumers accept corrected schema-21 migration state while rejecting future state.
assert 'latticevale_arch.py validate-options install-options.json --compat compatibility.conf' in cfg
assert 'PY_OPTIONS_VALIDATE' not in cfg
current=int(compat['INSTALL_OPTIONS_SCHEMA'])
validate_install_options({'schema':21,'repairOriginSchema':21,'workers':[]}, current)
try:
    validate_install_options({'schema':current+1,'workers':[]}, current)
except ValueError as exc:
    assert 'newer than supported' in str(exc)
else:
    raise AssertionError('future install-options schema did not fail closed')

# The resource-policy repair crash is protected adaptively: generation and validation
# call one canonical host budget and no specific machine topology is encoded.
assert 'runtime-policy.py host-budget' in cfg
assert cfg.count('resource_host_memory_budget "$mem_mib"') >= 2
assert 'directml_reserve=1792' not in cfg
prev=-1
for accel in ('cpu','vulkan','nvidia','amd'):
  for managed in (False,True):
    for directml in (False,True):
      prev=-1
      for mem in (2071,3331,5197,7817,11027,15733,24407,39191,68113):
        b=host_memory_budget(mem,accel,managed,directml)
        assert b['reserveMiB']+b['containerBudgetMiB']==mem
        assert b['containerBudgetMiB']>=384 and b['containerBudgetMiB']>=prev
        if directml: assert 0 < b['directmlHostReserveMiB'] <= b['reserveMiB']
        else: assert b['directmlHostReserveMiB']==0
        prev=b['containerBudgetMiB']

# DirectML remains independent from Linux-native GPU enumeration.  A qualified Windows
# GPU + /dev/dxg may select DirectML even with no DRM/KFD/CUDA adapter in WSL.
bridge={k:{'present':True} for k in ('libd3d12.so','libd3d12core.so','libdxcore.so')}
hardware={'schema':1,'windows':{'build':26200,'gpus':[{'id':'gpu-test','name':'AMD Example','vendor':'amd','vramMiB':8193}]},'wsl':{
    'architecture':'x86_64','dxg':{'present':True},'directxBridgeLibraries':bridge,'driRenderNodes':[],
    'drmAdapters':[],'kfd':{'present':False},'nvidiaSmi':{'available':False,'gpus':[]},
    'vulkan':{'toolPresent':False,'probeSucceeded':False,'devices':[]}}}
hardware['hardwareFingerprint']=fingerprint(hardware)
options={'schema':current,'localTextBackend':'directml','directmlTextModel':'Qwen/Qwen2.5-1.5B-Instruct',
         'ollamaBackend':'managed','ollamaAcceleration':'auto','gpuPreferenceMode':'explicit','gpuPreferenceId':'gpu-test',
         'gpuPreferenceName':'AMD Example','gpuPreferenceVendor':'amd','inferenceBackendPreference':'directml','workers':[]}
with tempfile.TemporaryDirectory() as td:
    selected=classify_backends(hardware,options,Path(td),compat)
assert selected['selection']['inferenceBackend']=='directml'
assert selected['adapterSelection']['selected']['id']=='gpu-test'

boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
assert "'vulkan'" in boot and '/dev/dri/renderD*' in boot
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
assert 'vulkan' in audit and 'OLLAMA_VULKAN' in audit
tool=ROOT/'tools/Audit-LatticeVale-Gpu.ps1'; assert tool.is_file()
for token in ('READ-ONLY','directml-gateway.sh diagnose','/dev/dri/renderD','/dev/dxg'):
    assert token in tool.read_text(encoding='utf-8'), token
assert (REPO/'README.md').read_text(encoding='utf-8').startswith('# LatticeVale v14.6.0')
print('PASS: v14.5.47 GPU recovery regressions preserved by v14.6.0')
