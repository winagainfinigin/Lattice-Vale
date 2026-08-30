#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
export DOCKER_HOST=unix:///var/run/docker.sock

usage() {
  cat <<'TXT'
Usage: ./manage.sh COMMAND [ARG]

  status                 Show current Hermes/service state without treating normal startup as failure
  verify [seconds]       Wait up to 300s (or supplied timeout) for the selected stack to become healthy
  audit                  State-aware read-only audit (includes incomplete/legacy state)
  audit-free             Read-only check of the current free/local operating path
  plan [--offline]       Show a read-only repair plan; never changes the stack
  repair --plan [--offline]
                         Alias for plan; applying repair still uses the Windows installer
  start                  Start Hermes and all selected services
  stop                   Stop the selected stack
  logs [service]         Follow logs (all selected services by default)
  restart [service]      Restart one service or the selected stack
  chat [profile]         Open interactive Hermes chat (default profile if omitted)
  profiles               List Hermes profiles
  kanban                  Show Kanban board/tasks (when enabled)
  reindex                 Run a QMD vault update/embed now (when enabled)
  backup                  Create a local backup under ./backups
  update                  Advanced upstream refresh of current configured refs; NOT the bundle-pinned installer updater
  dashboard-info          Print the dashboard URL (never prints its password)
  matrix-info             Print non-secret Matrix connection information
  matrix-profile-finish PROFILE
                         Explicitly finish one provisioned secondary Matrix profile
  matrix-credentials      Explicitly print installer-held Matrix bot credentials/secrets
  repair-info             Explain how to resume/repair with the Windows installer
  help                    Show this help
TXT
}

need_configured() { [[ -e .configured ]] || { echo 'The stack has not finished configuration.' >&2; exit 1; }; }
opt_bool() { jq -r ".${1} // false" install-options.json; }
opt_text() { jq -r ".${1} // empty" install-options.json; }
opt_port() { local key="$1" default="$2" v; v="$(jq -r --arg k "$key" --argjson d "$default" '.[$k] // $d' install-options.json)"; [[ "$v" =~ ^[0-9]+$ && "$v" -ge 1 && "$v" -le 65535 ]] || v="$default"; printf '%s' "$v"; }
HERMES_API_HOST_PORT="$(opt_port hermesApiPort 8642)"
DASHBOARD_HOST_PORT="$(opt_port dashboardLocalPort 9119)"
MATRIX_HOST_PORT="$(opt_port matrixLocalPort 8008)"
SEARXNG_HOST_PORT="$(opt_port searxngLocalPort 8888)"
HONCHO_HOST_PORT="$(opt_port honchoLocalPort 8000)"
WINDOWS_OLLAMA_BRIDGE_PORT="$(opt_port windowsOllamaBridgePort 11435)"
local_ai_enabled() { [[ "$(opt_bool honcho)" == true || "$(opt_bool hermesLocalAI)" == true ]]; }

ollama_backend() { local v; v="$(opt_text ollamaBackend)"; [[ "$v" == managed || "$v" == windows-native ]] || v=managed; printf '%s' "$v"; }
managed_ollama_enabled() { local_ai_enabled && [[ "$(ollama_backend)" == managed ]]; }
windows_native_ollama_enabled() { local_ai_enabled && [[ "$(ollama_backend)" == windows-native ]]; }
native_info_field() {
  local key="$1" default="${2:-}" value=''
  if [[ -r .windows-native-info ]]; then
    value="$(sed -n "s/^${key}=//p" .windows-native-info | head -n1 | tr -d '\r')"
  fi
  [[ -n "$value" ]] && printf '%s' "$value" || printf '%s' "$default"
}
native_service_transport() { native_info_field TRANSPORT windows-gateway-relay; }
windows_host_ip() {
  if windows_native_ollama_enabled && [[ "$(native_service_transport)" == wsl-localhost-relay ]]; then
    [[ -x ./native-ollama-relay.sh ]] || return 1
    ./native-ollama-relay.sh host
  else
    local host
    if [[ -r .windows-native-host-ip ]]; then
      host="$(head -n1 .windows-native-host-ip | tr -d '\r\n')"
      if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then printf '%s' "$host"; return; fi
    fi
    host="$(native_info_field HOST_ADDRESS '')"
    [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
    printf '%s' "$host"
  fi
}
native_ollama_base_url() { local host; host="$(windows_host_ip)"; [[ -n "$host" ]] || return 1; printf 'http://%s:%s' "$host" "$WINDOWS_OLLAMA_BRIDGE_PORT"; }

LATTICEVALE_PIN_DATE='2026-08-17'
env_value() {
  local key="$1" default="${2:-}" value='' line
  if [[ -r .env ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line%$'\r'}"
      case "$line" in
        "$key="*) value="${line#*=}"; break ;;
      esac
    done < .env
  fi
  [[ -n "$value" ]] && printf '%s' "$value" || printf '%s' "$default"
}
pin_age_days() {
  local pin_epoch now
  pin_epoch="$(date -u -d "$LATTICEVALE_PIN_DATE" +%s 2>/dev/null || true)"
  now="$(date -u +%s)"
  if [[ "$pin_epoch" =~ ^[0-9]+$ && "$now" =~ ^[0-9]+$ && "$now" -ge "$pin_epoch" ]]; then
    printf '%s' "$(( (now-pin_epoch) / 86400 ))"
  else
    printf '%s' unknown
  fi
}
show_pin_summary() {
  local age image
  age="$(pin_age_days)"
  echo
  echo "Configured image pins (LatticeVale pin date $LATTICEVALE_PIN_DATE; age: ${age} day(s); no network check):"
  printf '  %-12s %s\n' Hermes "$(env_value HERMES_IMAGE 'nousresearch/hermes-agent:v2026.8.16')"
  printf '  %-12s %s\n' Postgres "$(env_value POSTGRES_IMAGE 'postgres:16-alpine')"
  if [[ "$(opt_bool matrix)" == true ]]; then printf '  %-12s %s\n' Synapse "$(env_value SYNAPSE_IMAGE 'matrixdotorg/synapse:v1.158.0')"; fi
  if [[ "$(opt_bool searxng)" == true ]]; then
    printf '  %-12s %s\n' Valkey "$(env_value VALKEY_IMAGE 'valkey/valkey:8-alpine')"
    printf '  %-12s %s\n' SearXNG "$(env_value SEARXNG_IMAGE 'searxng/searxng:2026.8.17-374939b88')"
  fi
  if managed_ollama_enabled; then printf '  %-12s %s\n' Ollama "$(env_value OLLAMA_IMAGE 'ollama/ollama:0.32.14')"; elif windows_native_ollama_enabled; then printf '  %-12s %s\n' Ollama 'native Windows runtime (user-managed)'; fi
  if [[ "$(opt_bool honcho)" == true ]]; then
    printf '  %-12s %s\n' pgvector "$(env_value PGVECTOR_IMAGE 'pgvector/pgvector:pg15')"
    printf '  %-12s %s\n' Redis "$(env_value REDIS_IMAGE 'redis:8-alpine')"
  fi
  echo '  Note: pin age is visibility only; it does not mean a newer upstream release exists.'
}

gpu_vram_mib() {
  local accel="$1" smi total file bytes
  case "$accel" in
    nvidia)
      smi="$(command -v nvidia-smi 2>/dev/null || true)"
      [[ -n "$smi" ]] || [[ ! -x /usr/lib/wsl/lib/nvidia-smi ]] || smi=/usr/lib/wsl/lib/nvidia-smi
      [[ -n "$smi" ]] || return 1
      total="$("$smi" --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | awk '{s+=$1} END {if(s>0) printf "%.0f",s}')"
      [[ "$total" =~ ^[0-9]+$ ]] || return 1
      printf '%s' "$total"
      ;;
    amd)
      total=0
      shopt -s nullglob
      for file in /sys/class/drm/card*/device/mem_info_vram_total; do
        bytes="$(cat "$file" 2>/dev/null || true)"
        [[ "$bytes" =~ ^[0-9]+$ ]] || continue
        total=$(( total + bytes / 1048576 ))
      done
      shopt -u nullglob
      (( total > 0 )) || return 1
      printf '%s' "$total"
      ;;
    *) return 1 ;;
  esac
}

