from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
conf = (ROOT / 'stack' / 'configure-stack.sh').read_text(encoding='utf-8')
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}
# Host GPU model must never be treated as proof of WSL/container readiness.
assert 'function Get-OllamaWslGpuPrerequisites' in ps
assert '[[ -e /dev/kfd ]] && kfd=1' in ps
assert '[[ -d /dev/dri ]] && dri=1' in ps
assert '[[ -e /dev/dxg ]] && dxg=1' in ps
assert 'nvidia-smi -L' in ps
assert '$state.AmdDockerReady = ($state.Arch -eq \'x86_64\' -and $state.KfdPresent -and $state.DriPresent)' in ps
assert '$state.NvidiaWslReady = ($state.DxgPresent -and $state.NvidiaSmiReady)' in ps
assert 'LatticeVale does not infer AMD container support from the Windows GPU.' in ps
# Resume/repair with a now-invalid forced GPU mode must reconcile before bootstrap.
assert "The saved forced Ollama acceleration policy '$ollamaAcceleration' is not currently usable" in ps
assert 'Choose how this repair run should handle the unavailable saved Ollama GPU mode' in ps
assert 'Use WSL/Docker Ollama with Auto acceleration' in ps
assert 'Use WSL/Docker Ollama with CPU only' in ps
assert 'Stop this installer run and leave the saved acceleration choice unchanged' in ps
assert "$ollamaAcceleration = 'auto'" in ps
assert "$ollamaAcceleration = 'cpu'" in ps
# Fresh/reconfigure questionnaire must label and reject unavailable forced GPU selections.
assert 'AMD GPU via ROCm [currently unavailable for this Ollama Docker path' in ps
assert 'NVIDIA GPU [currently unavailable in selected distro' in ps
assert 'AMD/ROCm mode was not accepted because the selected Ubuntu distro does not currently expose the devices required by this Ollama Docker path.' in ps
assert 'NVIDIA mode was not accepted because the selected Ubuntu distro did not pass the WSL NVIDIA prerequisite probe.' in ps
# Defense in depth remains: if devices disappear after the Windows-side probe, Linux forced mode still fails closed.
assert "[[ -c /dev/kfd && -d /dev/dri ]] ||" in conf
assert 'Ollama AMD/ROCm acceleration was explicitly selected' in conf
print('v14.3.5 GPU prerequisite/repair fixtures: PASS')
