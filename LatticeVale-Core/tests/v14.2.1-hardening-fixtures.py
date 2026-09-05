#!/usr/bin/env python3
from pathlib import Path
import re, subprocess, tempfile
import yaml
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
conf=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
compose=(ROOT/'stack/compose.yaml').read_text(encoding='utf-8')
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
root=ROOT.parent
install=(root/'installer/install.ps1').read_text(encoding='utf-8')
verify=(root/'installer/verify-release.ps1').read_text(encoding='utf-8')
shared=(root/'tools/ReleaseManifest.ps1').read_text(encoding='utf-8')
generator=(root/'tools/New-SourceManifest.ps1').read_text(encoding='utf-8')
assert (ROOT/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}
assert 'schema = $compat.InstallOptionsSchema' in ps
assert "ollamaAcceleration = $ollamaAcceleration" in ps
assert "$options.Remove('ollamaAcceleration')" in ps and 'Legacy same-line repair: preserving the existing Ollama image/runtime choice' in ps
assert "containerResourceLimits = $containerResourceLimits" in ps
assert "@('auto','cpu','nvidia','amd')" in ps
assert 'install_nvidia_container_toolkit_if_needed' in boot
assert 'https://nvidia.github.io/libnvidia-container/gpgkey' in boot
assert 'unexpected package origin' in boot and 'nvidia\\.github\\.io/libnvidia-container/' in boot
assert 'nvidia-ctk runtime configure --runtime=docker' in boot
assert "nvidia_toolkit_version='1.20.0-1'" in boot
for pkg in ('nvidia-container-toolkit','nvidia-container-toolkit-base','libnvidia-container-tools','libnvidia-container1'):
    assert f'\"{pkg}=${{nvidia_toolkit_version}}\"' in boot
assert '--allow-downgrades' not in boot
assert 'dpkg --compare-versions' in boot
assert 'preserving it and verifying the runtime instead of downgrading' in boot
assert 'will not downgrade the newer packages automatically' in boot
assert 'cuda-drivers' not in boot and 'apt-get install -y cuda' not in boot
assert '/dev/kfd' in conf and '/dev/dri' in conf
assert 'group_add:' in conf and "stat -c '%g'" in conf
assert 'driver: nvidia' in conf and 'capabilities: [gpu]' in conf
assert 'compose.latticevale.yaml' in conf and 'compose.override.yaml' in conf
assert "grep -q '^SEARXNG_IMAGE=' .env || set_env" in conf
assert 'ollama_accel_managed=false' in conf and "has(\"ollamaAcceleration\")" in conf
assert 'LATTICEVALE_OLLAMA_IMAGE_AUTO' in conf and 'Preserving user-set OLLAMA_IMAGE=' in conf
assert 'custom Ollama image override preserved' in audit
assert 'GPU execution verified at runtime by ollama ps' in audit
assert 'parsed_bootstrap_options=' in boot and 'PY_BOOTSTRAP_OPTIONS' in boot
assert not any('grep -Eq' in line and 'honcho|hermesLocalAI' in line for line in boot.splitlines())
assert 'containerResourceLimits' in conf
assert 'runtimePolicy' in audit and 'compose.latticevale.yaml' in audit and 'LATTICEVALE_OLLAMA_ACCELERATION' in audit
assert 'searxng/searxng:latest' not in conf+compose
assert 'ollama/ollama:latest' not in conf+compose
assert 'searxng/searxng:2026.8.17-374939b88' in conf+compose
assert 'ollama/ollama:0.32.14' in conf+compose
assert 'ollama/ollama:0.32.14-rocm' in conf
assert '. $Verifier' in install and '. $Verifier' in verify
assert 'function Test-LatticeValeSourceManifest' in shared
assert 'function Assert-PortableReleaseRelativePath' not in install
assert 'function Assert-PortableReleaseRelativePath' not in verify
assert 'ReleaseManifest.ps1' in generator and 'Assert-LatticeValePortableReleaseRelativePath' in generator
assert 'function Assert-PortableReleaseRelativePath' not in generator
# Execute the generated resource-overlay function without Docker. This catches shell/YAML
# generation regressions that static string checks cannot.
start=conf.index('resource_gpu_coordination() {')
end=conf.index('\nchoose_ollama_context_length()', start)
functions=conf[start:end].replace('/proc/meminfo', 'fake-meminfo')
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    harness=r'''set -Eeuo pipefail
set_env() {
  local file="$1" key="$2" value="$3"
  python3 - "$file" "$key" "$value" <<'PY_ENV'
from pathlib import Path
import sys
p=Path(sys.argv[1]); k=sys.argv[2]; v=sys.argv[3]
lines=p.read_text().splitlines() if p.exists() else []
out=[]; done=False
for line in lines:
    if line.startswith(k+'='):
        if not done: out.append(k+'='+v); done=True
    else: out.append(line)
if not done: out.append(k+'='+v)
p.write_text('\n'.join(out)+'\n')
PY_ENV
}
opt_bool() { jq -r ".${1} // false" install-options.json; }
opt_text() { jq -r ".${1} // empty" install-options.json; }
local_ai_enabled() { [[ "$(opt_bool honcho)" == true || "$(opt_bool hermesLocalAI)" == true ]]; }
ollama_backend() { local value; value="$(opt_text ollamaBackend)"; [[ "$value" == managed || "$value" == windows-native ]] || value=managed; printf '%s' "$value"; }
managed_ollama_enabled() { local_ai_enabled && [[ "$(ollama_backend)" == managed ]]; }
ollama_gpu_metrics() { printf '1:8192:8192:8192\n'; }
''' + functions + r'''
cat > install-options.json <<'JSON_OPTIONS'
{"matrix":true,"searxng":true,"qmd":true,"honcho":true,"hermesLocalAI":true,"ollamaBackend":"managed"}
JSON_OPTIONS
printf 'MemTotal: 16777216 kB\n' > fake-meminfo
write_latticevale_compose_overlay cpu true
'''
    r=subprocess.run(['bash','-c',harness],cwd=td,text=True,capture_output=True,timeout=20)
    assert r.returncode==0, r.stderr
    overlay=(td/'compose.latticevale.yaml').read_text()
    env=(td/'.env').read_text()
    assert 'cpus:' in overlay and 'mem_limit:' in overlay
    assert 'COMPOSE_FILE=compose.yaml:compose.latticevale.yaml' in env
    mem_visible=16384
    limits=[int(x) for x in re.findall(r'mem_limit: "?(\d+)m"?', overlay)]
    assert limits and max(limits) <= mem_visible, (max(limits), mem_visible)
    parsed=yaml.safe_load(overlay)
    assert len(parsed['services'])==12

