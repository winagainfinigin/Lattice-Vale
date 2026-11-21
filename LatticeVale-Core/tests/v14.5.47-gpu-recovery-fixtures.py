#!/usr/bin/env python3
"""v14.5.47 GPU-recovery regressions preserved through the 14.6 architecture."""
from pathlib import Path
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.5.47','14.6.0','14.6.1','14.6.2','14.6.3','14.6.4','14.6.5','14.6.6','14.6.7','14.6.9','14.7.0'}, version
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
# Marker format remains at 14.6.5 for compatibility with existing runtime state.
marker_format_version = '14.6.5' if version in {'14.6.6','14.6.7','14.6.9','14.7.0'} else version
assert f'VERSION={marker_format_version}' in sh

# The user-visible HTTP gateway must report the current installer release instead.
py=(ROOT/'stack/directml-gateway.py').read_text(encoding='utf-8')
for token in (f'VERSION = "{version}"','DECLARED_VRAM_MIB','DECLARED_VRAM_SOURCE','DECLARED_VRAM_CONFIDENCE','vram_source','canonical:'):
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

# A WSLg virtual vgem/faux DRM node is not a Vulkan compute device. This
# exact topology must choose CPU for managed Ollama without blocking DirectML.
import copy
with tempfile.TemporaryDirectory() as td:
    virtual_hw = copy.deepcopy(hardware)
    virtual_hw['wsl']['driRenderNodes'] = ['/dev/dri/renderD128']
    virtual_hw['wsl']['drmAdapters'] = [{
        'renderNode':'/dev/dri/renderD128', 'driver':'faux_driver',
        'pciAddress':'vgem', 'vendor':'unknown', 'vendorId':'', 'vramMiB':0,
    }]
    virtual_hw['hardwareFingerprint'] = fingerprint(virtual_hw)
    result = classify_backends(virtual_hw, options, Path(td), compat)
    assert result['selection']['textBackend'] == 'directml', result['selection']
    assert result['selection']['ollamaAcceleration'] == 'cpu', result['selection']
    assert result['capabilities']['vulkan']['reasonCode'] == 'VULKAN_GPU_DEVICE_UNVERIFIED'
    assert result['capabilities']['directml']['available'] is True
    # Real AMD/Intel/NVIDIA render devices remain eligible for the subsequent
    # actual Ollama GPU offload check (but are not pre-labelled verified).
    for vendor, driver, vid in [('amd','amdgpu','0x1002'),('intel','i915','0x8086'),('nvidia','nvidia','0x10de')]:
        real_hw = copy.deepcopy(virtual_hw)
        real_hw['wsl']['drmAdapters'][0].update(
            driver=driver, pciAddress='0000:01:00.0', vendor=vendor, vendorId=vid)
        real_hw['hardwareFingerprint'] = fingerprint(real_hw)
        selected_real = classify_backends(real_hw, options, Path(td), compat)
        assert selected_real['selection']['ollamaAcceleration'] == 'vulkan', (vendor, selected_real['selection'])
        assert selected_real['capabilities']['vulkan']['status'] == 'available-unverified'
    # A software-only Vulkan enumeration must not stand in for a GPU when
    # DRM sysfs identity is missing. A reported real Vulkan device may.
    unknown_hw = copy.deepcopy(virtual_hw)
    unknown_hw['wsl']['drmAdapters'] = []
    unknown_hw['wsl']['vulkan'] = {'toolPresent':True, 'probeSucceeded':True, 'devices':['llvmpipe (LLVM 19)']}
    unknown_hw['hardwareFingerprint'] = fingerprint(unknown_hw)
    result_sw = classify_backends(unknown_hw, options, Path(td), compat)
    assert result_sw['selection']['ollamaAcceleration'] == 'cpu'
    unknown_hw['wsl']['vulkan']['devices'] = ['AMD Radeon Graphics']
    unknown_hw['hardwareFingerprint'] = fingerprint(unknown_hw)
    result_hw = classify_backends(unknown_hw, options, Path(td), compat)
    assert result_hw['selection']['ollamaAcceleration'] == 'vulkan'