ollama_model_artifact_mib() {
  local model="$1" pair size unit
  pair="$(docker compose exec -T ollama ollama list 2>/dev/null | awk -v m="$model" 'NR>1 && $1==m {print $3, $4; exit}')"
  [[ -n "$pair" ]] || return 1
  read -r size unit <<<"$pair"
  [[ "$size" =~ ^[0-9]+([.][0-9]+)?$ ]] || return 1
  case "${unit^^}" in
    GB|GIB) awk -v n="$size" 'BEGIN {printf "%.0f", n*1024}' ;;
    MB|MIB) awk -v n="$size" 'BEGIN {printf "%.0f", n}' ;;
    KB|KIB) awk -v n="$size" 'BEGIN {printf "%.0f", n/1024}' ;;
    *) return 1 ;;
  esac
}

show_hardware_summary() {
  local cpus mem_mib accel model vram_mib model_mib offload_line
  cpus="$(nproc 2>/dev/null || printf '?')"
  mem_mib="$(awk '/^MemTotal:/ {printf "%.0f", $2/1024}' /proc/meminfo 2>/dev/null || true)"
  echo
  echo 'Hardware / resource summary:'
  echo "  WSL CPUs:              $cpus"
  [[ -n "$mem_mib" ]] && echo "  WSL RAM:               $((mem_mib/1024)) GiB (${mem_mib} MiB visible)"
  echo "  Resource policy:       $(if [[ "$(opt_bool containerResourceLimits)" == true ]]; then echo 'adaptive ceilings'; else echo 'LatticeVale ceilings disabled'; fi)"
  local_ai_enabled || { echo '  Ollama:                not selected'; return 0; }
  if windows_native_ollama_enabled; then
    local native_base native_version native_ps
    native_base="$(native_ollama_base_url 2>/dev/null || true)"
    echo '  Ollama backend:        native Windows Ollama via WSL-only relay'
    echo "  Ollama model:          $(opt_text localTextModel)"
    echo '  Acceleration config:   owned by native Windows Ollama (not modified by LatticeVale)'
    if [[ -n "$native_base" ]]; then
      native_version="$(curl -fsS --connect-timeout 2 --max-time 5 "$native_base/api/version" 2>/dev/null | jq -r '.version // empty' 2>/dev/null || true)"
      [[ -n "$native_version" ]] && echo "  Native Ollama version: $native_version"
      native_ps="$(curl -fsS --connect-timeout 2 --max-time 5 "$native_base/api/ps" 2>/dev/null | jq -c '.models // []' 2>/dev/null || true)"
      [[ -n "$native_ps" && "$native_ps" != '[]' ]] && echo "  Loaded-model runtime:  $native_ps"
    fi
    echo '  GPU/VRAM reporting:    delegated to native Windows Ollama; WSL device files are not used for this backend.'
    return 0
  fi
  accel="$(env_value LATTICEVALE_OLLAMA_ACCELERATION "$(opt_text ollamaAcceleration)")"
  [[ -n "$accel" ]] || accel=cpu
  model="$(opt_text localTextModel)"
  echo "  Ollama model:          ${model:-unknown}"
  echo "  Acceleration config:   $accel"
  if vram_mib="$(gpu_vram_mib "$accel" 2>/dev/null)"; then
    echo "  Detected GPU VRAM:     $((vram_mib/1024)) GiB (${vram_mib} MiB aggregate)"
    if model_mib="$(ollama_model_artifact_mib "$model" 2>/dev/null)"; then
      echo "  Model artifact size:   ${model_mib} MiB (rough fit signal only)"
      if (( model_mib * 100 >= vram_mib * 85 )); then
        echo '  VRAM warning:          model artifact is >=85% of detected VRAM; context/KV-cache overhead may force partial CPU offload or OOM.'
      fi
    else
      echo '  VRAM fit estimate:     unavailable until the selected model is present in Ollama.'
    fi
  elif [[ "$accel" == nvidia || "$accel" == amd ]]; then
    echo '  Detected GPU VRAM:     unavailable; GPU plumbing may still be configured.'
  fi
  offload_line="$(docker compose exec -T ollama ollama ps 2>/dev/null | awk -v m="$model" 'NR>1 && $1==m {print; exit}')"
  if [[ -n "$offload_line" ]]; then
    echo "  Loaded-model runtime:  $offload_line"
  else
    echo '  Loaded-model offload:  not currently measurable (model is not loaded).'
  fi
  echo '  Note: model size vs VRAM is only a warning; quantization, context length, KV cache, multi-GPU use, and partial offload change actual memory needs.'
}

