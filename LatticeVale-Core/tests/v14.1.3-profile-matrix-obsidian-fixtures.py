#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ps1=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
version=(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}
assert 'schema = 19' in ps1

# Profile/Matrix intent is one data structure: arbitrary installer profile name -> same Matrix localpart.
assert '$matrixLocalpart = $name' in ps1
assert 'localpart = $matrixLocalpart' in ps1
assert 'modelMode = if ($clone)' in ps1
assert 'Give profile \'$name\' its own Matrix/Element bot and room?' in ps1
assert "Messages in that room use the model configured for profile '$name'." in ps1
assert "Use an existing encrypted Matrix room for '$name'?" in ps1
assert 'Complete-WorkerMatrixOptions $workers $matrix $false $true' in ps1  # conservative v13.16 -> v14 repair migration
assert 'Complete-WorkerMatrixOptions $workers $matrix $true $true' in ps1   # fresh/change selection
assert "localpart != name" in cfg or "localpart'] != name" in cfg
assert "[[ \"$localpart\" == \"$name\" ]]" in cfg
assert 'expected_user="@$localpart:hermes.local"' in cfg
assert 'windowsShortcuts' in cfg.split('bool_keys=',1)[1].split(']',1)[0], 'persisted shortcut option must receive strict boolean validation'
assert "schema must be an integer from 1 through 19" in cfg
assert "Profile 'hermes' cannot receive an independent LatticeVale Matrix identity" in ps1, 'secondary Matrix identity must not collide with default @hermes account'
assert '[[ -z "$default_token" || "$token" != "$default_token" ]] || return 1' in cfg, 'secondary profile must not reuse default bot token'
assert 'device_id="LATTICEVALE_${name^^}"' in cfg
assert 'FOUNDRY_PROVISIONING_STATE' in cfg, 'legacy v14 provisioning marker must still be readable for repair migration' 

# Never revive the invented matrix2/home_channel routing model.
for forbidden in ('platforms.matrix2','matrix2.max_message_length','home_channel.chat_id','platforms.matrix.home_channel'):
    assert forbidden not in ps1 + cfg + manage
assert 'MATRIX_HOME_ROOM' in cfg
assert 'MATRIX_ALLOWED_ROOMS' in cfg

# Profile model creation/selection is complete before Matrix identity/gateway provisioning.
assert cfg.index("run_stage profiles '") < cfg.index("run_stage matrix_profiles '")
assert 'hermes_model_configured "$pdir/config.yaml"' in cfg
assert cfg.index('hermes_model_configured "$pdir/config.yaml"') < cfg.index('gateway restart >/dev/null', cfg.index('stage_matrix_profiles()'))
assert 'HERMES_MODEL=$model' in cfg
assert "sed -n 's/^HERMES_MODEL=//p' \"$info\"" in cfg, 'repair verification must detect profile-model metadata drift'
assert 'info_model == model' in audit, 'state audit must verify Matrix binding metadata matches the profile current model'

# Secondary bots are independent users created through the private Synapse Admin API.
assert '/_synapse/admin/v2/users/$encoded_user' in cfg
assert 'user_type:"bot"' in cfg
assert 'enable_registration=true' not in cfg.replace(' ', '').lower()
assert 'set_env "$secret" MATRIX_ACCESS_TOKEN "$token"' in cfg
assert 'set_env "$secret" MATRIX_USER_ID "$expected_user"' in cfg
assert 'set_env "$secret" MATRIX_DEVICE_ID "$device_id"' in cfg
assert '/opt/data/profiles/$name/matrix-recovery-key.once' in cfg
assert 'secrets/matrix-profiles/$name.env' in cfg
assert '.matrix-profiles/$name.info' in cfg


