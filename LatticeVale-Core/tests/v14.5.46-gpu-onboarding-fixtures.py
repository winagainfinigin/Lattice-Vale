from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version == '14.5.46', version
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
boot = (ROOT / 'linux' / 'bootstrap.sh').read_text(encoding='utf-8')

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

print('v14.5.46 GPU ONBOARDING / RECOMMENDATION FIXTURES: PASS')
print('- GPU-vendor + WSL capability plan recommends NVIDIA, ROCm, DirectML, or CPU safely')
print('- questionnaire labels the detected-hardware recommendation without removing explicit choice')
print('- DirectML/NVIDIA prerequisites are reused or provisioned idempotently')
print('- AMD ROCm requires real WSL device exposure; host display drivers remain user/vendor-owned')
