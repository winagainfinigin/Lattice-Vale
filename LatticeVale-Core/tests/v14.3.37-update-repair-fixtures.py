from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS = (ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8-sig')
BOOT = (ROOT/'linux'/'bootstrap.sh').read_text(encoding='utf-8')
CONF = (ROOT/'stack'/'configure-stack.sh').read_text(encoding='utf-8')
MANAGE = (ROOT/'stack'/'manage.sh').read_text(encoding='utf-8')
VERSION = (ROOT/'VERSION.txt').read_text(encoding='ascii').strip()

assert VERSION in {'14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82'}, VERSION
assert "Update / repair installer-managed software" in PS
assert "$installMode = 'update'" in PS
assert "$forceManagedUpdate = $true" in PS
assert "schema = 19" in PS
assert "forceManagedUpdate = $forceManagedUpdate" in PS
assert "@('resume','change','reconfigure','advanced','update')" in PS
assert "@('resume','change','reconfigure','advanced','update')) -and $null -ne $existingOptions" in PS
assert "Creating pre-update managed-stack backup" in PS
assert "./manage.sh backup" in PS
assert "Update / repair stopped before software refresh because the pre-update managed-stack backup failed" in PS
assert "$forceManagedUpdateArg" in PS and "$bundleVersion, $forceManagedUpdateArg" in PS

assert 'force_managed_update="${4:-false}"' in BOOT
assert 'Update / repair is valid only for an existing installer-managed LatticeVale stack.' in BOOT
assert 'Explicit Update / repair requested: forcing this bundle' in BOOT
assert 'repair_refresh_pending=true' in BOOT
assert 'repair_root_refresh_needed=true' in BOOT
assert 'upgrading/installing only LatticeVale prerequisite packages plus the managed Docker package set' in BOOT

assert "'forceManagedUpdate'" in CONF
assert "schema must be an integer from 1 through 19" in CONF
assert "resume|reconfigure|update) return 0 ;;" in CONF
assert "Explicit Update / repair managed package/image/source refresh completed" in CONF
# The transient operation mode must not invalidate the saved configuration checkpoint identity.
assert "'forceManagedUpdate'" in CONF.split('OPTIONS_HASH=',1)[1].split('CURRENT_STAGE=',1)[0]
# A forced managed refresh must bypass the relevant checkpoints and exercise every
# installer-owned component update path rather than only refreshing apt metadata.
assert 'prepare_config|infrastructure) repair_package_refresh_pending' in CONF
assert 'provider_setup) [[ "$(opt_bool forceProviderSetup)" == true ]] || repair_package_refresh_pending' in CONF
assert 'profiles) [[ "$(opt_bool forceProfileSetup)" == true ]] || repair_package_refresh_pending' in CONF
assert 'docker compose pull --ignore-buildable' in CONF
assert 'docker compose build --pull qmd' in CONF
assert 'docker compose build --pull honcho-api' in CONF
assert 'Pulling Hermes image: $hermes_image' in CONF
assert 'reconciling installer-owned Honcho source to audited commit' in CONF
assert 'set_env .env SEARXNG_IMAGE "$tested_searxng_image"' in CONF
assert 'set_env .env OLLAMA_IMAGE "$desired_ollama_image"' in CONF

assert 'NOT the bundle-pinned installer updater' in MANAGE
assert 'Choose Update / repair installer-managed software' in MANAGE
assert 'may advance Honcho to repository HEAD' in MANAGE

print('v14.3.37 controlled update/repair fixtures: PASS')
