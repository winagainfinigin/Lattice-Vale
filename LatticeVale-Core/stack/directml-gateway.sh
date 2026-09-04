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
adapter_name() { opt_text directmlAdapterName; }
gpu_vendor() { local v; v="$(opt_text directmlGpuVendor)"; [[ "$v" == amd || "$v" == nvidia || "$v" == intel || "$v" == qualcomm ]] || v=''; printf '%s' "$v"; }

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
  if "$venv/bin/python" - <<'PY_DML_ENV_SHAPE' >/dev/null 2>&1
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

  if [[ "$current" == "$wanted" ]] && "$venv/bin/python" - <<'PY_PROBE_DEPS' >/dev/null 2>&1
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
    if "$venv/bin/python" - <<'PY_VERIFY_DML'
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

start_worker() {
  local host py native_url='' pid
  host="$(docker_host_gateway_ip)" || { log_msg 'waiting for Docker default host-gateway'; return 1; }
  py="$(python_bin)" || return 1
  if [[ "$(ollama_backend)" == windows-native ]]; then native_url="$(native_fallback_url 2>/dev/null || true)"; fi
  mkdir -p logs "$state_dir" "$hf_cache"
  stop_worker
  log_msg "starting DirectML gateway worker listen=${host}:$(port) model=$(model) fallback=$(ollama_backend)"
  env \
    HF_HOME="$PWD/$hf_cache" \
    TOKENIZERS_PARALLELISM=false \
    LATTICEVALE_STACK_DIR="$PWD" \
    LATTICEVALE_DIRECTML_MODEL="$(model)" \
    LATTICEVALE_DIRECTML_CONTEXT="$(sed -n 's/^DIRECTML_CONTEXT_LENGTH=//p' .env 2>/dev/null | head -n1 || printf 8192)" \
    LATTICEVALE_DIRECTML_VRAM_LIMIT_PCT="$(sed -n 's/^DIRECTML_VRAM_LIMIT_PCT=//p' .env 2>/dev/null | head -n1 || printf 75)" \
    LATTICEVALE_DIRECTML_ADAPTER_NAME="$(adapter_name)" \
    LATTICEVALE_DIRECTML_GPU_VENDOR="$(gpu_vendor)" \
    LATTICEVALE_DIRECTML_FORCE_FALLBACK="$(if [[ -e "$force_fallback_file" ]]; then printf 1; else printf 0; fi)" \
    LATTICEVALE_OLLAMA_TEXT_MODEL="$(fallback_model)" \
    LATTICEVALE_OLLAMA_BACKEND="$(ollama_backend)" \
    LATTICEVALE_NATIVE_OLLAMA_URL="$native_url" \
    LATTICEVALE_DIRECTML_MAX_NEW_TOKENS=512 \
    LATTICEVALE_DIRECTML_IDLE_UNLOAD_SECONDS=300 \
    OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" \
    MKL_NUM_THREADS="${MKL_NUM_THREADS:-4}" \
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
  while [[ ! -e "$disabled_file" ]]; do
    if ! owned_worker_pid >/dev/null 2>&1 || ! probe_health >/dev/null 2>&1; then
      start_worker || { sleep 5; continue; }
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
    printf '%s\n' "$(date --iso-8601=seconds) hard DirectML/model self-test failure" >"$force_fallback_file"
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
    echo "DirectML inference verification passed with model $(model)."
  else
    direct_error="$(jq -r '.x_latticevale_directml_error // empty' <<<"$response")"
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
  *) echo 'Usage: ./directml-gateway.sh {install|start|stop|restart|supervise|self-test|health|host|base-url|status}' >&2; exit 2 ;;
esac