# Profile Matrix provisioning is transactional: irreversible Synapse account/room work is recorded pending first and repair can resume it.
assert 'LATTICEVALE_PROVISIONING_STATE pending' in cfg
assert 'LATTICEVALE_PROVISIONING_STATE complete' in cfg
assert 'Resuming interrupted Matrix provisioning for Hermes profile' in cfg
assert cfg.index('LATTICEVALE_PROVISIONING_STATE pending') < cfg.index('/_synapse/admin/v2/users/$encoded_user', cfg.index('stage_matrix_profiles()'))
if version in {'14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}:
    assert 'LATTICEVALE_PROVISIONING_STATE pending-manual' in cfg
    assert 'MATRIX_SETUP_STATUS=$provisioning_state' in cfg
else:
    assert 'Mark complete LAST' in cfg
assert '[[ "$provisioning_state" == complete ]] || return 1' in cfg or 'pending-manual' in cfg

# Container/WSL execution scope: profile Hermes commands are docker exec, never host-only venv paths.
assert 'start_or_restart_profile_gateway_exact "$name"' in cfg
assert '/command/s6-svc -r "/run/service/gateway-$name"' in cfg
assert '/opt/hermes/.venv/bin/hermes' not in ps1 + cfg + manage

# The profile Matrix stage is a subshell, so EXIT cleanup/set -e cannot leak to an interactive parent shell.
assert re.search(r'^stage_matrix_profiles\(\) \(\n\s+set -Eeuo pipefail', cfg, re.M)
assert 'trap cleanup_matrix_profile_stage EXIT' in cfg

# Existing administrator-managed Synapse registration secrets are preserved; LatticeVale removes only its marker-owned secret.
# The human Matrix admin password is one-time only and is not kept as a persistent profile-management credential.
assert '.matrix-registration-secret-installer-managed' in cfg
assert 'if [[ "$matrix_registration_secret_managed" == true ]]' in cfg
assert "cfg.pop('registration_shared_secret', None)" in cfg

# Matrix-enabled workers run a profile gateway; ordinary Kanban-only workers stay non-resident.
assert "select(.matrix.enabled == true) | .name" in cfg
assert 'Named profiles' in cfg and 'remain stopped unless' in cfg

# Backups/audits include the new profile-Matrix metadata without exposing it as ordinary public state.
assert '.matrix-profiles' in manage
assert 'secrets/matrix-profiles' in manage
assert 'profileMatrix' in audit
assert 'matrixEnabled' in audit

# Obsidian vault is requested during the initial component questionnaire and persisted through the hardened path converter.
vault_prompt = ('Windows Obsidian vault folder (explicit Windows-local path required)' if version in {'14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'} else ('Windows Obsidian vault folder [suggested: $defaultObsidianVault; Enter accepts]' if version in {'14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21'} else 'Windows Obsidian vault folder [$defaultObsidianVault]'))
assert vault_prompt in ps1
assert ps1.index(vault_prompt) < ps1.index("Read-Choice 'Install fully self-hosted Honcho memory?'")
assert 'obsidianVaultWindowsPath = $obsidianVaultWindowsPath' in ps1
assert 'obsidianVaultWslPath = $obsidianVaultWslPath' in ps1
assert "'wslpath' @('-a','-u',$driveRootWindows)" in ps1
assert "'wslpath' @('-a','-u',$full)" not in ps1

assert 'secrets/matrix-admin.env' not in cfg
assert 'secrets/matrix-admin-once.env' in cfg
assert 'rm -f secrets/matrix-admin-once.env' in cfg
assert 'LatticeVale does not retain this password after the profile provisioning stage exits.' in cfg
assert 'profile create "$name" --clone' not in cfg
assert 'profile create "$name" --description "$desc"' in cfg
assert 'hermes -p "$name" gateway stop' in cfg
assert 'quiesce_profile_gateway_for_credential_write "$name"' in cfg
assert '/command/s6-svstat' in cfg and '/run/service/gateway-$name' in cfg
assert "gateway status 2>/dev/null | grep -qi 'running'" not in cfg
assert 'PY_PROFILE_SAFE_CLONE' in cfg
assert "prefixes=('TELEGRAM_','DISCORD_','SLACK_','MATRIX_'" in cfg

print('V14.3.0 PROFILE MATRIX + OBSIDIAN FIXTURES: PASS')