show_memory_pressure_summary() {
  local -a containers=(hermes-agent)
  [[ "$(opt_bool matrix)" == true ]] && containers+=(hermes-synapse-db hermes-synapse)
  [[ "$(opt_bool searxng)" == true ]] && containers+=(hermes-searxng-valkey hermes-searxng)
  [[ "$(opt_bool qmd)" == true ]] && containers+=(hermes-qmd hermes-qmd-indexer)
  managed_ollama_enabled && containers+=(hermes-ollama)
  [[ "$(opt_bool honcho)" == true ]] && containers+=(hermes-honcho-db hermes-honcho-redis hermes-honcho-api hermes-honcho-deriver)
  declare -A ev_before_max=() ev_before_oom=() ev_before_kill=() ev_path=()
  local c pid cg ev line
  for c in "${containers[@]}"; do
    pid="$(docker inspect -f '{{.State.Pid}}' "$c" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ && "$pid" -gt 0 && -r "/proc/$pid/cgroup" ]] || continue
    cg="$(awk -F: '$1=="0"{print $3;exit}' "/proc/$pid/cgroup" 2>/dev/null || true)"
    ev="/sys/fs/cgroup${cg}/memory.events"
    [[ -r "$ev" ]] || continue
    ev_path[$c]="$ev"
    ev_before_max[$c]="$(awk '$1=="max"{print $2}' "$ev")"
    ev_before_oom[$c]="$(awk '$1=="oom"{print $2}' "$ev")"
    ev_before_kill[$c]="$(awk '$1=="oom_kill"{print $2}' "$ev")"
  done
  ((${#ev_path[@]})) || return 0
  sleep 2
  echo
  echo 'Current cgroup memory-pressure sample (2s delta; lifetime counters shown only as context):'
  local now_max now_oom now_kill dmax doom dkill current max_limit pct
  for c in "${containers[@]}"; do
    ev="${ev_path[$c]:-}"; [[ -n "$ev" && -r "$ev" ]] || continue
    now_max="$(awk '$1=="max"{print $2}' "$ev")"; now_oom="$(awk '$1=="oom"{print $2}' "$ev")"; now_kill="$(awk '$1=="oom_kill"{print $2}' "$ev")"
    dmax=$((now_max-${ev_before_max[$c]:-0})); doom=$((now_oom-${ev_before_oom[$c]:-0})); dkill=$((now_kill-${ev_before_kill[$c]:-0}))
    pid="$(docker inspect -f '{{.State.Pid}}' "$c" 2>/dev/null || true)"; cg="$(awk -F: '$1=="0"{print $3;exit}' "/proc/$pid/cgroup" 2>/dev/null || true)"
    current="$(cat "/sys/fs/cgroup${cg}/memory.current" 2>/dev/null || printf 0)"; max_limit="$(cat "/sys/fs/cgroup${cg}/memory.max" 2>/dev/null || printf max)"
    pct='n/a'; if [[ "$current" =~ ^[0-9]+$ && "$max_limit" =~ ^[0-9]+$ && "$max_limit" -gt 0 ]]; then pct="$((current*100/max_limit))%"; fi
    if (( dkill > 0 )); then
      printf '  %-24s CRITICAL oom_kill +%s, oom +%s, memory.max +%s, usage=%s\n' "$c" "$dkill" "$doom" "$dmax" "$pct"
    elif (( doom > 0 )); then
      printf '  %-24s PRESSURE oom +%s, memory.max +%s, usage=%s\n' "$c" "$doom" "$dmax" "$pct"
    elif (( dmax > 0 )); then
      printf '  %-24s ACTIVE memory.max +%s in 2s, usage=%s (lifetime max=%s)\n' "$c" "$dmax" "$pct" "$now_max"
    elif (( now_max > 0 )); then
      printf '  %-24s HISTORICAL no new max/OOM events in 2s, usage=%s (lifetime max=%s)\n' "$c" "$pct" "$now_max"
    else
      printf '  %-24s CLEAR no max/OOM events, usage=%s\n' "$c" "$pct"
    fi
  done
}

docker_ready() { docker info >/dev/null 2>&1; }
ensure_docker_for_user() {
  docker_ready && return 0
  echo 'Docker is not running. Starting it through the installer helper (sudo may ask for your Ubuntu password)...' >&2
  sudo /usr/local/sbin/hermes-stack-start
}

bridge_task_name() {
  [[ -s .tailscale-info ]] || return 1
  sed -n 's/^BRIDGE_TASK_NAME=//p' .tailscale-info | head -n1 | tr -d '\r'
}

control_windows_bridge() {
  local verb="$1" task exe
  task="$(bridge_task_name 2>/dev/null || true)"
  [[ -n "$task" ]] || return 0
  exe="$(command -v schtasks.exe 2>/dev/null || true)"
  if [[ -z "$exe" ]] && command -v wslpath >/dev/null 2>&1; then
    local candidate
    candidate="$(wslpath -u 'C:\Windows\System32\schtasks.exe' 2>/dev/null || true)"
    if [[ -n "$candidate" && -x "$candidate" ]]; then exe="$candidate"; fi
  fi
  if [[ -z "$exe" ]]; then
    echo "Windows relay task '$task' exists, but WSL interop could not find schtasks.exe." >&2
    return 0
  fi
  case "$verb" in
    start)
      "$exe" /Run /TN "$task" >/dev/null 2>&1 || echo "Could not start Windows relay task '$task'; the local LatticeVale stack is still running." >&2 ;;
    stop)
      "$exe" /End /TN "$task" >/dev/null 2>&1 || true ;;
  esac
}

native_service_task_name() { native_info_field BRIDGE_TASK_NAME ''; }

set_env_value() {
  local file="$1" key="$2" value="$3"
  python3 - "$file" "$key" "$value" <<'PY_MANAGE_SET_ENV'
from pathlib import Path
import sys
p=Path(sys.argv[1]); key=sys.argv[2]; value=sys.argv[3]
lines=p.read_text(encoding='utf-8').splitlines() if p.exists() else []
out=[]; done=False
for line in lines:
    if line.startswith(key+'='):
        if not done: out.append(key+'='+value); done=True
    else: out.append(line)
if not done: out.append(key+'='+value)
p.write_text('\n'.join(out)+'\n',encoding='utf-8')
PY_MANAGE_SET_ENV
}

remove_env_value() {
  local file="$1" key="$2"
  python3 - "$file" "$key" <<'PY_MANAGE_REMOVE_ENV'
from pathlib import Path
import sys
p=Path(sys.argv[1]); key=sys.argv[2]
if not p.exists(): raise SystemExit(0)
lines=[line for line in p.read_text(encoding='utf-8').splitlines() if not line.startswith(key+'=')]
p.write_text(('\n'.join(lines)+'\n') if lines else '',encoding='utf-8')
PY_MANAGE_REMOVE_ENV
}

control_windows_native_services() {
  local verb="$1" task exe host base transport
  windows_native_ollama_enabled || return 0
  transport="$(native_service_transport)"
  case "$transport" in
    wsl-localhost-relay|wsl-host-relay)
      [[ -x ./native-ollama-relay.sh ]] || { echo 'Native Windows Ollama is selected for WSL-local transport, but native-ollama-relay.sh is missing. Rerun the Windows installer and choose Resume / repair.' >&2; return 1; }
      case "$verb" in
        start)
          ./native-ollama-relay.sh start >/dev/null || return 1
          host="$(./native-ollama-relay.sh host)" || { echo 'Could not resolve Docker host-gateway for the WSL-local native Ollama relay.' >&2; return 1; }
          set_env_value .env WINDOWS_HOST_IP "$host"
          base="http://${host}:${WINDOWS_OLLAMA_BRIDGE_PORT}"
          for _ in $(seq 1 30); do
            if curl -fsS --noproxy '*' --connect-timeout 2 --max-time 4 "$base/api/version" >/dev/null 2>&1; then return 0; fi
            sleep 1
          done
          echo "WSL-local native Windows Ollama relay did not become reachable at $base." >&2
          return 1
          ;;
        stop) ./native-ollama-relay.sh stop ;;
      esac
      return 0
      ;;
    windows-gateway-relay)
      task="$(native_service_task_name 2>/dev/null || true)"
      [[ -n "$task" ]] || { echo 'Native Windows Ollama is selected but Windows relay task metadata is missing. Rerun the Windows installer and choose Resume / repair.' >&2; return 1; }
      exe="$(command -v schtasks.exe 2>/dev/null || true)"
      if [[ -z "$exe" ]] && command -v wslpath >/dev/null 2>&1; then
        local candidate
        candidate="$(wslpath -u 'C:\Windows\System32\schtasks.exe' 2>/dev/null || true)"
        [[ -n "$candidate" && -x "$candidate" ]] && exe="$candidate"
      fi
      [[ -n "$exe" ]] || { echo "Windows native-service bridge task '$task' exists, but WSL interop could not find schtasks.exe." >&2; return 1; }
      case "$verb" in
        start)
          "$exe" /End /TN "$task" >/dev/null 2>&1 || true
          sleep 1
          rm -f .windows-native-host-ip
          "$exe" /Run /TN "$task" >/dev/null 2>&1 || { echo "Could not start Windows native-service bridge task '$task'." >&2; return 1; }
          for _ in $(seq 1 20); do [[ -s .windows-native-host-ip ]] && break; sleep 0.25; done
          host="$(windows_host_ip)"
          [[ -n "$host" ]] || { echo 'Could not resolve the Windows host address from WSL.' >&2; return 1; }
          set_env_value .env WINDOWS_HOST_IP "$host"
          base="http://${host}:${WINDOWS_OLLAMA_BRIDGE_PORT}"
          for _ in $(seq 1 30); do
            if curl -fsS --noproxy '*' --connect-timeout 2 --max-time 4 "$base/api/version" >/dev/null 2>&1; then return 0; fi
            sleep 1
          done
          echo "Native Windows Ollama relay did not become reachable at $base." >&2
          return 1
          ;;
        stop) "$exe" /End /TN "$task" >/dev/null 2>&1 || true ;;
      esac
      ;;
    *) echo "Unsupported native Ollama transport '$transport'; rerun the Windows installer and choose Resume / repair." >&2; return 1 ;;
  esac
}

