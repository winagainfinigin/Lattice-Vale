from pathlib import Path
import re

configure=Path(__file__).resolve().parents[1]/'stack'/'configure-stack.sh'
s=configure.read_text(encoding='utf-8')
m=re.search(r'apply_matrix_runtime_env\(\) \{(.*?)\n\}',s,re.S)
assert m, 'apply_matrix_runtime_env helper missing'
body=m.group(1)
assert 'MATRIX_RECOVERY_KEY_OUTPUT_FILE' not in re.search(r'for key in (.*?); do',body).group(1), 'one-time recovery output setting must not be copied into normal runtime env'
assert 'MATRIX_RECOVERY_KEY' in body, 'retained recovery key must still be propagated when available'
assert re.search(r'\n\s*return 0\s*$',body), 'helper must explicitly succeed after copying present optional values'
assert 'if [[ -n "$value" ]]; then' in body, 'optional keys must be handled without leaking a failed [[ ]] status'
assert 'apply_matrix_runtime_env secrets/matrix-bot.env' in s, 'integrations stage must still reapply Matrix runtime credentials'
print('v13.16.4 Matrix runtime env fixtures: PASS')