# The independent WSL-host DirectML dependency installation must precede
# optional managed-Ollama GPU verification. Gateway self-test remains last,
# after the Ollama fallback has been made ready.
infra_source = cfg[cfg.index('stage_infrastructure() {'):]
assert infra_source.index('Preparing the independently selected WSL PyTorch DirectML GPU environment') < infra_source.index('verify_or_rebudget_managed_ollama_acceleration "$current_managed_accel"')
assert infra_source.index('verify_or_rebudget_managed_ollama_acceleration "$current_managed_accel"') < infra_source.index('  repair_directml_gateway || return 1', infra_source.index('verify_or_rebudget_managed_ollama_acceleration "$current_managed_accel"'))

boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
assert "'vulkan'" in boot and '/dev/dri/renderD*' in boot
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
assert 'vulkan' in audit and 'OLLAMA_VULKAN' in audit
tool=ROOT/'tools/Audit-LatticeVale-Gpu.ps1'; assert tool.is_file()
for token in ('READ-ONLY','directml-gateway.sh diagnose','/dev/dri/renderD','/dev/dxg'):
    assert token in tool.read_text(encoding='utf-8'), token
assert (REPO/'README.md').read_text(encoding='utf-8').startswith(f'# LatticeVale v{version}')
print(f'PASS: v14.5.47 GPU recovery regressions preserved by v{version}')

# v14.7.0 GPU hotfix: probe the real shell function without touching Docker.
import os
import re
import subprocess

CORE = Path(__file__).resolve().parents[1]
src = (CORE / 'stack/configure-stack.sh').read_text(encoding='utf-8')
match = re.search(r'(?ms)^managed_ollama_processor_class\(\) \{\n.*?^\}\n', src)
assert match, 'managed_ollama_processor_class is missing'
fn = match.group(0)

