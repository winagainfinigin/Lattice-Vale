#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -eq 0 ]]; then echo 'Run this script as the normal Ubuntu user, not root.' >&2; exit 1; fi
cd "$(dirname "${BASH_SOURCE[0]}")"
# This installer owns an in-distro rootful Docker Engine. Never inherit a user's
# remote Docker context/host/TLS settings and accidentally mutate another daemon.
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
export DOCKER_HOST=unix:///var/run/docker.sock
[[ -f install-options.json ]] || { echo 'Missing install-options.json. Run the Windows installer.' >&2; exit 2; }
python3 -m json.tool install-options.json >/dev/null

# Treat install-options.json as untrusted persisted state. The Windows installer
# normally emits these values, but repair runs may encounter an older, truncated,
# or hand-edited file. Validate path-bearing names and control fields before any
# filesystem or Docker mutation.
python3 - install-options.json <<'PY_OPTIONS_VALIDATE'
import ipaddress,json,re,sys
from pathlib import Path
p=Path(sys.argv[1])
try:
    d=json.loads(p.read_text(encoding='utf-8'))
except Exception as exc:
    raise SystemExit(f'Invalid install-options.json: {exc}')
if not isinstance(d,dict):
    raise SystemExit('Invalid install-options.json: top level must be an object.')

bool_keys=(
    'dashboard','multiAgent','kanban','matrix','tailscale','installWindowsTailscale',
    'tailscaleDashboard','tailscaleMatrix','searxng','qmd','honcho','hermesLocalAI',
    'obsidian','unattendedUpdates','autoStart','windowsShortcuts','keepWslServicesRunning','containerResourceLimits','resetCheckpoints',
    'forceProviderSetup','forceProfileSetup','rebuildMatrixIdentity','repairMaintenance','forceManagedUpdate','universalRepairMigration',
)
for key in bool_keys:
    if key in d and not isinstance(d[key],bool):
        raise SystemExit(f'Invalid install-options.json: {key} must be true or false.')
if 'schema' in d and (isinstance(d['schema'],bool) or not isinstance(d['schema'],int) or not 1 <= d['schema'] <= 20):
    raise SystemExit('Invalid install-options.json: schema must be an integer from 1 through 20.')
if 'repairOriginSchema' in d and (isinstance(d['repairOriginSchema'],bool) or not isinstance(d['repairOriginSchema'],int) or not 0 <= d['repairOriginSchema'] <= 20):
    raise SystemExit('Invalid install-options.json: repairOriginSchema must be an integer from 0 through 20.')

workers=d.get('workers',[])
if not isinstance(workers,list):
    raise SystemExit('Invalid install-options.json: workers must be an array.')
if len(workers)>8:
    raise SystemExit('Invalid install-options.json: at most 8 additional profiles are supported.')
seen=set()
name_re=re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')
for i,w in enumerate(workers,1):
    if not isinstance(w,dict):
        raise SystemExit(f'Invalid install-options.json: worker {i} must be an object.')
    name=w.get('name')
    if not isinstance(name,str) or name=='default' or not name_re.fullmatch(name) or name in seen:
        raise SystemExit(f'Invalid install-options.json: worker {i} has an unsafe, reserved, or duplicate name.')
    seen.add(name)
    if 'description' in w and not isinstance(w['description'],str):
        raise SystemExit(f'Invalid install-options.json: worker {name} description must be text.')
    if 'clone' in w and not isinstance(w['clone'],bool):
        raise SystemExit(f'Invalid install-options.json: worker {name} clone must be true or false.')

    if 'modelMode' in w and w['modelMode'] not in ('clone-default','profile-selected'):
        raise SystemExit(f'Invalid install-options.json: worker {name} modelMode is invalid.')
    mx=w.get('matrix')
    if mx is not None:
        if not isinstance(mx,dict):
            raise SystemExit(f'Invalid install-options.json: worker {name} matrix must be an object.')
        if 'enabled' in mx and not isinstance(mx['enabled'],bool):
            raise SystemExit(f'Invalid install-options.json: worker {name} matrix.enabled must be true or false.')
        if mx.get('enabled') is True and name == 'hermes':
            raise SystemExit('Invalid install-options.json: a secondary Matrix-enabled profile cannot be named hermes because @hermes:hermes.local belongs to the default profile.')
        localpart=mx.get('localpart',name)
        if not isinstance(localpart,str) or localpart != name:
            raise SystemExit(f'Invalid install-options.json: worker {name} Matrix localpart must match the profile name.')
        mode=mx.get('roomMode','create')
        if mode not in ('create','existing'):
            raise SystemExit(f'Invalid install-options.json: worker {name} matrix.roomMode must be create or existing.')
        room_name=mx.get('roomName',f'LatticeVale {name}')
        if not isinstance(room_name,str) or not room_name.strip() or len(room_name)>120 or '\n' in room_name or '\r' in room_name:
            raise SystemExit(f'Invalid install-options.json: worker {name} Matrix room name is invalid.')
        room_id=mx.get('roomId','')
        if not isinstance(room_id,str):
            raise SystemExit(f'Invalid install-options.json: worker {name} matrix.roomId must be text.')
        if mode=='existing' and mx.get('enabled') and not re.fullmatch(r'![^:\s]+:[^\s]+',room_id):
            raise SystemExit(f'Invalid install-options.json: worker {name} existing Matrix room ID is invalid.')


text_backend=d.get('localTextBackend','ollama')
if text_backend not in ('ollama','directml'):
    raise SystemExit('Invalid install-options.json: localTextBackend must be ollama or directml.')
directml_model=d.get('directmlTextModel','Qwen/Qwen2.5-1.5B-Instruct')
if not isinstance(directml_model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}',directml_model):
    raise SystemExit('Invalid install-options.json: directmlTextModel must be a safe Hugging Face owner/model repository ID.')

backend=d.get('ollamaBackend','managed')
if backend not in ('managed','windows-native'):
    raise SystemExit('Invalid install-options.json: ollamaBackend must be managed or windows-native.')
accel=d.get('ollamaAcceleration')
if accel is not None and accel not in ('auto','cpu','nvidia','amd'):
    raise SystemExit('Invalid install-options.json: ollamaAcceleration must be auto, cpu, nvidia, or amd.')

model_re=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$')
for key in ('localTextModel','localEmbeddingModel'):
    value=d.get(key)
    if value is not None and (not isinstance(value,str) or not model_re.fullmatch(value)):
        raise SystemExit(f'Invalid install-options.json: {key} is not a safe Ollama model/tag.')

for key in ('hermesApiPort','dashboardLocalPort','matrixLocalPort','searxngLocalPort','honchoLocalPort',
            'tailscaleDashboardPort','tailscaleMatrixPort','dashboardBridgePort','matrixBridgePort','windowsOllamaBridgePort','windowsOllamaTargetPort','directmlPort'):
    if key in d and (isinstance(d[key],bool) or not isinstance(d[key],int) or not 1 <= d[key] <= 65535):
        raise SystemExit(f'Invalid install-options.json: {key} must be an integer TCP port from 1 to 65535.')

for key in ('timezone','installerVersion','installerMode','repairOriginVersion','questionnaireMode','obsidianVaultWindowsPath','obsidianVaultWslPath','windowsOllamaBridgeTaskName','windowsOllamaTransport','windowsOllamaTargetAddress','windowsOllamaHostAddress','directmlAdapterName','directmlGpuVendor'):
    if key in d and not isinstance(d[key],str):
        raise SystemExit(f'Invalid install-options.json: {key} must be text.')
if d.get('directmlGpuVendor','') not in ('','amd','nvidia','intel','qualcomm'):
    raise SystemExit('Invalid install-options.json: directmlGpuVendor must be amd, nvidia, intel, qualcomm, or empty.')
if isinstance(d.get('directmlAdapterName',''),str) and ('\n' in d.get('directmlAdapterName','') or '\r' in d.get('directmlAdapterName','') or len(d.get('directmlAdapterName','')) > 160):
    raise SystemExit('Invalid install-options.json: directmlAdapterName is too long or contains a newline.')
if 'questionnaireMode' in d and d['questionnaireMode'] not in ('quick','custom','explicit'):
    raise SystemExit('Invalid install-options.json: questionnaireMode must be quick, custom, or explicit.')
if backend == 'windows-native':
    transport=d.get('windowsOllamaTransport','windows-gateway-relay')
    if transport not in ('windows-gateway-relay','wsl-localhost-relay','wsl-host-relay'):
        raise SystemExit('Invalid install-options.json: windowsOllamaTransport must be windows-gateway-relay, wsl-localhost-relay, or wsl-host-relay.')
    target=str(d.get('windowsOllamaTargetAddress','127.0.0.1')).strip().lower()
    if target == 'localhost': target='127.0.0.1'
    try: target_ip=ipaddress.ip_address(target)
    except ValueError: raise SystemExit('Invalid install-options.json: windowsOllamaTargetAddress must be IPv4 loopback.')
    if target_ip.version != 4 or not target_ip.is_loopback:
        raise SystemExit('Invalid install-options.json: windowsOllamaTargetAddress must remain on IPv4 loopback.')
    host_address=str(d.get('windowsOllamaHostAddress','')).strip()
    if transport in ('windows-gateway-relay','wsl-host-relay'):
        try: host_ip=ipaddress.ip_address(host_address)
        except ValueError: raise SystemExit('Invalid install-options.json: windowsOllamaHostAddress must be a non-loopback IPv4 address for the selected Windows-host transport.')
        if host_ip.version != 4 or host_ip.is_loopback or host_ip.is_link_local:
            raise SystemExit('Invalid install-options.json: windowsOllamaHostAddress must be a non-loopback, non-link-local IPv4 address for the selected Windows-host transport.')
for key in ('kanbanMaxInProgress','kanbanMaxInProgressPerProfile'):
    if key in d and (isinstance(d[key],bool) or not isinstance(d[key],int) or not 1 <= d[key] <= 8):
        raise SystemExit(f'Invalid install-options.json: {key} must be an integer from 1 to 8.')
if d.get('obsidian'):
    wp=d.get('obsidianVaultWindowsPath','')
    lp=d.get('obsidianVaultWslPath','')
    if not re.fullmatch(r'[A-Za-z]:\\[^\r\n]+', wp):
        raise SystemExit('Invalid install-options.json: obsidianVaultWindowsPath must be a Windows-local drive path.')
    if not lp.startswith('/') or lp == '/' or '\n' in lp or '\r' in lp or '/..' in lp:
        raise SystemExit('Invalid install-options.json: obsidianVaultWslPath must be an absolute WSL path to a mounted local Windows drive.')
print('Persisted installer options validated.')
PY_OPTIONS_VALIDATE

opt_bool() { jq -r ".${1} // false" install-options.json; }
opt_text() { jq -r ".${1} // empty" install-options.json; }
opt_port() {
  local key="$1" default="$2" value
  value="$(jq -r --arg k "$key" --argjson d "$default" '.[$k] // $d' install-options.json)"
  [[ "$value" =~ ^[0-9]+$ && "$value" -ge 1 && "$value" -le 65535 ]] || value="$default"
  printf '%s' "$value"
}
HERMES_API_HOST_PORT="$(opt_port hermesApiPort 8642)"
DASHBOARD_HOST_PORT="$(opt_port dashboardLocalPort 9119)"
MATRIX_HOST_PORT="$(opt_port matrixLocalPort 8008)"
SEARXNG_HOST_PORT="$(opt_port searxngLocalPort 8888)"
HONCHO_HOST_PORT="$(opt_port honchoLocalPort 8000)"
WINDOWS_OLLAMA_BRIDGE_PORT="$(opt_port windowsOllamaBridgePort 11435)"
DIRECTML_PORT="$(opt_port directmlPort 11436)"
WINDOWS_OLLAMA_TRANSPORT="$(opt_text windowsOllamaTransport)"
[[ "$WINDOWS_OLLAMA_TRANSPORT" == windows-gateway-relay || "$WINDOWS_OLLAMA_TRANSPORT" == wsl-localhost-relay || "$WINDOWS_OLLAMA_TRANSPORT" == wsl-host-relay ]] || WINDOWS_OLLAMA_TRANSPORT=windows-gateway-relay
WINDOWS_OLLAMA_TARGET_ADDRESS="$(opt_text windowsOllamaTargetAddress)"
[[ -n "$WINDOWS_OLLAMA_TARGET_ADDRESS" ]] || WINDOWS_OLLAMA_TARGET_ADDRESS=127.0.0.1
WINDOWS_OLLAMA_TARGET_PORT="$(opt_port windowsOllamaTargetPort 11434)"
WINDOWS_OLLAMA_HOST_ADDRESS="$(opt_text windowsOllamaHostAddress)"
# LatticeVale intentionally pins installer-managed Matrix rooms to v10. This is a
# compatibility policy, not a request to follow Synapse's moving default.
LATTICEVALE_MATRIX_ROOM_VERSION=10
DASHBOARD_HOST_BIND=127.0.0.1
MATRIX_HOST_BIND=127.0.0.1
WSL_NETWORKING_MODE="$(opt_text wslNetworkingMode | tr '[:upper:]' '[:lower:]')"
# The Windows relay needs a non-loopback WSL bind only in NAT/compatibility mode.
# Mirrored mode gives Windows a localhost path to WSL, so keep selected services on
# loopback and avoid unnecessarily exposing them on mirrored host/LAN interfaces.
if [[ "$WSL_NETWORKING_MODE" != mirrored ]]; then
  [[ "$(opt_bool tailscaleDashboard)" == true ]] && DASHBOARD_HOST_BIND=0.0.0.0
  [[ "$(opt_bool tailscaleMatrix)" == true ]] && MATRIX_HOST_BIND=0.0.0.0
fi
# Release-candidate source pin: a clean install must build the same Honcho tree that
# this bundle was audited against. Windows Update / repair is the reproducible opt-in to apply a newer bundle's audited pin; ./manage.sh update remains a separate advanced upstream refresh.
HONCHO_SOURCE_COMMIT=444897975c95393b0d48024470ece03c025d3aa4
random_hex() { openssl rand -hex "${1:-24}"; }

matrix_login_json() {
  local u="$1" p="$2" device_id="${3:-}" display="${4:-LatticeVale}"
  local payload
  if [[ -n "$device_id" ]]; then
    payload="$(jq -cn --arg u "$u" --arg p "$p" --arg d "$device_id" --arg n "$display" '{type:"m.login.password",identifier:{type:"m.id.user",user:$u},password:$p,device_id:$d,initial_device_display_name:$n}')"
  else
    payload="$(jq -cn --arg u "$u" --arg p "$p" '{type:"m.login.password",identifier:{type:"m.id.user",user:$u},password:$p}')"
  fi
  curl -fsS --connect-timeout 5 --max-time 30 -X POST "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/login" \
    -H 'Content-Type: application/json' --data "$payload"
}

matrix_room_uri() {
  jq -rn --arg v "$1" '$v|@uri'
}

matrix_user_uri() {
  jq -rn --arg v "$1" '$v|@uri'
}

matrix_client_api_ready() {
  curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:${MATRIX_HOST_PORT}/health" >/dev/null 2>&1 || return 1
  curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/versions" 2>/dev/null |
    jq -e '.versions | type == "array" and length > 0' >/dev/null 2>&1
}

wait_matrix_client_api() {
  local tries="${1:-60}" i
  for i in $(seq 1 "$tries"); do
    matrix_client_api_ready && return 0
    sleep 2
  done
  echo "Matrix/Synapse did not expose a healthy Client-Server API on localhost:${MATRIX_HOST_PORT}. Profile room provisioning cannot continue until Matrix is online." >&2
  return 1
}

matrix_backend_ready_from_hermes() {
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent python3 -c '
import http.client, socket
socket.getaddrinfo("synapse", 8008)
c=http.client.HTTPConnection("synapse", 8008, timeout=5)
c.request("GET", "/_matrix/client/versions")
r=c.getresponse()
raise SystemExit(0 if 200 <= int(r.status) < 400 else 1)
' >/dev/null 2>&1
}

wait_matrix_backend_from_hermes() {
  local tries="${1:-60}" i
  for i in $(seq 1 "$tries"); do
    matrix_backend_ready_from_hermes && return 0
    sleep 2
  done
  echo 'Matrix is healthy on the WSL host but is not reachable as synapse:8008 from inside hermes-agent. Gateway reconciliation is blocked to avoid a false-running Matrix gateway.' >&2
  return 1
}

wait_managed_ollama_healthy() {
  local tries="${1:-60}" i status
  managed_ollama_enabled || return 0
  for i in $(seq 1 "$tries"); do
    status="$(docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null || true)"
    [[ "$status" == healthy ]] && return 0
    # Fail promptly on a terminal unhealthy state after Docker's own start-period/retries,
    # but tolerate the normal starting state during repair/startup reconciliation.
    [[ "$status" == unhealthy ]] && {
      echo 'LatticeVale-managed Ollama became unhealthy during reconciliation.' >&2
      docker logs --tail 120 hermes-ollama 2>&1 | tail -n 120 >&2 || true
      return 1
    }
    sleep 2
  done
  status="$(docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null || true)"
  echo "LatticeVale-managed Ollama did not become healthy within the bounded reconciliation window (last health state: ${status:-unknown})." >&2
  docker logs --tail 120 hermes-ollama 2>&1 | tail -n 120 >&2 || true
  return 1
}

ensure_matrix_online() {
  # A repair must not assume Synapse remained running from an earlier stage or prior
  # installer attempt. Start only the installer-managed Matrix services, then require
  # both the lightweight health endpoint and the Client-Server versions endpoint.
  timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build synapse-db synapse >/dev/null
  wait_matrix_client_api "${1:-60}"
}

matrix_require_room_v10() {
  local token="$1" capabilities status
  capabilities="$(curl -fsS --connect-timeout 5 --max-time 15 \
    -H "Authorization: Bearer $token" \
    "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/capabilities")" || return 1
  status="$(jq -r --arg v "$LATTICEVALE_MATRIX_ROOM_VERSION" '.capabilities["m.room_versions"].available[$v] // empty' <<<"$capabilities")"
  [[ "$status" == stable ]] || {
    echo "Synapse does not advertise required Matrix room version $LATTICEVALE_MATRIX_ROOM_VERSION as stable (status='${status:-missing}'). LatticeVale will not create a different room version automatically." >&2
    return 1
  }
}

matrix_room_version() {
  local token="$1" room_id="$2" encoded
  encoded="$(matrix_room_uri "$room_id")"
  curl -fsS --connect-timeout 5 --max-time 10 \
    -H "Authorization: Bearer $token" \
    "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$encoded/state/m.room.create/" 2>/dev/null |
    jq -r '.room_version // empty'
}

wait_matrix_room_join() {
  local token="$1" room_id="$2" label="$3" tries="${4:-45}" profile="${5:-}" i failures=0 gateway_state
  for i in $(seq 1 "$tries"); do
    if [[ -n "$profile" ]]; then
      if ! gateway_state="$(profile_gateway_s6_state "$profile")"; then
        echo "Unable to read exact s6 gateway state for profile '$profile' while waiting for Matrix membership." >&2
        profile_gateway_log_tail_exact "$profile"
        return 3
      fi
      if [[ "$gateway_state" != up ]]; then
        echo "Profile '$profile' exact s6 gateway service became '$gateway_state' before it joined Matrix room '$room_id'; aborting the wait immediately." >&2
        profile_gateway_log_tail_exact "$profile"
        return 3
      fi
    fi
    if ! matrix_client_api_ready; then
      failures=$((failures+1))
      if (( failures >= 3 )); then
        echo "Matrix/Synapse became unavailable while waiting for $label to join room '$room_id'. Stopping this join attempt so Resume / repair can continue later instead of looping." >&2
        return 2
      fi
      sleep 2
      continue
    fi
    failures=0
    if curl -fsS --connect-timeout 3 --max-time 7 -H "Authorization: Bearer $token" \
        "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/joined_rooms" 2>/dev/null |
        jq -e --arg r "$room_id" '.joined_rooms | index($r) != null' >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "$label did not join Matrix room '$room_id' within the bounded readiness window." >&2
  return 1
}

local_ai_enabled() {
  [[ "$(opt_bool honcho)" == true || "$(opt_bool hermesLocalAI)" == true ]]
}

local_text_backend() {
  local value
  value="$(opt_text localTextBackend)"
  [[ "$value" == ollama || "$value" == directml ]] || value=ollama
  printf '%s' "$value"
}

directml_text_enabled() {
  local_ai_enabled && [[ "$(local_text_backend)" == directml ]]
}

directml_text_model() {
  local value
  value="$(opt_text directmlTextModel)"
  [[ -n "$value" ]] || value='Qwen/Qwen2.5-1.5B-Instruct'
  printf '%s' "$value"
}

directml_openai_base_url() {
  printf 'http://directml.host:%s/v1' "$DIRECTML_PORT"
}

local_text_model_name() {
  if directml_text_enabled; then directml_text_model; else opt_text localTextModel; fi
}

local_text_openai_base_url() {
  if directml_text_enabled; then directml_openai_base_url; else ollama_openai_base_url; fi
}

local_text_context_length() {
  if directml_text_enabled; then printf '%s' 8192; else choose_ollama_context_length; fi
}

ollama_backend() {
  local value
  value="$(opt_text ollamaBackend)"
  [[ "$value" == managed || "$value" == windows-native ]] || value=managed
  printf '%s' "$value"
}

managed_ollama_enabled() {
  local_ai_enabled && [[ "$(ollama_backend)" == managed ]]
}

windows_native_ollama_enabled() {
  local_ai_enabled && [[ "$(ollama_backend)" == windows-native ]]
}

windows_host_ip() {
  local ip
  if windows_native_ollama_enabled && [[ "$WINDOWS_OLLAMA_TRANSPORT" == wsl-localhost-relay || "$WINDOWS_OLLAMA_TRANSPORT" == wsl-host-relay ]]; then
    [[ -x ./native-ollama-relay.sh ]] || return 1
    ./native-ollama-relay.sh host
    return
  fi
  ip="$WINDOWS_OLLAMA_HOST_ADDRESS"
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  printf '%s' "$ip"
}

ollama_api_base_url() {
  if windows_native_ollama_enabled; then
    local host
    host="$(windows_host_ip)" || return 1
    printf 'http://%s:%s' "$host" "$WINDOWS_OLLAMA_BRIDGE_PORT"
  else
    printf '%s' 'http://ollama:11434'
  fi
}

native_ollama_ready_base_url() {
  windows_native_ollama_enabled || return 1
  local transport base attempt
  transport="$WINDOWS_OLLAMA_TRANSPORT"
  if [[ "$transport" == wsl-localhost-relay || "$transport" == wsl-host-relay ]]; then
    [[ -x ./native-ollama-relay.sh ]] || { echo 'Native Ollama WSL relay helper is missing; rerun Resume / repair.' >&2; return 1; }
    # `ollama_api_base_url` can calculate Docker's host-gateway even when no relay
    # worker is listening there. Start/recover the supervised relay first and accept
    # the endpoint only after a real Ollama /api/version response succeeds.
    timeout --foreground --kill-after=5s 50s ./native-ollama-relay.sh start >/dev/null || {
      echo 'Could not establish the supervised WSL-local native Ollama relay.' >&2
      [[ -s logs/native-ollama-relay.log ]] && tail -n 16 logs/native-ollama-relay.log >&2 || true
      return 1
    }
    base="$(./native-ollama-relay.sh base-url 2>/dev/null || true)"
  else
    base="$(ollama_api_base_url 2>/dev/null || true)"
  fi
  [[ -n "$base" ]] || return 1
  for attempt in $(seq 1 8); do
    if timeout --foreground --kill-after=2s 8s python3 - "$base" <<'PY_NATIVE_READY_PROBE' >/dev/null 2>&1
import sys,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(sys.argv[1].rstrip('/')+'/api/version',timeout=5) as r:
    if not r.read(1024): raise SystemExit(1)
PY_NATIVE_READY_PROBE
    then
      printf '%s' "$base"
      return 0
    fi
    sleep 1
  done
  if [[ "$transport" == wsl-localhost-relay || "$transport" == wsl-host-relay ]]; then
    log_note='Native Ollama relay endpoint failed its HTTP probe after startup; forcing one bounded relay restart.'
    echo "$log_note" >&2
    timeout --foreground --kill-after=5s 50s ./native-ollama-relay.sh restart >/dev/null 2>&1 || true
    base="$(./native-ollama-relay.sh base-url 2>/dev/null || true)"
    for attempt in $(seq 1 8); do
      if timeout --foreground --kill-after=2s 8s python3 - "$base" <<'PY_NATIVE_READY_REPROBE' >/dev/null 2>&1
import sys,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(sys.argv[1].rstrip('/')+'/api/version',timeout=5) as r:
    if not r.read(1024): raise SystemExit(1)
PY_NATIVE_READY_REPROBE
      then
        printf '%s' "$base"
        return 0
      fi
      sleep 1
    done
  fi
  echo "Native Windows Ollama relay/API did not become healthy at ${base:-unknown endpoint}." >&2
  [[ -s logs/native-ollama-relay.log ]] && tail -n 16 logs/native-ollama-relay.log >&2 || true
  return 1
}

ollama_openai_base_url() {
  if windows_native_ollama_enabled; then
    printf 'http://windows.host:%s/v1' "$WINDOWS_OLLAMA_BRIDGE_PORT"
  else
    printf '%s' 'http://ollama:11434/v1'
  fi
}


nvidia_smi_path() {
  if command -v nvidia-smi >/dev/null 2>&1; then command -v nvidia-smi; return 0; fi
  [[ -x /usr/lib/wsl/lib/nvidia-smi ]] && { printf '%s' /usr/lib/wsl/lib/nvidia-smi; return 0; }
  return 1
}

nvidia_container_runtime_ready() {
  local smi
  smi="$(nvidia_smi_path 2>/dev/null || true)"
  [[ -n "$smi" ]] || return 1
  timeout --foreground --kill-after=3s 10s "$smi" -L >/dev/null 2>&1 || return 1
  timeout --foreground --kill-after=3s 10s docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'
}

ollama_gpu_inventory() {
  # Emit one "index|name|MiB" row per GPU visible to the managed Ollama runtime.
  # Resource policy v11 deliberately inventories individual adapters instead of
  # treating aggregate VRAM as one interchangeable pool: Ollama normally prefers a
  # single fitting GPU and spreads only when it needs multiple devices.
  local accel="$1" smi line idx name mib vf card vendor raw
  case "$accel" in
    nvidia)
      smi="$(nvidia_smi_path 2>/dev/null || true)"
      [[ -n "$smi" ]] || return 1
      while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        idx="${line%%,*}"; line="${line#*,}"
        name="${line%,*}"; mib="${line##*,}"
        idx="${idx//[[:space:]]/}"; mib="${mib//[[:space:]]/}"
        name="${name# }"; name="${name% }"
        [[ "$idx" =~ ^[0-9]+$ && "$mib" =~ ^[0-9]+$ && "$mib" -ge 256 ]] || continue
        printf '%s|%s|%s\n' "$idx" "$name" "$mib"
      done < <(timeout --foreground --kill-after=3s 10s "$smi" --query-gpu=index,name,memory.total --format=csv,noheader,nounits 2>/dev/null || true)
      ;;
    amd)
      idx=0
      shopt -s nullglob
      for vf in /sys/class/drm/card*/device/mem_info_vram_total; do
        card="${vf%/device/mem_info_vram_total}"
        vendor="$(cat "$card/device/vendor" 2>/dev/null || true)"
        [[ "$vendor" == 0x1002 ]] || continue
        raw="$(cat "$vf" 2>/dev/null || true)"
        [[ "$raw" =~ ^[0-9]+$ ]] || continue
        mib=$((raw/1048576)); (( mib >= 256 )) || continue
        name="AMD GPU ${card##*/}"
        printf '%s|%s|%s\n' "$idx" "$name" "$mib"
        idx=$((idx+1))
      done
      shopt -u nullglob
      ;;
    *) return 0 ;;
  esac
}

ollama_gpu_metrics() {
  # count:min:max:aggregate. Fail for a selected GPU backend if VRAM cannot be
  # measured; GPU-backed hard limits must never be based on an invented capacity.
  local accel="$1" inventory
  [[ "$accel" == nvidia || "$accel" == amd ]] || { printf '0:0:0:0\n'; return 0; }
  inventory="$(ollama_gpu_inventory "$accel")" || return 1
  [[ -n "$inventory" ]] || return 1
  python3 - "$inventory" <<'PY_GPU_METRICS'
import sys
vals=[]
for line in sys.argv[1].splitlines():
    try:
        mib=int(line.rsplit('|',1)[1])
    except Exception:
        continue
    if mib>0: vals.append(mib)
if not vals: raise SystemExit(1)
print(f"{len(vals)}:{min(vals)}:{max(vals)}:{sum(vals)}")
PY_GPU_METRICS
}

resource_gpu_coordination() {
  # Return per-GPU OLLAMA_GPU_OVERHEAD MiB and the DirectML VRAM percentage.
  # When both managed Ollama and DirectML use the same vendor, reserve a real VRAM
  # envelope from Ollama instead of allowing both backends to independently assume
  # most of the same adapter. Similar-size GPU sets use a half-and-half envelope;
  # highly heterogeneous sets key the fixed reserve to the smallest GPU so a tiny
  # secondary adapter cannot cause the large DirectML adapter to be overcommitted.
  local accel="$1" count="$2" min_mib="$3" max_mib="$4" directml_vendor overhead=0 directml_pct=75
  if [[ "$accel" != nvidia && "$accel" != amd ]]; then printf '0:75:false\n'; return 0; fi
  directml_vendor="$(opt_text directmlGpuVendor 2>/dev/null || true)"
  if resource_directml_selected && [[ "$directml_vendor" == "$accel" ]] && (( count > 0 && min_mib > 0 && max_mib > 0 )); then
    if (( max_mib*2 <= min_mib*3 )); then
      overhead=$((max_mib/2))
      directml_pct=50
    else
      overhead=$((min_mib*3/4))
      directml_pct=$((overhead*100/max_mib))
      (( directml_pct > 50 )) && directml_pct=50
      (( directml_pct < 5 )) && directml_pct=5
    fi
    overhead=$((((overhead+255)/256)*256))
    # Never reserve the entire smallest GPU. This is mostly defensive for odd
    # virtual/integrated reports; DirectML admission will still fail closed if its
    # policy-selected percentage provides less than the 1 GiB safe minimum.
    if (( overhead >= min_mib )); then overhead=$((((min_mib*3/4)/256)*256)); fi
    (( overhead < 256 )) && overhead=256
    printf '%s:%s:true\n' "$overhead" "$directml_pct"
  else
    printf '0:75:false\n'
  fi
}

resource_ram_profile() {
  local mem_mib="$1"
  if (( mem_mib <= 8192 )); then printf compact
  elif (( mem_mib <= 16384 )); then printf balanced
  else printf large
  fi
}

resource_cpu_profile() {
  local cpus="$1"
  if (( cpus <= 4 )); then printf compact
  elif (( cpus <= 8 )); then printf balanced
  else printf high
  fi
}

resource_ram_context_recommendation() {
  local mem_mib="$1"
  if (( mem_mib <= 8192 )); then printf 4096
  elif (( mem_mib <= 16384 )); then printf 16384
  elif (( mem_mib <= 32768 )); then printf 32768
  else printf 65536
  fi
}

resource_gpu_context_recommendation() {
  # Mirror Ollama's current VRAM-aware default bands, but cap the managed local
  # policy at 64k because larger contexts sharply multiply KV-cache use and this
  # stack prioritizes coexistence with Windows applications/games.
  local usable_mib="$1"
  if (( usable_mib < 24576 )); then printf 4096
  elif (( usable_mib < 49152 )); then printf 32768
  else printf 65536
  fi
}

ollama_gpu_fingerprint() {
  local accel="$1" metrics="$2" extra=''
  if [[ "$accel" == nvidia ]]; then
    local smi
    smi="$(nvidia_smi_path 2>/dev/null || true)"
    [[ -n "$smi" ]] && extra="$(timeout --foreground --kill-after=2s 8s "$smi" --query-gpu=driver_version --format=csv,noheader,nounits 2>/dev/null | sort -u | tr '\n' ',' || true)"
  elif [[ "$accel" == amd ]]; then
    extra="$(uname -r 2>/dev/null || true):$(cat /sys/module/amdgpu/version 2>/dev/null || true)"
  fi
  printf '%s' "$accel|$metrics|$extra" | sha256sum | awk '{print $1}'
}

ollama_gpu_fallback_matches() {
  local accel="$1" metrics="$2" marker=.latticevale-ollama-gpu-fallback fingerprint saved
  [[ -s "$marker" && ! -L "$marker" ]] || return 1
  fingerprint="$(ollama_gpu_fingerprint "$accel" "$metrics")" || return 1
  saved="$(sed -n 's/^FINGERPRINT=//p' "$marker" 2>/dev/null | head -n1)"
  [[ -n "$saved" && "$saved" == "$fingerprint" ]]
}

mark_ollama_gpu_fallback() {
  local accel="$1" metrics="$2" marker=.latticevale-ollama-gpu-fallback fingerprint
  fingerprint="$(ollama_gpu_fingerprint "$accel" "$metrics")" || return 1
  printf 'ACCEL=%s\nMETRICS=%s\nFINGERPRINT=%s\n' "$accel" "$metrics" "$fingerprint" > "$marker"
  chmod 0600 "$marker"
}

clear_ollama_gpu_fallback() {
  rm -f .latticevale-ollama-gpu-fallback
}

resolve_ollama_acceleration() {
  local requested smi metrics
  requested="$(opt_text ollamaAcceleration)"
  [[ -n "$requested" ]] || requested=cpu
  case "$requested" in
    cpu) printf '%s' cpu ;;
    nvidia)
      nvidia_container_runtime_ready || { echo 'Ollama NVIDIA acceleration was explicitly selected, but a working WSL NVIDIA device + Docker NVIDIA runtime was not verified. Repair the Windows NVIDIA/WSL driver or NVIDIA Container Toolkit, or rerun and choose Auto/CPU.' >&2; return 1; }
      metrics="$(ollama_gpu_metrics nvidia 2>/dev/null || true)"
      [[ -n "$metrics" ]] || { echo 'Ollama NVIDIA acceleration was selected, but LatticeVale could not inventory per-GPU VRAM. Refusing GPU-sized resource assumptions.' >&2; return 1; }
      printf '%s' nvidia ;;
    amd)
      [[ "$(uname -m)" == x86_64 ]] || { echo 'Ollama AMD/ROCm acceleration currently requires an x86_64 WSL distro.' >&2; return 1; }
      [[ -c /dev/kfd && -d /dev/dri ]] || { echo 'Ollama AMD/ROCm acceleration was explicitly selected, but /dev/kfd and /dev/dri are not both available in this WSL distro. Expose a supported AMD ROCm device or rerun and choose Auto/CPU.' >&2; return 1; }
      metrics="$(ollama_gpu_metrics amd 2>/dev/null || true)"
      [[ -n "$metrics" ]] || { echo 'Ollama AMD/ROCm acceleration was selected, but LatticeVale could not inventory per-GPU VRAM. Refusing GPU-sized resource assumptions.' >&2; return 1; }
      printf '%s' amd ;;
    auto)
      if nvidia_container_runtime_ready && metrics="$(ollama_gpu_metrics nvidia 2>/dev/null || true)" && [[ -n "$metrics" ]]; then
        if ollama_gpu_fallback_matches nvidia "$metrics"; then printf '%s' cpu; else printf '%s' nvidia; fi
      elif [[ "$(uname -m)" == x86_64 && -c /dev/kfd && -d /dev/dri ]] && metrics="$(ollama_gpu_metrics amd 2>/dev/null || true)" && [[ -n "$metrics" ]]; then
        if ollama_gpu_fallback_matches amd "$metrics"; then printf '%s' cpu; else printf '%s' amd; fi
      else printf '%s' cpu
      fi ;;
    *) echo "Unsupported Ollama acceleration policy: $requested" >&2; return 1 ;;
  esac
}

clamp_int() {
  local value="$1" min="$2" max="$3"
  (( value < min )) && value="$min"
  (( value > max )) && value="$max"
  printf '%s' "$value"
}

resource_matrix_profile_gateways() {
  if [[ "$(opt_bool matrix)" != true ]]; then
    printf '0'
    return 0
  fi
  local count
  count="$(jq -r '[.workers[]? | select((.matrix.enabled // false) == true)] | length' install-options.json 2>/dev/null || true)"
  [[ "$count" =~ ^[0-9]+$ && "$count" -le 8 ]] || { echo 'Could not determine Matrix-enabled secondary profile count for adaptive resource planning.' >&2; return 1; }
  printf '%s' "$count"
}

resource_kanban_concurrency() {
  if [[ "$(opt_bool kanban)" != true ]]; then
    printf '1'
    return 0
  fi
  local count
  count="$(jq -r '.kanbanMaxInProgress // 2' install-options.json 2>/dev/null || true)"
  [[ "$count" =~ ^[0-9]+$ && "$count" -ge 1 && "$count" -le 8 ]] || { echo 'Could not determine Kanban concurrency for adaptive resource planning.' >&2; return 1; }
  printf '%s' "$count"
}

resource_hermes_floor_mib() {
  local matrix_gateways="$1" kanban_concurrency="$2" extra_gateways extra_kanban floor
  # The 1024 MiB baseline is the real-world-proven shape for the default gateway,
  # Dashboard/API overhead, up to one secondary Matrix gateway, and up to three
  # concurrent Kanban tasks. Scale only beyond that baseline so ordinary one/two-
  # profile installs retain the known-good v5-v7 balance while larger public setups
  # receive additional headroom inside the same aggregate budget.
  extra_gateways=$(( matrix_gateways > 1 ? matrix_gateways - 1 : 0 ))
  extra_kanban=$(( kanban_concurrency > 3 ? kanban_concurrency - 3 : 0 ))
  floor=$((1024 + extra_gateways*192 + extra_kanban*96))
  (( floor > 4096 )) && floor=4096
  printf '%s' "$floor"
}


ollama_model_manifest_mib() {
  local model="$1"
  [[ -n "$model" ]] || return 1
  python3 - "$PWD/data/ollama/models/manifests" "$model" <<'PY_OLLAMA_MANIFEST_SIZE'
from pathlib import Path
import json,sys
root=Path(sys.argv[1]); raw=sys.argv[2].strip()
if not raw or not root.is_dir(): raise SystemExit(1)
name,tag=raw,'latest'
last_slash=name.rfind('/')
last_colon=name.rfind(':')
if last_colon>last_slash:
    name,tag=name[:last_colon],name[last_colon+1:] or 'latest'
parts=[p for p in name.split('/') if p]
if not parts: raise SystemExit(1)
if len(parts)==1:
    expected=root/'registry.ollama.ai'/'library'/parts[0]/tag
elif '.' in parts[0] or ':' in parts[0] or parts[0]=='localhost':
    expected=root.joinpath(*parts,tag)
else:
    expected=root/'registry.ollama.ai'/Path(*parts)/tag
candidates=[]
if expected.is_file(): candidates.append(expected)
suffix=tuple(parts+[tag])
for f in root.rglob(tag):
    if not f.is_file() or f in candidates: continue
    fp=f.parts
    if len(fp)>=len(suffix) and tuple(fp[-len(suffix):])==suffix:
        candidates.append(f)
for manifest in candidates:
    try:
        data=json.loads(manifest.read_text(encoding='utf-8'))
        entries=[]
        cfg=data.get('config')
        if isinstance(cfg,dict): entries.append(cfg)
        entries.extend(x for x in (data.get('layers') or []) if isinstance(x,dict))
        total=sum(int(x.get('size') or 0) for x in entries)
        if total>0:
            print((total+1048575)//1048576)
            raise SystemExit(0)
    except (OSError,ValueError,TypeError,json.JSONDecodeError):
        continue
raise SystemExit(1)
PY_OLLAMA_MANIFEST_SIZE
}

resource_directml_selected() {
  if declare -F directml_text_enabled >/dev/null 2>&1; then
    directml_text_enabled
    return
  fi
  [[ -s install-options.json && ! -L install-options.json ]] || return 1
  jq -e '((.honcho // false) or (.hermesLocalAI // false)) and ((.localTextBackend // "ollama") == "directml")' install-options.json >/dev/null 2>&1
}

resource_ollama_context_length() {
  local accel="${1:-cpu}" context
  context="$(sed -n 's/^OLLAMA_CONTEXT_LENGTH=//p' .env 2>/dev/null | head -n1 || true)"
  if [[ "$context" =~ ^[0-9]+$ && "$context" -ge 1024 ]]; then
    printf '%s' "$context"
  elif resource_directml_selected; then
    # Ollama is the embedding/failure-fallback backend in DirectML mode. Keep its
    # emergency text context compact even on large hosts so the fallback does not
    # claim VRAM/RAM intended for the primary DirectML process.
    printf '4096'
  elif declare -F choose_ollama_context_length >/dev/null 2>&1; then
    choose_ollama_context_length "$accel"
  else
    local mem_mib ram_ctx gpu_metrics count min_mib max_mib total_mib coordination overhead directml_pct shared usable_max gpu_ctx
    mem_mib="$(awk '/^MemTotal:/ {print int($2/1024); exit}' /proc/meminfo 2>/dev/null || true)"
    [[ "$mem_mib" =~ ^[0-9]+$ && "$mem_mib" -gt 0 ]] || return 1
    ram_ctx="$(resource_ram_context_recommendation "$mem_mib")"
    if [[ "$accel" == nvidia || "$accel" == amd ]]; then
      gpu_metrics="$(ollama_gpu_metrics "$accel")" || return 1
      IFS=: read -r count min_mib max_mib total_mib <<<"$gpu_metrics"
      coordination="$(resource_gpu_coordination "$accel" "$count" "$min_mib" "$max_mib")" || return 1
      IFS=: read -r overhead directml_pct shared <<<"$coordination"
      usable_max=$((max_mib-overhead)); (( usable_max < 0 )) && usable_max=0
      gpu_ctx="$(resource_gpu_context_recommendation "$usable_max")"
      (( gpu_ctx < ram_ctx )) && ram_ctx="$gpu_ctx"
    fi
    printf '%s' "$ram_ctx"
  fi
}

resource_ollama_model_metrics() {
  local accel="$1" text_model embed_model text_mib=0 embed_mib=0 artifact_mib=0 context floor transient context_overhead host_model_mib hybrid=false
  local gpu_metrics count=0 min_vram=0 max_vram=0 total_vram=0 coordination overhead_mib=0 directml_pct=75 shared=false usable_max=0 usable_total=0
  managed_ollama_enabled || { printf '0:0:0:0\n'; return 0; }
  resource_directml_selected && hybrid=true
  text_model="$(opt_text localTextModel)"
  embed_model="$(opt_text localEmbeddingModel)"
  text_mib="$(ollama_model_manifest_mib "$text_model" 2>/dev/null || printf 0)"
  if [[ "$(opt_bool honcho)" == true ]]; then
    embed_mib="$(ollama_model_manifest_mib "$embed_model" 2>/dev/null || printf 0)"
  fi
  [[ "$text_mib" =~ ^[0-9]+$ ]] || text_mib=0
  [[ "$embed_mib" =~ ^[0-9]+$ ]] || embed_mib=0
  artifact_mib=$(( text_mib > embed_mib ? text_mib : embed_mib ))
  context="$(resource_ollama_context_length "$accel")" || return 1
  [[ "$context" =~ ^[0-9]+$ ]] || return 1
  if [[ "$accel" == cpu ]]; then
    if [[ "$hybrid" == true ]]; then
      floor=3072
      if (( artifact_mib > 0 )); then
        transient=$((artifact_mib/8)); (( transient < 512 )) && transient=512
        context_overhead=$(((context+31)/32)); (( context_overhead < 128 )) && context_overhead=128; (( context_overhead > 768 )) && context_overhead=768
        floor=$((artifact_mib+transient+context_overhead))
        floor=$((((floor+255)/256)*256))
        (( floor < 3072 )) && floor=3072
      fi
    else
      # Policy v11 lowers only the provisional CPU-Ollama floor. Once the selected
      # model exists on disk, its measured artifact/context requirement remains
      # authoritative and can raise the floor or make the topology impossible.
      floor=4096
      if (( artifact_mib > 0 )); then
        transient=$((artifact_mib/4)); (( transient < 1024 )) && transient=1024
        context_overhead=$(((context+15)/16)); (( context_overhead < 256 )) && context_overhead=256; (( context_overhead > 2048 )) && context_overhead=2048
        floor=$((artifact_mib+transient+context_overhead))
        floor=$((((floor+255)/256)*256))
        (( floor < 4096 )) && floor=4096
      fi
    fi
  else
    gpu_metrics="$(ollama_gpu_metrics "$accel")" || return 1
    IFS=: read -r count min_vram max_vram total_vram <<<"$gpu_metrics"
    coordination="$(resource_gpu_coordination "$accel" "$count" "$min_vram" "$max_vram")" || return 1
    IFS=: read -r overhead_mib directml_pct shared <<<"$coordination"
    usable_max=$((max_vram-overhead_mib)); (( usable_max < 0 )) && usable_max=0
    usable_total=$((total_vram-overhead_mib*count)); (( usable_total < 0 )) && usable_total=0
    host_model_mib=$((artifact_mib/4))
    if (( artifact_mib > 0 )); then
      if (( artifact_mib <= usable_max )); then
        # Ollama normally keeps a fitting model on one GPU.
        host_model_mib=$((artifact_mib/8))
      elif (( artifact_mib <= usable_total )); then
        # If it cannot fit one GPU, Ollama can spread it across available GPUs.
        host_model_mib=$((artifact_mib/8))
      else
        # Preserve RAM for the portion that cannot fit in the measured usable VRAM,
        # plus conservative host/runtime overhead.
        host_model_mib=$((artifact_mib-usable_total+artifact_mib/8))
      fi
    fi
    if [[ "$hybrid" == true ]]; then
      context_overhead=$(((context+63)/64)); (( context_overhead < 128 )) && context_overhead=128; (( context_overhead > 768 )) && context_overhead=768
      floor=$((1536+host_model_mib+context_overhead))
      floor=$((((floor+255)/256)*256))
      (( floor < 1536 )) && floor=1536
    else
      context_overhead=$(((context+31)/32)); (( context_overhead < 256 )) && context_overhead=256; (( context_overhead > 2048 )) && context_overhead=2048
      floor=$((2048+host_model_mib+context_overhead))
      floor=$((((floor+255)/256)*256))
      (( floor < 2048 )) && floor=2048
    fi
  fi
  printf '%s:%s:%s:%s\n' "$text_mib" "$embed_mib" "$context" "$floor"
}

write_resource_policy_report() {
  # Human-readable, secret-free support artifact. It is regenerated whenever the
  # canonical policy changes and again after managed Ollama offload verification.
  local report=resource-policy-report.txt state=.latticevale-resource-state verified acceleration gpu_verified
  local statev
  statev() { sed -n "s/^$1=//p" "$state" 2>/dev/null | head -n1; }
  if [[ ! -s "$state" || -L "$state" ]]; then
    {
      printf 'LatticeVale Resource Policy Report\n'
      printf 'Resource policy: disabled or not yet generated\n'
      printf 'Adaptive container ceilings: disabled\n'
      printf 'Generated by: LatticeVale v14.5.42\n'
    } > "$report"
    chmod 0644 "$report"
    return 0
  fi
  acceleration="$(statev OLLAMA_ACCELERATION)"
  verified="$(sed -n 's/^LATTICEVALE_OLLAMA_GPU_OFFLOAD_VERIFIED=//p' .env 2>/dev/null | head -n1)"
  if [[ "$acceleration" == nvidia || "$acceleration" == amd ]]; then
    if [[ "$verified" == "$acceleration" ]]; then gpu_verified=yes
    elif [[ "$verified" == cpu ]]; then gpu_verified=no
    else gpu_verified=pending
    fi
  else
    gpu_verified='not applicable (CPU-managed or native/external mode)'
  fi
  {
    printf 'LatticeVale Resource Policy Report\n'
    printf 'Generated by: LatticeVale v14.5.42\n'
    printf 'Resource policy: v%s\n' "$(statev POLICY_VERSION)"
    printf 'Hardware fingerprint: %s\n' "$(statev HARDWARE_FINGERPRINT)"
    printf 'Policy fingerprint: %s\n' "$(statev POLICY_FINGERPRINT)"
    printf 'WSL RAM: %s MiB (%s)\n' "$(statev MEM_MIB)" "$(statev RAM_PROFILE)"
    printf 'WSL CPUs: %s (%s)\n' "$(statev CPUS)" "$(statev CPU_PROFILE)"
    printf 'Container budget: %s MiB\n' "$(statev BUDGET_MIB)"
    printf 'Ollama mode: %s\n' "$acceleration"
    printf 'GPU execution verified: %s\n' "$gpu_verified"
    printf 'GPU count: %s\n' "$(statev GPU_COUNT)"
    printf 'GPU VRAM min/max/aggregate: %s/%s/%s MiB\n' "$(statev GPU_MIN_MIB)" "$(statev GPU_MAX_MIB)" "$(statev GPU_TOTAL_MIB)"
    printf 'GPU heterogeneous: %s\n' "$(statev GPU_HETEROGENEOUS)"
    printf 'Ollama GPU overhead: %s MiB per GPU\n' "$(statev OLLAMA_GPU_OVERHEAD_MIB)"
    printf 'DirectML enabled: %s\n' "$(statev DIRECTML_SELECTED)"
    printf 'DirectML GPU: %s / %s\n' "$(statev DIRECTML_GPU_VENDOR)" "$(statev DIRECTML_ADAPTER_NAME)"
    printf 'DirectML VRAM limit: %s%%\n' "$(statev DIRECTML_VRAM_LIMIT_PCT)"
    printf 'Shared Ollama/DirectML vendor envelope: %s\n' "$(statev GPU_SHARED_WITH_DIRECTML)"
    printf 'Ollama context length: %s\n' "$(statev OLLAMA_CONTEXT_LENGTH)"
    printf 'Ollama model floor: %s MiB\n' "$(statev OLLAMA_MODEL_FLOOR_MIB)"
    printf 'Hermes RAM limit: %s MiB\n' "$(statev LIMIT_HERMES_MIB)"
    printf 'Hermes CPU limit: %s milli-CPU\n' "$(statev CPU_HERMES_MILLI)"
    if [[ -n "$(statev LIMIT_OLLAMA_MIB)" ]]; then
      printf 'Ollama RAM limit: %s MiB\n' "$(statev LIMIT_OLLAMA_MIB)"
      printf 'Ollama CPU limit: %s milli-CPU\n' "$(statev CPU_OLLAMA_MILLI)"
    fi
    printf 'Note: this report contains installer-owned resource decisions only; it intentionally excludes secrets.\n'
  } > "$report"
  chmod 0644 "$report"
}

write_latticevale_compose_overlay() {
  local accel="$1" limits="$2" cpus mem_mib compose_files matrix_profile_gateways kanban_concurrency hermes_floor_mib ollama_metrics ollama_text_mib ollama_embed_mib ollama_context ollama_floor_mib
  local ram_profile cpu_profile gpu_metrics gpu_count=0 gpu_min_mib=0 gpu_max_mib=0 gpu_total_mib=0 gpu_coordination ollama_gpu_overhead_mib=0 directml_vram_limit_pct=75 gpu_shared_directml=false
  cpus="$(nproc 2>/dev/null || true)"
  [[ "$cpus" =~ ^[0-9]+$ && "$cpus" -ge 1 ]] || { echo 'Could not determine the CPU allocation currently visible to WSL; refusing to invent adaptive resource defaults.' >&2; return 1; }
  mem_mib="$(awk '/^MemTotal:/ {print int($2/1024); exit}' /proc/meminfo 2>/dev/null || true)"
  [[ "$mem_mib" =~ ^[0-9]+$ && "$mem_mib" -ge 512 ]] || { echo 'Could not determine the RAM allocation currently visible to WSL; refusing to invent adaptive resource defaults.' >&2; return 1; }
  matrix_profile_gateways="$(resource_matrix_profile_gateways)" || return 1
  kanban_concurrency="$(resource_kanban_concurrency)" || return 1
  hermes_floor_mib="$(resource_hermes_floor_mib "$matrix_profile_gateways" "$kanban_concurrency")" || return 1
  ollama_metrics="$(resource_ollama_model_metrics "$accel")" || return 1
  IFS=: read -r ollama_text_mib ollama_embed_mib ollama_context ollama_floor_mib <<<"$ollama_metrics"
  [[ "$ollama_text_mib" =~ ^[0-9]+$ && "$ollama_embed_mib" =~ ^[0-9]+$ && "$ollama_context" =~ ^[0-9]+$ && "$ollama_floor_mib" =~ ^[0-9]+$ ]] || { echo 'Could not determine model-aware Ollama resource metrics.' >&2; return 1; }
  ram_profile="$(resource_ram_profile "$mem_mib")"
  cpu_profile="$(resource_cpu_profile "$cpus")"
  if [[ "$accel" == nvidia || "$accel" == amd ]]; then
    gpu_metrics="$(ollama_gpu_metrics "$accel")" || { echo 'Could not inventory GPU VRAM for the selected managed Ollama acceleration path.' >&2; return 1; }
    IFS=: read -r gpu_count gpu_min_mib gpu_max_mib gpu_total_mib <<<"$gpu_metrics"
    gpu_coordination="$(resource_gpu_coordination "$accel" "$gpu_count" "$gpu_min_mib" "$gpu_max_mib")" || return 1
    IFS=: read -r ollama_gpu_overhead_mib directml_vram_limit_pct gpu_shared_directml <<<"$gpu_coordination"
  fi
  [[ "$gpu_count" =~ ^[0-9]+$ && "$gpu_min_mib" =~ ^[0-9]+$ && "$gpu_max_mib" =~ ^[0-9]+$ && "$gpu_total_mib" =~ ^[0-9]+$ && "$ollama_gpu_overhead_mib" =~ ^[0-9]+$ && "$directml_vram_limit_pct" =~ ^[0-9]+$ ]] || { echo 'Invalid GPU resource-policy metrics.' >&2; return 1; }
  set_env .env OLLAMA_GPU_OVERHEAD "$((ollama_gpu_overhead_mib*1048576))"
  set_env .env LATTICEVALE_OLLAMA_GPU_OVERHEAD_AUTO "$((ollama_gpu_overhead_mib*1048576))"
  set_env .env DIRECTML_VRAM_LIMIT_PCT "$directml_vram_limit_pct"

  # LatticeVale v14.3.32 resource policy: calculate one aggregate container-memory
  # budget from the RAM actually visible inside WSL, reserve headroom for the WSL
  # kernel/Docker/cache, then distribute only that budget across services that are
  # actually enabled. This avoids the old per-service percentage scheme whose
  # theoretical maxima could substantially overcommit a small WSL VM.
  local reserve_pct reserve_mib budget_mib
  # v14.5.1 resource policy v9: retain hard aggregate budgeting while sizing managed
  # Ollama from installed model artifacts + context when measurable. CPU-backed
  # Ollama on >6-12 GiB WSL VMs uses a bounded 10% non-container reserve so common
  # local models retain transient headroom without re-starving Hermes.
  # Other >6-24 GiB shapes keep 20%; <=6 GiB keeps the conservative 30% reserve.
  if (( mem_mib <= 6144 )); then
    reserve_pct=30
  elif (( mem_mib <= 12288 )) && [[ "$accel" == cpu ]] && managed_ollama_enabled && ! directml_text_enabled; then
    reserve_pct=10
  elif (( mem_mib <= 24576 )); then
    reserve_pct=20
  else
    reserve_pct=15
  fi
  reserve_mib=$((mem_mib*reserve_pct/100))
  (( reserve_mib < 768 )) && reserve_mib=768
  (( reserve_mib > 4096 )) && reserve_mib=4096
  # DirectML runs as a WSL-host process, but the normal non-container reserve
  # already exists for kernel/cache/host work. Policy v10 treats the DirectML
  # requirement as a floor on that reserve instead of ADDING a second reserve.
  # This removes several GiB of double-counted headroom on ordinary 8-12 GiB WSL
  # VMs while still keeping DirectML outside the Docker budget.
  local directml_reserve_mib=0
  if directml_text_enabled; then
    # DirectML is a WSL-host process, not a cgroup-limited Compose service. Unlike
    # the v14.5.2 topology it can also use shared GPU/system memory for staging.
    # Keep a bounded quarter of WSL RAM outside the container budget so model load
    # cannot consume the last host headroom and destabilize the WSL VM.
    directml_reserve_mib=$((mem_mib/4))
    (( directml_reserve_mib < 2048 )) && directml_reserve_mib=2048
    (( directml_reserve_mib > 4096 )) && directml_reserve_mib=4096
    (( reserve_mib < directml_reserve_mib )) && reserve_mib=$directml_reserve_mib
  fi
  budget_mib=$((mem_mib-reserve_mib))
  (( budget_mib >= 384 )) || { echo "WSL exposes only ${mem_mib} MiB RAM, leaving too little memory for a safe adaptive LatticeVale container budget." >&2; return 1; }

  local hermes_cpu heavy_cpu medium_cpu light_cpu ollama_cpu topology_cpu_pressure topology_cpu_bonus
  local malloc_arena_max synapse_cache_factor pg_shared_buffers
  hermes_cpu=$(((cpus*3+3)/4)); (( hermes_cpu < 1 )) && hermes_cpu=1; (( hermes_cpu > cpus )) && hermes_cpu=$cpus
  topology_cpu_pressure=$(( (matrix_profile_gateways > 1 ? matrix_profile_gateways - 1 : 0) + (kanban_concurrency > 3 ? kanban_concurrency - 3 : 0) ))
  if (( topology_cpu_pressure > 0 )); then
    topology_cpu_bonus=$(((topology_cpu_pressure+2)/3))
    hermes_cpu=$((hermes_cpu+topology_cpu_bonus))
    (( hermes_cpu > cpus )) && hermes_cpu=$cpus
  fi
  heavy_cpu=$cpus
  medium_cpu=$(((cpus+1)/2)); (( medium_cpu < 1 )) && medium_cpu=1
  light_cpu=$(((cpus+3)/4)); (( light_cpu < 1 )) && light_cpu=1
  if [[ "$accel" == cpu ]]; then ollama_cpu="$heavy_cpu"; else ollama_cpu="$medium_cpu"; fi
  # CPU ceilings are CFS quotas, not pinned cores or reservations. They scale from
  # the processors actually visible to this WSL process: Hermes starts near 75% and
  # scales toward 100% for profile/Kanban-heavy topologies; CPU-heavy Ollama gets
  # 100%, medium services ~50%, and light stores ~25% (minimum one CPU).
  # Policy v9 persists the generated per-service quota too, so clean/repair/start
  # can prove Docker actually consumed a changed WSL CPU allocation.
  declare -A cpu_limits=(
    [hermes]="$hermes_cpu"
    [synapse-db]="$medium_cpu" [synapse]="$medium_cpu"
    [searxng-valkey]="$light_cpu" [searxng]="$medium_cpu"
    [qmd]="$medium_cpu" [qmd-indexer]="$medium_cpu"
    [ollama]="$ollama_cpu"
    [honcho-db]="$medium_cpu" [honcho-redis]="$light_cpu"
    [honcho-api]="$medium_cpu" [honcho-deriver]="$medium_cpu"
  )

  # Conservative application-level RAM defaults layered on top of hard ceilings.
  # Synapse documents SYNAPSE_CACHE_FACTOR as its supported cache/RAM tradeoff.
  # PostgreSQL typically defaults shared_buffers to 128MB; 64MB is appropriate for
  # these local stores on smaller WSL VMs. MALLOC_ARENA_MAX limits glibc allocator
  # arenas and reduces RSS growth from fragmentation in long-lived Python services.
  if (( mem_mib <= 6144 )); then
    malloc_arena_max=2; synapse_cache_factor=0.25; pg_shared_buffers=64MB
  elif (( mem_mib <= 12288 )); then
    malloc_arena_max=2; synapse_cache_factor=0.35; pg_shared_buffers=64MB
  else
    malloc_arena_max=4; synapse_cache_factor=0.50; pg_shared_buffers=128MB
  fi

  declare -A mem_limits=()
  local resource_plan active_count=0
  if [[ "$limits" == true ]]; then
    resource_plan="$(python3 - "$budget_mib" \
      "$(opt_bool matrix)" "$(opt_bool searxng)" "$(opt_bool qmd)" \
      "$(if managed_ollama_enabled; then printf true; else printf false; fi)" "$(opt_bool honcho)" "$accel" "$hermes_floor_mib" "$ollama_floor_mib" \
      "$(if (( mem_mib <= 12288 )); then printf true; else printf false; fi)" <<'PY_RESOURCE_PLAN'
import sys
budget=int(sys.argv[1])
matrix=sys.argv[2]=='true'; searxng=sys.argv[3]=='true'; qmd=sys.argv[4]=='true'; ollama=sys.argv[5]=='true'; honcho=sys.argv[6]=='true'; accel=sys.argv[7]
hermes_floor=int(sys.argv[8]); requested_ollama_floor=int(sys.argv[9]); lowmem=(sys.argv[10]=='true') if len(sys.argv)>10 else False
if not 1024 <= hermes_floor <= 4096:
    raise SystemExit('Invalid adaptive Hermes topology floor.')
# name, weight, preferred minimum MiB, useful ceiling MiB
# Policy v9 scales the central container floor with persistent secondary Matrix
# gateways and high Kanban concurrency while keeping the proven common-case floor.
if lowmem:
    # <=12 GiB WSL profile: preserve the real-world-proven 1 GiB Hermes floor,
    # but tighten supporting-service minima/caps so a normal 16 GiB Windows PC
    # (typically ~8 GiB WSL by default) can run the selected stack without every
    # idle helper reserving workstation-class headroom.
    hermes_cap=max(2048,min(4096,hermes_floor+2048))
    specs=[('hermes',8,hermes_floor,hermes_cap)]
    if matrix: specs += [('synapse-db',2,160,768),('synapse',2,192,768)]
    if searxng: specs += [('searxng-valkey',1,64,256),('searxng',2,192,768)]
    if qmd: specs += [('qmd',2,192,1024),('qmd-indexer',2,192,1024)]
    if honcho: specs += [('honcho-db',2,192,768),('honcho-redis',1,64,256),('honcho-api',4,384,1024),('honcho-deriver',3,256,1024)]
else:
    hermes_cap=max(4096,min(8192,hermes_floor+4096))
    specs=[('hermes',8,hermes_floor,hermes_cap)]
    if matrix: specs += [('synapse-db',2,256,2048),('synapse',2,256,1536)]
    if searxng: specs += [('searxng-valkey',1,128,768),('searxng',2,256,1536)]
    if qmd: specs += [('qmd',2,256,2048),('qmd-indexer',2,256,2048)]
    if honcho: specs += [('honcho-db',2,256,2048),('honcho-redis',1,128,768),('honcho-api',4,512,3072),('honcho-deriver',3,384,3072)]
# Policy v9 retains the corrected Hermes balance while making managed-Ollama viability model-aware, but the central Hermes runtime
# now has a 1 GiB preferred floor and Honcho API gets 512 MiB. This is based on a
# real full-stack failure where Hermes repeatedly hit a 544 MiB cgroup limit while
# WSL still had multiple GiB available. The aggregate still stays within budget.
# Policy v9 treats these minima as viability requirements instead of proportionally
# crushing them when the selected service set cannot fit the managed budget.
if ollama:
    other_min_total=sum(m for _n,_w,m,_c in specs)
    ollama_floor=max(2048,requested_ollama_floor)
    ollama_cap=max(ollama_floor+1024,min(8192,ollama_floor+2048)) if lowmem else max(32768,min(65536,ollama_floor+8192))
    specs += [('ollama',12,ollama_floor,ollama_cap)]
mins={n:m for n,w,m,c in specs}; caps={n:c for n,w,m,c in specs}; weights={n:w for n,w,m,c in specs}
alloc={n:0 for n,_,_,_ in specs}
min_total=sum(mins.values())
if min_total > budget:
    # Policy v9 never turns a selected service set into superficially valid but
    # implausibly tiny hard ceilings. The enabled set must fit its defined safe
    # minima inside the managed budget; otherwise the user can increase WSL RAM,
    # deselect services, use native-Windows Ollama, or disable LatticeVale ceilings.
    enabled=", ".join(n for n,_,_,_ in specs)
    print(
        f"Adaptive resource policy v11 cannot safely fit the selected services: "
        f"budget={budget}MiB, minimum={min_total}MiB, services={enabled}. "
        "Increase WSL-visible RAM, deselect components, use native-Windows Ollama where appropriate, "
        "or disable adaptive container ceilings.",
        file=sys.stderr,
    )
    raise SystemExit(3)
alloc.update(mins)
remaining=budget-min_total
# Weighted water-fill until all remaining budget is assigned or useful caps are hit.
while remaining >= 16:
    open_names=[n for n in alloc if alloc[n]+16 <= caps[n]]
    if not open_names: break
    total_w=sum(weights[n] for n in open_names)
    progressed=False
    for n in sorted(open_names,key=lambda x:weights[x],reverse=True):
        if remaining < 16: break
        share=max(16,int((remaining*weights[n]/total_w)//16)*16)
        add=min(share,caps[n]-alloc[n],remaining)
        add=(add//16)*16
        if add>=16:
            alloc[n]+=add; remaining-=add; progressed=True
    if not progressed: break
for n,_,_,_ in specs:
    print(f'{n}={alloc[n]}')
PY_RESOURCE_PLAN
)" || return 1
    while IFS='=' read -r svc mib; do
      [[ -n "$svc" && "$mib" =~ ^[0-9]+$ ]] || continue
      mem_limits["$svc"]="$mib"; active_count=$((active_count+1))
    done <<<"$resource_plan"
    (( active_count > 0 )) || { echo 'Adaptive resource planner produced no active services.' >&2; return 1; }
  fi

  # Policy v11 canonicalization: after hardware/topology/model planning completes,
  # freeze every installer-owned resource decision into one associative policy object.
  # Compose, persisted state, diagnostics, and later consistency checks consume these
  # exact values; none of those emitters independently re-derive service ceilings.
  declare -A resource_policy=(
    [POLICY_VERSION]=11
    [CPUS]="$cpus" [CPU_PROFILE]="$cpu_profile"
    [MEM_MIB]="$mem_mib" [RAM_PROFILE]="$ram_profile"
    [RESERVE_MIB]="$reserve_mib" [DIRECTML_HOST_RESERVE_MIB]="$directml_reserve_mib"
    [LOW_MEMORY_PROFILE]="$(if (( mem_mib <= 12288 )); then printf 1; else printf 0; fi)"
    [BUDGET_MIB]="$budget_mib" [MATRIX_PROFILE_GATEWAYS]="$matrix_profile_gateways"
    [KANBAN_CONCURRENCY]="$kanban_concurrency" [HERMES_MIN_MIB]="$hermes_floor_mib"
    [OLLAMA_ACCELERATION]="$accel" [GPU_COUNT]="$gpu_count"
    [GPU_MIN_MIB]="$gpu_min_mib" [GPU_MAX_MIB]="$gpu_max_mib" [GPU_TOTAL_MIB]="$gpu_total_mib"
    [GPU_HETEROGENEOUS]="$(if (( gpu_count > 1 && gpu_min_mib != gpu_max_mib )); then printf true; else printf false; fi)"
    [OLLAMA_GPU_OVERHEAD_MIB]="$ollama_gpu_overhead_mib" [DIRECTML_VRAM_LIMIT_PCT]="$directml_vram_limit_pct"
    [GPU_SHARED_WITH_DIRECTML]="$gpu_shared_directml"
    [DIRECTML_SELECTED]="$(if resource_directml_selected; then printf true; else printf false; fi)"
    [DIRECTML_GPU_VENDOR]="$(opt_text directmlGpuVendor 2>/dev/null || true)"
    [DIRECTML_ADAPTER_NAME]="$(opt_text directmlAdapterName 2>/dev/null || true)"
    [OLLAMA_TEXT_ARTIFACT_MIB]="$ollama_text_mib" [OLLAMA_EMBED_ARTIFACT_MIB]="$ollama_embed_mib"
    [OLLAMA_CONTEXT_LENGTH]="$ollama_context" [OLLAMA_MODEL_FLOOR_MIB]="$ollama_floor_mib"
    [MALLOC_ARENA_MAX]="$malloc_arena_max" [SYNAPSE_CACHE_FACTOR]="$synapse_cache_factor"
    [POSTGRES_SHARED_BUFFERS]="$pg_shared_buffers"
  )
  local resource_state_svc resource_state_key
  for resource_state_svc in hermes synapse-db synapse searxng-valkey searxng qmd qmd-indexer ollama honcho-db honcho-redis honcho-api honcho-deriver; do
    [[ -n "${mem_limits[$resource_state_svc]:-}" ]] || continue
    resource_state_key="${resource_state_svc^^}"; resource_state_key="${resource_state_key//-/_}"
    resource_policy["LIMIT_${resource_state_key}_MIB"]="${mem_limits[$resource_state_svc]}"
    resource_policy["CPU_${resource_state_key}_MILLI"]="${cpu_limits[$resource_state_svc]}000"
  done
  local hardware_material policy_material
  hardware_material="CPUS=${resource_policy[CPUS]}|MEM_MIB=${resource_policy[MEM_MIB]}|OLLAMA_ACCELERATION=${resource_policy[OLLAMA_ACCELERATION]}|GPU_COUNT=${resource_policy[GPU_COUNT]}|GPU_MIN_MIB=${resource_policy[GPU_MIN_MIB]}|GPU_MAX_MIB=${resource_policy[GPU_MAX_MIB]}|GPU_TOTAL_MIB=${resource_policy[GPU_TOTAL_MIB]}|DIRECTML_SELECTED=${resource_policy[DIRECTML_SELECTED]}|DIRECTML_GPU_VENDOR=${resource_policy[DIRECTML_GPU_VENDOR]}|DIRECTML_ADAPTER_NAME=${resource_policy[DIRECTML_ADAPTER_NAME]}"
  resource_policy[HARDWARE_FINGERPRINT]="$(printf '%s' "$hardware_material" | sha256sum | awk '{print $1}')"
  policy_material="$(for resource_state_key in "${!resource_policy[@]}"; do printf '%s=%s\n' "$resource_state_key" "${resource_policy[$resource_state_key]}"; done | LC_ALL=C sort)"
  resource_policy[POLICY_FINGERPRINT]="$(printf '%s\n' "$policy_material" | sha256sum | awk '{print $1}')"

  # From this point onward, resource_policy[] is the only installer-owned source
  # for emitted resource limits/tuning. This prevents planner/Compose/state drift.
  rm -f compose.latticevale.yaml
  if [[ "$limits" == true || "$accel" != cpu ]]; then
    {
      echo 'services:'
      if [[ "$limits" == true ]]; then
        printf '  hermes:\n    cpus: "%s"\n    mem_limit: "%sm"\n    environment:\n      MALLOC_ARENA_MAX: "%s"\n' "$((${resource_policy[CPU_HERMES_MILLI]}/1000))" "${resource_policy[LIMIT_HERMES_MIB]}" "${resource_policy[MALLOC_ARENA_MAX]}"
        if [[ "$(opt_bool matrix)" == true ]]; then
          printf '  synapse-db:\n    cpus: "%s"\n    mem_limit: "%sm"\n    command: ["postgres", "-c", "shared_buffers=%s"]\n' "$((${resource_policy[CPU_SYNAPSE_DB_MILLI]}/1000))" "${resource_policy[LIMIT_SYNAPSE_DB_MIB]}" "${resource_policy[POSTGRES_SHARED_BUFFERS]}"
          printf '  synapse:\n    cpus: "%s"\n    mem_limit: "%sm"\n    environment:\n      MALLOC_ARENA_MAX: "%s"\n      SYNAPSE_CACHE_FACTOR: "%s"\n' "$((${resource_policy[CPU_SYNAPSE_MILLI]}/1000))" "${resource_policy[LIMIT_SYNAPSE_MIB]}" "${resource_policy[MALLOC_ARENA_MAX]}" "${resource_policy[SYNAPSE_CACHE_FACTOR]}"
        fi
        if [[ "$(opt_bool searxng)" == true ]]; then
          printf '  searxng-valkey:\n    cpus: "%s"\n    mem_limit: "%sm"\n' "$((${resource_policy[CPU_SEARXNG_VALKEY_MILLI]}/1000))" "${resource_policy[LIMIT_SEARXNG_VALKEY_MIB]}"
          printf '  searxng:\n    cpus: "%s"\n    mem_limit: "%sm"\n' "$((${resource_policy[CPU_SEARXNG_MILLI]}/1000))" "${resource_policy[LIMIT_SEARXNG_MIB]}"
        fi
        if [[ "$(opt_bool qmd)" == true ]]; then
          printf '  qmd:\n    cpus: "%s"\n    mem_limit: "%sm"\n' "$((${resource_policy[CPU_QMD_MILLI]}/1000))" "${resource_policy[LIMIT_QMD_MIB]}"
          printf '  qmd-indexer:\n    cpus: "%s"\n    mem_limit: "%sm"\n' "$((${resource_policy[CPU_QMD_INDEXER_MILLI]}/1000))" "${resource_policy[LIMIT_QMD_INDEXER_MIB]}"
        fi
        if managed_ollama_enabled; then
          printf '  ollama:\n    cpus: "%s"\n    mem_limit: "%sm"\n' "$((${resource_policy[CPU_OLLAMA_MILLI]}/1000))" "${resource_policy[LIMIT_OLLAMA_MIB]}"
          if [[ "$accel" == nvidia ]]; then
            printf '    deploy:\n      resources:\n        reservations:\n          devices:\n            - driver: nvidia\n              count: all\n              capabilities: [gpu]\n'
          elif [[ "$accel" == amd ]]; then
            printf '    devices:\n      - /dev/kfd:/dev/kfd\n      - /dev/dri:/dev/dri\n'
            local dev gid amd_gids=() seen_gids=' '
            for dev in /dev/kfd /dev/dri/card* /dev/dri/renderD*; do
              [[ -e "$dev" ]] || continue
              gid="$(stat -c '%g' -- "$dev" 2>/dev/null || true)"
              [[ "$gid" =~ ^[0-9]+$ ]] || continue
              [[ "$seen_gids" == *" $gid "* ]] && continue
              amd_gids+=("$gid"); seen_gids+="$gid "
            done
            if (( ${#amd_gids[@]} > 0 )); then
              echo '    group_add:'
              for gid in "${amd_gids[@]}"; do printf '      - "%s"\n' "$gid"; done
            fi
          fi
        fi
        if [[ "$(opt_bool honcho)" == true ]]; then
          printf '  honcho-db:\n    cpus: "%s"\n    mem_limit: "%sm"\n    command: ["postgres", "-c", "max_connections=200", "-c", "shared_buffers=%s"]\n' "$((${resource_policy[CPU_HONCHO_DB_MILLI]}/1000))" "${resource_policy[LIMIT_HONCHO_DB_MIB]}" "${resource_policy[POSTGRES_SHARED_BUFFERS]}"
          printf '  honcho-redis:\n    cpus: "%s"\n    mem_limit: "%sm"\n' "$((${resource_policy[CPU_HONCHO_REDIS_MILLI]}/1000))" "${resource_policy[LIMIT_HONCHO_REDIS_MIB]}"
          printf '  honcho-api:\n    cpus: "%s"\n    mem_limit: "%sm"\n    environment:\n      MALLOC_ARENA_MAX: "%s"\n' "$((${resource_policy[CPU_HONCHO_API_MILLI]}/1000))" "${resource_policy[LIMIT_HONCHO_API_MIB]}" "${resource_policy[MALLOC_ARENA_MAX]}"
          printf '  honcho-deriver:\n    cpus: "%s"\n    mem_limit: "%sm"\n    environment:\n      MALLOC_ARENA_MAX: "%s"\n' "$((${resource_policy[CPU_HONCHO_DERIVER_MILLI]}/1000))" "${resource_policy[LIMIT_HONCHO_DERIVER_MIB]}" "${resource_policy[MALLOC_ARENA_MAX]}"
        fi
      elif managed_ollama_enabled; then
        echo '  ollama:'
        if [[ "$accel" == nvidia ]]; then
          printf '    deploy:\n      resources:\n        reservations:\n          devices:\n            - driver: nvidia\n              count: all\n              capabilities: [gpu]\n'
        elif [[ "$accel" == amd ]]; then
          printf '    devices:\n      - /dev/kfd:/dev/kfd\n      - /dev/dri:/dev/dri\n'
          local dev gid amd_gids=() seen_gids=' '
          for dev in /dev/kfd /dev/dri/card* /dev/dri/renderD*; do
            [[ -e "$dev" ]] || continue
            gid="$(stat -c '%g' -- "$dev" 2>/dev/null || true)"
            [[ "$gid" =~ ^[0-9]+$ ]] || continue
            [[ "$seen_gids" == *" $gid "* ]] && continue
            amd_gids+=("$gid"); seen_gids+="$gid "
          done
          if (( ${#amd_gids[@]} > 0 )); then
            echo '    group_add:'
            for gid in "${amd_gids[@]}"; do printf '      - "%s"\n' "$gid"; done
          fi
        fi
      fi
    } > compose.latticevale.yaml
    chmod 0644 compose.latticevale.yaml
  fi
  compose_files='compose.yaml'
  [[ -s compose.latticevale.yaml ]] && compose_files+=':compose.latticevale.yaml'
  [[ -s compose.override.yaml ]] && compose_files+=':compose.override.yaml'
  set_env .env COMPOSE_FILE "$compose_files"
  if [[ "$limits" == true ]]; then
    {
      # Keep POLICY_VERSION=11 first for human readability and compatibility with
      # older repair diagnostics, while every value still comes from the canonical object.
      printf 'POLICY_VERSION=%s\n' "${resource_policy[POLICY_VERSION]}"
      for resource_state_key in "${!resource_policy[@]}"; do
        [[ "$resource_state_key" == POLICY_VERSION ]] && continue
        printf '%s=%s\n' "$resource_state_key" "${resource_policy[$resource_state_key]}"
      done | LC_ALL=C sort
    } > .latticevale-resource-state
    chmod 0600 .latticevale-resource-state
    echo "Adaptive container ceilings (policy v11): WSL CPUs=${resource_policy[CPUS]} (${resource_policy[CPU_PROFILE]}), RAM=${resource_policy[MEM_MIB]}MiB (${resource_policy[RAM_PROFILE]}), reserved=${resource_policy[RESERVE_MIB]}MiB (DirectML host reserve=${resource_policy[DIRECTML_HOST_RESERVE_MIB]}MiB), container budget=${resource_policy[BUDGET_MIB]}MiB across ${active_count} enabled services; Hermes topology floor=${resource_policy[HERMES_MIN_MIB]}MiB for ${resource_policy[MATRIX_PROFILE_GATEWAYS]} secondary Matrix gateway(s) and Kanban concurrency ${resource_policy[KANBAN_CONCURRENCY]}; managed Ollama model-aware floor=${resource_policy[OLLAMA_MODEL_FLOOR_MIB]}MiB (text artifact=${resource_policy[OLLAMA_TEXT_ARTIFACT_MIB]}MiB, embedding artifact=${resource_policy[OLLAMA_EMBED_ARTIFACT_MIB]}MiB, context=${resource_policy[OLLAMA_CONTEXT_LENGTH]}); GPU inventory=${resource_policy[GPU_COUNT]} adapter(s), min/max/aggregate=${resource_policy[GPU_MIN_MIB]}/${resource_policy[GPU_MAX_MIB]}/${resource_policy[GPU_TOTAL_MIB]}MiB, heterogeneous=${resource_policy[GPU_HETEROGENEOUS]}, OLLAMA_GPU_OVERHEAD=${resource_policy[OLLAMA_GPU_OVERHEAD_MIB]}MiB per GPU, DirectML VRAM limit=${resource_policy[DIRECTML_VRAM_LIMIT_PCT]}%, shared-vendor=${resource_policy[GPU_SHARED_WITH_DIRECTML]}; hardware fingerprint=${resource_policy[HARDWARE_FINGERPRINT]}; policy fingerprint=${resource_policy[POLICY_FINGERPRINT]}; user compose.override.yaml is applied last."
  else
    rm -f .latticevale-resource-state
    echo 'Adaptive container ceilings: disabled; any existing user compose.override.yaml remains authoritative.'
  fi
  write_resource_policy_report
  echo "Ollama acceleration resolved: $accel"
}

verify_adaptive_runtime_policy() {
  [[ "$(opt_bool containerResourceLimits)" == true ]] || return 0
  local cpus mem_mib compose_selector overlay accel ollama_metrics current_text_mib current_embed_mib current_ollama_context current_ollama_floor
  local matrix_gateways kanban_concurrency hermes_floor directml_reserve=0 lowmem=0 ram_profile cpu_profile
  local gpu_metrics gpu_count=0 gpu_min=0 gpu_max=0 gpu_total=0 gpu_coord overhead=0 directml_pct=75 shared=false heterogeneous=false
  local directml_selected=false directml_vendor directml_adapter hardware_material hardware_fingerprint policy_fingerprint actual_policy_fingerprint
  cpus="$(nproc 2>/dev/null || true)"
  mem_mib="$(awk '/^MemTotal:/ {print int($2/1024); exit}' /proc/meminfo 2>/dev/null || true)"
  [[ "$cpus" =~ ^[0-9]+$ && "$cpus" -ge 1 && "$mem_mib" =~ ^[0-9]+$ && "$mem_mib" -ge 512 ]] || return 1
  [[ -s .latticevale-resource-state && ! -L .latticevale-resource-state ]] || return 1
  statev() { sed -n "s/^$1=//p" .latticevale-resource-state 2>/dev/null | head -n1; }
  ram_profile="$(resource_ram_profile "$mem_mib")"; cpu_profile="$(resource_cpu_profile "$cpus")"
  (( mem_mib <= 12288 )) && lowmem=1
  matrix_gateways="$(resource_matrix_profile_gateways)" || return 1
  kanban_concurrency="$(resource_kanban_concurrency)" || return 1
  hermes_floor="$(resource_hermes_floor_mib "$matrix_gateways" "$kanban_concurrency")" || return 1
  if resource_directml_selected; then
    directml_selected=true
    if (( mem_mib <= 8192 )); then directml_reserve=1536
    elif (( mem_mib <= 12288 )); then directml_reserve=1792
    elif (( mem_mib <= 16384 )); then directml_reserve=2048
    elif (( mem_mib <= 24576 )); then directml_reserve=2560
    else directml_reserve=3072
    fi
  fi
  accel=cpu; if managed_ollama_enabled; then accel="$(resolve_ollama_acceleration)" || return 1; fi
  if [[ "$accel" == nvidia || "$accel" == amd ]]; then
    gpu_metrics="$(ollama_gpu_metrics "$accel")" || return 1
    IFS=: read -r gpu_count gpu_min gpu_max gpu_total <<<"$gpu_metrics"
    gpu_coord="$(resource_gpu_coordination "$accel" "$gpu_count" "$gpu_min" "$gpu_max")" || return 1
    IFS=: read -r overhead directml_pct shared <<<"$gpu_coord"
  fi
  (( gpu_count > 1 && gpu_min != gpu_max )) && heterogeneous=true
  directml_vendor="$(opt_text directmlGpuVendor 2>/dev/null || true)"
  directml_adapter="$(opt_text directmlAdapterName 2>/dev/null || true)"
  hardware_material="CPUS=$cpus|MEM_MIB=$mem_mib|OLLAMA_ACCELERATION=$accel|GPU_COUNT=$gpu_count|GPU_MIN_MIB=$gpu_min|GPU_MAX_MIB=$gpu_max|GPU_TOTAL_MIB=$gpu_total|DIRECTML_SELECTED=$directml_selected|DIRECTML_GPU_VENDOR=$directml_vendor|DIRECTML_ADAPTER_NAME=$directml_adapter"
  hardware_fingerprint="$(printf '%s' "$hardware_material" | sha256sum | awk '{print $1}')"
  policy_fingerprint="$(statev POLICY_FINGERPRINT)"
  actual_policy_fingerprint="$(grep -v '^POLICY_FINGERPRINT=' .latticevale-resource-state | LC_ALL=C sort | sha256sum | awk '{print $1}')"
  [[ -n "$policy_fingerprint" && "$policy_fingerprint" == "$actual_policy_fingerprint" ]] || return 1
  ollama_metrics="$(resource_ollama_model_metrics "$accel")" || return 1
  IFS=: read -r current_text_mib current_embed_mib current_ollama_context current_ollama_floor <<<"$ollama_metrics"
  [[ "$(statev POLICY_VERSION)" == 11 && "$(statev CPUS)" == "$cpus" && "$(statev CPU_PROFILE)" == "$cpu_profile" && \
     "$(statev MEM_MIB)" == "$mem_mib" && "$(statev RAM_PROFILE)" == "$ram_profile" && \
     "$(statev DIRECTML_HOST_RESERVE_MIB)" == "$directml_reserve" && "$(statev LOW_MEMORY_PROFILE)" == "$lowmem" && \
     "$(statev MATRIX_PROFILE_GATEWAYS)" == "$matrix_gateways" && "$(statev KANBAN_CONCURRENCY)" == "$kanban_concurrency" && \
     "$(statev HERMES_MIN_MIB)" == "$hermes_floor" && "$(statev OLLAMA_ACCELERATION)" == "$accel" && \
     "$(statev GPU_COUNT)" == "$gpu_count" && "$(statev GPU_MIN_MIB)" == "$gpu_min" && "$(statev GPU_MAX_MIB)" == "$gpu_max" && \
     "$(statev GPU_TOTAL_MIB)" == "$gpu_total" && "$(statev GPU_HETEROGENEOUS)" == "$heterogeneous" && "$(statev OLLAMA_GPU_OVERHEAD_MIB)" == "$overhead" && \
     "$(statev DIRECTML_VRAM_LIMIT_PCT)" == "$directml_pct" && "$(statev GPU_SHARED_WITH_DIRECTML)" == "$shared" && \
     "$(statev DIRECTML_SELECTED)" == "$directml_selected" && "$(statev DIRECTML_GPU_VENDOR)" == "$directml_vendor" && \
     "$(statev DIRECTML_ADAPTER_NAME)" == "$directml_adapter" && "$(statev HARDWARE_FINGERPRINT)" == "$hardware_fingerprint" && \
     "$(statev OLLAMA_TEXT_ARTIFACT_MIB)" == "$current_text_mib" && "$(statev OLLAMA_EMBED_ARTIFACT_MIB)" == "$current_embed_mib" && \
     "$(statev OLLAMA_CONTEXT_LENGTH)" == "$current_ollama_context" && "$(statev OLLAMA_MODEL_FLOOR_MIB)" == "$current_ollama_floor" ]] || return 1
  [[ -s compose.latticevale.yaml && ! -L compose.latticevale.yaml ]] || return 1
  [[ -s resource-policy-report.txt && ! -L resource-policy-report.txt ]] || return 1
  grep -Fq "Policy fingerprint: $policy_fingerprint" resource-policy-report.txt || return 1
  grep -Fq "Hardware fingerprint: $hardware_fingerprint" resource-policy-report.txt || return 1
  overlay="$(cat compose.latticevale.yaml 2>/dev/null)" || return 1
  grep -q 'MALLOC_ARENA_MAX:' <<<"$overlay" || return 1
  if [[ "$(opt_bool matrix)" == true ]]; then
    grep -q 'SYNAPSE_CACHE_FACTOR:' <<<"$overlay" || return 1
    grep -q 'shared_buffers=' <<<"$overlay" || return 1
  fi
  if [[ "$(opt_bool honcho)" == true ]]; then
    grep -q 'max_connections=200' <<<"$overlay" || return 1
    grep -q 'shared_buffers=' <<<"$overlay" || return 1
  fi
  compose_selector="$(sed -n 's/^COMPOSE_FILE=//p' .env 2>/dev/null | head -n1)"
  [[ ":$compose_selector:" == *':compose.latticevale.yaml:'* ]] || return 1
  return 0
}

verify_live_resource_policy_limits() {
  [[ "$(opt_bool containerResourceLimits)" == true ]] || return 0
  [[ -s .latticevale-resource-state && ! -L .latticevale-resource-state ]] || return 1
  command -v docker >/dev/null 2>&1 || return 1

  # Compare against the EFFECTIVE Compose model, not merely LatticeVale's generated
  # overlay, because compose.override.yaml is user-owned and deliberately applied last.
  # Policy v9 proves an existing container consumed both current mem_limit and cpus
  # while preserving user overrides as authoritative.
  local effective_limits
  effective_limits="$(timeout --foreground --kill-after=3s 15s docker compose config --format json 2>/dev/null | python3 -c '
import json,re,sys
try: data=json.load(sys.stdin)
except Exception: raise SystemExit(2)
def size_bytes(v):
    if isinstance(v,(int,float)): return int(v)
    s=str(v or "").strip().lower()
    if not s: return 0
    if s.isdigit(): return int(s)
    m=re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b?)",s)
    if not m: return 0
    n=float(m.group(1)); u=m.group(2)
    mult={"":1,"b":1,"k":1024,"kb":1024,"ki":1024,"kib":1024,"m":1024**2,"mb":1024**2,"mi":1024**2,"mib":1024**2,"g":1024**3,"gb":1024**3,"gi":1024**3,"gib":1024**3,"t":1024**4,"tb":1024**4,"ti":1024**4,"tib":1024**4}.get(u,0)
    return int(n*mult) if mult else 0
def cpu_nanos(v):
    try: return int(round(float(v or 0)*1_000_000_000))
    except Exception: return 0
for name,cfg in (data.get("services") or {}).items():
    cfg=cfg or {}
    print(f"{name}={size_bytes(cfg.get('"'"'mem_limit'"'"'))}:{cpu_nanos(cfg.get('"'"'cpus'"'"'))}")
')" || return 1

  local -a resource_pairs=("hermes:hermes-agent")
  [[ "$(opt_bool matrix)" == true ]] && resource_pairs+=("synapse-db:hermes-synapse-db" "synapse:hermes-synapse")
  [[ "$(opt_bool searxng)" == true ]] && resource_pairs+=("searxng-valkey:hermes-searxng-valkey" "searxng:hermes-searxng")
  [[ "$(opt_bool qmd)" == true ]] && resource_pairs+=("qmd:hermes-qmd" "qmd-indexer:hermes-qmd-indexer")
  managed_ollama_enabled && resource_pairs+=("ollama:hermes-ollama")
  [[ "$(opt_bool honcho)" == true ]] && resource_pairs+=("honcho-db:hermes-honcho-db" "honcho-redis:hermes-honcho-redis" "honcho-api:hermes-honcho-api" "honcho-deriver:hermes-honcho-deriver")

  local pair service container expected_pair expected_bytes expected_nano actual_pair actual_bytes actual_nano
  for pair in "${resource_pairs[@]}"; do
    service="${pair%%:*}"; container="${pair#*:}"
    expected_pair="$(sed -n "s/^${service}=//p" <<<"$effective_limits" | head -n1)"
    expected_bytes="${expected_pair%%:*}"; expected_nano="${expected_pair#*:}"
    [[ "$expected_bytes" =~ ^[0-9]+$ && "$expected_bytes" -gt 0 ]] || {
      echo "Adaptive resource verification failed: effective Compose mem_limit for $service is missing or invalid." >&2
      return 1
    }
    [[ "$expected_nano" =~ ^[0-9]+$ && "$expected_nano" -gt 0 ]] || {
      echo "Adaptive resource verification failed: effective Compose cpus for $service is missing or invalid." >&2
      return 1
    }
    actual_pair="$(timeout --foreground --kill-after=2s 8s docker inspect -f '{{.HostConfig.Memory}}:{{.HostConfig.NanoCpus}}' "$container" 2>/dev/null || true)"
    actual_bytes="${actual_pair%%:*}"; actual_nano="${actual_pair#*:}"
    [[ "$actual_bytes" =~ ^[0-9]+$ && "$actual_nano" =~ ^[0-9]+$ ]] || {
      echo "Adaptive resource verification failed: selected container $container is not available for live CPU/RAM verification." >&2
      return 1
    }
    if [[ "$actual_bytes" != "$expected_bytes" ]]; then
      echo "Adaptive resource verification failed: $container is still using $actual_bytes memory bytes instead of effective Compose limit $expected_bytes bytes. Compose reconciliation is required." >&2
      return 1
    fi
    if [[ "$actual_nano" != "$expected_nano" ]]; then
      echo "Adaptive resource verification failed: $container is still using $actual_nano NanoCPUs instead of effective Compose CPU limit $expected_nano NanoCPUs. Compose reconciliation is required." >&2
      return 1
    fi
  done
  return 0
}

repair_runtime_policy_reconcile() {
  [[ "$(opt_bool containerResourceLimits)" == true ]] || return 0
  if verify_adaptive_runtime_policy; then
    echo 'Adaptive runtime/RAM policy is already current.'
    return 0
  fi
  local accel=cpu
  if managed_ollama_enabled; then accel="$(resolve_ollama_acceleration)" || return 1; fi
  echo 'Adaptive runtime/RAM policy is stale or incomplete; regenerating the installer-owned overlay from the CPU/RAM currently visible to WSL.'
  write_latticevale_compose_overlay "$accel" true
  verify_adaptive_runtime_policy || { echo 'Adaptive runtime/RAM policy regeneration completed but failed live verification.' >&2; return 1; }
  # The overlay is persistent configuration, but existing containers do not consume
  # changed mem_limit/environment/command values until Compose reconciles them. Mark
  # the owning runtime stages pending so Resume / repair cannot report success with a
  # correct file on disk but stale live containers.
  state_mark infrastructure pending 'adaptive runtime/RAM policy changed; selected infrastructure containers require Compose reconciliation'
  state_mark reconcile pending 'adaptive runtime/RAM policy changed; complete stack requires Compose reconciliation'
}

choose_ollama_context_length() {
  # Policy v11 sizes the automatic context from both WSL RAM and the *usable* VRAM
  # of the largest eligible managed-Ollama GPU.  Compact (<=8 GiB) hosts use 4096,
  # and GPU-backed installs take the smaller RAM/VRAM recommendation.  User-owned
  # OLLAMA_CONTEXT_LENGTH values are still preserved by the caller.
  local accel="${1:-cpu}" mem_mib ram_ctx gpu_metrics count min_mib max_mib total_mib
  local coordination overhead directml_pct shared usable_max gpu_ctx
  mem_mib="$(awk '/^MemTotal:/ {print int($2/1024); exit}' /proc/meminfo 2>/dev/null || true)"
  [[ "$mem_mib" =~ ^[0-9]+$ && "$mem_mib" -gt 0 ]] || { echo 'Could not determine WSL memory for automatic Ollama context sizing; refusing to assume a default allocation.' >&2; return 1; }
  ram_ctx="$(resource_ram_context_recommendation "$mem_mib")"
  if [[ "$accel" == nvidia || "$accel" == amd ]]; then
    gpu_metrics="$(ollama_gpu_metrics "$accel")" || { echo "Could not inventory $accel VRAM for automatic Ollama context sizing." >&2; return 1; }
    IFS=: read -r count min_mib max_mib total_mib <<<"$gpu_metrics"
    coordination="$(resource_gpu_coordination "$accel" "$count" "$min_mib" "$max_mib")" || return 1
    IFS=: read -r overhead directml_pct shared <<<"$coordination"
    usable_max=$((max_mib-overhead)); (( usable_max < 0 )) && usable_max=0
    gpu_ctx="$(resource_gpu_context_recommendation "$usable_max")"
    (( gpu_ctx < ram_ctx )) && ram_ctx="$gpu_ctx"
  fi
  printf '%s' "$ram_ctx"
}

assert_docker_namespace_safe() {
  local name project network_label working_dir attached_id attached_project attached_dir
  local expected_dir owned_anchor=false
  expected_dir="$(pwd -P)"
  local containers=(
    hermes-agent hermes-synapse-db hermes-synapse hermes-searxng-valkey hermes-searxng
    hermes-qmd hermes-qmd-indexer hermes-ollama hermes-honcho-db hermes-honcho-redis
    hermes-honcho-api hermes-honcho-deriver hermes-tailscale hermes-tailscale-matrix
  )
  for name in "${containers[@]}"; do
    timeout --foreground --kill-after=5s 15s docker inspect "$name" >/dev/null 2>&1 || continue
    project="$(timeout --foreground --kill-after=5s 15s docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$name" 2>/dev/null || true)"
    working_dir="$(timeout --foreground --kill-after=5s 15s docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$name" 2>/dev/null || true)"
    if [[ "$project" != hermesstack || -z "$working_dir" || "$(realpath -m -- "$working_dir")" != "$expected_dir" ]]; then
      echo "Docker container name '$name' already exists but belongs to another or unprovable Compose working directory. Expected '$expected_dir'; found project='$project' working_dir='${working_dir:-missing}'. Refusing to remove or replace it." >&2
      return 1
    fi
    owned_anchor=true
  done
  for name in hermes-backend hermes-edge; do
    timeout --foreground --kill-after=5s 15s docker network inspect "$name" >/dev/null 2>&1 || continue
    project="$(timeout --foreground --kill-after=5s 15s docker network inspect -f '{{ index .Labels "com.docker.compose.project" }}' "$name" 2>/dev/null || true)"
    network_label="$(timeout --foreground --kill-after=5s 15s docker network inspect -f '{{ index .Labels "com.docker.compose.network" }}' "$name" 2>/dev/null || true)"
    if [[ "$project" != hermesstack || -z "$network_label" ]]; then
      echo "Docker network '$name' already exists but is not owned by the hermesstack Compose project. Refusing to reuse a foreign network." >&2
      return 1
    fi
    mapfile -t attached_ids < <(timeout --foreground --kill-after=5s 15s docker network inspect "$name" 2>/dev/null | jq -r '.[0].Containers // {} | keys[]')
    if ((${#attached_ids[@]} == 0)) && [[ "$owned_anchor" != true ]]; then
      echo "Docker network '$name' already exists but no container proves that it belongs to '$expected_dir'. Refusing to reuse an ambiguous pre-existing network." >&2
      return 1
    fi
    for attached_id in "${attached_ids[@]}"; do
      attached_project="$(timeout --foreground --kill-after=5s 15s docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$attached_id" 2>/dev/null || true)"
      attached_dir="$(timeout --foreground --kill-after=5s 15s docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$attached_id" 2>/dev/null || true)"
      if [[ "$attached_project" != hermesstack || -z "$attached_dir" || "$(realpath -m -- "$attached_dir")" != "$expected_dir" ]]; then
        echo "Docker network '$name' is attached to a container from another or unprovable Compose working directory. Refusing to reuse it." >&2
        return 1
      fi
    done
  done
}

ollama_model_present() {
  local model="$1"
  if windows_native_ollama_enabled; then
    local base
    base="$(native_ollama_ready_base_url)" || return 2
    timeout --foreground --kill-after=5s 30s python3 - "$base" "$model" <<'PY_NATIVE_TAGS'
import json,sys,urllib.request
base=sys.argv[1].rstrip('/'); wanted=sys.argv[2]
with urllib.request.urlopen(base+'/api/tags', timeout=10) as r:
    payload=json.load(r)
for item in payload.get('models',[]):
    name=str(item.get('name') or item.get('model') or '')
    if name==wanted or (':' not in wanted and name.startswith(wanted+':')):
        raise SystemExit(0)
raise SystemExit(1)
PY_NATIVE_TAGS
  else
    # The Docker/Ollama CLI can block indefinitely if the daemon or WSL transport is
    # unhealthy. Every non-interactive readiness command in this stage is bounded.
    timeout --foreground --kill-after=5s 30s docker compose exec -T ollama ollama list 2>/dev/null \
      | awk 'NR>1 {print $1}' | grep -Fxq "$model"
  fi
}

ensure_ollama_model() {
  local model="$1"
  [[ -n "$model" ]] || { echo 'Local Ollama model name is empty.' >&2; return 1; }
  local present_rc=0
  if ollama_model_present "$model"; then
    echo "Ollama model already present: $model"
    return 0
  else
    present_rc=$?
  fi
  if windows_native_ollama_enabled && (( present_rc == 2 )); then
    echo "Native Windows Ollama became unavailable while checking model '$model'; model validation will not misreport this as a missing model." >&2
    return 1
  fi
  echo "Downloading Ollama model: $model"
  echo 'Model download has a 60-minute safety timeout; rerunning Resume / repair continues safely if the network stalls.'
  if windows_native_ollama_enabled; then
    local base rc=0
    base="$(native_ollama_ready_base_url)" || { echo 'Could not establish native Windows Ollama through the WSL relay.' >&2; return 1; }
    timeout --foreground --kill-after=15s 3600s python3 - "$base" "$model" <<'PY_NATIVE_PULL' || rc=$?
import json,sys,urllib.request
base=sys.argv[1].rstrip('/'); model=sys.argv[2]
body=json.dumps({'model':model,'stream':False}).encode('utf-8')
req=urllib.request.Request(base+'/api/pull',data=body,headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(req,timeout=3550) as r:
    payload=json.load(r)
status=str(payload.get('status','')) if isinstance(payload,dict) else ''
if status and status not in ('success',''): print(status)
PY_NATIVE_PULL
    if (( rc != 0 )); then
      echo "Native Windows Ollama model download failed or exceeded its safety timeout for '$model' (exit $rc)." >&2
      return "$rc"
    fi
  else
    if timeout --foreground --kill-after=15s 3600s docker compose exec -T ollama ollama pull "$model"; then
      :
    else
      rc=$?
      echo "Ollama model download failed or exceeded its safety timeout for '$model' (exit $rc)." >&2
      return "$rc"
    fi
  fi
  if ! ollama_model_present "$model"; then
    echo "Ollama reported the pull operation complete, but '$model' is still not listed by the selected backend. Resume / repair can retry after checking the Ollama model store and network." >&2
    return 1
  fi
  echo "Ollama model ready: $model"
}

unload_ollama_model() {
  local model="$1"
  if windows_native_ollama_enabled; then
    local base
    base="$(ollama_api_base_url 2>/dev/null || true)"
    [[ -n "$base" ]] || return 0
    timeout --foreground --kill-after=5s 30s python3 - "$base" "$model" <<'PY_NATIVE_UNLOAD' >/dev/null 2>&1 || true
import json,sys,urllib.request
base=sys.argv[1].rstrip('/'); model=sys.argv[2]
body=json.dumps({'model':model,'keep_alive':0}).encode('utf-8')
req=urllib.request.Request(base+'/api/generate',data=body,headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(req,timeout=20) as r: r.read(1024)
PY_NATIVE_UNLOAD
  else
    timeout --foreground --kill-after=5s 30s docker compose exec -T ollama ollama stop "$model" >/dev/null 2>&1 || true
  fi
}

managed_ollama_processor_class() {
  # Load the selected model once, then use Ollama's own PROCESSOR report as the
  # runtime truth.  Device discovery alone is not accepted as proof of GPU offload.
  # Output: gpu, cpu, or unknown.  Any CPU/GPU split counts as GPU-backed because
  # the resource policy only needs proof that an accelerator is actually in use.
  local model="$1" ps_output processor_line result=unknown
  managed_ollama_enabled || { printf 'unknown\n'; return 0; }
  if ! timeout --foreground --kill-after=15s 240s docker compose exec -T ollama ollama run "$model" 'Reply with OK only.' >/dev/null 2>&1; then
    printf 'unknown\n'
    return 0
  fi
  ps_output="$(timeout --foreground --kill-after=5s 30s docker compose exec -T ollama ollama ps 2>/dev/null || true)"
  processor_line="$(printf '%s\n' "$ps_output" | awk -v wanted="$model" 'NR>1 && ($1==wanted || ($1 ~ ("^" wanted ":") && wanted !~ /:/)) {print; exit}')"
  [[ -n "$processor_line" ]] || processor_line="$(printf '%s\n' "$ps_output" | awk 'NR>1 {print; exit}')"
  if [[ "$processor_line" == *GPU* ]]; then result=gpu
  elif [[ "$processor_line" == *CPU* ]]; then result=cpu
  fi
  unload_ollama_model "$model"
  printf '%s\n' "$result"
}

verify_or_rebudget_managed_ollama_acceleration() {
  local accel="$1" model="$2" requested processor metrics old_auto current_context cpu_context
  [[ "$accel" == nvidia || "$accel" == amd ]] || return 0
  echo "Verifying managed Ollama $accel offload with Ollama's live PROCESSOR report."
  processor="$(managed_ollama_processor_class "$model")"
  case "$processor" in
    gpu)
      clear_ollama_gpu_fallback
      set_env .env LATTICEVALE_OLLAMA_GPU_OFFLOAD_VERIFIED "$accel"
      write_resource_policy_report
      echo "Managed Ollama runtime verification passed: $model is using GPU offload."
      return 0
      ;;
    cpu)
      requested="$(opt_text ollamaAcceleration)"; [[ -n "$requested" ]] || requested=cpu
      if [[ "$requested" != auto ]]; then
        echo "Ollama $accel acceleration was explicitly selected, but Ollama reports CPU execution for '$model'. Refusing to retain GPU-sized resource assumptions. Choose Auto/CPU or repair the GPU runtime." >&2
        return 1
      fi
      metrics="$(ollama_gpu_metrics "$accel" 2>/dev/null || true)"
      [[ -n "$metrics" ]] || { echo 'Ollama fell back to CPU and the GPU fingerprint could not be recorded safely.' >&2; return 1; }
      mark_ollama_gpu_fallback "$accel" "$metrics" || return 1
      set_env .env LATTICEVALE_OLLAMA_ACCELERATION cpu
      set_env .env LATTICEVALE_OLLAMA_GPU_OFFLOAD_VERIFIED cpu
      old_auto="$(sed -n 's/^LATTICEVALE_OLLAMA_CONTEXT_AUTO=//p' .env | head -n1)"
      current_context="$(sed -n 's/^OLLAMA_CONTEXT_LENGTH=//p' .env | head -n1)"
      cpu_context="$(choose_ollama_context_length cpu)" || return 1
      if [[ -z "$current_context" || ( -n "$old_auto" && "$current_context" == "$old_auto" ) ]]; then
        set_env .env OLLAMA_CONTEXT_LENGTH "$cpu_context"
      fi
      set_env .env LATTICEVALE_OLLAMA_CONTEXT_AUTO "$cpu_context"
      echo "Auto-selected $accel was detected but Ollama executed on CPU. Re-budgeting this hardware/runtime fingerprint as CPU; a driver/kernel/VRAM fingerprint change will retry GPU acceleration."
      write_latticevale_compose_overlay cpu "$(opt_bool containerResourceLimits)" || return 1
      timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build ollama || return 1
      wait_managed_ollama_healthy 60 || return 1
      return 0
      ;;
    *)
      echo "Ollama $accel acceleration was selected, but LatticeVale could not prove GPU offload from a bounded 'ollama ps' PROCESSOR check for '$model'. Refusing unverified GPU-sized resource assumptions." >&2
      return 1
      ;;
  esac
}

verify_honcho_embedding_model() {
  local model="$1" rc=0 base host_ip
  echo "Verifying Honcho embedding model '$model' can return 1536 dimensions (4-minute safety timeout)."

  # Native Windows Ollama is already verified from the selected WSL distro before
  # model validation. Do not require a Compose network that may not exist yet on a
  # fresh/resumed install: validate the exact OpenAI-compatible endpoint directly
  # through the verified WSL relay. Honcho container reachability is verified later
  # when its infrastructure is started on the real Compose networks.
  if windows_native_ollama_enabled; then
    base="$(native_ollama_ready_base_url)" || { echo 'Could not establish native Windows Ollama through the verified WSL relay.' >&2; return 1; }
    base="${base%/}/v1"
    timeout --foreground --kill-after=15s 240s python3 - "$model" "$base" <<'PY_NATIVE_OLLAMA_EMBED_CHECK' || rc=$?
import json,sys,urllib.request
model=sys.argv[1]; base=sys.argv[2].rstrip('/')
body=json.dumps({
    'model':model,
    'input':'Hermes local Honcho embedding compatibility check',
    'dimensions':1536,
    'encoding_format':'float',
}).encode('utf-8')
req=urllib.request.Request(
    base+'/embeddings',
    data=body,
    headers={'Content-Type':'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload=json.load(resp)
    vector=payload['data'][0]['embedding']
    if not isinstance(vector,list) or len(vector)!=1536:
        raise RuntimeError(f'expected 1536 dimensions, received {len(vector) if isinstance(vector,list) else "non-vector output"}')
except Exception as exc:
    print(f"Native Ollama embedding verification failed for {model}: {exc}", file=sys.stderr)
    print('Honcho requires an Ollama embedding model that succeeds through /v1/embeddings with dimensions=1536.', file=sys.stderr)
    print('The model does not need to be downloaded manually; LatticeVale pulls missing selected models through the native Ollama API.', file=sys.stderr)
    print('Rerun the installer and choose Resume / repair after correcting Ollama/model availability.', file=sys.stderr)
    raise SystemExit(1)
print(f'Honcho embedding verification passed through native Windows Ollama: {model} -> 1536 dimensions.')
PY_NATIVE_OLLAMA_EMBED_CHECK
  else
    base="$(ollama_openai_base_url)"
    host_ip="$(windows_host_ip 2>/dev/null || printf '127.0.0.1')"
    timeout --foreground --kill-after=15s 240s docker run --rm -i --network hermes-backend \
      --add-host "windows.host:${host_ip}" \
      --entrypoint /app/.venv/bin/python hermes-honcho:local - "$model" "$base" <<'PY_OLLAMA_EMBED_CHECK' || rc=$?
import json,sys,urllib.request
model=sys.argv[1]; base=sys.argv[2].rstrip('/')
body=json.dumps({
    'model':model,
    'input':'Hermes local Honcho embedding compatibility check',
    'dimensions':1536,
    'encoding_format':'float',
}).encode('utf-8')
req=urllib.request.Request(
    base+'/embeddings',
    data=body,
    headers={'Content-Type':'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload=json.load(resp)
    vector=payload['data'][0]['embedding']
    if not isinstance(vector,list) or len(vector)!=1536:
        raise RuntimeError(f'expected 1536 dimensions, received {len(vector) if isinstance(vector,list) else "non-vector output"}')
except Exception as exc:
    print(f"Local embedding verification failed for {model}: {exc}", file=sys.stderr)
    print('Honcho requires an Ollama embedding model that succeeds through /v1/embeddings with dimensions=1536.', file=sys.stderr)
    print('Rerun the installer and choose Resume / repair after correcting Ollama/model availability.', file=sys.stderr)
    raise SystemExit(1)
print(f'Honcho embedding verification passed: {model} -> 1536 dimensions.')
PY_OLLAMA_EMBED_CHECK
  fi

  unload_ollama_model "$model"
  if (( rc != 0 )); then
    if (( rc == 124 || rc == 137 )); then
      echo "Embedding verification exceeded the 4-minute safety timeout for '$model'. The installer stopped this check instead of hanging indefinitely." >&2
    fi
    return "$rc"
  fi
}

read_yes_no() {
  local prompt="$1" default="${2:-yes}" answer suffix
  [[ "$default" == yes ]] && suffix='[Y/n]' || suffix='[y/N]'
  while true; do
    read -r -p "$prompt $suffix " answer
    [[ -z "$answer" ]] && [[ "$default" == yes ]] && return 0
    [[ -z "$answer" ]] && return 1
    case "${answer,,}" in y|yes) return 0;; n|no) return 1;; *) echo 'Enter Y or N.' >&2;; esac
  done
}

hermes_model_configured() {
  local cfg="$1"
  [[ -s "$cfg" ]] || return 1
  python3 - "$cfg" <<'PY_MODEL_CHECK'
from pathlib import Path
import sys,yaml
try:
    cfg=yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8')) or {}
except Exception:
    raise SystemExit(1)
model=cfg.get('model')
ok=isinstance(model,dict) and isinstance(model.get('default'),str) and bool(model['default'].strip())
raise SystemExit(0 if ok else 1)
PY_MODEL_CHECK
}

hash_dashboard_password() {
  # Match Hermes BasicAuthProvider's documented scrypt format so no plaintext
  # dashboard password is ever written to disk. Password bytes arrive on stdin.
  python3 -c 'import base64,hashlib,secrets,sys; p=sys.stdin.buffer.read(); salt=secrets.token_bytes(16); dk=hashlib.scrypt(p,salt=salt,n=2**14,r=8,p=1,dklen=32,maxmem=0); print(f"scrypt${2**14}$8$1${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}")'
}

require_secret() {
  local prompt="$1" value
  while true; do
    read -r -s -p "$prompt: " value; echo >&2
    if [[ -n "$value" && "$value" != *$'\n'* && "$value" != *$'\r'* ]]; then printf '%s' "$value"; return 0; fi
    echo 'A non-empty, single-line value is required.' >&2
  done
}

read_password_twice() {
  local label="$1" first second
  while true; do
    first="$(require_secret "$label")"
    second="$(require_secret "Repeat $label")"
    if [[ "$first" == "$second" && ${#first} -ge 12 ]]; then printf '%s' "$first"; return 0; fi
    echo 'Passwords must match and contain at least 12 characters.' >&2
  done
}

read_env_file_value_optional() {
  # Optional state files are intentionally absent during some first-run/resume paths.
  # Avoid sed|head here: with set -o pipefail, a missing file makes sed return 2 and
  # can abort the entire installer before the caller gets to apply its fallback.
  local file="$1" key="$2" line
  [[ -r "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    case "$line" in
      "$key="*) printf '%s' "${line#*=}"; return 0 ;;
    esac
  done < "$file"
  return 0
}

set_env() {
  local file="$1" key="$2" value="$3"
  python3 - "$file" "$key" "$value" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); key=sys.argv[2]; value=sys.argv[3]
if '\n' in value or '\r' in value: raise SystemExit('environment values must be one line')
lines=p.read_text(encoding='utf-8').splitlines() if p.exists() else []
out=[]; done=False
for line in lines:
    if line.startswith(key+'='):
        if not done: out.append(f'{key}={value}'); done=True
    else: out.append(line)
if not done: out.append(f'{key}={value}')
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text('\n'.join(out)+'\n',encoding='utf-8')
PY
}

quote_env_key_literal() {
  # Compose interpolates $NAME in unquoted env-file values. Dashboard scrypt
  # hashes contain '$', so store that value single-quoted per Docker env-file
  # syntax. This preserves the exact hash without requiring a newer Compose.
  local file="$1" key="$2"
  python3 - "$file" "$key" <<'PY_ENV_LITERAL'
from pathlib import Path
import sys
p=Path(sys.argv[1]); key=sys.argv[2]
if not p.exists(): raise SystemExit(0)
lines=p.read_text(encoding='utf-8').splitlines(); out=[]
for line in lines:
    if line.startswith(key+'='):
        value=line[len(key)+1:]
        if len(value)>=2 and value[0]=="'" and value[-1]=="'":
            out.append(line); continue
        if "'" in value or '\n' in value or '\r' in value:
            raise SystemExit(f'{key} cannot be safely encoded as a literal env-file value')
        out.append(f"{key}='{value}'")
    else:
        out.append(line)
p.write_text('\n'.join(out)+('\n' if out else ''),encoding='utf-8')
PY_ENV_LITERAL
}

remove_env_keys() {
  local file="$1"; shift
  [[ -f "$file" ]] || return 0
  python3 - "$file" "$@" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); keys=set(sys.argv[2:])
lines=p.read_text(encoding='utf-8').splitlines()
lines=[line for line in lines if not any(line.startswith(k+'=') for k in keys)]
p.write_text('\n'.join(lines)+('\n' if lines else ''),encoding='utf-8')
PY
}


apply_matrix_runtime_env() {
  # secrets/matrix-bot.env may also retain installer-only recovery material such
  # as MATRIX_BOT_PASSWORD. Copy only variables Hermes itself consumes so the
  # preferred access-token authentication remains unambiguous. Missing optional
  # values (notably MATRIX_RECOVERY_KEY on older identities) must not become the
  # function exit status: live integration verification decides whether required
  # Matrix runtime settings are actually present. MATRIX_RECOVERY_KEY_OUTPUT_FILE
  # is intentionally excluded because it is one-time bootstrap state and is
  # removed after recovery-key capture.
  local source="${1:-secrets/matrix-bot.env}" key value
  [[ -s "$source" ]] || return 1
  for key in MATRIX_HOMESERVER MATRIX_ACCESS_TOKEN MATRIX_USER_ID MATRIX_ALLOWED_USERS MATRIX_ALLOWED_ROOMS MATRIX_E2EE_MODE MATRIX_DEVICE_ID MATRIX_RECOVERY_KEY; do
    value="$(sed -n "s/^${key}=//p" "$source" | head -n1)"
    if [[ -n "$value" ]]; then
      set_env data/hermes/.env "$key" "$value"
    fi
  done
  # Hermes v2026.8.16 supports native Matrix/Element reaction controls for
  # approval/model-picker prompts. Keep them enabled and sender-bound by default.
  set_env data/hermes/.env MATRIX_REACTIONS true
  set_env data/hermes/.env MATRIX_APPROVAL_REQUIRE_SENDER true
  return 0
}

wait_http() {
  local name="$1" url="$2" tries="${3:-60}" i
  for i in $(seq 1 "$tries"); do curl -fsS --connect-timeout 3 --max-time 5 "$url" >/dev/null 2>&1 && return 0; sleep 2; done
  echo "$name did not become healthy at $url." >&2; return 1
}

qmd_health_ok() {
  timeout --foreground --kill-after=5s 15s docker exec hermes-qmd curl -fsS --connect-timeout 3 --max-time 5 http://127.0.0.1:8181/health >/dev/null 2>&1
}

recycle_hermes_bounded() {
  # Matrix cross-signing changes Hermes' on-disk runtime environment. Avoid
  # `docker compose restart hermes` here: Compose restart can remain stuck while
  # waiting for the container to stop and, per Docker's documented behavior,
  # restart does not recreate a service to pick up Compose-level configuration
  # changes. LatticeVale instead performs a bounded, ownership-checked recycle.
  local reason="${1:-configuration reload}" expected_dir project working_dir
  expected_dir="$(pwd -P)"

  if timeout --foreground --kill-after=5s 15s docker inspect hermes-agent >/dev/null 2>&1; then
    project="$(timeout --foreground --kill-after=5s 15s docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' hermes-agent 2>/dev/null || true)"
    working_dir="$(timeout --foreground --kill-after=5s 15s docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' hermes-agent 2>/dev/null || true)"
    if [[ "$project" != hermesstack || -z "$working_dir" || "$(realpath -m -- "$working_dir")" != "$expected_dir" ]]; then
      echo "Refusing to recycle hermes-agent for $reason because Docker ownership cannot be proven for '$expected_dir'." >&2
      return 1
    fi

    echo "Reloading Hermes for $reason (graceful stop limited to 10 seconds)."
    if ! timeout --foreground --kill-after=5s 20s docker stop --time 10 hermes-agent >/dev/null 2>&1; then
      echo 'Hermes did not stop within the bounded grace period; forcing removal of only the LatticeVale-owned hermes-agent container.' >&2
    fi
    # Bind-mounted profile/Matrix/session state lives under ./data/hermes, so
    # removing this installer-owned container does not remove persistent state.
    if ! timeout --foreground --kill-after=5s 20s docker rm -f hermes-agent >/dev/null 2>&1; then
      echo 'Could not remove the old hermes-agent container after the bounded stop attempt.' >&2
      return 1
    fi
  else
    echo "Starting Hermes for $reason."
  fi

  if ! timeout --foreground --kill-after=10s 90s docker compose up -d --pull never --no-build --no-deps hermes >/dev/null; then
    echo "Hermes failed to start after the bounded $reason recycle." >&2
    return 1
  fi

  echo 'Waiting up to 60 seconds for Hermes to become command-ready.'
  local i
  for i in $(seq 1 30); do
    if timeout --foreground --kill-after=5s 10s docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Hermes did not become command-ready after the bounded $reason recycle." >&2
  timeout --foreground --kill-after=5s 15s docker inspect -f 'state={{.State.Status}} exit={{.State.ExitCode}} restarts={{.RestartCount}}' hermes-agent 2>/dev/null >&2 || true
  timeout --foreground --kill-after=5s 15s docker logs --tail 80 hermes-agent 2>&1 >&2 || true
  return 1
}

wait_qmd_health() {
  local tries="${1:-60}" i
  for i in $(seq 1 "$tries"); do qmd_health_ok && return 0; sleep 2; done
  echo 'QMD did not become healthy on its Docker-internal health endpoint.' >&2
  return 1
}

timezone="$(opt_text timezone)"
if [[ -z "$timezone" || "$timezone" == *".."* || ! -f "/usr/share/zoneinfo/$timezone" ]]; then
  echo "Invalid IANA timezone '$timezone'. Use a value such as America/Los_Angeles, Europe/London, or Etc/UTC." >&2
  exit 3
fi
if [[ "$(opt_bool tailscaleDashboard)" == true && ( "$(opt_bool tailscale)" != true || "$(opt_bool dashboard)" != true ) ]]; then
  echo 'Invalid options: Windows Tailscale Dashboard exposure requires both Tailscale integration and Dashboard.' >&2; exit 3
fi
if [[ "$(opt_bool tailscaleMatrix)" == true && ( "$(opt_bool tailscale)" != true || "$(opt_bool matrix)" != true ) ]]; then
  echo 'Invalid options: Windows Tailscale Matrix exposure requires both Tailscale integration and Matrix.' >&2; exit 3
fi
if local_ai_enabled; then
  local_text_model="$(opt_text localTextModel)"
  [[ -n "$local_text_model" ]] || { echo 'Invalid options: localTextModel is required because Ollama remains the fallback/embedding backend.' >&2; exit 3; }
  if directml_text_enabled; then
    [[ -x ./directml-gateway.sh && -f ./directml-gateway.py && -f ./directml-requirements.txt ]] || { echo 'Invalid bundle: DirectML gateway files are missing.' >&2; exit 3; }
    [[ -n "$(directml_text_model)" ]] || { echo 'Invalid options: directmlTextModel is required for DirectML.' >&2; exit 3; }
  fi
fi
if [[ "$(opt_bool honcho)" == true ]]; then
  local_embedding_model="$(opt_text localEmbeddingModel)"
  [[ -n "$local_embedding_model" ]] || { echo 'Invalid options: localEmbeddingModel is required when Honcho is selected.' >&2; exit 3; }
fi

# Current Hermes images recursively chown several HERMES_HOME subtrees at startup.
# Refuse symlinks at those ownership roots so a customized/partial install cannot
# redirect container startup ownership changes outside the dedicated data volume.
assert_hermes_chown_targets_safe() {
  local target rel
  if [[ -L data/hermes ]]; then
    echo "Unsafe Hermes data path: '$PWD/data/hermes' is a symbolic link. Replace it with a real directory before continuing." >&2
    return 1
  fi
  for rel in cron sessions logs hooks memories skills skins plans workspace home profiles platforms/pairing; do
    target="data/hermes/$rel"
    if [[ -L "$target" ]]; then
      echo "Unsafe Hermes ownership target: '$target' is a symbolic link. Current Hermes container startup recursively changes ownership at this path, so the installer will not follow it." >&2
      return 1
    fi
  done
}
assert_hermes_chown_targets_safe

INSTALLER_VERSION="$(opt_text installerVersion)"
[[ "$INSTALLER_VERSION" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || { echo 'Invalid or missing installerVersion in install-options.json.' >&2; exit 3; }
repair_maintenance_enabled() {
  [[ "$(opt_bool repairMaintenance)" == true && "$(opt_text installerMode)" != fresh ]]
}

repair_package_refresh_pending() {
  repair_maintenance_enabled && [[ -f .repair-package-refresh-pending && ! -L .repair-package-refresh-pending ]]
}

complete_repair_package_refresh() {
  repair_package_refresh_pending || return 0
  local now tmp policy_revision
  now="$(date +%s)"
  policy_revision="$(sed -n 's/^POLICY_REVISION=//p' .repair-package-refresh-pending 2>/dev/null | head -n1 || true)"
  [[ "$policy_revision" =~ ^[0-9]+$ && "$policy_revision" -ge 1 ]] || { echo 'Cannot finalize managed package/image refresh: pending refresh marker has an invalid policy revision.' >&2; return 1; }
  tmp=".repair-package-refresh.tmp.$$"
  printf 'LAST_SUCCESS_EPOCH=%s\nPOLICY_REVISION=%s\nINSTALLER_VERSION=%s\n' "$now" "$policy_revision" "$INSTALLER_VERSION" > "$tmp"
  chmod 0600 "$tmp"
  mv -f -- "$tmp" .repair-package-refresh
  rm -f .repair-package-refresh-pending
  if [[ "$(opt_bool forceManagedUpdate)" == true ]]; then
    echo 'Explicit Update / repair managed package/image/source refresh completed. Future ordinary repairs return to the normal age-gated refresh policy.'
  else
    echo 'Managed package/image/source refresh completed; ordinary repairs return to the periodic compatibility.conf age/policy gate. A bundle-version change alone does not force another managed component refresh.'
  fi
}

bytes_human() {
  python3 - "$1" <<'PY_BYTES_HUMAN'
import sys
try: n=float(sys.argv[1])
except Exception: n=0
units=['B','KiB','MiB','GiB','TiB']
i=0
while n>=1024 and i<len(units)-1:
    n/=1024; i+=1
print(f'{n:.1f} {units[i]}')
PY_BYTES_HUMAN
}

root_free_bytes() {
  df -Pk / | awk 'NR==2 {print $4*1024}'
}

show_repair_storage_report() {
  local free_bytes stack_kib
  local -a report_paths=(data backups workspace vendor)
  free_bytes="$(root_free_bytes 2>/dev/null || echo 0)"
  # Never let an informational repair report walk an external DrvFs/Obsidian mount.
  # `du -x` stays on the WSL root filesystem even if an interrupted legacy bind mount
  # is still active below the stack. Keep diagnostics tightly bounded so repair does
  # not appear hung on large databases/backups.
  stack_kib="$(timeout --foreground --kill-after=2s 8s du -skx . 2>/dev/null | awk '{print $1}' || true)"
  echo "WSL root free space: $(bytes_human "${free_bytes:-0}")"
  if [[ "$stack_kib" =~ ^[0-9]+$ ]]; then echo "LatticeVale stack footprint on WSL filesystem (external mounts excluded): $(bytes_human "$((stack_kib*1024))")"; fi
  echo 'Largest persistent LatticeVale paths on the WSL filesystem (informational; none are deleted by repair):'
  [[ "$(opt_bool obsidian)" == true ]] || report_paths+=(vault)
  timeout --foreground --kill-after=2s 10s du -shx -- "${report_paths[@]}" 2>/dev/null | sort -hr | head -n 12 || true
  echo 'Docker storage summary:'
  timeout --foreground --kill-after=2s 10s docker system df 2>/dev/null || true
}

prune_old_installer_config_backups() {
  # bootstrap.sh creates small configuration-only pre-version backups. Keep the eight
  # newest. User-created ./manage.sh backup snapshots have timestamp-only names and are
  # deliberately outside this pattern.
  local -a dirs=()
  local d
  while IFS= read -r d; do
    [[ -n "$d" ]] || continue
    # Current bootstrap names are pre-<version>-YYYYMMDDTHHMMSSZ. Restrict deletion
    # to that exact installer-owned shape so similarly named user folders are preserved.
    [[ "$(basename -- "$d")" =~ ^pre-[A-Za-z0-9._-]+-[0-9]{8}T[0-9]{6}Z$ ]] || continue
    # Name shape alone is not proof of ownership. Only prune directories carrying
    # the installer-created configuration snapshot, and refuse symlinked archives.
    [[ -f "$d/installer-config.tar.gz" && ! -L "$d/installer-config.tar.gz" ]] || continue
    dirs+=("$d")
  done < <(
    find backups -mindepth 1 -maxdepth 1 -type d -name 'pre-*' -printf '%T@ %p\n' 2>/dev/null | sort -nr | cut -d' ' -f2-
  )
  if ((${#dirs[@]} > 8)); then
    for d in "${dirs[@]:8}"; do
      rm -rf -- "$d"
      echo "Removed superseded installer configuration backup: $d"
    done
  fi
}

cap_installer_event_log() {
  local f=logs/installer-events.jsonl bytes tmp
  [[ -f "$f" ]] || return 0
  bytes="$(stat -c '%s' "$f" 2>/dev/null || echo 0)"
  if [[ "$bytes" =~ ^[0-9]+$ && "$bytes" -gt 10485760 ]]; then
    tmp="${f}.trim.$$"
    tail -n 5000 "$f" > "$tmp"
    chmod 0600 "$tmp"
    mv -f "$tmp" "$f"
    echo 'Trimmed the installer-owned event history to its newest 5,000 records.'
  fi
}

repair_storage_maintenance() {
  repair_maintenance_enabled || return 0
  echo 'Repair maintenance preserves Matrix/Postgres data, Hermes profiles/memory/sessions, QMD data, Ollama models, vault/workspace files, credentials, and user backups.'
  show_repair_storage_report

  # Docker may also be used by workloads outside LatticeVale in the selected distro.
  # Automatic repair therefore treats engine-global images/build cache as shared state:
  # report usage above, but never prune it without an explicit user-owned Docker action.
  # Reclaim only artifacts whose LatticeVale ownership can be proven locally.
  echo 'Automatic repair leaves engine-global Docker images and build cache untouched; only proven LatticeVale-owned disposable state is reclaimed.'
  prune_old_installer_config_backups
  cap_installer_event_log

  local free_after
  free_after="$(root_free_bytes 2>/dev/null || echo 0)"
  echo "WSL root free space after disposable cleanup: $(bytes_human "${free_after:-0}")"
  if [[ "$free_after" =~ ^[0-9]+$ && "$free_after" -lt 2147483648 ]]; then
    echo 'Less than 2 GiB remains free inside the WSL root filesystem after safe cleanup.' >&2
    echo 'Persistent user/application data was not deleted. Free space manually (for example obsolete user files or intentionally unused Ollama models), then rerun Resume / repair.' >&2
    return 1
  fi
  return 0
}

repair_database_maintenance() {
  repair_maintenance_enabled || return 0
  # Normal VACUUM reclaims dead tuples for database reuse and ANALYZE refreshes planner
  # statistics. It does not perform VACUUM FULL, delete messages/memory, or rewrite the
  # database into a smaller destructive form. Failures are warnings because service
  # health verification remains authoritative for the repair outcome.
  if [[ "$(opt_bool matrix)" == true ]] && docker compose ps --status running synapse-db 2>/dev/null | grep -q synapse-db; then
    echo 'Running bounded PostgreSQL VACUUM (ANALYZE) for Synapse.'
    if ! timeout --foreground --kill-after=15s 900s docker compose exec -T synapse-db psql -v ON_ERROR_STOP=1 -U synapse -d synapse -c 'VACUUM (ANALYZE);' >/dev/null; then
      echo 'WARNING: Synapse VACUUM (ANALYZE) did not complete; persistent data is unchanged and repair will continue.' >&2
    fi
  fi
  if [[ "$(opt_bool honcho)" == true ]] && docker compose ps --status running honcho-db 2>/dev/null | grep -q honcho-db; then
    echo 'Running bounded PostgreSQL VACUUM (ANALYZE) for Honcho.'
    if ! timeout --foreground --kill-after=15s 900s docker compose exec -T honcho-db psql -v ON_ERROR_STOP=1 -U honcho -d honcho -c 'VACUUM (ANALYZE);' >/dev/null; then
      echo 'WARNING: Honcho VACUUM (ANALYZE) did not complete; persistent data is unchanged and repair will continue.' >&2
    fi
  fi
}

run_uncheckpointed_repair_step() {
  local stage="$1" description="$2" action="$3"
  repair_maintenance_enabled || return 0
  CURRENT_STAGE="$stage"
  echo
  echo "==> $description"
  state_mark "$stage" running
  if ! "$action"; then
    state_mark "$stage" broken 'repair maintenance step failed safely; persistent data preserved'
    return 1
  fi
  state_mark "$stage" done
}

STATE_FILE=".installer-state.json"
OPTIONS_HASH="$(python3 - <<'PY_OPTIONS_HASH'
import hashlib,json
d=json.load(open('install-options.json'))
for k in ('installerVersion','installerMode','repairOriginVersion','repairOriginSchema','universalRepairMigration','resetCheckpoints','forceProviderSetup','forceProfileSetup','rebuildMatrixIdentity','repairMaintenance','forceManagedUpdate'):
    d.pop(k,None)
# Checkpoints represent managed-stack choices, not the ZIP release number. Older
# LatticeVale builds included installerVersion here, invalidating every stage whenever
# a newer bundle was used and making Resume / repair replay clean-install work.
payload=json.dumps({'options':d},sort_keys=True,separators=(',',':')).encode()
print(hashlib.sha256(payload).hexdigest())
PY_OPTIONS_HASH
)"
CURRENT_STAGE="startup"

# Explicit per-stage migration epochs let future releases rerun only the stage whose
# behavior truly changed instead of invalidating the whole installation.
checkpoint_revision() {
  case "$1" in
    matrix_profiles|matrix_profile_cross_signing) printf '3' ;;
    kanban_gateway) printf '4' ;;
    finalize) printf '2' ;;
    reconcile) printf '4' ;;
    integrations) printf '4' ;;
    prepare_config|infrastructure|matrix_bootstrap|provider_setup|profiles|matrix_cross_signing) printf '1' ;;
    *) printf '1' ;;
  esac
}

matrix_profile_activation_pending() {
  [[ "$(opt_bool matrix)" == true ]] || return 1
  local name secret state
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    secret="secrets/matrix-profiles/$name.env"
    [[ -s "$secret" ]] || continue
    state="$(read_env_file_value_optional "$secret" LATTICEVALE_PROVISIONING_STATE)"
    [[ -n "$state" ]] || state="$(read_env_file_value_optional "$secret" FOUNDRY_PROVISIONING_STATE)"
    [[ "$state" == pending-manual ]] && return 0
  done < <(jq -r '.workers[]? | select(.matrix.enabled == true) | .name' install-options.json 2>/dev/null || true)
  return 1
}

matrix_profile_cross_signing_pending() {
  [[ "$(opt_bool matrix)" == true ]] || return 1
  local name secret state cross_state recovery runtime_recovery
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    secret="secrets/matrix-profiles/$name.env"
    [[ -s "$secret" ]] || continue
    state="$(read_env_file_value_optional "$secret" LATTICEVALE_PROVISIONING_STATE)"
    [[ -n "$state" ]] || state="$(read_env_file_value_optional "$secret" FOUNDRY_PROVISIONING_STATE)"
    [[ "$state" == complete ]] || continue
    cross_state="$(read_env_file_value_optional "$secret" LATTICEVALE_CROSS_SIGNING_STATE)"
    if [[ -z "$cross_state" ]]; then
      recovery="$(read_env_file_value_optional "$secret" MATRIX_RECOVERY_KEY)"
      runtime_recovery="$(read_env_file_value_optional "data/hermes/profiles/$name/.env" MATRIX_RECOVERY_KEY)"
      if [[ -n "$recovery" && "$runtime_recovery" == "$recovery" ]]; then cross_state=complete; else cross_state=pending; fi
    fi
    [[ "$cross_state" == pending ]] && return 0
  done < <(jq -r '.workers[]? | select(.matrix.enabled == true) | .name' install-options.json 2>/dev/null || true)
  return 1
}

checkpoint_bypass_requested() {
  case "$1" in
    prepare_config|infrastructure) repair_package_refresh_pending ;;
    provider_setup) [[ "$(opt_bool forceProviderSetup)" == true ]] || repair_package_refresh_pending ;;
    profiles) [[ "$(opt_bool forceProfileSetup)" == true ]] || repair_package_refresh_pending ;;
    matrix_bootstrap) [[ "$(opt_bool rebuildMatrixIdentity)" == true ]] ;;
    matrix_cross_signing) [[ -e .matrix-cross-signing-pending ]] ;;
    matrix_profiles) matrix_profile_activation_pending ;;
    matrix_profile_cross_signing) matrix_profile_cross_signing_pending ;;
    *) return 1 ;;
  esac
}

resume_adoption_allowed() {
  case "$(opt_text installerMode)" in
    resume|reconfigure|update) return 0 ;;
    *) return 1 ;;
  esac
}

state_init() {
  python3 - "$STATE_FILE" "$INSTALLER_VERSION" "$OPTIONS_HASH" <<'PY_STATE_INIT'
from pathlib import Path
import json,sys,datetime
p=Path(sys.argv[1]); ver=sys.argv[2]; h=sys.argv[3]
try: d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
except Exception: d={}
d.setdefault('schema',1); d['installerVersion']=ver; d.setdefault('stages',{}); d.setdefault('history',[])
d['optionsHash']=h; d['status']='running'; d['lastStartedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat(); d.setdefault('currentStage','startup')
p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8'); p.chmod(0o600)
PY_STATE_INIT
}

state_mark() {
  local stage="$1" status="$2" detail="${3:-}" revision
  revision="$(checkpoint_revision "$stage")"
  python3 - "$STATE_FILE" "$stage" "$status" "$detail" "$OPTIONS_HASH" "$revision" <<'PY_STATE_MARK'
from pathlib import Path
import json,sys,datetime
p=Path(sys.argv[1]); stage,status,detail,h,revision=sys.argv[2:7]; now=datetime.datetime.now(datetime.timezone.utc).isoformat()
try: d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
except Exception: d={}
d.setdefault('schema',1); d.setdefault('stages',{}); d.setdefault('history',[]); d['optionsHash']=h; d['currentStage']=stage; d['status']='running' if status in ('running','pending') else d.get('status','running')
e=d['stages'].setdefault(stage,{})
e['status']=status; e['updatedAt']=now; e['optionsHash']=h; e['revision']=int(revision)
if detail: e['detail']=detail[:500]
if status=='running': e['startedAt']=now
if status=='done': e['completedAt']=now
if status=='broken': d['status']='failed'; d['lastErrorStage']=stage; d['lastError']=detail[:500]
d['history']=(d['history']+[{'at':now,'stage':stage,'status':status,'revision':int(revision)}])[-100:]
p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8'); p.chmod(0o600)
log=Path('logs/installer-events.jsonl'); log.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
entry={'at':now,'stage':stage,'status':status,'revision':int(revision)}
if detail: entry['detail']=detail[:500]
with log.open('a',encoding='utf-8') as f: f.write(json.dumps(entry,separators=(',',':'))+'\n')
log.chmod(0o600)
PY_STATE_MARK
}

state_stage_current() {
  local stage="$1" revision
  revision="$(checkpoint_revision "$stage")"
  python3 - "$STATE_FILE" "$stage" "$OPTIONS_HASH" "$revision" <<'PY_STATE_CHECK'
from pathlib import Path
import json,sys
p=Path(sys.argv[1]); stage=sys.argv[2]; h=sys.argv[3]; revision=int(sys.argv[4])
try: d=json.loads(p.read_text(encoding='utf-8'))
except Exception: raise SystemExit(1)
e=(d.get('stages') or {}).get(stage) or {}
stored_revision=int(e.get('revision',1))
raise SystemExit(0 if e.get('status')=='done' and e.get('optionsHash')==h and stored_revision==revision else 1)
PY_STATE_CHECK
}

state_stage_revision_stale() {
  local stage="$1" revision
  revision="$(checkpoint_revision "$stage")"
  python3 - "$STATE_FILE" "$stage" "$OPTIONS_HASH" "$revision" <<'PY_STATE_REVISION_STALE'
from pathlib import Path
import json,sys
p=Path(sys.argv[1]); stage=sys.argv[2]; h=sys.argv[3]; revision=int(sys.argv[4])
try: d=json.loads(p.read_text(encoding='utf-8'))
except Exception: raise SystemExit(1)
e=(d.get('stages') or {}).get(stage) or {}
try: stored_revision=int(e.get('revision',1))
except Exception: stored_revision=1
# A revision bump is an explicit installer migration request. Live-health shortcuts
# must not adopt/skip it merely because the old runtime still happens to be healthy.
raise SystemExit(0 if e.get('status')=='done' and e.get('optionsHash')==h and stored_revision!=revision else 1)
PY_STATE_REVISION_STALE
}

state_stage_legacy_adoptable() {
  local stage="$1" revision
  revision="$(checkpoint_revision "$stage")"
  [[ "$revision" == 1 ]] || return 1
  python3 - "$STATE_FILE" "$stage" <<'PY_STATE_LEGACY'
from pathlib import Path
import json,sys
p=Path(sys.argv[1]); stage=sys.argv[2]
try: d=json.loads(p.read_text(encoding='utf-8'))
except Exception: raise SystemExit(1)
e=(d.get('stages') or {}).get(stage) or {}
# v13.16.6 and older had no revision field and embedded installerVersion in optionsHash.
# A completed baseline checkpoint can be migrated only after its live verifier passes.
raise SystemExit(0 if e.get('status')=='done' and int(e.get('revision',1))==1 else 1)
PY_STATE_LEGACY
}

state_finish() {
  python3 - "$STATE_FILE" <<'PY_STATE_FINISH'
from pathlib import Path
import json,sys,datetime
p=Path(sys.argv[1]); d=json.loads(p.read_text(encoding='utf-8')); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
d['status']='complete'; d['currentStage']=None; d['lastCompletedAt']=now; d.pop('lastError',None); d.pop('lastErrorStage',None)
p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8'); p.chmod(0o600)
log=Path('logs/installer-events.jsonl'); log.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
with log.open('a',encoding='utf-8') as f: f.write(json.dumps({'at':now,'stage':'installer','status':'complete'},separators=(',',':'))+'\n')
log.chmod(0o600)
PY_STATE_FINISH
}

on_error() {
  local rc=$? line="${BASH_LINENO[0]:-${LINENO}}"
  trap - ERR
  state_mark "$CURRENT_STAGE" broken "command failed near line $line (exit $rc)" || true
  echo "Configuration failed during stage '$CURRENT_STAGE' near line $line (exit $rc). Rerun the installer and choose Resume / repair." >&2
  exit "$rc"
}
trap on_error ERR

on_interrupt() {
  trap - INT TERM ERR
  state_mark "$CURRENT_STAGE" broken 'installer interrupted by user/system signal' || true
  echo "Configuration interrupted during stage '$CURRENT_STAGE'. Completed data was preserved; rerun and choose Resume / repair." >&2
  exit 130
}
trap on_interrupt INT TERM

run_stage() {
  local stage="$1" description="$2" verifier="$3" action="$4"
  CURRENT_STAGE="$stage"
  RUN_STAGE_MIGRATION_REQUIRED=false

  # Explicit recovery requests always win over checkpoints. Older same-version
  # Reconfigure runs could otherwise skip provider/profile actions entirely.
  if ! checkpoint_bypass_requested "$stage"; then
    if state_stage_current "$stage" && "$verifier"; then
      printf '%-28s %s\n' "$description" 'OK - already complete'
      return 0
    fi

    # One-time migration from pre-v13.16.7 checkpoint hashes. A newer ZIP no longer
    # justifies replaying a healthy stage; live state is authoritative in Resume mode.
    if resume_adoption_allowed && state_stage_legacy_adoptable "$stage" && "$verifier"; then
      state_mark "$stage" done 'adopted live-verified legacy checkpoint without replaying stage action'
      printf '%-28s %s\n' "$description" 'OK - live state verified; checkpoint migrated'
      return 0
    fi
  fi

  # Preserve intentional per-stage migrations. If a future release bumps only this
  # stage revision, the stage action must run even when its pre-migration runtime is
  # currently healthy; otherwise repair's local-start optimization could swallow the
  # migration and mark the newer revision complete without applying it.
  if state_stage_revision_stale "$stage"; then
    RUN_STAGE_MIGRATION_REQUIRED=true
  fi

  echo
  echo "==> $description"
  state_mark "$stage" running
  "$action"
  if ! "$verifier"; then
    state_mark "$stage" broken 'post-stage verification failed'
    echo "Stage '$stage' finished commands but failed its live verification." >&2
    return 1
  fi
  state_mark "$stage" done
}

http_status_ok() {
  local url="$1" code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || true)"
  [[ "$code" =~ ^(2|3|401|403) ]]
}


wait_hermes_gateway_surfaces() {
  local context="${1:-gateway lifecycle}" tries="${2:-60}" i api_ok dashboard_ok
  for i in $(seq 1 "$tries"); do
    api_ok=false
    dashboard_ok=true
    if timeout --foreground --kill-after=5s 15s docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1 && \
       http_status_ok "http://127.0.0.1:${HERMES_API_HOST_PORT}/health"; then
      api_ok=true
    fi
    if [[ "$(opt_bool dashboard)" == true ]] && ! http_status_ok "http://127.0.0.1:${DASHBOARD_HOST_PORT}/"; then
      dashboard_ok=false
    fi
    [[ "$api_ok" == true && "$dashboard_ok" == true ]] && return 0
    sleep 2
  done
  echo "Hermes gateway surfaces did not recover after ${context}: API health and/or Dashboard remained unavailable after the bounded wait." >&2
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent /command/s6-svstat /run/service/gateway-default 2>&1 >&2 || true
  timeout --foreground --kill-after=5s 15s docker logs --tail 120 hermes-agent 2>&1 | tail -n 120 >&2 || true
  return 1
}

verify_prepare_config() {
  [[ -s .env && -f secrets/hermes-runtime.env && -f secrets/honcho.env && -f data/hermes/.env ]] || return 1
  grep -q '^API_SERVER_ENABLED=true$' data/hermes/.env || return 1
  grep -q '^API_SERVER_HOST=0.0.0.0$' data/hermes/.env || return 1
  grep -q '^API_SERVER_PORT=8642$' data/hermes/.env || return 1
  api_server_key="$(sed -n 's/^API_SERVER_KEY=//p' data/hermes/.env | head -n1)"
  [[ ${#api_server_key} -ge 16 ]] || return 1
  unset api_server_key
  if [[ "$(opt_bool dashboard)" == true ]]; then
    grep -q '^HERMES_DASHBOARD_BASIC_AUTH_USERNAME=' secrets/hermes-runtime.env || return 1
    grep -Fq "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH='scrypt\$" secrets/hermes-runtime.env || return 1
  fi
  [[ "$(opt_bool searxng)" != true || -s config/searxng/settings.yml ]] || return 1
  if [[ "$(opt_bool qmd)" == true ]]; then
    grep -q '^QMD_VERSION=2.5.3$' .env || return 1
  fi
  if local_ai_enabled; then
    grep -q '^OLLAMA_TEXT_MODEL=' .env || return 1
    grep -q '^LATTICEVALE_LOCAL_TEXT_BACKEND=' .env || return 1
    if directml_text_enabled; then
      grep -q '^DIRECTML_TEXT_MODEL=' .env || return 1
      grep -q '^DIRECTML_PORT=' .env || return 1
      [[ -x ./directml-gateway.sh && -f ./directml-gateway.py && -f ./directml-requirements.txt ]] || return 1
    fi
    if managed_ollama_enabled; then
      grep -q '^OLLAMA_IMAGE=' .env || return 1
      [[ ! -e .windows-native-info ]] || return 1
    else
      [[ -s .windows-native-info ]] || return 1
      grep -Eq '^TRANSPORT=(windows-gateway-relay|wsl-localhost-relay|wsl-host-relay)$' .windows-native-info || return 1
      grep -Eq '^TARGET_ADDRESS=(localhost|127\.[0-9]+\.[0-9]+\.[0-9]+)$' .windows-native-info || return 1
      grep -Eq '^TARGET_PORT=[0-9]+$' .windows-native-info || return 1
      grep -q '^WINDOWS_HOST_IP=' .env || return 1
      grep -q '^WINDOWS_OLLAMA_BRIDGE_PORT=' .env || return 1
      if [[ "$(sed -n 's/^TRANSPORT=//p' .windows-native-info | head -n1)" == wsl-localhost-relay || "$(sed -n 's/^TRANSPORT=//p' .windows-native-info | head -n1)" == wsl-host-relay ]]; then
        [[ -x ./native-ollama-relay.sh && -f ./native-ollama-relay.py ]] || return 1
      fi
    fi
  fi
  if [[ "$(opt_bool honcho)" == true ]]; then
    grep -q '^LLM_OPENAI_API_KEY=ollama-local$' secrets/honcho.env || return 1
    [[ -s config/honcho/config.toml && -s data/hermes/honcho.json && -d vendor/honcho ]] || return 1
    grep -Fq "base_url = \"$(ollama_openai_base_url)\"" config/honcho/config.toml || return 1
    grep -Fq "base_url = \"$(local_text_openai_base_url)\"" config/honcho/config.toml || return 1
    grep -q 'VECTOR_DIMENSIONS = 1536' config/honcho/config.toml || return 1
    python3 - <<'PY_HONCHO_ROUTE_CHECK' || return 1
import json
from pathlib import Path
cfg=json.loads(Path('data/hermes/honcho.json').read_text(encoding='utf-8'))
raise SystemExit(0 if cfg.get('baseUrl')=='http://honcho-api:8000' else 1)
PY_HONCHO_ROUTE_CHECK
  fi
  [[ "$(opt_bool matrix)" != true || -s data/synapse/homeserver.yaml ]] || return 1
  # Installer-owned stale containers from disabled/legacy options make this stage incomplete.
  names="$(docker ps -a --format '{{.Names}}' 2>/dev/null || true)"
  grep -Eq '^(hermes-tailscale|hermes-tailscale-matrix)$' <<<"$names" && return 1
  [[ "$(opt_bool matrix)" == true ]] || ! grep -Eq '^(hermes-synapse|hermes-synapse-db)$' <<<"$names" || return 1
  [[ "$(opt_bool searxng)" == true ]] || ! grep -Eq '^(hermes-searxng|hermes-searxng-valkey)$' <<<"$names" || return 1
  [[ "$(opt_bool qmd)" == true ]] || ! grep -Eq '^(hermes-qmd|hermes-qmd-indexer)$' <<<"$names" || return 1
  [[ "$(opt_bool honcho)" == true ]] || ! grep -Eq '^(hermes-honcho-api|hermes-honcho-deriver|hermes-honcho-db|hermes-honcho-redis)$' <<<"$names" || return 1
  managed_ollama_enabled || ! grep -Eq '^hermes-ollama$' <<<"$names" || return 1
  return 0
}

verify_infrastructure() {
  docker compose config --quiet >/dev/null 2>&1 || return 1
  if managed_ollama_enabled; then
    docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null | grep -qx healthy || return 1
  elif windows_native_ollama_enabled; then
    local native_base
    native_base="$(native_ollama_ready_base_url)" || return 1
    timeout --foreground --kill-after=5s 15s python3 - "$native_base" <<'PY_NATIVE_INFRA_VERIFY' >/dev/null 2>&1 || return 1
import sys,urllib.request
urllib.request.urlopen(sys.argv[1].rstrip('/')+'/api/version',timeout=5).read()
PY_NATIVE_INFRA_VERIFY
  fi
  if local_ai_enabled; then
    ollama_model_present "$(opt_text localTextModel)" || return 1
    if [[ "$(opt_bool honcho)" == true ]]; then ollama_model_present "$(opt_text localEmbeddingModel)" || return 1; fi
    if directml_text_enabled; then
      [[ -x ./directml-gateway.sh ]] || return 1
      timeout --foreground --kill-after=5s 40s ./directml-gateway.sh start >/dev/null || return 1
      timeout --foreground --kill-after=3s 15s ./directml-gateway.sh health >/dev/null || return 1
    fi
  fi
  if [[ "$(opt_bool searxng)" == true ]]; then wait_http SearXNG http://127.0.0.1:${SEARXNG_HOST_PORT}/ 1 || return 1; fi
  if [[ "$(opt_bool qmd)" == true ]]; then qmd_health_ok || return 1; fi
  if [[ "$(opt_bool honcho)" == true ]]; then wait_http Honcho http://127.0.0.1:${HONCHO_HOST_PORT}/health 1 || return 1; fi
  if [[ "$(opt_bool matrix)" == true ]]; then matrix_client_api_ready || return 1; fi
  return 0
}

verify_matrix() {
  [[ "$(opt_bool matrix)" != true ]] && return 0
  # An explicit Advanced Recovery identity rebuild is a transaction, not a healthy
  # steady state. Even when the old identity is still fully usable (interruption before
  # replacement bootstrap persistence), force the Matrix stage to inspect the pending
  # marker instead of silently adopting/keeping the checkpoint as complete.
  [[ ! -e .matrix-identity-rebuild-pending ]] || return 1
  [[ -s secrets/matrix-bot.env && -s .matrix-info ]] || return 1
  matrix_client_api_ready || return 1
  local token e2ee_mode device_id user_id room_id live_user recorded_version configured_version
  token="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_ACCESS_TOKEN)"
  e2ee_mode="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_E2EE_MODE)"
  device_id="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_DEVICE_ID)"
  user_id="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_USER_ID)"
  room_id="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_ALLOWED_ROOMS)"
  recorded_version="$(read_env_file_value_optional .matrix-info MATRIX_ROOM_VERSION)"
  [[ -n "$token" && "$e2ee_mode" == required && -n "$device_id" && -n "$user_id" && "$room_id" == !*:* ]] || return 1
  [[ "$recorded_version" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]] || return 1
  configured_version="$(python3 - <<'PY_VERIFY_MATRIX_ROOM_POLICY'
from pathlib import Path
import yaml
p=Path('data/synapse/homeserver.yaml')
try: cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
except Exception: cfg={}
print(str(cfg.get('default_room_version','')))
PY_VERIFY_MATRIX_ROOM_POLICY
)"
  [[ "$configured_version" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]] || return 1
  # Cross-signing recovery is intentionally verified in its own later stage. Do not
  # make an older otherwise-valid Matrix identity look broken merely because a
  # pre-v13.15 install did not retain its generated recovery key.
  live_user="$(curl -fsS --connect-timeout 3 --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/account/whoami" 2>/dev/null | jq -r '.user_id // empty' || true)"
  [[ "$live_user" == "$user_id" ]] || return 1
  curl -fsS --connect-timeout 3 --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/devices" | jq -e --arg d "$device_id" '.devices | any(.device_id == $d)' >/dev/null 2>&1
}

verify_matrix_cross_signing() {
  [[ "$(opt_bool matrix)" != true ]] && return 0
  [[ -s secrets/matrix-bot.env ]] || return 1
  local recovery_key runtime_key
  recovery_key="$(sed -n 's/^MATRIX_RECOVERY_KEY=//p' secrets/matrix-bot.env | head -n1)"
  runtime_key="$(sed -n 's/^MATRIX_RECOVERY_KEY=//p' data/hermes/.env | head -n1)"
  if [[ -e .matrix-cross-signing-pending ]]; then
    # This marker is created only for a preserved pre-installer-managed Matrix identity
    # whose existing recovery key is unavailable. It is intentionally retryable: the
    # identity/token/device/crypto DB remain intact and Resume / repair prompts again.
    # Fresh installer-managed identities never get this soft-pending exemption.
    ! grep -Fq 'MATRIX_CROSS_SIGNING=installer-managed' .matrix-info 2>/dev/null || return 1
    [[ -z "$recovery_key" ]] || return 1
    ! grep -q '^MATRIX_RECOVERY_KEY_OUTPUT_FILE=' data/hermes/.env 2>/dev/null || return 1
    [[ ! -e data/hermes/matrix-recovery-key.once ]] || return 1
    return 0
  fi
  [[ -n "$recovery_key" && "$runtime_key" == "$recovery_key" ]] || return 1
  ! grep -q '^MATRIX_RECOVERY_KEY_OUTPUT_FILE=' data/hermes/.env 2>/dev/null || return 1
  [[ ! -e data/hermes/matrix-recovery-key.once ]] || return 1
  return 0
}

stage_matrix_cross_signing() {
  [[ "$(opt_bool matrix)" != true ]] && return 0
  [[ -s secrets/matrix-bot.env ]] || { echo 'Matrix credentials are missing; repair Matrix bootstrap first.' >&2; return 1; }

  local recovery_key once_file=/opt/data/matrix-recovery-key.once host_once=data/hermes/matrix-recovery-key.once supplied=''
  recovery_key="$(sed -n 's/^MATRIX_RECOVERY_KEY=//p' secrets/matrix-bot.env | head -n1)"

  if [[ -z "$recovery_key" ]]; then
    echo 'Securing Hermes Matrix cross-signing so Element can recognize the bot device as owner-verified.'

    # On a fresh install the first Hermes start in stage_profiles may already have
    # bootstrapped cross-signing and written this one-time 0600 file. Capture that
    # file BEFORE any recycle; Hermes intentionally does not overwrite/regenerate it.
    if [[ ! -s "$host_once" ]]; then
      set_env data/hermes/.env MATRIX_RECOVERY_KEY_OUTPUT_FILE "$once_file"
      set_env secrets/matrix-bot.env MATRIX_RECOVERY_KEY_OUTPUT_FILE "$once_file"
      chmod 0600 data/hermes/.env secrets/matrix-bot.env

      # Older/resumed installs may not have started with the output-file setting.
      # Ask Hermes once through its supported mechanism while preserving the existing
      # access token/device/crypto store; never delete crypto.db here.
      ensure_matrix_online 30
      recycle_hermes_bounded 'Matrix recovery-key bootstrap' || return 1
      echo 'Waiting up to 120 seconds for Hermes to emit the one-time Matrix recovery key.'
      matrix_offline_streak=0
      for _ in $(seq 1 60); do
        [[ -s "$host_once" ]] && break
        if matrix_client_api_ready; then
          matrix_offline_streak=0
        else
          matrix_offline_streak=$((matrix_offline_streak+1))
          if (( matrix_offline_streak >= 3 )); then
            echo 'Matrix/Synapse went offline while waiting for the default Hermes recovery key; stopping this stage for safe Resume / repair.' >&2
            return 1
          fi
        fi
        sleep 2
      done
    fi

    if [[ -s "$host_once" ]]; then
      recovery_key="$(tr -d '\r\n' < "$host_once")"
      [[ -n "$recovery_key" ]] || { echo 'Hermes created an empty Matrix recovery-key file.' >&2; return 1; }
      echo 'Captured the one-time Hermes Matrix recovery key into the installer secret store.'
    else
      echo
      echo 'This existing Matrix identity did not generate a new recovery key. That usually means cross-signing was already bootstrapped by an older LatticeVale release but its recovery key was not retained.' >&2
      echo 'No Matrix crypto database, device, access token, account, or room will be deleted automatically.' >&2
      if [[ -t 0 ]]; then
        read -r -s -p 'If you already have the Hermes bot account recovery/security key, paste it now (or press Enter to preserve the current identity unchanged): ' supplied
        echo
      fi
      recovery_key="$supplied"
      if [[ -z "$recovery_key" ]]; then
        remove_env_keys data/hermes/.env MATRIX_RECOVERY_KEY_OUTPUT_FILE
        remove_env_keys secrets/matrix-bot.env MATRIX_RECOVERY_KEY_OUTPUT_FILE
        rm -f "$host_once"
        echo 'Matrix E2EE remains enabled, but automatic owner cross-signing could not be completed without the pre-existing bot recovery key.' >&2
        echo 'The repair will continue so Windows/Tailscale reconciliation can complete. After obtaining or resetting the Hermes bot recovery key in Element, rerun Resume / repair and paste it at this prompt.' >&2
        # Pre-v13.15 installations could already have a usable encrypted identity but
        # no retained recovery secret. This is not a reason to block unrelated repair
        # stages or destructively rotate Matrix state. Clean v13.15 identities are
        # marked installer-managed and are expected to emit the one-time key.
        if ! grep -Fq 'MATRIX_CROSS_SIGNING=installer-managed' .matrix-info 2>/dev/null; then
          touch .matrix-cross-signing-pending
          chmod 0600 .matrix-cross-signing-pending
          return 0
        fi
        return 1
      fi
    fi
  fi

  set_env secrets/matrix-bot.env MATRIX_RECOVERY_KEY "$recovery_key"
  set_env data/hermes/.env MATRIX_RECOVERY_KEY "$recovery_key"
  remove_env_keys secrets/matrix-bot.env MATRIX_RECOVERY_KEY_OUTPUT_FILE
  remove_env_keys data/hermes/.env MATRIX_RECOVERY_KEY_OUTPUT_FILE
  rm -f "$host_once"
  chmod 0600 secrets/matrix-bot.env data/hermes/.env
  rm -f .matrix-cross-signing-pending

  recycle_hermes_bounded 'Matrix recovery-key activation' || return 1

  # Cross-signing is an upstream Matrix/Hermes trust operation, and the exact log
  # line is not a reliable installer health boundary. Older LatticeVale releases were
  # more tolerant here. Once the supported recovery key is persisted, its one-time
  # output setting is removed, and Hermes has restarted successfully, treat the
  # configuration step as complete. Look briefly for upstream confirmation, but do
  # not abort an otherwise healthy clean or repair install just because that log
  # message is absent or delayed.
  echo 'Checking briefly for Hermes Matrix cross-signing confirmation (advisory only).'
  sleep 5
  if timeout --foreground --kill-after=5s 15s docker logs --since 2m hermes-agent 2>&1 | grep -Fq 'Matrix: cross-signing verified via recovery key'; then
    echo 'Hermes Matrix device cross-signing confirmed via the retained recovery key.'
  else
    echo 'WARNING: Hermes retained and loaded the Matrix recovery key, but no explicit cross-signing confirmation log was observed. Continuing because this log message is advisory, not a reliable install-failure signal.' >&2
    timeout --foreground --kill-after=5s 15s docker logs --tail 80 hermes-agent 2>&1 | grep -i -E 'matrix|cross-sign|recovery|e2ee' >&2 || true
  fi
  return 0
}

verify_provider() {
  hermes_model_configured data/hermes/config.yaml || return 1
  if [[ "$(opt_bool hermesLocalAI)" == true ]]; then
    local expected_context
    expected_context="$(local_text_context_length)"
    python3 - data/hermes/config.yaml "$(local_text_model_name)" "$expected_context" "$(local_text_openai_base_url)" <<'PY_LOCAL_PROVIDER_CHECK'
from pathlib import Path
import sys,yaml
cfg=yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8')) or {}
m=cfg.get('model') or {}
ok=(m.get('default')==sys.argv[2] and m.get('provider')=='custom' and
    m.get('base_url')==sys.argv[4] and int(m.get('context_length') or 0)==int(sys.argv[3]))
raise SystemExit(0 if ok else 1)
PY_LOCAL_PROVIDER_CHECK
  fi
  return 0
}

profile_gateway_s6_state() {
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

profile_gateway_is_running_exact() {
  local state
  state="$(profile_gateway_s6_state "$1")" || return 2
  [[ "$state" == up ]]
}

wait_profile_gateway_up_exact() {
  local name="$1" wait_seconds="${2:-60}" i state consecutive_up=0 observed_state=false
  [[ "$wait_seconds" =~ ^[0-9]+$ && "$wait_seconds" -ge 1 ]] || wait_seconds=60
  # Gateway lifecycle commands can temporarily tear down/recreate the dynamic s6
  # service while the Python runtime is under CPU/memory pressure. Treat a transient
  # s6-svstat/exec failure as STARTING rather than immediately poisoning reconcile.
  # Require two consecutive 'up' observations so a momentary process spawn is not
  # mistaken for stable readiness. The loop remains strictly bounded.
  for i in $(seq 1 "$wait_seconds"); do
    if state="$(profile_gateway_s6_state "$name" 2>/dev/null)"; then
      observed_state=true
      if [[ "$state" == up ]]; then
        consecutive_up=$((consecutive_up+1))
        (( consecutive_up >= 2 )) && return 0
      else
        consecutive_up=0
      fi
    else
      state=unknown
      consecutive_up=0
    fi
    sleep 1
  done
  [[ "$observed_state" == true ]] || return 2
  return 1
}

profile_gateway_log_tail_exact() {
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

start_or_restart_profile_gateway_exact() {
  local name="$1" state action
  if ! state="$(profile_gateway_s6_state "$name")"; then
    echo "Unable to determine exact s6 state for profile '$name' before gateway activation." >&2
    return 1
  fi
  case "$state" in
    up) action=restart ;;
    down) action=start ;;
    absent)
      echo "Profile '$name' has no registered s6 gateway service. LatticeVale will not recreate or replace the profile automatically because that would risk its persisted state." >&2
      profile_gateway_log_tail_exact "$name"
      return 1
      ;;
    *)
      echo "Profile '$name' exact s6 gateway state is '$state'; refusing to guess whether start or restart is appropriate." >&2
      return 1
      ;;
  esac
  if ! timeout --foreground --kill-after=5s 60s docker exec -u hermes hermes-agent hermes -p "$name" gateway "$action" >/dev/null; then
    # Hermes' named-profile lifecycle command has had regressions where the profile
    # exists and its dynamic s6 slot is present, but `gateway start/restart` still
    # reports that the service is unavailable. Fall back only to the exact proven
    # s6 service directory. -U clears a stale persistent ./down marker on start;
    # -r restarts an already-wanted-up service. No profile-blind process action occurs.
    echo "WARNING: Profile '$name' Hermes gateway $action command failed; retrying through its exact s6 service slot." >&2
    if [[ "$action" == start ]]; then
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "/run/service/gateway-$name" >/dev/null 2>&1 || {
        echo "Profile '$name' exact s6 gateway start fallback failed." >&2
        profile_gateway_log_tail_exact "$name"
        return 1
      }
    else
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -r "/run/service/gateway-$name" >/dev/null 2>&1 || {
        echo "Profile '$name' exact s6 gateway restart fallback failed." >&2
        profile_gateway_log_tail_exact "$name"
        return 1
      }
    fi
  fi
  if ! wait_profile_gateway_up_exact "$name" 60; then
    # A successful Hermes lifecycle command may return before its dynamic s6 service
    # has settled. Request only this proven service slot up once, then grant one final
    # bounded readiness window. This is preservation-first: no profile recreation,
    # container-wide restart, or process-name kill is used.
    echo "WARNING: Profile '$name' exact s6 gateway service is still settling after $action; requesting the same exact service slot up and retrying readiness." >&2
    timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "/run/service/gateway-$name" >/dev/null 2>&1 || true
    if ! wait_profile_gateway_up_exact "$name" 60; then
      echo "Profile '$name' exact s6 gateway service did not become stably running after bounded $action recovery." >&2
      profile_gateway_log_tail_exact "$name"
      return 1
    fi
  fi
  return 0
}


start_or_restart_default_gateway_exact() {
  local state action service="/run/service/gateway-default"
  if ! state="$(profile_gateway_s6_state default)"; then
    echo 'Unable to determine exact s6 state for the default gateway before activation.' >&2
    return 1
  fi
  case "$state" in
    up) action=restart ;;
    down) action=start ;;
    absent)
      echo 'Default gateway has no registered s6 service slot; refusing to guess or recreate it automatically.' >&2
      profile_gateway_log_tail_exact default
      return 1
      ;;
    *)
      echo "Default gateway exact s6 state is '$state'; refusing an ambiguous lifecycle action." >&2
      return 1
      ;;
  esac
  if ! timeout --foreground --kill-after=5s 60s docker exec -u hermes hermes-agent hermes gateway "$action" >/dev/null 2>&1; then
    echo "WARNING: Hermes default gateway $action command failed; retrying only its exact s6 service slot." >&2
    if [[ "$action" == start ]]; then
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "$service" >/dev/null 2>&1 || {
        echo 'Default gateway exact s6 start fallback failed.' >&2
        profile_gateway_log_tail_exact default
        return 1
      }
    else
      timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -r "$service" >/dev/null 2>&1 || {
        echo 'Default gateway exact s6 restart fallback failed.' >&2
        profile_gateway_log_tail_exact default
        return 1
      }
    fi
  fi
  if ! wait_profile_gateway_up_exact default 60; then
    # Hermes can report restart success before the exact dynamic s6 slot has settled.
    # Reassert only the already-proven default slot as wanted-up and allow one final
    # bounded readiness window instead of failing a healthy-but-slow repair.
    echo "WARNING: Default gateway exact s6 service is still settling after $action; requesting the same exact service slot up and retrying readiness." >&2
    timeout --foreground --kill-after=5s 30s docker exec hermes-agent /command/s6-svc -U "$service" >/dev/null 2>&1 || true
    if ! wait_profile_gateway_up_exact default 60; then
      echo "Default gateway exact s6 service did not become stably running after bounded $action recovery." >&2
      profile_gateway_log_tail_exact default
      return 1
    fi
  fi
  return 0
}

wait_profile_gateway_down_exact() {
  local name="$1" i state
  for i in $(seq 1 20); do
    if ! state="$(profile_gateway_s6_state "$name")"; then
      return 2
    fi
    [[ "$state" != up ]] && return 0
    sleep 1
  done
  return 1
}

stop_profile_gateway_exact() {
  local name="$1" service="/run/service/gateway-$1"
  timeout --foreground --kill-after=5s 20s docker exec -u hermes hermes-agent hermes -p "$name" gateway stop >/dev/null 2>&1 || true
  wait_profile_gateway_down_exact "$name" && return 0
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent /command/s6-svc -d "$service" >/dev/null 2>&1 || true
  wait_profile_gateway_down_exact "$name"
}

stop_profile_gateway_after_matrix_failure() {
  stop_profile_gateway_exact "$1"
}

quiesce_profile_gateway_for_credential_write() {
  local name="$1" service state raw pid current
  service="/run/service/gateway-$name"

  # Upstream Hermes profile creation registers an s6 slot and may start it immediately.
  # Ask Hermes to persist an explicit stopped state first, then verify the exact profile
  # slot rather than trusting `gateway status` (which has had cross-profile false positives).
  timeout --foreground --kill-after=5s 30s docker exec -u hermes hermes-agent hermes -p "$name" gateway stop >/dev/null 2>&1 || true
  if wait_profile_gateway_down_exact "$name"; then
    return 0
  fi

  if ! state="$(profile_gateway_s6_state "$name")"; then
    echo "Unable to determine exact s6 state for new profile '$name'; refusing to copy profile credentials." >&2
    return 1
  fi
  [[ "$state" == up ]] || return 0

  # Defense against upstream dynamic-s6 stop races: request down directly on this one
  # service slot, never through a profile-blind process search or global gateway kill.
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent /command/s6-svc -d "$service" >/dev/null 2>&1 || true
  if wait_profile_gateway_down_exact "$name"; then
    return 0
  fi

  if ! raw="$(timeout --foreground --kill-after=5s 15s docker exec hermes-agent /command/s6-svstat "$service" 2>/dev/null)"; then
    echo "Unable to inspect exact s6 service '$service' after stop request; refusing credential copy." >&2
    return 1
  fi
  pid="$(sed -n 's/^up (pid \([0-9][0-9]*\)).*/\1/p' <<<"$raw" | head -n1)"
  [[ "$pid" =~ ^[0-9]+$ ]] || {
    echo "Profile '$name' exact s6 service is still up but its service PID could not be determined; refusing credential copy." >&2
    return 1
  }

  echo "Hermes profile '$name' did not quiesce after its normal stop request; terminating only exact s6 service PID $pid before credential handoff."
  timeout --foreground --kill-after=5s 15s docker exec hermes-agent sh -c 'kill -TERM "$1" 2>/dev/null || true' sh "$pid" >/dev/null 2>&1 || true
  if wait_profile_gateway_down_exact "$name"; then
    return 0
  fi

  # Re-read the exact service PID before escalating. Never kill a recycled/unrelated PID.
  if ! raw="$(timeout --foreground --kill-after=5s 15s docker exec hermes-agent /command/s6-svstat "$service" 2>/dev/null)"; then
    echo "Unable to re-check exact s6 service '$service' after TERM; refusing credential copy." >&2
    return 1
  fi
  current="$(sed -n 's/^up (pid \([0-9][0-9]*\)).*/\1/p' <<<"$raw" | head -n1)"
  if [[ "$current" == "$pid" ]]; then
    timeout --foreground --kill-after=5s 15s docker exec hermes-agent sh -c 'kill -KILL "$1" 2>/dev/null || true' sh "$pid" >/dev/null 2>&1 || true
  fi
  if wait_profile_gateway_down_exact "$name"; then
    return 0
  fi

  echo "New profile '$name' exact s6 gateway service remained active after bounded profile-scoped shutdown; refusing to copy credentials." >&2
  return 1
}

verify_profiles() {
  local worker name clone
  while IFS= read -r worker; do
    [[ -n "$worker" ]] || continue
    name="$(jq -r '.name' <<<"$worker")"
    clone="$(jq -r '.clone // false' <<<"$worker")"
    [[ -d "data/hermes/profiles/$name" ]] || return 1
    hermes_model_configured "data/hermes/profiles/$name/config.yaml" || return 1
    if [[ "$(opt_bool hermesLocalAI)" == true && "$clone" == true ]]; then
      python3 - "data/hermes/profiles/$name/config.yaml" "$(local_text_model_name)" "$(local_text_openai_base_url)" <<'PY_VERIFY_CLONED_LOCAL_OLLAMA' || return 1
from pathlib import Path
import sys,yaml
cfg=yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8')) or {}
m=cfg.get('model') or {}
# Only enforce the relay URL when this cloned profile is still using the installer
# local-Ollama model. Profiles deliberately changed to another provider/model remain user-owned.
if m.get('provider')=='custom' and m.get('default')==sys.argv[2]:
    raise SystemExit(0 if m.get('base_url')==sys.argv[3] else 1)
raise SystemExit(0)
PY_VERIFY_CLONED_LOCAL_OLLAMA
    fi
  done < <(jq -c '.workers[]?' install-options.json)
  return 0
}

verify_matrix_profiles() {
  [[ "$(opt_bool matrix)" != true ]] && return 0
  matrix_client_api_ready || return 1
  local worker name enabled localpart pdir secret info token user_id room_id expected_user runtime_user joined model default_token room_mode room_version provisioning_state setup_status
  default_token="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_ACCESS_TOKEN)"
  while IFS= read -r worker; do
    [[ -n "$worker" ]] || continue
    enabled="$(jq -r '.matrix.enabled // false' <<<"$worker")"
    [[ "$enabled" == true ]] || continue
    name="$(jq -r '.name' <<<"$worker")"
    localpart="$(jq -r '.matrix.localpart // .name' <<<"$worker")"
    pdir="data/hermes/profiles/$name"
    secret="secrets/matrix-profiles/$name.env"
    info=".matrix-profiles/$name.info"
    hermes_model_configured "$pdir/config.yaml" || return 1
    [[ -s "$secret" && -s "$info" && -s "$pdir/.env" ]] || return 1
    model="$(python3 - "$pdir/config.yaml" <<'PY_VERIFY_PROFILE_MATRIX_MODEL'
from pathlib import Path
import sys,yaml
cfg=yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8')) or {}
print(((cfg.get('model') or {}).get('default') or '').strip())
PY_VERIFY_PROFILE_MATRIX_MODEL
)"
    [[ -n "$model" && "$(sed -n 's/^HERMES_MODEL=//p' "$info" | head -n1)" == "$model" ]] || return 1
    token="$(read_env_file_value_optional "$secret" MATRIX_ACCESS_TOKEN)"
    user_id="$(read_env_file_value_optional "$secret" MATRIX_USER_ID)"
    room_id="$(read_env_file_value_optional "$secret" MATRIX_ALLOWED_ROOMS)"
    provisioning_state="$(read_env_file_value_optional "$secret" LATTICEVALE_PROVISIONING_STATE)"
    [[ -n "$provisioning_state" ]] || provisioning_state="$(read_env_file_value_optional "$secret" FOUNDRY_PROVISIONING_STATE)"
    expected_user="@$localpart:hermes.local"
    [[ "$provisioning_state" == complete || "$provisioning_state" == pending-manual ]] || return 1
    [[ -n "$token" && "$user_id" == "$expected_user" && "$room_id" == !*:* ]] || return 1
    [[ -z "$default_token" || "$token" != "$default_token" ]] || return 1
    [[ "$(read_env_file_value_optional "$pdir/.env" MATRIX_ACCESS_TOKEN)" == "$token" ]] || return 1
    [[ "$(read_env_file_value_optional "$pdir/.env" MATRIX_USER_ID)" == "$expected_user" ]] || return 1
    [[ "$(read_env_file_value_optional "$pdir/.env" MATRIX_ALLOWED_ROOMS)" == "$room_id" ]] || return 1
    [[ "$(read_env_file_value_optional "$pdir/.env" MATRIX_HOME_ROOM)" == "$room_id" ]] || return 1
    setup_status="$(read_env_file_value_optional "$info" MATRIX_SETUP_STATUS)"
    [[ "$setup_status" == "$provisioning_state" ]] || return 1
    runtime_user="$(curl -fsS --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/account/whoami" 2>/dev/null | jq -r '.user_id // empty' || true)"
    [[ "$runtime_user" == "$expected_user" ]] || return 1
    room_mode="$(read_env_file_value_optional "$secret" MATRIX_ROOM_MODE)"
    if [[ "$room_mode" == create ]]; then
      # The recorded room-version marker is part of the protected provisioning
      # transaction and must always match policy. Do not, however, require the pending
      # bot itself to query live room metadata before it has accepted the invite: Synapse
      # can legitimately deny that lookup until membership is complete. Live room-version
      # verification remains strict once the profile is marked complete.
      [[ "$(read_env_file_value_optional "$secret" MATRIX_ROOM_VERSION)" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]] || {
        echo "Matrix profile '$name' verification failed: protected room-version marker is missing or does not match v$LATTICEVALE_MATRIX_ROOM_VERSION." >&2
        return 1
      }
    fi
    if [[ "$provisioning_state" == pending-manual ]]; then
      # The account/token/room/model transaction is valid and protected. Hermes-side
      # invite acceptance and E2EE recovery-key persistence are a retryable runtime
      # activation state, not a failed provisioning transaction. Resume / repair is
      # forced back through this stage by checkpoint_bypass_requested while pending.
      continue
    fi
    if [[ "$room_mode" == create ]]; then
      room_version="$(matrix_room_version "$token" "$room_id" || true)"
      [[ "$room_version" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]] || {
        echo "Matrix profile '$name' verification failed: completed profile cannot verify live room version v$LATTICEVALE_MATRIX_ROOM_VERSION for '$room_id'." >&2
        return 1
      }
    fi
    joined="$(curl -fsS --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/joined_rooms" 2>/dev/null | jq -r --arg r "$room_id" '.joined_rooms | index($r) != null' || true)"
    [[ "$joined" == true ]] || return 1
    # Gateway runtime health is intentionally verified/retried by later lifecycle and
    # state-audit paths. A stopped exact gateway must not invalidate an otherwise valid
    # identity/room provisioning stage.
  done < <(jq -c '.workers[]?' install-options.json)
  return 0
}

verify_matrix_profile_cross_signing() {
  [[ "$(opt_bool matrix)" != true ]] && return 0
  local worker name enabled pdir secret recovery runtime_recovery provisioning_state cross_state
  while IFS= read -r worker; do
    [[ -n "$worker" ]] || continue
    enabled="$(jq -r '.matrix.enabled // false' <<<"$worker")"
    [[ "$enabled" == true ]] || continue
    name="$(jq -r '.name' <<<"$worker")"
    pdir="data/hermes/profiles/$name"
    secret="secrets/matrix-profiles/$name.env"
    [[ -s "$secret" && -s "$pdir/.env" ]] || return 1
    provisioning_state="$(read_env_file_value_optional "$secret" LATTICEVALE_PROVISIONING_STATE)"
    [[ -n "$provisioning_state" ]] || provisioning_state="$(read_env_file_value_optional "$secret" FOUNDRY_PROVISIONING_STATE)"
    if [[ "$provisioning_state" == pending-manual ]]; then
      continue
    fi
    [[ "$provisioning_state" == complete ]] || return 1
    recovery="$(read_env_file_value_optional "$secret" MATRIX_RECOVERY_KEY)"
    runtime_recovery="$(read_env_file_value_optional "$pdir/.env" MATRIX_RECOVERY_KEY)"
    cross_state="$(read_env_file_value_optional "$secret" LATTICEVALE_CROSS_SIGNING_STATE)"
    if [[ -z "$cross_state" ]]; then
      if [[ -n "$recovery" && "$runtime_recovery" == "$recovery" ]]; then cross_state=complete; else cross_state=pending; fi
    fi
    if [[ "$cross_state" == pending ]]; then
      continue
    fi
    [[ "$cross_state" == complete ]] || return 1
    [[ -n "$recovery" && "$runtime_recovery" == "$recovery" ]] || return 1
    ! grep -q '^MATRIX_RECOVERY_KEY_OUTPUT_FILE=' "$pdir/.env" 2>/dev/null || return 1
    [[ ! -e "$pdir/matrix-recovery-key.once" ]] || return 1
  done < <(jq -c '.workers[]?' install-options.json)
  return 0
}

verify_integrations() {
  python3 - install-options.json data/hermes .installer-managed-profiles <<'PY_VERIFY_INTEGRATIONS'
from pathlib import Path
import json,sys
try: import yaml
except Exception: raise SystemExit(1)
opts=json.loads(Path(sys.argv[1]).read_text()); root=Path(sys.argv[2]); managed=Path(sys.argv[3])
names=[x.strip() for x in managed.read_text().splitlines() if x.strip()] if managed.exists() else []
names=[n for n in names if (root/'profiles'/n).is_dir()]
# Routing may intentionally point at a user-created Hermes profile that LatticeVale
# does not own. Validate against every real profile on disk, while modifying/verifying
# only the default + installer-managed profile configs below.
all_profiles=[]
profiles_dir=root/'profiles'
if profiles_dir.is_dir():
    all_profiles=sorted(child.name for child in profiles_dir.iterdir() if child.is_dir() and (child/'config.yaml').is_file())
known=['default']+[n for n in all_profiles if n!='default']
paths=[root/'config.yaml']+[root/'profiles'/n/'config.yaml' for n in names]
if not (root/'config.yaml').exists(): raise SystemExit(1)
root_cfg=yaml.safe_load((root/'config.yaml').read_text()) or {}
root_kb=root_cfg.get('kanban') if isinstance(root_cfg.get('kanban'),dict) else {}
canonical_orchestrator=str(root_kb.get('orchestrator_profile') or '').strip()
if canonical_orchestrator not in known: canonical_orchestrator='default'
canonical_assignee=str(root_kb.get('default_assignee') or '').strip()
if canonical_assignee not in known:
    # Prefer another installer-managed profile when available; never silently reroute
    # work into an unrelated user-owned profile merely because its directory exists.
    candidates=[n for n in names if n in known and n != canonical_orchestrator]
    canonical_assignee=candidates[0] if candidates else canonical_orchestrator
canonical_review=root_kb.get('review_dispatch') if isinstance(root_kb.get('review_dispatch'),bool) else True
for p in paths:
    if not p.exists(): raise SystemExit(1)
    cfg=yaml.safe_load(p.read_text()) or {}
    if cfg.get('multiplex_profiles') is True: raise SystemExit(1)
    gateway=cfg.get('gateway') or {}
    if not isinstance(gateway,dict) or gateway.get('multiplex_profiles') is not False: raise SystemExit(1)
    envp=p.parent/'.env'
    if envp.exists() and any(line.startswith('GATEWAY_MULTIPLEX_PROFILES=') for line in envp.read_text().splitlines()): raise SystemExit(1)
    tools=cfg.get('toolsets') or []
    if isinstance(tools,str): tools=[tools]
    if ('kanban' in tools) != bool(opts.get('kanban')): raise SystemExit(1)
    skills=cfg.get('skills') or {}
    if not isinstance(skills,dict) or not isinstance(skills.get('write_approval'),bool): raise SystemExit(1)
    soul=p.parent/'SOUL.md'
    soul_text=soul.read_text(encoding='utf-8') if soul.exists() else ''
    if '<!-- HERMES_SKILL_MANAGEMENT_POLICY_START -->' not in soul_text or '<!-- HERMES_SKILL_MANAGEMENT_POLICY_END -->' not in soul_text: raise SystemExit(1)
    plugins=cfg.get('plugins') or {}; enabled=plugins.get('enabled') or []; disabled=plugins.get('disabled') or []
    if isinstance(enabled,str): enabled=[enabled]
    if isinstance(disabled,str): disabled=[disabled]
    if opts.get('kanban'):
        kb=cfg.get('kanban') or {}
        if kb.get('dispatch_in_gateway') is not True: raise SystemExit(1)
        if kb.get('dispatch_interval_seconds') != 30: raise SystemExit(1)
        if kb.get('review_dispatch') is not canonical_review: raise SystemExit(1)
        if kb.get('auto_decompose') is not True or kb.get('auto_decompose_per_tick') != 1: raise SystemExit(1)
        if kb.get('auto_subscribe_on_create') is not True: raise SystemExit(1)
        if kb.get('orchestrator_profile') != canonical_orchestrator: raise SystemExit(1)
        if kb.get('default_assignee') != canonical_assignee: raise SystemExit(1)
        if kb.get('orchestrator_profile') not in known or kb.get('default_assignee') not in known: raise SystemExit(1)
        if kb.get('max_in_progress') != int(opts.get('kanbanMaxInProgress') or 2): raise SystemExit(1)
        if kb.get('max_in_progress_per_profile') != int(opts.get('kanbanMaxInProgressPerProfile') or 1): raise SystemExit(1)
        if 'latticevale-kanban-policy' not in enabled: raise SystemExit(1)
        if '<!-- HERMES_AUTO_KANBAN_POLICY_START -->' not in soul_text or '<!-- HERMES_AUTO_KANBAN_POLICY_END -->' not in soul_text: raise SystemExit(1)
        plugin=p.parent/'plugins'/'latticevale-kanban-policy'
        manifest=(plugin/'plugin.yaml').read_text(encoding='utf-8') if (plugin/'plugin.yaml').exists() else ''
        code=(plugin/'__init__.py').read_text(encoding='utf-8') if (plugin/'__init__.py').exists() else ''
        if 'version: "1.2.0"' not in manifest: raise SystemExit(1)
        if '_guard_kanban_tool' not in code or '_modify' not in code or 'HERMES_KANBAN_TASK' not in code: raise SystemExit(1)
        if '"action": "modify"' not in code: raise SystemExit(1)
    else:
        if 'latticevale-kanban-policy' in enabled: raise SystemExit(1)
    if 'browser' not in tools: raise SystemExit(1)
    browser=cfg.get('browser') or {}
    if not isinstance(browser,dict) or not str(browser.get('engine') or '').strip(): raise SystemExit(1)
    env_keys=set()
    if envp.exists():
        for line in envp.read_text(encoding='utf-8',errors='replace').splitlines():
            line=line.strip()
            if line and not line.startswith('#') and '=' in line:
                env_keys.add(line.split('=',1)[0].strip())
    browser_selection_env_keys={'BROWSER_USE_API_KEY','BROWSERBASE_API_KEY','BROWSERBASE_PROJECT_ID','CAMOFOX_URL','BROWSER_CDP_URL'}
    tool_gateway=cfg.get('tool_gateway') if isinstance(cfg.get('tool_gateway'),dict) else {}
    gateway_browser=str(tool_gateway.get('browser') or '').strip().lower()=='gateway'
    explicit_backend=str(browser.get('backend') or '').strip()
    if not str(browser.get('cloud_provider') or '').strip() and not explicit_backend and not gateway_browser and not (env_keys & browser_selection_env_keys): raise SystemExit(1)
    auxiliary=cfg.get('auxiliary') or {}
    web_extract_aux=auxiliary.get('web_extract') if isinstance(auxiliary,dict) else None
    if not isinstance(web_extract_aux,dict): raise SystemExit(1)
    timeout=web_extract_aux.get('timeout')
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or timeout <= 0: raise SystemExit(1)
    web=cfg.get('web') or {}
    if bool(web.get('search_backend')=='searxng') != bool(opts.get('searxng')): raise SystemExit(1)
    shared=str(web.get('backend') or '').strip()
    extract=str(web.get('extract_backend') or '').strip()
    if opts.get('searxng') and shared in {'','searxng'} and extract in {'','searxng'}: raise SystemExit(1)
    if opts.get('searxng') and shared not in {'','searxng'} and extract=='latticevale-local': raise SystemExit(1)
    if not opts.get('searxng') and extract=='latticevale-local': raise SystemExit(1)
    if extract=='latticevale-local':
        if 'web/latticevale-web-extract' not in enabled or 'latticevale-web-extract' in disabled: raise SystemExit(1)
        plugin=p.parent/'plugins'/'web'/'latticevale-web-extract'
        manifest=(plugin/'plugin.yaml').read_text(encoding='utf-8') if (plugin/'plugin.yaml').exists() else ''
        init=(plugin/'__init__.py').read_text(encoding='utf-8') if (plugin/'__init__.py').exists() else ''
        provider=(plugin/'provider.py').read_text(encoding='utf-8') if (plugin/'provider.py').exists() else ''
        if 'name: latticevale-web-extract' not in manifest or 'latticevale-local' not in manifest: raise SystemExit(1)
        if 'register_web_search_provider' not in init: raise SystemExit(1)
        if 'class LatticeValeLocalExtractProvider' not in provider or 'supports_extract' not in provider: raise SystemExit(1)
        if 'create_ssrf_safe_client' not in provider or 'normalize_url_for_request' not in provider or 'sensitive_query_param_name' not in provider or 'is_safe_url' not in provider or 'follow_redirects=False' not in provider: raise SystemExit(1)
    elif 'web/latticevale-web-extract' in enabled:
        raise SystemExit(1)
    mcp=cfg.get('mcp_servers') or {}
    if ('qmd' in mcp) != bool(opts.get('qmd')): raise SystemExit(1)
    mem=cfg.get('memory') or {}
    if bool(mem.get('provider')=='honcho') != bool(opts.get('honcho')): raise SystemExit(1)
    if ('dashboard_auth/basic' in enabled) != bool(opts.get('dashboard')): raise SystemExit(1)
matrix_keys={'MATRIX_HOMESERVER','MATRIX_ACCESS_TOKEN','MATRIX_USER_ID','MATRIX_PASSWORD','MATRIX_ALLOWED_USERS','MATRIX_ALLOWED_ROOMS','MATRIX_E2EE_MODE','MATRIX_DEVICE_ID','MATRIX_RECOVERY_KEY','MATRIX_RECOVERY_KEY_OUTPUT_FILE','MATRIX_REACTIONS','MATRIX_APPROVAL_REQUIRE_SENDER'}
if opts.get('matrix'):
    keys={}
    for line in (root/'.env').read_text().splitlines() if (root/'.env').exists() else []:
        if '=' in line: keys[line.split('=',1)[0]]=1
    need={'MATRIX_HOMESERVER','MATRIX_ACCESS_TOKEN','MATRIX_USER_ID','MATRIX_ALLOWED_USERS','MATRIX_ALLOWED_ROOMS','MATRIX_E2EE_MODE','MATRIX_DEVICE_ID','MATRIX_REACTIONS','MATRIX_APPROVAL_REQUIRE_SENDER'}
    if not need.issubset(keys): raise SystemExit(1)
    values={}
    for line in (root/'.env').read_text().splitlines() if (root/'.env').exists() else []:
        if '=' in line:
            k,v=line.split('=',1); values[k]=v.strip().lower()
    if values.get('MATRIX_REACTIONS')!='true' or values.get('MATRIX_APPROVAL_REQUIRE_SENDER')!='true': raise SystemExit(1)
else:
    root_env=(root/'.env').read_text(encoding='utf-8',errors='replace') if (root/'.env').exists() else ''
    if any(line.split('=',1)[0] in matrix_keys for line in root_env.splitlines() if '=' in line): raise SystemExit(1)
for name in names:
    envp=root/'profiles'/name/'.env'
    if not envp.exists(): continue
    present={line.split('=',1)[0] for line in envp.read_text(encoding='utf-8',errors='replace').splitlines() if '=' in line}
    enabled=bool(opts.get('matrix')) and any(w.get('name')==name and isinstance(w.get('matrix'),dict) and w['matrix'].get('enabled') is True for w in (opts.get('workers') or []))
    if not enabled and (present & matrix_keys): raise SystemExit(1)
raise SystemExit(0)
PY_VERIFY_INTEGRATIONS
}


verify_reconcile() {
  # This verifier is called both to adopt an already-complete checkpoint and after the
  # reconcile action. Keep it strict about real failures, but make startup settling
  # explicit and diagnostic instead of returning a generic exit 1.
  if ! docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1; then
    echo 'Reconcile verification failed: Hermes CLI is not ready inside hermes-agent.' >&2
    return 1
  fi
  if ! http_status_ok http://127.0.0.1:${HERMES_API_HOST_PORT}/health; then
    echo 'Reconcile verification failed: Hermes API health endpoint is not ready.' >&2
    return 1
  fi
  if [[ "$(opt_bool dashboard)" == true ]] && ! http_status_ok http://127.0.0.1:${DASHBOARD_HOST_PORT}/; then
    echo 'Reconcile verification failed: Dashboard endpoint is not ready.' >&2
    return 1
  fi
  if ! verify_live_resource_policy_limits; then
    echo 'Reconcile verification failed: live Docker CPU/RAM ceilings do not match the current adaptive resource policy.' >&2
    return 1
  fi
  if managed_ollama_enabled; then
    local ollama_health
    ollama_health="$(docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null || true)"
    if [[ "$ollama_health" != healthy ]]; then
      echo "Reconcile verification failed: managed Ollama is not healthy (state: ${ollama_health:-unknown})." >&2
      return 1
    fi
  fi
  if windows_native_ollama_enabled; then
    local native_base
    native_base="$(ollama_api_base_url)" || {
      echo 'Reconcile verification failed: native Windows Ollama API base URL is unavailable.' >&2
      return 1
    }
    if ! timeout --foreground --kill-after=5s 15s python3 - "$native_base" <<'PY_NATIVE_RECONCILE' >/dev/null 2>&1
import sys,urllib.request
urllib.request.urlopen(sys.argv[1].rstrip('/')+'/api/tags',timeout=5).read()
PY_NATIVE_RECONCILE
    then
      echo 'Reconcile verification failed: native Windows Ollama /api/tags is unreachable.' >&2
      return 1
    fi
  fi
  if [[ "$(opt_bool hermesLocalAI)" == true ]]; then
    local hermes_local_url
    hermes_local_url="$(local_text_openai_base_url)"
    if ! docker exec hermes-agent python - "$hermes_local_url" <<'PY_HERMES_LOCAL_RECONCILE' >/dev/null 2>&1
import sys,urllib.request
base=sys.argv[1].rstrip('/')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(base+'/models',timeout=5) as r:
    if not r.read(4096): raise SystemExit(1)
PY_HERMES_LOCAL_RECONCILE
    then
      echo 'Reconcile verification failed: Hermes cannot reach its configured local OpenAI-compatible text backend.' >&2
      return 1
    fi
  fi
  if [[ "$(opt_bool matrix)" == true ]]; then
    if ! matrix_client_api_ready; then
      echo 'Reconcile verification failed: Matrix Client-Server API is not ready on the WSL host.' >&2
      return 1
    fi
    if ! matrix_backend_ready_from_hermes; then
      echo 'Reconcile verification failed: Synapse is not reachable as synapse:8008 from inside hermes-agent.' >&2
      return 1
    fi
  fi
  if [[ "$(opt_bool searxng)" == true ]] && ! http_status_ok http://127.0.0.1:${SEARXNG_HOST_PORT}/; then
    echo 'Reconcile verification failed: SearXNG endpoint is not ready.' >&2
    return 1
  fi
  if [[ "$(opt_bool qmd)" == true ]] && ! qmd_health_ok; then
    echo 'Reconcile verification failed: QMD is not healthy.' >&2
    return 1
  fi
  if [[ "$(opt_bool honcho)" == true ]] && ! http_status_ok http://127.0.0.1:${HONCHO_HOST_PORT}/health; then
    echo 'Reconcile verification failed: Honcho API is not ready.' >&2
    return 1
  fi
  return 0
}

verify_kanban_gateway() {
  docker compose ps --status running hermes 2>/dev/null | grep -q hermes || return 1
  docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1 || return 1
  http_status_ok "http://127.0.0.1:${HERMES_API_HOST_PORT}/health" || return 1
  if [[ "$(opt_bool dashboard)" == true ]]; then
    http_status_ok "http://127.0.0.1:${DASHBOARD_HOST_PORT}/" || return 1
  fi
  if [[ "$(opt_bool matrix)" == true ]]; then
    matrix_client_api_ready || return 1
    matrix_backend_ready_from_hermes || return 1
  fi
  if [[ "$(opt_bool kanban)" == true ]]; then
    docker exec -u hermes hermes-agent hermes kanban list >/dev/null 2>&1 || return 1
  fi
  return 0
}

verify_finalize() { [[ -s .install-info && -e .configured && -s "$STATE_FILE" ]]; }

state_init
if [[ "$(opt_bool resetCheckpoints)" == true ]]; then
  python3 - "$STATE_FILE" <<'PY_RESET'
from pathlib import Path
import json,sys
p=Path(sys.argv[1]); d=json.loads(p.read_text()); d['stages']={}; d['status']='running'; d['currentStage']='checkpoint-reset'; p.write_text(json.dumps(d,indent=2)+'\n'); p.chmod(0o600)
PY_RESET
fi

# Cross-stage helpers must be defined at script load time. Resume / repair may
# legitimately skip the prepare-config stage and continue at the later integrations stage.
# Keeping these helpers global preserves the v14.5.2 repair invariant that any
# independently resumed stage has all of its callable dependencies available.
choose_honcho_timeout() {
  local cpus accel text_mib=0 timeout
  cpus="$(nproc 2>/dev/null || printf 4)"; [[ "$cpus" =~ ^[0-9]+$ ]] || cpus=4
  if directml_text_enabled; then
    # DirectML has a potentially expensive first model load but subsequent calls are
    # GPU-backed through the shared gateway. Give cold starts room without inheriting
    # CPU-Ollama's larger model-size timeout penalties.
    timeout=150
  elif windows_native_ollama_enabled; then
    timeout=150
  else
    accel="$(sed -n 's/^LATTICEVALE_OLLAMA_ACCELERATION=//p' .env 2>/dev/null | head -n1)"; [[ -n "$accel" ]] || accel="$(resolve_ollama_acceleration 2>/dev/null || printf cpu)"
    if [[ "$accel" == cpu ]]; then
      if (( cpus <= 4 )); then timeout=180; elif (( cpus <= 8 )); then timeout=150; else timeout=120; fi
    else
      timeout=90
    fi
  fi
  text_mib="$(ollama_model_manifest_mib "$(opt_text localTextModel)" 2>/dev/null || printf 0)"
  if ! directml_text_enabled && [[ "$text_mib" =~ ^[0-9]+$ ]]; then
    if (( text_mib >= 16384 )); then timeout=$((timeout+120)); elif (( text_mib >= 8192 )); then timeout=$((timeout+60)); elif (( text_mib >= 4096 )); then timeout=$((timeout+30)); fi
  fi
  (( timeout > 300 )) && timeout=300
  printf '%s' "$timeout"
}

apply_honcho_timeout_policy() {
  local path="$1" recommended marker
  [[ -s "$path" ]] || return 1
  recommended="$(choose_honcho_timeout)" || return 1
  marker="${path}.latticevale-timeout-auto"
  python3 - "$path" "$marker" "$recommended" <<'PY_HONCHO_TIMEOUT'
from pathlib import Path
import json,sys
path=Path(sys.argv[1]); marker=Path(sys.argv[2]); recommended=float(sys.argv[3])
try: cfg=json.loads(path.read_text(encoding='utf-8'))
except Exception as exc: raise SystemExit(f'Invalid Honcho JSON {path}: {exc}')
if not isinstance(cfg,dict): raise SystemExit('Honcho config root must be an object')
current=cfg.get('timeout', cfg.get('requestTimeout'))
previous=None
try: previous=float(marker.read_text(encoding='utf-8').strip()) if marker.is_file() else None
except Exception: previous=None
owned=(current is None) or (previous is not None and isinstance(current,(int,float)) and float(current)==previous)
if owned:
    cfg.pop('requestTimeout',None)
    cfg['timeout']=recommended
    path.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    path.chmod(0o600)
    marker.write_text(str(int(recommended) if recommended.is_integer() else recommended)+'\n',encoding='utf-8')
    marker.chmod(0o600)
    print(f'Honcho request timeout: LatticeVale-managed {recommended:g}s ({path})')
else:
    marker.unlink(missing_ok=True)
    print(f'Preserving user-set Honcho request timeout={current} ({path})')
PY_HONCHO_TIMEOUT
}

stage_prepare_config() {
assert_docker_namespace_safe
mkdir -p backups config/searxng config/honcho data/hermes data/qmd/config data/qmd/cache data/synapse data/synapse-db \
  data/honcho-db data/honcho-redis data/searxng-valkey secrets vault vendor workspace
managed_ollama_enabled && mkdir -p data/ollama
chmod 0700 secrets data/hermes data/synapse
chmod 0750 workspace data/qmd data/qmd/config data/qmd/cache

# Never chmod/chown through an external vault target. A Windows-backed DrvFS/9p
# directory can reject POSIX mode changes, and a stale bind/symlink would redirect
# permissions changes outside the installer-owned Linux stack. The Windows stage
# reconciles known legacy Obsidian targets before bootstrap; this is defense in depth.
if [[ -L vault ]]; then
  echo "Installer-owned vault path '$PWD/vault' is a symbolic link. LatticeVale will not change permissions through it; rerun the Windows installer so the target can be inspected/reconciled explicitly." >&2
  return 1
fi
if mountpoint -q -- vault 2>/dev/null; then
  vault_mount_info="$(findmnt -n -o SOURCE,FSTYPE,OPTIONS -T vault 2>/dev/null | head -n1 || true)"
  echo "Installer-owned vault path '$PWD/vault' is still a mountpoint (${vault_mount_info:-unknown source/filesystem}). LatticeVale will not chmod an external mount; rerun the Windows installer and explicitly reconcile it." >&2
  return 1
fi
chmod 0750 vault

# Windows Obsidian needs a normal Windows-local vault for reliable file watching.
# Hermes/QMD mount that same Windows folder through WSL. Repair copies legacy
# stack-vault files non-destructively; existing Windows vault files always win.
obsidian_vault_host_path=''
if [[ "$(opt_bool obsidian)" == true ]]; then
  obsidian_vault_host_path="$(opt_text obsidianVaultWslPath)"
  [[ -n "$obsidian_vault_host_path" && "$obsidian_vault_host_path" == /* && "$obsidian_vault_host_path" != / ]] || { echo 'Obsidian is selected but its Windows-native WSL vault path is missing or invalid.' >&2; return 1; }
  obsidian_vault_fs="$(findmnt -n -o FSTYPE -T "$obsidian_vault_host_path" 2>/dev/null | head -n1 || true)"
  case "${obsidian_vault_fs,,}" in
    9p|drvfs|fuseblk|ntfs|ntfs3) ;;
    *) echo "Obsidian vault source '$obsidian_vault_host_path' is not verified as Windows-backed storage (filesystem: ${obsidian_vault_fs:-unknown})." >&2; return 1;;
  esac
  mkdir -p -- "$obsidian_vault_host_path"
  if find vault -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .; then
    echo "Migrating legacy WSL stack-vault files into Windows Obsidian vault (existing Windows files are never overwritten): $obsidian_vault_host_path"
    cp -a -n vault/. "$obsidian_vault_host_path"/ || { echo 'Could not safely copy the legacy WSL vault into the Windows Obsidian vault.' >&2; return 1; }
    echo 'The original WSL vault files are preserved as a fallback; Compose now mounts the Windows vault as /vault.'
  fi
fi
: > /dev/null
[[ -e secrets/hermes-runtime.env ]] || : > secrets/hermes-runtime.env
[[ -e secrets/honcho.env ]] || : > secrets/honcho.env
chmod 0600 secrets/hermes-runtime.env secrets/honcho.env

# Compose profiles are generated solely from the user's selections.
profiles=()
[[ "$(opt_bool matrix)" == true ]] && profiles+=(matrix)
[[ "$(opt_bool searxng)" == true ]] && profiles+=(search)
[[ "$(opt_bool qmd)" == true ]] && profiles+=(qmd)
[[ "$(opt_bool honcho)" == true ]] && profiles+=(honcho)
managed_ollama_enabled && profiles+=(local-ai)
compose_profiles="$(IFS=,; echo "${profiles[*]:-}")"
if windows_native_ollama_enabled && [[ ",$compose_profiles," == *,local-ai,* ]]; then
  echo 'Internal Ollama backend error: native Windows Ollama was selected but the managed local-ai Compose profile is active. Refusing to download/start the managed Ollama image.' >&2
  return 1
fi
# If a previously selected optional service is now disabled, stop/remove only its containers. Persistent data is retained.
# v3 migration: old releases used Tailscale containers inside WSL; remove those containers unconditionally but leave their data folders untouched.
timeout --foreground --kill-after=5s 60s docker rm -f hermes-tailscale hermes-tailscale-matrix >/dev/null 2>&1 || true
[[ "$(opt_bool matrix)" == true ]] || { docker rm -f hermes-synapse hermes-synapse-db >/dev/null 2>&1 || true; }
[[ "$(opt_bool searxng)" == true ]] || { docker rm -f hermes-searxng hermes-searxng-valkey >/dev/null 2>&1 || true; }
[[ "$(opt_bool qmd)" == true ]] || { docker rm -f hermes-qmd hermes-qmd-indexer >/dev/null 2>&1 || true; }
[[ "$(opt_bool honcho)" == true ]] || { timeout --foreground --kill-after=5s 60s docker rm -f hermes-honcho-api hermes-honcho-deriver hermes-honcho-db hermes-honcho-redis >/dev/null 2>&1 || true; }
managed_ollama_enabled || { docker rm -f hermes-ollama >/dev/null 2>&1 || true; }

# Preserve database passwords across resumptions/upgrades.
RESOURCE_CONTEXT_ACCEL=cpu
if managed_ollama_enabled; then
  RESOURCE_CONTEXT_ACCEL="$(resolve_ollama_acceleration)" || return 1
fi
OLLAMA_AUTO_CONTEXT_LENGTH="$(if directml_text_enabled; then printf 4096; else choose_ollama_context_length "$RESOURCE_CONTEXT_ACCEL"; fi)" || return 1
OLLAMA_AUTO_KEEP_ALIVE="$(if directml_text_enabled; then printf '0s'; else printf '30s'; fi)"
OLLAMA_MEM_GIB="$(awk '/^MemTotal:/ {printf "%.1f", $2/1024/1024; exit}' /proc/meminfo 2>/dev/null || printf '?')"
NATIVE_WINDOWS_HOST_IP=127.0.0.1
if windows_native_ollama_enabled; then
  printf 'BACKEND=windows-native\nTRANSPORT=%s\nBRIDGE_TASK_NAME=%s\nBRIDGE_PORT=%s\nHOST_ADDRESS=%s\nTARGET_ADDRESS=%s\nTARGET_PORT=%s\nWSL_NETWORKING_MODE=%s\nWSL_NETWORKING_MODE_OWNER=%s\n' \
    "$WINDOWS_OLLAMA_TRANSPORT" "$(opt_text windowsOllamaBridgeTaskName)" "$WINDOWS_OLLAMA_BRIDGE_PORT" "$WINDOWS_OLLAMA_HOST_ADDRESS" \
    "$WINDOWS_OLLAMA_TARGET_ADDRESS" "$WINDOWS_OLLAMA_TARGET_PORT" "$(opt_text wslNetworkingMode)" "$(opt_text wslNetworkingModeOwner)" > .windows-native-info
  chmod 0600 .windows-native-info
  if [[ "$WINDOWS_OLLAMA_TRANSPORT" == wsl-localhost-relay || "$WINDOWS_OLLAMA_TRANSPORT" == wsl-host-relay ]]; then
    [[ -x ./native-ollama-relay.sh ]] || { echo 'Native Ollama WSL-local relay helper is missing; rerun the Windows installer.' >&2; return 1; }
    ./native-ollama-relay.sh start >/dev/null || { echo 'Could not start the WSL-local native Ollama relay.' >&2; return 1; }
  else
    [[ ! -x ./native-ollama-relay.sh ]] || ./native-ollama-relay.sh stop >/dev/null 2>&1 || true
  fi
  NATIVE_WINDOWS_HOST_IP="$(windows_host_ip)" || { echo 'Native Windows Ollama is selected, but its selected relay transport could not resolve a Docker-reachable host address.' >&2; return 1; }
  echo "Ollama backend: native Windows Ollama through verified WSL-only relay ${NATIVE_WINDOWS_HOST_IP}:${WINDOWS_OLLAMA_BRIDGE_PORT} (${WINDOWS_OLLAMA_TRANSPORT}). Native Ollama owns GPU/CPU selection, loaded-model limits, and keep-alive policy."
else
  [[ ! -x ./native-ollama-relay.sh ]] || ./native-ollama-relay.sh stop >/dev/null 2>&1 || true
  rm -f .windows-native-info
  echo "Ollama memory policy: WSL memory=${OLLAMA_MEM_GIB} GiB; context=${OLLAMA_AUTO_CONTEXT_LENGTH}; max-loaded-models=1; parallel=1; keep-alive=${OLLAMA_AUTO_KEEP_ALIVE}."
fi
env_was_new=false
if [[ ! -f .env ]]; then
  env_was_new=true
  cat > .env <<EOF_ENV
COMPOSE_PROJECT_NAME=hermesstack
COMPOSE_PROFILES=$compose_profiles
HERMES_IMAGE=nousresearch/hermes-agent:v2026.8.16
SYNAPSE_IMAGE=matrixdotorg/synapse:v1.158.0
POSTGRES_IMAGE=postgres:16-alpine
PGVECTOR_IMAGE=pgvector/pgvector:pg15
REDIS_IMAGE=redis:8-alpine
VALKEY_IMAGE=valkey/valkey:8-alpine
SEARXNG_IMAGE=searxng/searxng:2026.8.17-374939b88
LATTICEVALE_SEARXNG_IMAGE_AUTO=searxng/searxng:2026.8.17-374939b88
OLLAMA_IMAGE=ollama/ollama:0.32.14
LATTICEVALE_OLLAMA_IMAGE_AUTO=ollama/ollama:0.32.14
LATTICEVALE_HONCHO_SOURCE_AUTO=$HONCHO_SOURCE_COMMIT
OLLAMA_CONTEXT_LENGTH=$OLLAMA_AUTO_CONTEXT_LENGTH
LATTICEVALE_OLLAMA_CONTEXT_AUTO=$OLLAMA_AUTO_CONTEXT_LENGTH
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_NUM_PARALLEL=1
OLLAMA_KEEP_ALIVE=$OLLAMA_AUTO_KEEP_ALIVE
OLLAMA_GPU_OVERHEAD=0
LATTICEVALE_OLLAMA_GPU_OVERHEAD_AUTO=0
OLLAMA_TEXT_MODEL=$(opt_text localTextModel)
OLLAMA_EMBED_MODEL=$(opt_text localEmbeddingModel)
LATTICEVALE_LOCAL_TEXT_BACKEND=$(local_text_backend)
DIRECTML_TEXT_MODEL=$(directml_text_model)
DIRECTML_PORT=$DIRECTML_PORT
DIRECTML_CONTEXT_LENGTH=8192
DIRECTML_VRAM_LIMIT_PCT=75
HONCHO_POSTGRES_PASSWORD=$(random_hex 24)
SYNAPSE_POSTGRES_PASSWORD=$(random_hex 24)
STACK_UID=$(id -u)
STACK_GID=$(id -g)
HERMES_API_HOST_PORT=$HERMES_API_HOST_PORT
DASHBOARD_HOST_PORT=$DASHBOARD_HOST_PORT
DASHBOARD_HOST_BIND=$DASHBOARD_HOST_BIND
MATRIX_HOST_PORT=$MATRIX_HOST_PORT
MATRIX_HOST_BIND=$MATRIX_HOST_BIND
SEARXNG_HOST_PORT=$SEARXNG_HOST_PORT
HONCHO_HOST_PORT=$HONCHO_HOST_PORT
WINDOWS_HOST_IP=$NATIVE_WINDOWS_HOST_IP
WINDOWS_OLLAMA_BRIDGE_PORT=$WINDOWS_OLLAMA_BRIDGE_PORT
TZ=$timezone
QMD_VERSION=2.5.3
QMD_FORCE_CPU=1
QMD_INDEX_INTERVAL=7200
EOF_ENV
else
  set_env .env COMPOSE_PROFILES "$compose_profiles"
  set_env .env HERMES_IMAGE nousresearch/hermes-agent:v2026.8.16
  set_env .env SYNAPSE_IMAGE matrixdotorg/synapse:v1.158.0
  set_env .env POSTGRES_IMAGE postgres:16-alpine
  set_env .env PGVECTOR_IMAGE pgvector/pgvector:pg15
  set_env .env REDIS_IMAGE redis:8-alpine
  set_env .env VALKEY_IMAGE valkey/valkey:8-alpine
  # Existing installations may intentionally carry older or custom image tags. Between
  # managed refresh windows they remain untouched. During a due periodic refresh, only a
  # value proven to equal LatticeVale's last recorded automatic value advances to the
  # current tested pin; arbitrary/custom values remain user-owned.
  tested_searxng_image=searxng/searxng:2026.8.17-374939b88
  grep -q '^SEARXNG_IMAGE=' .env || set_env .env SEARXNG_IMAGE "$tested_searxng_image"
  grep -q '^OLLAMA_IMAGE=' .env || set_env .env OLLAMA_IMAGE ollama/ollama:0.32.14
  existing_searxng_image="$(sed -n 's/^SEARXNG_IMAGE=//p' .env | head -n1)"
  previous_auto_searxng_image="$(sed -n 's/^LATTICEVALE_SEARXNG_IMAGE_AUTO=//p' .env | head -n1)"
  searxng_installer_owned=false
  if [[ -n "$previous_auto_searxng_image" && "$existing_searxng_image" == "$previous_auto_searxng_image" ]]; then
    searxng_installer_owned=true
  elif [[ -z "$previous_auto_searxng_image" && "$existing_searxng_image" == "$tested_searxng_image" ]]; then
    # Adopt the exact known tested default from releases that predate the ownership marker.
    searxng_installer_owned=true
  fi
  if repair_package_refresh_pending && [[ "$searxng_installer_owned" == true ]]; then
    set_env .env SEARXNG_IMAGE "$tested_searxng_image"
    existing_searxng_image="$tested_searxng_image"
    echo "Periodic repair refresh: SearXNG remains on the current LatticeVale-tested image $tested_searxng_image."
  elif [[ "$existing_searxng_image" == *:latest || "$existing_searxng_image" == "searxng/searxng" ]]; then
    warn "Preserving existing floating SearXNG image '$existing_searxng_image' because its ownership is not proven. LatticeVale will not reinterpret an ambiguous legacy/custom value during repair."
  elif [[ "$searxng_installer_owned" != true && "$existing_searxng_image" != "$tested_searxng_image" ]]; then
    echo "Preserving user-set SEARXNG_IMAGE=$existing_searxng_image. LatticeVale tested default is $tested_searxng_image."
  fi
  if [[ "$existing_searxng_image" == "$tested_searxng_image" ]]; then
    # Record only a value that is actually active as the last installer-managed value.
    set_env .env LATTICEVALE_SEARXNG_IMAGE_AUTO "$tested_searxng_image"
  elif [[ "$searxng_installer_owned" == true && -n "$previous_auto_searxng_image" ]]; then
    # A newer bundle may have a newer tested pin, but between refresh windows keep the
    # marker on the old value actually in use so the next due refresh can still prove ownership.
    set_env .env LATTICEVALE_SEARXNG_IMAGE_AUTO "$previous_auto_searxng_image"
  elif [[ -z "$previous_auto_searxng_image" ]]; then
    # For an unproven custom/legacy value, record the tested comparison point without
    # claiming the current override itself is installer-owned.
    set_env .env LATTICEVALE_SEARXNG_IMAGE_AUTO "$tested_searxng_image"
  fi
  existing_ollama_image="$(sed -n 's/^OLLAMA_IMAGE=//p' .env | head -n1)"
  if [[ "$existing_ollama_image" == *:latest || "$existing_ollama_image" == "ollama/ollama" ]]; then
    warn "Existing floating Ollama image '$existing_ollama_image' will be changed only when it is proven installer-owned by the Ollama ownership marker or by an explicit acceleration-policy migration; otherwise it remains preserved."
  fi
  unset tested_searxng_image previous_auto_searxng_image searxng_installer_owned
  current_ollama_context="$(sed -n 's/^OLLAMA_CONTEXT_LENGTH=//p' .env | head -n1)"
  previous_auto_context="$(sed -n 's/^LATTICEVALE_OLLAMA_CONTEXT_AUTO=//p' .env | head -n1)"
  [[ -n "$previous_auto_context" ]] || previous_auto_context="$(sed -n 's/^FOUNDRY_OLLAMA_CONTEXT_AUTO=//p' .env | head -n1)"
  # Migrate the old installer-owned 65536 default, or advance a previous automatic
  # value when the WSL memory budget changes. Preserve a clearly user-overridden value.
  if [[ -z "$current_ollama_context" || "$current_ollama_context" == 65536 || ( -n "$previous_auto_context" && "$current_ollama_context" == "$previous_auto_context" ) ]]; then
    set_env .env OLLAMA_CONTEXT_LENGTH "$OLLAMA_AUTO_CONTEXT_LENGTH"
  else
    echo "Preserving user-set OLLAMA_CONTEXT_LENGTH=$current_ollama_context (automatic recommendation: $OLLAMA_AUTO_CONTEXT_LENGTH)."
  fi
  set_env .env LATTICEVALE_OLLAMA_CONTEXT_AUTO "$OLLAMA_AUTO_CONTEXT_LENGTH"
  remove_env_keys .env FOUNDRY_OLLAMA_CONTEXT_AUTO
  set_env .env OLLAMA_MAX_LOADED_MODELS 1
  set_env .env OLLAMA_NUM_PARALLEL 1
  set_env .env OLLAMA_KEEP_ALIVE "$OLLAMA_AUTO_KEEP_ALIVE"
  grep -q '^OLLAMA_GPU_OVERHEAD=' .env || set_env .env OLLAMA_GPU_OVERHEAD 0
  grep -q '^LATTICEVALE_OLLAMA_GPU_OVERHEAD_AUTO=' .env || set_env .env LATTICEVALE_OLLAMA_GPU_OVERHEAD_AUTO 0
  set_env .env OLLAMA_TEXT_MODEL "$(opt_text localTextModel)"
  set_env .env OLLAMA_EMBED_MODEL "$(opt_text localEmbeddingModel)"
  set_env .env LATTICEVALE_LOCAL_TEXT_BACKEND "$(local_text_backend)"
  set_env .env DIRECTML_TEXT_MODEL "$(directml_text_model)"
  set_env .env DIRECTML_PORT "$DIRECTML_PORT"
  set_env .env DIRECTML_CONTEXT_LENGTH 8192
  set_env .env DIRECTML_VRAM_LIMIT_PCT 75
  set_env .env QMD_VERSION 2.5.3
  set_env .env STACK_UID "$(id -u)"
  set_env .env STACK_GID "$(id -g)"
  set_env .env HERMES_API_HOST_PORT "$HERMES_API_HOST_PORT"
  set_env .env DASHBOARD_HOST_PORT "$DASHBOARD_HOST_PORT"
  set_env .env DASHBOARD_HOST_BIND "$DASHBOARD_HOST_BIND"
  set_env .env MATRIX_HOST_PORT "$MATRIX_HOST_PORT"
  set_env .env MATRIX_HOST_BIND "$MATRIX_HOST_BIND"
  set_env .env SEARXNG_HOST_PORT "$SEARXNG_HOST_PORT"
  set_env .env HONCHO_HOST_PORT "$HONCHO_HOST_PORT"
  set_env .env WINDOWS_HOST_IP "$NATIVE_WINDOWS_HOST_IP"
  set_env .env WINDOWS_OLLAMA_BRIDGE_PORT "$WINDOWS_OLLAMA_BRIDGE_PORT"
  set_env .env TZ "$timezone"
  grep -q '^HONCHO_POSTGRES_PASSWORD=' .env || set_env .env HONCHO_POSTGRES_PASSWORD "$(random_hex 24)"
  grep -q '^SYNAPSE_POSTGRES_PASSWORD=' .env || set_env .env SYNAPSE_POSTGRES_PASSWORD "$(random_hex 24)"
fi

# v13.16.6: built-in QMD indexing now runs every two hours. Migrate only the old
# LatticeVale 6-hour default; preserve a deliberate user override.
current_qmd_interval="$(sed -n 's/^QMD_INDEX_INTERVAL=//p' .env | head -n1)"
if [[ -z "$current_qmd_interval" || "$current_qmd_interval" == 21600 ]]; then
  set_env .env QMD_INDEX_INTERVAL 7200
elif [[ "$current_qmd_interval" != 7200 ]]; then
  echo "Preserving user-set QMD_INDEX_INTERVAL=$current_qmd_interval (LatticeVale default: 7200)."
fi
if [[ "$(opt_bool obsidian)" == true ]]; then
  set_env .env OBSIDIAN_VAULT_HOST_PATH "$obsidian_vault_host_path"
else
  remove_env_keys .env OBSIDIAN_VAULT_HOST_PATH
fi

# Remove only the exact legacy cron entry previously recommended for LatticeVale QMD.
# The built-in qmd-indexer owns the two-hour cadence now, preventing duplicate runs.
if command -v crontab >/dev/null 2>&1 && crontab -l 2>/dev/null | grep -q 'HERMES_QMD_REINDEX'; then
  cron_tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v 'HERMES_QMD_REINDEX' > "$cron_tmp" || true
  crontab "$cron_tmp"
  rm -f "$cron_tmp"
  echo 'Removed legacy HERMES_QMD_REINDEX cron entry; the built-in QMD indexer now runs every two hours.'
fi
# v3 no longer runs Tailscale inside WSL/Docker. Remove obsolete non-secret container settings from older .env files.
sed -i -E '/^TAILSCALE_(IMAGE|HOSTNAME|MATRIX_HOSTNAME)=/d' .env
chmod 0600 .env
if windows_native_ollama_enabled; then
  # .windows-native-info is written before native relay resolution so both transport
  # implementations read one canonical, non-secret description of the selected bridge.
  chmod 0600 .windows-native-info
else
  rm -f .windows-native-info
fi

OLLAMA_RESOLVED_ACCELERATION=cpu
if managed_ollama_enabled; then
  OLLAMA_RESOLVED_ACCELERATION="$(resolve_ollama_acceleration)"
elif windows_native_ollama_enabled; then
  OLLAMA_RESOLVED_ACCELERATION=windows-native
fi
ollama_accel_managed=false
if jq -e 'has("ollamaAcceleration")' install-options.json >/dev/null 2>&1; then
  ollama_accel_managed=true
fi
current_ollama_image="$(sed -n 's/^OLLAMA_IMAGE=//p' .env | head -n1)"
previous_auto_ollama_image="$(sed -n 's/^LATTICEVALE_OLLAMA_IMAGE_AUTO=//p' .env | head -n1)"
previous_resolved_acceleration="$(sed -n 's/^LATTICEVALE_OLLAMA_ACCELERATION=//p' .env | head -n1)"
desired_ollama_image=ollama/ollama:0.32.14
[[ "$OLLAMA_RESOLVED_ACCELERATION" == amd ]] && desired_ollama_image=ollama/ollama:0.32.14-rocm
if [[ "$ollama_accel_managed" == true && "$(ollama_backend)" == managed ]]; then
  installer_owned_ollama_image=false
  ollama_policy_switch=false
  if [[ "$env_was_new" == true || -z "$current_ollama_image" ]]; then
    installer_owned_ollama_image=true
  elif [[ -n "$previous_auto_ollama_image" && "$current_ollama_image" == "$previous_auto_ollama_image" ]]; then
    installer_owned_ollama_image=true
  elif [[ -z "$previous_auto_ollama_image" && "$current_ollama_image" =~ ^ollama/ollama:(latest|0\.32\.14|0\.32\.14-rocm)$ ]]; then
    # v14.2.0 did not yet persist an image-ownership marker. Recognize only its
    # exact installer defaults/floating predecessor; arbitrary custom tags stay user-owned.
    installer_owned_ollama_image=true
  fi
  if [[ -n "$previous_resolved_acceleration" && "$previous_resolved_acceleration" != "$OLLAMA_RESOLVED_ACCELERATION" ]]; then
    # An explicit acceleration-policy change may require switching standard <-> ROCm now,
    # independently of the periodic refresh window.
    ollama_policy_switch=true
    installer_owned_ollama_image=true
  fi
  if [[ "$installer_owned_ollama_image" == true ]]; then
    if [[ "$env_was_new" == true || -z "$current_ollama_image" || "$current_ollama_image" == "$desired_ollama_image" ]] || repair_package_refresh_pending || [[ "$ollama_policy_switch" == true ]]; then
      set_env .env OLLAMA_IMAGE "$desired_ollama_image"
      current_ollama_image="$desired_ollama_image"
      set_env .env LATTICEVALE_OLLAMA_IMAGE_AUTO "$desired_ollama_image"
    else
      echo "Preserving installer-owned OLLAMA_IMAGE=$current_ollama_image until the periodic managed refresh is due (current tested pin: $desired_ollama_image)."
      [[ -n "$previous_auto_ollama_image" ]] && set_env .env LATTICEVALE_OLLAMA_IMAGE_AUTO "$previous_auto_ollama_image"
    fi
  else
    echo "Preserving user-set OLLAMA_IMAGE=$current_ollama_image. LatticeVale tested default for acceleration=$OLLAMA_RESOLVED_ACCELERATION is $desired_ollama_image."
    [[ -n "$previous_auto_ollama_image" ]] || set_env .env LATTICEVALE_OLLAMA_IMAGE_AUTO "$desired_ollama_image"
  fi
fi
set_env .env LATTICEVALE_OLLAMA_ACCELERATION "$OLLAMA_RESOLVED_ACCELERATION"
unset current_ollama_image previous_auto_ollama_image previous_resolved_acceleration desired_ollama_image installer_owned_ollama_image ollama_policy_switch env_was_new
overlay_acceleration="$OLLAMA_RESOLVED_ACCELERATION"
[[ "$overlay_acceleration" == windows-native ]] && overlay_acceleration=cpu
write_latticevale_compose_overlay "$overlay_acceleration" "$(opt_bool containerResourceLimits)"
timeout --foreground --kill-after=5s 60s docker compose config --quiet

# The compose file publishes the default Hermes OpenAI-compatible API on a
# loopback-only Windows host port. API settings are intentionally profile-local:
# current Hermes Docker supervision can run named profile gateways in this same
# container, and container-wide API_SERVER_* variables would be inherited by every
# profile and force them to collide on the default port. Preserve an older installer
# key when migrating it, then remove all API server variables from the container-wide
# runtime env. Browser CORS remains disabled by default.
[[ -e data/hermes/.env ]] || : > data/hermes/.env
api_server_key="$(read_env_file_value_optional data/hermes/.env API_SERVER_KEY)"
if [[ ${#api_server_key} -lt 16 ]]; then
  legacy_api_server_key="$(read_env_file_value_optional secrets/hermes-runtime.env API_SERVER_KEY)"
  if [[ ${#legacy_api_server_key} -ge 16 ]]; then api_server_key="$legacy_api_server_key"; else api_server_key="$(random_hex 32)"; fi
  unset legacy_api_server_key
fi
set_env data/hermes/.env API_SERVER_ENABLED true
set_env data/hermes/.env API_SERVER_HOST 0.0.0.0
set_env data/hermes/.env API_SERVER_PORT 8642
set_env data/hermes/.env API_SERVER_KEY "$api_server_key"
remove_env_keys data/hermes/.env API_SERVER_CORS_ORIGINS
remove_env_keys secrets/hermes-runtime.env API_SERVER_ENABLED API_SERVER_HOST API_SERVER_PORT API_SERVER_KEY API_SERVER_CORS_ORIGINS API_SERVER_MODEL_NAME
# Do not allow the container environment to opt s6 into multiplex mode while
# profile YAML is normalized to standalone gateways. This prevents a split-brain
# topology and the associated per-profile restart loops.
remove_env_keys secrets/hermes-runtime.env GATEWAY_MULTIPLEX_PROFILES
unset api_server_key
chmod 0600 data/hermes/.env secrets/hermes-runtime.env

if [[ "$(opt_bool dashboard)" == true ]]; then
  # Migrate an older plaintext bundle credential to Hermes's preferred scrypt form.
  if grep -q '^HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=' secrets/hermes-runtime.env 2>/dev/null && \
     ! grep -q '^HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=' secrets/hermes-runtime.env 2>/dev/null; then
    legacy_password="$(sed -n 's/^HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=//p' secrets/hermes-runtime.env | head -n1)"
    [[ -n "$legacy_password" ]] && set_env secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH "$(printf '%s' "$legacy_password" | hash_dashboard_password)"
    unset legacy_password
    remove_env_keys secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_PASSWORD
  fi
  have_dash_creds=false
  if grep -q '^HERMES_DASHBOARD_BASIC_AUTH_USERNAME=' secrets/hermes-runtime.env 2>/dev/null && \
     grep -q '^HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=' secrets/hermes-runtime.env 2>/dev/null; then
    have_dash_creds=true
    existing_dash_user="$(sed -n 's/^HERMES_DASHBOARD_BASIC_AUTH_USERNAME=//p' secrets/hermes-runtime.env | head -n1)"
    echo
    echo "Existing Dashboard credentials found for '$existing_dash_user'. The password itself is not stored."
    echo '  YES: keep the current dashboard login.'
    echo '  NO = SAFE: replace it with a new username/password; installation continues.'
    if ! read_yes_no 'Keep these Dashboard credentials?' yes; then have_dash_creds=false; fi
  fi
  if [[ "$have_dash_creds" != true ]]; then
    echo
    echo 'Dashboard security: choose credentials used only by the Hermes dashboard.'
    default_dash_user="${USER//[^a-zA-Z0-9_.-]/}"
    default_dash_user="${default_dash_user:-owner}"
    while true; do
      read -r -p "Dashboard username [$default_dash_user]: " dash_user
      dash_user="${dash_user:-$default_dash_user}"
      dash_user="${dash_user#"${dash_user%%[![:space:]]*}"}"
      dash_user="${dash_user%"${dash_user##*[![:space:]]}"}"
      if [[ "$dash_user" =~ ^[A-Za-z0-9_.-]{1,64}$ ]]; then break; fi
      echo 'Use 1-64 letters, numbers, ., _, or - for the Dashboard username.' >&2
    done
    dash_password="$(read_password_twice 'Dashboard password')"
    dash_hash="$(printf '%s' "$dash_password" | hash_dashboard_password)"
    set_env secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_USERNAME "$dash_user"
    set_env secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH "$dash_hash"
    # Rotating the signing secret invalidates old sessions whenever credentials are replaced.
    set_env secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_SECRET "$(random_hex 32)"
    unset dash_password dash_hash
  fi
  set_env secrets/hermes-runtime.env HERMES_DASHBOARD 1
  set_env secrets/hermes-runtime.env HERMES_DASHBOARD_HOST 0.0.0.0
  set_env secrets/hermes-runtime.env HERMES_DASHBOARD_PORT 9119
  grep -q '^HERMES_DASHBOARD_BASIC_AUTH_SECRET=' secrets/hermes-runtime.env || set_env secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_SECRET "$(random_hex 32)"
  # v13 migration: v12 wrote the scrypt hash unquoted. Docker Compose interprets
  # '$NAME' sequences in such env-file values and can silently blank part of it.
  quote_env_key_literal secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH
  remove_env_keys secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_PASSWORD
else
  remove_env_keys secrets/hermes-runtime.env HERMES_DASHBOARD HERMES_DASHBOARD_HOST HERMES_DASHBOARD_PORT \
    HERMES_DASHBOARD_BASIC_AUTH_USERNAME HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH \
    HERMES_DASHBOARD_BASIC_AUTH_PASSWORD HERMES_DASHBOARD_BASIC_AUTH_SECRET HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS
fi
chmod 0600 secrets/hermes-runtime.env

if [[ "$(opt_bool searxng)" == true ]]; then
  if [[ ! -s config/searxng/settings.yml ]]; then
    searxng_secret="$(random_hex 32)"
    python3 - "$searxng_secret" <<'PY'
from pathlib import Path
import sys,yaml
cfg={
 'use_default_settings': True,
 'general': {'instance_name':'LatticeVale Search'},
 'search': {'safe_search':1,'formats':['html','json']},
 'server': {'secret_key':sys.argv[1],'limiter':False,'public_instance':False,'bind_address':'0.0.0.0'},
 'valkey': {'url':'valkey://searxng-valkey:6379/0'},
}
Path('config/searxng/settings.yml').write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY
  fi
  # v14.1.3 rebrand migration: change only the exact historical installer-owned
  # default title. A user-customized SearXNG instance name is preserved.
  python3 - <<'PY_SEARXNG_BRAND'
from pathlib import Path
import yaml
p=Path('config/searxng/settings.yml')
try:
    cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
except Exception:
    raise SystemExit(0)
general=cfg.get('general')
if isinstance(general,dict) and general.get('instance_name') == 'Hermes Search':
    general['instance_name']='LatticeVale Search'
    p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY_SEARXNG_BRAND
fi

if [[ "$(opt_bool honcho)" == true ]]; then
  # Honcho source follows the same ownership boundary as image pins. A due periodic repair
  # may advance only a checkout proven to be the last LatticeVale-managed commit. A custom
  # checkout/remote is preserved. This restores aged-repair convergence without turning
  # ordinary repair into an upstream source update.
  previous_auto_honcho_commit="$(sed -n 's/^LATTICEVALE_HONCHO_SOURCE_AUTO=//p' .env | head -n1)"
  if [[ ! -d vendor/honcho/.git ]]; then
    echo "Fetching audited self-hosted Honcho source commit $HONCHO_SOURCE_COMMIT."
    rm -rf vendor/honcho
    git init -q vendor/honcho
    git -C vendor/honcho remote add origin https://github.com/plastic-labs/honcho.git
    timeout --foreground --kill-after=15s 900s git -C vendor/honcho fetch --depth 1 origin "$HONCHO_SOURCE_COMMIT"
    git -C vendor/honcho checkout -q --detach FETCH_HEAD
    resolved_honcho_commit="$(git -C vendor/honcho rev-parse HEAD)"
    [[ "$resolved_honcho_commit" == "$HONCHO_SOURCE_COMMIT" ]] || { echo 'Honcho source pin verification failed.' >&2; exit 1; }
    set_env .env LATTICEVALE_HONCHO_SOURCE_AUTO "$HONCHO_SOURCE_COMMIT"
    unset resolved_honcho_commit
  else
    honcho_commit="$(git -C vendor/honcho rev-parse HEAD 2>/dev/null || true)"
    honcho_origin="$(git -C vendor/honcho remote get-url origin 2>/dev/null || true)"
    if [[ -z "$honcho_commit" ]]; then
      echo 'Existing Honcho source checkout is invalid; preserving it and stopping instead of overwriting it.' >&2
      exit 1
    fi
    honcho_installer_owned=false
    if [[ "$honcho_origin" == 'https://github.com/plastic-labs/honcho.git' ]]; then
      if [[ -n "$previous_auto_honcho_commit" && "$honcho_commit" == "$previous_auto_honcho_commit" ]]; then
        honcho_installer_owned=true
      elif [[ -z "$previous_auto_honcho_commit" && "$honcho_commit" == "$HONCHO_SOURCE_COMMIT" ]]; then
        honcho_installer_owned=true
      fi
    fi
    if repair_package_refresh_pending && [[ "$honcho_installer_owned" == true ]]; then
      echo "Periodic repair refresh: reconciling installer-owned Honcho source to audited commit $HONCHO_SOURCE_COMMIT."
      timeout --foreground --kill-after=15s 900s git -C vendor/honcho fetch --depth 1 origin "$HONCHO_SOURCE_COMMIT"
      git -C vendor/honcho checkout -q --detach FETCH_HEAD
      resolved_honcho_commit="$(git -C vendor/honcho rev-parse HEAD)"
      [[ "$resolved_honcho_commit" == "$HONCHO_SOURCE_COMMIT" ]] || { echo 'Honcho source refresh pin verification failed.' >&2; exit 1; }
      set_env .env LATTICEVALE_HONCHO_SOURCE_AUTO "$HONCHO_SOURCE_COMMIT"
      honcho_commit="$resolved_honcho_commit"
      unset resolved_honcho_commit
    elif [[ "$honcho_installer_owned" == true ]]; then
      echo "Reusing installer-owned self-hosted Honcho source commit ${honcho_commit:0:12}; periodic refresh is not due."
      set_env .env LATTICEVALE_HONCHO_SOURCE_AUTO "$honcho_commit"
    else
      echo "Preserving custom/legacy Honcho source commit ${honcho_commit:0:12}; its prior LatticeVale ownership cannot be proven, so repair will not overwrite it."
      [[ -n "$previous_auto_honcho_commit" ]] || set_env .env LATTICEVALE_HONCHO_SOURCE_AUTO "$HONCHO_SOURCE_COMMIT"
    fi
    unset honcho_commit honcho_origin honcho_installer_owned
  fi
  unset previous_auto_honcho_commit

  # v12 migration: previous releases self-hosted Honcho itself but could use cloud
  # embeddings/LLM inference. Preserve a populated legacy DB/cache before switching
  # embedding spaces, then start a clean local DB so incompatible vectors are never mixed.
  # A populated pre-v12 Honcho DB may contain vectors produced by a different embedding
  # model. Detect local-v12 provenance from BOTH the active model routing and the dummy
  # local-only API key. If either proof is missing, preserve the old store before creating
  # the new local embedding space. This also covers interrupted/partial older installs whose
  # secret file is missing or incomplete.
  honcho_db_populated=false
  [[ -f data/honcho-db/PG_VERSION || -f data/honcho-db/pgdata/PG_VERSION ]] && honcho_db_populated=true
  honcho_local_config=false
  if [[ -s config/honcho/config.toml ]] &&      grep -Fq "base_url = \"$(ollama_openai_base_url)\"" config/honcho/config.toml &&      grep -Fq "base_url = \"$(local_text_openai_base_url)\"" config/honcho/config.toml &&      grep -q 'VECTOR_DIMENSIONS = 1536' config/honcho/config.toml &&      grep -q '^LLM_OPENAI_API_KEY=ollama-local$' secrets/honcho.env 2>/dev/null; then
    honcho_local_config=true
  fi
  if [[ "$honcho_db_populated" == true && "$honcho_local_config" != true ]]; then
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    echo
    echo 'Existing Honcho data predates or cannot prove the v12 local embedding configuration.'
    echo 'v12 is preserving that database/cache unchanged and initializing a fresh fully-local Honcho store.'
    timeout --foreground --kill-after=5s 60s docker rm -f hermes-honcho-api hermes-honcho-deriver hermes-honcho-db hermes-honcho-redis >/dev/null 2>&1 || true
    mv data/honcho-db "backups/honcho-db-pre-local-$stamp"
    mkdir -p data/honcho-db
    if [[ -d data/honcho-redis && -n "$(find data/honcho-redis -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
      mv data/honcho-redis "backups/honcho-redis-pre-local-$stamp"
      mkdir -p data/honcho-redis
    fi
    if [[ -e secrets/honcho.env ]]; then
      cp -a secrets/honcho.env "backups/honcho-env-pre-local-$stamp"
      chmod 0600 "backups/honcho-env-pre-local-$stamp"
    fi
  fi
  unset honcho_db_populated honcho_local_config



  # Active Honcho inference is now entirely local. "ollama-local" is a dummy
  # compatibility value for the OpenAI client; it is not a cloud credential.
  : > secrets/honcho.env
  set_env secrets/honcho.env LLM_OPENAI_API_KEY ollama-local
  chmod 0600 secrets/honcho.env

  local_text_model="$(local_text_model_name)"
  local_embedding_model="$(opt_text localEmbeddingModel)"
  python3 - "$local_text_model" "$local_embedding_model" "$(ollama_openai_base_url)" "$(local_text_openai_base_url)" <<'PY_HONCHO_LOCAL'
from pathlib import Path
import json,sys
text_model, embed_model, embedding_base, text_base = sys.argv[1:5]
q=lambda x: json.dumps(x)
sections=[]
sections += [
    '[auth]', 'USE_AUTH = false', '',
    '[sentry]', 'ENABLED = false', '',
    '[telemetry]', 'ENABLED = false', '',
    '[cache]', 'ENABLED = true', '',
    '[vector_store]', 'TYPE = "pgvector"', '',
    '[embedding]', 'VECTOR_DIMENSIONS = 1536', '',
    '[embedding.model_config]',
    'transport = "openai"',
    f'model = {q(embed_model)}',
    'dimensions_mode = "always"',
    'encoding_format_mode = "float"',
    '',
    '[embedding.model_config.overrides]',
    f'base_url = {q(embedding_base)}',
    'api_key_env = "LLM_OPENAI_API_KEY"',
    '',
]
def add_model(section):
    sections.extend([
        f'[{section}]',
        'transport = "openai"',
        f'model = {q(text_model)}',
        '',
        f'[{section}.overrides]',
        f'base_url = {q(text_base)}',
        'api_key_env = "LLM_OPENAI_API_KEY"',
        '',
    ])
add_model('deriver.model_config')
for level in ('minimal','low','medium','high','max'):
    add_model(f'dialectic.levels.{level}.model_config')
add_model('summary.model_config')
add_model('dream.deduction_model_config')
add_model('dream.induction_model_config')
Path('config/honcho/config.toml').write_text('\n'.join(sections), encoding='utf-8')
PY_HONCHO_LOCAL
  chmod 0644 config/honcho/config.toml

  if [[ ! -s data/hermes/honcho.json ]]; then
    read -r -p "Honcho human peer name [${USER:-user}]: " honcho_peer
    honcho_peer="${honcho_peer:-${USER:-user}}"
    python3 - "$honcho_peer" <<'PY'
from pathlib import Path
import json,sys
peer=sys.argv[1]
cfg={'baseUrl':'http://honcho-api:8000','hosts':{'hermes':{'enabled':True,'aiPeer':'hermes','peerName':peer,'workspace':'hermes'}}}
Path('data/hermes/honcho.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
PY
    chmod 0600 data/hermes/honcho.json
  fi
else
  # Never leave a former cloud key active after Honcho is deselected.
  remove_env_keys secrets/honcho.env LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY
fi

# Synapse config must be generated before compose starts the Matrix profile.
if [[ "$(opt_bool matrix)" == true && ! -s data/synapse/homeserver.yaml ]]; then
  echo 'Generating self-hosted Matrix/Synapse configuration.'
  synapse_image="$(grep '^SYNAPSE_IMAGE=' .env | cut -d= -f2-)"
  timeout --foreground --kill-after=15s 3600s docker pull "$synapse_image"
  docker run --rm -e SYNAPSE_SERVER_NAME=hermes.local -e SYNAPSE_REPORT_STATS=no \
    -e UID="$(id -u)" -e GID="$(id -g)" -v "$PWD/data/synapse:/data" "$synapse_image" generate
  synapse_db_password="$(grep '^SYNAPSE_POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
  registration_secret="$(random_hex 32)"
  python3 - "$synapse_db_password" "$registration_secret" "$MATRIX_HOST_PORT" <<'PY'
from pathlib import Path
import sys,yaml
p=Path('data/synapse/homeserver.yaml'); cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
cfg['database']={'name':'psycopg2','args':{'user':'synapse','password':sys.argv[1],'database':'synapse','host':'synapse-db','cp_min':5,'cp_max':10}}
cfg['enable_registration']=False; cfg['registration_shared_secret']=sys.argv[2]; cfg['report_stats']=False
# LatticeVale-managed rooms are pinned to Matrix room version 10 for the tested
# Element/Hermes compatibility policy. Room creation also passes room_version=10
# explicitly, so this setting protects other local rooms created by this Synapse.
cfg['default_room_version']='10'
cfg['public_baseurl']=f'http://localhost:{int(sys.argv[3])}/'
p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY
  chmod 0600 data/synapse/homeserver.yaml
  # Marker means LatticeVale generated this registration secret solely for bootstrap.
  # A pre-existing administrator-managed registration secret has no marker and is preserved.
  : > .matrix-registration-secret-installer-managed
  chmod 0600 .matrix-registration-secret-installer-managed
fi
return 0
}

qmd_tail_logs() {
  echo '--- QMD container diagnostics (last 120 lines) ---' >&2
  docker inspect -f 'state={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} exit={{.State.ExitCode}} restarts={{.RestartCount}}' hermes-qmd 2>/dev/null >&2 || true
  docker logs --tail 120 hermes-qmd 2>&1 >&2 || true
  echo '--- end QMD diagnostics ---' >&2
}

qmd_quarantine_index() {
  # QMD's SQLite index is derived from the vault. Preserve it before rebuilding;
  # model downloads under data/qmd/cache/models are intentionally left in place.
  local stamp backup moved=false f
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup="backups/qmd-index-$stamp"
  mkdir -p "$backup"; chmod 0700 "$backup"
  for f in data/qmd/cache/index.sqlite data/qmd/cache/index.sqlite-wal data/qmd/cache/index.sqlite-shm; do
    if [[ -e "$f" ]]; then mv "$f" "$backup/"; moved=true; fi
  done
  if [[ "$moved" == true ]]; then
    echo "Preserved the prior QMD SQLite index under $backup and will rebuild it from the vault." >&2
  else
    rmdir "$backup" 2>/dev/null || true
  fi
}

start_qmd_resilient() {
  local logs
  echo 'Starting QMD independently so health failures can be diagnosed and repaired.'
  timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build --no-deps qmd
  if wait_qmd_health 45; then return 0; fi

  logs="$(docker logs --tail 160 hermes-qmd 2>&1 || true)"
  qmd_tail_logs

  # Permission repair is safe because these two directories are installer-owned and
  # are expected to be writable by the selected Linux user / matching container UID.
  if grep -Eqi 'permission denied|EACCES' <<<"$logs"; then
    echo 'QMD reported a write-permission error; repairing only installer-owned QMD config/cache permissions.' >&2
    chmod -R u+rwX data/qmd/config data/qmd/cache
  fi

  # Current upstream QMD has had fresh-store/schema regressions in MCP startup. The
  # SQLite index is reconstructible; never delete it, quarantine it and retry once.
  if grep -Eqi 'SQLite|no such column|no such table|database.*malformed|schema' <<<"$logs"; then
    timeout --foreground --kill-after=5s 60s docker compose stop qmd qmd-indexer >/dev/null 2>&1 || true
    qmd_quarantine_index
  fi

  timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build --force-recreate --no-deps qmd
  if wait_qmd_health 45; then return 0; fi
  qmd_tail_logs
  echo 'QMD still failed after the safe one-time repair. Its source vault and prior index backup were preserved.' >&2
  return 1
}

selected_infrastructure_services() {
managed_ollama_enabled && echo ollama
[[ "$(opt_bool matrix)" == true ]] && { echo synapse-db; echo synapse; }
[[ "$(opt_bool searxng)" == true ]] && { echo searxng-valkey; echo searxng; }
[[ "$(opt_bool qmd)" == true ]] && { echo qmd; echo qmd-indexer; }
[[ "$(opt_bool honcho)" == true ]] && { echo honcho-db; echo honcho-redis; echo honcho-api; echo honcho-deriver; }
# An empty selection is valid. This helper feeds process substitutions while ERR tracing
# is enabled, so never let the final false optional-service test become the function status.
return 0
}

service_ready_for_local_repair() {
local service="$1" cid state
cid="$(timeout --foreground --kill-after=2s 8s docker compose ps -q --all "$service" 2>/dev/null | head -n1 || true)"
[[ -n "$cid" ]] || return 1
state="$(timeout --foreground --kill-after=2s 8s docker inspect -f '{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || true)"
[[ "$state" == 'true|none' || "$state" == 'true|healthy' ]]
}

start_existing_infrastructure_for_repair() {
# A stopped but otherwise healthy managed stack is not a reason to refresh images.
# First try to recover selected services strictly from already-installed images/builds.
local -a services=()
local service all_ready deadline
mapfile -t services < <(selected_infrastructure_services)
if ((${#services[@]})); then
  timeout --foreground --kill-after=10s 240s docker compose up -d --pull never --no-build "${services[@]}" || return 1
fi
# Wait on cheap Docker state/health probes under one hard wall-clock deadline. Do not
# call the full endpoint/model verifier in a loop: on a broken QMD/Ollama/HTTP service
# that can multiply nested probe timeouts into many minutes before targeted repair.
deadline=$(( $(date +%s) + 120 ))
while (( $(date +%s) < deadline )); do
  all_ready=true
  for service in "${services[@]}"; do
    service_ready_for_local_repair "$service" || { all_ready=false; break; }
  done
  if [[ "$all_ready" == true ]]; then
    # One authoritative full verification is enough. If model/endpoint state is still
    # wrong, return immediately so the targeted repair path can act on it.
    if verify_infrastructure; then
      # DirectML lives on the WSL host, not in Compose. A repair that recovered all
      # containers from local images must still recover/verify that host gateway.
      if directml_text_enabled; then
        timeout --foreground --kill-after=10s 120s ./directml-gateway.sh start >/dev/null || return 1
        timeout --foreground --kill-after=3s 15s ./directml-gateway.sh health >/dev/null || return 1
      fi
      return 0
    fi
    return 1
  fi
  sleep 2
done
return 1
}

reconcile_model_aware_ollama_resources() {
  managed_ollama_enabled || return 0
  [[ "$(opt_bool containerResourceLimits)" == true ]] || return 0
  local accel before after
  accel="$(resolve_ollama_acceleration)" || return 1
  before="$(sha256sum .latticevale-resource-state 2>/dev/null | awk '{print $1}' || true)"
  write_latticevale_compose_overlay "$accel" true || return 1
  after="$(sha256sum .latticevale-resource-state 2>/dev/null | awk '{print $1}' || true)"
  if [[ "$before" != "$after" ]]; then
    echo 'Managed Ollama model artifacts are now measurable; reconciling the model-aware policy v11 ceiling before model inference/embedding verification.'
    timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build ollama || return 1
    wait_managed_ollama_healthy 60 || return 1
    state_mark reconcile pending 'model-aware Ollama resource fingerprint changed after model download; complete stack requires Compose reconciliation'
  fi
  return 0
}

stage_infrastructure() {
# Validate the Compose model before starting, downloading, or building anything.
docker compose config --quiet

# Resume/change/reconfigure is recovery, not an implicit update command. A deliberately
# stopped stack should come back using its existing local images without broad pulls/builds.
if repair_maintenance_enabled && ! repair_package_refresh_pending && [[ "${RUN_STAGE_MIGRATION_REQUIRED:-false}" != true ]]; then
  echo 'Repair infrastructure: trying existing local images/builds before any network refresh.'
  if start_existing_infrastructure_for_repair; then
    echo 'Repair infrastructure recovered from existing local images; no broad image pull/build was needed.'
    return 0
  fi
  echo 'Existing local infrastructure did not become healthy; continuing with bounded pull/build repair for the selected components.'
fi

# INSTALL ORDER: supporting infrastructure comes first. This makes selected services real and
# reachable before Hermes asks for provider/model configuration. Matrix in particular must have
# a running homeserver, bot account, and room before Hermes is configured to use it.
echo 'Preparing selected Docker infrastructure before Hermes setup.'
echo 'Docker image pulls/builds use a 60-minute safety timeout per operation so a broken network/daemon cannot hang repair forever.'
local -a infrastructure_services=()
mapfile -t infrastructure_services < <(selected_infrastructure_services)
if ((${#infrastructure_services[@]})); then
  timeout --foreground --kill-after=15s 3600s docker compose pull --ignore-buildable "${infrastructure_services[@]}"
fi
[[ "$(opt_bool qmd)" == true ]] && timeout --foreground --kill-after=15s 3600s docker compose build --pull qmd
[[ "$(opt_bool honcho)" == true ]] && timeout --foreground --kill-after=15s 3600s docker compose build --pull honcho-api

# The selected Ollama backend is made reachable before Honcho/Hermes whenever either uses it.
if local_ai_enabled; then
  echo 'Quiescing existing Hermes/Honcho model consumers before Ollama model validation.'
  timeout --foreground --kill-after=10s 90s docker compose stop hermes honcho-api honcho-deriver >/dev/null 2>&1 || true
  if managed_ollama_enabled; then
    echo 'Starting LatticeVale-managed Ollama inside WSL/Docker (cloud features disabled).'
    timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build ollama
    for _ in $(seq 1 60); do
      timeout --foreground --kill-after=5s 15s docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null | grep -qx healthy && break
      sleep 2
    done
    timeout --foreground --kill-after=5s 15s docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null | grep -qx healthy
  else
    native_base="$(native_ollama_ready_base_url)" || { echo 'Could not establish the verified native Windows Ollama relay/API before model validation.' >&2; return 1; }
    echo "Using native Windows Ollama through $native_base. Selected models do not need to be pre-downloaded on Windows: LatticeVale detects them through /api/tags and pulls missing selections through /api/pull. It will not modify native Ollama runtime/network settings during model validation."
  fi
  ensure_ollama_model "$(opt_text localTextModel)"
  if managed_ollama_enabled; then
    current_managed_accel="$(sed -n 's/^LATTICEVALE_OLLAMA_ACCELERATION=//p' .env | head -n1)"
    [[ -n "$current_managed_accel" ]] || current_managed_accel="$(resolve_ollama_acceleration)" || return 1
    verify_or_rebudget_managed_ollama_acceleration "$current_managed_accel" "$(opt_text localTextModel)" || return 1
  fi
  if [[ "$(opt_bool honcho)" == true ]]; then
    ensure_ollama_model "$(opt_text localEmbeddingModel)"
  fi
  reconcile_model_aware_ollama_resources || return 1
  if [[ "$(opt_bool honcho)" == true ]]; then
    if managed_ollama_enabled; then
      echo 'Restarting managed Ollama before embedding verification to release any resident text model and reclaim memory.'
      timeout --foreground --kill-after=10s 90s docker compose restart ollama
      for _ in $(seq 1 45); do
        timeout --foreground --kill-after=5s 15s docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null | grep -qx healthy && break
        sleep 2
      done
      timeout --foreground --kill-after=5s 15s docker inspect -f '{{.State.Health.Status}}' hermes-ollama 2>/dev/null | grep -qx healthy
    fi
    verify_honcho_embedding_model "$(opt_text localEmbeddingModel)"
  fi
  if directml_text_enabled; then
    echo 'Preparing the isolated PyTorch DirectML text gateway. Ollama remains ready as its automatic fallback.'
    timeout --foreground --kill-after=20s 3900s ./directml-gateway.sh install || return 1
    timeout --foreground --kill-after=10s 120s ./directml-gateway.sh restart || return 1
    # A successful gateway self-test may report either directml or ollama-fallback.
    # Fallback is deliberately install-safe: the stack remains functional and later
    # Resume / repair retries the isolated DirectML dependency/model path.
    if ! timeout --foreground --kill-after=20s 3600s ./directml-gateway.sh self-test; then
      echo 'DirectML gateway self-test failed and no Ollama fallback response was available.' >&2
      return 1
    fi
  fi
fi

infra_services=()
[[ "$(opt_bool matrix)" == true ]] && infra_services+=(synapse-db synapse)
[[ "$(opt_bool searxng)" == true ]] && infra_services+=(searxng-valkey searxng)
[[ "$(opt_bool honcho)" == true ]] && infra_services+=(honcho-db honcho-redis honcho-api honcho-deriver)
if ((${#infra_services[@]})); then
  timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build "${infra_services[@]}"
fi

[[ "$(opt_bool searxng)" == true ]] && wait_http SearXNG http://127.0.0.1:${SEARXNG_HOST_PORT}/ 60
if [[ "$(opt_bool qmd)" == true ]]; then
  start_qmd_resilient
  timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build qmd-indexer
fi
[[ "$(opt_bool honcho)" == true ]] && wait_http Honcho http://127.0.0.1:${HONCHO_HOST_PORT}/health 90
return 0
}

stage_matrix_bootstrap() {
local hermes_image
# Matrix bootstrap intentionally happens BEFORE Hermes provider/model setup. The bot credentials
# are saved locally and are applied again after Hermes setup in case the upstream wizard edits .env.
if [[ "$(opt_bool matrix)" == true ]] && { [[ "$(opt_bool rebuildMatrixIdentity)" == true ]] || ! verify_matrix; }; then
  ensure_matrix_online 90
  echo
  matrix_bootstrap=secrets/matrix-bootstrap.env

  # v14.3.8 room-policy migration: a v14.3.7-managed identity can be completely
  # healthy while its installer-created room is v11. Matrix cannot downgrade a room
  # in place. Preserve the existing room and identity, create a replacement v10 room,
  # and switch only installer-owned routing to it. Do not recreate users or rotate tokens.
  if [[ "$(opt_bool rebuildMatrixIdentity)" != true && -s secrets/matrix-bot.env && -s .matrix-info && ! -s "$matrix_bootstrap" ]]; then
    existing_token="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_ACCESS_TOKEN)"
    existing_user="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_USER_ID)"
    existing_device="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_DEVICE_ID)"
    existing_room="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_ALLOWED_ROOMS)"
    existing_admin="$(read_env_file_value_optional .matrix-info MATRIX_ADMIN)"
    existing_live_user="$(curl -fsS --connect-timeout 3 --max-time 5 -H "Authorization: Bearer $existing_token" \
      "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/account/whoami" 2>/dev/null | jq -r '.user_id // empty' || true)"
    existing_room_version=''
    existing_algorithm=''
    if [[ -n "$existing_token" && "$existing_live_user" == "$existing_user" && "$existing_room" == !*:* ]]; then
      existing_room_version="$(matrix_room_version "$existing_token" "$existing_room" || true)"
      existing_encoded_room="$(matrix_room_uri "$existing_room")"
      existing_algorithm="$(curl -fsS --connect-timeout 3 --max-time 5 -H "Authorization: Bearer $existing_token" \
        "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$existing_encoded_room/state/m.room.encryption/" 2>/dev/null | jq -r '.algorithm // empty' || true)"
    fi
    if [[ -n "$existing_room_version" && "$existing_room_version" != "$LATTICEVALE_MATRIX_ROOM_VERSION" && "$existing_algorithm" == 'm.megolm.v1.aes-sha2' && -n "$existing_admin" && -n "$existing_device" ]]; then
      echo "LatticeVale-managed Matrix room '$existing_room' uses room version $existing_room_version; this release pins managed rooms to version $LATTICEVALE_MATRIX_ROOM_VERSION."
      echo 'Matrix rooms cannot be downgraded in place. LatticeVale will preserve the old room and create a replacement v10 room using the existing bot identity.'
      [[ -t 0 ]] || { echo "One-time Matrix admin authentication is required to create the replacement v10 room. Rerun interactively; no Matrix state was changed." >&2; return 1; }
      read -r -s -p "Matrix admin password for @$existing_admin:hermes.local: " existing_admin_password
      echo
      [[ -n "$existing_admin_password" ]] || { echo 'No Matrix admin password supplied; existing Matrix state was left unchanged.' >&2; return 1; }
      existing_admin_login="$(matrix_login_json "$existing_admin" "$existing_admin_password" 'LATTICEVALE_ADMIN' 'LatticeVale Admin')" || { echo "Could not authenticate existing Matrix admin '@$existing_admin:hermes.local'; existing Matrix state was left unchanged." >&2; unset existing_admin_password; return 1; }
      existing_admin_token="$(jq -er .access_token <<<"$existing_admin_login")"
      matrix_require_room_v10 "$existing_admin_token" || { unset existing_admin_password existing_admin_token; return 1; }

      migration_dir="backups/matrix-room-v10-$(date -u +%Y%m%dT%H%M%SZ)"
      mkdir -p "$migration_dir"; chmod 0700 "$migration_dir"
      cp -a .matrix-info secrets/matrix-bot.env "$migration_dir/"

      python3 - <<'PY_MATRIX_FORCE_V10'
from pathlib import Path
import yaml
p=Path('data/synapse/homeserver.yaml')
cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
cfg['default_room_version']='10'
p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY_MATRIX_FORCE_V10
      chmod 0600 data/synapse/homeserver.yaml

      replacement_payload="$(jq -cn --arg bot "$existing_user" --arg rv "$LATTICEVALE_MATRIX_ROOM_VERSION" '{
        preset:"private_chat",is_direct:true,name:"LatticeVale",topic:"Private LatticeVale-managed Hermes Agent room",
        room_version:$rv,invite:[$bot],initial_state:[{type:"m.room.encryption",state_key:"",content:{algorithm:"m.megolm.v1.aes-sha2"}}]
      }')"
      replacement_room="$(curl -fsS --connect-timeout 5 --max-time 30 -X POST "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/createRoom" \
        -H "Authorization: Bearer $existing_admin_token" -H 'Content-Type: application/json' --data "$replacement_payload" | jq -er .room_id)"
      replacement_encoded="$(matrix_room_uri "$replacement_room")"
      replacement_algorithm="$(curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $existing_admin_token" \
        "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$replacement_encoded/state/m.room.encryption/" | jq -r '.algorithm // empty')"
      replacement_version="$(matrix_room_version "$existing_admin_token" "$replacement_room")"
      [[ "$replacement_algorithm" == 'm.megolm.v1.aes-sha2' && "$replacement_version" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]] || { echo 'Replacement Matrix room failed v10/encryption verification; preserved backups are under the Matrix room migration backup directory.' >&2; return 1; }

      set_env data/hermes/.env MATRIX_ALLOWED_ROOMS "$replacement_room"
      set_env secrets/matrix-bot.env MATRIX_ALLOWED_ROOMS "$replacement_room"
      set_env .matrix-info MATRIX_ROOM "$replacement_room"
      set_env .matrix-info MATRIX_ROOM_VERSION "$LATTICEVALE_MATRIX_ROOM_VERSION"
      set_env .matrix-info MATRIX_PREVIOUS_ROOM "$existing_room"
      chmod 0600 data/hermes/.env secrets/matrix-bot.env .matrix-info
      curl -fsS --connect-timeout 3 --max-time 10 -X POST "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/logout" \
        -H "Authorization: Bearer $existing_admin_token" -H 'Content-Type: application/json' --data '{}' >/dev/null 2>&1 || true
      unset existing_admin_password existing_admin_token existing_admin_login
      timeout --foreground --kill-after=10s 180s docker compose restart synapse >/dev/null
      wait_matrix_client_api 60
      touch .matrix-configured
      chmod 0600 .matrix-configured
      echo "Created replacement encrypted Matrix room '$replacement_room' at room version $LATTICEVALE_MATRIX_ROOM_VERSION; preserved prior room '$existing_room' unchanged."
      return 0
    fi
  fi

  echo 'Matrix account setup: create one admin account and one Hermes bot account on this private homeserver.'
  matrix_registration_secret_managed=false
  if [[ -f .matrix-registration-secret-installer-managed ]]; then
    matrix_registration_secret_managed=true
  fi
  if ! grep -Eq '^[[:space:]]*registration_shared_secret:' data/synapse/homeserver.yaml 2>/dev/null; then
    # v13.16+ normally removes the shared secret after bootstrap. Advanced identity
    # rebuilds still need it, so restore one only for this installer-owned operation.
    registration_secret="$(random_hex 32)"
    python3 - "$registration_secret" <<'PY_MATRIX_TEMP_REG'
from pathlib import Path
import sys,yaml
p=Path('data/synapse/homeserver.yaml')
cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
cfg['enable_registration']=False
cfg['registration_shared_secret']=sys.argv[1]
p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY_MATRIX_TEMP_REG
    chmod 0600 data/synapse/homeserver.yaml
    matrix_registration_secret_managed=true
    : > .matrix-registration-secret-installer-managed
    chmod 0600 .matrix-registration-secret-installer-managed
    timeout --foreground --kill-after=10s 180s docker compose restart synapse >/dev/null
    wait_matrix_client_api 60
  fi
  matrix_bot='hermes'
  matrix_admin_default=''
  matrix_admin_locked=false
  matrix_bot_device_id='LATTICEVALE_BOT'
  rebuild_marker='.matrix-identity-rebuild-pending'
  if [[ "$(opt_bool rebuildMatrixIdentity)" == true && ! -s "$matrix_bootstrap" ]]; then
    echo 'Advanced recovery: preparing a transactional rebuild of the installer-owned Matrix bot/room identity while preserving Synapse data.'
    recovery_dir="backups/matrix-identity-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$recovery_dir"; chmod 0700 "$recovery_dir"
    for f in secrets/matrix-bot.env .matrix-info .matrix-configured; do [[ -e "$f" ]] && cp -a "$f" "$recovery_dir/"; done
    if [[ -d data/hermes/platforms/matrix/store ]]; then
      cp -a data/hermes/platforms/matrix/store "$recovery_dir/matrix-store"
    fi
    printf '%s\n' "$recovery_dir" > "$rebuild_marker"; chmod 0600 "$rebuild_marker"
    recovery_suffix="$(openssl rand -hex 3)"
    matrix_bot="hermes_recovery_$recovery_suffix"
    matrix_bot_device_id="LATTICEVALE_RECOVERY_${recovery_suffix^^}"
    matrix_admin_default="$(read_env_file_value_optional .matrix-info MATRIX_ADMIN)"
    [[ -n "$matrix_admin_default" ]] || { echo 'Advanced Matrix bot/room rebuild requires the existing installer-recorded human Matrix admin identity; .matrix-info does not contain MATRIX_ADMIN, so refusing a broader identity replacement.' >&2; return 1; }
    matrix_admin_locked=true
    echo "Advanced recovery will preserve human Matrix admin '@$matrix_admin_default:hermes.local' and every secondary profile identity/room. Only the installer-owned default bot/device/room will be replaced."
    echo 'The current Matrix credentials and crypto store remain active until replacement bootstrap credentials are safely persisted.'
  fi
  if [[ -s secrets/matrix-bot.env && ! -s "$matrix_bootstrap" ]]; then
    echo 'Existing Matrix bot credentials are present but failed live verification. Automatic identity replacement is unsafe.' >&2
    echo 'Use Advanced recovery to preserve data and explicitly rebuild the installer-owned Matrix bot identity.' >&2
    return 1
  fi
  if [[ -s "$matrix_bootstrap" ]]; then
    echo 'Resuming a previously interrupted Matrix account setup.'
    matrix_admin="$(sed -n 's/^MATRIX_ADMIN=//p' "$matrix_bootstrap" | head -n1)"
    matrix_password="$(sed -n 's/^MATRIX_ADMIN_PASSWORD=//p' "$matrix_bootstrap" | head -n1)"
    bot_password="$(sed -n 's/^MATRIX_BOT_PASSWORD=//p' "$matrix_bootstrap" | head -n1)"
    matrix_bot="$(sed -n 's/^MATRIX_BOT_USERNAME=//p' "$matrix_bootstrap" | head -n1)"
    matrix_bot_device_id="$(sed -n 's/^MATRIX_BOT_DEVICE_ID=//p' "$matrix_bootstrap" | head -n1)"
    matrix_bot="${matrix_bot:-hermes}"
    matrix_bot_device_id="${matrix_bot_device_id:-LATTICEVALE_BOT}"
  else
    default_admin="${matrix_admin_default:-${USER//[^a-zA-Z0-9._=-]/}}"; default_admin="${default_admin:-owner}"
    if [[ "$matrix_admin_locked" == true ]]; then
      matrix_admin="$default_admin"
      echo "Advanced Matrix recovery is reusing existing human admin '@$matrix_admin:hermes.local'; its username will not be changed."
    else
      while true; do
        read -r -p "Matrix admin username [$default_admin]: " matrix_admin
        matrix_admin="${matrix_admin:-$default_admin}"
        matrix_admin="${matrix_admin#"${matrix_admin%%[![:space:]]*}"}"
        matrix_admin="${matrix_admin%"${matrix_admin##*[![:space:]]}"}"
        if [[ "$matrix_admin" =~ ^[A-Za-z0-9._=-]{1,64}$ ]]; then
          if [[ "$matrix_admin" == "$matrix_bot" ]]; then
            echo "Matrix admin username '$matrix_admin' conflicts with the default Hermes bot identity; choose a different admin username." >&2
            continue
          fi
          if jq -e --arg u "$matrix_admin" '.workers[]? | select(.matrix.enabled == true and (.matrix.localpart // .name) == $u)' install-options.json >/dev/null 2>&1; then
            echo "Matrix admin username '$matrix_admin' conflicts with a Matrix-enabled Hermes profile localpart; choose a different admin username." >&2
            continue
          fi
          break
        fi
        echo 'Use 1-64 letters, numbers, ., _, =, or - for the Matrix username.' >&2
      done
    fi
    matrix_password="$(read_password_twice 'Matrix admin password')"
    bot_password="$(random_hex 24)"
    cat > "$matrix_bootstrap" <<EOF_MATRIX_BOOTSTRAP
MATRIX_ADMIN=$matrix_admin
MATRIX_ADMIN_PASSWORD=$matrix_password
MATRIX_BOT_PASSWORD=$bot_password
MATRIX_BOT_USERNAME=$matrix_bot
MATRIX_BOT_DEVICE_ID=$matrix_bot_device_id
EOF_MATRIX_BOOTSTRAP
    chmod 0600 "$matrix_bootstrap"
  fi

  # Once replacement bootstrap credentials are durable, retire only the old
  # installer-owned runtime identity. The preserved backup remains available, while
  # Hermes receives a fresh crypto store for the new Matrix account/device as required
  # by its E2EE model. If interrupted after this point, matrix-bootstrap.env + the
  # pending marker make Resume deterministic instead of falling back to @hermes.
  if [[ -s "$rebuild_marker" ]]; then
    recovery_dir="$(head -n1 "$rebuild_marker" 2>/dev/null || true)"
    [[ -n "$recovery_dir" && -d "$recovery_dir" ]] || { echo 'Matrix identity rebuild marker exists but its recovery backup directory is missing; refusing to replace the active identity.' >&2; return 1; }
    rm -f secrets/matrix-bot.env .matrix-info .matrix-configured
    remove_env_keys data/hermes/.env MATRIX_HOMESERVER MATRIX_ACCESS_TOKEN MATRIX_USER_ID MATRIX_PASSWORD MATRIX_ALLOWED_USERS MATRIX_ALLOWED_ROOMS MATRIX_E2EE_MODE MATRIX_DEVICE_ID MATRIX_RECOVERY_KEY MATRIX_RECOVERY_KEY_OUTPUT_FILE MATRIX_REACTIONS MATRIX_APPROVAL_REQUIRE_SENDER
    rm -rf data/hermes/platforms/matrix/store
    mkdir -p data/hermes/platforms/matrix/store
    chmod 0700 data/hermes/platforms/matrix/store
  fi

  timeout --foreground --kill-after=5s 60s docker exec hermes-synapse register_new_matrix_user -c /data/homeserver.yaml -u "$matrix_admin" -p "$matrix_password" -a http://127.0.0.1:8008 >/dev/null 2>&1 || echo 'Matrix admin may already exist; verifying the saved credentials.'
  timeout --foreground --kill-after=5s 60s docker exec hermes-synapse register_new_matrix_user -c /data/homeserver.yaml -u "$matrix_bot" -p "$bot_password" --no-admin http://127.0.0.1:8008 >/dev/null 2>&1 || echo 'Matrix bot may already exist; verifying the saved credentials.'
  # Hermes image/E2EE dependency validation runs after the image is pulled and the
  # core container is started in stage_profiles. Room creation can safely happen first.
  bot_device_id="$matrix_bot_device_id"
  [[ -n "$bot_device_id" ]] || bot_device_id="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_DEVICE_ID)"
  [[ -n "$bot_device_id" ]] || bot_device_id='LATTICEVALE_BOT'
  admin_login="$(matrix_login_json "$matrix_admin" "$matrix_password")"
  bot_login="$(matrix_login_json "$matrix_bot" "$bot_password" "$bot_device_id")"
  admin_token="$(jq -er .access_token <<<"$admin_login")"
  bot_token="$(jq -er .access_token <<<"$bot_login")"
  returned_bot_device_id="$(jq -er .device_id <<<"$bot_login")"
  [[ "$returned_bot_device_id" == "$bot_device_id" ]] || { echo "Matrix login returned unexpected bot device ID '$returned_bot_device_id' (expected '$bot_device_id')." >&2; return 1; }
  admin_id="@$matrix_admin:hermes.local"
  bot_id="@$matrix_bot:hermes.local"
  # v14 never persists the human Matrix admin password as a long-lived secret.
  # If secondary Matrix profiles are requested, retain it only in a one-time 0600
  # handoff file so the later profile stage can finish this same install/resume run.
  # The profile stage deletes the file on exit; older repairs simply prompt once.
  if jq -e '.workers[]? | select(.matrix.enabled == true)' install-options.json >/dev/null 2>&1; then
    cat > secrets/matrix-admin-once.env <<EOF_MATRIX_ADMIN_ONCE
MATRIX_ADMIN=$matrix_admin
MATRIX_ADMIN_PASSWORD=$matrix_password
EOF_MATRIX_ADMIN_ONCE
    chmod 0600 secrets/matrix-admin-once.env
  fi

  # LatticeVale intentionally pins installer-managed rooms to Matrix room version 10.
  # Do not follow Synapse's moving default: Element/Hermes compatibility for this
  # release is validated against v10, and createRoom will receive the version explicitly.
  matrix_require_room_v10 "$admin_token"
  room_version="$LATTICEVALE_MATRIX_ROOM_VERSION"

  python3 - "$room_version" <<'PY_MATRIX_ROOM_VERSION'
from pathlib import Path
import sys,yaml
p=Path('data/synapse/homeserver.yaml')
cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
cfg['default_room_version']=str(sys.argv[1])
p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY_MATRIX_ROOM_VERSION
  chmod 0600 data/synapse/homeserver.yaml

  room_payload="$(jq -cn --arg bot "$bot_id" --arg rv "$room_version" '{
    preset:"private_chat",
    is_direct:true,
    name:"LatticeVale",
    topic:"Private LatticeVale-managed Hermes Agent room",
    room_version:$rv,
    invite:[$bot],
    initial_state:[{type:"m.room.encryption",state_key:"",content:{algorithm:"m.megolm.v1.aes-sha2"}}]
  }')"
  room_id="$(curl -fsS --connect-timeout 5 --max-time 30 -X POST http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/createRoom \
    -H "Authorization: Bearer $admin_token" -H 'Content-Type: application/json' \
    --data "$room_payload" | jq -er .room_id)"
  encoded_room="$(jq -rn --arg v "$room_id" '$v|@uri')"

  # Do not pre-join the bot with raw Client-Server calls. Hermes starts later with
  # E2EE already initialized and auto-joins its pending encrypted-room invite. This
  # avoids the upstream fresh-crypto-store/already-joined-room failure mode.
  encryption_algorithm="$(curl -fsS --connect-timeout 5 --max-time 30 \
    -H "Authorization: Bearer $admin_token" \
    "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$encoded_room/state/m.room.encryption/" | jq -er .algorithm)"
  [[ "$encryption_algorithm" == 'm.megolm.v1.aes-sha2' ]] || { echo 'Matrix room encryption state did not verify after room creation.' >&2; return 1; }
  created_room_version="$(matrix_room_version "$admin_token" "$room_id")"
  [[ "$created_room_version" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]] || { echo "Matrix room was created at unexpected room version '$created_room_version' (expected $LATTICEVALE_MATRIX_ROOM_VERSION)." >&2; return 1; }

  set_env data/hermes/.env MATRIX_HOMESERVER http://synapse:8008
  set_env data/hermes/.env MATRIX_ACCESS_TOKEN "$bot_token"
  set_env data/hermes/.env MATRIX_USER_ID "$bot_id"
  set_env data/hermes/.env MATRIX_ALLOWED_USERS "$admin_id"
  set_env data/hermes/.env MATRIX_ALLOWED_ROOMS "$room_id"
  set_env data/hermes/.env MATRIX_E2EE_MODE required
  set_env data/hermes/.env MATRIX_DEVICE_ID "$bot_device_id"
  set_env data/hermes/.env MATRIX_RECOVERY_KEY_OUTPUT_FILE /opt/data/matrix-recovery-key.once
  rm -f data/hermes/matrix-recovery-key.once
  cat > secrets/matrix-bot.env <<EOF_MATRIX_SECRET
MATRIX_HOMESERVER=http://synapse:8008
MATRIX_ACCESS_TOKEN=$bot_token
MATRIX_USER_ID=$bot_id
MATRIX_BOT_PASSWORD=$bot_password
MATRIX_ALLOWED_USERS=$admin_id
MATRIX_ALLOWED_ROOMS=$room_id
MATRIX_E2EE_MODE=required
MATRIX_DEVICE_ID=$bot_device_id
MATRIX_RECOVERY_KEY_OUTPUT_FILE=/opt/data/matrix-recovery-key.once
EOF_MATRIX_SECRET
  chmod 0600 secrets/matrix-bot.env
  cat > .matrix-info <<EOF_MATRIX
MATRIX_ADMIN=$matrix_admin
MATRIX_BOT=$matrix_bot
MATRIX_USER_ID=$bot_id
MATRIX_HOMESERVER=http://synapse:8008
MATRIX_LOCAL=http://localhost:${MATRIX_HOST_PORT}
MATRIX_ROOM=$room_id
MATRIX_ROOM_VERSION=$room_version
MATRIX_E2EE_MODE=required
MATRIX_DEVICE_ID=$bot_device_id
MATRIX_CROSS_SIGNING=installer-managed
EOF_MATRIX
  chmod 0600 .matrix-info
  curl -fsS --connect-timeout 5 --max-time 30 -X POST http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/logout -H "Authorization: Bearer $admin_token" -H 'Content-Type: application/json' --data '{}' >/dev/null || true
  # Registration is no longer needed after installer bootstrap. Remove only a secret
  # proven to be LatticeVale-owned; preserve a pre-existing administrator-managed secret.
  if [[ "$matrix_registration_secret_managed" == true ]]; then
    python3 - <<'PY_MATRIX_LOCK'
from pathlib import Path
import yaml
p=Path('data/synapse/homeserver.yaml')
cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
cfg.pop('registration_shared_secret', None)
p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY_MATRIX_LOCK
    rm -f .matrix-registration-secret-installer-managed
  fi
  timeout --foreground --kill-after=10s 180s docker compose restart synapse >/dev/null
  wait_matrix_client_api 60
  unset matrix_password bot_password admin_token bot_token
  touch .matrix-configured
  rm -f "$matrix_bootstrap" "$rebuild_marker"
fi
return 0
}

stage_provider_setup() {
# Stages must be independently resumable. Never rely on a shell variable that was
# populated only when an earlier stage executed; that earlier stage may live-verify
# and be skipped during repair. Reload the persisted image selected by prepare_config.
local hermes_image
hermes_image="$(sed -n 's/^HERMES_IMAGE=//p' .env | head -n1)"
[[ -n "$hermes_image" ]] || { echo 'HERMES_IMAGE is missing from .env; rerun Resume / repair so prepare_config can reconstruct installer-owned configuration.' >&2; return 1; }
[[ "$hermes_image" =~ ^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}$ ]] || { echo 'HERMES_IMAGE in .env contains unsupported characters; refusing to pass an unsafe persisted image reference to Docker.' >&2; return 1; }

# Pull the selected Hermes image only when it is not already available during repair.
# Provider/profile reconfiguration must not silently refresh an otherwise healthy pinned
# image. A periodic managed repair refresh or explicit Windows Update / repair is the bounded bundle-aligned exception for installer-owned package/image drift; `./manage.sh update` remains a separate broad upstream-refresh path.
if repair_maintenance_enabled && ! repair_package_refresh_pending && docker image inspect "$hermes_image" >/dev/null 2>&1; then
  echo "Repair provider setup: reusing existing Hermes image $hermes_image (no implicit pull)."
else
  echo "Pulling Hermes image: $hermes_image"
  timeout --foreground --kill-after=15s 3600s docker pull "$hermes_image"
fi

if [[ "$(opt_bool hermesLocalAI)" == true ]]; then
  # Hermes consumes either backend through the same OpenAI-compatible custom-provider
  # contract. DirectML is a host gateway; Ollama remains its transparent fallback.
  local_model="$(local_text_model_name)"
  local_context="$(local_text_context_length)"
  python3 - data/hermes/config.yaml "$local_model" "$local_context" "$(local_text_openai_base_url)" <<'PY_LOCAL_HERMES'
from pathlib import Path
import sys,yaml
p=Path(sys.argv[1]); model=sys.argv[2]; context=int(sys.argv[3]); base_url=sys.argv[4]
try: cfg=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}
except Exception: cfg={}
cfg=cfg or {}
m=cfg.setdefault('model',{})
m['default']=model
m['provider']='custom'
m['base_url']=base_url
m['context_length']=context
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY_LOCAL_HERMES
  echo "Hermes default provider configured for LatticeVale local text backend $(local_text_backend), model '$local_model' (${local_context}-token context)."
else
  if [[ "$(opt_bool forceProviderSetup)" == true ]] || ! hermes_model_configured data/hermes/config.yaml; then
    echo
    echo 'DEFAULT Hermes profile provider/model selection follows.'
    echo 'Only the upstream `hermes model` wizard is opened here. Matrix, browser, search, memory, Dashboard, and other installer-selected integrations are configured separately by LatticeVale.'
    echo 'Choose the AI provider/model and enter or authenticate required credentials. OpenCode Go is supported by current Hermes as provider `opencode-go`.'
    echo 'Secrets remain in data/hermes/.env.'
    docker run --rm -it -e HERMES_UID="$(id -u)" -e HERMES_GID="$(id -g)" \
      -v "$PWD/data/hermes:/opt/data" -v "$PWD/workspace:/workspace" -v "$PWD/vault:/vault" "$hermes_image" model
    hermes_model_configured data/hermes/config.yaml || { echo 'Hermes model selection exited without a configured default model. Rerun the installer and complete the DEFAULT profile provider/model selection.' >&2; exit 4; }
  fi
fi
return 0
}

stage_profiles() {
# Start core Hermes first so profile management uses the official in-container s6 supervisor.
timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build hermes
for _ in $(seq 1 60); do timeout --foreground --kill-after=5s 15s docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1 && break; sleep 2; done
timeout --foreground --kill-after=5s 15s docker exec -u hermes hermes-agent hermes --version >/dev/null

if [[ "$(opt_bool matrix)" == true ]]; then
  # Current Hermes Docker releases bake the Matrix/E2EE dependencies into the image.
  # Verify the actual running image before relying on an encrypted room; fail clearly
  # rather than completing with a gateway that cannot decrypt Matrix traffic.
  if ! timeout --foreground --kill-after=5s 30s docker exec -u hermes hermes-agent python -c 'import mautrix, olm' >/dev/null 2>&1; then
    echo 'The running Hermes image does not provide the Matrix E2EE dependencies (mautrix + olm) required by this LatticeVale configuration.' >&2
    return 1
  fi
fi

# Track every profile this installer has ever managed. Reruns update integrations on old profiles too,
# but never delete them merely because multi-agent was later turned off.
touch .installer-managed-profiles
chmod 0600 .installer-managed-profiles
while IFS= read -r current_name; do
  [[ -n "$current_name" ]] || continue
  grep -Fxq "$current_name" .installer-managed-profiles || printf '%s\n' "$current_name" >> .installer-managed-profiles
done < <(jq -r '.workers[]?.name' install-options.json)
sort -u -o .installer-managed-profiles .installer-managed-profiles

# Create requested profiles. If a previous run was interrupted after directory creation but before
# provider setup completed, actual config state (not a marker file) decides whether setup resumes.
# IMPORTANT: do not feed this loop with `done < <(jq ...)`. The profile setup command below is
# interactive (`docker exec -it`) and must inherit the PTY supplied by bootstrap.sh. Redirecting
# the loop's stdin to jq replaces that PTY with a pipe and Docker correctly rejects `-t`.
mapfile -t requested_workers < <(jq -c '.workers[]?' install-options.json)
for worker in "${requested_workers[@]}"; do
  [[ -n "$worker" ]] || continue
  name="$(jq -r '.name' <<<"$worker")"
  desc="$(jq -r '.description' <<<"$worker")"
  clone="$(jq -r '.clone' <<<"$worker")"
  created=false
  if [[ ! -d "data/hermes/profiles/$name" ]]; then
    # Current Hermes Docker releases register/start a supervised gateway when a profile
    # is created. Never use upstream --clone here: it can expose copied messaging
    # credentials to that gateway before a post-create sanitizer gets a chance to run.
    # Create credential-empty, stop immediately, then perform a LatticeVale-controlled clone.
    docker exec -u hermes hermes-agent hermes profile create "$name" --description "$desc"
    # Profile creation may auto-start its s6 slot in current upstream images. Stop it
    # before writing provider credentials, and fail closed if it remains resident.
    quiesce_profile_gateway_for_credential_write "$name"
    if [[ "$clone" == true ]]; then
      python3 - "data/hermes" "data/hermes/profiles/$name" <<'PY_PROFILE_SAFE_CLONE'
from pathlib import Path
import shutil,sys,yaml
src=Path(sys.argv[1]); dst=Path(sys.argv[2]); dst.mkdir(parents=True,exist_ok=True)

# Match the useful provider/config portion of upstream --clone without ever copying
# a live messaging/gateway credential into the newly-created profile.
prefixes=('TELEGRAM_','DISCORD_','SLACK_','MATRIX_','WHATSAPP_','SIGNAL_','EMAIL_','HOMEASSISTANT_','MATTERMOST_','DINGTALK_','FEISHU_','LARK_','WECOM_','WEIXIN_','BLUEBUBBLES_','QQ_','YUANBAO_','MSTEAMS_','LINE_','NTFY_','WEBHOOK_','API_SERVER_')
source_env=src/'.env'; dest_env=dst/'.env'
if source_env.exists():
    kept=[line for line in source_env.read_text(encoding='utf-8').splitlines()
          if not line.startswith(prefixes) and not line.startswith('GATEWAY_MULTIPLEX_PROFILES=')]
    dest_env.write_text('\n'.join(kept)+('\n' if kept else ''),encoding='utf-8')
    dest_env.chmod(0o600)

source_cfg=src/'config.yaml'; dest_cfg=dst/'config.yaml'
if source_cfg.exists():
    cfg=yaml.safe_load(source_cfg.read_text(encoding='utf-8')) or {}
else:
    cfg={}
cfg.pop('platforms',None)
cfg.pop('multiplex_profiles',None)
gateway=cfg.get('gateway')
if not isinstance(gateway,dict): gateway={}
gateway['multiplex_profiles']=False
cfg['gateway']=gateway
dest_cfg.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')

soul=src/'SOUL.md'
if soul.exists(): shutil.copy2(soul,dst/'SOUL.md')
skills=src/'skills'
if skills.is_dir(): shutil.copytree(skills,dst/'skills',dirs_exist_ok=True)
PY_PROFILE_SAFE_CLONE
    fi
    created=true
  else
    # Keep the requested role description current without recreating/destructively replacing the profile.
    docker exec -u hermes hermes-agent hermes profile describe "$name" --text "$desc" >/dev/null 2>&1 || true
  fi
  if [[ "$(opt_bool forceProfileSetup)" == true ]] || ! hermes_model_configured "data/hermes/profiles/$name/config.yaml"; then
    echo
    if [[ "$clone" == true && "$created" == false ]]; then
      echo "Profile '$name' exists but has no configured default model; resuming provider/model setup instead of assuming the earlier clone completed."
    else
      echo "SECONDARY Hermes profile '$name' provider/model selection follows."
      echo "This `hermes -p $name model` wizard changes only profile '$name'; it does not modify the default profile or configure Matrix/browser integrations."
    fi
    docker exec -it -u hermes hermes-agent hermes -p "$name" model
    hermes_model_configured "data/hermes/profiles/$name/config.yaml" || { echo "Secondary profile '$name' model selection exited without a configured default model." >&2; exit 4; }
  fi

  # Profiles are independent Hermes homes; the selected local text backend is therefore
  # a model setting, not a single shared process env override. For installer-cloned
  # profiles still using LatticeVale's selected local model, repair only the endpoint.
  # A profile deliberately switched to another provider/model is left untouched.
  if [[ "$(opt_bool hermesLocalAI)" == true && "$clone" == true ]]; then
    python3 - "data/hermes/profiles/$name/config.yaml" "$(local_text_model_name)" "$(local_text_openai_base_url)" <<'PY_REPAIR_CLONED_LOCAL_OLLAMA'
from pathlib import Path
import sys,yaml
p=Path(sys.argv[1]); cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}; m=cfg.get('model') or {}
if m.get('provider')=='custom' and m.get('default')==sys.argv[2] and m.get('base_url')!=sys.argv[3]:
    m['base_url']=sys.argv[3]
    cfg['model']=m
    p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY_REPAIR_CLONED_LOCAL_OLLAMA
  fi
done
return 0
}

stage_matrix_profiles() (
  set -Eeuo pipefail
  [[ "$(opt_bool matrix)" != true ]] && return 0
  mapfile -t matrix_workers < <(jq -c '.workers[]? | select(.matrix.enabled == true)' install-options.json)
  ((${#matrix_workers[@]})) || return 0

  ensure_matrix_online 90
  [[ -s .matrix-info && -s secrets/matrix-bot.env ]] || { echo 'Default Matrix bootstrap must be healthy before profile-specific Matrix provisioning.' >&2; return 1; }
  mkdir -p secrets/matrix-profiles .matrix-profiles
  chmod 0700 secrets/matrix-profiles .matrix-profiles
  cat > MATRIX-SECONDARY-PROFILES.txt <<'EOF_MATRIX_HANDOFF_HEADER'
LatticeVale secondary Matrix profiles

This file contains no passwords, access tokens, or recovery keys.
LatticeVale provisions the Matrix account, encrypted room, invite, and protected credentials.
Selected secondary Hermes Matrix profiles are activated automatically during installation or Resume / repair.
A pending-manual marker means activation is incomplete and will be retried without replacing the existing identity, token, room, or E2EE state.
EOF_MATRIX_HANDOFF_HEADER
  chmod 0644 MATRIX-SECONDARY-PROFILES.txt

  admin_localpart="$(sed -n 's/^MATRIX_ADMIN=//p' .matrix-info | head -n1)"
  [[ -n "$admin_localpart" ]] || { echo 'Default Matrix admin identity is missing from .matrix-info.' >&2; return 1; }
  admin_user="@$admin_localpart:hermes.local"

  # Existing installer-managed profile identities can be verified/reapplied without
  # authenticating the human admin. Admin credentials are needed only when at least
  # one newly-enabled profile identity/room must actually be created or adopted.
  needs_matrix_admin=false
  for worker in "${matrix_workers[@]}"; do
    name="$(jq -r '.name' <<<"$worker")"
    secret="secrets/matrix-profiles/$name.env"
    if [[ ! -s "$secret" ]]; then
      needs_matrix_admin=true
      break
    fi
    provisioning_state="$(sed -n 's/^LATTICEVALE_PROVISIONING_STATE=//p' "$secret" | head -n1)"
    [[ -n "$provisioning_state" ]] || provisioning_state="$(sed -n 's/^FOUNDRY_PROVISIONING_STATE=//p' "$secret" | head -n1)"
    if [[ -z "$provisioning_state" ]]; then
      # v13.17 staging/early-v14 compatibility: a legacy LatticeVale record with a
      # verified identity, token, and room is complete even before the explicit
      # transaction marker existed. Any other installer-held partial record needs
      # admin access so it can be resumed rather than silently treated as healthy.
      legacy_token="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' "$secret" | head -n1)"
      legacy_user="$(sed -n 's/^MATRIX_USER_ID=//p' "$secret" | head -n1)"
      legacy_room="$(sed -n 's/^MATRIX_ALLOWED_ROOMS=//p' "$secret" | head -n1)"
      if [[ -n "$legacy_token" && -n "$legacy_user" && "$legacy_room" == !*:* ]]; then
        provisioning_state=complete
      else
        provisioning_state=pending
      fi
    fi
    if [[ "$provisioning_state" != complete && "$provisioning_state" != pending-manual ]]; then
      needs_matrix_admin=true
      break
    fi
    # Installer-created profile rooms are part of the v10 policy. If a previous
    # release created one at another version, repair needs one-time admin access to
    # create a v10 replacement while preserving the existing bot identity.
    room_mode_scan="$(jq -r '.matrix.roomMode // "create"' <<<"$worker")"
    if [[ "$room_mode_scan" == create ]]; then
      scan_recorded_version="$(read_env_file_value_optional "$secret" MATRIX_ROOM_VERSION)"
      # v14.3.7 and older did not persist a profile room-version marker. Require
      # one-time admin verification on repair rather than assuming the room version.
      if [[ "$scan_recorded_version" != "$LATTICEVALE_MATRIX_ROOM_VERSION" ]]; then
        needs_matrix_admin=true
        break
      fi
    fi
  done

  admin_password=''
  admin_token=''
  cleanup_matrix_profile_stage() {
    if [[ -n "${admin_token:-}" ]]; then
      curl -fsS --connect-timeout 3 --max-time 10 -X POST "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/logout" \
        -H "Authorization: Bearer $admin_token" -H 'Content-Type: application/json' --data '{}' >/dev/null 2>&1 || true
    fi
    rm -f secrets/matrix-admin-once.env
    unset admin_password admin_token admin_login
  }
  trap cleanup_matrix_profile_stage EXIT

  if [[ "$needs_matrix_admin" == true ]]; then
    if [[ -s secrets/matrix-admin-once.env ]]; then
      saved_admin="$(sed -n 's/^MATRIX_ADMIN=//p' secrets/matrix-admin-once.env | head -n1)"
      if [[ "$saved_admin" == "$admin_localpart" ]]; then
        admin_password="$(sed -n 's/^MATRIX_ADMIN_PASSWORD=//p' secrets/matrix-admin-once.env | head -n1)"
      fi
    fi
    if [[ -z "$admin_password" ]]; then
      if [[ ! -t 0 ]]; then
        echo "Creating or resuming a Matrix-enabled profile needs one-time authentication for existing admin '$admin_user'. Rerun interactively; existing Matrix identities were left unchanged." >&2
        return 1
      fi
      echo
      echo "One-time authentication: enter the existing Matrix admin password for $admin_user."
      echo 'LatticeVale does not retain this password after the profile provisioning stage exits.'
      read -r -s -p 'Matrix admin password: ' admin_password
      echo
      [[ -n "$admin_password" ]] || { echo 'No Matrix admin password supplied; leaving existing Matrix state unchanged.' >&2; return 1; }
    fi
    # A human may spend time entering the one-time admin password. Re-assert Matrix
    # readiness immediately before using it so provisioning never assumes the service
    # stayed online while the questionnaire was waiting for input.
    ensure_matrix_online 60
    admin_login="$(matrix_login_json "$admin_localpart" "$admin_password" 'LATTICEVALE_ADMIN' 'LatticeVale Admin')" || {
      echo "Could not authenticate Matrix admin '$admin_user'. No profile bot account or room was modified." >&2
      return 1
    }
    admin_token="$(jq -er .access_token <<<"$admin_login")"
    matrix_require_room_v10 "$admin_token"
  fi

  for worker in "${matrix_workers[@]}"; do
    name="$(jq -r '.name' <<<"$worker")"
    localpart="$(jq -r '.matrix.localpart // .name' <<<"$worker")"
    room_mode="$(jq -r '.matrix.roomMode // "create"' <<<"$worker")"
    room_name="$(jq -r '.matrix.roomName // ("LatticeVale " + .name)' <<<"$worker")"
    requested_room="$(jq -r '.matrix.roomId // empty' <<<"$worker")"
    pdir="data/hermes/profiles/$name"
    penv="$pdir/.env"
    secret="secrets/matrix-profiles/$name.env"
    info=".matrix-profiles/$name.info"
    expected_user="@$localpart:hermes.local"
    [[ "$localpart" == "$name" ]] || { echo "Profile '$name' Matrix localpart must match its profile name." >&2; return 1; }
    [[ -d "$pdir" ]] || { echo "Profile '$name' does not exist; Matrix provisioning will not create an identity detached from a Hermes profile." >&2; return 1; }
    hermes_model_configured "$pdir/config.yaml" || { echo "Profile '$name' has no configured model; complete its model selection before Matrix is started." >&2; return 1; }
    touch "$penv"; chmod 0600 "$penv"

    provisioning_state=''
    if [[ -s "$secret" ]]; then
      provisioning_state="$(sed -n 's/^LATTICEVALE_PROVISIONING_STATE=//p' "$secret" | head -n1)"
    [[ -n "$provisioning_state" ]] || provisioning_state="$(sed -n 's/^FOUNDRY_PROVISIONING_STATE=//p' "$secret" | head -n1)"
      if [[ -z "$provisioning_state" ]]; then
        legacy_token="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' "$secret" | head -n1)"
        legacy_user="$(sed -n 's/^MATRIX_USER_ID=//p' "$secret" | head -n1)"
        legacy_room="$(sed -n 's/^MATRIX_ALLOWED_ROOMS=//p' "$secret" | head -n1)"
        if [[ -n "$legacy_token" && "$legacy_user" == "$expected_user" && "$legacy_room" == !*:* ]]; then
          provisioning_state=complete
          set_env "$secret" LATTICEVALE_PROVISIONING_STATE complete
          chmod 0600 "$secret"
        elif [[ "$legacy_user" == "$expected_user" && -n "$(sed -n 's/^MATRIX_BOT_PASSWORD=//p' "$secret" | head -n1)" ]]; then
          provisioning_state=pending
          set_env "$secret" LATTICEVALE_PROVISIONING_STATE pending
          chmod 0600 "$secret"
        else
          echo "Installer-held Matrix state for profile '$name' is incomplete and cannot be safely classified; refusing automatic identity replacement." >&2
          return 1
        fi
      fi
    fi

    if [[ ( "$provisioning_state" == complete || "$provisioning_state" == pending-manual ) && "$room_mode" == create ]]; then
      recorded_room="$(read_env_file_value_optional "$secret" MATRIX_ALLOWED_ROOMS)"
      recorded_version="$(read_env_file_value_optional "$secret" MATRIX_ROOM_VERSION)"
      if [[ "$recorded_version" != "$LATTICEVALE_MATRIX_ROOM_VERSION" ]]; then
        [[ -n "$admin_token" ]] || { echo "Profile '$name' needs one-time Matrix admin verification of its LatticeVale-managed room version." >&2; return 1; }
        [[ "$recorded_room" == !*:* ]] || { echo "Profile '$name' has no valid managed Matrix room to verify." >&2; return 1; }
        recorded_version="$(matrix_room_version "$admin_token" "$recorded_room" || true)"
        [[ -n "$recorded_version" ]] || { echo "Could not determine Matrix room version for profile '$name' room '$recorded_room'." >&2; return 1; }
        if [[ "$recorded_version" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]]; then
          set_env "$secret" MATRIX_ROOM_VERSION "$LATTICEVALE_MATRIX_ROOM_VERSION"
        else
          profile_migration_dir="backups/matrix-profile-room-v10-${name}-$(date -u +%Y%m%dT%H%M%SZ)"
          mkdir -p "$profile_migration_dir"; chmod 0700 "$profile_migration_dir"
          cp -a "$secret" "$profile_migration_dir/"
          set_env "$secret" MATRIX_PREVIOUS_ROOM "$recorded_room"
          remove_env_keys "$secret" MATRIX_ALLOWED_ROOMS MATRIX_HOME_ROOM MATRIX_ROOM_VERSION
          set_env "$secret" LATTICEVALE_PROVISIONING_STATE pending
          provisioning_state=pending
          echo "Profile '$name' managed Matrix room '$recorded_room' uses room version $recorded_version; preserving it and creating a replacement v$LATTICEVALE_MATRIX_ROOM_VERSION room."
        fi
      fi
    fi

    if [[ "$provisioning_state" == complete || "$provisioning_state" == pending-manual ]]; then
      token="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' "$secret" | head -n1)"
      user_id="$(sed -n 's/^MATRIX_USER_ID=//p' "$secret" | head -n1)"
      room_id="$(sed -n 's/^MATRIX_ALLOWED_ROOMS=//p' "$secret" | head -n1)"
      [[ "$user_id" == "$expected_user" && -n "$token" && "$room_id" == !*:* ]] || { echo "Installer-held Matrix state for profile '$name' is incomplete; refusing automatic identity replacement." >&2; return 1; }
      live_user="$(curl -fsS --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/account/whoami" | jq -r '.user_id // empty')" || true
      [[ "$live_user" == "$expected_user" ]] || { echo "Matrix token for profile '$name' failed identity verification; refusing to rotate it automatically." >&2; return 1; }
      if [[ "$room_mode" == existing && -n "$requested_room" && "$requested_room" != "$room_id" ]]; then
        echo "Profile '$name' already has an installer-managed Matrix room '$room_id'; refusing to silently move it to '$requested_room'." >&2
        return 1
      fi
      echo "Matrix profile '$name' already has a verified independent identity; preserving it."
    elif [[ -z "$provisioning_state" || "$provisioning_state" == pending ]]; then
      [[ -n "$admin_token" ]] || { echo "Matrix admin authentication is unavailable for new or interrupted profile '$name'." >&2; return 1; }

      if [[ -z "$provisioning_state" ]]; then
        # Never overwrite a manually configured Matrix profile that LatticeVale does not own.
        if grep -q '^MATRIX_' "$penv" 2>/dev/null; then
          echo "Profile '$name' already contains Matrix settings but no LatticeVale ownership record. Preserving them and refusing to overwrite an unknown identity." >&2
          return 1
        fi

        # Validate an adopted room before creating a bot identity. This keeps a bad
        # room ID from creating an otherwise-unused Matrix account.
        if [[ "$room_mode" == existing ]]; then
          room_id="$requested_room"
          [[ "$room_id" == !*:* ]] || { echo "Profile '$name' existing Matrix room ID is invalid." >&2; return 1; }
          encoded_room="$(matrix_room_uri "$room_id")"
          algorithm="$(curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $admin_token" \
            "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$encoded_room/state/m.room.encryption/" | jq -r '.algorithm // empty')" || true
          [[ "$algorithm" == 'm.megolm.v1.aes-sha2' ]] || { echo "Existing Matrix room '$room_id' is unavailable to $admin_user or is not encrypted; no profile identity was created." >&2; return 1; }
        else
          room_id=''
        fi

        bot_password="$(random_hex 24)"
        device_id="LATTICEVALE_${name^^}"
        device_id="${device_id//-/_}"
        encoded_user="$(matrix_user_uri "$expected_user")"
        user_status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 -H "Authorization: Bearer $admin_token" \
          "http://127.0.0.1:${MATRIX_HOST_PORT}/_synapse/admin/v2/users/$encoded_user" || true)"
        if [[ "$user_status" == 200 ]]; then
          echo "Matrix account '$expected_user' already exists but is not recorded as LatticeVale-managed for profile '$name'. Refusing to reset its password or take ownership." >&2
          return 1
        elif [[ "$user_status" != 404 ]]; then
          echo "Could not safely determine whether Matrix account '$expected_user' exists (HTTP $user_status)." >&2
          return 1
        fi

        # Write installer ownership BEFORE the irreversible account creation. If
        # Synapse succeeds and the next room/invite step is interrupted, repair can
        # resume this exact identity instead of seeing an unexplained existing user.
        : > "$secret"
        chmod 0600 "$secret"
        set_env "$secret" LATTICEVALE_PROVISIONING_STATE pending
        set_env "$secret" HERMES_PROFILE "$name"
        set_env "$secret" MATRIX_HOMESERVER http://synapse:8008
        set_env "$secret" MATRIX_USER_ID "$expected_user"
        set_env "$secret" MATRIX_BOT_PASSWORD "$bot_password"
        set_env "$secret" MATRIX_DEVICE_ID "$device_id"
        set_env "$secret" MATRIX_ROOM_MODE "$room_mode"
        [[ -n "$room_id" ]] && { set_env "$secret" MATRIX_ALLOWED_ROOMS "$room_id"; set_env "$secret" MATRIX_HOME_ROOM "$room_id"; }

        create_user_payload="$(jq -cn --arg p "$bot_password" --arg n "LatticeVale $name" '{password:$p,admin:false,deactivated:false,user_type:"bot",displayname:$n}')"
        curl -fsS --connect-timeout 5 --max-time 30 -X PUT \
          "http://127.0.0.1:${MATRIX_HOST_PORT}/_synapse/admin/v2/users/$encoded_user" \
          -H "Authorization: Bearer $admin_token" -H 'Content-Type: application/json' --data "$create_user_payload" >/dev/null
        provisioning_state=pending
      else
        # Resume only an identity LatticeVale explicitly recorded as pending. The
        # profile name/user/room-mode must still match the current install intent.
        pending_profile="$(sed -n 's/^HERMES_PROFILE=//p' "$secret" | head -n1)"
        pending_user="$(sed -n 's/^MATRIX_USER_ID=//p' "$secret" | head -n1)"
        pending_mode="$(sed -n 's/^MATRIX_ROOM_MODE=//p' "$secret" | head -n1)"
        [[ "$pending_profile" == "$name" && "$pending_user" == "$expected_user" ]] || { echo "Pending Matrix ownership record for '$name' does not match the requested profile identity." >&2; return 1; }
        [[ -z "$pending_mode" || "$pending_mode" == "$room_mode" ]] || { echo "Pending Matrix room mode for '$name' differs from the current installer selection; refusing to redirect it automatically." >&2; return 1; }
        bot_password="$(sed -n 's/^MATRIX_BOT_PASSWORD=//p' "$secret" | head -n1)"
        device_id="$(sed -n 's/^MATRIX_DEVICE_ID=//p' "$secret" | head -n1)"
        room_id="$(sed -n 's/^MATRIX_ALLOWED_ROOMS=//p' "$secret" | head -n1)"
        [[ -n "$bot_password" && -n "$device_id" ]] || { echo "Pending Matrix state for '$name' lacks the installer-generated password/device needed for safe resume." >&2; return 1; }
        if [[ "$room_mode" == existing && -n "$requested_room" && -n "$room_id" && "$requested_room" != "$room_id" ]]; then
          echo "Pending Matrix room for '$name' is '$room_id'; refusing to redirect it to '$requested_room'." >&2
          return 1
        fi
        encoded_user="$(matrix_user_uri "$expected_user")"
        user_status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 -H "Authorization: Bearer $admin_token" \
          "http://127.0.0.1:${MATRIX_HOST_PORT}/_synapse/admin/v2/users/$encoded_user" || true)"
        if [[ "$user_status" == 404 ]]; then
          create_user_payload="$(jq -cn --arg p "$bot_password" --arg n "LatticeVale $name" '{password:$p,admin:false,deactivated:false,user_type:"bot",displayname:$n}')"
          curl -fsS --connect-timeout 5 --max-time 30 -X PUT \
            "http://127.0.0.1:${MATRIX_HOST_PORT}/_synapse/admin/v2/users/$encoded_user" \
            -H "Authorization: Bearer $admin_token" -H 'Content-Type: application/json' --data "$create_user_payload" >/dev/null
        elif [[ "$user_status" != 200 ]]; then
          echo "Could not safely resume Matrix account '$expected_user' (HTTP $user_status)." >&2
          return 1
        fi
        echo "Resuming interrupted Matrix provisioning for Hermes profile '$name'."
      fi

      bot_login="$(matrix_login_json "$localpart" "$bot_password" "$device_id" "LatticeVale $name")" || { echo "Could not log in installer-managed Matrix profile '$name' while provisioning/resuming." >&2; return 1; }
      token="$(jq -er .access_token <<<"$bot_login")"
      returned_user="$(jq -er .user_id <<<"$bot_login")"
      returned_device="$(jq -er .device_id <<<"$bot_login")"
      [[ "$returned_user" == "$expected_user" && "$returned_device" == "$device_id" ]] || { echo "Matrix login identity mismatch while provisioning profile '$name'." >&2; return 1; }
      set_env "$secret" MATRIX_ACCESS_TOKEN "$token"

      # A prior interrupted release may already have created the pending profile room
      # at Synapse's then-default version. For installer-created rooms, preserve that
      # room and replace only the pending routing target with an explicit v10 room.
      if [[ "$room_mode" == create && -n "$room_id" ]]; then
        pending_room_version="$(matrix_room_version "$admin_token" "$room_id" || true)"
        if [[ -n "$pending_room_version" && "$pending_room_version" != "$LATTICEVALE_MATRIX_ROOM_VERSION" ]]; then
          set_env "$secret" MATRIX_PREVIOUS_ROOM "$room_id"
          remove_env_keys "$secret" MATRIX_ALLOWED_ROOMS MATRIX_HOME_ROOM MATRIX_ROOM_VERSION
          echo "Pending profile '$name' room '$room_id' uses room version $pending_room_version; preserving it and creating a replacement v$LATTICEVALE_MATRIX_ROOM_VERSION room."
          room_id=''
        fi
      fi

      if [[ -z "$room_id" ]]; then
        if [[ "$room_mode" == existing ]]; then
          room_id="$requested_room"
          [[ "$room_id" == !*:* ]] || { echo "Profile '$name' existing Matrix room ID is invalid." >&2; return 1; }
          encoded_room="$(matrix_room_uri "$room_id")"
          algorithm="$(curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $admin_token" \
            "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$encoded_room/state/m.room.encryption/" | jq -r '.algorithm // empty')" || true
          [[ "$algorithm" == 'm.megolm.v1.aes-sha2' ]] || { echo "Existing Matrix room '$room_id' is unavailable to $admin_user or is not encrypted; pending profile identity was preserved for repair." >&2; return 1; }
        else
          room_payload="$(jq -cn --arg bot "$expected_user" --arg n "$room_name" --arg t "Private LatticeVale-managed Hermes profile room for $name" --arg rv "$LATTICEVALE_MATRIX_ROOM_VERSION" '{preset:"private_chat",is_direct:true,name:$n,topic:$t,room_version:$rv,invite:[$bot],initial_state:[{type:"m.room.encryption",state_key:"",content:{algorithm:"m.megolm.v1.aes-sha2"}}]}')"
          room_id="$(curl -fsS --connect-timeout 5 --max-time 30 -X POST "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/createRoom" \
            -H "Authorization: Bearer $admin_token" -H 'Content-Type: application/json' --data "$room_payload" | jq -er .room_id)"
          created_room_version="$(matrix_room_version "$admin_token" "$room_id")"
          [[ "$created_room_version" == "$LATTICEVALE_MATRIX_ROOM_VERSION" ]] || { echo "Profile '$name' room was created at unexpected Matrix room version '$created_room_version'." >&2; return 1; }
        fi
        # Persist the room immediately: any interruption after create/adopt can now
        # resume the same room instead of creating a duplicate.
        set_env "$secret" MATRIX_ALLOWED_ROOMS "$room_id"
        set_env "$secret" MATRIX_HOME_ROOM "$room_id"
        if [[ "$room_mode" == create ]]; then set_env "$secret" MATRIX_ROOM_VERSION "$LATTICEVALE_MATRIX_ROOM_VERSION"; fi
      fi

      encoded_room="$(matrix_room_uri "$room_id")"
      algorithm="$(curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $admin_token" \
        "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$encoded_room/state/m.room.encryption/" | jq -r '.algorithm // empty')" || true
      [[ "$algorithm" == 'm.megolm.v1.aes-sha2' ]] || { echo "Matrix room '$room_id' for profile '$name' failed encryption verification; pending state was preserved for repair." >&2; return 1; }

      invite_payload="$(jq -cn --arg u "$expected_user" '{user_id:$u}')"
      curl -fsS --connect-timeout 5 --max-time 20 -X POST \
        "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$encoded_room/invite" \
        -H "Authorization: Bearer $admin_token" -H 'Content-Type: application/json' --data "$invite_payload" >/dev/null 2>&1 || true
      membership="$(curl -fsS --connect-timeout 5 --max-time 10 -H "Authorization: Bearer $admin_token" \
        "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$encoded_room/state/m.room.member/$encoded_user" 2>/dev/null | jq -r '.membership // empty' || true)"
      [[ "$membership" == invite || "$membership" == join ]] || { echo "Could not verify an invite/join for '$expected_user' in room '$room_id'; pending state was preserved for repair." >&2; return 1; }

      set_env "$penv" MATRIX_HOMESERVER http://synapse:8008
      set_env "$penv" MATRIX_ACCESS_TOKEN "$token"
      set_env "$penv" MATRIX_USER_ID "$expected_user"
      remove_env_keys "$penv" MATRIX_PASSWORD
      set_env "$penv" MATRIX_ALLOWED_USERS "$admin_user"
      set_env "$penv" MATRIX_ALLOWED_ROOMS "$room_id"
      set_env "$penv" MATRIX_HOME_ROOM "$room_id"
      set_env "$penv" MATRIX_E2EE_MODE required
      set_env "$penv" MATRIX_DEVICE_ID "$device_id"
      set_env "$penv" MATRIX_SESSION_SCOPE room
      set_env "$penv" MATRIX_AUTO_THREAD false
      set_env "$penv" MATRIX_APPROVAL_REQUIRE_SENDER true
      set_env "$penv" MATRIX_RECOVERY_KEY_OUTPUT_FILE "/opt/data/profiles/$name/matrix-recovery-key.once"
      rm -f "$pdir/matrix-recovery-key.once"
      chmod 0600 "$penv"

      set_env "$secret" HERMES_PROFILE "$name"
      set_env "$secret" MATRIX_HOMESERVER http://synapse:8008
      set_env "$secret" MATRIX_ACCESS_TOKEN "$token"
      set_env "$secret" MATRIX_USER_ID "$expected_user"
      set_env "$secret" MATRIX_BOT_PASSWORD "$bot_password"
      set_env "$secret" MATRIX_ALLOWED_USERS "$admin_user"
      set_env "$secret" MATRIX_ALLOWED_ROOMS "$room_id"
      set_env "$secret" MATRIX_HOME_ROOM "$room_id"
      set_env "$secret" MATRIX_E2EE_MODE required
      set_env "$secret" MATRIX_DEVICE_ID "$device_id"
      set_env "$secret" MATRIX_ROOM_MODE "$room_mode"
      set_env "$secret" MATRIX_RECOVERY_KEY_OUTPUT_FILE "/opt/data/profiles/$name/matrix-recovery-key.once"
      # Resource provisioning is complete, but Hermes-side activation is intentionally
      # left to an explicit post-install command. This keeps a secondary-profile Matrix
      # join/E2EE edge from making the whole LatticeVale install fail.
      set_env "$secret" LATTICEVALE_PROVISIONING_STATE pending-manual
      provisioning_state=pending-manual
      chmod 0600 "$secret"
      echo "Provisioned independent Matrix identity '$expected_user' and encrypted room for Hermes profile '$name'."
    else
      echo "Unknown Matrix provisioning state '$provisioning_state' for profile '$name'; refusing automatic changes." >&2
      return 1
    fi

    # Re-apply installer-owned profile Matrix values from the protected secret store on
    # every repair in case an upstream setup wizard rewrote the profile .env.
    token="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' "$secret" | head -n1)"
    user_id="$(sed -n 's/^MATRIX_USER_ID=//p' "$secret" | head -n1)"
    room_id="$(sed -n 's/^MATRIX_ALLOWED_ROOMS=//p' "$secret" | head -n1)"
    device_id="$(sed -n 's/^MATRIX_DEVICE_ID=//p' "$secret" | head -n1)"
    recovery="$(sed -n 's/^MATRIX_RECOVERY_KEY=//p' "$secret" | head -n1)"
    set_env "$penv" MATRIX_HOMESERVER http://synapse:8008
    set_env "$penv" MATRIX_ACCESS_TOKEN "$token"
    set_env "$penv" MATRIX_USER_ID "$user_id"
    remove_env_keys "$penv" MATRIX_PASSWORD
    set_env "$penv" MATRIX_ALLOWED_USERS "$admin_user"
    set_env "$penv" MATRIX_ALLOWED_ROOMS "$room_id"
    set_env "$penv" MATRIX_HOME_ROOM "$room_id"
    set_env "$penv" MATRIX_E2EE_MODE required
    set_env "$penv" MATRIX_DEVICE_ID "$device_id"
    set_env "$penv" MATRIX_SESSION_SCOPE room
    set_env "$penv" MATRIX_AUTO_THREAD false
    set_env "$penv" MATRIX_APPROVAL_REQUIRE_SENDER true
    if [[ -n "$recovery" ]]; then
      set_env "$penv" MATRIX_RECOVERY_KEY "$recovery"
      remove_env_keys "$penv" MATRIX_RECOVERY_KEY_OUTPUT_FILE
    else
      set_env "$penv" MATRIX_RECOVERY_KEY_OUTPUT_FILE "/opt/data/profiles/$name/matrix-recovery-key.once"
    fi
    chmod 0600 "$penv"

    # v14.3.8 could mark the resource transaction complete before the profile actually
    # joined its room. Reclassify that exact state as pending-manual without changing
    # the bot account, token, device ID, room, or E2EE files.
    if [[ "$provisioning_state" == complete ]]; then
      joined_now="$(curl -fsS --max-time 5 -H "Authorization: Bearer $token" "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/joined_rooms" 2>/dev/null | jq -r --arg r "$room_id" '.joined_rooms | index($r) != null' || true)"
      if [[ "$joined_now" != true ]]; then
        set_env "$secret" LATTICEVALE_PROVISIONING_STATE pending-manual
        provisioning_state=pending-manual
        echo "Profile '$name' has valid Matrix resources but has not joined room '$room_id'; converting the old completed marker to pending-manual without replacing any Matrix state."
      fi
    fi

    model="$(python3 - "$pdir/config.yaml" <<'PY_PROFILE_MODEL'
from pathlib import Path
import sys,yaml
cfg=yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8')) or {}
print(((cfg.get('model') or {}).get('default') or '').strip())
PY_PROFILE_MODEL
)"
    [[ -n "$model" ]] || { echo "Profile '$name' model disappeared during Matrix provisioning." >&2; return 1; }
    cat > "$info" <<EOF_MATRIX_PROFILE_INFO
HERMES_PROFILE=$name
HERMES_MODEL=$model
MATRIX_USER_ID=$user_id
MATRIX_ROOM=$room_id
MATRIX_ROOM_MODE=$room_mode
MATRIX_ROOM_VERSION=$(if [[ "$room_mode" == create ]]; then printf '%s' "$LATTICEVALE_MATRIX_ROOM_VERSION"; else read_env_file_value_optional "$secret" MATRIX_ROOM_VERSION; fi)
MATRIX_E2EE_MODE=required
MATRIX_DEVICE_ID=$device_id
MATRIX_SETUP_STATUS=$provisioning_state
EOF_MATRIX_PROFILE_INFO
    chmod 0600 "$info"

    if [[ "$provisioning_state" == pending-manual ]]; then
      # Resource provisioning is resumable, but a selected Matrix-enabled profile is not
      # installation-complete until its exact Hermes gateway has accepted the invite and
      # persisted E2EE recovery state. Reuse the bounded recovery command automatically.
      quiesce_profile_gateway_for_credential_write "$name"
      cat >> MATRIX-SECONDARY-PROFILES.txt <<EOF_MATRIX_PROFILE_HANDOFF

Profile: $name
Status: pending-manual
Matrix user: $user_id
Room ID: $room_id
Room version: $(if [[ "$room_mode" == create ]]; then printf '%s' "$LATTICEVALE_MATRIX_ROOM_VERSION"; else read_env_file_value_optional "$secret" MATRIX_ROOM_VERSION; fi)
Encryption: required
EOF_MATRIX_PROFILE_HANDOFF
      echo "Activating Matrix communication for Hermes profile '$name' in its installer-managed room."
      if ./manage.sh matrix-profile-finish "$name"; then
        echo "Profile '$name' Matrix communication is active."
        continue
      fi
      echo "WARNING: Profile '$name' Matrix resources are valid and preserved, but automatic Hermes activation is still pending. Continuing LatticeVale without failing the core stack; Resume / repair and normal stack start will retry the same protected identity and room." >&2
      continue
    fi

    # Completed Matrix profiles must also have their exact profile gateway running; a
    # joined room with a stopped gateway is not a working communication path.
    ensure_matrix_online 30
    if ! start_or_restart_profile_gateway_exact "$name"; then
      echo "WARNING: Profile '$name' Matrix gateway could not be started; preserving its completed Matrix identity and continuing the core stack." >&2
      continue
    fi
    if ! wait_profile_gateway_up_exact "$name"; then
      echo "WARNING: Profile '$name' Matrix gateway did not become running; preserving its completed Matrix identity and continuing the core stack." >&2
      continue
    fi
    cat >> MATRIX-SECONDARY-PROFILES.txt <<EOF_MATRIX_PROFILE_HANDOFF

Profile: $name
Status: complete
Matrix user: $user_id
Room ID: $room_id
Room version: $(if [[ "$room_mode" == create ]]; then printf '%s' "$LATTICEVALE_MATRIX_ROOM_VERSION"; else read_env_file_value_optional "$secret" MATRIX_ROOM_VERSION; fi)
Encryption: required
EOF_MATRIX_PROFILE_HANDOFF
  done
  return 0
)

stage_matrix_profile_cross_signing() {
  [[ "$(opt_bool matrix)" != true ]] && return 0
  mapfile -t matrix_workers < <(jq -c '.workers[]? | select(.matrix.enabled == true)' install-options.json)
  ((${#matrix_workers[@]})) || return 0
  local worker name pdir penv secret recovery host_once token
  for worker in "${matrix_workers[@]}"; do
    name="$(jq -r '.name' <<<"$worker")"
    pdir="data/hermes/profiles/$name"; penv="$pdir/.env"; secret="secrets/matrix-profiles/$name.env"; host_once="$pdir/matrix-recovery-key.once"
    if [[ ! -s "$secret" || ! -s "$penv" ]]; then
      echo "WARNING: Matrix profile '$name' credentials are incomplete; skipping this profile without blocking the core stack." >&2
      continue
    fi
    provisioning_state="$(read_env_file_value_optional "$secret" LATTICEVALE_PROVISIONING_STATE)"
    [[ -n "$provisioning_state" ]] || provisioning_state="$(read_env_file_value_optional "$secret" FOUNDRY_PROVISIONING_STATE)"
    if [[ "$provisioning_state" == pending-manual ]]; then
      set_env "$secret" LATTICEVALE_CROSS_SIGNING_STATE pending
      set_env ".matrix-profiles/$name.info" MATRIX_CROSS_SIGNING_STATUS pending
      echo "Profile '$name' Matrix activation is incomplete; retrying automatic completion before cross-signing."
      if ./manage.sh matrix-profile-finish "$name"; then
        provisioning_state=complete
      else
        echo "WARNING: Matrix profile '$name' is still pending; preserving it and skipping cross-signing for this profile on this run." >&2
        continue
      fi
    fi
    [[ "$provisioning_state" == complete ]] || { echo "WARNING: Matrix profile '$name' has unexpected provisioning state '$provisioning_state'; skipping this profile without blocking the stack." >&2; continue; }
    recovery="$(sed -n 's/^MATRIX_RECOVERY_KEY=//p' "$secret" | head -n1)"
    set_env "$secret" LATTICEVALE_CROSS_SIGNING_STATE pending
    set_env ".matrix-profiles/$name.info" MATRIX_CROSS_SIGNING_STATUS pending
    if [[ -z "$recovery" ]]; then
      if [[ ! -s "$host_once" ]]; then
        set_env "$penv" MATRIX_RECOVERY_KEY_OUTPUT_FILE "/opt/data/profiles/$name/matrix-recovery-key.once"
        set_env "$secret" MATRIX_RECOVERY_KEY_OUTPUT_FILE "/opt/data/profiles/$name/matrix-recovery-key.once"
        chmod 0600 "$penv" "$secret"
        ensure_matrix_online 30
        if ! start_or_restart_profile_gateway_exact "$name"; then
          echo "WARNING: Matrix profile '$name' gateway could not start for recovery-key generation; preserving its state and skipping cross-signing on this run." >&2
          continue
        fi
        echo "Waiting for profile '$name' one-time Matrix recovery key."
        matrix_offline_streak=0
        for _ in $(seq 1 60); do
          [[ -s "$host_once" ]] && break
          if matrix_client_api_ready; then
            matrix_offline_streak=0
          else
            matrix_offline_streak=$((matrix_offline_streak+1))
            if (( matrix_offline_streak >= 3 )); then
              stop_profile_gateway_after_matrix_failure "$name" || true
              echo "Matrix/Synapse went offline while waiting for profile '$name' recovery key; stopped the profile gateway and preserved resumable state." >&2
              return 1
            fi
          fi
          sleep 2
        done
      fi
      if [[ ! -s "$host_once" ]]; then
        echo "WARNING: Fresh Matrix profile '$name' did not emit its one-time recovery key. Its token, room, and crypto store were preserved; skipping this profile without destructive recovery." >&2
        continue
      fi
      recovery="$(tr -d '\r\n' < "$host_once")"
      if [[ -z "$recovery" ]]; then
        echo "WARNING: Profile '$name' emitted an empty Matrix recovery key; preserving its existing state and skipping this profile on this run." >&2
        continue
      fi
    fi
    set_env "$secret" MATRIX_RECOVERY_KEY "$recovery"
    set_env "$penv" MATRIX_RECOVERY_KEY "$recovery"
    remove_env_keys "$secret" MATRIX_RECOVERY_KEY_OUTPUT_FILE
    remove_env_keys "$penv" MATRIX_RECOVERY_KEY_OUTPUT_FILE
    rm -f "$host_once"
    set_env "$secret" LATTICEVALE_CROSS_SIGNING_STATE complete
    set_env ".matrix-profiles/$name.info" MATRIX_CROSS_SIGNING_STATUS complete
    chmod 0600 "$secret" "$penv" ".matrix-profiles/$name.info"
    if ! start_or_restart_profile_gateway_exact "$name"; then
      echo "WARNING: Matrix profile '$name' gateway reload after cross-signing failed; recovery state is safely persisted and the core stack will continue. Normal start/repair will retry gateway activation." >&2
      continue
    fi
  done
  return 0
}

stage_integrations() {
# Apply stack integrations without replacing the provider/model choices made by the user.
python3 - install-options.json data/hermes .installer-managed-profiles <<'PY'
from pathlib import Path
import json,sys,yaml
opts=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); root=Path(sys.argv[2]); managed=Path(sys.argv[3])
names=[x.strip() for x in managed.read_text(encoding='utf-8').splitlines() if x.strip()] if managed.exists() else []
names=[n for n in names if (root/'profiles'/n).is_dir()]
# Preserve valid routing to any real Hermes profile, including user-created profiles
# outside LatticeVale ownership. Only default + names are modified by this stage.
all_profiles=[]
profiles_dir=root/'profiles'
if profiles_dir.is_dir():
    all_profiles=sorted(child.name for child in profiles_dir.iterdir() if child.is_dir() and (child/'config.yaml').is_file())
known=['default']+[n for n in all_profiles if n!='default']
root_cfg_path=root/'config.yaml'
root_cfg=yaml.safe_load(root_cfg_path.read_text(encoding='utf-8')) if root_cfg_path.exists() else {}
root_cfg=root_cfg or {}
root_kb=root_cfg.get('kanban') if isinstance(root_cfg.get('kanban'),dict) else {}
canonical_orchestrator=str(root_kb.get('orchestrator_profile') or '').strip()
if canonical_orchestrator not in known: canonical_orchestrator='default'
canonical_assignee=str(root_kb.get('default_assignee') or '').strip()
if canonical_assignee not in known:
    # Generic fallback: prefer another LatticeVale-managed profile when one exists;
    # otherwise keep the orchestrator. Do not conscript an unrelated user-owned
    # profile into automatic work just because it is present on disk.
    candidates=[n for n in names if n in known and n != canonical_orchestrator]
    canonical_assignee=candidates[0] if candidates else canonical_orchestrator
canonical_review=root_kb.get('review_dispatch') if isinstance(root_kb.get('review_dispatch'),bool) else True
profiles=[('default',root_cfg_path)]+[(name,root/'profiles'/name/'config.yaml') for name in names]
for name,p in profiles:
    cfg=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}
    cfg=cfg or {}
    cfg.pop('multiplex_profiles',None)
    gateway=cfg.get('gateway')
    if not isinstance(gateway,dict): gateway={}
    gateway['multiplex_profiles']=False
    cfg['gateway']=gateway
    cfg.setdefault('terminal',{})['cwd']='/workspace'
    guard=cfg.setdefault('tool_loop_guardrails',{})
    guard['warnings_enabled']=True
    guard['hard_stop_enabled']=True
    warn=guard.get('warn_after') if isinstance(guard.get('warn_after'),dict) else {}
    warn.setdefault('exact_failure',2)
    warn.setdefault('same_tool_failure',3)
    warn.setdefault('idempotent_no_progress',2)
    guard['warn_after']=warn
    hard=guard.get('hard_stop_after') if isinstance(guard.get('hard_stop_after'),dict) else {}
    hard.setdefault('exact_failure',5)
    hard.setdefault('same_tool_failure',8)
    hard.setdefault('idempotent_no_progress',5)
    guard['hard_stop_after']=hard
    # Agent-managed skill writes are a normal Hermes capability. Make the default
    # explicit on clean installs, but preserve a user's explicit approval gate on
    # repair/reconfigure/update rather than silently weakening it.
    skills_cfg=cfg.get('skills')
    if not isinstance(skills_cfg,dict): skills_cfg={}
    skills_cfg.setdefault('write_approval',False)
    cfg['skills']=skills_cfg
    plugins=cfg.setdefault('plugins',{})
    enabled=plugins.get('enabled') or []
    disabled=plugins.get('disabled') or []
    if isinstance(enabled,str): enabled=[enabled]
    if isinstance(disabled,str): disabled=[disabled]
    dashboard_auth_ids={'basic','dashboard_auth/basic'}
    if opts.get('dashboard'):
        disabled=[x for x in disabled if x not in dashboard_auth_ids]
        enabled=[x for x in enabled if x!='basic']
        if 'dashboard_auth/basic' not in enabled: enabled.append('dashboard_auth/basic')
    else:
        enabled=[x for x in enabled if x not in dashboard_auth_ids]
    plugins['enabled']=enabled; plugins['disabled']=disabled
    tools=cfg.get('toolsets') or ['hermes-cli']
    if isinstance(tools,str): tools=[tools]
    if 'hermes-cli' not in tools: tools.insert(0,'hermes-cli')
    if 'browser' not in tools: tools.append('browser')
    browser=cfg.get('browser')
    if not isinstance(browser,dict): browser={}
    browser.setdefault('engine','auto')
    # Prefer Hermes's zero-cost local Chromium path only when the profile has no
    # explicit browser backend/provider and no evidence of an intentional cloud
    # browser selection. Repair/update must not replace a user's paid/custom choice.
    env_keys=set()
    env_path=p.parent/'.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8',errors='replace').splitlines():
            line=line.strip()
            if line and not line.startswith('#') and '=' in line:
                env_keys.add(line.split('=',1)[0].strip())
    browser_selection_env_keys={'BROWSER_USE_API_KEY','BROWSERBASE_API_KEY','BROWSERBASE_PROJECT_ID','CAMOFOX_URL','BROWSER_CDP_URL'}
    tool_gateway=cfg.get('tool_gateway') if isinstance(cfg.get('tool_gateway'),dict) else {}
    gateway_browser=str(tool_gateway.get('browser') or '').strip().lower()=='gateway'
    explicit_backend=str(browser.get('backend') or '').strip()
    if not str(browser.get('cloud_provider') or '').strip() and not explicit_backend and not gateway_browser and not (env_keys & browser_selection_env_keys):
        browser['cloud_provider']='local'
    cfg['browser']=browser
    # Hermes fresh installs default web_extract summarization to 360 seconds, while
    # older/migrated configs with this key absent can fall back to 30 seconds. Add
    # only the missing value; preserve an explicit provider/model/timeout selection.
    auxiliary=cfg.get('auxiliary')
    if not isinstance(auxiliary,dict): auxiliary={}
    web_extract_aux=auxiliary.get('web_extract')
    if not isinstance(web_extract_aux,dict): web_extract_aux={}
    web_extract_aux.setdefault('timeout',360)
    auxiliary['web_extract']=web_extract_aux
    cfg['auxiliary']=auxiliary
    if opts.get('kanban'):
        # LatticeVale intentionally exposes routing tools to managed gateway profiles
        # so substantive requests arriving through any configured profile can enter
        # triage. The runtime guard below prevents unbound chat turns from using
        # claimed-worker lifecycle operations.
        if 'kanban' not in tools: tools.append('kanban')
        if 'latticevale-kanban-policy' not in enabled: enabled.append('latticevale-kanban-policy')
        disabled=[x for x in disabled if x!='latticevale-kanban-policy']
    else:
        tools=[t for t in tools if t!='kanban']
        enabled=[x for x in enabled if x!='latticevale-kanban-policy']
        if 'latticevale-kanban-policy' not in disabled: disabled.append('latticevale-kanban-policy')
    plugins['enabled']=enabled; plugins['disabled']=disabled
    cfg['toolsets']=tools
    if opts.get('kanban'):
        kanban=cfg.get('kanban')
        if not isinstance(kanban,dict): kanban={}
        # Shared-board routing must be deterministic whichever managed gateway owns
        # the singleton dispatcher lock. Preserve valid existing root routing names,
        # repair stale/deleted names against the discovered profile roster, and then
        # replicate the canonical values to every managed profile config.
        kanban['dispatch_in_gateway']=True
        kanban['dispatch_interval_seconds']=30
        kanban['review_dispatch']=canonical_review
        kanban['auto_decompose']=True
        kanban['auto_decompose_per_tick']=1
        kanban['auto_subscribe_on_create']=True
        kanban['orchestrator_profile']=canonical_orchestrator
        kanban['default_assignee']=canonical_assignee
        kanban['max_in_progress']=int(opts.get('kanbanMaxInProgress') or 2)
        kanban['max_in_progress_per_profile']=int(opts.get('kanbanMaxInProgressPerProfile') or 1)
        cfg['kanban']=kanban
    elif isinstance(cfg.get('kanban'),dict):
        cfg['kanban']['dispatch_in_gateway']=False
    # SearXNG is Hermes' keyless search backend, but upstream Hermes explicitly
    # marks it search-only.  When LatticeVale owns the SearXNG selection and the
    # user has not chosen another extract-capable provider, pair it with the
    # lightweight LatticeVale local extractor generated below.  Preserve explicit
    # web.backend / web.extract_backend choices so repair never replaces a user's
    # Firecrawl/Tavily/Exa/Parallel/custom provider.
    web=cfg.get('web')
    if not isinstance(web,dict): web={}
    if opts.get('searxng'):
        web['search_backend']='searxng'
        shared=str(web.get('backend') or '').strip()
        extract=str(web.get('extract_backend') or '').strip()
        if shared in {'','searxng'} and extract in {'','searxng','latticevale-local'}:
            web['extract_backend']='latticevale-local'
        elif shared not in {'','searxng'} and extract=='latticevale-local':
            # An explicit shared provider supersedes LatticeVale's installer-owned
            # default extractor; remove only our selection so Hermes can use it.
            web.pop('extract_backend',None)
    else:
        if web.get('search_backend')=='searxng': web.pop('search_backend',None)
        if web.get('extract_backend')=='latticevale-local': web.pop('extract_backend',None)
    if web: cfg['web']=web
    else: cfg.pop('web',None)
    local_extract=isinstance(cfg.get('web'),dict) and cfg['web'].get('extract_backend')=='latticevale-local'
    if local_extract:
        if 'web/latticevale-web-extract' not in enabled: enabled.append('web/latticevale-web-extract')
        disabled=[x for x in disabled if x not in {'web/latticevale-web-extract','latticevale-web-extract'}]
    else:
        enabled=[x for x in enabled if x not in {'web/latticevale-web-extract','latticevale-web-extract'}]
        disabled=[x for x in disabled if x not in {'web/latticevale-web-extract','latticevale-web-extract'}]
    plugins['enabled']=enabled; plugins['disabled']=disabled
    if opts.get('qmd'):
        cfg.setdefault('mcp_servers',{})['qmd']={'url':'http://qmd:8181/mcp','timeout':30}
    elif isinstance(cfg.get('mcp_servers'),dict):
        cfg['mcp_servers'].pop('qmd',None)
        if not cfg['mcp_servers']: cfg.pop('mcp_servers',None)
    if opts.get('honcho'):
        cfg.setdefault('memory',{})['provider']='honcho'
    elif isinstance(cfg.get('memory'),dict) and cfg['memory'].get('provider')=='honcho':
        cfg['memory'].pop('provider',None)
        if not cfg['memory']: cfg.pop('memory',None)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
PY
# Keep automatic Kanban behavior in a narrowly installer-owned SOUL block so custom
# identity/personality text is preserved. Disabling Kanban removes only this block.
python3 - install-options.json data/hermes .installer-managed-profiles <<'PY_KANBAN_SOUL'
from pathlib import Path
import json,re,sys
opts=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root=Path(sys.argv[2]); managed=Path(sys.argv[3])
names=[x.strip() for x in managed.read_text(encoding='utf-8').splitlines() if x.strip()] if managed.exists() else []
paths=[root/'SOUL.md']+[root/'profiles'/n/'SOUL.md' for n in names if (root/'profiles'/n).is_dir()]
start='<!-- HERMES_AUTO_KANBAN_POLICY_START -->'
end='<!-- HERMES_AUTO_KANBAN_POLICY_END -->'
pattern=re.compile(re.escape(start)+r'.*?'+re.escape(end),re.S)
block='\n'.join([
    start,
    '',
    '## Automatic Multi-Agent Orchestration',
    '',
    '- Handle genuinely simple questions and lightweight actions directly.',
    '- For substantive research, troubleshooting, implementation, multi-step work, or work that benefits from durable handoff/parallel execution, create exactly one root Kanban card in triage (`triage=true`) unless the user explicitly asks for a different workflow.',
    '- A normal chat/gateway turn is not a claimed Kanban worker merely because Kanban tools are visible. In an unbound turn, use routing/orchestrator operations only; do not call worker lifecycle tools such as `kanban_complete`, `kanban_block`, `kanban_heartbeat`, `kanban_request_review`, or `kanban_request_changes`.',
    '- `kanban_show()` without an explicit id is worker-scoped and is valid only when Hermes actually spawned the process with `HERMES_KANBAN_TASK`. Never pass the literal strings `$HERMES_KANBAN_TASK`, `${HERMES_KANBAN_TASK}`, or `HERMES_KANBAN_TASK` as a task id.',
    '- Every user-originated root card created from an unbound session enters triage first. Dispatcher/worker-created child cards may use the lifecycle/status required by the active task graph; do not recursively force worker fan-out children back through triage.',
    '- Before naming an assignee, use the live Hermes profile roster. Use only exact installed profile names. Prefer the configured orchestrator for a root routing card when known; otherwise use a real current profile and let the triage decomposer route children.',
    '- If a Kanban tool reports a missing/unknown task id, do not retry the same call. Determine whether the turn is unbound, list/read the board with an exact id when appropriate, or create a triage root card instead.',
    '- Dispatcher-spawned workers begin with `kanban_show()` (no task-id argument), work only their claimed card, heartbeat during long work, and terminate exactly once with complete, review, or block according to Hermes worker protocol.',
    '- Do not duplicate cards after creator-session wakeups or retries. Inspect the current board/task state before creating follow-up work when provenance is uncertain.',
    '- After a task completes, prefer `kanban_show`, `kanban_attachments`, and the task result/declared artifacts. Scratch workspaces may be removed after completion; do not repeatedly probe stale workspace paths when durable attachments exist.',
    '- When the user asks for the results of completed work, answer from the substantive task results/artifacts unless they explicitly ask for board mechanics or status. Do not substitute a queue-status recap for the requested deliverable content.',
    '- Preserve user constraints, dependencies, configured concurrency limits, worker handoffs, review flow, and final-answer responsibility.',
    '',
    end,
])
for p in paths:
    p.parent.mkdir(parents=True,exist_ok=True)
    text=p.read_text(encoding='utf-8') if p.exists() else ''
    if opts.get('kanban'):
        if pattern.search(text): text=pattern.sub(block,text)
        else: text=(text.rstrip()+'\n\n' if text.strip() else '')+block+'\n'
    else:
        text=pattern.sub('',text).strip()
        if text: text+='\n'
    p.write_text(text,encoding='utf-8')
PY_KANBAN_SOUL

# Skill-management recovery policy is useful with or without Kanban. It is applied to
# every installer-managed profile without replacing custom SOUL/personality content.
python3 - data/hermes .installer-managed-profiles <<'PY_SKILL_SOUL'
from pathlib import Path
import re,sys
root=Path(sys.argv[1]); managed=Path(sys.argv[2])
names=[x.strip() for x in managed.read_text(encoding='utf-8').splitlines() if x.strip()] if managed.exists() else []
paths=[root/'SOUL.md']+[root/'profiles'/n/'SOUL.md' for n in names if (root/'profiles'/n).is_dir()]
start='<!-- HERMES_SKILL_MANAGEMENT_POLICY_START -->'
end='<!-- HERMES_SKILL_MANAGEMENT_POLICY_END -->'
pattern=re.compile(re.escape(start)+r'.*?'+re.escape(end),re.S)
block='\n'.join([
    start,
    '',
    '## Skill Authoring and Tool-Failure Recovery',
    '',
    '- When a requested skill name is human-readable, normalize it before `skill_manage`: lowercase letters/numbers plus hyphens, dots, or underscores; no spaces; start with a letter or digit.',
    '- For `create` and full `edit`, submit one complete `SKILL.md` with a closed YAML frontmatter block. Keep `name` consistent with the skill slug and use a one-sentence description of at most 60 characters ending with a period unless the installed Hermes validator reports a stricter rule.',
    '- Use `create` only for a new skill, `patch` only after loading the current skill in the same review/authoring turn and matching an exact `old_string`, `edit` for a major full rewrite, and `write_file` for supporting files. If Hermes says the current SKILL.md was not loaded, call `skill_view` before rebuilding the patch.',
    '- When source material is supplied, read the complete requested input before authoring. For large files or folders, use bounded chunks/search plus explicit coverage tracking; never silently infer unread sections.',
    '- Treat every tool validation error as corrective data. Fix the named field or syntax before another call. Never repeat an identical failing `skill_manage` request.',
    '- After two failures on the same skill operation, stop that approach: inspect the current skill/tool requirements, switch create/patch/edit strategy as appropriate, and preserve any valid partial work. Do not weaken tool-loop hard stops to force progress.',
    '- After a skill write succeeds, verify the skill can be listed/viewed and that its frontmatter and supporting files are readable before reporting success.',
    '',
    end,
])
for p in paths:
    p.parent.mkdir(parents=True,exist_ok=True)
    text=p.read_text(encoding='utf-8') if p.exists() else ''
    if pattern.search(text): text=pattern.sub(block,text)
    else: text=(text.rstrip()+'\n\n' if text.strip() else '')+block+'\n'
    p.write_text(text,encoding='utf-8')
PY_SKILL_SOUL

# Runtime guard for model-driven Kanban operations on Hermes surfaces that execute
# pre_tool_call hooks. Hermes v0.20.2 supports both blocking calls and shallow argument
# modification. LatticeVale only rewrites deterministic context mistakes; ambiguous or
# destructive lifecycle calls without a real worker binding are blocked with corrective text.
python3 - install-options.json data/hermes .installer-managed-profiles <<'PY_KANBAN_POLICY_PLUGIN'
from pathlib import Path
import json,shutil,sys
opts=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root=Path(sys.argv[2]); managed=Path(sys.argv[3])
names=[x.strip() for x in managed.read_text(encoding='utf-8').splitlines() if x.strip()] if managed.exists() else []
homes=[root]+[root/'profiles'/n for n in names if (root/'profiles'/n).is_dir()]
manifest='name: latticevale-kanban-policy\nversion: "1.2.0"\ndescription: LatticeVale triage and Kanban task-context guard.\n'
code='''from pathlib import Path
import os


def _shared_hermes_root():
    candidates=[]
    env_home=os.environ.get("HERMES_HOME")
    if env_home:
        candidates.append(Path(env_home))
    candidates.append(Path("/opt/data"))
    candidates.append(Path.home()/".hermes")
    for home in candidates:
        try:
            if home.parent.name == "profiles":
                home=home.parent.parent
            if (home/"config.yaml").is_file() or (home/"profiles").is_dir():
                return home
        except Exception:
            continue
    home=candidates[0]
    return home.parent.parent if home.parent.name == "profiles" else home


def _profile_roster():
    root=_shared_hermes_root()
    names={"default"}
    profiles=root/"profiles"
    if profiles.is_dir():
        for child in profiles.iterdir():
            if child.is_dir() and (child/"config.yaml").is_file():
                names.add(child.name)
    return sorted(names)


def _orchestrator_profile(roster):
    root=_shared_hermes_root()
    try:
        import yaml
        cfg=yaml.safe_load((root/"config.yaml").read_text(encoding="utf-8")) or {}
        kb=cfg.get("kanban") if isinstance(cfg.get("kanban"),dict) else {}
        value=str(kb.get("orchestrator_profile") or "").strip()
        if value in roster:
            return value
    except Exception:
        pass
    return "default" if "default" in roster else (roster[0] if roster else "")


def _is_placeholder_task_id(value):
    value=str(value or "").strip()
    return value in {"$HERMES_KANBAN_TASK", "${HERMES_KANBAN_TASK}", "HERMES_KANBAN_TASK"}


def _block(message):
    return {"action": "block", "message": message}


def _modify(**changes):
    return {"action": "modify", "args": changes}


def _guard_kanban_tool(tool_name, args, **kwargs):
    if not isinstance(args, dict):
        args={}
    roster=_profile_roster()
    bound=str(os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    explicit=str(args.get("task_id") or "").strip()

    if _is_placeholder_task_id(explicit):
        if bound:
            return _modify(task_id=bound)
        return _block(
            "Do not pass HERMES_KANBAN_TASK as literal text. This process has no bound worker task. Use an exact task id returned by the board, or route/create work instead of retrying the placeholder."
        )

    if tool_name == "kanban_create":
        assignee=str(args.get("assignee") or "").strip()
        if not assignee:
            orch=_orchestrator_profile(roster)
            return _block(
                "kanban_create requires a real assignee. Installed profiles: "
                + ", ".join(roster)
                + (f'. Configured orchestrator: {orch}.' if orch else '.')
                + " Retry once with an exact installed profile name."
            )
        if assignee not in roster:
            return _block(
                f'Invalid Kanban assignee "{assignee}". Installed profiles: '
                + ", ".join(roster)
                + ". Retry once with an exact installed profile; never invent role-like profile names."
            )
        # A root card created from a normal user/orchestrator turn belongs in triage.
        # Hermes pre_tool_call modification is shallow, so only the triage field is
        # changed and every other model-supplied argument is preserved.
        if not bound and args.get("triage") is not True:
            return _modify(triage=True)
        return None

    worker_only={
        "kanban_complete", "kanban_request_review", "kanban_request_changes",
        "kanban_block", "kanban_heartbeat", "kanban_attach", "kanban_attach_url",
    }
    if tool_name in worker_only:
        if not bound:
            return _block(
                f"{tool_name} is a claimed-worker lifecycle operation, but this process has no HERMES_KANBAN_TASK binding. In a normal chat turn, create/list/route tasks instead of pretending to be a worker. Do not retry this call unchanged."
            )
        if explicit and explicit != bound:
            return _block(
                f"{tool_name} is bound to task {bound}, but the call supplied a different task id. Work only the claimed task and omit task_id unless the tool explicitly requires it."
            )

    if tool_name in {"kanban_show", "kanban_attachments"} and not bound and not explicit:
        return _block(
            f"{tool_name} has no bound worker task in this normal session. Supply an exact real task_id from the board, or use kanban_list/kanban_create as appropriate."
        )

    if tool_name == "kanban_comment" and not explicit and not bound:
        return _block(
            "kanban_comment requires an exact real task_id in an ordinary/orchestrator session. Do not use a shell-variable placeholder."
        )
    return None


def register(ctx):
    ctx.register_hook("pre_tool_call", _guard_kanban_tool)
'''
for home in homes:
    d=home/'plugins'/'latticevale-kanban-policy'
    if opts.get('kanban'):
        d.mkdir(parents=True,exist_ok=True)
        (d/'plugin.yaml').write_text(manifest,encoding='utf-8')
        (d/'__init__.py').write_text(code,encoding='utf-8')
    elif d.exists():
        shutil.rmtree(d)
PY_KANBAN_POLICY_PLUGIN
# LatticeVale supplies a small keyless extraction provider because Hermes' bundled
# SearXNG backend is intentionally search-only.  This adds no container, package,
# daemon, listener, API key, or host-network mutation.  It is generated only when
# the effective managed-profile config selects latticevale-local.
python3 - data/hermes .installer-managed-profiles <<'PY_LATTICEVALE_WEB_EXTRACT_PLUGIN'
from pathlib import Path
import shutil,sys,yaml
root=Path(sys.argv[1]); managed=Path(sys.argv[2])
names=[x.strip() for x in managed.read_text(encoding='utf-8').splitlines() if x.strip()] if managed.exists() else []
homes=[root]+[root/'profiles'/n for n in names if (root/'profiles'/n).is_dir()]
manifest='name: latticevale-web-extract\nversion: "14.4.81"\ndescription: Keyless HTTP(S) page extraction for LatticeVale-managed Hermes.\nauthor: LatticeVale\nkind: backend\nprovides_web_providers:\n  - latticevale-local\n'
init_code='from .provider import LatticeValeLocalExtractProvider\n\n\ndef register(ctx):\n    ctx.register_web_search_provider(LatticeValeLocalExtractProvider())\n'
provider_code='from __future__ import annotations\n\nimport json\nimport re\nfrom html.parser import HTMLParser\nfrom typing import Any, Dict, List, Tuple\nfrom urllib.parse import urljoin, urlsplit\nfrom xml.etree import ElementTree\n\nfrom agent.web_search_provider import WebSearchProvider\nfrom tools.url_safety import (\n    create_ssrf_safe_client,\n    is_safe_url,\n    normalize_url_for_request,\n    sensitive_query_param_name,\n)\n\n\n_MAX_RESPONSE_BYTES = 2_000_000\n_MAX_REDIRECTS = 5\n_DEFAULT_MAX_CHARS = 100_000\n_MAX_OUTPUT_CHARS = 250_000\n_USER_AGENT = "LatticeVale-WebExtract/14.4.81 (Hermes Agent local extraction)"\n_REDIRECT_CODES = {301, 302, 303, 307, 308}\n_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}\n\n\nclass _HTMLTextExtractor(HTMLParser):\n    def __init__(self) -> None:\n        super().__init__(convert_charrefs=True)\n        self.parts: List[str] = []\n        self.title_parts: List[str] = []\n        self._skip_depth = 0\n        self._in_title = False\n\n    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]) -> None:\n        tag = tag.lower()\n        if tag in _SKIP_TAGS:\n            self._skip_depth += 1\n        if tag == "title" and not self._skip_depth:\n            self._in_title = True\n        if tag in {\n            "p", "div", "section", "article", "main", "header", "footer",\n            "nav", "aside", "li", "br", "tr", "h1", "h2", "h3", "h4",\n            "h5", "h6",\n        } and not self._skip_depth:\n            self.parts.append("\\n")\n\n    def handle_endtag(self, tag: str) -> None:\n        tag = tag.lower()\n        if tag == "title":\n            self._in_title = False\n        if tag in _SKIP_TAGS and self._skip_depth:\n            self._skip_depth -= 1\n        if tag in {\n            "p", "div", "section", "article", "main", "li", "tr", "h1",\n            "h2", "h3", "h4", "h5", "h6",\n        } and not self._skip_depth:\n            self.parts.append("\\n")\n\n    def handle_data(self, data: str) -> None:\n        if self._skip_depth:\n            return\n        if self._in_title:\n            self.title_parts.append(data)\n        self.parts.append(data)\n\n\ndef _clean_text(value: str) -> str:\n    value = value.replace("\\r\\n", "\\n").replace("\\r", "\\n")\n    value = re.sub(r"[ \\t\\f\\v]+", " ", value)\n    value = re.sub(r" *\\n *", "\\n", value)\n    value = re.sub(r"\\n{3,}", "\\n\\n", value)\n    return value.strip()\n\n\ndef _normalized_safe_url(url: str) -> str:\n    raw = str(url).strip()\n    parsed = urlsplit(raw)\n    if parsed.scheme.lower() not in {"http", "https"}:\n        raise ValueError("only HTTP(S) URLs are supported")\n    if not parsed.hostname:\n        raise ValueError("URL has no hostname")\n    if parsed.username is not None or parsed.password is not None:\n        raise ValueError("URLs containing credentials are not allowed")\n    normalized = normalize_url_for_request(raw)\n    sensitive = sensitive_query_param_name(normalized)\n    if sensitive:\n        raise ValueError(f"URL contains a credential-like query parameter: {sensitive}")\n    if not is_safe_url(normalized):\n        raise ValueError("URL targets a private or internal network address")\n    return normalized\n\n\ndef _text_content_type(content_type: str) -> bool:\n    base = (content_type or "").split(";", 1)[0].strip().lower()\n    if not base:\n        return True\n    return (\n        base.startswith("text/")\n        or base in {\n            "application/json",\n            "application/ld+json",\n            "application/xml",\n            "application/xhtml+xml",\n            "application/rss+xml",\n            "application/atom+xml",\n        }\n        or base.endswith("+json")\n        or base.endswith("+xml")\n    )\n\n\ndef _decode_body(raw: bytes, encoding: str | None) -> str:\n    return raw.decode(encoding or "utf-8", errors="replace")\n\n\ndef _extract_text(raw_text: str, content_type: str) -> Tuple[str, str]:\n    base = (content_type or "").split(";", 1)[0].strip().lower()\n    if "html" in base or (not base and "<html" in raw_text[:1000].lower()):\n        parser = _HTMLTextExtractor()\n        parser.feed(raw_text)\n        parser.close()\n        title = _clean_text(" ".join(parser.title_parts))\n        return title, _clean_text("".join(parser.parts))\n    if "json" in base:\n        try:\n            obj = json.loads(raw_text)\n            return "", json.dumps(obj, indent=2, ensure_ascii=False)\n        except Exception:\n            return "", _clean_text(raw_text)\n    if "xml" in base or "rss" in base or "atom" in base:\n        try:\n            root = ElementTree.fromstring(raw_text)\n            return "", _clean_text(" ".join(t for t in root.itertext()))\n        except Exception:\n            return "", _clean_text(raw_text)\n    return "", _clean_text(raw_text)\n\n\ndef _fetch_text(url: str, max_chars: int) -> Dict[str, Any]:\n    import httpx\n\n    current = _normalized_safe_url(url)\n    timeout = httpx.Timeout(20.0, connect=5.0)\n    headers = {\n        "User-Agent": _USER_AGENT,\n        "Accept": (\n            "text/html,application/xhtml+xml,application/json,application/xml,"\n            "text/plain;q=0.9,*/*;q=0.1"\n        ),\n    }\n    with create_ssrf_safe_client(\n        timeout=timeout,\n        follow_redirects=False,\n        headers=headers,\n    ) as client:\n        for redirect_count in range(_MAX_REDIRECTS + 1):\n            current = _normalized_safe_url(current)\n            with client.stream("GET", current) as response:\n                if response.status_code in _REDIRECT_CODES:\n                    if redirect_count >= _MAX_REDIRECTS:\n                        raise ValueError("too many redirects")\n                    location = response.headers.get("location", "").strip()\n                    if not location:\n                        raise ValueError("redirect response had no Location header")\n                    current = _normalized_safe_url(urljoin(current, location))\n                    continue\n                response.raise_for_status()\n                content_type = response.headers.get("content-type", "")\n                if not _text_content_type(content_type):\n                    raise ValueError(\n                        f"unsupported content type: {content_type or \'unknown\'}"\n                    )\n                body = bytearray()\n                truncated_bytes = False\n                for chunk in response.iter_bytes():\n                    remaining = _MAX_RESPONSE_BYTES - len(body)\n                    if remaining <= 0:\n                        truncated_bytes = True\n                        break\n                    if len(chunk) > remaining:\n                        body.extend(chunk[:remaining])\n                        truncated_bytes = True\n                        break\n                    body.extend(chunk)\n                raw_text = _decode_body(bytes(body), response.encoding)\n                title, content = _extract_text(raw_text, content_type)\n                truncated_chars = len(content) > max_chars or len(raw_text) > max_chars\n                return {\n                    "url": str(url),\n                    "title": title,\n                    "content": content[:max_chars],\n                    "raw_content": raw_text[:max_chars],\n                    "metadata": {\n                        "provider": "latticevale-local",\n                        "final_url": current,\n                        "status_code": response.status_code,\n                        "content_type": content_type,\n                        "truncated": bool(truncated_bytes or truncated_chars),\n                    },\n                }\n    raise ValueError("request did not complete")\n\n\nclass LatticeValeLocalExtractProvider(WebSearchProvider):\n    @property\n    def name(self) -> str:\n        return "latticevale-local"\n\n    @property\n    def display_name(self) -> str:\n        return "LatticeVale Local Extract"\n\n    def is_available(self) -> bool:\n        return True\n\n    def supports_search(self) -> bool:\n        return False\n\n    def supports_extract(self) -> bool:\n        return True\n\n    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:\n        try:\n            requested = int(kwargs.get("max_chars") or _DEFAULT_MAX_CHARS)\n        except (TypeError, ValueError):\n            requested = _DEFAULT_MAX_CHARS\n        max_chars = min(max(requested, 2_000), _MAX_OUTPUT_CHARS)\n        results: List[Dict[str, Any]] = []\n        for url in urls:\n            try:\n                results.append(_fetch_text(str(url), max_chars))\n            except Exception as exc:\n                results.append({\n                    "url": str(url),\n                    "title": "",\n                    "content": "",\n                    "raw_content": "",\n                    "metadata": {"provider": "latticevale-local"},\n                    "error": str(exc),\n                })\n        return results\n\n    def get_setup_schema(self) -> Dict[str, Any]:\n        return {\n            "name": "LatticeVale Local Extract",\n            "badge": "free · local",\n            "tag": (\n                "Keyless extraction for HTTP(S) text pages using Hermes\' "\n                "URL-safety policy; no additional service required."\n            ),\n            "env_vars": [],\n        }\n'
for home in homes:
    cfg_path=home/'config.yaml'
    cfg=yaml.safe_load(cfg_path.read_text(encoding='utf-8')) if cfg_path.exists() else {}
    cfg=cfg or {}
    web=cfg.get('web') if isinstance(cfg.get('web'),dict) else {}
    selected=web.get('extract_backend')=='latticevale-local'
    d=home/'plugins'/'web'/'latticevale-web-extract'
    if selected:
        d.mkdir(parents=True,exist_ok=True)
        (d/'plugin.yaml').write_text(manifest,encoding='utf-8')
        (d/'__init__.py').write_text(init_code,encoding='utf-8')
        (d/'provider.py').write_text(provider_code,encoding='utf-8')
    elif d.exists():
        shutil.rmtree(d)
PY_LATTICEVALE_WEB_EXTRACT_PLUGIN
# Environment values shared by every profile are written to each profile's private .env.
profile_envs=(data/hermes/.env)
while IFS= read -r name; do
  [[ -d "data/hermes/profiles/$name" ]] && profile_envs+=("data/hermes/profiles/$name/.env")
done < .installer-managed-profiles
for f in "${profile_envs[@]}"; do
  touch "$f"; chmod 0600 "$f"
  set_env "$f" TERMINAL_CWD /workspace
  remove_env_keys "$f" GATEWAY_MULTIPLEX_PROFILES
  if [[ "$(opt_bool searxng)" == true ]]; then set_env "$f" SEARXNG_URL http://searxng:8080; else remove_env_keys "$f" SEARXNG_URL; fi
  if [[ "$(opt_bool qmd)" == true ]]; then set_env "$f" OBSIDIAN_VAULT_PATH /vault; else remove_env_keys "$f" OBSIDIAN_VAULT_PATH; fi

  # Matrix runtime credentials are active only when both the shared Matrix service
  # and this exact profile's Matrix intent are enabled. Preserve installer secret
  # stores/rooms when disabled, but remove live gateway credentials so a stale
  # profile process cannot keep retrying a Synapse service the user turned off.
  matrix_runtime_enabled=false
  if [[ "$f" == data/hermes/.env ]]; then
    [[ "$(opt_bool matrix)" == true ]] && matrix_runtime_enabled=true
  elif [[ "$(opt_bool matrix)" == true ]]; then
    matrix_profile_name="${f#data/hermes/profiles/}"; matrix_profile_name="${matrix_profile_name%%/*}"
    if jq -e --arg n "$matrix_profile_name" '.workers[]? | select(.name == $n and .matrix.enabled == true)' install-options.json >/dev/null 2>&1; then
      matrix_runtime_enabled=true
    fi
  fi
  if [[ "$matrix_runtime_enabled" != true ]]; then
    remove_env_keys "$f" MATRIX_HOMESERVER MATRIX_ACCESS_TOKEN MATRIX_USER_ID MATRIX_PASSWORD MATRIX_ALLOWED_USERS MATRIX_ALLOWED_ROOMS MATRIX_E2EE_MODE MATRIX_DEVICE_ID MATRIX_RECOVERY_KEY MATRIX_RECOVERY_KEY_OUTPUT_FILE MATRIX_REACTIONS MATRIX_APPROVAL_REQUIRE_SENDER
  fi
done

if [[ "$(opt_bool honcho)" == true ]]; then
  # Honcho uses a dedicated AI peer per profile while sharing the user's workspace.
  peer="$(python3 -c 'import json; print(json.load(open("data/hermes/honcho.json"))["hosts"]["hermes"]["peerName"])')"
  python3 - "$peer" .installer-managed-profiles <<'PY'
from pathlib import Path
import json,sys
peer=sys.argv[1]; managed=Path(sys.argv[2])
names=[x.strip() for x in managed.read_text().splitlines() if x.strip()] if managed.exists() else []
for name in ['default']+[n for n in names if (Path('data/hermes/profiles')/n).is_dir()]:
    host='hermes' if name=='default' else 'hermes.'+name
    path=Path('data/hermes/honcho.json') if name=='default' else Path('data/hermes/profiles')/name/'honcho.json'
    try: cfg=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    except Exception: cfg={}
    if not isinstance(cfg,dict): cfg={}
    cfg['baseUrl']='http://honcho-api:8000'
    hosts=cfg.get('hosts') if isinstance(cfg.get('hosts'),dict) else {}
    block=hosts.get(host) if isinstance(hosts.get(host),dict) else {}
    block.update({'enabled':True,'aiPeer':'hermes' if name=='default' else name,'peerName':peer,'workspace':'hermes'})
    hosts[host]=block; cfg['hosts']=hosts
    path.write_text(json.dumps(cfg,indent=2)+'\n')
    path.chmod(0o600)
PY
  apply_honcho_timeout_policy data/hermes/honcho.json || return 1
  while IFS= read -r honcho_profile; do
    [[ -n "$honcho_profile" && -s "data/hermes/profiles/$honcho_profile/honcho.json" ]] || continue
    apply_honcho_timeout_policy "data/hermes/profiles/$honcho_profile/honcho.json" || return 1
  done < .installer-managed-profiles
fi


# Reapply Matrix runtime credentials after provider/model selection. The Matrix bot password,
# when retained, stays installer-private in secrets/matrix-bot.env; Hermes authenticates with
# the access token, which upstream recommends as the more reliable method.
if [[ "$(opt_bool matrix)" == true && -e .matrix-configured && -s secrets/matrix-bot.env ]]; then
  apply_matrix_runtime_env secrets/matrix-bot.env
fi
return 0
}

stage_reconcile() {
# Start/reconcile the complete selected stack after all Hermes profile and integration config is written.
# Matrix-backed Hermes gateways are sensitive to a Docker DNS/Synapse startup race.
# Bring Synapse to host-level readiness first; after Hermes starts, prove the same
# synapse:8008 endpoint is reachable from inside hermes-agent before recycling the
# default gateway. This applies equally to fresh install and repair/update runs.
if [[ "$(opt_bool matrix)" == true ]]; then
  ensure_matrix_online 60
fi
timeout --foreground --kill-after=10s 180s docker compose up -d --pull never --no-build --remove-orphans
# Compose considers a container 'Running' before its healthcheck becomes healthy. Hotfix 1
# could therefore finish Matrix reconciliation quickly and immediately fail verify_reconcile
# while managed Ollama was still in its normal startup period. Wait for the selected managed
# Ollama healthcheck here so repair/fresh install only verify after the backend has settled.
wait_managed_ollama_healthy 60
for _ in $(seq 1 60); do timeout --foreground --kill-after=5s 15s docker exec -u hermes hermes-agent hermes --version >/dev/null 2>&1 && break; sleep 2; done
timeout --foreground --kill-after=5s 15s docker exec -u hermes hermes-agent hermes --version >/dev/null
wait_http Hermes-API http://127.0.0.1:${HERMES_API_HOST_PORT}/health 60
if [[ "$(opt_bool dashboard)" == true ]]; then
  wait_http Dashboard http://127.0.0.1:${DASHBOARD_HOST_PORT}/ 60
fi

# Recheck selected service health after final reconciliation.
if [[ "$(opt_bool matrix)" == true ]]; then
  wait_matrix_backend_from_hermes 60
  if ! start_or_restart_default_gateway_exact; then
    echo 'Default Hermes gateway restart failed after Matrix became reachable from the Hermes container.' >&2
    return 1
  fi
  matrix_room="$(sed -n 's/^MATRIX_ROOM=//p' .matrix-info | head -n1)"
  matrix_token="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' secrets/matrix-bot.env | head -n1)"
  if [[ -n "$matrix_room" && -n "$matrix_token" ]]; then
    if wait_matrix_room_join "$matrix_token" "$matrix_room" 'Default Hermes Matrix bot' 45; then
      :
    else
      join_rc=$?
      if [[ "$join_rc" -eq 2 ]]; then
        echo 'Matrix/Synapse became unavailable during the default-bot join check. LatticeVale will restart its managed Synapse services and retry once automatically.' >&2
        if ensure_matrix_online 60 && \
           start_or_restart_default_gateway_exact && \
           wait_matrix_room_join "$matrix_token" "$matrix_room" 'Default Hermes Matrix bot' 45; then
          echo 'Default Hermes Matrix join recovered after restarting Synapse.'
        else
          echo 'Default Hermes Matrix bot still did not join after one bounded Synapse recovery attempt; preserved state is resumable.' >&2
          docker logs --tail 120 hermes-agent 2>&1 | tail -n 120 >&2 || true
          return 1
        fi
      else
        echo 'Default Hermes Matrix bot did not join the installer-created encrypted room within the bounded readiness window.' >&2
        docker logs --tail 120 hermes-agent 2>&1 | tail -n 120 >&2 || true
        return 1
      fi
    fi

    matrix_device_id="$(sed -n 's/^MATRIX_DEVICE_ID=//p' secrets/matrix-bot.env | head -n1)"
    [[ -n "$matrix_device_id" ]] || { echo 'Matrix E2EE device ID is missing after reconciliation.' >&2; return 1; }
    curl -fsS --connect-timeout 5 --max-time 10 -H "Authorization: Bearer $matrix_token" \
      http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/devices | \
      jq -e --arg d "$matrix_device_id" '.devices | any(.device_id == $d)' >/dev/null 2>&1 || { echo "Matrix bot device '$matrix_device_id' did not verify on the homeserver." >&2; return 1; }

    reconcile_encoded_room="$(jq -rn --arg v "$matrix_room" '$v|@uri')"
    reconcile_encryption_algorithm="$(curl -fsS --connect-timeout 5 --max-time 10 -H "Authorization: Bearer $matrix_token" \
      "http://127.0.0.1:${MATRIX_HOST_PORT}/_matrix/client/v3/rooms/$reconcile_encoded_room/state/m.room.encryption/" | jq -er .algorithm)"
    [[ "$reconcile_encryption_algorithm" == 'm.megolm.v1.aes-sha2' ]] || { echo 'Matrix room is no longer verified as end-to-end encrypted.' >&2; return 1; }
  fi
fi
[[ "$(opt_bool searxng)" == true ]] && wait_http SearXNG http://127.0.0.1:${SEARXNG_HOST_PORT}/ 60
[[ "$(opt_bool qmd)" == true ]] && wait_qmd_health 90
[[ "$(opt_bool honcho)" == true ]] && wait_http Honcho http://127.0.0.1:${HONCHO_HOST_PORT}/health 90
# The default gateway restart above also restarts the gateway-owned API/Dashboard server.
# Hotfix 2 waited for these surfaces before that restart, then verified them immediately
# afterward. Put the readiness barrier after the final lifecycle mutation instead.
wait_hermes_gateway_surfaces 'reconcile gateway restart' 60
if [[ "$(opt_bool matrix)" == true ]]; then
  wait_matrix_backend_from_hermes 60
fi
verify_live_resource_policy_limits || {
  echo 'Reconcile completed but the live Docker CPU/RAM ceilings still do not match policy v11.' >&2
  return 1
}
return 0
}

stage_kanban_gateway() {
if [[ "$(opt_bool kanban)" == true ]]; then
  echo 'Initializing Hermes Kanban.'
  timeout --foreground --kill-after=5s 60s docker exec -u hermes hermes-agent hermes kanban init >/dev/null
  # Explicit top-level toolsets are intentional: current Hermes releases gate orchestrator Kanban on this setting.
fi

# Reload the default gateway after all config/env integration changes. Named profiles
# remain stopped unless their installer options explicitly enable an independent Matrix
# room; those profiles need a resident gateway to receive Matrix traffic. If Matrix is
# selected, require Synapse to be reachable from inside hermes-agent before any gateway
# reload so a live process is not mistaken for a connected Matrix adapter.
if [[ "$(opt_bool matrix)" == true ]]; then
  ensure_matrix_online 60
  wait_matrix_backend_from_hermes 60
fi
if ! start_or_restart_default_gateway_exact; then
  echo 'Default Hermes gateway could not be reconciled after Kanban/config initialization.' >&2
  return 1
fi
# Stop installer-managed profile gateways that are no longer runtime-enabled for
# Matrix before starting the selected ones. LatticeVale keeps their secret stores and
# rooms intact so re-enabling Matrix can restore the same identity later.
while IFS= read -r managed_profile; do
  [[ -n "$managed_profile" ]] || continue
  profile_matrix_enabled=false
  if [[ "$(opt_bool matrix)" == true ]] && jq -e --arg n "$managed_profile" '.workers[]? | select(.name == $n and .matrix.enabled == true)' install-options.json >/dev/null 2>&1; then
    profile_matrix_enabled=true
  fi
  if [[ "$profile_matrix_enabled" != true ]]; then
    if ! stop_profile_gateway_exact "$managed_profile"; then
      echo "WARNING: profile '$managed_profile' is not Matrix-enabled but its exact gateway could not be stopped cleanly; preserved profile state was not deleted." >&2
    fi
  fi
done < .installer-managed-profiles

if [[ "$(opt_bool matrix)" == true ]]; then
  while IFS= read -r matrix_profile; do
    [[ -n "$matrix_profile" ]] || continue
    matrix_profile_secret="secrets/matrix-profiles/$matrix_profile.env"
    matrix_profile_state="$(read_env_file_value_optional "$matrix_profile_secret" LATTICEVALE_PROVISIONING_STATE)"
    [[ -n "$matrix_profile_state" ]] || matrix_profile_state="$(read_env_file_value_optional "$matrix_profile_secret" FOUNDRY_PROVISIONING_STATE)"
    if [[ "$matrix_profile_state" == pending-manual ]]; then
      echo "Profile '$matrix_profile' Matrix activation is incomplete; retrying the bounded finisher before gateway reconciliation."
      if ./manage.sh matrix-profile-finish "$matrix_profile"; then
        matrix_profile_state=complete
      else
        echo "WARNING: Matrix profile '$matrix_profile' remains pending; skipping its gateway reconciliation without blocking the core stack." >&2
        continue
      fi
    fi
    [[ "$matrix_profile_state" == complete ]] || continue
    if ! start_or_restart_profile_gateway_exact "$matrix_profile"; then
      echo "WARNING: Matrix profile '$matrix_profile' gateway could not be started; preserving profile state without blocking the core stack." >&2
      continue
    fi
  done < <(jq -r '.workers[]? | select(.matrix.enabled == true) | .name' install-options.json)
fi
# This stage performs the last gateway restart in the installer. Do not mark it done
# until the gateway-owned API/Dashboard surfaces have actually returned.
wait_hermes_gateway_surfaces 'Kanban/final gateway reload' 60
if [[ "$(opt_bool matrix)" == true ]]; then
  wait_matrix_backend_from_hermes 60
fi
return 0
}

stage_finalize() {
cat > .install-info <<EOF_INFO
DASHBOARD=$(opt_bool dashboard)
MULTI_AGENT=$(opt_bool multiAgent)
KANBAN=$(opt_bool kanban)
MATRIX=$(opt_bool matrix)
TAILSCALE=$(opt_bool tailscale)
TAILSCALE_MODE=$(opt_text tailscaleMode)
TAILSCALE_DASHBOARD=$(opt_bool tailscaleDashboard)
TAILSCALE_DASHBOARD_PORT=$(opt_text tailscaleDashboardPort)
TAILSCALE_DASHBOARD_BRIDGE_PORT=$(opt_text dashboardBridgePort)
TAILSCALE_MATRIX=$(opt_bool tailscaleMatrix)
TAILSCALE_MATRIX_PORT=$(opt_text tailscaleMatrixPort)
TAILSCALE_MATRIX_BRIDGE_PORT=$(opt_text matrixBridgePort)
SEARXNG=$(opt_bool searxng)
QMD=$(opt_bool qmd)
HONCHO=$(opt_bool honcho)
HERMES_LOCAL_AI=$(opt_bool hermesLocalAI)
LOCAL_TEXT_BACKEND=$(local_text_backend)
LOCAL_TEXT_MODEL=$(local_text_model_name)
DIRECTML_TEXT_MODEL=$(directml_text_model)
DIRECTML_PORT=$DIRECTML_PORT
OLLAMA_FALLBACK_TEXT_MODEL=$(opt_text localTextModel)
LOCAL_EMBEDDING_MODEL=$(opt_text localEmbeddingModel)
OBSIDIAN=$(opt_bool obsidian)
DASHBOARD_LOCAL=http://localhost:${DASHBOARD_HOST_PORT}
MATRIX_LOCAL=http://localhost:${MATRIX_HOST_PORT}
OBSIDIAN_VAULT=$(if [[ "$(opt_bool obsidian)" == true ]]; then opt_text obsidianVaultWslPath; else printf '%s' "$PWD/vault"; fi)
EOF_INFO
chmod 0600 .install-info

touch .configured
chmod 0600 .configured

echo
echo 'Stack configuration complete.'
[[ "$(opt_bool dashboard)" == true ]] && echo "Dashboard: http://localhost:${DASHBOARD_HOST_PORT}"
[[ "$(opt_bool matrix)" == true ]] && echo "Matrix:    http://localhost:${MATRIX_HOST_PORT}"
[[ "$(opt_bool searxng)" == true ]] && echo "SearXNG:   http://localhost:${SEARXNG_HOST_PORT}"
[[ "$(opt_bool qmd)" == true ]] && echo 'QMD:       Docker-internal MCP/search service (Hermes -> http://qmd:8181/mcp)'
[[ "$(opt_bool honcho)" == true ]] && echo "Honcho:    http://localhost:${HONCHO_HOST_PORT}/health (text=$(local_text_backend); embeddings=Ollama)"
[[ "$(opt_bool hermesLocalAI)" == true ]] && echo "Hermes AI: LatticeVale local text backend=$(local_text_backend), model=$(local_text_model_name)"
echo
echo 'LatticeVale hardware/resource summary:'
echo "  WSL CPUs: $(nproc 2>/dev/null || printf '?')"
visible_mem_mib="$(awk '/^MemTotal:/ {printf "%.0f", $2/1024}' /proc/meminfo 2>/dev/null || true)"
[[ -n "$visible_mem_mib" ]] && echo "  WSL RAM:  $((visible_mem_mib/1024)) GiB (${visible_mem_mib} MiB visible)"
echo "  Resource policy: $(if [[ "$(opt_bool containerResourceLimits)" == true ]]; then printf '%s' 'adaptive ceilings'; else printf '%s' 'LatticeVale ceilings disabled'; fi)"
if local_ai_enabled; then
  echo "  Text backend: $(local_text_backend)"
  if directml_text_enabled; then
    echo "  DirectML model: $(directml_text_model) (port $DIRECTML_PORT; 8192-token cap; serial inference; 300s idle unload)"
    echo "  Ollama fallback model: $(opt_text localTextModel)"
  else
    echo "  Ollama text model: $(opt_text localTextModel)"
  fi
  echo "  Ollama acceleration/fallback configuration: $(sed -n 's/^LATTICEVALE_OLLAMA_ACCELERATION=//p' .env | head -n1)"
  echo '  Run ./manage.sh status after model use for DirectML/fallback health and Ollama loaded-model offload evidence.'
else
  echo '  Ollama: not selected'
fi
if [[ -e .matrix-cross-signing-pending ]]; then
  echo 'Default Matrix identity cross-signing recovery is pending for a preserved legacy identity. The stack remains usable; Resume / repair will retry without rotating its account, device, room, token, or crypto store.'
fi
if [[ -s MATRIX-SECONDARY-PROFILES.txt ]] && grep -q '^Status: pending-manual$' MATRIX-SECONDARY-PROFILES.txt 2>/dev/null; then
  echo 'Secondary Matrix profile activation is pending. The core stack is configured; Resume / repair and normal stack start will retry the existing protected identity and room.'
fi
if grep -q '^LATTICEVALE_CROSS_SIGNING_STATE=pending$' secrets/matrix-profiles/*.env 2>/dev/null; then
  echo 'Secondary Matrix profile cross-signing persistence is pending. The protected profile state is intact; Resume / repair will retry this hardening step.'
fi
echo 'Run ./manage.sh verify for a startup-aware post-install verification (it waits for services to settle).'
return 0
}


# Lightweight runtime refresh used after a WSL restart. WSL CPU/RAM limits are
# effective only after the WSL VM restarts; recalculating here means the next normal
# LatticeVale start automatically follows the resources WSL now exposes.
if [[ "${1:-}" == --refresh-resource-policy ]]; then
  if [[ "$(opt_bool containerResourceLimits)" == true ]] && verify_adaptive_runtime_policy; then
    exit 0
  fi
  refresh_accel=cpu
  if managed_ollama_enabled; then refresh_accel="$(resolve_ollama_acceleration)" || exit 1; fi
  write_latticevale_compose_overlay "$refresh_accel" "$(opt_bool containerResourceLimits)"
  exit 0
fi

# Canonical resumable sequence. Checkpoints are tied to managed choices and explicit
# per-stage migration revisions, not the installer ZIP version. Legacy checkpoints are
# migrated only after live verification, while explicit recovery flags force their stages.
assert_docker_namespace_safe
run_stage prepare_config 'Prepare installer-owned configuration' verify_prepare_config stage_prepare_config
run_uncheckpointed_repair_step repair_runtime_policy 'Reconcile adaptive runtime/RAM policy' repair_runtime_policy_reconcile
run_uncheckpointed_repair_step repair_storage_maintenance 'Repair age/storage drift and reclaim LatticeVale-owned disposable cache' repair_storage_maintenance
run_stage infrastructure 'Start and verify selected supporting infrastructure' verify_infrastructure stage_infrastructure
run_uncheckpointed_repair_step repair_database_maintenance 'Maintain aged installer-managed databases safely' repair_database_maintenance
run_stage matrix_bootstrap 'Bootstrap and verify Matrix identity/room' verify_matrix stage_matrix_bootstrap
run_stage provider_setup 'Configure and verify default Hermes provider/model' verify_provider stage_provider_setup
run_stage profiles 'Create/repair and verify Hermes profiles' verify_profiles stage_profiles
complete_repair_package_refresh
run_stage matrix_profiles 'Provision and verify profile-specific Matrix identities/rooms' verify_matrix_profiles stage_matrix_profiles
run_stage matrix_cross_signing 'Secure Matrix device cross-signing settings' verify_matrix_cross_signing stage_matrix_cross_signing
run_stage matrix_profile_cross_signing 'Secure profile-specific Matrix device cross-signing settings' verify_matrix_profile_cross_signing stage_matrix_profile_cross_signing
run_stage integrations 'Apply and verify Hermes integrations' verify_integrations stage_integrations
run_stage reconcile 'Reconcile and health-check the complete Docker stack' verify_reconcile stage_reconcile
run_stage kanban_gateway 'Initialize Kanban and reload the Hermes gateway' verify_kanban_gateway stage_kanban_gateway
run_stage finalize 'Write final installer metadata' verify_finalize stage_finalize
if ! verify_adaptive_runtime_policy; then
  CURRENT_STAGE=repair_runtime_policy
  state_mark repair_runtime_policy broken 'adaptive runtime/RAM policy is still stale or incomplete after repair'
  echo 'Final repair verification failed: adaptive runtime/RAM policy is still stale or incomplete. The installer will not report success while runtimePolicy remains PARTIAL.' >&2
  exit 1
fi
state_finish

echo
echo 'Recovery-aware configuration complete.'
echo 'Run ./manage.sh audit for the state-aware verification report.'

