#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT.parent
errors=[]

def check(cond, msg):
    if not cond:
        errors.append(msg)

def check_before(text, first, second, msg):
    """Record missing/order failures without aborting the rest of the audit."""
    first_pos=text.find(first)
    second_pos=text.find(second)
    check(first_pos >= 0, f'{msg}: missing first marker: {first}')
    check(second_pos >= 0, f'{msg}: missing second marker: {second}')
    if first_pos >= 0 and second_pos >= 0:
        check(first_pos < second_pos, msg)

def read(rel):
    p=ROOT/rel
    check(p.is_file(), f'missing required file: {rel}')
    return p.read_text(encoding='utf-8') if p.is_file() else ''

version=read('VERSION.txt').strip()
ps1=read('Install-LatticeVale.ps1')
bootstrap=read('linux/bootstrap.sh')
compose_text=read('stack/compose.yaml')
configure=read('stack/configure-stack.sh')
manage=read('stack/manage.sh')
state_audit=read('stack/state-audit.py')
relay=read('windows/LatticeVale-WslNativeRelay.ps1')
shortcut_launcher=read('windows/LatticeVale-Shortcut.ps1')
release_install=(RELEASE_ROOT/'installer/Install-LatticeVale.ps1').read_text(encoding='utf-8')
release_verify=(RELEASE_ROOT/'installer/verify-release.ps1').read_text(encoding='utf-8')
manifest_generator=(RELEASE_ROOT/'tools/New-SourceManifest.ps1').read_text(encoding='utf-8')
readme=(RELEASE_ROOT/'docs/README.md').read_text(encoding='utf-8')
audit=read('AUDIT.md')
compatibility=read('compatibility.conf')

# PowerShell parse guard: a bare variable immediately followed by ':' is parsed
# as a scoped/provider variable reference. Scan every shipped PowerShell file,
# including newly-added helpers, rather than maintaining a fragile hard-coded list.
_allowed_ps_colon_prefixes={'env','global','local','script','private','using','variable','function','alias'}
_shipped_ps1=[]
for _path in sorted(RELEASE_ROOT.rglob('*.ps1'),key=lambda p:p.relative_to(RELEASE_ROOT).as_posix().lower()):
    if '.git' in _path.parts:
        continue
    _label=_path.relative_to(RELEASE_ROOT).as_posix()
    _bytes=_path.read_bytes()
    _bad=[(i,b) for i,b in enumerate(_bytes) if b > 0x7f]
    check(not _bad, f'PowerShell {_label} contains non-ASCII byte 0x{_bad[0][1]:02x} at offset {_bad[0][0]}' if _bad else '')
    try:
        _source=_bytes.decode('ascii')
    except UnicodeDecodeError:
        _source=_bytes.decode('ascii',errors='replace')
    _shipped_ps1.append((_label,_source))
check(bool(_shipped_ps1),'no shipped PowerShell files found')
check(any(_label.endswith('/Finalize-LatticeVale-OverwritePatch.ps1') or _label == 'tools/Finalize-LatticeVale-OverwritePatch.ps1' for _label,_ in _shipped_ps1),
      'overwrite-patch finalizer is missing from shipped PowerShell audit coverage')
for _label,_source in _shipped_ps1:
    for _lineno,_line in enumerate(_source.splitlines(),1):
        for _match in re.finditer(r'\$([A-Za-z_][A-Za-z0-9_]*):',_line):
            check(_match.group(1).lower() in _allowed_ps_colon_prefixes,
                  f'PowerShell {_label} unbraced variable-before-colon at line {_lineno}: {_line.strip()}')

# Bash syntax
for rel in ('linux/bootstrap.sh','stack/configure-stack.sh','stack/manage.sh','stack/qmd-index-cycle.sh','stack/native-ollama-relay.sh'):
    r=subprocess.run(['bash','-n',str(ROOT/rel)],capture_output=True,text=True)
    check(r.returncode==0, f'bash -n failed for {rel}: {r.stderr.strip()}')

# Regression fixtures are executed exactly once by tests/run-regressions.py.  Keep this
# file a static/source audit instead of recursively spawning a manually-maintained subset.
runner=read('tests/run-regressions.py')
check('glob("*-fixtures.py")' in runner, 'regression runner must auto-discover *-fixtures.py')
check('subprocess.run' in runner, 'regression runner must execute discovered fixtures')

# Compose parse + expected security structure
try:
    compose=yaml.safe_load(compose_text) or {}
except Exception as e:
    compose={}; errors.append(f'compose YAML failed: {e}')