pull_ollama_model() {
  local model="$1" base rc=0
  if windows_native_ollama_enabled; then
    base="$(native_ollama_base_url)" || return 1
    echo "Pulling '$model' into native Windows Ollama through the verified WSL relay."
    timeout --foreground --kill-after=15s 3600s python3 - "$base" "$model" <<'PY_MANAGE_NATIVE_PULL' || rc=$?
import json,sys,urllib.request
base=sys.argv[1].rstrip('/'); model=sys.argv[2]
body=json.dumps({'model':model,'stream':False}).encode('utf-8')
req=urllib.request.Request(base+'/api/pull',data=body,headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(req,timeout=3550) as r: json.load(r)
PY_MANAGE_NATIVE_PULL
    return "$rc"
  fi
  timeout --foreground --kill-after=15s 3600s docker compose exec -T ollama ollama pull "$model"
}

selected_service_names() {
  echo hermes
  if [[ "$(opt_bool matrix)" == true ]]; then echo synapse-db; echo synapse; fi
  if [[ "$(opt_bool searxng)" == true ]]; then echo searxng-valkey; echo searxng; fi
  if [[ "$(opt_bool qmd)" == true ]]; then echo qmd; echo qmd-indexer; fi
  if managed_ollama_enabled; then echo ollama; fi
  if [[ "$(opt_bool honcho)" == true ]]; then echo honcho-db; echo honcho-redis; echo honcho-api; echo honcho-deriver; fi
}

container_is_starting() {
  local name="$1" raw running health started now epoch age
  raw="$(docker inspect -f '{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.State.StartedAt}}' "$name" 2>/dev/null || true)"
  [[ -n "$raw" ]] || return 1
  IFS='|' read -r running health started <<<"$raw"
  [[ "$running" == true ]] || return 1
  [[ "$health" == starting ]] && return 0
  epoch="$(date -d "$started" +%s 2>/dev/null || true)"
  [[ "$epoch" =~ ^[0-9]+$ ]] || return 1
  now="$(date +%s)"; age=$((now-epoch))
  (( age >= 0 && age < 300 ))
}

container_stopped_cleanly() {
  local name="$1" raw running exit_code oom error status restart_policy
  raw="$(docker inspect -f '{{.State.Running}}|{{.State.ExitCode}}|{{.State.OOMKilled}}|{{.State.Error}}|{{.State.Status}}|{{.HostConfig.RestartPolicy.Name}}' "$name" 2>/dev/null || true)"
  [[ -n "$raw" ]] || return 1
  IFS='|' read -r running exit_code oom error status restart_policy <<<"$raw"
  [[ "$running" == false && "$oom" == false && -z "$error" ]] || return 1
  if [[ "$status" == created && "$exit_code" == 0 ]]; then return 0; fi
  # LatticeVale-managed services use restart: unless-stopped. Docker may record a graceful
  # Compose stop as 0, 143 (SIGTERM), or 137 (forced SIGKILL after the stop timeout).
  # Those are intentional STOPPED states when the restart policy remains unless-stopped.
  [[ "$status" == exited && "$restart_policy" == unless-stopped && "$exit_code" =~ ^(0|137|143)$ ]]
}

check_http() {
  local name="$1" url="$2" container="${3:-}" code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || true)"
  if [[ "$code" =~ ^(2|3|401|403) ]]; then
    printf '%-12s OK (%s)\n' "$name" "$code"
  elif [[ -n "$container" ]] && container_is_starting "$container"; then
    printf '%-12s STARTING\n' "$name"
  elif [[ -n "$container" ]] && container_stopped_cleanly "$container"; then
    printf '%-12s STOPPED\n' "$name"
  else
    printf '%-12s FAILED (%s)\n' "$name" "${code:-no response}"
  fi
}

check_qmd() {
  if docker exec hermes-qmd curl -fsS --max-time 5 http://127.0.0.1:8181/health >/dev/null 2>&1; then
    printf '%-12s %s\n' QMD 'OK (Docker-internal)'
  elif container_is_starting hermes-qmd; then
    printf '%-12s %s\n' QMD 'STARTING (Docker-internal)'
  elif container_stopped_cleanly hermes-qmd; then
    printf '%-12s %s\n' QMD 'STOPPED'
  else
    printf '%-12s %s\n' QMD 'FAILED'
  fi
}

status() {
  if ! docker_ready; then
    echo 'Docker daemon is not running. Use ./manage.sh start (or sudo /usr/local/sbin/hermes-stack-start) first.' >&2
    return 1
  fi
  docker compose ps
  echo
  if docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1; then
    printf '%-12s %s\n' Hermes "$(docker exec -u hermes hermes-agent hermes --version 2>/dev/null | head -n1)"
  elif container_is_starting hermes-agent; then
    printf '%-12s STARTING\n' Hermes
  elif container_stopped_cleanly hermes-agent; then
    printf '%-12s STOPPED\n' Hermes
  else
    printf '%-12s FAILED\n' Hermes
  fi
  check_http Hermes-API http://127.0.0.1:${HERMES_API_HOST_PORT}/health hermes-agent
  [[ "$(opt_bool dashboard)" == true ]] && check_http Dashboard http://127.0.0.1:${DASHBOARD_HOST_PORT}/ hermes-agent
  [[ "$(opt_bool matrix)" == true ]] && check_http Matrix http://127.0.0.1:${MATRIX_HOST_PORT}/health hermes-synapse
  [[ "$(opt_bool searxng)" == true ]] && check_http SearXNG http://127.0.0.1:${SEARXNG_HOST_PORT}/ hermes-searxng
  [[ "$(opt_bool qmd)" == true ]] && check_qmd
  if managed_ollama_enabled; then
    if docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null | grep -qx healthy; then
      printf '%-12s OK (%s)\n' Ollama "$(opt_text localTextModel)"
    elif container_is_starting hermes-ollama; then
      printf '%-12s STARTING\n' Ollama
    elif container_stopped_cleanly hermes-ollama; then
      printf '%-12s STOPPED\n' Ollama
    else
      printf '%-12s FAILED\n' Ollama
    fi
  elif windows_native_ollama_enabled; then
    native_base="$(native_ollama_base_url 2>/dev/null || true)"
    if [[ -n "$native_base" ]] && curl -fsS --connect-timeout 2 --max-time 5 "$native_base/api/version" >/dev/null 2>&1; then
      printf '%-12s OK (%s; native Windows)\n' Ollama "$(opt_text localTextModel)"
    else
      printf '%-12s FAILED (native Windows relay/API unavailable)\n' Ollama
    fi
  fi
  [[ "$(opt_bool honcho)" == true ]] && check_http Honcho http://127.0.0.1:${HONCHO_HOST_PORT}/health hermes-honcho-api
  if [[ "$(opt_bool tailscale)" == true ]]; then
    if [[ -s .tailscale-info ]]; then
      printf '%-12s %s\n' Tailscale 'Windows-host Serve configured'
    else
      printf '%-12s %s\n' Tailscale 'Windows-host integration selected; no active installer-owned Serve mapping recorded'
    fi
  fi
  show_pin_summary
  show_hardware_summary
  show_memory_pressure_summary
  echo
  docker exec -u hermes hermes-agent hermes profile list || true
  if [[ "$(opt_bool kanban)" == true ]]; then echo; docker exec -u hermes hermes-agent hermes kanban list || true; fi
}

verify() {
  local timeout="${1:-300}" deadline overall
  [[ "$timeout" =~ ^[0-9]+$ && "$timeout" -ge 1 && "$timeout" -le 1800 ]] || { echo 'verify timeout must be 1-1800 seconds.' >&2; return 2; }
  docker_ready || { echo 'Docker daemon is not running. Start the stack first with ./manage.sh start.' >&2; return 2; }
  deadline=$(( $(date +%s) + timeout ))
  while :; do
    overall="$(python3 ./state-audit.py --stack . --json | jq -r '.overall // "UNKNOWN"')"
    case "$overall" in
      HEALTHY)
        followup="$(python3 ./state-audit.py --stack . --json | jq -r '.windowsFollowup | length')"
        if [[ "$followup" =~ ^[0-9]+$ && "$followup" -gt 0 ]]; then
          echo 'LatticeVale verification: HEALTHY (optional Windows follow-up remains)'
          python3 ./state-audit.py --stack .
          echo
          echo 'Core LatticeVale/WSL services are healthy. Windows-only PARTIAL hints do not require Linux stack repair.'
          echo 'Rerun the Windows installer only if you want it to reconcile Tailscale, Windows apps, or auto-start.'
        else
          echo 'LatticeVale verification: HEALTHY'
        fi
        status
        return 0
        ;;
      NEEDS_REPAIR)
        python3 ./state-audit.py --stack .
        echo
        echo 'The stack has a confirmed repair condition. Rerun the Windows installer and choose Resume / repair.' >&2
        return 2
        ;;
      STOPPED)
        python3 ./state-audit.py --stack .
        echo
        echo 'The stack is configured but stopped. Start it with ./manage.sh start; repair is not required merely because services are stopped.' >&2
        return 4
        ;;
      STARTING)
        if (( $(date +%s) >= deadline )); then
          echo "Timed out after ${timeout}s while services were still starting." >&2
          python3 ./state-audit.py --stack .
          docker compose ps
          return 3
        fi
        echo 'Selected services are still starting; waiting...' >&2
        sleep 5
        ;;
      *)
        python3 ./state-audit.py --stack .
        echo "Unexpected audit state: $overall" >&2
        return 2
        ;;
    esac
  done
}

selected_matrix_profile_names() {
  [[ "$(opt_bool matrix)" == true ]] || return 0
  jq -r '.workers[]? | select(.matrix.enabled == true) | .name' install-options.json 2>/dev/null || return 1
  return 0
}

