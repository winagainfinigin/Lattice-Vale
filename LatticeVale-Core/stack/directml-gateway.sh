#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

state_dir=data/directml
venv="$state_dir/venv"
hf_cache="$state_dir/hf-cache"
requirements=./directml-requirements.txt
requirements_hash="$state_dir/requirements.sha256"
deps_failed="$state_dir/dependencies.failed"
force_fallback_file="$state_dir/force-fallback"
last_backend="$state_dir/last-backend"
pid_file=.directml-gateway.pid
supervisor_pid_file=.directml-gateway-supervisor.pid
disabled_file=.directml-gateway.disabled
log_file=logs/directml-gateway.log
service_name=latticevale-directml-gateway.service

opt_text() { jq -r ".${1} // empty" install-options.json; }
opt_port() { local key="$1" default="$2" v; v="$(jq -r --arg k "$key" --argjson d "$default" '.[$k] // $d' install-options.json)"; [[ "$v" =~ ^[0-9]+$ && "$v" -ge 1 && "$v" -le 65535 ]] || v="$default"; printf '%s' "$v"; }
local_text_backend() { local v; v="$(opt_text localTextBackend)"; [[ "$v" == ollama || "$v" == directml ]] || v=ollama; printf '%s' "$v"; }
directml_selected() { [[ "$(local_text_backend)" == directml ]] && [[ "$(jq -r '(.honcho // false) or (.hermesLocalAI // false)' install-options.json)" == true ]]; }
port() { opt_port directmlPort 11436; }
model() { local v; v="$(opt_text directmlTextModel)"; [[ -n "$v" ]] || v='Qwen/Qwen2.5-1.5B-Instruct'; printf '%s' "$v"; }
fallback_model() { local v; v="$(opt_text localTextModel)"; [[ -n "$v" ]] || v='qwen3.5:4b'; printf '%s' "$v"; }
ollama_backend() { local v; v="$(opt_text ollamaBackend)"; [[ "$v" == managed || "$v" == windows-native ]] || v=managed; printf '%s' "$v"; }
adapter_name() {
  local v
  v="$(jq -r '.adapterSelection.selected.name // empty' data/latticevale/backend-capabilities.json 2>/dev/null || true)"
  [[ -n "$v" ]] || v="$(opt_text directmlAdapterName)"
  printf '%s' "$v"
}
gpu_vendor() {
  local v
  v="$(jq -r '.adapterSelection.selected.vendor // empty' data/latticevale/backend-capabilities.json 2>/dev/null || true)"
  [[ -n "$v" ]] || v="$(opt_text directmlGpuVendor)"
  [[ "$v" == amd || "$v" == nvidia || "$v" == intel || "$v" == qualcomm || "$v" == other ]] || v=''
  printf '%s' "$v"
}
declared_vram_mib() {
  local v=0
  if [[ -s data/latticevale/backend-capabilities.json && ! -L data/latticevale/backend-capabilities.json ]]; then
    v="$(jq -r '.adapterSelection.selected.directmlAdmission.capacityMiB // 0' data/latticevale/backend-capabilities.json 2>/dev/null || printf 0)"
  fi
  # Migration compatibility only: older 14.5.x stacks stored a selected-adapter
  # value in install-options.json. New 14.6 runtime admission uses derived state.
  if [[ ! "$v" =~ ^[0-9]+$ || "$v" -le 0 ]]; then
    v="$(jq -r '.directmlVramMiB // 0' install-options.json 2>/dev/null || printf 0)"
  fi
  [[ "$v" =~ ^[0-9]+$ && "$v" -ge 0 && "$v" -le 1048576 ]] || v=0
  printf '%s' "$v"
}
declared_vram_source() {
  local v legacy_v
  v="$(jq -r '.adapterSelection.selected.directmlAdmission.source // empty' data/latticevale/backend-capabilities.json 2>/dev/null || true)"
  if [[ -z "$v" ]]; then
    legacy_v="$(jq -r '.directmlVramMiB // 0' install-options.json 2>/dev/null || printf 0)"
    if [[ "$legacy_v" =~ ^[0-9]+$ && "$legacy_v" -ge 256 ]]; then
      v=legacy-install-options
    else
      v=unavailable
    fi
  fi
  printf '%s' "$v"
}
declared_vram_confidence() {
  local v legacy_v
  v="$(jq -r '.adapterSelection.selected.directmlAdmission.confidence // empty' data/latticevale/backend-capabilities.json 2>/dev/null || true)"
  if [[ -z "$v" ]]; then
    legacy_v="$(jq -r '.directmlVramMiB // 0' install-options.json 2>/dev/null || printf 0)"
    if [[ "$legacy_v" =~ ^[0-9]+$ && "$legacy_v" -ge 256 ]]; then
      v=legacy
    else
      v=none
    fi
  fi
  printf '%s' "$v"
}
directml_env_adapter() { adapter_name; }