services=compose.get('services',{})
check('hermes' in services,'core hermes service missing')
check(len(services)==12,f'expected 12 compose services, got {len(services)}')
check('/var/run/docker.sock' not in compose_text,'Docker socket must not be mounted into Hermes')
check('tailscale/tailscale' not in compose_text,'Tailscale must not run inside WSL/Docker')
check('${DASHBOARD_HOST_BIND:-127.0.0.1}:${DASHBOARD_HOST_PORT:-9119}:9119' in compose_text,'Dashboard must default to localhost through explicit bind variable')
check('${MATRIX_HOST_BIND:-127.0.0.1}:${MATRIX_HOST_PORT:-8008}:8008' in compose_text,'Matrix must default to localhost through explicit bind variable')
check('ollama' in services,'local Ollama service missing')
check('OLLAMA_NO_CLOUD' in compose_text,'Ollama cloud-disable setting missing')
check('profiles: ["local-ai"]' in compose_text,'Ollama local-ai profile missing')
check('./config/honcho/config.toml:/app/config.toml:ro' in compose_text,'Honcho local model config mount missing')
check('ollama' not in (services.get('honcho-api',{}).get('depends_on') or {}),'Honcho must not hard-depend on managed Ollama because Windows-native Ollama is supported')
check(any(str(x).startswith('windows.host:') for x in services.get('honcho-api',{}).get('extra_hosts',[])),'Honcho native-Windows Ollama host mapping missing')
check('OpenAI API key for Honcho' not in configure,'Honcho must not request a cloud OpenAI key')
check('LLM_OPENAI_API_KEY ollama-local' in configure,'Honcho local OpenAI-compatible dummy key missing')
check('ollama_openai_base_url' in configure and "f'base_url = {q(ollama_base)}'" in configure,'Honcho must route inference through the selected local Ollama backend')
check('VECTOR_DIMENSIONS = 1536' in configure and 'dimensions_mode = "always"' in configure,'Honcho local embedding dimensions configuration missing')
check('Use Ollama as the default Hermes AI provider?' in ps1,'Hermes local-AI choice missing')
check('LatticeVale-managed WSL/Docker Ollama can be installed automatically' in ps1,'native-vs-managed Ollama ownership guidance missing')
check("m['base_url']=base_url" in configure and '$(ollama_openai_base_url)' in configure,'Hermes selected Ollama endpoint configuration missing')
check('>=64000' not in configure and "int(m.get('context_length') or 0)==int(sys.argv[3])" in configure,'Hermes local-AI verifier must honor the memory-aware persisted Ollama context')

# v13 prerequisite-only WSL + recovery/diagnostic invariants
for forbidden in (
    'wsl.exe --import','wsl --import','--unregister','--set-version','wsl.exe --install','wsl --install',
    'wsl.exe --update','wsl --update','cloud-images.ubuntu.com','ubuntu-noble-wsl','Install-UbuntuWslDistro',
    'Select-LatticeValeStorageLocation','Enable-WindowsOptionalFeature','dism.exe','useradd',
):
    check(forbidden.lower() not in ps1.lower(), f'forbidden WSL/distro mutation remains: {forbidden}')
check('[string]$DistroName = \'\'' in ps1,'DistroName should be optional selector, not a created default distro')
check('Select-ExistingUbuntuDistro' in ps1,'existing distro selection function missing')
check('Get-UbuntuDistroInfo' in ps1,'Ubuntu distro eligibility probe missing')
check('Get-LatticeValeCompatibility' in ps1 and 'SupportedUbuntuVersions' in ps1,'single-source Ubuntu compatibility loader missing')
check('SUPPORTED_UBUNTU_VERSIONS="22.04 24.04 26.04"' in compatibility,'current Docker Ubuntu support matrix missing from compatibility.conf')
check("Add-DistroBlocker $result 'WSL1'" in ps1 and 'WSL2 is required' in ps1,'WSL2 distro requirement missing')
check('Get-DistroRegistrationInfo' in ps1 and 'registration.BasePath' in ps1,'registered existing distro storage check missing')
check('MinHostPartitionTotalGiBExclusive' in ps1 and 'MinHostPartitionFreeGiB' in ps1,'compatibility-driven storage thresholds missing')
check('Select-ExistingLinuxUser' in ps1 and 'does not create accounts' in ps1,'existing-user-only behavior missing')
check('Get-InstalledDockerConflictPackages' in ps1,'Docker conflict detection missing')
check('Allow replacement of these conflicting Docker packages?' in ps1,'required Docker conflict confirmation missing')
check('Reuse the existing unrecognized ~/hermes-stack directory?' in ps1,'existing stack-path collision confirmation missing')
check('function Copy-LocalFileToWslRoot' in ps1 and 'RedirectStandardInput' in ps1 and 'Stage through wsl.exe stdin' in ps1,'private stdin-based WSL staging missing')
check("'dd', \"of=$DestinationLinux\", 'status=none'" in ps1 and "Invoke-WslDirectCapture $Name 'root' 'chmod'" in ps1 and "cat > \"$1\"" not in ps1, 'WSL staging must use direct dd argv plus separate chmod; nested bash positional staging is forbidden')
# Private installer-file staging must remain independent of Windows drive automount/wslpath.
# v13.16.6 uses wslpath only in the dedicated Windows-native Obsidian vault converter.
_staging_start=ps1.find('function Copy-LocalFileToWslRoot')
_staging_end=ps1.find('function ',_staging_start+10)
_staging_body=ps1[_staging_start:_staging_end if _staging_end>_staging_start else len(ps1)]
check('wslpath' not in _staging_body,'private WSL staging must not depend on Windows drive automount/wslpath')
check('function Convert-WindowsLocalPathToWslPath' in ps1 and "'wslpath' @('-a','-u',$driveRootWindows)" in ps1 and "'wslpath' @('-a','-u',$full)" not in ps1,
      'Windows-native Obsidian vault translation must be bind-mount-safe and drive-root based')