# Execute the two GPU overlay variants too. Acceleration prerequisite detection is
# tested separately; this verifies that the YAML emitted after a successful detection
# is structurally valid and maps the expected devices/reservation into Ollama.
for accel in ('nvidia','amd'):
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        harness=r'''set -Eeuo pipefail
set_env() {
  local file="$1" key="$2" value="$3"
  python3 - "$file" "$key" "$value" <<'PY_ENV'
from pathlib import Path
import sys
p=Path(sys.argv[1]); k=sys.argv[2]; v=sys.argv[3]
lines=p.read_text().splitlines() if p.exists() else []
out=[]; done=False
for line in lines:
    if line.startswith(k+'='):
        if not done: out.append(k+'='+v); done=True
    else: out.append(line)
if not done: out.append(k+'='+v)
p.write_text('\n'.join(out)+'\n')
PY_ENV
}
opt_bool() { jq -r ".${1} // false" install-options.json; }
opt_text() { jq -r ".${1} // empty" install-options.json; }
local_ai_enabled() { [[ "$(opt_bool honcho)" == true || "$(opt_bool hermesLocalAI)" == true ]]; }
ollama_backend() { local value; value="$(opt_text ollamaBackend)"; [[ "$value" == managed || "$value" == windows-native ]] || value=managed; printf '%s' "$value"; }
managed_ollama_enabled() { local_ai_enabled && [[ "$(ollama_backend)" == managed ]]; }
ollama_gpu_metrics() { printf '1:8192:8192:8192\n'; }
''' + functions + r'''
cat > install-options.json <<'JSON_OPTIONS'
{"hermesLocalAI":true,"ollamaBackend":"managed"}
JSON_OPTIONS
''' + f"printf 'MemTotal: 16777216 kB\\n' > fake-meminfo\nwrite_latticevale_compose_overlay {accel} false\n"
        r=subprocess.run(['bash','-c',harness],cwd=td,text=True,capture_output=True,timeout=20)
        assert r.returncode==0, (accel,r.stderr)
        parsed=yaml.safe_load((td/'compose.latticevale.yaml').read_text())
        ollama=parsed['services']['ollama']
        if accel=='nvidia':
            device=ollama['deploy']['resources']['reservations']['devices'][0]
            assert device['driver']=='nvidia' and device['count']=='all' and 'gpu' in device['capabilities']
        else:
            assert '/dev/kfd:/dev/kfd' in ollama['devices'] and '/dev/dri:/dev/dri' in ollama['devices']


