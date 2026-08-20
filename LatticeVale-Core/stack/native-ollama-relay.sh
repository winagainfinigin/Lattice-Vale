#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

info_file=.windows-native-info
pid_file=.native-ollama-relay.pid
supervisor_pid_file=.native-ollama-relay-supervisor.pid
state_file=.native-ollama-relay.state
disabled_file=.native-ollama-relay.disabled
lock_file=.native-ollama-relay.lock
log_file=logs/native-ollama-relay.log
relay_py=./native-ollama-relay.py
service_name=latticevale-native-ollama-relay.service
refresh_seconds=15
max_connections=64
connect_timeout=5
idle_timeout=300

field() {
  local key="$1" default="${2:-}" value=''
  if [[ -r "$info_file" ]]; then
    value="$(sed -n "s/^${key}=//p" "$info_file" | head -n1 | tr -d '\r')"
  fi
  [[ -n "$value" ]] && printf '%s' "$value" || printf '%s' "$default"
}

transport() { field TRANSPORT windows-gateway-relay; }
bridge_port() { field BRIDGE_PORT 11435; }
target_address() { field TARGET_ADDRESS 127.0.0.1; }
target_port() { field TARGET_PORT 11434; }
host_address() { field HOST_ADDRESS ''; }

log_msg() {
  mkdir -p logs
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$log_file"
}

