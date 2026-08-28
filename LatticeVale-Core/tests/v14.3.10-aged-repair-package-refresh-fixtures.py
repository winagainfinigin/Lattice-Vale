#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text().strip()
assert version in {'14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}, version
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
compat=(ROOT/'compatibility.conf').read_text(encoding='utf-8')

# The historical refresh interval remains 30 days. v14.4.5 briefly treated a bundle
# version change as a bounded managed-refresh trigger. v14.4.6 supersedes that behavior:
# the explicit policy revision is the immediate convergence signal and VERSION is provenance.
assert 'MANAGED_REPAIR_REFRESH_DAYS=30' in compat
assert ('MANAGED_REPAIR_REFRESH_REVISION=2' in compat) if version in {'14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'} else ('MANAGED_REPAIR_REFRESH_REVISION=1' in compat)
assert "MANAGED_REPAIR_REFRESH_DAYS'" in ps and 'ManagedRepairRefreshDays' in ps
assert "MANAGED_REPAIR_REFRESH_REVISION'" in ps and 'ManagedRepairRefreshRevision' in ps
assert '.repair-package-refresh' in boot and '.repair-package-refresh-pending' in boot
assert 'installer-config.tar.gz' in boot and '.repair-package-refresh .repair-package-refresh-pending' in boot
assert 'legacy installs without a refresh marker refresh once' in boot
assert 'now_epoch - last_refresh_epoch >= repair_refresh_interval_seconds' in boot
assert 'last_refresh_revision' in boot and 'last_refresh_revision" != "$repair_refresh_revision' in boot
if version in {'14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}:
    assert r"printf 'POLICY_REVISION=%s\nINSTALLER_VERSION=%s\n'" in boot
    assert 'last_refresh_installer_version' in boot
    assert 'pending_refresh_installer_version' in boot
    if version in {'14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84'}:
        assert '[[ "$last_refresh_installer_version" != "$installer_version" ]]' not in boot
        assert '[[ "$pending_refresh_revision" == "$repair_refresh_revision" ]]' in boot
else:
    assert r"printf 'POLICY_REVISION=%s\n'" in boot

# A due repair refresh upgrades only packages LatticeVale actually manages/depends on.
# It must not become an indiscriminate Ubuntu full-system upgrade.
assert 'upgrading/installing only LatticeVale prerequisite packages' in boot
assert '"${prereq_packages[@]}"' in boot
assert 'upgrading/installing the complete official Docker Engine/CLI/containerd/Buildx/Compose package set' in boot
assert '"${docker_required_packages[@]}"' in boot
for forbidden in ('apt-get upgrade', 'apt upgrade', 'full-upgrade', 'dist-upgrade'):
    assert forbidden not in boot, forbidden

# When the package half is complete, Resume carries a pending handoff into the user-level
# configure stage. Current installer-owned image/config pins are reapplied and the local-first
# no-network shortcut is bypassed only for this periodic refresh cycle.
assert 'repair_package_refresh_pending()' in cfg
bypass=cfg[cfg.index('checkpoint_bypass_requested()'):cfg.index('\nresume_adoption_allowed()')]
assert 'prepare_config|infrastructure' in bypass
assert 'provider_setup' in bypass and 'repair_package_refresh_pending' in bypass
assert 'profiles' in bypass and 'repair_package_refresh_pending' in bypass
infra=cfg[cfg.index('stage_infrastructure()'):cfg.index('\nstage_matrix_bootstrap()')]
assert 'repair_maintenance_enabled && ! repair_package_refresh_pending' in infra
assert 'docker compose pull --ignore-buildable' in infra
provider=cfg[cfg.index('stage_provider_setup()'):cfg.index('\nstage_profiles()')]
assert 'repair_maintenance_enabled && ! repair_package_refresh_pending' in provider
assert 'docker pull "$hermes_image"' in provider

# The periodic cycle is not marked complete until infrastructure + Hermes profile/container
# refresh has verified. Interrupted later stages therefore do not repeat package work.
start=cfg.rindex("run_stage prepare_config")
sequence=cfg[start:cfg.index('state_finish', start)]
assert sequence.index("run_stage infrastructure") < sequence.index("run_stage profiles")
assert sequence.index("run_stage profiles") < sequence.index('complete_repair_package_refresh')
assert 'LAST_SUCCESS_EPOCH=' in cfg and 'POLICY_REVISION=' in cfg
assert "s/^POLICY_REVISION=//p' .repair-package-refresh-pending" in cfg
assert 'rm -f .repair-package-refresh-pending' in cfg

# NVIDIA toolkit is also re-evaluated on a due package refresh rather than being skipped
# solely because an older working runtime is present; newer complete toolkits remain preserved
# by the existing no-downgrade logic.
assert 'nvidia_runtime_ready && [[ "$repair_root_refresh_needed" != true ]]' in boot
assert 'toolkit_has_newer' in boot and 'preserving it and verifying the runtime instead of downgrading' in boot


# Periodic convergence must advance only LatticeVale-owned app pins/source. Custom values
# remain outside the automatic repair boundary.
assert 'LATTICEVALE_SEARXNG_IMAGE_AUTO' in cfg
assert 'repair_package_refresh_pending && [[ "$searxng_installer_owned" == true ]]' in cfg
assert 'Preserving user-set SEARXNG_IMAGE=' in cfg
assert 'between refresh windows keep the' in cfg and 'marker on the old value actually in use' in cfg
assert 'Preserving installer-owned OLLAMA_IMAGE=' in cfg
assert 'repair_package_refresh_pending || [[ "$ollama_policy_switch" == true ]]' in cfg
assert 'LATTICEVALE_HONCHO_SOURCE_AUTO' in cfg
assert 'repair_package_refresh_pending && [[ "$honcho_installer_owned" == true ]]' in cfg
assert 'Preserving custom/legacy Honcho source commit' in cfg

print('v14.3.10 aged repair package-refresh fixtures: PASS')