check("'findmnt' @('-n', '-o', 'FSTYPE', '-T', $linuxPath)" in ps1 and "-not $linuxRoot.StartsWith('/mnt/')" not in ps1,
      'Obsidian vault translation must support custom WSL Windows-drive automount roots and verify Windows-backed storage')
check('This installer never installs, updates, imports, unregisters, converts, or repairs WSL distributions.' in ps1,'prerequisite-only WSL message missing')
check("Get-WindowsOptionalFeatureStateSafe 'Microsoft-Windows-Subsystem-Linux'" in ps1,'WSL optional component diagnostic missing')
check('legacy/inbox feature state is advisory for WSL2' in ps1 and 'Continuing to functional WSL/distro checks' in ps1,'modern Store/MSI WSL must not be blocked solely by legacy optional-feature state')
check('throw "Windows Subsystem for Linux optional feature is' not in ps1,'legacy optional-feature state must not be a fatal WSL2 prerequisite')
check('WSL_HOST_E_UNEXPECTED' in ps1 and 'Repair-LatticeVale-WslHost.ps1' in ps1,'E_UNEXPECTED host-repair diagnostic missing')
check('no Linux distribution is registered' in ps1,'zero-distro WSL must be rejected')
check("@('--version')" in ps1 and 'legacy/inbox-compatible WSL' in ps1,'modern + legacy WSL implementation detection missing')
check('ConvertFrom-WslCliOutput' in ps1 and '.Replace([string][char]0, [string]::Empty)' in ps1,'WSL output normalization missing')
check('Get-WslOsRelease' in ps1 and "'cat' @('/etc/os-release')" in ps1,'direct os-release distro probe missing')
check("'cat' @('/etc/lsb-release')" in ps1,'lsb-release fallback probe missing')
check('ConvertFrom-OsReleaseText' in ps1,'PowerShell-side os-release parser missing')
check('printf \"%s|%s|%s' not in ps1,'fragile shell-expanded distro identity probe still present')


# Full distro diagnostics / failure-classification behavior
check('Invoke-NativeProcessCapture' in ps1 and 'WaitForExit($TimeoutSeconds * 1000)' in ps1,'bounded native/WSL probe helper missing')
check('TimedOut = $true' in ps1 and 'UNRESPONSIVE' in ps1,'probe timeout classification missing')
check('Get-LinuxFilesystemInfo' in ps1 and "'df' @('-Pk', '/')" in ps1,'Linux VHD/root filesystem diagnostic missing')
check('Show-DistroDiagnostic' in ps1 and 'Host partition ..' in ps1 and 'Linux filesystem' in ps1,'per-distro multidimensional diagnostics missing')
check('BlockerCodes' in ps1 and 'STORAGE_FREE_LOW' in ps1 and 'UNLAUNCHABLE' in ps1,'structured distro blocker codes missing')
check('LegacyInstallerArtifact' in ps1 and 'Older pre-LatticeVale distro name detected' in ps1,'legacy pre-LatticeVale distro reporting missing')
check('No new Ubuntu installation is required.' in ps1,'storage-only failure must not tell user to reinstall Ubuntu')
check('Get-SafeDiagnosticExcerpt' in ps1 and 'WSL output:' in ps1,'meaningful sanitized WSL probe error reporting missing')
check("'compatibility.conf'" in ps1 and "Copy-LocalFileToWslRoot $DistroName (Join-Path $PSScriptRoot 'compatibility.conf')" in ps1,'compatibility.conf must be required and staged into WSL')


# v13 recovery architecture
for phrase in ('Resume / repair installation','Change installed components','Verify installation only','Reconfigure providers/profiles','Advanced recovery'):
    check(phrase in ps1, f'missing recovery mode: {phrase}')