with tempfile.TemporaryDirectory(prefix='lv-ollama-offload-') as temp:
    root = Path(temp)
    docker = root / 'docker'
    docker.write_text("""#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_CALLS"
if [[ "$*" == *" ollama run "* ]]; then
  [[ "$*" == *" --keepalive 60s "* ]] || exit 65
  [[ "${FAKE_RUN_STATUS:-ok}" == ok ]] || { echo 'synthetic load failure' >&2; exit 42; }
  exit 0
fi
if [[ "$*" == *" ollama ps" ]]; then
  [[ "${FAKE_PS_STATUS:-ok}" == ok ]] || exit 43
  cat "$FAKE_DOCKER_PS"
  exit 0
fi
exit 44
""", encoding='utf-8')
    docker.chmod(0o755)
    # Match Ollama's documented fixed-width columns. A processor report is
    # authoritative only for its selected row and its PROCESSOR column.
    def ps_table(rows, header=True):
        fmt = '{:<36}{:<18}{:<12}{:<22}{}\n'
        text = fmt.format('NAME', 'ID', 'SIZE', 'PROCESSOR', 'UNTIL') if header else 'MALFORMED HEADER\n'
        for model_name, processor in rows:
            text += fmt.format(model_name, 'abc', '4.0 GB', processor, '1 minute from now')
        return text

    cases = [
        # name, requested model, status of run, status of ps, loaded rows, expected, diagnostic
        ('gpu', 'qwen3.5:4b', 'ok', 'ok', [('qwen3.5:4b','100% GPU')], 'gpu', ''),
        ('mixed', 'qwen3.5:4b', 'ok', 'ok', [('qwen3.5:4b','40%/60% CPU/GPU')], 'gpu', ''),
        ('cpu', 'qwen3.5:4b', 'ok', 'ok', [('qwen3.5:4b','100% CPU')], 'cpu', ''),
        ('other', 'qwen3.5:4b', 'ok', 'ok', [('some-other:1b','100% GPU')], 'unknown', 'was absent'),
        ('no-model', 'qwen3.5:4b', 'ok', 'ok', [], 'unknown', 'was absent'),
        ('generation-error', 'qwen3.5:4b', 'failed', 'ok', [], 'unknown', 'model inference failed'),
        ('ps-error', 'qwen3.5:4b', 'ok', 'failed', [], 'unknown', "'ollama ps' failed"),
        ('gpu-in-name', 'UpperGPU:4b', 'ok', 'ok', [('UpperGPU:4b','100% CPU')], 'cpu', ''),
        ('cpu-named-but-gpu', 'UpperCPU:4b', 'ok', 'ok', [('UpperCPU:4b','100% GPU')], 'gpu', ''),
        ('literal-name-match', 'model.name:latest', 'ok', 'ok', [('modelXname:latest','100% GPU')], 'unknown', 'was absent'),
        ('exact-first-model', 'qwen3.5:4b', 'ok', 'ok', [('other:latest','100% GPU'),('qwen3.5:4b','100% CPU')], 'cpu', ''),
        ('implicit-latest', 'qwen3.5', 'ok', 'ok', [('qwen3.5:latest','100% GPU')], 'gpu', ''),
        ('other-tag-not-proof', 'qwen3.5', 'ok', 'ok', [('qwen3.5:8b','100% GPU')], 'unknown', 'was absent'),
        ('unknown-processor', 'qwen3.5:4b', 'ok', 'ok', [('qwen3.5:4b','unverified')], 'unknown', 'not report a recognizable'),
    ]
    for name, model, run_status, ps_status, rows, expected, msg in cases:
        ps_file = root / (name + '.ps')
        ps_file.write_text(ps_table(rows), encoding='utf-8')
        calls = root / (name + '.calls')
        env = dict(os.environ)
        env.update(PATH=str(root) + os.pathsep + env['PATH'],
                   FAKE_DOCKER_PS=str(ps_file), FAKE_DOCKER_CALLS=str(calls),
                   FAKE_RUN_STATUS=run_status, FAKE_PS_STATUS=ps_status)
        script = """set -o pipefail
managed_ollama_enabled() { return 0; }
unload_ollama_model() { printf 'unload:%s\n' "$1" >> "$FAKE_DOCKER_CALLS"; }
""" + fn + '\nmanaged_ollama_processor_class ' + model + '\n'
        done = subprocess.run(['bash', '-c', script], text=True, capture_output=True, env=env, timeout=25)
        assert done.returncode == 0, (name, done.stderr)
        assert done.stdout.strip() == expected, (name, done.stdout, done.stderr)
        assert msg.lower() in done.stderr.lower(), (name, done.stderr)
        history = calls.read_text(encoding='utf-8')
        assert '--keepalive 60s' in history, name
        if run_status == 'ok':
            assert history.count('ollama ps') == 1, name
        else:
            assert 'ollama ps' not in history, name
        assert f'unload:{model}' in history, name
    assert 'OLLAMA_KEEP_ALIVE' in fn and '--keepalive 60s' in fn
print('PASS: request-scoped model offload, cleanup, and exact PROCESSOR parsing (14 cases)')


