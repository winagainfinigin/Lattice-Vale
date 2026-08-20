#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
for text in (
    'function Get-LatticeValePublishedPortOwnership',
    'com.docker.compose.project.working_dir',
    "project == 'hermesstack'",
    "'0.0.0.0'",
    'function Resolve-LatticeValeRepairLocalPort',
    'Reconciling existing localhost port ownership',
    "'hermes-agent' 8642",
    "'hermes-agent' 9119",
    "'hermes-synapse' 8008",
    "'hermes-searxng' 8080",
    "'hermes-honcho-api' 8000",
    '$priorDashboardLocalPort',
    '$priorMatrixLocalPort',
    '$oldDashboardBackendPort',
    '$oldMatrixBackendPort',
    'Write-LatticeValeBridgeConfig',
    'Invoke-LatticeValeBridgeRefresh',
):
    assert text in ps, text
# Legacy installer-owned direct Serve rules are recognized through the previously saved local port.
assert "$oldDashboardBackendPort = if ($oldDashboardBridgePort -gt 0) { $oldDashboardBridgePort } else { $priorDashboardLocalPort }" in ps
assert "$oldMatrixBackendPort = if ($oldMatrixBridgePort -gt 0) { $oldMatrixBridgePort } else { $priorMatrixLocalPort }" in ps
# New bridge mappings use stable Windows bridge ports; changing a WSL backend port is repaired by the native relay following the current WSL IP, not by destroying the HTTPS Serve rule.
assert "Disable-WindowsTailscaleServe $tailscaleExe $oldDashboardPort $oldDashboardBackendPort 'Dashboard'" in ps
assert "Disable-WindowsTailscaleServe $tailscaleExe $oldMatrixPort $oldMatrixBackendPort 'Matrix'" in ps
print('REPAIR PORT RECONCILIATION: PASS')