check('schema = 19' in ps1,'v14 options schema missing')
check('STATE_FILE=".installer-state.json"' in configure,'installer state file missing')
check('state_stage_current "$stage" && "$verifier"' in configure,'checkpoint skip must require live verifier')
check('post-stage verification failed' in configure,'post-stage live verification missing')
for stage in ('prepare_config','infrastructure','matrix_bootstrap','provider_setup','profiles','matrix_profiles','matrix_cross_signing','matrix_profile_cross_signing','integrations','reconcile','kanban_gateway','finalize'):
    check(f'run_stage {stage} ' in configure, f'missing resumable stage: {stage}')
check('state-audit.py' in bootstrap and 'state-audit.py' in ps1,'state audit must ship into existing stack')
check('installer-config.tar.gz' in bootstrap,'pre-change installer config backup missing')
check('audit) python3 ./state-audit.py --stack . ;;' in manage,'manage.sh audit command missing')
check('rebuildMatrixIdentity' in configure and 'hermes_recovery_' in configure,'explicit Matrix identity recovery missing')
check('Automatic identity replacement is unsafe.' in configure,'normal Matrix repair must not silently replace identity')
check('.installer-state.json' in readme and 'The state file is only a hint' in readme,'README state authority rule missing')
check('NEEDS_REPAIR' in state_audit and 'OUTDATED' in state_audit and 'STARTING' in state_audit,'state audit recovery/startup classification missing')
check('logs/installer-events.jsonl' in configure,'structured recovery event log missing')
check('Set-InstallerWindowsState' in ps1 and "'stage':'windows'" in ps1,'Windows recovery event recording missing')
check('Show-WindowsRecoveryAudit' in ps1 and 'Test-WingetPackageInstalled' in ps1,'live Windows verify-only audit missing')

# v13 interrupted-install / cross-user hardening
check('INSTALLER_VERSION="$(opt_text installerVersion)"' in configure,'dynamic installer bundle version missing from checkpoint identity')
check("payload=json.dumps({'options':d}" in configure and "{'installerVersion':ver,'options':d}" not in configure,'checkpoint fingerprint must be stable across bundle-version-only changes')
check('QMD_VERSION=2.5.3' in configure and 'QMD_VERSION:-2.5.3' in compose_text,'QMD must be pinned to tested 2.5.3 instead of latest')
check('docker compose build --pull qmd' in configure and '--no-cache qmd' not in configure,'QMD repair should reuse Docker build cache')
check('start_qmd_resilient' in configure and 'qmd_quarantine_index' in configure,'QMD backup-first self-repair missing')
check('docker compose up -d --pull never --no-build --no-deps qmd' in configure,'QMD must start independently for diagnosable health failures')
check('quote_env_key_literal secrets/hermes-runtime.env HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH' in configure,'Compose-safe dashboard hash migration missing')
check('HOME: /tmp/qmd-home' in compose_text and 'INDEX_PATH: /home/node/.cache/qmd/index.sqlite' in compose_text,'QMD arbitrary-UID runtime path hardening missing')
check('Convert-LinuxPathToWslUnc' in ps1 and '$stackLinuxPath' in ps1,'custom Linux home UNC conversion missing')
check("$nativeArch -ne 'X64'" in ps1,'unverified architectures must be rejected as ineligible')

# Docker current official Ubuntu install shape
check('docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc' in bootstrap,'Docker conflict package set missing')
check('/etc/apt/sources.list.d/docker.sources' in bootstrap,'current Docker deb822 sources file missing')
check('/etc/apt/keyrings/docker.asc' in bootstrap,'current Docker ASCII keyring path missing')
check('SUPPORTED_UBUNTU_VERSIONS' in bootstrap and '. "$compat_file"' in bootstrap,'bootstrap must consume compatibility.conf instead of duplicating Ubuntu versions')
check('docker_required_packages=(docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin)' in bootstrap and 'for pkg in "${docker_required_packages[@]}"' in bootstrap,'Docker readiness must require all official packages')
check('start_docker_daemon' in bootstrap and 'service docker start' in bootstrap and 'nohup dockerd' in bootstrap,'systemd/non-systemd Docker startup compatibility missing')
check('selected_infrastructure_services() {' in configure and 'An empty selection is valid.' in configure and 'return 0\n}' in configure[configure.index('selected_infrastructure_services() {'):configure.index('service_ready_for_local_repair()')], 'empty optional infrastructure selection must return success under ERR tracing')

# Existing optional-service behavior retained
for phrase in ('Install Hermes Dashboard?','Create multiple Hermes profiles?','Enable Hermes Kanban?','Install Matrix/Synapse?',
               'Use Windows Tailscale for private remote access?','Install SearXNG + Valkey?','Install QMD?','Install fully self-hosted Honcho memory?',
               'Install/configure Obsidian for Windows?','Enable unattended Ubuntu security updates?',
               'Start the stack automatically at Windows logon?'):
    check(phrase in ps1, f'missing user-facing option: {phrase}')