log_msg() {
  mkdir -p logs
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$log_file"
}

docker_host_gateway_ip() {
  local ip
  ip="$(docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null | head -n1 | tr -d '\r' || true)"
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  case "$ip" in 127.*|169.254.*|0.0.0.0) return 1;; esac
  printf '%s' "$ip"
}

native_fallback_url() {
  [[ "$(ollama_backend)" == windows-native ]] || return 0
  [[ -x ./native-ollama-relay.sh ]] || return 1
  local base
  base="$(./native-ollama-relay.sh base-url 2>/dev/null || true)"
  [[ -n "$base" ]] || return 1
  printf '%s/v1' "${base%/}"
}

python_bin() {
  [[ -x "$venv/bin/python" ]] && { printf '%s' "$venv/bin/python"; return; }
  command -v python3
}

requirements_digest() { sha256sum "$requirements" | awk '{print $1}'; }

# WSL's D3D12 translation layer chooses the exposed adapter before torch-directml
# imports.  Saving an adapter in Python alone is therefore too late on multi-GPU
# systems.  Microsoft documents MESA_D3D12_DEFAULT_ADAPTER_NAME for this purpose.
directml_runtime_fingerprint() {
  local material='' p
  material="kernel=$(uname -r 2>/dev/null || true)|hardware=$(jq -r '.hardwareFingerprint // empty' data/latticevale/hardware-capabilities.json 2>/dev/null || true)|backend=$(jq -r '.backendFingerprint // empty' data/latticevale/backend-capabilities.json 2>/dev/null || true)|adapter=$(adapter_name)|vendor=$(gpu_vendor)|vram=$(declared_vram_mib)|vram_source=$(declared_vram_source)|req=$(requirements_digest 2>/dev/null || true)"
  for p in /dev/dxg /usr/lib/wsl/lib/libd3d12.so /usr/lib/wsl/lib/libd3d12core.so /usr/lib/wsl/lib/libdxcore.so; do
    if [[ -e "$p" ]]; then
      material+="|$p=$(stat -Lc '%t:%T:%s:%Y' "$p" 2>/dev/null || true)"
    else
      material+="|$p=missing"
    fi
  done
  printf '%s' "$material" | sha256sum | awk '{print $1}'
}

write_force_fallback() {
  local reason="$1" fp
  fp="$(directml_runtime_fingerprint 2>/dev/null || true)"
  {
    printf 'VERSION=14.6.0\n'
    printf 'TIME=%s\n' "$(date --iso-8601=seconds)"
    printf 'FINGERPRINT=%s\n' "$fp"
    printf 'REASON=%s\n' "$reason"
  } >"$force_fallback_file"
  chmod 0600 "$force_fallback_file" 2>/dev/null || true
}

reconcile_force_fallback() {
  [[ -s "$force_fallback_file" && ! -L "$force_fallback_file" ]] || return 0
  local saved current marker_version
  marker_version="$(sed -n 's/^VERSION=//p' "$force_fallback_file" 2>/dev/null | head -n1)"
  saved="$(sed -n 's/^FINGERPRINT=//p' "$force_fallback_file" 2>/dev/null | head -n1)"
  current="$(directml_runtime_fingerprint 2>/dev/null || true)"
  # v14.5.46 markers carried no fingerprint.  Retry once after upgrading to the
  # corrected adapter-selection/runtime fingerprint implementation.  Thereafter
  # retry automatically only when the relevant WSL GPU/runtime shape changes.
  if [[ "$marker_version" != 14.6.0 || -z "$saved" || ( -n "$current" && "$saved" != "$current" ) ]]; then
    log_msg 'DirectML runtime fingerprint changed (or legacy fallback marker found); clearing fallback marker for one fresh hardware probe'
    rm -f "$force_fallback_file"
  fi
}

