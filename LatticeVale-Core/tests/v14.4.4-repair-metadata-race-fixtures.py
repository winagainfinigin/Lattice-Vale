#!/usr/bin/env python3
"""Deterministic v14.4.4 live metadata-repair race regressions."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
version = (root / 'VERSION.txt').read_text().strip()
assert version in {'14.4.4','14.4.5','14.4.6'}, version
bootstrap = (root / 'linux' / 'bootstrap.sh').read_text()

start = bootstrap.index('repair_user_tree() {')
end_marker = '\n}\n\ninstall -d -m 0700'
end = bootstrap.index(end_marker, start) + 3
func = bootstrap[start:end]

required = [
    'find -P "$path" -xdev -ignore_readdir_race -print0',
    'if [[ ! -e "$item" && ! -L "$item" ]]; then',
    'if [[ ! -L "$item" ]]; then',
    'Failed to repair ownership for',
    'Failed to repair permissions for',
]
for token in required:
    assert token in func, token
assert 'chown -hR' not in func
assert 'chmod -R u+rwX' not in func

with tempfile.TemporaryDirectory() as td:
    script = f'''set -Eeuo pipefail
stack_dir={td!r}
linux_uid="$(id -u)"
linux_gid="$(id -g)"
{func}
mkdir -p "$stack_dir/data/hermes"
touch "$stack_dir/data/hermes/keep.db" "$stack_dir/data/hermes/kanban.db-shm"

# Deterministically emulate the observed race: the sidecar existed during the
# snapshot, then vanished immediately before chown could operate on it.
chown() {{
  local item="${{!#}}"
  if [[ "$item" == */kanban.db-shm ]]; then
    rm -f -- "$item"
    return 1
  fi
  command chown "$@"
}}
repair_user_tree data/hermes
[[ ! -e "$stack_dir/data/hermes/kanban.db-shm" ]]
[[ -e "$stack_dir/data/hermes/keep.db" ]]

# A genuine ownership failure on a still-existing entry must remain fatal.
touch "$stack_dir/data/hermes/hard-failure"
chown() {{
  local item="${{!#}}"
  if [[ "$item" == */hard-failure ]]; then
    return 1
  fi
  command chown "$@"
}}
if repair_user_tree data/hermes; then
  echo 'repair_user_tree incorrectly swallowed a real chown failure' >&2
  exit 21
fi
[[ -e "$stack_dir/data/hermes/hard-failure" ]]
'''
    subprocess.run(['bash', '-c', script], check=True)

print('v14.4.4 repair metadata-race fixtures: PASS')
