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
    "schema 24 remains supported": "INSTALL_OPTIONS_SCHEMA=24" in compat,
    "fresh Synapse identity comes from persisted options": "SYNAPSE_SERVER_NAME=\"$matrix_server_name\"" in configure,
    "installed homeserver identity takes precedence": "matrix_identity_domain() {" in configure and "cfg.get('server_name')" in configure,
    "Matrix profile IDs use live identity domain": 'expected_user="@$localpart:$(matrix_identity_domain)"' in configure,
    "existing hermes.local clients get manual discovery guidance": "MANUAL_HOMESERVER_REQUIRED" in installer and "MANUAL_HOMESERVER_REQUIRED" in audit,
    "identity and Element URL are stored separately": "matrixServerName = $matrixIdentityDomain" in installer and "matrixClientHomeserverUrl = $matrixClientHomeserverUrl" in installer,
    "fresh remote Matrix identity is resolved before account creation": installer.index("A fresh remote-capable Matrix install needs an authenticated Windows Tailscale node") < installer.index("$matrixIdentityDomain = 'hermes.local'") and "no Matrix identity or account has been created yet" in installer,
    "existing Synapse server_name overrides persisted identity": "$existingSynapseConfig.Text -match '(?m)^server_name:" in installer and "$matrixIdentityDomain = [string]$Matches[1]" in installer,
    "local-only fresh installs retain hermes.local": "$matrixIdentityDomain = 'hermes.local'" in installer and "matrixServerName = $matrixIdentityDomain" in installer,
    "remote-device validation selects the tracked Matrix listener when enabled": "if ($trackedMatrixPort -gt 0) { $trackedMatrixPort } else { $trackedDashboardPort }" in installer and "if ($trackedMatrixPort -gt 0) { $matrixBridgePort } else { $dashboardBridgePort }" in installer and "Invoke-TailscaleRemotePeerValidation $tailscaleExe $dnsName $tsStatus.IPv4 $remoteValidationPort $remoteValidationBackendPort $remoteValidationService" in installer,
    "remote challenge uses a unique path on configured listener": "'/.latticevale-validation/'" in installer and '"--https=$HttpsPort"' in installer,
    "challenge tokens and paths are unique for every device": "[Guid]::NewGuid().ToString('N').Substring(0,12)" in installer and "$path='/.latticevale-validation/'+[Guid]::NewGuid().ToString('N')" in installer,
    "challenge cleanup is path-scoped after each attempt": '"--set-path=$path"' in installer and "'off') 30" in installer and "finally {\n            if ($serveStarted)" in installer,
    "permanent Matrix root route is checked": "RootTargets" in installer and "Permanent Matrix HTTPS mapping did not verify after challenge cleanup." in installer,
    "remote validation aggregates per-device pass fail and skip outcomes": "result.Passed++;" in installer and "result.Failed++;" in installer and "result.Skipped++;" in installer and "REMOTE_VALIDATION_SKIPPED" in installer,
    "ACL, transport, TLS, and hostname failures have separate categories": "'DNS unavailable / hostname not found'" in installer and "'Connection timed out / unreachable / refused'" in installer and "'TLS or certificate error'" in installer and "'Page opened but the validation code did not match'" in installer,
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
