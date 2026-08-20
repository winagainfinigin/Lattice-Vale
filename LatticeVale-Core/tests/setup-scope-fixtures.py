from pathlib import Path
root=Path(__file__).resolve().parents[1]
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(root/'stack/manage.sh').read_text(encoding='utf-8')
readme=(root/'README.md').read_text(encoding='utf-8')

assert '"$hermes_image" setup' not in cfg
assert 'hermes -p "$name" setup' not in cfg
assert '"$hermes_image" model' in cfg
assert 'hermes -p "$name" model' in cfg
assert "DEFAULT Hermes profile provider/model selection follows." in cfg
assert "SECONDARY Hermes profile '$name' provider/model selection follows." in cfg
assert "if 'browser' not in tools: tools.append('browser')" in cfg
assert "browser.setdefault('engine','auto')" in cfg
assert 'MATRIX_BOT_PASSWORD=$bot_password' in cfg
assert 'for key in MATRIX_HOMESERVER MATRIX_ACCESS_TOKEN MATRIX_USER_ID MATRIX_ALLOWED_USERS MATRIX_ALLOWED_ROOMS MATRIX_E2EE_MODE' in cfg
helper=cfg.split('apply_matrix_runtime_env()',1)[1].split('\n}',1)[0]
assert 'MATRIX_BOT_PASSWORD' in helper  # comment documents exclusion
loop=helper.split('for key in',1)[1].split('; do',1)[0]
assert 'MATRIX_BOT_PASSWORD' not in loop
assert 'matrix-credentials' in manage
assert 'MATRIX_BOT_PASSWORD=not-retained-by-older-installer-release' in manage
for expected in (
    'choose **Local browser** rather than Browser Use cloud',
    '**Default profile:**',
    '**Secondary profiles:**',
    '**OpenCode Go:**',
    'http://synapse:8008',
    '@hermes:hermes.local',
    './manage.sh matrix-credentials',
):
    assert expected in readme, expected
print('SETUP SCOPE / MATRIX / BROWSER FIXTURES: PASS')