# Image ownership marker semantics: the installer owns its recorded default, but a
# deliberate .env override must survive a same-policy repair. Static assertions pin
# the branch conditions so future refactors cannot silently revert to unconditional set_env.
assert 'current_ollama_image == previous_auto_ollama_image' not in conf  # shell syntax is quoted operands
assert '"$current_ollama_image" == "$previous_auto_ollama_image"' in conf
assert '"$previous_resolved_acceleration" != "$OLLAMA_RESOLVED_ACCELERATION"' in conf
assert 'set_env .env LATTICEVALE_OLLAMA_IMAGE_AUTO "$desired_ollama_image"' in conf

# Execute the image-ownership branch itself. A deliberate custom image must survive a
# same-policy repair, while a policy change from CPU to AMD may switch an installer-owned
# default to the tested ROCm image.
image_start=conf.index('ollama_accel_managed=false')
image_end=conf.index('\noverlay_acceleration=', image_start)
image_logic=conf[image_start:image_end]
set_env_helper=r'''set_env() {
  local file="$1" key="$2" value="$3"
  python3 - "$file" "$key" "$value" <<'PY_ENV'
from pathlib import Path
import sys
p=Path(sys.argv[1]); k=sys.argv[2]; v=sys.argv[3]
lines=p.read_text().splitlines() if p.exists() else []
out=[]; done=False
for line in lines:
    if line.startswith(k+'='):
        if not done: out.append(k+'='+v); done=True
    else: out.append(line)
if not done: out.append(k+'='+v)
p.write_text('\n'.join(out)+'\n')
PY_ENV
}
'''
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    (td/'install-options.json').write_text('{"ollamaAcceleration":"cpu"}\n')
    (td/'.env').write_text(
        'OLLAMA_IMAGE=example/ollama:custom\n'
        'LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:0.32.14\n'
        'LATTICEVALE_OLLAMA_ACCELERATION=cpu\n'
    )
    harness='set -Eeuo pipefail\n'+set_env_helper+'\nollama_backend(){ printf managed; }\nOLLAMA_RESOLVED_ACCELERATION=cpu\nenv_was_new=false\n'+image_logic+'\n'
    r=subprocess.run(['bash','-c',harness],cwd=td,text=True,capture_output=True,timeout=20)
    assert r.returncode==0, r.stderr
    env=(td/'.env').read_text()
    assert 'OLLAMA_IMAGE=example/ollama:custom\n' in env
    assert 'LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:0.32.14\n' in env
    assert 'Preserving user-set OLLAMA_IMAGE=example/ollama:custom' in r.stdout

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    (td/'install-options.json').write_text('{"ollamaAcceleration":"amd"}\n')
    (td/'.env').write_text(
        'OLLAMA_IMAGE=ollama/ollama:0.32.14\n'
        'LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:0.32.14\n'
        'LATTICEVALE_OLLAMA_ACCELERATION=cpu\n'
    )
    harness='set -Eeuo pipefail\n'+set_env_helper+'\nollama_backend(){ printf managed; }\nOLLAMA_RESOLVED_ACCELERATION=amd\nenv_was_new=false\n'+image_logic+'\n'
    r=subprocess.run(['bash','-c',harness],cwd=td,text=True,capture_output=True,timeout=20)
    assert r.returncode==0, r.stderr
    env=(td/'.env').read_text()
    assert 'OLLAMA_IMAGE=ollama/ollama:0.32.14-rocm\n' in env
    assert 'LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:0.32.14-rocm\n' in env

print('v14.3.0 hardening fixtures: PASS')