windows_host_gateway_ip() {
  local line token candidate=''
  while IFS= read -r line; do
    set -- $line
    while [[ $# -gt 0 ]]; do
      token="$1"; shift
      if [[ "$token" == via && $# -gt 0 ]]; then candidate="$1"; break 2; fi
    done
  done < <(ip -4 route show default 2>/dev/null || true)
  if [[ ! "$candidate" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then candidate="$(host_address)"; fi
  [[ "$candidate" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  case "$candidate" in 127.*|169.254.*|0.0.0.0) return 1;; esac
  printf '%s' "$candidate"
}

docker_host_gateway_ip() {
  local ip
  ip="$(docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null | head -n1 | tr -d '\r' || true)"
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  case "$ip" in 127.*|169.254.*|0.0.0.0) return 1;; esac
  printf '%s' "$ip"
}

owned_worker_pid() {
  [[ -s "$pid_file" ]] || return 1
  local pid cmdline
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$PWD/native-ollama-relay.py"* ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  printf '%s' "$pid"
}

owned_supervisor_pid() {
  [[ -s "$supervisor_pid_file" ]] || return 1
  local pid cmdline
  pid="$(cat "$supervisor_pid_file" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"native-ollama-relay.sh"* && "$cmdline" == *"supervise"* ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  printf '%s' "$pid"
}

stop_worker() {
  local pid=''
  if pid="$(owned_worker_pid 2>/dev/null)"; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file" "$state_file"
}

probe_url() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --noproxy '*' --connect-timeout 2 --max-time 5 "$url" >/dev/null
  else
    python3 - "$url" <<'PY_PROBE'
import sys,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(sys.argv[1],timeout=5) as r:
    if not r.read(1024): raise SystemExit(1)
PY_PROBE
  fi
}

resolve_endpoints() {
  local mode gateway target port tport
  mode="$(transport)"
  [[ "$mode" == wsl-localhost-relay || "$mode" == wsl-host-relay ]] || return 2
  gateway="$(docker_host_gateway_ip)" || return 1
  port="$(bridge_port)"; tport="$(target_port)"
  if [[ "$mode" == wsl-host-relay ]]; then
    target="$(windows_host_gateway_ip)" || return 1
  else
    target="$(target_address)"
  fi
  [[ "$port" =~ ^[0-9]+$ && "$port" -ge 1 && "$port" -le 65535 ]] || return 1
  [[ "$tport" =~ ^[0-9]+$ && "$tport" -ge 1 && "$tport" -le 65535 ]] || return 1
  if [[ "$mode" == wsl-localhost-relay ]]; then
    case "${target,,}" in localhost|127.*) ;; *) return 1;; esac
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$mode" "$gateway" "$port" "$target" "$tport"
}

worker_state_matches() {
  local mode="$1" gateway="$2" port="$3" target="$4" tport="$5" pid=''
  pid="$(owned_worker_pid 2>/dev/null)" || return 1
  [[ -r "$state_file" ]] || return 1
  grep -Fxq "MODE=$mode" "$state_file" || return 1
  grep -Fxq "LISTEN_ADDRESS=$gateway" "$state_file" || return 1
  grep -Fxq "LISTEN_PORT=$port" "$state_file" || return 1
  grep -Fxq "TARGET_ADDRESS=$target" "$state_file" || return 1
  grep -Fxq "TARGET_PORT=$tport" "$state_file" || return 1
  return 0
}

start_worker() {
  local mode="$1" gateway="$2" port="$3" target="$4" tport="$5" pid
  local -a target_mode_args=()
  [[ "$mode" == wsl-host-relay ]] && target_mode_args+=(--allow-private-target)
  probe_url "http://${target}:${tport}/api/version" || return 1
  stop_worker
  mkdir -p logs
  log_msg "starting relay worker listen=${gateway}:${port} target=${target}:${tport} transport=${mode}"
  nohup python3 "$relay_py" \
    --listen-address "$gateway" --listen-port "$port" \
    --target-address "$target" --target-port "$tport" \
    --max-connections "$max_connections" --connect-timeout "$connect_timeout" --idle-timeout "$idle_timeout" \
    "${target_mode_args[@]}" >>"$log_file" 2>&1 </dev/null &
  pid=$!
  printf '%s\n' "$pid" > "$pid_file"
  cat > "$state_file" <<EOF_STATE
MODE=$mode
LISTEN_ADDRESS=$gateway
LISTEN_PORT=$port
TARGET_ADDRESS=$target
TARGET_PORT=$tport
EOF_STATE
  for _ in $(seq 1 40); do
    if probe_url "http://${gateway}:${port}/api/version"; then
      log_msg "relay worker ready pid=${pid} listen=${gateway}:${port} target=${target}:${tport}"
      return 0
    fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  log_msg "relay worker failed readiness check listen=${gateway}:${port} target=${target}:${tport}"
  stop_worker
  return 1
}

supervise_relay() {
  command -v python3 >/dev/null 2>&1 || { echo 'python3 is required for the WSL-local native Ollama relay.' >&2; exit 1; }
  [[ -x "$relay_py" ]] || { echo "Native Ollama relay helper is missing: $relay_py" >&2; exit 1; }
  mkdir -p logs
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$lock_file"
    flock -n 9 || exit 0
  fi
  printf '%s\n' "$$" > "$supervisor_pid_file"
  cleanup_supervisor() {
    stop_worker
    rm -f "$supervisor_pid_file"
    log_msg 'relay supervisor stopped'
    exit 0
  }
  trap cleanup_supervisor TERM INT HUP
  log_msg "relay supervisor started pid=$$ refresh=${refresh_seconds}s"
  local last_problem='' endpoint_line='' mode gateway port target tport
  while [[ ! -e "$disabled_file" ]]; do
    mode="$(transport)"
    if [[ "$mode" != wsl-localhost-relay && "$mode" != wsl-host-relay ]]; then
      stop_worker
      log_msg "relay supervisor exiting because transport=${mode} is not WSL-local"
      rm -f "$supervisor_pid_file"
      exit 0
    fi
    endpoint_line="$(resolve_endpoints 2>/dev/null || true)"
    if [[ -z "$endpoint_line" ]]; then
      stop_worker
      if [[ "$last_problem" != topology ]]; then log_msg 'relay waiting: Docker/WSL topology is not currently discoverable'; last_problem=topology; fi
      sleep "$refresh_seconds"
      continue
    fi
    IFS=$'\t' read -r mode gateway port target tport <<<"$endpoint_line"
    if ! probe_url "http://${target}:${tport}/api/version"; then
      stop_worker
      if [[ "$last_problem" != target ]]; then log_msg "relay waiting: native Ollama target unavailable at ${target}:${tport}"; last_problem=target; fi
      sleep "$refresh_seconds"
      continue
    fi
    if ! worker_state_matches "$mode" "$gateway" "$port" "$target" "$tport"; then
      if [[ -s "$state_file" ]]; then log_msg "relay topology changed; rebuilding worker for listen=${gateway}:${port} target=${target}:${tport}"; fi
      start_worker "$mode" "$gateway" "$port" "$target" "$tport" || {
        if [[ "$last_problem" != worker ]]; then log_msg 'relay worker restart failed; supervisor will retry'; last_problem=worker; fi
        sleep "$refresh_seconds"
        continue
      }
    elif ! probe_url "http://${gateway}:${port}/api/version"; then
      log_msg "relay health probe failed at ${gateway}:${port}; restarting worker"
      start_worker "$mode" "$gateway" "$port" "$target" "$tport" || true
    fi
    last_problem=''
    sleep "$refresh_seconds"
  done
  cleanup_supervisor
}

wait_ready() {
  local endpoint_line mode gateway port target tport
  for _ in $(seq 1 60); do
    endpoint_line="$(resolve_endpoints 2>/dev/null || true)"
    if [[ -n "$endpoint_line" ]]; then
      IFS=$'\t' read -r mode gateway port target tport <<<"$endpoint_line"
      if probe_url "http://${gateway}:${port}/api/version"; then printf '%s' "$gateway"; return 0; fi
    fi
    sleep 0.25
  done
  return 1
}

start_relay() {
  local mode supervisor=''
  mode="$(transport)"
  if [[ "$mode" != wsl-localhost-relay && "$mode" != wsl-host-relay ]]; then return 0; fi
  rm -f "$disabled_file"
  if supervisor="$(owned_supervisor_pid 2>/dev/null)"; then
    if wait_ready; then return 0; fi
    log_msg "existing relay supervisor pid=${supervisor} is alive but unhealthy; restarting supervisor"
    kill -TERM "$supervisor" 2>/dev/null || true
    for _ in $(seq 1 30); do kill -0 "$supervisor" 2>/dev/null || break; sleep 0.1; done
    kill -9 "$supervisor" 2>/dev/null || true
    stop_worker
    rm -f "$supervisor_pid_file"
  fi
  if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1 && systemctl cat "$service_name" >/dev/null 2>&1; then
    systemctl start "$service_name" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      if systemctl is-active --quiet "$service_name" 2>/dev/null; then
        if wait_ready; then return 0; fi
        log_msg 'systemd relay service is active but unhealthy; restarting it once'
        systemctl restart "$service_name" >/dev/null 2>&1 || true
        wait_ready && return 0
        break
      fi
      sleep 0.25
    done
  fi
  mkdir -p logs
  nohup bash "$PWD/native-ollama-relay.sh" supervise >>"$log_file" 2>&1 </dev/null &
  for _ in $(seq 1 20); do owned_supervisor_pid >/dev/null 2>&1 && break; sleep 0.1; done
  if wait_ready; then return 0; fi
  echo 'WSL-local native Ollama relay supervisor did not establish a healthy relay.' >&2
  [[ -s "$log_file" ]] && tail -n 12 "$log_file" >&2 || true
  return 1
}

stop_relay() {
  local pid=''
  touch "$disabled_file"
  if pid="$(owned_supervisor_pid 2>/dev/null)"; then
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
  fi
  stop_worker
  rm -f "$supervisor_pid_file"
}

case "${1:-status}" in
  start) start_relay ;;
  stop) stop_relay ;;
  restart) stop_relay; rm -f "$disabled_file"; start_relay ;;
  supervise) supervise_relay ;;
  host) docker_host_gateway_ip ;;
  base-url)
    host="$(docker_host_gateway_ip)" || exit 1
    printf 'http://%s:%s' "$host" "$(bridge_port)"
    ;;
  status)
    if [[ "$(transport)" != wsl-localhost-relay && "$(transport)" != wsl-host-relay ]]; then echo 'inactive (transport is not a WSL-local relay)'; exit 0; fi
    if pid="$(owned_supervisor_pid 2>/dev/null)"; then
      worker="$(owned_worker_pid 2>/dev/null || true)"
      if endpoint="$(resolve_endpoints 2>/dev/null)"; then
        IFS=$'\t' read -r _ gateway port target tport <<<"$endpoint"
        if probe_url "http://${gateway}:${port}/api/version"; then health=healthy; else health=unhealthy; fi
        echo "supervised pid=$pid worker=${worker:-none} health=$health listen=${gateway}:${port} target=${target}:${tport}"
      else
        echo "supervised pid=$pid worker=${worker:-none} health=waiting-topology"
      fi
    else
      echo 'stopped'
    fi
    ;;
  *) echo 'Usage: ./native-ollama-relay.sh {start|stop|restart|supervise|host|base-url|status}' >&2; exit 2;;
esac
