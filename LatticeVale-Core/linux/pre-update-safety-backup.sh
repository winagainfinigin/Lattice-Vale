#!/usr/bin/env bash
set -Eeuo pipefail

# Bundle-owned pre-install safety backup for LatticeVale existing-stack changes.
# This deliberately does not call the currently installed manage.sh: repair
# must remain able to repair a broken/outdated management script.

STACK="${1:-}"
OWNER_UID="${2:-}"
OWNER_GID="${3:-}"
[[ -n "$STACK" && "$STACK" == /* && -d "$STACK" ]] || {
  echo "PREUPDATE_BACKUP_FAILED step=validate-stack detail=managed stack path is missing or invalid: ${STACK:-<empty>}" >&2
  exit 2
}
if [[ -n "$OWNER_UID$OWNER_GID" ]]; then
  [[ "$OWNER_UID" =~ ^[0-9]+$ && "$OWNER_GID" =~ ^[0-9]+$ ]] || {
    echo "PREUPDATE_BACKUP_FAILED step=validate-owner detail=owner UID/GID must be numeric when supplied: ${OWNER_UID:-<empty>}:${OWNER_GID:-<empty>}" >&2
    exit 2
  }
fi
if [[ $(id -u) -ne 0 ]]; then
  echo "PREUPDATE_BACKUP_FAILED step=validate-privilege detail=bundle-owned pre-update backup must run as WSL root so container-owned persistent files can be read safely" >&2
  exit 2
fi
cd -- "$STACK"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
TARGET="$STACK/backups/pre-update-$STAMP"
TMP_TARGET="$TARGET.partial"
STEP=initialize
BACKUP_COMPLETE=false
RESTORE_NEEDED=false
COMPOSE_AVAILABLE=false
RUNNING_SERVICES=()
COMPOSE_LOG="$(mktemp /tmp/latticevale-preupdate-compose.XXXXXX)"

report_progress() {
  printf 'LV_PROGRESS|%s|%s\n' "$1" "$2"
}

human_bytes() {
  awk -v bytes="${1:-0}" 'BEGIN {split("B KiB MiB GiB TiB",u," "); i=1; while (bytes>=1024 && i<5) {bytes/=1024; i++} printf "%.1f %s",bytes,u[i]}'
}

wait_with_progress() {
  local pid="$1" percent="$2" label="$3" output_path="${4:-}" started="$SECONDS" elapsed bytes
  while kill -0 "$pid" 2>/dev/null; do
    sleep 5
    kill -0 "$pid" 2>/dev/null || break
    elapsed=$((SECONDS-started))
    bytes=0
    [[ -n "$output_path" && -f "$output_path" ]] && bytes="$(stat -c '%s' -- "$output_path" 2>/dev/null || echo 0)"
    report_progress "$percent" "$label; ${elapsed}s elapsed$(if [[ -n "$output_path" ]]; then printf '; %s written' "$(human_bytes "$bytes")"; fi)"
  done
  wait "$pid"
}

safe_restore() {
  local rc=0
  if [[ "$RESTORE_NEEDED" == true && ${#RUNNING_SERVICES[@]} -gt 0 && "$COMPOSE_AVAILABLE" == true ]]; then
    echo "Restoring previously running LatticeVale containers: ${RUNNING_SERVICES[*]}"
    : > "$COMPOSE_LOG"
    if ! docker compose start "${RUNNING_SERVICES[@]}" >"$COMPOSE_LOG" 2>&1; then
      echo "PREUPDATE_BACKUP_RESTORE_FAILED services=${RUNNING_SERVICES[*]}" >&2
      tail -n 12 "$COMPOSE_LOG" >&2 || true
      rc=1
    fi
    RESTORE_NEEDED=false
  fi
  return "$rc"
}

on_exit() {
  local rc=$?
  set +e
  local restore_rc=0
  safe_restore || restore_rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "PREUPDATE_BACKUP_FAILED step=$STEP exit=$rc partial=$TMP_TARGET" >&2
  elif [[ $restore_rc -ne 0 ]]; then
    echo "PREUPDATE_BACKUP_FAILED step=restore-services exit=$restore_rc backup=$TARGET" >&2
    rc=$restore_rc
  fi
  if [[ $rc -ne 0 && "$BACKUP_COMPLETE" != true ]]; then
    rm -rf -- "$TMP_TARGET" 2>/dev/null || true
  fi
  rm -f -- "$COMPOSE_LOG" 2>/dev/null || true
  exit "$rc"
}
trap on_exit EXIT
trap 'rc=$?; echo "PREUPDATE_BACKUP_ERROR step=$STEP line=$LINENO exit=$rc" >&2; exit "$rc"' ERR

STEP=create-target
report_progress 2 'Preparing verified pre-install backup'
install -d -m 0700 -- "$STACK/backups"
rm -rf -- "$TMP_TARGET"
install -d -m 0700 -- "$TMP_TARGET"
echo "Pre-update safety backup destination: $TARGET"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && [[ -s compose.yaml ]]; then
  STEP=inspect-compose
  if docker compose config >/dev/null 2>&1; then
    COMPOSE_AVAILABLE=true
    mapfile -t RUNNING_SERVICES < <(docker compose ps --services --status running 2>/dev/null | sed '/^[[:space:]]*$/d' || true)
  fi
fi

matrix_dumped=false
honcho_dumped=false
if [[ "$COMPOSE_AVAILABLE" == true ]]; then
  if printf '%s\n' "${RUNNING_SERVICES[@]}" | grep -Fxq synapse-db; then
    STEP=dump-synapse-postgres
    echo 'Dumping running Synapse PostgreSQL database.'
    docker compose exec -T synapse-db pg_dump -U synapse -d synapse -Fc > "$TMP_TARGET/synapse.dump" 2> "$TMP_TARGET/synapse-pg-dump.log" &
    dump_pid=$!
    if ! wait_with_progress "$dump_pid" 12 'Dumping Synapse PostgreSQL database' "$TMP_TARGET/synapse.dump"; then
      tail -n 12 "$TMP_TARGET/synapse-pg-dump.log" >&2 || true
      exit 1
    fi
    rm -f -- "$TMP_TARGET/synapse-pg-dump.log"
    [[ -s "$TMP_TARGET/synapse.dump" && "$(head -c 5 "$TMP_TARGET/synapse.dump")" == PGDMP ]] || {
      echo 'Synapse pg_dump did not produce a valid PostgreSQL custom-format dump.' >&2
      exit 1
    }
    matrix_dumped=true
  fi
  if printf '%s\n' "${RUNNING_SERVICES[@]}" | grep -Fxq honcho-db; then
    STEP=dump-honcho-postgres
    echo 'Dumping running Honcho PostgreSQL database.'
    docker compose exec -T honcho-db pg_dump -U honcho -d honcho -Fc > "$TMP_TARGET/honcho.dump" 2> "$TMP_TARGET/honcho-pg-dump.log" &
    dump_pid=$!
    if ! wait_with_progress "$dump_pid" 18 'Dumping Honcho PostgreSQL database' "$TMP_TARGET/honcho.dump"; then
      tail -n 12 "$TMP_TARGET/honcho-pg-dump.log" >&2 || true
      exit 1
    fi
    rm -f -- "$TMP_TARGET/honcho-pg-dump.log"
    [[ -s "$TMP_TARGET/honcho.dump" && "$(head -c 5 "$TMP_TARGET/honcho.dump")" == PGDMP ]] || {
      echo 'Honcho pg_dump did not produce a valid PostgreSQL custom-format dump.' >&2
      exit 1
    }
    honcho_dumped=true
  fi
fi

# Freeze only containers that were already running while the filesystem snapshot is
# created. PostgreSQL has already been dumped above; stopping the writers also makes
# SQLite/JSON/config state in Hermes/QMD/etc. consistent. Restore exactly these existing
# containers before returning to the Windows installer.
if [[ "$COMPOSE_AVAILABLE" == true && ${#RUNNING_SERVICES[@]} -gt 0 ]]; then
  STEP=stop-running-services
  report_progress 22 'Pausing only the containers that were already running for a consistent snapshot'
  echo "Temporarily stopping ${#RUNNING_SERVICES[@]} running LatticeVale container(s) for a consistent filesystem snapshot."
  RESTORE_NEEDED=true
  : > "$COMPOSE_LOG"
  if ! docker compose stop --timeout 45 "${RUNNING_SERVICES[@]}" >"$COMPOSE_LOG" 2>&1; then
    echo "Unable to stop all previously-running LatticeVale containers for the consistent snapshot." >&2
    tail -n 12 "$COMPOSE_LOG" >&2 || true
    exit 1
  fi
fi

STEP=archive-persistent-state
items=()
for p in \
  .env install-options.json .installer-state.json compatibility.conf state-audit.py latticevale_readonly.py latticevale_arch.py hardware-capabilities.py backend-capabilities.py runtime-policy.py diagnostics.py repair-plan.py audit-free.py checkpoint-metadata.json .install-info \
  .configured .provider-configured .installer-managed-profiles .matrix-configured \
  .matrix-info .matrix-profiles .tailscale-info .windows-native-info \
  compose.yaml compose.override.yaml config secrets logs \
  data/hermes data/qmd data/synapse data/tailscale data/tailscale-matrix \
  data/searxng-valkey data/honcho-redis data/ollama data/latticevale vault workspace backups/.keep; do
  [[ -e "$p" ]] && items+=("$p")
done
[[ "$matrix_dumped" == false && -e data/synapse-db ]] && items+=(data/synapse-db)
[[ "$honcho_dumped" == false && -e data/honcho-db ]] && items+=(data/honcho-db)

if ((${#items[@]})); then
  echo "Archiving ${#items[@]} persistent/configuration path(s) with root read access so container-owned files are preserved. This can take time when local Ollama models are present."
  report_progress 25 'Estimating archive size for the backup progress bar'
  estimate_file="$TMP_TARGET/.estimated-tar-bytes"
  python3 - "${items[@]}" > "$estimate_file" <<'PY_ESTIMATE' &
import os
import stat
import sys

payload = 0
entries = 0
long_names = 0

def account(path):
    global payload, entries, long_names
    try:
        info = os.lstat(path)
    except OSError:
        return
    entries += 1
    if len(os.fsencode(path)) > 100:
        long_names += 1
    if stat.S_ISREG(info.st_mode):
        payload += info.st_size
    elif stat.S_ISLNK(info.st_mode):
        payload += len(os.fsencode(os.readlink(path)))

for item in sys.argv[1:]:
    account(item)
    if os.path.isdir(item) and not os.path.islink(item):
        for root, dirs, files in os.walk(item, followlinks=False):
            for name in dirs + files:
                account(os.path.join(root, name))
print(max(1024, payload + entries * 1024 + long_names * 1024 + 1024))
PY_ESTIMATE
  estimate_pid=$!
  wait_with_progress "$estimate_pid" 25 'Estimating archive size for the backup progress bar'
  estimated_tar_bytes="$(cat "$estimate_file")"
  rm -f -- "$estimate_file"
  [[ "$estimated_tar_bytes" =~ ^[0-9]+$ ]] || estimated_tar_bytes=1
  progress_gzip="$TMP_TARGET/.latticevale-progress-gzip.py"
  cat > "$progress_gzip" <<'PY_GZIP'
import gzip
import sys
import time

destination = sys.argv[1]
estimated = max(1, int(sys.argv[2]))
processed = 0
last_report = 0.0
started = time.monotonic()

def human(value):
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB')
    value = float(value)
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    return f'{value:.1f} {units[unit]}'

with open(destination, 'wb') as raw:
    with gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=6) as archive:
        while True:
            chunk = sys.stdin.buffer.read(1024 * 1024)
            if not chunk:
                break
            archive.write(chunk)
            processed += len(chunk)
            now = time.monotonic()
            if now - last_report >= 1:
                fraction = min(0.99, processed / estimated)
                percent = 25 + int(fraction * 60)
                status = f'Archiving backup (approx. {int(fraction * 100)}%); {human(processed)} of about {human(estimated)} read; {int(now-started)}s elapsed'
                print(f'LV_PROGRESS|{percent}|{status}', file=sys.stderr, flush=True)
                last_report = now

print('LV_PROGRESS|87|Backup archive compressed; verifying its contents', file=sys.stderr, flush=True)
PY_GZIP
  chmod 0600 -- "$progress_gzip"
  tar -cf - -- "${items[@]}" | python3 "$progress_gzip" "$TMP_TARGET/files.tar.gz" "$estimated_tar_bytes"
  rm -f -- "$progress_gzip"
  [[ -s "$TMP_TARGET/files.tar.gz" ]] || { echo 'Persistent-state archive was created but is empty.' >&2; exit 1; }
  tar -tzf "$TMP_TARGET/files.tar.gz" >/dev/null
else
  echo 'No persistent/configuration paths were present to archive.'
fi

STEP=write-metadata
report_progress 90 'Writing backup ownership and recovery metadata'
{
  printf 'LatticeVale pre-update safety backup\n'
  printf 'created_utc=%s\n' "$STAMP"
  printf 'stack=%s\n' "$STACK"
  printf 'synapse_pg_dump=%s\n' "$matrix_dumped"
  printf 'honcho_pg_dump=%s\n' "$honcho_dumped"
  printf 'running_services_before=%s\n' "${RUNNING_SERVICES[*]:-none}"
  printf 'note=This backup may contain API keys, Matrix credentials, profile configuration, databases, vault/workspace files, and local model data. Protect it accordingly.\n'
} > "$TMP_TARGET/BACKUP-INFO.txt"
chmod -R go-rwx -- "$TMP_TARGET"
if [[ -n "$OWNER_UID" && -n "$OWNER_GID" ]]; then
  STEP=assign-backup-owner
  chown -R "$OWNER_UID:$OWNER_GID" -- "$TMP_TARGET"
fi

STEP=commit-backup
report_progress 96 'Committing the verified backup'
mv -- "$TMP_TARGET" "$TARGET"
BACKUP_COMPLETE=true

STEP=restore-services
report_progress 98 'Restoring the containers that were running before backup'
safe_restore

STEP=complete
report_progress 100 'Pre-install safety backup complete and verified'
echo "PREUPDATE_BACKUP_OK path=$TARGET"
echo 'Pre-install safety backup verified. Persistent application data remains in place; this is an additional rollback copy.'
