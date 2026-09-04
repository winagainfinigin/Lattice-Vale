#!/usr/bin/env bash
set -Eeuo pipefail

# LatticeVale explicit cleanup maintenance.
# This script is intentionally narrower than Docker/system pruning. It never removes
# containers, networks, volumes, tagged images, persistent application data, user-created
# backups, Ollama models, Matrix/Honcho databases, Hermes state, QMD state, vault/workspace
# files, credentials, or the WSL VHDX itself.

STACK="${1:-}"
SCOPES_CSV="${2:-}"

fail() {
  printf 'LATTICEVALE_CLEANUP_FAILED detail=%s\n' "$*" >&2
  exit 2
}

[[ $(id -u) -eq 0 ]] || fail 'cleanup must run as WSL root'
[[ -n "$STACK" && "$STACK" == /* && -d "$STACK" ]] || fail "managed stack path is missing or invalid: ${STACK:-<empty>}"
[[ -n "$SCOPES_CSV" ]] || fail 'no cleanup scopes were selected'

STACK_REAL="$(readlink -f -- "$STACK" 2>/dev/null || true)"
[[ -n "$STACK_REAL" && "$STACK_REAL" == "$STACK" ]] || fail 'managed stack path must resolve to itself; symlinked stack roots are refused'
cd -- "$STACK"

# Option 7 is only for a currently recognizable managed install. Refuse cleanup if the
# active intent/state files are missing or symlinked, because pre-update backups can be a
# recovery authority when those files are damaged.
for required in install-options.json .installer-state.json compose.yaml; do
  [[ -f "$required" && ! -L "$required" ]] || fail "current managed-state file is missing or unsafe: $required"
done
python3 - <<'PY_VALIDATE'
import json
from pathlib import Path
for name in ('install-options.json', '.installer-state.json'):
    p=Path(name)
    try:
        obj=json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        raise SystemExit(f'{name} is not valid JSON: {exc}')
    if not isinstance(obj, dict):
        raise SystemExit(f'{name} must contain a JSON object')
if not json.loads(Path('install-options.json').read_text(encoding='utf-8')).get('installerVersion'):
    raise SystemExit('install-options.json has no installerVersion; refusing cleanup')
PY_VALIDATE

IFS=',' read -r -a REQUESTED <<< "$SCOPES_CSV"
declare -A WANT=()
for scope in "${REQUESTED[@]}"; do
  case "$scope" in
    preupdate-backups|staging|apt-cache|docker-dangling|docker-build-cache|trim-root)
      WANT["$scope"]=1
      ;;
    *) fail "unknown cleanup scope: $scope" ;;
  esac
done

bytes_human() {
  python3 - "$1" <<'PY_BYTES'
import sys
try: n=float(sys.argv[1])
except Exception: n=0
units=['B','KiB','MiB','GiB','TiB']; i=0
while n>=1024 and i<len(units)-1:
    n/=1024; i+=1
print(f'{n:.1f} {units[i]}')
PY_BYTES
}

path_bytes() {
  local p="$1" n
  [[ -e "$p" ]] || { echo 0; return 0; }
  n="$(du -sb -- "$p" 2>/dev/null | awk '{print $1}' || true)"
  [[ "$n" =~ ^[0-9]+$ ]] || n=0
  echo "$n"
}

root_free_bytes() {
  df -Pk / 2>/dev/null | awk 'NR==2 {print $4*1024}'
}

valid_preupdate_backup() {
  local d="$1" base info
  [[ -d "$d" && ! -L "$d" ]] || return 1
  base="$(basename -- "$d")"
  [[ "$base" =~ ^pre-update-[0-9]{8}T[0-9]{6}Z-[0-9]+$ ]] || return 1
  info="$d/BACKUP-INFO.txt"
  [[ -f "$info" && ! -L "$info" ]] || return 1
  [[ "$(head -n 1 -- "$info" 2>/dev/null || true)" == 'LatticeVale pre-update safety backup' ]] || return 1
  grep -Fxq -- "stack=$STACK" "$info" 2>/dev/null || return 1
  return 0
}

show_state() {
  local free backups
  free="$(root_free_bytes 2>/dev/null || echo 0)"
  backups="$(path_bytes backups)"
  echo "WSL root free space: $(bytes_human "${free:-0}")"
  echo "LatticeVale backups directory: $(bytes_human "$backups")"
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo 'Docker storage summary:'
    docker system df 2>/dev/null || true
  else
    echo 'Docker daemon unavailable; Docker cleanup scopes will be skipped safely.'
  fi
}

echo '=== LatticeVale cleanup / reclaim disk space ==='
echo "Stack: $STACK"
echo "Selected scopes: ${REQUESTED[*]}"
echo 'Safety boundary: persistent data, Docker volumes/containers/networks/tagged images, configured models, and user backups are not cleanup targets.'
echo
echo '--- BEFORE ---'
show_state

if [[ -n "${WANT[preupdate-backups]:-}" ]]; then
  echo
  echo '--- LatticeVale Option 6 pre-update safety backups ---'
  removed=0
  reclaimed=0
  while IFS= read -r -d '' d; do
    if valid_preupdate_backup "$d"; then
      n="$(path_bytes "$d")"
      echo "Removing verified installer-created pre-update backup: $d ($(bytes_human "$n"))"
      rm -rf --one-file-system -- "$d"
      removed=$((removed+1))
      reclaimed=$((reclaimed+n))
    else
      echo "Preserved unverified backup-like directory: $d"
    fi
  done < <(find backups -mindepth 1 -maxdepth 1 -type d -name 'pre-update-*' -print0 2>/dev/null || true)
  echo "Verified pre-update backups removed: $removed; nominal contents removed: $(bytes_human "$reclaimed")"
fi

if [[ -n "${WANT[staging]:-}" ]]; then
  echo
  echo '--- Disposable LatticeVale staging residue ---'
  removed=0
  while IFS= read -r -d '' d; do
    [[ -d "$d" && ! -L "$d" ]] || continue
    uid="$(stat -c '%u' -- "$d" 2>/dev/null || echo -1)"
    [[ "$uid" == 0 ]] || { echo "Preserved non-root staging-like directory: $d"; continue; }
    echo "Removing stale root-owned installer staging directory: $d"
    rm -rf --one-file-system -- "$d"
    removed=$((removed+1))
  done < <(
    find /tmp -mindepth 1 -maxdepth 1 -type d \
      \( -name 'latticevale-installer-*' -o -name 'latticevale-audit-*' -o -name 'latticevale-preupdate-*' -o -name 'hermes-installer-*' -o -name 'hermes-audit-*' \) \
      -mmin +60 -print0 2>/dev/null || true
  )
  while IFS= read -r -d '' d; do
    [[ -d "$d" && ! -L "$d" ]] || continue
    base="$(basename -- "$d")"
    [[ "$base" =~ ^pre-update-[0-9]{8}T[0-9]{6}Z-[0-9]+\.partial$ ]] || continue
    echo "Removing incomplete pre-update backup residue: $d"
    rm -rf --one-file-system -- "$d"
    removed=$((removed+1))
  done < <(find backups -mindepth 1 -maxdepth 1 -type d -name 'pre-update-*.partial' -mmin +60 -print0 2>/dev/null || true)
  echo "Disposable staging entries removed: $removed"
fi

if [[ -n "${WANT[apt-cache]:-}" ]]; then
  echo
  echo '--- APT downloaded-package cache ---'
  before="$(path_bytes /var/cache/apt/archives)"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get clean
    after="$(path_bytes /var/cache/apt/archives)"
    echo "APT cache before: $(bytes_human "$before"); after: $(bytes_human "$after")"
  else
    echo 'apt-get is unavailable; skipped.'
  fi
fi

if [[ -n "${WANT[docker-dangling]:-}" ]]; then
  echo
  echo '--- Docker dangling images only ---'
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    # Deliberately no -a: Docker documents the default as dangling images only.
    # A dangling image is untagged and not referenced by a container.
    docker image prune -f
  else
    echo 'Docker daemon unavailable; skipped dangling-image cleanup.'
  fi
fi

if [[ -n "${WANT[docker-build-cache]:-}" ]]; then
  echo
  echo '--- Docker dangling build cache only ---'
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    # Deliberately no --all/-a. This explicit maintenance action removes only the
    # default builder's dangling cache and cannot remove runtime containers, volumes,
    # networks, tagged images, or persistent LatticeVale application data.
    docker builder prune -f
  else
    echo 'Docker daemon unavailable; skipped build-cache cleanup.'
  fi
fi

if [[ -n "${WANT[trim-root]:-}" ]]; then
  echo
  echo '--- WSL root filesystem TRIM ---'
  if command -v fstrim >/dev/null 2>&1; then
    if ! fstrim -v /; then
      echo 'Root filesystem TRIM is unsupported or unavailable on this WSL storage; no filesystem data was changed.' >&2
    fi
  else
    echo 'fstrim is unavailable; skipped.'
  fi
fi

echo
echo '--- AFTER ---'
show_state
cat <<'EOF_NOTE'

Cleanup completed without deleting LatticeVale runtime containers, Docker volumes or networks,
tagged images, Hermes/Matrix/Honcho/QMD/Ollama persistent data, vault/workspace files, credentials,
or user-created backups. Deleting files inside WSL may not immediately reduce the Windows-side
VHDX file size on every WSL/storage configuration; Option 7 deliberately does not resize, move,
mount, or compact the VHDX itself.
EOF_NOTE