check('Install Ubuntu Pro for WSL?' not in ps1 and 'Canonical.UbuntuProforWSL' not in ps1 and 'ubuntuPro' not in ps1,'Ubuntu Pro must not remain a current LatticeVale installer/config option')
check('POLICY_VERSION=4' in configure and 'saved_version" != 4' in manage and 'values.get("POLICY_VERSION") != "4"' in state_audit,'adaptive resource policy v4 convergence/audit markers missing')
check('/etc/sysctl.d/99-latticevale-redis-valkey.conf' in bootstrap and 'vm.overcommit_memory = 1' in bootstrap and 'sysctl -w vm.overcommit_memory=1' in bootstrap,'Redis/Valkey overcommit prerequisite missing')
check('$description.Length -le 240' in ps1,'profile description 240-char guard missing')
check('dashboard_auth/basic' in configure,'Dashboard auth plugin configuration missing')
check("host='hermes' if name=='default' else 'hermes.'+name" in configure,'Honcho profile host keys must use hermes.<profile>')
check('HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH' in configure,'hashed Dashboard password missing')
check("if 'kanban' not in tools: tools.append('kanban')" in configure,'explicit Kanban toolset opt-in missing')
check("kanban['dispatch_interval_seconds']=30" in configure and "kanban['auto_decompose_per_tick']=1" in configure,
      'conservative automatic Kanban dispatcher settings missing')
check("kanban['max_in_progress']=int(opts.get('kanbanMaxInProgress') or 2)" in configure and
      "kanban['max_in_progress_per_profile']=int(opts.get('kanbanMaxInProgressPerProfile') or 1)" in configure,
      'Kanban provider-pressure concurrency caps missing')
check('HERMES_AUTO_KANBAN_POLICY_START' in configure and 'normal chat/gateway turn is not a claimed Kanban worker' in configure and 'HERMES_KANBAN_TASK' in configure,
      'installer-owned automatic Kanban task-context policy missing')
check('HERMES_SKILL_MANAGEMENT_POLICY_START' in configure and 'Never repeat an identical failing `skill_manage` request' in configure,
      'installer-owned skill-management recovery policy missing')
check('version: "1.2.0"' in configure and '"action": "modify"' in configure and '_modify' in configure and '_guard_kanban_tool' in configure,
      'Kanban runtime plugin must use current guarded block/shallow-modify pre_tool_call semantics')
check("skills_cfg.setdefault('write_approval',False)" in configure,
      'agent-managed skill write default/preservation logic missing')
check("kanban['review_dispatch']=canonical_review" in configure and 'canonical_assignee' in configure,
      'portable canonical Kanban routing/review policy missing')
check('MATRIX_REACTIONS true' in configure and 'MATRIX_APPROVAL_REQUIRE_SENDER true' in configure,
      'Matrix clickable approval reaction settings missing')
check('${OBSIDIAN_VAULT_HOST_PATH:-./vault}:/vault:rw' in compose_text and
      compose_text.count('${OBSIDIAN_VAULT_HOST_PATH:-./vault}:/vault:ro') >= 2,
      'Windows-native Obsidian host vault must feed Hermes and QMD through /vault')
check('QMD_INDEX_INTERVAL: ${QMD_INDEX_INTERVAL:-7200}' in compose_text and 'QMD_INDEX_INTERVAL:-7200' in read('stack/qmd-index-cycle.sh'),
      'built-in QMD index cadence must default to two hours')
check('function Repair-LegacyObsidianStackVaultMount' in ps1 and "Reconciling legacy Obsidian vault mounts" in ps1,
      'legacy host-level Obsidian bind-mount reconciliation missing')
check('.latticevale-v14.1.3.bak' in ps1 and 'backup="${fstab}.latticevale-v14.1.3.bak"' in ps1 and "'umount' @('-l', '--', $vaultPath)" in ps1,
      'legacy Obsidian bind mount must be backed out with fstab backup and bounded detach fallback')
check('HERMES_QMD_REINDEX' in configure and "grep -v 'HERMES_QMD_REINDEX'" in configure,
      'legacy duplicate QMD cron reconciliation missing')