install_dependencies() {
  directml_selected || return 0
  mkdir -p "$state_dir" "$hf_cache" logs
  [[ -f "$requirements" ]] || { echo 'DirectML requirements file is missing; rerun the Windows installer and choose Resume / repair.' >&2; return 1; }
  if [[ ! -x "$venv/bin/python" ]]; then
    rm -rf "$venv"
    if ! python3 -m venv "$venv"; then
      echo 'WARNING: Could not create the isolated DirectML Python venv. The gateway will remain Ollama-fallback capable and repair will retry.' >&2
      printf '%s\n' 'python3 -m venv failed' >"$deps_failed"
      return 0
    fi
  fi
  local wanted current='' rebuild=false
  wanted="$(requirements_digest)"
  [[ -r "$requirements_hash" ]] && current="$(cat "$requirements_hash" 2>/dev/null || true)"

  # v14.5.3 used the default Linux PyTorch wheel, which can pull CUDA/NVIDIA
  # runtime packages even on AMD/Intel DirectML systems. The DirectML venv is
  # installer-owned, so repair may safely rebuild only this venv when that stale
  # dependency shape is detected.
  if env MESA_D3D12_DEFAULT_ADAPTER_NAME="$(directml_env_adapter)" "$venv/bin/python" - <<'PY_DML_ENV_SHAPE' >/dev/null 2>&1
import importlib.metadata as md
try:
    import torch
except Exception:
    raise SystemExit(1)
version=str(torch.__version__).lower()
if '+cpu' not in version:
    raise SystemExit(1)
if any((d.metadata.get('Name') or '').lower().startswith('nvidia-') for d in md.distributions()):
    raise SystemExit(1)
PY_DML_ENV_SHAPE
  then
    :
  else
    rebuild=true
  fi
  if [[ "$rebuild" == true ]]; then
    echo 'Replacing the old DirectML Python environment with the vendor-neutral CPU PyTorch base (DirectML still performs GPU execution).'
    rm -rf "$venv"
    python3 -m venv "$venv" || { printf '%s\n' 'python3 -m venv failed during DirectML dependency migration' >"$deps_failed"; return 0; }
    current=''
  fi

  if [[ "$current" == "$wanted" ]] && env MESA_D3D12_DEFAULT_ADAPTER_NAME="$(directml_env_adapter)" "$venv/bin/python" - <<'PY_PROBE_DEPS' >/dev/null 2>&1
import importlib.metadata as md
import torch,torch_directml,transformers
assert '+cpu' in str(torch.__version__).lower()
assert not any((d.metadata.get('Name') or '').lower().startswith('nvidia-') for d in md.distributions())
x=(torch.tensor([1.0]).to(torch_directml.device())+2.0).cpu().item()
raise SystemExit(0 if abs(float(x)-3.0)<0.001 else 1)
PY_PROBE_DEPS
  then
    rm -f "$deps_failed"
    echo 'DirectML Python environment already satisfies the pinned vendor-neutral compatibility set.'
    return 0
  fi

  echo 'Installing/updating the isolated PyTorch DirectML compatibility environment...'
  # DirectML is the GPU backend. Install the CPU-only PyTorch base deliberately so
  # pip cannot drag CUDA/NVIDIA wheels into AMD/Intel/Qualcomm DirectML installs.
  if timeout --foreground --kill-after=20s 1800s "$venv/bin/python" -m pip install --disable-pip-version-check --upgrade 'pip<26' >/dev/null 2>&1 && \
     timeout --foreground --kill-after=30s 3600s "$venv/bin/python" -m pip install --disable-pip-version-check --index-url https://download.pytorch.org/whl/cpu 'torch==2.4.1+cpu' 'torchvision==0.19.1+cpu' && \
     timeout --foreground --kill-after=30s 1800s "$venv/bin/python" -m pip install --disable-pip-version-check -r "$requirements" && \
     timeout --foreground --kill-after=30s 1800s "$venv/bin/python" -m pip install --disable-pip-version-check --no-deps 'torch-directml==0.2.5.dev240914'; then
    if env MESA_D3D12_DEFAULT_ADAPTER_NAME="$(directml_env_adapter)" "$venv/bin/python" - <<'PY_VERIFY_DML'
import importlib.metadata as md
import torch,torch_directml,transformers
bad=sorted((d.metadata.get('Name') or '') for d in md.distributions() if (d.metadata.get('Name') or '').lower().startswith('nvidia-'))
if bad:
    raise SystemExit('unexpected NVIDIA packages in DirectML venv: '+','.join(bad))
if '+cpu' not in str(torch.__version__).lower():
    raise SystemExit(f'DirectML venv expected CPU PyTorch base but found torch={torch.__version__}')
x=(torch.tensor([1.0]).to(torch_directml.device())+2.0).cpu().item()
print(f'DirectML tensor probe passed: torch={torch.__version__}; transformers={transformers.__version__}; device={torch_directml.device()}; result={x}')
raise SystemExit(0 if abs(float(x)-3.0)<0.001 else 1)
PY_VERIFY_DML
    then
      printf '%s\n' "$wanted" >"$requirements_hash"
      rm -f "$deps_failed" "$force_fallback_file"
      return 0
    fi
  fi
  rm -f "$requirements_hash"
  printf '%s\n' 'Pinned vendor-neutral DirectML dependency installation or tensor probe failed; gateway will use Ollama fallback until repair succeeds.' >"$deps_failed"
  echo 'WARNING: PyTorch DirectML could not be activated. LatticeVale will still route through the gateway and use the selected Ollama fallback; Resume / repair will retry DirectML installation.' >&2
  return 0
}

