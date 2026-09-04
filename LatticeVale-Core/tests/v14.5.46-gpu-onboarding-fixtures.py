from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version == '14.5.46', version
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
boot = (ROOT / 'linux' / 'bootstrap.sh').read_text(encoding='utf-8')
cfg = (ROOT / 'stack' / 'configure-stack.sh').read_text(encoding='utf-8')
dml_sh = (ROOT / 'stack' / 'directml-gateway.sh').read_text(encoding='utf-8')
dml_py = (ROOT / 'stack' / 'directml-gateway.py').read_text(encoding='utf-8')

# Hardware-aware recommendation is distinct from the authoritative runtime probes.
for token in (
    'function Get-LatticeValeWslGpuComponentInventory',
    'function Get-LatticeValeGpuAccelerationPlan',
    'function Write-LatticeValeGpuAccelerationPlan',
    'RecommendedTextBackend',
    'RecommendedOllamaAcceleration',
    'GPU-aware recommendation:',
    '[recommended for detected hardware]',
):
    assert token in ps, token

plan = ps[ps.index('function Get-LatticeValeGpuAccelerationPlan'):ps.index('function Write-LatticeValeGpuAccelerationPlan')]
assert plan.index("$ollama.NvidiaWslReady") < plan.index("$ollama.AmdDockerReady") < plan.index("$directml.BridgeLibrariesReady")
assert "Managed Ollama NVIDIA acceleration is the preferred stable path" in plan
assert "Managed Ollama ROCm is the preferred verified container path" in plan
assert "DirectML is recommended" in plan
assert "the managed ROCm container path is not fully verified" in plan
assert "No verified GPU acceleration path" in plan

# The recommendation must not turn a Windows vendor string into GPU admission.
assert 'Get-OllamaWslGpuPrerequisites $Name $User' in plan
assert 'Get-DirectMLWslPrerequisites $Name $User' in plan
assert "-and $ollama.NvidiaWslReady" in plan
assert "-and $ollama.AmdDockerReady" in plan
assert "-and $directml.DxgPresent -and $directml.BridgeLibrariesReady" in plan

# Questionnaire reports reuse/install intent and preserves explicit choice.
assert 'WSL acceleration components:' in ps
assert 'LatticeVale will install them if DirectML is selected' in ps
assert 'LatticeVale will install/configure it only if NVIDIA managed Ollama is selected' in ps
assert "Read-Menu 'Local text inference backend'" in ps
assert "Read-Menu 'Ollama hardware acceleration'" in ps

# Installer-owned WSL prerequisites are idempotently acquired only for the selected path.
assert "Installing missing DirectML WSL prerequisites:" in boot
assert "DirectML WSL prerequisite packages are already installed; reusing them." in boot
assert "NVIDIA Container Toolkit and Docker GPU runtime are already verified; reusing them." in boot
assert 'install_nvidia_container_toolkit_if_needed' in boot
assert "AMD/ROCm managed Ollama selected. Reusing the WSL-provided /dev/kfd + /dev/dri" in boot

# Host/vendor driver ownership remains explicit; LatticeVale must not install a Linux display driver.
assert 'No Linux NVIDIA display driver was installed.' in boot
assert 'does not install or replace the Windows/host display driver' in boot

# Same-version Resume / repair may skip prepare_config; helpers used by later stages
# must therefore be defined globally before the first stage function.
assert cfg.index('apply_honcho_timeout_policy() {') < cfg.index('stage_prepare_config() {')
assert cfg.index('apply_honcho_timeout_policy data/hermes/honcho.json') > cfg.index('stage_integrations() {')

# DirectML adds a WSL-host workload that did not exist in the stable v14.5.2 topology.
assert 'managed_ollama_enabled && ! directml_text_enabled' in cfg
assert 'directml_reserve_mib=$((mem_mib/4))' in cfg
assert 'directml_reserve_mib=2048' in cfg and 'directml_reserve_mib=4096' in cfg

# Compact WSL CPU allocations leave CPU for Docker/WSL housekeeping; repeated hard
# DirectML starts switch to lightweight fallback rather than hot-looping torch imports.
assert 'directml_cpu_threads() {' in dml_sh
assert 'OMP_NUM_THREADS="$cpu_threads"' in dml_sh and 'MKL_NUM_THREADS="$cpu_threads"' in dml_sh
assert 'worker failed twice before reaching health' in dml_sh
assert 'restart deferred ${delay}s' in dml_sh
assert 'LATTICEVALE_DIRECTML_HOST_RESERVE_MIB' in dml_sh
assert dml_py.index('if FORCE_FALLBACK:') < dml_py.index('import torch\n')
assert '_host_mem_available_mib' in dml_py and 'DirectML host-RAM admission refused' in dml_py
assert 'torch.set_num_threads(CPU_THREADS)' in dml_py

# Current WSL distinguishes distro-instance idleness from VM idleness. Persistent
# server lifetime must disable both timers, while repair still applies the policy only
# after Linux stages complete successfully.
assert 'function Set-WslGlobalIdleTimeoutsDisabled' in ps
assert 'instanceIdleTimeout=-1' in ps and 'vmIdleTimeout=-1' in ps
assert ps.index("if ($applyWslLifetimePolicy) {") > ps.index("Invoke-LatticeValeWslInteractiveGuarded $DistroName")

print('v14.5.46 GPU ONBOARDING / RECOMMENDATION FIXTURES: PASS')
print('- GPU-vendor + WSL capability plan recommends NVIDIA, ROCm, DirectML, or CPU safely')
print('- questionnaire labels the detected-hardware recommendation without removing explicit choice')
print('- DirectML/NVIDIA prerequisites are reused or provisioned idempotently')
print('- AMD ROCm requires real WSL device exposure; host display drivers remain user/vendor-owned')
