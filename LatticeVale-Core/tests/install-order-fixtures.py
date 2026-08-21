from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = (root / 'VERSION.txt').read_text().strip()
configure = (root / 'stack' / 'configure-stack.sh').read_text(encoding='utf-8')
ps1 = (root / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
readme = (root / 'README.md').read_text(encoding='utf-8')

def pos(text, needle):
    i = text.find(needle)
    assert i >= 0, f'missing marker: {needle}'
    return i

# Runtime stage calls are the canonical order, independent of function-definition layout.
stages=['prepare_config','infrastructure','matrix_bootstrap','provider_setup','profiles','matrix_cross_signing','integrations','reconcile','kanban_gateway','finalize']
positions=[pos(configure,f'run_stage {s} ') for s in stages]
assert positions == sorted(positions)
assert pos(configure,'run_stage matrix_bootstrap ') < pos(configure,'run_stage provider_setup ')
assert pos(configure,'run_stage profiles ') < pos(configure,'run_stage matrix_cross_signing ') < pos(configure,'run_stage integrations ')
assert pos(configure,'run_stage integrations ') < pos(configure,'run_stage reconcile ')
assert pos(configure,'run_stage reconcile ') < pos(configure,'run_stage kanban_gateway ')

# Matrix infrastructure/identity logic exists inside its pre-provider stage.
if version in {'14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}:
    assert 'ensure_matrix_online 90' in configure
    assert '/_matrix/client/versions' in configure
else:
    assert 'wait_http Matrix http://127.0.0.1:${MATRIX_HOST_PORT}/health 90' in configure
assert 'Matrix account setup: create one admin account and one Hermes bot account' in configure
assert 'secrets/matrix-bot.env' in configure

# Windows-only add-ons/exposure happen after Linux bootstrap succeeds.
bootstrap = pos(ps1, "Write-Step 'Bootstrapping Docker and the selected LatticeVale stack inside Ubuntu'")
windows_apps = pos(ps1, "Write-Step 'Installing selected Windows applications'")
tailscale = pos(ps1, "Write-Step 'Configuring Windows Tailscale access to selected WSL services'")
autostart = pos(ps1, "Write-Step 'Registering selected stack to start at Windows logon'")
assert bootstrap < windows_apps < tailscale < autostart

# README explicitly documents Matrix-before-Hermes and recovery ordering.
assert '**bootstrap and verify Matrix before Hermes setup**' in readme
assert 'Hermes provider/model selection therefore does **not** run before a selected Matrix homeserver' in readme
assert 'Resume / repair' in readme

print('INSTALL ORDER FIXTURES: PASS')
print('- checkpointed Linux stage order enforced')
print('- Matrix identity/bootstrap precedes provider setup')
print('- Matrix cross-signing follows Hermes startup and precedes integrations/reconciliation')
print('- integrations/reconciliation precede Kanban + gateway')
print('- Windows add-ons/Tailscale/autostart follow Linux success')