check('hermes kanban init' in configure,'Kanban initialization missing')
check('tailscale serve reset' not in (ps1+configure+manage).lower(),'must not globally reset Tailscale Serve')
check('[[ "$(opt_bool tailscaleDashboard)" == true ]] && DASHBOARD_HOST_BIND=0.0.0.0' in configure,'Dashboard WSL interface bind must be conditional on Tailscale exposure')
check('[[ "$(opt_bool tailscaleMatrix)" == true ]] && MATRIX_HOST_BIND=0.0.0.0' in configure,'Matrix WSL interface bind must be conditional on Tailscale exposure')
check('LatticeVale-WslNativeRelay.ps1' in ps1,'Windows-native WSL relay helper must be bundled')
check("transport='windows-native-tcp-relay'" in ps1,'native relay transport metadata missing')
check('new TcpListener(IPAddress.Loopback, listenPort)' in relay,'native Windows loopback TCP listener missing')
check("Invoke-WslDistroCommand $DistroName 'root' '/usr/local/sbin/hermes-stack-start'" in relay,'native relay must start/recover the installer-owned Hermes stack')
check('listener.Start(128); // synchronous bind' in relay,'native relay must surface loopback bind failures synchronously')
check('-RestartCount 5' in ps1 and '-RestartInterval (New-TimeSpan -Minutes 1)' in ps1,'native relay task restart-on-failure policy missing')
check('interface portproxy add' not in relay.lower() and 'netsh.exe' not in relay.lower(),'v13.16.3 relay must not depend on netsh portproxy')
check('Migration cleanup only: v13.12.x used netsh portproxy' in ps1,'legacy portproxy cleanup boundary missing')
check("@('serve','status','--json')" in ps1 and "@('serve','get-config','--all')" in ps1,'Tailscale Serve status/full-config collision checks missing')
check('Get-AuthenticodeSignature -LiteralPath $installer' in ps1 and "$signerSubject -notmatch '(?i)tailscale'" in ps1, 'direct Tailscale download must be Authenticode-verified before execution')
check('matrixdotorg/synapse:v1.158.0' in configure and 'matrixdotorg/synapse:v1.158.0' in compose_text,'Synapse must be pinned to the current tested stable release')
check('/_matrix/client/v3/capabilities' in configure and 'm.room_versions' in configure,'Matrix room-version capability negotiation missing')
check('LATTICEVALE_MATRIX_ROOM_VERSION=10' in configure and "cfg['default_room_version']='10'" in configure,'LatticeVale-managed Matrix room version must be pinned to v10')
check('matrix_client_api_ready()' in configure and '/_matrix/client/versions' in configure and 'ensure_matrix_online()' in configure,'Matrix Client-Server readiness/order guard missing')
check('wait_matrix_room_join()' in configure and 'failures >= 3' in configure and 'return 2' in configure,'Matrix profile join wait must stop on sustained homeserver outage')
check('MATRIX_PREVIOUS_ROOM' in configure and 'backups/matrix-room-v10-' in configure,'managed non-v10 Matrix room preservation/replacement migration missing')
check('room_version:$rv' in configure and 'm.room.encryption' in configure,'explicit stable encrypted Matrix room creation missing')
check('MATRIX_E2EE_MODE required' in configure and 'MATRIX_DEVICE_ID' in configure,'Matrix required-E2EE/stable device configuration missing')
check('MATRIX_RECOVERY_KEY_OUTPUT_FILE' in configure and 'MATRIX_RECOVERY_KEY' in configure,'Matrix recovery-key capture/persistence support missing')
check("cfg.pop('multiplex_profiles',None)" in configure and "gateway['multiplex_profiles']=False" in configure,'LatticeVale standalone per-profile gateway topology normalization missing')
check('remove_env_keys secrets/hermes-runtime.env GATEWAY_MULTIPLEX_PROFILES' in configure,'container-level multiplex opt-in cleanup missing')
check('remove_env_keys "$f" GATEWAY_MULTIPLEX_PROFILES' in configure,'per-profile multiplex environment override cleanup missing')
check('gatewayTopology' in state_audit and 'yaml_multiplex_enabled' in state_audit,'read-only audit must detect unsafe multiplex opt-in')
check('run_stage matrix_cross_signing' in configure and 'cross-signing verified via recovery key' in configure,'Matrix cross-signing verification stage missing')
check('crypto.db' in configure and 'never delete crypto.db here' in configure,'Matrix repair must explicitly preserve the existing crypto identity')
check("Get-OptionTcpPort $existingOptions 'tailscaleMatrixPort' 443" in ps1 and "Get-OptionTcpPort $old 'tailscaleMatrixPort' 443" in ps1 and "Read-TcpPort 'Matrix Tailscale HTTPS port' $defaultMatrixPort $disallow" in ps1,'Matrix Tailscale endpoint must default to standard HTTPS 443')
check('Get-TailscaleHttpsUrl' in ps1 and 'if ($Port -eq 443)' in ps1,'Tailscale URL formatter must omit the default HTTPS port')
check("@('serve','--bg'" in ps1 and 'http://127.0.0.1:$BackendPort' in ps1,'Tailscale Serve must remain persistent and tailnet-only')
check('if (Test-RelayTargetForServices $currentIp $services)' in relay and 'Find-ReachableWslIp $distro $services' in relay,'relay must prefer cached direct backend checks before WSL discovery')
check("Starting relay listeners without a live WSL target" in relay,'passive relay must be able to bind before WSL/Hermes starts')
check("docker exec -u hermes hermes-agent python -c 'import mautrix, olm'" in configure,'running Hermes Matrix E2EE dependency preflight missing')
check("cfg['default_room_version']=str(sys.argv[1])" in configure,'Synapse stable default_room_version hardening missing')
check('returned_bot_device_id' in configure,'Matrix stable bot device ID login verification missing')
check('stage_matrix_profiles() (' in configure and '/_synapse/admin/v2/users/$encoded_user' in configure,'profile-specific Matrix identity provisioning missing')
check('MATRIX_HOME_ROOM' in configure and 'MATRIX_ALLOWED_ROOMS' in configure,'profile Matrix room routing/allowlist missing')
check('secrets/matrix-profiles/$name.env' in configure and '.matrix-profiles/$name.info' in configure,'profile Matrix protected state/metadata missing')
check('hermes_model_configured "$pdir/config.yaml"' in configure and 'HERMES_MODEL=$model' in configure,'profile Matrix provisioning must remain bound to the configured profile/model')
check('matrix2.' not in configure and 'platforms.matrix2' not in configure,'invented second Matrix adapter namespace must never be generated')
check(('Windows Obsidian vault folder (explicit Windows-local path required)' in ps1 and 'Windows Obsidian vault folder [suggested:' not in ps1) if version in {'14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'} else (('Windows Obsidian vault folder [suggested: $defaultObsidianVault; Enter accepts]' in ps1) if version in {'14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21'} else ('Windows Obsidian vault folder [$defaultObsidianVault]' in ps1)),'initial installer questionnaire must collect an explicit Windows Obsidian vault path without a v14.3.22 suggestion')
check('/_matrix/client/v3/join/$encoded_room' not in configure,'installer must not pre-join Hermes before its fresh E2EE state store initializes')
check('/_matrix/client/v3/joined_rooms' in configure,'post-start Matrix auto-join verification missing')
check('start_or_restart_profile_gateway_exact()' in configure and 'action=start' in configure and 'action=restart' in configure,'profile Matrix gateway activation must distinguish stopped from running s6 services')
if version in {'14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}:
    check('LATTICEVALE_PROVISIONING_STATE pending-manual' in configure and './manage.sh matrix-profile-finish "$name"' in configure,'profile Matrix retry/manual-finish path missing')
else:
    check("wait_matrix_room_join \"$token\" \"$room_id\" \"Profile '$name' Matrix bot\" 45 \"$name\"" in configure,'profile Matrix join verification must track the exact named gateway')
check('/opt/data/logs/gateways/$name/current' in configure,'profile Matrix failure diagnostics must use the exact profile gateway log')
check('already installed / no upgrade available' in ps1.lower() or 'Test-WingetPackageInstalled' in ps1,'WinGet live-installed-state reconciliation missing')
check('LatticeVale stack auto-start attempt' in bootstrap and 'for attempt in 1 2 3' in bootstrap,'stack autostart retry hardening missing')
check('stack_dir=$stack_dir_q' in bootstrap and "bash -c 'cd \"\\$1\"" in bootstrap and 'bash \"\\$stack_dir\"' in bootstrap,'stack-start helper must use explicit configured stack directory, not generator/root HOME')
check('/root/hermes-stack' not in bootstrap and 'cd \"$HOME/hermes-stack\"' not in bootstrap,'stack-start helper must not hardcode or derive the stack from root HOME')
check("[version]'2.5.4'" in ps1 and 'instanceIdleTimeout=-1' in ps1,'WSL 2.5.4+ instance lifetime policy missing')
check('vmIdleTimeout=-1' not in ps1,'installer must not conflate distro instance idle timeout with VM idle timeout')
check('Test-LatticeValeWslPersistence $DistroName 75' in ps1,'post-config WSL lifetime verification missing')
check("Get-OptionValue $old 'autoStart' $false" in ps1 and "Get-OptionValue $existingOptions 'autoStart' $false" in ps1,'full stack auto-start must default off when no prior explicit selection exists')
check('Register-LatticeValeBridgeRefreshTask $bridgePaths $true $autoStart' in ps1,'relay must start independently while WSL wake/recovery remains tied to explicit stack auto-start')
check("if ($EnsureStackRunning) { $relayArgs += '-EnsureDistroRunning' }" in ps1,'relay must only receive WSL wake/recovery permission from explicit stack auto-start')
check('control_windows_bridge start' in manage and 'control_windows_bridge stop' in manage,'manual manage.sh lifecycle must coordinate the Windows relay task')
check('start_selected_matrix_profile_gateways' in manage and "select(.matrix.enabled == true)" in manage, 'manage.sh start/restart/update must reconcile only installer-selected Matrix profile gateways')
check(r'runuser -u "\$stack_user" -- env -u DOCKER_CONTEXT' in bootstrap,'stack auto-start must run Compose as the selected Ubuntu user')
check('-RestartCount 3' in ps1 and 'LastTaskResult' in ps1 and 'autoStartValidated' in ps1,'Windows stack auto-start task execution validation/retry missing')
check('docker exec -u hermes hermes-agent hermes' in configure,'Hermes CLI should run unprivileged')
if version in {'14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}:
    check("integrations) printf '4' ;;" in configure,'v14.4.7+ integration migration revision missing')
    check("web['extract_backend']='latticevale-local'" in configure,'v14.4.7+ keyless extract backend selection missing')
    check('latticevale-web-extract' in configure and 'register_web_search_provider' in configure,'v14.4.7+ web extraction plugin generation missing')
    check('create_ssrf_safe_client' in configure and 'follow_redirects=False' in configure and 'normalize_url_for_request' in configure and 'sensitive_query_param_name' in configure and 'is_safe_url' in configure,'v14.4.7+ extractor network-safety boundaries missing')
    check("browser['cloud_provider']='local'" in configure and "browser.setdefault('engine','auto')" in configure,'v14.4.8 free local-browser reliability default missing')
    check("web_extract_aux.setdefault('timeout',360)" in configure,'v14.4.8 web-extract auxiliary timeout repair missing')
if version in {'14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}:
    check('& $powershellExe @helperArgs | Out-Host' in ps1,'v14.4.82 WSL helper diagnostics must bypass the function success-output return stream')
    check('$helperExitCode = [int]$LASTEXITCODE' in ps1 and 'return $helperExitCode' in ps1,'v14.4.82 WSL helper wrapper must return only the scalar native exit code')

check('chown -R "$linux_user:$linux_user" "$stack_dir"' not in bootstrap,'must not recursively chown persistent container data')

# Install ordering: selected infrastructure/Matrix must exist before Hermes provider setup.
# Missing markers are audit failures, not Python exceptions, so CI reports every
# regression in one run instead of terminating with ValueError.
check_before(configure, 'Preparing selected Docker infrastructure before Hermes setup.', 'DEFAULT Hermes profile provider/model selection follows.', 'supporting infrastructure must precede default Hermes provider/model selection')
check_before(configure, 'Matrix account setup: create one admin account and one Hermes bot account', 'DEFAULT Hermes profile provider/model selection follows.', 'Matrix bootstrap must precede default Hermes provider/model selection')
check_before(ps1, "Write-Step 'Bootstrapping Docker and the selected LatticeVale stack inside Ubuntu'", "Write-Step 'Installing selected Windows applications'", 'Windows add-ons must follow successful Linux stack bootstrap')

# README must make prerequisites unmistakable
for phrase in ('does not install, import, unregister, convert, move, or repair WSL itself','Existing Ubuntu **22.04, 24.04, or 26.04** distro running as **WSL2**','over 50 GiB total capacity','at least 50 GiB free'):
    check(phrase in readme, f'README missing prerequisite wording: {phrase}')
for bad in ('dedicated Ubuntu 24.04 WSL2 distro (created only if missing)','wsl --import <name>','-InstallLocation'):
    check(bad not in readme, f'README still documents old distro-creation behavior: {bad}')

# Lightweight PowerShell literal/delimiter smoke test.
def strip_ps_literals(text:str)->str:
    # Here-strings first.
    text=re.sub(r"@'[^\n]*\n(?s:.*?)^[ \t]*'@[ \t]*$",'',text,flags=re.M)
    text=re.sub(r'@"[^\n]*\n(?s:.*?)^[ \t]*"@[ \t]*$','',text,flags=re.M)
    out=[]; i=0; state='normal'
    while i<len(text):
        ch=text[i]
        if state=='normal':
            if ch=='#':
                j=text.find('\n',i)
                if j<0: break
                out.append('\n'); i=j+1; continue
            if ch=="'": state='single'; i+=1; continue
            if ch=='"': state='double'; i+=1; continue
            out.append(ch); i+=1; continue
        if state=='single':
            if ch=="'":
                if i+1<len(text) and text[i+1]=="'": i+=2; continue
                state='normal'
            i+=1; continue
        if state=='double':
            if ch=='`' and i+1<len(text): i+=2; continue
            if ch=='"': state='normal'
            i+=1; continue
    check(state=='normal',f'PowerShell string appears unterminated: {state}')
    return ''.join(out)

for label,source in _shipped_ps1:
    clean=strip_ps_literals(source)
    for l,r,n in (('{','}','braces'),('(',')','parentheses'),('[',']','brackets')):
        depth=0
        for c in clean:
            if c==l: depth+=1
            elif c==r:
                depth-=1
                if depth<0:
                    errors.append(f'PowerShell {label} {n} close before open'); break
        check(depth==0,f'PowerShell {label} {n} unbalanced: {depth}')

if errors:
    print('STATIC AUDIT: FAIL')
    for e in errors: print('-',e)
    raise SystemExit(1)
print(f'STATIC AUDIT: PASS (v{version})')
print(f'{len(services)} Compose services')
print(f'v{version} LatticeVale release + retained existing-WSL/recovery invariants verified')
