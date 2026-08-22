#!/usr/bin/env python3
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
version=(root/'VERSION.txt').read_text().strip()
assert version in {'14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82'}
cfg=(root/'stack/configure-stack.sh').read_text()
assert 'read_env_file_value_optional()' in cfg
assert 'bot_device_id="$(read_env_file_value_optional secrets/matrix-bot.env MATRIX_DEVICE_ID)"' in cfg
assert "secrets/matrix-bot.env 2>/dev/null | head -n1" not in cfg

if version in {'14.3.6','14.3.7'}:
    assert "tail -n1 || true)" in cfg
else:
    assert 'matrix_require_room_v10()' in cfg
    assert 'wait_matrix_client_api()' in cfg
start=cfg.index('read_env_file_value_optional() {')
end=cfg.index('\n}\n',start)+3
helper=cfg[start:end]
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    script=td/'t.sh'
    script.write_text('#!/usr/bin/env bash\nset -Eeuo pipefail\n'+helper+'\nv="$(read_env_file_value_optional does-not-exist.env MATRIX_DEVICE_ID)"\n[[ -z "$v" ]]\nprintf \'MATRIX_DEVICE_ID=ABC=123\\r\\nOTHER=x\\n\' > present.env\nv="$(read_env_file_value_optional present.env MATRIX_DEVICE_ID)"\n[[ "$v" == \'ABC=123\' ]]\n')
    r=subprocess.run(['bash',str(script)],cwd=td,capture_output=True,text=True)
    assert r.returncode==0, r.stdout+r.stderr
print('v14.3.6 Matrix first-bootstrap pipefail fixtures: PASS')