profile_gateway_s6_state_exact() {
  local name="$1" service out
  service="/run/service/gateway-$name"
  if ! out="$(timeout --foreground --kill-after=5s 15s docker exec hermes-agent sh -c '
svc="$1"
if [ ! -d "$svc" ]; then
  printf "absent\\n"
  exit 0
fi
exec /command/s6-svstat "$svc"
' sh "$service" 2>/dev/null)"; then
    printf 'unknown\n'
    return 1
  fi
  case "$out" in
    up\ *) printf 'up\n' ;;
    down\ *) printf 'down\n' ;;
    absent) printf 'absent\n' ;;
    *) printf 'unknown\n'; return 1 ;;
  esac
}

wait_profile_gateway_up_exact() {
  local name="$1" wait_seconds="${2:-60}" i state consecutive_up=0 observed_state=false
  [[ "$wait_seconds" =~ ^[0-9]+$ && "$wait_seconds" -ge 1 ]] || wait_seconds=60
  for i in $(seq 1 "$wait_seconds"); do
    if state="$(profile_gateway_s6_state_exact "$name" 2>/dev/null)"; then
      observed_state=true
      if [[ "$state" == up ]]; then
        consecutive_up=$((consecutive_up+1))
        (( consecutive_up >= 2 )) && return 0
      else
        consecutive_up=0
      fi
    else
      consecutive_up=0
    fi
    sleep 1
  done
  [[ "$observed_state" == true ]] || return 2
  return 1
}

profile_gateway_log_tail_exact_manage() {
  local name="$1"
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent sh -c '
name="$1"
log="/opt/data/logs/gateways/$name/current"
if [ -f "$log" ]; then
  printf '%s\n' "--- exact Hermes gateway log: $name ---"
  tail -n 120 "$log"
else
  printf "No rotated gateway log exists yet for profile %s at %s\n" "$name" "$log"
fi
' sh "$name" >&2 || true
}

start_profile_gateway_exact_manage() {
  local name="$1" state service
  service="/run/service/gateway-$name"
  state="$(profile_gateway_s6_state_exact "$name" 2>/dev/null || true)"
  case "$state" in
    up) return 0 ;;
    down) ;;
    absent)
      echo "Profile '$name' has no exact s6 gateway service slot; preserving its Matrix state and refusing a profile-blind start." >&2
      profile_gateway_log_tail_exact_manage "$name"
      return 1
      ;;
    *)
      echo "Could not determine the exact s6 gateway state for profile '$name'." >&2
      return 1
      ;;
  esac

  if timeout --foreground --kill-after=5s 60s docker exec -u hermes hermes-agent hermes -p "$name" gateway start >/dev/null; then
    wait_profile_gateway_up_exact "$name" 60 && return 0
    echo "WARNING: Hermes named-profile gateway start returned before '$name' became stably ready; retrying only its exact s6 service slot." >&2
  else
    echo "WARNING: Hermes named-profile gateway start failed for '$name'; retrying only its exact s6 service slot." >&2
  fi

  # -U both requests the exact service up and removes a stale ./down marker that may
  # have been left by a prior profile-scoped stop. This is intentionally narrower
  # than restarting the container/default gateway or searching/killing by process name.
  if ! timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "$service" >/dev/null 2>&1; then
    echo "Exact s6 gateway start fallback failed for profile '$name'." >&2
    profile_gateway_log_tail_exact_manage "$name"
    return 1
  fi
  if ! wait_profile_gateway_up_exact "$name" 60; then
    echo "Profile '$name' exact s6 gateway service did not become stably running after bounded fallback activation." >&2
    profile_gateway_log_tail_exact_manage "$name"
    return 1
  fi
  return 0
}

reconcile_default_gateway_manage() {
  local state action service lifecycle_ok=false
  service="/run/service/gateway-default"
  state="$(profile_gateway_s6_state_exact default 2>/dev/null || true)"
  case "$state" in
    up) action=restart ;;
    down) action=start ;;
    absent)
      echo 'Default gateway has no exact s6 service slot; Matrix runtime cannot be reconciled safely.' >&2
      profile_gateway_log_tail_exact_manage default
      return 1
      ;;
    *)
      echo 'Could not determine the exact default gateway s6 state.' >&2
      return 1
      ;;
  esac

  if timeout --foreground --kill-after=5s 60s docker exec -u hermes hermes-agent hermes gateway "$action" >/dev/null 2>&1; then
    lifecycle_ok=true
    wait_profile_gateway_up_exact default 60 && return 0
    echo "WARNING: Hermes default gateway $action returned before its exact s6 service became stably ready; reasserting only that service slot." >&2
    timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "$service" >/dev/null 2>&1 || true
  else
    echo "WARNING: Hermes default gateway $action failed; retrying only its exact s6 service slot." >&2
    if [[ "$action" == start ]]; then
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "$service" >/dev/null 2>&1 || return 1
    else
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -r "$service" >/dev/null 2>&1 || return 1
    fi
  fi

  wait_profile_gateway_up_exact default 60 || {
    profile_gateway_log_tail_exact_manage default
    return 1
  }
}

reconcile_profile_gateway_exact_manage() {
  local name="$1" state action service
  service="/run/service/gateway-$name"
  state="$(profile_gateway_s6_state_exact "$name" 2>/dev/null || true)"
  case "$state" in
    up) action=restart ;;
    down) action=start ;;
    absent)
      echo "Profile '$name' has no exact s6 gateway service slot; preserving its Matrix state." >&2
      profile_gateway_log_tail_exact_manage "$name"
      return 1
      ;;
    *)
      echo "Could not determine the exact s6 gateway state for profile '$name'." >&2
      return 1
      ;;
  esac

  if timeout --foreground --kill-after=5s 60s docker exec -u hermes hermes-agent hermes -p "$name" gateway "$action" >/dev/null 2>&1; then
    wait_profile_gateway_up_exact "$name" 60 && return 0
    echo "WARNING: Hermes profile '$name' gateway $action returned before its exact s6 service became stably ready; reasserting only that service slot." >&2
    timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "$service" >/dev/null 2>&1 || true
  else
    echo "WARNING: Hermes profile '$name' gateway $action failed; retrying only its exact s6 service slot." >&2
    if [[ "$action" == start ]]; then
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "$service" >/dev/null 2>&1 || return 1
    else
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -r "$service" >/dev/null 2>&1 || return 1
    fi
  fi

  wait_profile_gateway_up_exact "$name" 60 || {
    profile_gateway_log_tail_exact_manage "$name"
    return 1
  }
}

stop_profile_gateway_exact_manage() {
  local name="$1" state
  timeout --foreground --kill-after=5s 30s docker exec -u hermes hermes-agent hermes -p "$name" gateway stop >/dev/null 2>&1 || true
  sleep 1
  state="$(profile_gateway_s6_state_exact "$name" 2>/dev/null || true)"
  if [[ "$state" == up ]]; then
    timeout --foreground --kill-after=5s 15s docker exec hermes-agent /command/s6-svc -d "/run/service/gateway-$name" >/dev/null 2>&1 || true
  fi
}

refresh_matrix_profile_handoff() {
  local f profile status user room version
  cat > MATRIX-SECONDARY-PROFILES.txt <<'EOF_MATRIX_HANDOFF_MANAGE'
LatticeVale secondary Matrix profiles

This file contains no passwords, access tokens, or recovery keys.
LatticeVale provisions the Matrix account, encrypted room, invite, and protected credentials.
A pending-manual profile is incomplete activation state. LatticeVale repair/start paths retry it without replacing its protected Matrix identity or room.
EOF_MATRIX_HANDOFF_MANAGE
  if [[ -d .matrix-profiles ]]; then
    while IFS= read -r f; do
      [[ -s "$f" ]] || continue
      profile="$(sed -n 's/^HERMES_PROFILE=//p' "$f" | head -n1)"
      status="$(sed -n 's/^MATRIX_SETUP_STATUS=//p' "$f" | head -n1)"
      user="$(sed -n 's/^MATRIX_USER_ID=//p' "$f" | head -n1)"
      room="$(sed -n 's/^MATRIX_ROOM=//p' "$f" | head -n1)"
      version="$(sed -n 's/^MATRIX_ROOM_VERSION=//p' "$f" | head -n1)"
      cat >> MATRIX-SECONDARY-PROFILES.txt <<EOF_MATRIX_HANDOFF_MANAGE_PROFILE

Profile: $profile
Status: ${status:-unknown}
Matrix user: $user
Room ID: $room
Room version: $version
Encryption: required
EOF_MATRIX_HANDOFF_MANAGE_PROFILE
      if [[ "$status" == pending-manual ]]; then
        echo "Recovery command: ./manage.sh matrix-profile-finish $profile" >> MATRIX-SECONDARY-PROFILES.txt
      fi
    done < <(find .matrix-profiles -maxdepth 1 -type f -name '*.info' -print 2>/dev/null | sort)
  fi
  chmod 0644 MATRIX-SECONDARY-PROFILES.txt
}

