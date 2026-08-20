#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
bootstrap=(root/'linux/bootstrap.sh').read_text(encoding='utf-8')
configure=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
assert 'runuser --pty -u "$linux_user" -- env HOME="$user_home" USER="$linux_user" bash "$stack_dir/configure-stack.sh"' in bootstrap, 'configure-stack must run behind a PTY'
assert 'runuser -u "$linux_user" -- env HOME="$user_home" USER="$linux_user" bash "$stack_dir/configure-stack.sh"' not in bootstrap, 'non-PTY runuser invocation reintroduced'
assert 'docker run --rm -it' in configure, 'default Hermes setup must retain interactive TTY'
assert 'docker exec -it -u hermes hermes-agent hermes -p "$name" model' in configure, 'profile setup must retain interactive TTY'
assert "mapfile -t requested_workers < <(jq -c '.workers[]?' install-options.json)" in configure, 'profile list must be materialized before entering interactive loop'
assert "\ndone < <(jq -c '.workers[]?' install-options.json)" not in configure, 'profile loop must not replace TTY stdin with jq process-substitution pipe'
print('INTERACTIVE TTY FIXTURES: PASS')
