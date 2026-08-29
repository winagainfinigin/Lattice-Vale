#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
version=(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()
assert version in {'14.4.85','14.5.0'}, version

# Regression observed on released Hotfix 1: docker compose reported all services up,
# but hermes-ollama was only Running (healthcheck still starting). stage_reconcile then
# finished and verify_reconcile immediately failed the repair with a generic message.
assert 'wait_managed_ollama_healthy()' in cfg
helper=cfg[cfg.index('wait_managed_ollama_healthy()'):cfg.index('ensure_matrix_online()', cfg.index('wait_managed_ollama_healthy()'))]
assert "[[ \"$status\" == healthy ]] && return 0" in helper
assert "[[ \"$status\" == unhealthy ]]" in helper
assert 'normal starting state' in helper

stage=cfg[cfg.index('stage_reconcile()'):cfg.index('stage_kanban_gateway()')]
compose='docker compose up -d --pull never --no-build --remove-orphans'
assert stage.index(compose) < stage.index('wait_managed_ollama_healthy 60') < stage.index('hermes --version')
assert 'wait_http Dashboard http://127.0.0.1:${DASHBOARD_HOST_PORT}/ 60' in stage
assert 'wait_matrix_backend_from_hermes 60' in stage

verify=cfg[cfg.index('verify_reconcile()'):cfg.index('verify_kanban_gateway()')]
assert "managed Ollama is not healthy" in verify
assert 'Synapse is not reachable as synapse:8008 from inside hermes-agent' in verify
for component in ('Hermes CLI','Hermes API','Dashboard','SearXNG','QMD','Honcho API'):
    assert component in verify, component

checkpoint=cfg[cfg.index('checkpoint_revision()'):cfg.index('matrix_profile_activation_pending()')]
assert "reconcile) printf '4'" in checkpoint
assert "kanban_gateway) printf '4'" in checkpoint  # v14.4.85 final candidate advances the final gateway lifecycle stage too.

# Execute the bounded Ollama waiter with a mocked Docker health sequence. This proves
# normal 'starting' is tolerated and eventually succeeds, while terminal 'unhealthy'
# fails immediately rather than being incorrectly accepted.
func_start=cfg.index('wait_managed_ollama_healthy() {')
func_end=cfg.index('\nensure_matrix_online() {', func_start)
func=cfg[func_start:func_end]
mock_ok=f'''set -e
managed_ollama_enabled() {{ return 0; }}
countfile=$(mktemp)
echo 0 > "$countfile"
docker() {{
  if [ "$1" = inspect ]; then
    n=$(cat "$countfile"); n=$((n+1)); echo "$n" > "$countfile"
    if [ "$n" -lt 3 ]; then echo starting; else echo healthy; fi
  else
    return 0
  fi
}}
sleep() {{ :; }}
{func}
wait_managed_ollama_healthy 5
rm -f "$countfile"
'''
r=subprocess.run(['bash','-c',mock_ok],capture_output=True,text=True)
assert r.returncode == 0, r.stderr
mock_bad=f'''set -e
managed_ollama_enabled() {{ return 0; }}
docker() {{ if [ "$1" = inspect ]; then echo unhealthy; else return 0; fi; }}
sleep() {{ :; }}
{func}
wait_managed_ollama_healthy 5
'''
r=subprocess.run(['bash','-c',mock_bad],capture_output=True,text=True)
assert r.returncode != 0
assert 'became unhealthy' in r.stderr

r=subprocess.run(['bash','-n',str(ROOT/'stack/configure-stack.sh')],capture_output=True,text=True)
assert r.returncode == 0, r.stderr
print('v14.4.85 RECONCILE STARTUP FIXTURES: PASS')