owned_worker_pid() {
  [[ -s "$pid_file" ]] || return 1
  local pid cmdline
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
  cmdline="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$PWD/directml-gateway.py"* ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  printf '%s' "$pid"
}

owned_supervisor_pid() {
  [[ -s "$supervisor_pid_file" ]] || return 1
  local pid cmdline
  pid="$(cat "$supervisor_pid_file" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
  cmdline="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"directml-gateway.sh"* && "$cmdline" == *"supervise"* ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  printf '%s' "$pid"
}

stop_worker() {
  local pid=''
  if pid="$(owned_worker_pid 2>/dev/null)"; then
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

health_url() {
  local host
  host="$(docker_host_gateway_ip)" || return 1
  printf 'http://%s:%s/health' "$host" "$(port)"
}

probe_health() {
  local url
  url="$(health_url)" || return 1
  curl -fsS --noproxy '*' --connect-timeout 2 --max-time 8 "$url"
}

directml_cpu_threads() {
  local planned cpus
  planned="$(sed -n 's/^DIRECTML_CPU_THREADS=//p' .latticevale-resource-state 2>/dev/null | head -n1 || true)"
  if [[ "$planned" =~ ^[0-9]+$ && "$planned" -ge 1 ]]; then printf '%s' "$planned"; return 0; fi
  cpus="$(nproc 2>/dev/null || printf 1)"
  [[ "$cpus" =~ ^[0-9]+$ && "$cpus" -ge 1 ]] || cpus=1
  python3 runtime-policy.py directml-cpu "$cpus" 2>/dev/null || printf 1
}

start_worker() {
  local host py native_url='' pid cpu_threads host_reserve max_new_tokens context_length mem_mib vram_mib
  host="$(docker_host_gateway_ip)" || { log_msg 'waiting for Docker default host-gateway'; return 1; }
  py="$(python_bin)" || return 1
  if [[ "$(ollama_backend)" == windows-native ]]; then native_url="$(native_fallback_url 2>/dev/null || true)"; fi
  mkdir -p logs "$state_dir" "$hf_cache"
  reconcile_force_fallback
  stop_worker
  cpu_threads="$(directml_cpu_threads)"
  context_length="$(sed -n 's/^DIRECTML_CONTEXT_LENGTH=//p' .env 2>/dev/null | head -n1 || true)"
  if [[ ! "$context_length" =~ ^[0-9]+$ ]]; then
    mem_mib="$(awk '/^MemTotal:/ {print int($2/1024); exit}' /proc/meminfo 2>/dev/null || printf 0)"
    vram_mib="$(declared_vram_mib)"
    context_length="$(python3 runtime-policy.py directml-context "$mem_mib" "$vram_mib" 2>/dev/null || printf 4096)"
  fi
  host_reserve="$(sed -n 's/^DIRECTML_HOST_RESERVE_MIB=//p' .latticevale-resource-state 2>/dev/null | head -n1 || true)"
  [[ "$host_reserve" =~ ^[0-9]+$ ]] || host_reserve=2048
  max_new_tokens="$(sed -n 's/^DIRECTML_MAX_NEW_TOKENS=//p' .latticevale-resource-state 2>/dev/null | head -n1 || true)"
  if [[ ! "$max_new_tokens" =~ ^[0-9]+$ ]]; then
    local current_context
    current_context="$(sed -n 's/^DIRECTML_CONTEXT_LENGTH=//p' .env 2>/dev/null | head -n1 || printf 4096)"
    max_new_tokens="$(python3 runtime-policy.py directml-generation "$current_context" 2>/dev/null || printf 512)"
  fi
  log_msg "starting DirectML gateway worker listen=${host}:$(port) model=$(model) fallback=$(ollama_backend) cpu_threads=${cpu_threads} host_reserve=${host_reserve}MiB"
  env \
    HF_HOME="$PWD/$hf_cache" \
    TOKENIZERS_PARALLELISM=false \
    LATTICEVALE_STACK_DIR="$PWD" \
    LATTICEVALE_DIRECTML_MODEL="$(model)" \
    LATTICEVALE_DIRECTML_CONTEXT="$context_length" \
    LATTICEVALE_DIRECTML_VRAM_LIMIT_PCT="$(sed -n 's/^DIRECTML_VRAM_LIMIT_PCT=//p' .env 2>/dev/null | head -n1 || printf 75)" \
    LATTICEVALE_DIRECTML_ADAPTER_NAME="$(adapter_name)" \
    LATTICEVALE_DIRECTML_GPU_VENDOR="$(gpu_vendor)" \
    LATTICEVALE_DIRECTML_VRAM_MIB="$(declared_vram_mib)" \
    LATTICEVALE_DIRECTML_VRAM_SOURCE="$(declared_vram_source)" \
    LATTICEVALE_DIRECTML_VRAM_CONFIDENCE="$(declared_vram_confidence)" \
    MESA_D3D12_DEFAULT_ADAPTER_NAME="$(directml_env_adapter)" \
    LATTICEVALE_DIRECTML_FORCE_FALLBACK="$(if [[ -e "$force_fallback_file" ]]; then printf 1; else printf 0; fi)" \
    LATTICEVALE_OLLAMA_TEXT_MODEL="$(fallback_model)" \
    LATTICEVALE_OLLAMA_BACKEND="$(ollama_backend)" \
    LATTICEVALE_NATIVE_OLLAMA_URL="$native_url" \
    LATTICEVALE_DIRECTML_MAX_NEW_TOKENS="$max_new_tokens" \
    LATTICEVALE_DIRECTML_IDLE_UNLOAD_SECONDS=300 \
    LATTICEVALE_DIRECTML_HOST_RESERVE_MIB="$host_reserve" \
    LATTICEVALE_DIRECTML_CPU_THREADS="$cpu_threads" \
    OMP_NUM_THREADS="$cpu_threads" \
    MKL_NUM_THREADS="$cpu_threads" \
    "$py" "$PWD/directml-gateway.py" --listen-address "$host" --listen-port "$(port)" >>"$log_file" 2>&1 </dev/null &
  pid=$!
  printf '%s\n' "$pid" >"$pid_file"
  for _ in $(seq 1 60); do
    if probe_health >/dev/null 2>&1; then log_msg "DirectML gateway worker ready pid=$pid"; return 0; fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  log_msg 'DirectML gateway worker did not become healthy'
  stop_worker
  return 1
}

supervise_gateway() {
  directml_selected || exit 0
  mkdir -p logs "$state_dir"
  rm -f "$disabled_file"
  if command -v flock >/dev/null 2>&1; then exec 9>.directml-gateway.lock; flock -n 9 || exit 0; fi
  printf '%s\n' "$$" >"$supervisor_pid_file"
  cleanup() { stop_worker; rm -f "$supervisor_pid_file"; log_msg 'DirectML gateway supervisor stopped'; exit 0; }
  trap cleanup TERM INT HUP
  log_msg "DirectML gateway supervisor started pid=$$"
  local failures=0 delay=5
  while [[ ! -e "$disabled_file" ]]; do
    if ! owned_worker_pid >/dev/null 2>&1 || ! probe_health >/dev/null 2>&1; then
      if start_worker; then
        failures=0; delay=5
      else
        failures=$((failures+1))
        if (( failures >= 2 )) && [[ ! -e "$force_fallback_file" ]]; then
          log_msg 'DirectML worker failed twice before reaching health; switching to lightweight Ollama fallback to protect WSL host resources'
          write_force_fallback 'repeated DirectML worker startup failure'
          failures=0; delay=5
        else
          (( delay < 60 )) && delay=$((delay*3))
          (( delay > 60 )) && delay=60
          log_msg "DirectML worker restart deferred ${delay}s after startup failure"
          sleep "$delay"
        fi
        continue
      fi
    fi
    sleep 15
  done
  cleanup
}

wait_ready() {
  for _ in $(seq 1 80); do probe_health >/dev/null 2>&1 && return 0; sleep 0.25; done
  return 1
}

start_gateway() {
  directml_selected || return 0
  rm -f "$disabled_file"
  if owned_supervisor_pid >/dev/null 2>&1; then wait_ready && return 0; fi
  if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1 && systemctl cat "$service_name" >/dev/null 2>&1; then
    systemctl start "$service_name" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      if owned_supervisor_pid >/dev/null 2>&1 && wait_ready; then return 0; fi
      sleep 0.25
    done
  fi
  mkdir -p logs
  nohup bash "$PWD/directml-gateway.sh" supervise >>"$log_file" 2>&1 </dev/null &
  for _ in $(seq 1 30); do owned_supervisor_pid >/dev/null 2>&1 && break; sleep 0.1; done
  wait_ready && return 0
  echo 'DirectML gateway did not become reachable. Check logs/directml-gateway.log.' >&2
  return 1
}

stop_gateway() {
  local pid=''
  touch "$disabled_file"
  if pid="$(owned_supervisor_pid 2>/dev/null)"; then
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
  fi
  stop_worker
  rm -f "$supervisor_pid_file"
}

self_test() {
  start_gateway || return 1
  local host payload response backend direct_error
  host="$(docker_host_gateway_ip)" || return 1
  payload="$(python3 - "$(model)" <<'PY_SELF_PAYLOAD'
import json,sys
print(json.dumps({'model':sys.argv[1],'messages':[{'role':'user','content':'Reply with exactly: LatticeVale DirectML test'}],'max_tokens':32,'temperature':0,'stream':False}))
PY_SELF_PAYLOAD
)"
  if ! response="$(timeout --foreground --kill-after=20s 3600s curl -fsS --noproxy '*' --connect-timeout 5 --max-time 3500 -H 'Content-Type: application/json' -d "$payload" "http://${host}:$(port)/v1/chat/completions" 2>/dev/null)"; then
    # Native DirectML/model failures can terminate the Python worker before it has
    # a chance to catch the exception and proxy the same request. Preserve service
    # availability: record a bounded fallback mode, restart the gateway without a
    # DirectML model attempt, and prove Ollama can answer. Resume / repair clears
    # this marker after rebuilding/revalidating the DirectML environment.
    echo 'WARNING: DirectML model self-test terminated without an HTTP response. Switching this installation to managed Ollama fallback mode until the next Resume / repair retries DirectML.' >&2
    mkdir -p "$state_dir"
    write_force_fallback 'hard DirectML/model self-test failure'
    stop_gateway
    rm -f "$disabled_file"
    start_gateway || return 1
    host="$(docker_host_gateway_ip)" || return 1
    response="$(timeout --foreground --kill-after=20s 360s curl -fsS --noproxy '*' --connect-timeout 5 --max-time 340 -H 'Content-Type: application/json' -d "$payload" "http://${host}:$(port)/v1/chat/completions")" || return 1
  fi
  backend="$(jq -r '.x_latticevale_backend // empty' <<<"$response")"
  [[ -n "$backend" ]] || return 1
  printf '%s\n' "$backend" >"$last_backend"
  if [[ "$backend" == directml ]]; then
    rm -f "$force_fallback_file"
    python3 latticevale_arch.py record-health directml verified-working DML_RUNTIME_VERIFIED --stack . --compat compatibility.conf --hardware data/latticevale/hardware-capabilities.json --detail "DirectML model self-test passed" >/dev/null 2>&1 || true
    python3 backend-capabilities.py --stack . --compat compatibility.conf --hardware data/latticevale/hardware-capabilities.json --options install-options.json --output data/latticevale/backend-capabilities.json >/dev/null 2>&1 || true
    echo "DirectML inference verification passed with model $(model)."
  else
    direct_error="$(jq -r '.x_latticevale_directml_error // empty' <<<"$response")"
    local reason_code=DML_MODEL_EXECUTION_FAILED
    if [[ "$direct_error" == *'no trusted bounded memory-capacity source'* || "$direct_error" == *'VRAM capacity'* ]]; then
      reason_code=DML_VRAM_CAPACITY_UNAVAILABLE
    fi
    python3 latticevale_arch.py record-health directml failed "$reason_code" --stack . --compat compatibility.conf --hardware data/latticevale/hardware-capabilities.json --detail "${direct_error:-DirectML model execution unavailable}" >/dev/null 2>&1 || true
    python3 backend-capabilities.py --stack . --compat compatibility.conf --hardware data/latticevale/hardware-capabilities.json --options install-options.json --output data/latticevale/backend-capabilities.json >/dev/null 2>&1 || true
    echo "WARNING: DirectML gateway is operational but this test used Ollama fallback. ${direct_error:-DirectML model execution was unavailable.}" >&2
  fi
}