matrix_client_api_ready_manage() {
  curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:${MATRIX_HOST_PORT}/health" >/dev/null 2>&1 &&
  curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/versions" >/dev/null 2>&1
}

wait_hermes_cli_manage() {
  local i
  for i in $(seq 1 60); do
    if timeout --foreground --kill-after=5s 15s docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo 'Hermes container did not become CLI-ready.' >&2
  return 1
}


http_status_ok_manage() {
  local url="$1" code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || true)"
  [[ "$code" =~ ^(2|3|401|403) ]]
}

wait_hermes_gateway_surfaces_manage() {
  local context="${1:-gateway lifecycle}" i api_ok dashboard_ok
  for i in $(seq 1 60); do
    api_ok=false
    dashboard_ok=true
    if timeout --foreground --kill-after=5s 15s docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1 && \
       http_status_ok_manage "http://127.0.0.1:${HERMES_API_HOST_PORT}/health"; then
      api_ok=true
    fi
    if [[ "$(opt_bool dashboard)" == true ]] && ! http_status_ok_manage "http://127.0.0.1:${DASHBOARD_HOST_PORT}/"; then
      dashboard_ok=false
    fi
    [[ "$api_ok" == true && "$dashboard_ok" == true ]] && return 0
    sleep 2
  done
  echo "Hermes API/Dashboard did not recover after ${context}." >&2
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent /command/s6-svstat /run/service/gateway-default 2>&1 >&2 || true
  timeout --foreground --kill-after=5s 15s docker logs --tail 120 hermes-agent 2>&1 | tail -n 120 >&2 || true
  return 1
}

matrix_backend_ready_from_hermes_manage() {
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent python3 -c '
import http.client, socket
socket.getaddrinfo("synapse", 8008)
c=http.client.HTTPConnection("synapse", 8008, timeout=5)
c.request("GET", "/_matrix/client/versions")
r=c.getresponse()
raise SystemExit(0 if 200 <= int(r.status) < 400 else 1)
' >/dev/null 2>&1
}

wait_matrix_backend_from_hermes_manage() {
  local i
  for i in $(seq 1 60); do
    matrix_backend_ready_from_hermes_manage && return 0
    sleep 2
  done
  echo 'Matrix is healthy on the WSL host but is not reachable as synapse:8008 from inside hermes-agent; refusing to leave Matrix gateways in a false-running state.' >&2
  return 1
}

ensure_matrix_server_online_manage() {
  local i
  docker compose up -d --pull never --no-build synapse-db synapse >/dev/null
  for i in $(seq 1 60); do
    matrix_client_api_ready_manage && return 0
    sleep 2
  done
  echo 'Matrix Client-Server API did not become ready.' >&2
  return 1
}

ensure_matrix_runtime_online_manage() {
  ensure_matrix_server_online_manage
  docker compose up -d --pull never --no-build --no-deps hermes >/dev/null
  wait_hermes_cli_manage
  wait_matrix_backend_from_hermes_manage
}

finish_matrix_profile() {
  local name="$1" secret info pdir penv state token user_id room_id live_user joined host_once recovery i setup_status
  [[ "$name" =~ ^[a-z0-9][a-z0-9_-]{0,31}$ ]] || { echo 'Profile name is invalid.' >&2; return 2; }
  [[ "$(opt_bool matrix)" == true ]] || { echo 'Matrix is not selected for this stack.' >&2; return 2; }
  secret="secrets/matrix-profiles/$name.env"; info=".matrix-profiles/$name.info"; pdir="data/hermes/profiles/$name"; penv="$pdir/.env"
  [[ -s "$secret" && -s "$info" && -s "$penv" ]] || { echo "Profile '$name' has not been provisioned by LatticeVale. Run Resume / repair first." >&2; return 2; }
  state="$(sed -n 's/^LATTICEVALE_PROVISIONING_STATE=//p' "$secret" | head -n1)"
  [[ -n "$state" ]] || state="$(sed -n 's/^FOUNDRY_PROVISIONING_STATE=//p' "$secret" | head -n1)"
  if [[ "$state" == complete ]]; then
    echo "Matrix profile '$name' is already marked complete."
    return 0
  fi
  [[ "$state" == pending-manual ]] || { echo "Profile '$name' is in state '$state', not pending-manual. Run Resume / repair." >&2; return 2; }
  token="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' "$secret" | head -n1)"
  user_id="$(sed -n 's/^MATRIX_USER_ID=//p' "$secret" | head -n1)"
  room_id="$(sed -n 's/^MATRIX_ALLOWED_ROOMS=//p' "$secret" | head -n1)"
  [[ -n "$token" && "$user_id" == @*:* && "$room_id" == !*:* ]] || { echo "Profile '$name' protected Matrix record is incomplete. Run Resume / repair." >&2; return 2; }
  ensure_matrix_runtime_online_manage
  live_user="$(curl -fsS --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/account/whoami" | jq -r '.user_id // empty')" || true
  [[ "$live_user" == "$user_id" ]] || { echo "Matrix token for profile '$name' no longer authenticates as '$user_id'. No credentials were replaced." >&2; return 1; }
  start_profile_gateway_exact_manage "$name" || { echo "Profile '$name' exact gateway service could not be activated; protected Matrix state remains pending-manual." >&2; return 1; }
  echo "Waiting for '$name' to accept its existing Matrix invitation..."
  joined=false
  for i in $(seq 1 60); do
    if ! matrix_client_api_ready_manage; then
      stop_profile_gateway_exact_manage "$name"
      echo 'Matrix became unavailable while finishing the profile; the exact profile gateway was stopped and state remains pending-manual.' >&2
      return 1
    fi
    joined="$(curl -fsS --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/joined_rooms" 2>/dev/null | jq -r --arg r "$room_id" '.joined_rooms | index($r) != null' || true)"
    [[ "$joined" == true ]] && break
    sleep 2
  done
  if [[ "$joined" != true ]]; then
    stop_profile_gateway_exact_manage "$name"
    echo "Profile '$name' did not join room '$room_id'. The exact profile gateway was stopped; state remains pending-manual." >&2
    return 1
  fi

  recovery="$(sed -n 's/^MATRIX_RECOVERY_KEY=//p' "$secret" | head -n1)"
  host_once="$pdir/matrix-recovery-key.once"
  if [[ -z "$recovery" ]]; then
    echo "Waiting briefly for '$name' Matrix E2EE recovery key..."
    for i in $(seq 1 60); do
      [[ -s "$host_once" ]] && break
      sleep 2
    done
    if [[ -s "$host_once" ]]; then
      recovery="$(tr -d '\r\n' < "$host_once")"
      if [[ -n "$recovery" ]]; then
        set_env_value "$secret" MATRIX_RECOVERY_KEY "$recovery"
        set_env_value "$penv" MATRIX_RECOVERY_KEY "$recovery"
        remove_env_value "$secret" MATRIX_RECOVERY_KEY_OUTPUT_FILE
        remove_env_value "$penv" MATRIX_RECOVERY_KEY_OUTPUT_FILE
        rm -f "$host_once"
      fi
    fi
  fi
  if [[ -z "$recovery" ]]; then
    stop_profile_gateway_exact_manage "$name"
    echo "Profile '$name' joined successfully, but no recovery key was emitted yet. The exact profile gateway was stopped and state remains pending-manual so a later retry can finish E2EE persistence safely." >&2
    return 1
  fi
  set_env_value "$secret" LATTICEVALE_PROVISIONING_STATE complete
  set_env_value "$info" MATRIX_SETUP_STATUS complete
  set_env_value "$secret" LATTICEVALE_CROSS_SIGNING_STATE complete
  set_env_value "$info" MATRIX_CROSS_SIGNING_STATUS complete
  chmod 0600 "$secret" "$info" "$penv"
  refresh_matrix_profile_handoff
  echo "Matrix profile '$name' is complete: $user_id -> $room_id"
  return 0
}