# Behavioral proof: Auto tolerates a failed GPU runtime only by rebuilding a
# CPU-only Ollama instance and confirming actual CPU inference. Explicit GPU
# selections stay fail-closed; a failed CPU retry is also a hard failure.
fn_verify_match = re.search(r'(?ms)^verify_or_rebudget_managed_ollama_acceleration\(\) \{\n.*?^\}\n', src)
assert fn_verify_match
fn_verify = fn_verify_match.group(0)
for requested_accel, first_processor, retry_processor, expected_rc in (
    ('auto','unknown','cpu',0),
    ('auto','unknown','unknown',1),
    ('vulkan','unknown','cpu',1),
    ('auto','cpu','',0),
):
    script = r'''set -Eeuo pipefail
processors=("$FIRST" "$SECOND")
managed_ollama_processor_class() {
  local count=0
  [[ -f "$TEST_COUNT" ]] && count="$(cat "$TEST_COUNT")"
  printf '%s\n' "${processors[count]:-unknown}"
  printf '%s\n' "$((count+1))" > "$TEST_COUNT"
}
opt_text() { printf '%s\n' "$REQUESTED"; }
ollama_gpu_metrics() { printf '0:0:0:0'; }
mark_ollama_gpu_fallback() { printf 'MARK\n' >> "$TEST_LOG"; }
set_env() { printf 'ENV:%s=%s\n' "$2" "$3" >> "$TEST_LOG"; }
choose_ollama_context_length() { printf 4096; }
opt_bool() { printf true; }
write_latticevale_compose_overlay() { printf 'CPU_OVERLAY\n' >> "$TEST_LOG"; }
wait_managed_ollama_healthy() { return 0; }
write_resource_policy_report() { :; }
clear_ollama_gpu_fallback() { :; }
timeout() {
  while [ $# -gt 0 ]; do
    case "$1" in --foreground|--kill-after=*) shift ;; [0-9]*s) shift; break ;; *) break ;; esac
  done
  "$@"
}
docker() { printf 'DOCKER:%s\n' "$*" >> "$TEST_LOG"; }
python3() { return 0; }
''' + fn_verify + '\nverify_or_rebudget_managed_ollama_acceleration vulkan "qwen3.5:4b"\n'
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ)
        env.update(REQUESTED=requested_accel, FIRST=first_processor,
                   SECOND=retry_processor, TEST_LOG=str(Path(d)/'history'), TEST_COUNT=str(Path(d)/'count'))
        (Path(d)/'.env').write_text('OLLAMA_CONTEXT_LENGTH=16384\n',encoding='utf-8')
        run = subprocess.run(['bash','-c',script],cwd=d,text=True,capture_output=True,env=env,timeout=15)
        assert run.returncode == expected_rc, (requested_accel,first_processor,retry_processor,run.returncode,run.stderr)
        hist = (Path(d)/'history').read_text() if (Path(d)/'history').exists() else ''
        if requested_accel == 'auto':
            assert 'CPU_OVERLAY' in hist and 'DOCKER:compose up' in hist
        else:
            assert 'CPU_OVERLAY' not in hist
print('PASS: fail-closed explicit GPU and verified Auto CPU rescue (4 cases)')

# Verify shell-side GPU candidate selection agrees with canonical Python.
# Render nodes are symlinks to the host's harmless /dev/null character device
# in this fixture; no device nodes, drivers, or packages are changed.
vk_fn_match = re.search(r'(?ms)^vulkan_dri_runtime_ready\(\) \{\n.*?^\}\n', src)
assert vk_fn_match
vk_fn = vk_fn_match.group(0).replace('/dev/dri/renderD*', '"$FAKE_DRI"/renderD*').replace('/sys/class/drm/', '${FAKE_SYS}/')
for driver, expected_ok in [('faux_driver', False), ('vgem', False), ('vkms', False), ('amdgpu', True), ('i915', True)]:
    with tempfile.TemporaryDirectory(prefix='lv-vulkan-driver-') as d:
        path = Path(d)
        dri = path/'dri'; dri.mkdir()
        (dri/'renderD128').symlink_to('/dev/null')
        sysroot = path/'sys'; dev = sysroot/'renderD128'/'device'; dev.mkdir(parents=True)
        driver_path = path/'drivers'/driver; driver_path.mkdir(parents=True)
        (dev/'driver').symlink_to(driver_path)
        (dev/'vendor').write_text('0x1002\n')
        env = dict(os.environ, FAKE_DRI=str(dri), FAKE_SYS=str(sysroot))
        done = subprocess.run(['bash','-c',vk_fn+'\nvulkan_dri_runtime_ready\n'], env=env, timeout=8)
        assert (done.returncode == 0) == expected_ok, (driver,done.returncode)
print('PASS: host Vulkan render-node identity classification (5 cases)')