case "${1:-status}" in
  install) install_dependencies ;;
  start) start_gateway ;;
  stop) stop_gateway ;;
  restart) stop_gateway; rm -f "$disabled_file"; start_gateway ;;
  supervise) supervise_gateway ;;
  self-test) self_test ;;
  health) probe_health ;;
  host) docker_host_gateway_ip ;;
  base-url)
    host="$(docker_host_gateway_ip)" || exit 1
    printf 'http://%s:%s/v1' "$host" "$(port)"
    ;;
  diagnose)
    echo "selected=$(if directml_selected; then printf true; else printf false; fi)"
    echo "adapter=$(adapter_name)"
    echo "vendor=$(gpu_vendor)"
    echo "declared_vram_mib=$(declared_vram_mib)"
    echo "declared_vram_source=$(declared_vram_source)"
    echo "declared_vram_confidence=$(declared_vram_confidence)"
    echo "mesa_d3d12_adapter=$(directml_env_adapter)"
    echo "runtime_fingerprint=$(directml_runtime_fingerprint 2>/dev/null || true)"
    for p in /dev/dxg /usr/lib/wsl/lib/libd3d12.so /usr/lib/wsl/lib/libd3d12core.so /usr/lib/wsl/lib/libdxcore.so; do [[ -e "$p" ]] && echo "$p=present" || echo "$p=missing"; done
    [[ -e "$force_fallback_file" ]] && { echo 'force_fallback=present'; cat "$force_fallback_file"; } || echo 'force_fallback=absent'
    if [[ -x "$venv/bin/python" ]]; then
      env MESA_D3D12_DEFAULT_ADAPTER_NAME="$(directml_env_adapter)" LATTICEVALE_DIRECTML_VRAM_MIB="$(declared_vram_mib)" LATTICEVALE_DIRECTML_VRAM_SOURCE="$(declared_vram_source)" LATTICEVALE_DIRECTML_VRAM_CONFIDENCE="$(declared_vram_confidence)" "$venv/bin/python" - <<'PY_DIAG_DML'