start_selected_matrix_profile_gateways() {
  [[ "$(opt_bool matrix)" == true ]] || return 0
  local name info secret state
  local -a names=()

  # A running s6 gateway process is not sufficient evidence of Matrix connectivity.
  # After stack start/restart the gateway can race Docker DNS/Synapse, remain alive,
  # and never reconnect. Require host + in-container Matrix reachability first, then
  # recycle the default and selected profile gateways against the proven backend.
  ensure_matrix_runtime_online_manage
  reconcile_default_gateway_manage

  mapfile -t names < <(selected_matrix_profile_names)
  ((${#names[@]})) || return 0

  for name in "${names[@]}"; do
    [[ "$name" =~ ^[a-z0-9][a-z0-9_-]{0,31}$ ]] || {
      echo "Invalid installer-managed profile name in install-options.json: $name" >&2
      return 1
    }
    info=".matrix-profiles/$name.info"
    secret="secrets/matrix-profiles/$name.env"
    if [[ ! -s "$info" || ! -s "$secret" ]]; then
      echo "Matrix-enabled profile '$name' is not fully provisioned. Rerun the Windows installer and choose Resume / repair." >&2
      return 1
    fi
    state="$(sed -n 's/^LATTICEVALE_PROVISIONING_STATE=//p' "$secret" | head -n1)"
    [[ -n "$state" ]] || state="$(sed -n 's/^FOUNDRY_PROVISIONING_STATE=//p' "$secret" | head -n1)"
    if [[ "$state" == pending-manual ]]; then
      echo "Matrix profile '$name' activation is incomplete; retrying the existing room/identity now."
      if finish_matrix_profile "$name"; then
        state=complete
      else
        echo "WARNING: Matrix profile '$name' remains pending; leaving only that profile gateway stopped and continuing core stack startup." >&2
        continue
      fi
    fi
    if [[ -n "$state" && "$state" != complete ]]; then
      echo "Matrix-enabled profile '$name' has incomplete provisioning state '$state'. Rerun Resume / repair." >&2
      return 1
    fi
    if ! reconcile_profile_gateway_exact_manage "$name"; then
      echo "WARNING: Matrix-enabled profile '$name' gateway remains unavailable; preserving that profile and continuing core stack startup. Resume / repair will retry it." >&2
      continue
    fi
    echo "Profile gateway running with Matrix backend verified: $name"
  done
  return 0
}

refresh_adaptive_resource_policy() {
  RESOURCE_POLICY_CHANGED=false
  [[ "$(opt_bool containerResourceLimits)" == true ]] || return 0
  local before after
  before="$(sha256sum .latticevale-resource-state 2>/dev/null | awk '{print $1}' || true)"
  timeout --foreground --kill-after=10s 90s ./configure-stack.sh --refresh-resource-policy || return 1
  after="$(sha256sum .latticevale-resource-state 2>/dev/null | awk '{print $1}' || true)"
  if [[ "$before" != "$after" ]]; then
    echo 'Adaptive resource fingerprint changed (hardware, topology, model artifacts/context, or policy revision); Compose reconciliation will apply the new ceilings.'
    RESOURCE_POLICY_CHANGED=true
  fi
}

backup() {
  local stamp target matrix_dumped=false honcho_dumped=false
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"; target="$PWD/backups/$stamp"; install -d -m 0700 "$target"
  if [[ "$(opt_bool matrix)" == true ]] && docker compose ps --status running synapse-db | grep -q synapse-db; then
    docker compose exec -T synapse-db pg_dump -U synapse -d synapse -Fc > "$target/synapse.dump"
    matrix_dumped=true
  fi
  if [[ "$(opt_bool honcho)" == true ]] && docker compose ps --status running honcho-db | grep -q honcho-db; then
    docker compose exec -T honcho-db pg_dump -U honcho -d honcho -Fc > "$target/honcho.dump"
    honcho_dumped=true
  fi
  local -a items=()
  for p in .env install-options.json .installer-state.json state-audit.py .install-info .configured .provider-configured .installer-managed-profiles .matrix-configured .matrix-info .matrix-profiles .tailscale-info .windows-native-info \
    compose.yaml config secrets logs data/hermes data/qmd data/synapse data/tailscale data/tailscale-matrix data/searxng-valkey data/honcho-redis data/ollama vault workspace; do
    [[ -e "$p" ]] && items+=("$p")
  done
  [[ "$matrix_dumped" == false && -e data/synapse-db ]] && items+=(data/synapse-db)
  [[ "$honcho_dumped" == false && -e data/honcho-db ]] && items+=(data/honcho-db)
  ((${#items[@]})) && tar -czf "$target/files.tar.gz" "${items[@]}"
  chmod -R go-rwx "$target"
  echo "Backup created: $target"
  echo 'Security note: this backup may contain API keys, Matrix credentials, profile configuration, and other sensitive state. Store it securely and consider encrypting it before copying it to cloud storage or another system.'
}

cmd="${1:-status}"
# matrix-profile-finish is an installer recovery primitive as well as a post-install
# management command. configure-stack.sh invokes it before the final .configured marker
# exists, so gating it behind need_configured makes clean install/Resume repair call a
# command that manage.sh itself refuses. Keep every other management command behind the
# completed-stack guard, but permit this one narrowly after its installer-owned inputs
# exist; finish_matrix_profile performs the remaining identity/token/room safety checks.
if [[ "$cmd" == matrix-profile-finish ]]; then
  [[ -n "${2:-}" ]] || { echo 'Usage: ./manage.sh matrix-profile-finish PROFILE' >&2; exit 2; }
  [[ -s install-options.json && -s compose.yaml && -s .env ]] || {
    echo 'Matrix profile recovery is not staged far enough to run safely. Rerun the Windows installer and choose Resume / repair.' >&2
    exit 1
  }
  ensure_docker_for_user
  finish_matrix_profile "$2"
  exit $?
fi

need_configured
case "$cmd" in
  status) status ;;
  verify) verify "${2:-300}" ;;
  audit) python3 ./state-audit.py --stack . ;;
  audit-free) python3 ./audit-free.py --stack . "${@:2}" ;;
  plan) python3 ./repair-plan.py --stack . "${@:2}" ;;
  repair)
    if [[ "${2:-}" == --plan ]]; then
      python3 ./repair-plan.py --stack . "${@:3}"
    else
      echo 'Repair application remains owned by the Windows installer. Use: ./manage.sh repair --plan' >&2
      echo 'Then rerun Install-LatticeVale.ps1 and choose Resume / repair to apply verified changes.' >&2
      exit 2
    fi ;;
  repair-info)
    echo 'Rerun Install-LatticeVale.ps1 from the Windows bundle.'
    echo 'Resume / repair preserves completed work and reruns failed/incomplete/stale stages; it refreshes installer-owned components when the periodic gate is due or the managed-refresh policy revision changes. A bundle-version change alone stays local-first.'
    echo "Choose Update / repair installer-managed software when you want to force the current bundle's declared component versions/channels immediately, including after a version-only bundle change that does not advance the managed-refresh policy revision."
    echo './manage.sh update is a separate advanced upstream-refresh command: it pulls the currently configured image refs and may advance Honcho to repository HEAD, so it is not equivalent to the tested bundle updater.' ;;
  start)
    ensure_docker_for_user
    refresh_adaptive_resource_policy
    control_windows_native_services start
    if [[ "$(opt_bool matrix)" == true ]]; then ensure_matrix_server_online_manage; fi
    docker compose up -d --pull never --no-build
    start_selected_matrix_profile_gateways
    wait_hermes_gateway_surfaces_manage 'stack start/gateway reconciliation'
    control_windows_bridge start
    status
    ;;
  stop) docker compose stop; control_windows_bridge stop; control_windows_native_services stop ;;
  logs)
    if [[ -n "${2:-}" ]]; then docker compose logs --tail=200 -f "$2"; else docker compose logs --tail=100 -f; fi ;;
  restart)
    refresh_adaptive_resource_policy
    control_windows_native_services start
    if [[ "${RESOURCE_POLICY_CHANGED:-false}" == true ]]; then
      echo 'Adaptive resource policy changed; reconciling Compose before restart so new memory/environment/command settings become live.'
      docker compose up -d --pull never --no-build
    fi
    if [[ -n "${2:-}" ]]; then docker compose restart "$2"; else docker compose restart; fi
    if [[ -z "${2:-}" || "${2:-}" == hermes || "${2:-}" == synapse || "${2:-}" == synapse-db ]]; then
      start_selected_matrix_profile_gateways
      wait_hermes_gateway_surfaces_manage 'stack restart/gateway reconciliation'
    fi
    control_windows_bridge start ;;
  chat)
    profile="${2:-default}"
    if [[ "$profile" == default ]]; then docker exec -it -u hermes hermes-agent hermes chat
    else docker exec -it -u hermes hermes-agent hermes -p "$profile" chat; fi ;;
  profiles) docker exec -u hermes hermes-agent hermes profile list ;;
  kanban)
    [[ "$(opt_bool kanban)" == true ]] || { echo 'Kanban was not selected. Rerun the Windows installer to enable it.' >&2; exit 2; }
    docker exec -u hermes hermes-agent hermes kanban list ;;
  reindex)
    [[ "$(opt_bool qmd)" == true ]] || { echo 'QMD was not selected.' >&2; exit 2; }
    docker compose exec qmd qmd update -c obsidian
    docker compose exec qmd qmd embed -c obsidian ;;
  backup) backup ;;
  update)
    backup
    timeout --foreground --kill-after=5s 60s docker compose config --quiet
    mapfile -t update_services < <(selected_service_names)
    if ((${#update_services[@]})); then
      timeout --foreground --kill-after=15s 3600s docker compose pull --ignore-buildable "${update_services[@]}"
    fi
    [[ "$(opt_bool qmd)" == true ]] && timeout --foreground --kill-after=15s 3600s docker compose build --pull qmd
    if [[ "$(opt_bool honcho)" == true ]]; then
      # Honcho currently has no reliable GitHub Releases feed. An explicit update is
      # permission to advance to the repository's current default-branch commit.
      timeout --foreground --kill-after=10s 600s git -C vendor/honcho fetch --depth 1 origin HEAD
      git -C vendor/honcho checkout --force --detach FETCH_HEAD
      timeout --foreground --kill-after=15s 3600s docker compose build --pull honcho-api
    fi
    refresh_adaptive_resource_policy
    control_windows_native_services start
    if [[ "$(opt_bool matrix)" == true ]]; then ensure_matrix_server_online_manage; fi
    timeout --foreground --kill-after=10s 300s docker compose up -d --pull never --no-build --remove-orphans
    start_selected_matrix_profile_gateways
    wait_hermes_gateway_surfaces_manage 'stack update/gateway reconciliation'
    if local_ai_enabled; then
      if managed_ollama_enabled; then
        for _ in $(seq 1 60); do timeout --foreground --kill-after=5s 15s docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null | grep -qx healthy && break; sleep 2; done
      fi
      pull_ollama_model "$(opt_text localTextModel)"
      if [[ "$(opt_bool honcho)" == true ]]; then pull_ollama_model "$(opt_text localEmbeddingModel)"; fi
    fi
    status ;;
  dashboard-info)
    if [[ "$(opt_bool dashboard)" == true ]]; then
      echo "Dashboard: http://localhost:${DASHBOARD_HOST_PORT}"
      user="$(sed -n 's/^HERMES_DASHBOARD_BASIC_AUTH_USERNAME=//p' secrets/hermes-runtime.env | head -n1)"
      [[ -n "$user" ]] && echo "Username: $user"
      echo 'The plaintext password is not stored; only its scrypt hash is kept. Rerun the Windows installer to replace forgotten credentials.'
      if [[ "$(opt_bool tailscaleDashboard)" == true && -s .tailscale-info ]]; then
        dns="$(sed -n 's/^TAILSCALE_DNS=//p' .tailscale-info | head -n1)"
        port="$(sed -n 's/^DASHBOARD_HTTPS_PORT=//p' .tailscale-info | head -n1)"
        [[ -n "$dns" && "$port" =~ ^[0-9]+$ && "$port" -gt 0 ]] && echo "Tailscale: https://$dns:$port"
      fi
    else echo 'Dashboard was not selected.'; fi ;;
  matrix-info)
    if [[ "$(opt_bool matrix)" == true && -f .matrix-info ]]; then
      cat .matrix-info
      if [[ -s secrets/matrix-bot.env ]]; then
        homeserver="$(sed -n 's/^MATRIX_HOMESERVER=//p' secrets/matrix-bot.env | head -n1)"
        user_id="$(sed -n 's/^MATRIX_USER_ID=//p' secrets/matrix-bot.env | head -n1)"
        [[ -n "$homeserver" ]] && echo "MATRIX_HOMESERVER=$homeserver"
        [[ -n "$user_id" ]] && echo "MATRIX_USER_ID=$user_id"
      fi
      if [[ -d .matrix-profiles ]]; then
        first_profile=true
        while IFS= read -r profile_info; do
          [[ -n "$profile_info" && -s "$profile_info" ]] || continue
          if [[ "$first_profile" == true ]]; then
            echo
            echo 'Profile-specific Matrix rooms:'
            first_profile=false
          fi
          echo "--- $(basename "$profile_info" .info) ---"
          cat "$profile_info"
        done < <(find .matrix-profiles -maxdepth 1 -type f -name '*.info' -print 2>/dev/null | sort)
      fi
      if [[ "$(opt_bool tailscaleMatrix)" == true && -s .tailscale-info ]]; then
        dns="$(sed -n 's/^TAILSCALE_DNS=//p' .tailscale-info | head -n1)"
        port="$(sed -n 's/^MATRIX_HTTPS_PORT=//p' .tailscale-info | head -n1)"
        if [[ -n "$dns" && "$port" =~ ^[0-9]+$ && "$port" -gt 0 ]]; then
          if [[ "$port" == 443 ]]; then echo "MATRIX_TAILSCALE=https://$dns"; else echo "MATRIX_TAILSCALE=https://$dns:$port"; fi
        fi
      fi
    else echo 'Matrix was not selected or has not completed setup.'; fi ;;
  matrix-credentials)
    matrix_profile="${2:-default}"
    if [[ "$matrix_profile" == default ]]; then
      matrix_secret='secrets/matrix-bot.env'
    elif [[ "$matrix_profile" =~ ^[a-z0-9][a-z0-9_-]{0,31}$ ]]; then
      matrix_secret="secrets/matrix-profiles/$matrix_profile.env"
    else
      echo 'Profile must be default or a valid Hermes profile name.' >&2; exit 2
    fi
    if [[ "$(opt_bool matrix)" == true && -s "$matrix_secret" ]]; then
      echo "WARNING: the following values authenticate Matrix profile '$matrix_profile'. Do not post or commit them." >&2
      homeserver="$(sed -n 's/^MATRIX_HOMESERVER=//p' "$matrix_secret" | head -n1)"
      user_id="$(sed -n 's/^MATRIX_USER_ID=//p' "$matrix_secret" | head -n1)"
      token="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' "$matrix_secret" | head -n1)"
      password="$(sed -n 's/^MATRIX_BOT_PASSWORD=//p' "$matrix_secret" | head -n1)"
      recovery="$(sed -n 's/^MATRIX_RECOVERY_KEY=//p' "$matrix_secret" | head -n1)"
      echo "HERMES_PROFILE=$matrix_profile"
      echo "MATRIX_HOMESERVER=${homeserver:-http://synapse:8008}"
      echo "MATRIX_USER_ID=${user_id:-unknown}"
      echo "MATRIX_ACCESS_TOKEN=${token:-not-retained}"
      if [[ -n "$password" ]]; then
        echo "MATRIX_BOT_PASSWORD=$password"
      else
        echo 'MATRIX_BOT_PASSWORD=not-retained-by-older-installer-release'
        echo 'The existing access token remains the preferred Hermes authentication method.' >&2
      fi
      if [[ -n "$recovery" ]]; then echo "MATRIX_RECOVERY_KEY=$recovery"; else echo 'MATRIX_RECOVERY_KEY=not-retained'; fi
    else echo "Matrix credentials for profile '$matrix_profile' are not installer-managed or have not completed setup."; fi ;;
  help|-h|--help) usage ;;
  *) usage >&2; exit 2 ;;
esac
