#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "Bootstrap failed on line $LINENO" >&2' ERR

if [[ $EUID -ne 0 ]]; then echo 'Run this bootstrap as root.' >&2; exit 1; fi
# The bundle installs and manages the rootful Engine in this WSL distro. Force all
# installer Docker operations to its local socket rather than inherited CLI context.
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
export DOCKER_HOST=unix:///var/run/docker.sock
linux_user="${1:-}"
options_b64="${2:-}"
installer_version="${3:-v13}"
force_managed_update="${4:-false}"
[[ "$force_managed_update" == true || "$force_managed_update" == false ]] || { echo 'Invalid force-managed-update control flag.' >&2; exit 2; }
if [[ -z "$linux_user" ]] || ! id "$linux_user" >/dev/null 2>&1; then
  echo 'Usage: bootstrap.sh EXISTING_LINUX_USER OPTIONS_BASE64' >&2; exit 2
fi
if [[ -z "$options_b64" ]]; then echo 'Installer options were not supplied.' >&2; exit 2; fi
[[ "$installer_version" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || { echo 'Installer version identifier is invalid.' >&2; exit 2; }

bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
user_home="$(getent passwd "$linux_user" | cut -d: -f6)"
if [[ -z "$user_home" || "$user_home" != /* || ! -d "$user_home" ]]; then
  echo "The selected Linux user '$linux_user' has no usable absolute home directory." >&2
  exit 2
fi
stack_dir="$user_home/hermes-stack"
linux_uid="$(id -u "$linux_user")"
linux_gid="$(id -g "$linux_user")"

# Decode the Windows-selected options before package/recovery work so a managed repair can
# distinguish missing prerequisites from already-satisfied prerequisites without upgrading
# unrelated packages. Full JSON validation happens after python3 is guaranteed available.
tmp_options="$(mktemp)"
trap 'rm -f "$tmp_options"' EXIT
printf '%s' "$options_b64" | base64 -d > "$tmp_options"
repair_run=false
obsidian_selected=false
local_ai_requested=false
ollama_acceleration=cpu
# Before Python is guaranteed available, determine only the package-maintenance mode
# from installer-owned filesystem state. Do not regex-parse JSON control flags: valid
# JSON strings can contain text that looks like another key/value pair.
if [[ -f "$stack_dir/install-options.json" || -f "$stack_dir/.installer-state.json" ]]; then repair_run=true; fi
if [[ "$force_managed_update" == true && "$repair_run" != true ]]; then
  echo 'Update / repair is valid only for an existing installer-managed LatticeVale stack.' >&2
  exit 2
fi

# A managed stack root must be a real directory. Never let root-level recovery operations
# follow a replacement symlink outside the selected user's dedicated Hermes tree.
if [[ -L "$stack_dir" ]]; then
  echo "Unsafe LatticeVale stack path: '$stack_dir' is a symbolic link. Replace it with a real directory before continuing." >&2
  exit 2
fi

# An existing managed stack can reach this bootstrap with very little logical WSL free
# space. Reclaim only root-owned disposable package/staging residue BEFORE creating the
# pre-repair configuration snapshot. This deliberately never touches application data.
if [[ -f "$stack_dir/install-options.json" || -f "$stack_dir/.installer-state.json" ]]; then
  echo 'Repair pre-maintenance: clearing disposable APT cache and stale LatticeVale staging directories.'
  apt-get clean >/dev/null 2>&1 || true
  find /tmp -mindepth 1 -maxdepth 1 -type d \( -name 'latticevale-installer-*' -o -name 'latticevale-audit-*' -o -name 'hermes-installer-*' -o -name 'hermes-audit-*' \) -mmin +60 -exec rm -rf -- {} + 2>/dev/null || true
fi

# Preserve installer-owned configuration before a rerun upgrades/replaces scripts. This is
# deliberately configuration-focused; database bind mounts are never deleted by the installer.
if [[ -d "$stack_dir" ]]; then
  if [[ -L "$stack_dir/backups" ]]; then
    echo "Unsafe LatticeVale backup path: '$stack_dir/backups' is a symbolic link. Repair it manually before continuing." >&2
    exit 2
  fi
  if [[ -e "$stack_dir/backups" ]] && mountpoint -q -- "$stack_dir/backups" 2>/dev/null; then
    echo "Unsafe LatticeVale backup path: '$stack_dir/backups' is an external mountpoint. LatticeVale will not write repair snapshots across it." >&2
    exit 2
  fi
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="$stack_dir/backups/pre-$installer_version-$stamp"
  install -d -m 0700 -o "$linux_uid" -g "$linux_gid" "$backup_dir"
  backup_items=()
  for item in compose.yaml compose.latticevale.yaml compose.override.yaml configure-stack.sh manage.sh state-audit.py install-options.json .installer-state.json .install-info .configured .repair-package-refresh .repair-package-refresh-pending .matrix-info .matrix-configured .tailscale-info .windows-native-info .env secrets data/hermes/config.yaml data/hermes/.env .installer-managed-profiles; do
    [[ -e "$stack_dir/$item" ]] && backup_items+=("$item")
  done
  # Logs are diagnostic, not application state. Preserve them in the configuration
  # snapshot when reasonably small, but do not duplicate a pathological log tree and
  # consume the remaining repair space before cleanup can run.
  if [[ -d "$stack_dir/logs" ]]; then
    # Log sizing is advisory. Keep it on the WSL root filesystem and hard-bound the
    # scan so a pathological/log-mounted tree cannot stall repair before staging.
    logs_kib="$(timeout --foreground --kill-after=2s 10s du -skx -- "$stack_dir/logs" 2>/dev/null | awk '{print $1}' || true)"
    if [[ "$logs_kib" =~ ^[0-9]+$ && "$logs_kib" -le 102400 ]]; then
      backup_items+=(logs)
    elif [[ "$logs_kib" =~ ^[0-9]+$ ]]; then
      echo 'Skipping oversized installer-log directory in the pre-repair configuration snapshot; application data is unaffected.' >&2
    else
      echo 'Skipping installer logs because their size could not be determined within the bounded repair diagnostic window; application data is unaffected.' >&2
    fi
  fi
  if ((${#backup_items[@]})); then
    (cd "$stack_dir" && tar -czf "$backup_dir/installer-config.tar.gz" "${backup_items[@]}")
    chown "$linux_uid:$linux_gid" "$backup_dir/installer-config.tar.gz"
    chmod 0600 "$backup_dir/installer-config.tar.gz"
  fi
fi

compat_file="$bundle_root/compatibility.conf"
[[ -r "$compat_file" ]] || { echo 'Installer bundle is incomplete: compatibility.conf is missing.' >&2; exit 3; }
# shellcheck disable=SC1090
. "$compat_file"
[[ -n "${SUPPORTED_UBUNTU_VERSIONS:-}" ]] || { echo 'compatibility.conf has no supported Ubuntu release list.' >&2; exit 3; }

repair_refresh_days="${MANAGED_REPAIR_REFRESH_DAYS:-30}"
[[ "$repair_refresh_days" =~ ^[0-9]+$ && "$repair_refresh_days" -ge 1 && "$repair_refresh_days" -le 365 ]] || { echo 'Invalid MANAGED_REPAIR_REFRESH_DAYS in compatibility.conf.' >&2; exit 3; }
repair_refresh_interval_seconds=$((repair_refresh_days * 86400))
repair_refresh_revision="${MANAGED_REPAIR_REFRESH_REVISION:-1}"
[[ "$repair_refresh_revision" =~ ^[0-9]+$ && "$repair_refresh_revision" -ge 1 ]] || { echo 'Invalid MANAGED_REPAIR_REFRESH_REVISION in compatibility.conf.' >&2; exit 3; }
repair_refresh_state="$stack_dir/.repair-package-refresh"
repair_refresh_pending_file="$stack_dir/.repair-package-refresh-pending"
repair_refresh_pending=false
repair_root_refresh_needed=false
if [[ "$repair_run" == true ]]; then
  for marker in "$repair_refresh_state" "$repair_refresh_pending_file"; do
    [[ ! -L "$marker" ]] || { echo "Unsafe installer repair-refresh marker: '$marker' is a symbolic link." >&2; exit 3; }
  done
  if [[ -f "$repair_refresh_pending_file" ]]; then
    repair_refresh_pending=true
    echo 'Managed package/image refresh was already started by an earlier interrupted run; resuming the pending refresh without repeating completed root package work.'
  else
    last_refresh_epoch="$(sed -n 's/^LAST_SUCCESS_EPOCH=//p' "$repair_refresh_state" 2>/dev/null | head -n1 || true)"
    last_refresh_revision="$(sed -n 's/^POLICY_REVISION=//p' "$repair_refresh_state" 2>/dev/null | head -n1 || true)"
    now_epoch="$(date +%s)"
    if [[ "$force_managed_update" == true ]]; then
      repair_refresh_pending=true
      repair_root_refresh_needed=true
      echo "Explicit Update / repair requested: forcing this bundle's installer-managed package/image/source refresh now; the ${repair_refresh_days}-day periodic gate is bypassed for this run."
    elif [[ ! "$last_refresh_epoch" =~ ^[0-9]+$ ]] || [[ "$last_refresh_revision" != "$repair_refresh_revision" ]] || (( now_epoch - last_refresh_epoch >= repair_refresh_interval_seconds )); then
      repair_refresh_pending=true
      repair_root_refresh_needed=true
      if [[ "$last_refresh_revision" != "$repair_refresh_revision" ]]; then
        echo "Managed repair package/image refresh is due because the installer refresh policy revision changed (saved: ${last_refresh_revision:-none}; required: $repair_refresh_revision)."
      else
        echo "Managed repair package/image refresh is due (interval: ${repair_refresh_days} days; legacy installs without a refresh marker refresh once)."
      fi
    fi
    unset last_refresh_epoch last_refresh_revision now_epoch
  fi
  unset marker
fi

. /etc/os-release 2>/dev/null || { echo 'Could not identify the Linux distribution.' >&2; exit 3; }
if [[ "${ID:-}" != ubuntu ]]; then echo "This bundle supports Ubuntu WSL distributions only; detected ${ID:-unknown}." >&2; exit 3; fi
case " ${SUPPORTED_UBUNTU_VERSIONS} " in
  *" ${VERSION_ID:-unknown} "*) ;;
  *) echo "Unsupported Ubuntu release ${VERSION_ID:-unknown}. Supported releases for this installer build: ${SUPPORTED_UBUNTU_VERSIONS}." >&2; exit 3;;
esac
export DEBIAN_FRONTEND=noninteractive
prereq_packages=(ca-certificates curl git gnupg jq openssl python3 python3-yaml sudo tzdata uidmap)
missing_prereqs=()
for pkg in "${prereq_packages[@]}"; do
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -qx 'install ok installed' || missing_prereqs+=("$pkg")
done
if [[ "$repair_root_refresh_needed" == true ]]; then
  if [[ "$force_managed_update" == true ]]; then
    echo 'Update / repair: refreshing APT metadata and upgrading/installing only LatticeVale prerequisite packages plus the managed Docker package set; unrelated Ubuntu packages are not broadly upgraded.'
  else
    echo 'Aged managed repair: refreshing APT metadata and upgrading/installing only LatticeVale prerequisite packages; unrelated Ubuntu packages are not broadly upgraded.'
  fi
  apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
  apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends "${prereq_packages[@]}"
elif [[ "$repair_run" == true && ${#missing_prereqs[@]} -eq 0 ]]; then
  echo 'Repair prerequisite check: required Ubuntu packages are already installed and the periodic managed-package refresh is not due.'
else
  apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
  if [[ "$repair_run" == true ]]; then
    apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends "${missing_prereqs[@]}"
  else
    apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends "${prereq_packages[@]}"
  fi
fi
python3 -m json.tool "$tmp_options" >/dev/null
# Parse every root-affecting option structurally before GPU/runtime or permission
# behavior consumes it. This is deliberately narrower than configure-stack's full
# schema validation, which still runs before stack-level mutations.
parsed_bootstrap_options="$(python3 - "$tmp_options" <<'PY_BOOTSTRAP_OPTIONS'
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding='utf-8'))
if not isinstance(d,dict):
    raise SystemExit('Invalid install options: top level must be an object.')
def flag(name):
    v=d.get(name,False)
    if not isinstance(v,bool):
        raise SystemExit(f'Invalid install options: {name} must be true or false.')
    return 'true' if v else 'false'
accel=d.get('ollamaAcceleration','cpu')
if accel not in ('auto','cpu','nvidia','amd'):
    raise SystemExit('Invalid install options: ollamaAcceleration must be auto, cpu, nvidia, or amd.')
backend=d.get('ollamaBackend','managed')
if backend not in ('managed','windows-native'):
    raise SystemExit('Invalid install options: ollamaBackend must be managed or windows-native.')
transport=d.get('windowsOllamaTransport','windows-gateway-relay') or 'windows-gateway-relay'
if backend == 'windows-native' and transport not in ('windows-gateway-relay','wsl-localhost-relay','wsl-host-relay'):
    raise SystemExit('Invalid install options: windowsOllamaTransport must be windows-gateway-relay, wsl-localhost-relay, or wsl-host-relay when native Windows Ollama is selected.')
if backend != 'windows-native':
    transport='windows-gateway-relay'
local_ai = d.get('honcho',False) or d.get('hermesLocalAI',False)
for key in ('honcho','hermesLocalAI'):
    if key in d and not isinstance(d[key],bool):
        raise SystemExit(f'Invalid install options: {key} must be true or false.')
print('\t'.join((flag('repairMaintenance'),flag('obsidian'),'true' if local_ai else 'false',accel,backend,transport)))
PY_BOOTSTRAP_OPTIONS
)"
IFS=$'\t' read -r requested_repair obsidian_selected local_ai_requested ollama_acceleration ollama_backend ollama_transport <<< "$parsed_bootstrap_options"
# Existing installer-owned state remains sufficient to select repair-safe package
# behavior even if a reconfigure run intentionally records repairMaintenance=false.
[[ "$requested_repair" == true ]] && repair_run=true
unset parsed_bootstrap_options requested_repair

# Avoid redoing Docker package surgery on every recovery run only when ALL
# packages required by Docker's official Ubuntu installation are installed.
docker_packages_ready=true
docker_required_packages=(docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin)
missing_docker_packages=()
for pkg in "${docker_required_packages[@]}"; do
  if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -qx 'install ok installed'; then
    docker_packages_ready=false
    missing_docker_packages+=("$pkg")
  fi
done
if [[ "$docker_packages_ready" != true || "$repair_root_refresh_needed" == true ]]; then
  # Docker's official Ubuntu packages conflict with distro-provided Docker/containerd packages.
  # Remove package conflicts only; never delete /var/lib/docker or /var/lib/containerd data.
  for pkg in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
    apt-get remove -y "$pkg" >/dev/null 2>&1 || true
  done

  # Preserve any pre-existing Docker repository configuration before normalizing
  # it to Docker's current official Ubuntu instructions. Backup suffixes are ignored
  # by APT, so recovery remains possible without creating duplicate active sources.
  repo_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  for existing in /etc/apt/sources.list.d/docker.sources /etc/apt/sources.list.d/docker.list                   /etc/apt/keyrings/docker.asc /etc/apt/keyrings/docker.gpg; do
    if [[ -e "$existing" ]]; then
      cp -a -- "$existing" "$existing.latticevale-pre-$repo_stamp.bak"
    fi
  done
  unset existing repo_stamp

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL --connect-timeout 15 --max-time 120 --retry 3 --retry-delay 2 https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  arch="$(dpkg --print-architecture)"
  ubuntu_codename="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
  [[ -n "$ubuntu_codename" ]] || { echo 'Ubuntu codename is missing from /etc/os-release.' >&2; exit 4; }
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $ubuntu_codename
Components: stable
Architectures: $arch
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  rm -f /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.gpg
  apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
  if [[ "$repair_root_refresh_needed" == true ]]; then
    echo "Aged managed repair: upgrading/installing the complete official Docker Engine/CLI/containerd/Buildx/Compose package set from Docker's configured stable Ubuntu repository."
    apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y "${docker_required_packages[@]}"
  elif [[ "$repair_run" == true ]]; then
    echo "Repair Docker package check: installing only missing official Docker packages: ${missing_docker_packages[*]}"
    apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y "${missing_docker_packages[@]}"
  else
    apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y "${docker_required_packages[@]}"
  fi
fi
usermod -aG docker "$linux_user"

start_docker_daemon() {
  if timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1; then return 0; fi
  if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl enable docker.service containerd.service >/dev/null 2>&1 || true
    timeout --foreground --kill-after=10s 90s systemctl start docker.service
  elif command -v service >/dev/null 2>&1; then
    timeout --foreground --kill-after=10s 90s service docker start >/dev/null 2>&1 || true
  fi
  for _ in {1..30}; do timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1 && return 0; sleep 1; done
  # Last-resort compatibility path for older inbox WSL2 builds without systemd/init startup.
  nohup dockerd >/var/log/hermes-dockerd.log 2>&1 </dev/null &
  for _ in {1..30}; do timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1 && return 0; sleep 1; done
  echo 'Docker daemon did not start. See /var/log/hermes-dockerd.log if present.' >&2
  return 1
}

start_docker_daemon

nvidia_smi_path() {
  if command -v nvidia-smi >/dev/null 2>&1; then command -v nvidia-smi; return 0; fi
  [[ -x /usr/lib/wsl/lib/nvidia-smi ]] && { printf '%s' /usr/lib/wsl/lib/nvidia-smi; return 0; }
  return 1
}

nvidia_runtime_ready() {
  local smi
  smi="$(nvidia_smi_path 2>/dev/null || true)"
  [[ -n "$smi" ]] || return 1
  timeout --foreground --kill-after=3s 10s "$smi" -L >/dev/null 2>&1 || return 1
  timeout --foreground --kill-after=3s 10s docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'
}

install_nvidia_container_toolkit_if_needed() {
  if nvidia_runtime_ready && [[ "$repair_root_refresh_needed" != true ]]; then return 0; fi
  local smi repo_stamp daemon_backup='' daemon_existed=false configured=false
  smi="$(nvidia_smi_path 2>/dev/null || true)"
  [[ -n "$smi" ]] || return 1
  timeout --foreground --kill-after=3s 10s "$smi" -L >/dev/null 2>&1 || return 1
  [[ "$(dpkg --print-architecture)" == amd64 ]] || return 1
  echo 'NVIDIA GPU support detected in WSL; configuring the official NVIDIA Container Toolkit for Docker.'
  repo_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  if [[ -e /etc/docker/daemon.json ]]; then
    daemon_existed=true
    daemon_backup="/etc/docker/daemon.json.latticevale-pre-$repo_stamp.bak"
    cp -a /etc/docker/daemon.json "$daemon_backup"
  fi
  local nvidia_toolkit_version='1.20.0-1'
  local -a nvidia_toolkit_packages=(
    nvidia-container-toolkit
    nvidia-container-toolkit-base
    libnvidia-container-tools
    libnvidia-container1
  )
  local toolkit_install_needed=false toolkit_has_newer=false toolkit_has_older=false toolkit_missing=false pkg installed_version
  for pkg in "${nvidia_toolkit_packages[@]}"; do
    installed_version="$(dpkg-query -W -f='${Version}' "$pkg" 2>/dev/null || true)"
    if [[ -z "$installed_version" ]]; then
      toolkit_missing=true
      toolkit_install_needed=true
      continue
    fi
    if dpkg --compare-versions "$installed_version" gt "$nvidia_toolkit_version"; then
      toolkit_has_newer=true
    elif dpkg --compare-versions "$installed_version" lt "$nvidia_toolkit_version"; then
      toolkit_has_older=true
      toolkit_install_needed=true
    fi
  done

  if [[ "$toolkit_has_newer" == true ]]; then
    if [[ "$toolkit_missing" == false && "$toolkit_has_older" == false ]] && command -v nvidia-ctk >/dev/null 2>&1; then
      echo "A complete NVIDIA Container Toolkit newer than LatticeVale's tested ${nvidia_toolkit_version} pin is already installed; preserving it and verifying the runtime instead of downgrading."
      toolkit_install_needed=false
    else
      echo "A mixed NVIDIA Container Toolkit installation contains package(s) newer than LatticeVale's tested ${nvidia_toolkit_version} pin plus missing/older components. LatticeVale will not downgrade the newer packages automatically. Align the NVIDIA Container Toolkit packages manually, or rerun with CPU acceleration." >&2
      return 1
    fi
  fi

  if [[ "$toolkit_install_needed" == true ]] || ! command -v nvidia-ctk >/dev/null 2>&1; then
    local source_path=/etc/apt/sources.list.d/nvidia-container-toolkit.list
    local key_path=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    local source_backup='' key_backup='' key_tmp='' list_tmp=''
    if [[ -e "$source_path" ]]; then
      source_backup="${source_path}.latticevale-pre-$repo_stamp.bak"
      cp -a "$source_path" "$source_backup" || return 1
    fi
    if [[ -e "$key_path" ]]; then
      key_backup="${key_path}.latticevale-pre-$repo_stamp.bak"
      cp -a "$key_path" "$key_backup" || return 1
    fi
    install -m 0755 -d /usr/share/keyrings || return 1
    key_tmp="$(mktemp)"; list_tmp="$(mktemp)"
    if ! curl -fsSL --connect-timeout 15 --max-time 120 --retry 3 --retry-delay 2 https://nvidia.github.io/libnvidia-container/gpgkey \
      | gpg --dearmor --yes -o "$key_tmp"; then
      rm -f "$key_tmp" "$list_tmp"
      echo 'NVIDIA Container Toolkit signing-key download/parse failed.' >&2
      return 1
    fi
    if ! curl -fsSL --connect-timeout 15 --max-time 120 --retry 3 --retry-delay 2 https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' > "$list_tmp"; then
      rm -f "$key_tmp" "$list_tmp"
      echo 'NVIDIA Container Toolkit repository metadata download failed.' >&2
      return 1
    fi
    [[ -s "$key_tmp" && -s "$list_tmp" ]] || { rm -f "$key_tmp" "$list_tmp"; echo 'NVIDIA Container Toolkit repository metadata was empty.' >&2; return 1; }
    if grep -Ev '^[[:space:]]*(#|$)' "$list_tmp" | grep -Ev '^deb([[:space:]]+\[[^]]+\])?[[:space:]]+https://nvidia\.github\.io/libnvidia-container/' >/dev/null; then
      rm -f "$key_tmp" "$list_tmp"
      echo 'NVIDIA Container Toolkit repository metadata referenced an unexpected package origin.' >&2
      return 1
    fi
    install -m 0644 "$key_tmp" "$key_path" || { rm -f "$key_tmp" "$list_tmp"; return 1; }
    install -m 0644 "$list_tmp" "$source_path" || { rm -f "$key_tmp" "$list_tmp"; return 1; }
    rm -f "$key_tmp" "$list_tmp"
    if ! apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update; then
      if [[ -n "$source_backup" && -f "$source_backup" ]]; then cp -a "$source_backup" "$source_path" || true; else rm -f "$source_path"; fi
      if [[ -n "$key_backup" && -f "$key_backup" ]]; then cp -a "$key_backup" "$key_path" || true; else rm -f "$key_path"; fi
      return 1
    fi
    # Install the complete tested package set only when doing so is an upgrade or
    # first install. A newer complete toolkit is preserved above, so no downgrade
    # permission is necessary or desirable here.
    if ! apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends \
      "nvidia-container-toolkit=${nvidia_toolkit_version}" \
      "nvidia-container-toolkit-base=${nvidia_toolkit_version}" \
      "libnvidia-container-tools=${nvidia_toolkit_version}" \
      "libnvidia-container1=${nvidia_toolkit_version}"; then
      if [[ -n "$source_backup" && -f "$source_backup" ]]; then cp -a "$source_backup" "$source_path" || true; else rm -f "$source_path"; fi
      if [[ -n "$key_backup" && -f "$key_backup" ]]; then cp -a "$key_backup" "$key_path" || true; else rm -f "$key_path"; fi
      return 1
    fi
  fi
  command -v nvidia-ctk >/dev/null 2>&1 || return 1
  nvidia-ctk runtime configure --runtime=docker && configured=true
  if [[ "$configured" == true ]]; then
    if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
      timeout --foreground --kill-after=10s 90s systemctl restart docker.service || true
    else
      timeout --foreground --kill-after=10s 90s service docker restart >/dev/null 2>&1 || true
    fi
    for _ in {1..30}; do timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1 && break; sleep 1; done
    nvidia_runtime_ready && return 0
  fi
  echo 'WARNING: NVIDIA Docker runtime verification failed; restoring the previous Docker daemon configuration.' >&2
  if [[ "$daemon_existed" == true && -n "$daemon_backup" && -f "$daemon_backup" ]]; then cp -a "$daemon_backup" /etc/docker/daemon.json
  else rm -f /etc/docker/daemon.json
  fi
  if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
    timeout --foreground --kill-after=10s 90s systemctl restart docker.service >/dev/null 2>&1 || true
  else
    timeout --foreground --kill-after=10s 90s service docker restart >/dev/null 2>&1 || true
  fi
  for _ in {1..30}; do timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1 && break; sleep 1; done
  return 1
}

if [[ "$local_ai_requested" == true && "$ollama_backend" == managed && "$ollama_acceleration" != cpu ]]; then
  if [[ "$ollama_acceleration" == nvidia ]]; then
    install_nvidia_container_toolkit_if_needed || { echo 'NVIDIA acceleration was explicitly selected but the NVIDIA Container Toolkit could not be configured/verified. No Linux NVIDIA display driver was installed. Fix Windows/WSL GPU support or rerun with Auto/CPU.' >&2; exit 5; }
  elif [[ "$ollama_acceleration" == auto ]]; then
    if nvidia_smi_path >/dev/null 2>&1; then
      install_nvidia_container_toolkit_if_needed || echo 'WARNING: NVIDIA GPU was detected, but the Docker NVIDIA runtime could not be configured. Auto mode will fall back to another supported accelerator or CPU.' >&2
    fi
  fi
fi

# A single root helper gives Windows auto-start and older non-systemd WSL2 builds the
# same reliable startup path. The user can also run it manually with sudo after wsl --shutdown.
printf -v stack_user_q '%q' "$linux_user"
printf -v stack_home_q '%q' "$user_home"
printf -v stack_dir_q '%q' "$stack_dir"
cat > /usr/local/sbin/hermes-stack-start <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
export DOCKER_HOST=unix:///var/run/docker.sock
stack_user=$stack_user_q
stack_home=$stack_home_q
stack_dir=$stack_dir_q
if ! timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1; then
  if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
    timeout --foreground --kill-after=10s 90s systemctl start docker.service
  elif command -v service >/dev/null 2>&1; then
    timeout --foreground --kill-after=10s 90s service docker start >/dev/null 2>&1 || true
  fi
fi
for _ in {1..20}; do timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1 && break; sleep 1; done
if ! timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1; then
  nohup dockerd >/var/log/hermes-dockerd.log 2>&1 </dev/null &
  for _ in {1..30}; do timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1 && break; sleep 1; done
fi
timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1 || { echo 'Docker daemon could not be started.' >&2; exit 1; }
# Refresh adaptive ceilings only when that policy is enabled and the WSL-visible
# CPU/RAM fingerprint changed. A routine start must not rewrite Compose state needlessly.
resource_limits_enabled="$(python3 - "\$stack_dir/install-options.json" <<'PY_RESOURCE_ENABLED'
import json,sys
try:
    d=json.load(open(sys.argv[1],encoding='utf-8'))
    print('true' if d.get('containerResourceLimits') is True else 'false')
except Exception:
    print('false')
PY_RESOURCE_ENABLED
)"
if [[ "\$resource_limits_enabled" == true ]]; then
  current_cpus="$(nproc 2>/dev/null || true)"
  current_mem_mib="$(awk '/^MemTotal:/ {print int($2/1024); exit}' /proc/meminfo 2>/dev/null || true)"
  if [[ -s "\$stack_dir/.latticevale-resource-state" ]]; then
    saved_version="$(sed -n 's/^POLICY_VERSION=//p' "\$stack_dir/.latticevale-resource-state" 2>/dev/null | head -n1 || true)"
    saved_cpus="$(sed -n 's/^CPUS=//p' "\$stack_dir/.latticevale-resource-state" 2>/dev/null | head -n1 || true)"
    saved_mem="$(sed -n 's/^MEM_MIB=//p' "\$stack_dir/.latticevale-resource-state" 2>/dev/null | head -n1 || true)"
  else
    saved_version=''
    saved_cpus=''
    saved_mem=''
  fi
  if [[ "\$saved_version" != 2 || "\$saved_cpus" != "\$current_cpus" || "\$saved_mem" != "\$current_mem_mib" ]]; then
    runuser -u "\$stack_user" -- env HOME="\$stack_home" USER="\$stack_user" DOCKER_HOST=unix:///var/run/docker.sock \
      bash -c 'cd "\$1" && ./configure-stack.sh --refresh-resource-policy' bash "\$stack_dir" || { echo 'Could not refresh LatticeVale adaptive resource policy.' >&2; exit 1; }
  fi
fi
if [[ -s "\$stack_dir/.windows-native-info" ]]; then
  native_transport="\$(sed -n 's/^TRANSPORT=//p' "\$stack_dir/.windows-native-info" | head -n1 | tr -d '\r')"
  native_task="\$(sed -n 's/^BRIDGE_TASK_NAME=//p' "\$stack_dir/.windows-native-info" | head -n1 | tr -d '\r')"
  native_port="\$(sed -n 's/^BRIDGE_PORT=//p' "\$stack_dir/.windows-native-info" | head -n1 | tr -d '\r')"
  native_host_address="\$(sed -n 's/^HOST_ADDRESS=//p' "\$stack_dir/.windows-native-info" | head -n1 | tr -d '\r')"
  [[ -n "\$native_transport" ]] || native_transport=windows-gateway-relay
  [[ "\$native_port" =~ ^[0-9]+\$ ]] || { echo 'Native Windows Ollama bridge metadata is invalid; rerun the Windows installer.' >&2; exit 1; }
  case "\$native_transport" in
    wsl-localhost-relay|wsl-host-relay)
      rm -f "\$stack_dir/.native-ollama-relay.disabled"
      if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1 && systemctl cat latticevale-native-ollama-relay.service >/dev/null 2>&1; then
        systemctl restart latticevale-native-ollama-relay.service >/dev/null 2>&1 || true
      fi
      runuser -u "\$stack_user" -- env HOME="\$stack_home" USER="\$stack_user" DOCKER_HOST=unix:///var/run/docker.sock \
        bash -c 'cd "\$1" && ./native-ollama-relay.sh start >/dev/null' bash "\$stack_dir" || { echo 'Could not start the supervised WSL-local native Ollama relay.' >&2; exit 1; }
      native_host="\$(runuser -u "\$stack_user" -- env HOME="\$stack_home" USER="\$stack_user" DOCKER_HOST=unix:///var/run/docker.sock \
        bash -c 'cd "\$1" && ./native-ollama-relay.sh host' bash "\$stack_dir")"
      ;;
    windows-gateway-relay)
      [[ -n "\$native_task" ]] || { echo 'Native Windows Ollama Windows-relay task metadata is invalid; rerun the Windows installer.' >&2; exit 1; }
      if command -v schtasks.exe >/dev/null 2>&1; then
        schtasks.exe /End /TN "\$native_task" >/dev/null 2>&1 || true
        sleep 1
        rm -f "\$stack_dir/.windows-native-host-ip"
        schtasks.exe /Run /TN "\$native_task" >/dev/null 2>&1 || { echo 'Could not start the LatticeVale native Windows Ollama bridge task.' >&2; exit 1; }
        for _ in {1..20}; do [[ -s "\$stack_dir/.windows-native-host-ip" ]] && break; sleep 0.25; done
      else
        echo 'Windows Task Scheduler interop is unavailable; native Windows Ollama cannot be linked from this WSL session.' >&2
        exit 1
      fi
      native_host="\$native_host_address"
      if [[ -s "\$stack_dir/.windows-native-host-ip" ]]; then
        refreshed_host="\$(head -n1 "\$stack_dir/.windows-native-host-ip" | tr -d '\r\n')"
        [[ "\$refreshed_host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\$ ]] && native_host="\$refreshed_host"
      fi
      [[ "\$native_host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\$ ]] || { echo 'Native Windows Ollama host-address metadata is invalid; rerun the Windows installer.' >&2; exit 1; }
      ;;
    *) echo "Unsupported native Windows Ollama transport '\$native_transport'; rerun the Windows installer." >&2; exit 1 ;;
  esac
  [[ -n "\$native_host" ]] || { echo 'Could not resolve a Docker-reachable host address for native Ollama.' >&2; exit 1; }
  python3 - "\$stack_dir/.env" "\$native_host" <<'PY_NATIVE_ENV'
from pathlib import Path
import sys
p=Path(sys.argv[1]); value=sys.argv[2]
lines=p.read_text(encoding='utf-8').splitlines() if p.exists() else []
out=[]; done=False
for line in lines:
    if line.startswith('WINDOWS_HOST_IP='):
        if not done: out.append('WINDOWS_HOST_IP='+value); done=True
    else: out.append(line)
if not done: out.append('WINDOWS_HOST_IP='+value)
p.write_text('\n'.join(out)+'\n',encoding='utf-8')
PY_NATIVE_ENV
  native_ready=false
  for _ in {1..30}; do
    if curl -fsS --noproxy '*' --connect-timeout 2 --max-time 4 "http://\${native_host}:\${native_port}/api/version" >/dev/null 2>&1; then native_ready=true; break; fi
    sleep 1
  done
  [[ "\$native_ready" == true ]] || { echo 'Native Windows Ollama relay did not become reachable from WSL.' >&2; exit 1; }
fi
started=false
for attempt in 1 2 3; do
  if runuser -u "\$stack_user" -- env -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH -u DOCKER_API_VERSION \
    DOCKER_HOST=unix:///var/run/docker.sock HOME="\$stack_home" USER="\$stack_user" \
    bash -c 'cd "\$1" && timeout --foreground --kill-after=10s 240s docker compose up -d --pull never --no-build' bash "\$stack_dir"; then
    started=true
    break
  fi
  echo "LatticeVale stack auto-start attempt \$attempt failed; retrying." >&2
  sleep 5
done
[[ "\$started" == true ]] || { echo 'LatticeVale stack could not be started after three attempts.' >&2; exit 1; }
EOF
chmod 0755 /usr/local/sbin/hermes-stack-start

# When this WSL distro already runs systemd, let systemd supervise the WSL-local
# native Ollama relay. Do not enable systemd or alter /etc/wsl.conf here: systemd
# support is a distro/WSL policy choice. Non-systemd environments retain the
# relay helper's built-in watchdog fallback.
relay_unit=/etc/systemd/system/latticevale-native-ollama-relay.service
if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1 && [[ "$ollama_backend" == windows-native ]] && [[ "$ollama_transport" == wsl-localhost-relay || "$ollama_transport" == wsl-host-relay ]]; then
  cat > "$relay_unit" <<EOF_RELAY_UNIT
[Unit]
Description=LatticeVale WSL-local native Ollama relay supervisor
After=docker.service network.target
Wants=docker.service
StartLimitIntervalSec=60
StartLimitBurst=10

[Service]
Type=simple
User=$linux_user
WorkingDirectory=$stack_dir
Environment=HOME=$user_home
Environment=DOCKER_HOST=unix:///var/run/docker.sock
ExecStart=/bin/bash $stack_dir/native-ollama-relay.sh supervise
Restart=on-failure
RestartSec=2s

[Install]
WantedBy=multi-user.target
EOF_RELAY_UNIT
  chmod 0644 "$relay_unit"
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable latticevale-native-ollama-relay.service >/dev/null 2>&1 || true
elif [[ -f "$relay_unit" ]] && grep -Fq "$stack_dir/native-ollama-relay.sh" "$relay_unit" 2>/dev/null; then
  systemctl disable --now latticevale-native-ollama-relay.service >/dev/null 2>&1 || true
  rm -f "$relay_unit"
  systemctl daemon-reload >/dev/null 2>&1 || true
fi

unattended="$(jq -r '.unattendedUpdates // true' "$tmp_options")"
legacy_periodic=/etc/apt/apt.conf.d/20auto-upgrades
hermes_periodic=/etc/apt/apt.conf.d/52hermes-unattended-upgrades
# v13.10 migration: older builds wrote Ubuntu's generic 20auto-upgrades file.
# Remove it only when its bytes exactly match the legacy installer-owned content;
# never overwrite or remove an administrator's customized APT policy.
legacy_expected="$(mktemp)"
cat > "$legacy_expected" <<'CFG'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CFG
if [[ -f "$legacy_periodic" ]] && cmp -s "$legacy_periodic" "$legacy_expected"; then
  rm -f "$legacy_periodic"
fi
rm -f "$legacy_expected"

if [[ "$unattended" == true ]]; then
  if [[ "$repair_root_refresh_needed" == true ]] || ! dpkg-query -W -f='${Status}' unattended-upgrades 2>/dev/null | grep -qx 'install ok installed'; then
    [[ "$repair_root_refresh_needed" == true ]] || apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
    apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends unattended-upgrades
  fi
  cat > "$hermes_periodic" <<'CFG'
// Installer-owned policy. Do not put local administrator policy in this file.
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";
CFG
  chmod 0644 "$hermes_periodic"
  if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now unattended-upgrades
  else
    if [[ "$repair_root_refresh_needed" == true ]] || ! dpkg-query -W -f='${Status}' cron 2>/dev/null | grep -qx 'install ok installed'; then
      [[ "$repair_root_refresh_needed" == true ]] || apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
      apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends cron
    fi
    service cron start >/dev/null 2>&1 || true
  fi
else
  # Removing the installer-owned periodic policy is sufficient to disable the
  # Hermes-managed schedule. Do not disable Ubuntu's global service: another
  # administrator/package policy may legitimately use it.
  rm -f "$hermes_periodic"
fi

if [[ "$repair_root_refresh_needed" == true ]]; then
  # Root package work is complete. Persist a tiny owner-writable handoff so the user-level
  # configure stage refreshes the selected current Compose images/builds before this
  # periodic maintenance cycle is considered complete. If a later stage is interrupted,
  # Resume / repair continues the image half without repeating completed root package work.
  printf 'POLICY_REVISION=%s\n' "$repair_refresh_revision" > "$repair_refresh_pending_file"
  chown "$linux_uid:$linux_gid" "$repair_refresh_pending_file"
  chmod 0600 "$repair_refresh_pending_file"
  repair_refresh_pending=true
fi

# Repair only trees that are intentionally owned/written by the selected Ubuntu UID/GID.
# Never recursively chown database/model trees: Postgres and Ollama legitimately maintain
# container-owned files under data/synapse-db, data/honcho-db, and data/ollama.
repair_user_tree() {
  local rel="$1" path="$stack_dir/$1"
  [[ -e "$path" || -L "$path" ]] || return 0
  if [[ -L "$path" ]]; then
    echo "Unsafe installer-owned path: '$path' is a symbolic link. Repair it manually before continuing." >&2
    return 1
  fi
  if mountpoint -q -- "$path" 2>/dev/null; then
    echo "Unsafe installer-owned path: '$path' is a mountpoint. LatticeVale will not recursively change ownership across an external mount." >&2
    return 1
  fi
  chown -hR -P --preserve-root "$linux_uid:$linux_gid" "$path"
  chmod -R u+rwX "$path"
}

install -d -m 0700 -o "$linux_uid" -g "$linux_gid" "$stack_dir"
for managed_parent in config data; do
  managed_path="$stack_dir/$managed_parent"
  if [[ -e "$managed_path" && -L "$managed_path" ]]; then
    echo "Unsafe installer $managed_parent path: '$managed_path' is a symbolic link." >&2
    exit 2
  fi
  if [[ -e "$managed_path" ]] && mountpoint -q -- "$managed_path" 2>/dev/null; then
    echo "Unsafe installer $managed_parent path: '$managed_path' is an external mountpoint. LatticeVale expects managed service state on the distro's Linux filesystem." >&2
    exit 2
  fi
done
unset managed_parent managed_path
install -d -m 0750 -o "$linux_uid" -g "$linux_gid" "$stack_dir/data"

for rel in backups secrets logs vendor data/hermes data/qmd data/synapse data/searxng-valkey data/honcho-redis; do
  repair_user_tree "$rel"
done
# User content is part of the selected stack and Hermes writes it as STACK_UID/GID.
# When native Windows Obsidian integration is selected, Docker mounts the Windows vault
# directly. Never recursively chown/chmod a host vault even if a stale external mount has
# somehow survived an interrupted older repair.
repair_user_tree workspace
if [[ "$obsidian_selected" != true ]]; then
  repair_user_tree vault
fi
# Honcho config is installer-authored and read-only in its container. SearXNG may create
# additional container-owned helper files, so normalize only the directory and settings.yml.
repair_user_tree config/honcho
install -d -m 0755 -o "$linux_uid" -g "$linux_gid" "$stack_dir/config" "$stack_dir/config/searxng"
if [[ -f "$stack_dir/config/searxng/settings.yml" && ! -L "$stack_dir/config/searxng/settings.yml" ]]; then
  chown "$linux_uid:$linux_gid" "$stack_dir/config/searxng/settings.yml"
  chmod u+rw "$stack_dir/config/searxng/settings.yml"
fi

# Restore private modes without taking write access away from the selected owner.
if [[ -d "$stack_dir/secrets" ]]; then
  find -P "$stack_dir/secrets" -type d -exec chmod 0700 {} +
  find -P "$stack_dir/secrets" -type f -exec chmod 0600 {} +
fi
if [[ -d "$stack_dir/logs" ]]; then
  find -P "$stack_dir/logs" -type d -exec chmod 0700 {} +
  find -P "$stack_dir/logs" -type f -exec chmod 0600 {} +
fi
if [[ -d "$stack_dir/backups" ]]; then
  chmod -R u+rwX,go-rwx "$stack_dir/backups"
fi
[[ -d "$stack_dir/data/hermes" ]] && chmod 0700 "$stack_dir/data/hermes"
[[ -d "$stack_dir/data/synapse" ]] && chmod 0700 "$stack_dir/data/synapse"
[[ -d "$stack_dir/data/qmd" ]] && chmod 0750 "$stack_dir/data/qmd"

# Root-assisted recovery also normalizes installer metadata that a failed older build may
# have left root-owned. These files are intended to remain writable by the selected user.
for rel in .env .installer-state.json .install-info .configured .repair-package-refresh .repair-package-refresh-pending .matrix-info .matrix-configured .tailscale-info .windows-native-info .installer-managed-profiles install-options.json; do
  path="$stack_dir/$rel"
  if [[ -f "$path" && ! -L "$path" ]]; then
    chown "$linux_uid:$linux_gid" "$path"
    chmod u+rw "$path"
  fi
done
unset rel path

# The installer owns only these support files. Never recursively chown the whole stack on a
# rerun: Postgres/Synapse/Honcho database and Ollama model bind mounts stay container-owned.
# Refuse replacement symlinks before root writes installer-controlled files; otherwise a broken
# or hostile prior install could redirect a repair write outside the dedicated stack tree.
installer_owned_files=(
  compose.yaml Dockerfile.qmd patch-qmd-bind.py configure-stack.sh manage.sh state-audit.py
  qmd-index-cycle.sh native-ollama-relay.py native-ollama-relay.sh install-options.json
)
for rel in "${installer_owned_files[@]}"; do
  if [[ -L "$stack_dir/$rel" ]]; then
    echo "Unsafe installer-owned file: '$stack_dir/$rel' is a symbolic link. Replace it with a regular file or remove it before continuing." >&2
    exit 2
  fi
done
unset installer_owned_files rel

install -m 0644 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/compose.yaml" "$stack_dir/compose.yaml"
install -m 0644 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/Dockerfile.qmd" "$stack_dir/Dockerfile.qmd"
install -m 0644 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/patch-qmd-bind.py" "$stack_dir/patch-qmd-bind.py"
install -m 0755 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/configure-stack.sh" "$stack_dir/configure-stack.sh"
install -m 0755 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/manage.sh" "$stack_dir/manage.sh"
install -m 0755 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/state-audit.py" "$stack_dir/state-audit.py"
install -m 0755 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/qmd-index-cycle.sh" "$stack_dir/qmd-index-cycle.sh"
install -m 0755 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/native-ollama-relay.py" "$stack_dir/native-ollama-relay.py"
install -m 0755 -o "$linux_uid" -g "$linux_gid" \
  "$bundle_root/stack/native-ollama-relay.sh" "$stack_dir/native-ollama-relay.sh"
install -m 0600 -o "$linux_uid" -g "$linux_gid" "$tmp_options" "$stack_dir/install-options.json"
rm -f "$tmp_options"
trap - EXIT

# Fail early with a useful path instead of letting a later Python/Docker command surface an
# opaque EACCES. Only paths that the selected user/UID-mapped containers are expected to
# write are tested; database/model paths owned by their containers are intentionally absent.
verify_write_dirs=(
  "$stack_dir" "$stack_dir/data" "$stack_dir/config" "$stack_dir/config/searxng"
  "$stack_dir/backups" "$stack_dir/secrets" "$stack_dir/logs" "$stack_dir/vendor"
  "$stack_dir/workspace" "$stack_dir/data/hermes" "$stack_dir/data/qmd"
  "$stack_dir/data/qmd/config" "$stack_dir/data/qmd/cache" "$stack_dir/data/synapse"
  "$stack_dir/data/searxng-valkey" "$stack_dir/data/honcho-redis"
)
[[ "$obsidian_selected" == true ]] || verify_write_dirs+=("$stack_dir/vault")
verify_write_files=(
  "$stack_dir/compose.yaml" "$stack_dir/Dockerfile.qmd" "$stack_dir/patch-qmd-bind.py"
  "$stack_dir/configure-stack.sh" "$stack_dir/manage.sh" "$stack_dir/state-audit.py"
  "$stack_dir/qmd-index-cycle.sh" "$stack_dir/native-ollama-relay.py" "$stack_dir/native-ollama-relay.sh" "$stack_dir/install-options.json" "$stack_dir/.env"
  "$stack_dir/.repair-package-refresh" "$stack_dir/.repair-package-refresh-pending"
  "$stack_dir/.installer-state.json" "$stack_dir/.install-info" "$stack_dir/.configured"
  "$stack_dir/.matrix-info" "$stack_dir/.matrix-configured" "$stack_dir/.tailscale-info" "$stack_dir/.windows-native-info"
  "$stack_dir/.installer-managed-profiles" "$stack_dir/data/hermes/config.yaml"
  "$stack_dir/data/hermes/.env"
)
verify_selected_user_writable() {
  runuser -u "$linux_user" -- env HOME="$user_home" USER="$linux_user" python3 - \
    "${#verify_write_dirs[@]}" "${verify_write_dirs[@]}" "${verify_write_files[@]}" <<'PY_WRITABLE'
import os,sys
ndir=int(sys.argv[1])
dirs=sys.argv[2:2+ndir]
files=sys.argv[2+ndir:]
bad=[]
for raw in dirs:
    if not os.path.exists(raw):
        continue
    if os.path.islink(raw) or not os.path.isdir(raw) or not os.access(raw, os.W_OK | os.X_OK):
        bad.append(raw)
for raw in files:
    if not os.path.exists(raw):
        continue
    if os.path.islink(raw) or not os.path.isfile(raw) or not os.access(raw, os.W_OK):
        bad.append(raw)
if bad:
    print('Selected Ubuntu user cannot write required installer paths:', file=sys.stderr)
    for path in bad:
        print('  - '+path, file=sys.stderr)
    raise SystemExit(1)
PY_WRITABLE
}

verify_selected_user_writable

runuser --pty -u "$linux_user" -- env HOME="$user_home" USER="$linux_user" bash "$stack_dir/configure-stack.sh"

# A container entrypoint must not be allowed to make a successful fresh install unrepairable.
# Reclaim only the roots/files that LatticeVale deliberately owns after the services have started.
# Database/model trees (synapse-db, honcho-db, ollama) remain container-owned and are excluded.
for path in "${verify_write_dirs[@]}"; do
  [[ -d "$path" && ! -L "$path" ]] || continue
  chown "$linux_uid:$linux_gid" "$path"
  chmod u+rwx "$path"
done
for path in "${verify_write_files[@]}"; do
  [[ -f "$path" && ! -L "$path" ]] || continue
  chown "$linux_uid:$linux_gid" "$path"
  chmod u+rw "$path"
done
# SearXNG historically defaults to taking ownership of /etc/searxng. Compose now disables
# that behavior, and this one-time post-service reconciliation repairs older partial installs.
if [[ -f "$stack_dir/config/searxng/settings.yml" && ! -L "$stack_dir/config/searxng/settings.yml" ]]; then
  chown "$linux_uid:$linux_gid" "$stack_dir/config/searxng/settings.yml"
  chmod u+rw "$stack_dir/config/searxng/settings.yml"
fi
verify_selected_user_writable
unset verify_write_dirs verify_write_files

echo "Docker and the LatticeVale stack are installed at $stack_dir."
