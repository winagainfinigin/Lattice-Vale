#!/usr/bin/env python3
"""Focused source contract for the 14.6.3 Matrix/gateway hotfix."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
installer = (ROOT / "Install-LatticeVale.ps1").read_text(encoding="utf-8")
configure = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
manage = (ROOT / "stack/manage.sh").read_text(encoding="utf-8")
audit = (ROOT / "stack/state-audit.py").read_text(encoding="utf-8")
compat = (ROOT / "compatibility.conf").read_text(encoding="utf-8")
release_policy = (ROOT / "release/release-content.json").read_text(encoding="utf-8")

kanban_start = configure.index("stage_kanban_gateway() {")
kanban_end = configure.index("\nstage_finalize() {", kanban_start)
kanban_stage = configure[kanban_start:kanban_end]

checks = {
    "repair asks to skip a per-run full safety backup before staging": "Skip the pre-install safety backup for this run?" in installer and "if ($repairMaintenance -and -not $skipPreInstallBackup)" in installer,
    "backup skip choice gates only the bundle-owned full backup": "elseif ($repairMaintenance -and $skipPreInstallBackup)" in installer and "Per-run choice: skipping the pre-install safety backup." in installer,
    "bundle backup helper streams database and archive progress": "LV_PROGRESS|" in (ROOT / "linux/pre-update-safety-backup.sh").read_text(encoding="utf-8") and "Archiving backup (approx." in (ROOT / "linux/pre-update-safety-backup.sh").read_text(encoding="utf-8"),
    "Windows installer renders streamed maintenance progress": "Write-Progress -Id $progressId" in installer and "LatticeVale pre-install safety backup" in installer,
    "APT refresh skip is passed to bootstrap only for this run": "Skip Ubuntu APT package-index refresh for this run?" in installer and "$skipUbuntuAptRefreshArg" in installer and 'skip_ubuntu_apt_refresh="${6:-false}"' in (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8"),
    "APT preflight includes required DirectML packages": 'directml="$4"' in installer and 'python3-venv libblas3 libomp5 liblapack3' in installer,
    "APT preflight follows the bootstrap NVIDIA device probe": '/usr/lib/wsl/lib/nvidia-smi' in installer,
    "APT index refresh displays elapsed activity progress": "APT index refresh [%-10s] %ss elapsed (%s; activity indicator)" in (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8"),
    "APT refresh prompt appears only when a refresh is planned or uncertain": "Ubuntu package-index refresh is not planned for this run" in installer and "if ($aptRefreshNeeded)" in installer,
    "healthy repair skips unnecessary pre-maintenance cache and staging cleanup": "root_free_kib >= 2097152" in (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8") and "skipped disposable-cache purge and stale staging scan" in (ROOT / "linux/bootstrap.sh").read_text(encoding="utf-8"),
    "cleanup streams helper output while it runs": "LatticeVale cleanup / reclaim disk space" in installer and "Invoke-NativeProcessCapture 'wsl.exe' $wslArgs 1800 $cleanupScript" in installer,
    "schema 24 remains supported": "INSTALL_OPTIONS_SCHEMA=24" in compat,
    "fresh Synapse identity comes from persisted options": "SYNAPSE_SERVER_NAME=\"$matrix_server_name\"" in configure,
    "installed homeserver identity takes precedence": "matrix_identity_domain() {" in configure and "cfg.get('server_name')" in configure,
    "Matrix profile IDs use live identity domain": 'expected_user="@$localpart:$(matrix_identity_domain)"' in configure,
    "existing hermes.local clients get manual discovery guidance": "MANUAL_HOMESERVER_REQUIRED" in installer and "MANUAL_HOMESERVER_REQUIRED" in audit,
    "identity and Element URL are stored separately": "matrixServerName = $matrixIdentityDomain" in installer and "matrixClientHomeserverUrl = $matrixClientHomeserverUrl" in installer,
    "fresh remote Matrix identity is resolved before account creation": installer.index("A fresh remote-capable Matrix install needs an authenticated Windows Tailscale node") < installer.index("$matrixIdentityDomain = 'hermes.local'") and "no Matrix identity or account has been created yet" in installer,
    "existing Synapse server_name overrides persisted identity": "$existingSynapseConfig.Text -match '(?m)^server_name:" in installer and "$matrixIdentityDomain = [string]$Matches[1]" in installer,
    "local-only fresh installs retain hermes.local": "$matrixIdentityDomain = 'hermes.local'" in installer and "matrixServerName = $matrixIdentityDomain" in installer,
    "remote-device page challenge is not required during installation": "Remote-device page challenge skipped" in installer and "Invoke-TailscaleRemotePeerValidation" not in installer and "Remote-device page validation is not part of installation" in installer,
    "matching untracked Matrix rule is automatically adopted without teardown": "adopting it without changing or restarting Tailscale Serve" in installer and "return 'adopt'" in installer and "if ($resolution -eq 'adopt')" in installer,
    "matching tracked Serve routes stay in place": "Keeping the existing installer-owned Matrix Serve mapping" in installer and "Keeping the existing installer-owned Dashboard Serve mapping" in installer,
    "existing route validation remains local and covers Matrix API paths": "Test-MatrixTailscaleClientPathViaIpv4 $matrixPublicUrl" in installer and "'/_matrix/client/v3/login'" in installer,
    "manifest generator excludes overwrite-patch deletion paths": "PATCH-DELETE.txt" in (ROOT.parent / "tools/New-SourceManifest.ps1").read_text(encoding="utf-8"),
    "Matrix transport, API, and MXID autodiscovery are separate": "$result.Transport" in installer and "$result.ClientApi" in installer and "$result.MxidAutodiscovery" in installer and "clientApi=$($result.ClientApi)" in installer,
    "all three remote Matrix endpoints are independently probed": "'/_matrix/client/versions'" in installer and "'/.well-known/matrix/client'" in installer and "'/_matrix/client/v3/login'" in installer,
    "changing the Tailscale hostname updates persisted client endpoints": "Update-MatrixEndpointOptionsInWsl" in installer and "tailscaleHostname=$TailscaleHostname" in installer,
    "managed gateways migrate at finalization and lifecycle start": "hermes gateway migrate --multiplex -y" in configure and "hermes gateway migrate --multiplex -y" in manage and ".installer-gateway-multiplex-owned" in manage,
    "final Kanban reload skips separate Matrix profile gateways after multiplex migration": ".installer-gateway-multiplex-owned" in kanban_stage and "skipping separate profile gateway starts" in kanban_stage and kanban_stage.index(".installer-gateway-multiplex-owned") < kanban_stage.index("start_or_restart_profile_gateway_exact"),
    "temporary standalone settings are ownership-tracked and restored": ".installer-temporary-standalone-profiles.json" in configure and "original.get('present')" in configure and "standalone choices remain for Hermes to honor" in manage,
    "gateway convergence verifies the live Hermes served profile record": "gateway_state.json" in configure and "served_profiles" in configure and "gateway_state.json" in manage and "served_profiles" in manage,
    "global migration refuses to alter an active unowned gateway": "unowned_multiplex_candidates" in configure and "unowned_multiplex_candidates" in manage and "unowned profile" in configure and "unowned profile" in manage,
    "default profile is excluded from temporary standalone mode": "if name != 'default':\n        if gateway.get('standalone') is not True" in configure,
    "managed topology supports default-only and named Matrix profiles": "mapfile -t managed_profiles" in configure and "profile_matrix_enabled=true" in configure and "selected_matrix_profile_names" in manage,
    "audit recognizes shared multiplexer topology": "Hermes host gateway multiplexer is active" in audit,
    "audit preserves explicit standalone choices": "Explicit gateway.standalone choices are user-owned topology" in audit and "yaml_multiplex_enabled(path)" in audit,
    "legacy false multiplex override is removed while true remains supported": "remove_legacy_gateway_multiplex_off" in configure and "false|no|off|0" in configure and "preserve an" in configure and 'value != "true"' in audit,
    "release manifest excludes generated bytecode caches": "LatticeVale-Core/stack/__pycache__/" in release_policy,
    "documented identity fallback matches supported Tailscale setup": "does not create Tailscale Service resources" in (ROOT.parent / "docs/Instructions.txt").read_text(encoding="utf-8"),
    "upgrade paths keep schema 23/24 data and named Matrix IDs": "1 <= schema <= current_schema" in (ROOT / "stack/latticevale_arch.py").read_text(encoding="utf-8") and 'expected_user="@$localpart:$(matrix_identity_domain)"' in configure,
}
spec = importlib.util.spec_from_file_location("latticevale_arch", ROOT / "stack/latticevale_arch.py")
arch = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(arch)
arch.validate_install_options({"schema": 24}, 24)  # existing schema-24 files remain readable
arch.validate_install_options({"schema": 23}, 24)  # 14.6.2 schema-23 state remains migratable
arch.validate_install_options({"schema": 24, "matrixServerName": "node.tailnet.ts.net", "matrixClientHomeserverUrl": "https://node.tailnet.ts.net/", "tailscaleHostname": "node.tailnet.ts.net"}, 24)
try:
    arch.validate_install_options({"schema": 24, "matrixClientHomeserverUrl": "javascript:alert(1)"}, 24)
except ValueError:
    pass
else:
    raise AssertionError("unsafe Matrix client URL was accepted")
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} {name}")
raise SystemExit(1 if failed else 0)