import torch, torch_directml
print(f'torch={torch.__version__}')
print(f'device_count={torch_directml.device_count()}')
for i in range(int(torch_directml.device_count())):
    try: name=torch_directml.device_name(i)
    except Exception as exc: name=f'<name-error:{exc}>'
    try: mem=torch_directml.gpu_memory(i) if hasattr(torch_directml,'gpu_memory') else 'api-missing'
    except Exception as exc: mem=f'<memory-error:{exc}>'
    print(f'adapter[{i}]={name}; gpu_memory={mem}')
d=torch_directml.device(); value=(torch.tensor([1.0]).to(d)+2.0).cpu().item(); print(f'default_device={d}; tensor_result={value}')
PY_DIAG_DML
    else
      echo 'directml_venv=missing'
    fi
    ;;
  status)
    if ! directml_selected; then echo 'inactive (DirectML text backend not selected)'; exit 0; fi
    if health="$(probe_health 2>/dev/null)"; then
      backend="$(cat "$last_backend" 2>/dev/null || true)"
      ready="$(jq -r '.directml_ready // false' <<<"$health" 2>/dev/null || printf false)"
      loaded="$(jq -r '.model_loaded // false' <<<"$health" 2>/dev/null || printf false)"
      echo "healthy directml_ready=$ready model_loaded=$loaded last_inference_backend=${backend:-not-tested} endpoint=$(health_url)"
    elif pid="$(owned_supervisor_pid 2>/dev/null)"; then
      echo "supervised pid=$pid health=waiting/unhealthy"
      exit 1
    else
      echo 'stopped'
      exit 1
    fi
    ;;
  *) echo 'Usage: ./directml-gateway.sh {install|start|stop|restart|supervise|self-test|health|host|base-url|diagnose|status}' >&2; exit 2 ;;
esac
