#!/usr/bin/env python3
from pathlib import Path
import re, subprocess, tempfile, shutil, os, signal, time, sys
from types import SimpleNamespace
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
version=(ROOT/'VERSION.txt').read_text().strip()


def run_bash_fixture(harness, cwd, timeout=20):
    """Run a legacy shell harness in its own bounded process group.

    The regression runner already starts each fixture in a new session.  Creating a
    second GNU ``timeout --foreground`` layer here made this historical fixture
    sensitive to nested session/process-group behavior.  Give the synthetic shell its
    own session instead, keep output file-backed, and kill only that session on timeout.
    Production validation and all fixture assertions remain unchanged.
    """
    with tempfile.TemporaryFile(mode="w+") as out, tempfile.TemporaryFile(mode="w+") as err:
        proc = subprocess.Popen(
            ["bash", "-c", harness],
            cwd=cwd,
            text=True,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            returncode = proc.wait()
            out.seek(0); err.seek(0)
            stdout = out.read(); stderr = err.read()
            raise AssertionError(
                f"legacy bash fixture exceeded {timeout}s; stdout={stdout[-2000:]!r}; stderr={stderr[-2000:]!r}"
            ) from exc
        finally:
            # A well-behaved harness exits with all children reaped.  If an old shell
            # snippet detached a descendant, terminate only this synthetic session so
            # it cannot leak into later regression fixtures.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        out.seek(0); err.seek(0)
        stdout=out.read(); stderr=err.read()
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


assert version in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0','14.6.1','14.6.2'}
assert 'schema = $compat.InstallOptionsSchema' in ps
assert "ollamaAcceleration = $ollamaAcceleration" in ps
assert "$options.Remove('ollamaAcceleration')" in ps and 'Legacy same-line repair: preserving the existing Ollama image/runtime choice' in ps
assert "containerResourceLimits = $containerResourceLimits" in ps
assert "@('auto','cpu','nvidia','amd','vulkan')" in ps if version in {'14.5.47','14.6.0','14.6.1','14.6.2'} else "@('auto','cpu','nvidia','amd')" in ps
assert 'install_nvidia_container_toolkit_if_needed' in boot
assert 'https://nvidia.github.io/libnvidia-container/gpgkey' in boot
assert 'unexpected package origin' in boot and 'nvidia\\.github\\.io/libnvidia-container/' in boot
assert 'nvidia-ctk runtime configure --runtime=docker' in boot
for pkg in ('nvidia-container-toolkit','nvidia-container-toolkit-base','libnvidia-container-tools','libnvidia-container1'):
    assert pkg in boot
assert "consult NVIDIA's stable APT channel" in boot
assert 'newest available toolkit' in boot
assert '--allow-downgrades' not in boot
assert '"${nvidia_toolkit_packages[@]}"' in boot
assert 'cuda-drivers' not in boot and 'apt-get install -y cuda' not in boot
assert '/dev/kfd' in conf and '/dev/dri' in conf
assert 'group_add:' in conf and "stat -c '%g'" in conf
assert 'driver: nvidia' in conf and 'capabilities: [gpu]' in conf
assert 'compose.latticevale.yaml' in conf and 'compose.override.yaml' in conf
assert 'LATTICEVALE_SEARXNG_IMAGE_AUTO' in (ROOT/'stack/managed-upstreams.py').read_text(encoding='utf-8')
assert 'def desired_ollama' in (ROOT/'stack/managed-upstreams.py').read_text(encoding='utf-8')
assert 'LATTICEVALE_OLLAMA_IMAGE_AUTO' in (ROOT/'stack/managed-upstreams.py').read_text(encoding='utf-8') and 'user-override' in (ROOT/'stack/managed-upstreams.py').read_text(encoding='utf-8')
assert 'custom Ollama image override preserved' in audit
assert 'GPU execution verified at runtime by ollama ps' in audit
assert 'parsed_bootstrap_options=' in boot and 'PY_BOOTSTRAP_OPTIONS' in boot
assert not any('grep -Eq' in line and 'honcho|hermesLocalAI' in line for line in boot.splitlines())
assert 'containerResourceLimits' in conf
assert 'runtimePolicy' in audit and 'compose.latticevale.yaml' in audit and 'LATTICEVALE_OLLAMA_ACCELERATION' in audit
assert 'searxng/searxng:latest' in conf+compose
assert 'ollama/ollama:latest' in conf+compose
upstreams=(ROOT/'stack/managed-upstreams.py').read_text(encoding='utf-8')
assert 'ollama/ollama:rocm' in upstreams and 'acceleration == "amd"' in upstreams
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
    shutil.copy2(ROOT/'stack/runtime-policy.py', td/'runtime-policy.py')
    shutil.copy2(ROOT/'stack/latticevale_arch.py', td/'latticevale_arch.py')
    shutil.copy2(ROOT/'compatibility.conf', td/'compatibility.conf')
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
directml_text_enabled() { return 1; }
ollama_gpu_metrics() { printf '1:8192:8192:8192\n'; }
''' + functions + r'''
cat > install-options.json <<'JSON_OPTIONS'
{"matrix":true,"searxng":true,"qmd":true,"honcho":true,"hermesLocalAI":true,"ollamaBackend":"managed"}
JSON_OPTIONS
printf 'MemTotal: 16777216 kB\n' > fake-meminfo
mkdir -p data/latticevale
cat > data/latticevale/hardware-capabilities.json <<'JSON_HARDWARE'
{"hardwareFingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","wsl":{"cpuCount":4,"memoryMiB":16384}}
JSON_HARDWARE
cat > data/latticevale/backend-capabilities.json <<'JSON_BACKENDS'
{"backendFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","selection":{}}
JSON_BACKENDS
write_latticevale_compose_overlay cpu true
'''
    r=run_bash_fixture(harness, td, 45)
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

# GPU overlay branches are source-validated here instead of re-running the full
# adaptive planner in a synthetic host. The latter depends on host device/runtime
# behavior and can retain descendants on build-only Linux runners. Canonical CPU/RAM
# planning has dedicated deterministic fixtures; this historical hardening check owns
# only the emitted NVIDIA/AMD Compose device syntax.
overlay_fn=conf[conf.index('write_latticevale_compose_overlay() {'):conf.index('\nruntime_policy_verify_error()', conf.index('write_latticevale_compose_overlay() {'))]
assert "driver: nvidia" in overlay_fn
assert "count: all" in overlay_fn
assert "capabilities: [gpu]" in overlay_fn
assert "/dev/kfd:/dev/kfd" in overlay_fn
assert "/dev/dri:/dev/dri" in overlay_fn
assert "group_add:" in overlay_fn and "stat -c '%g'" in overlay_fn
for snippet in (
    'services:\n  ollama:\n    deploy:\n      resources:\n        reservations:\n          devices:\n            - driver: nvidia\n              count: all\n              capabilities: [gpu]\n',
    'services:\n  ollama:\n    devices:\n      - /dev/kfd:/dev/kfd\n      - /dev/dri:/dev/dri\n    group_add:\n      - "44"\n',
):
    parsed=yaml.safe_load(snippet)
    assert 'ollama' in parsed['services']


# Image ownership marker semantics are centralized in managed-upstreams.py. A deliberate
# override survives refresh, while an installer-owned old CPU image advances to the ROCm
# rolling stable channel when AMD becomes the selected managed acceleration path.
upstream_helper=ROOT/'stack/managed-upstreams.py'
upstream_text=upstream_helper.read_text(encoding='utf-8')
assert 'current == prior_auto' in upstream_text and 'user-override' in upstream_text
assert 'ollama/ollama:rocm' in upstream_text and 'acceleration == "amd"' in upstream_text

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    shutil.copy2(upstream_helper, td/'managed-upstreams.py')
    (td/'install-options.json').write_text('{"honcho":false}\n')
    (td/'.env').write_text(
        'OLLAMA_IMAGE=example/ollama:custom\n'
        'LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:0.32.14\n'
    )
    r=subprocess.run([sys.executable, str(td/'managed-upstreams.py'), 'reconcile', '--stack', str(td), '--refresh', '--ollama-acceleration', 'cpu'], text=True, capture_output=True)
    assert r.returncode==0, r.stderr
    env=(td/'.env').read_text()
    assert 'OLLAMA_IMAGE=example/ollama:custom\n' in env

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    shutil.copy2(upstream_helper, td/'managed-upstreams.py')
    (td/'install-options.json').write_text('{"honcho":false}\n')
    (td/'.env').write_text(
        'OLLAMA_IMAGE=ollama/ollama:0.32.14\n'
        'LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:0.32.14\n'
    )
    r=subprocess.run([sys.executable, str(td/'managed-upstreams.py'), 'reconcile', '--stack', str(td), '--refresh', '--ollama-acceleration', 'amd'], text=True, capture_output=True)
    assert r.returncode==0, r.stderr
    env=(td/'.env').read_text()
    assert 'OLLAMA_IMAGE=ollama/ollama:rocm\n' in env
    assert 'LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:rocm\n' in env

print('v14.3.0 hardening fixtures: PASS')
