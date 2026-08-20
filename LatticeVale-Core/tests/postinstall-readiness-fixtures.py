#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
compose=(root/'stack/compose.yaml').read_text()
manage=(root/'stack/manage.sh').read_text()
audit=(root/'stack/state-audit.py').read_text()
bootstrap=(root/'linux/bootstrap.sh').read_text()
readme=(root/'README.md').read_text()
ps1=(root/'Install-LatticeVale.ps1').read_text()
assert 'FORCE_OWNERSHIP: "false"' in compose
assert 'verify [seconds]' in manage and 'LatticeVale verification: HEALTHY' in manage
assert 'STARTING' in audit and 'STARTUP_GRACE_SECONDS = 300' in audit
assert 'container_state' in audit and 'is_settling' in audit
assert 'verify_selected_user_writable' in bootstrap
assert bootstrap.count('verify_selected_user_writable') >= 3  # definition + pre + post
assert 'after the services have started' in bootstrap
assert '## After the installer finishes' in readme
assert './manage.sh verify' in readme
assert 'Verify (recommended):' in ps1 and './manage.sh verify' in ps1
print('POST-INSTALL READINESS FIXTURES: PASS')
