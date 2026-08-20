from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2'}, version

ps = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
launcher = (ROOT / 'windows/LatticeVale-Shortcut.ps1').read_text(encoding='ascii')
cfg = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')
readme = (ROOT / 'README.md').read_text(encoding='utf-8')

# Shortcut configuration is backend-aware and records only the already-detected native app/API.
shortcut_cfg = ps[ps.index('function Install-LatticeValeDesktopShortcuts'):ps.index('function Remove-LatticeValeDesktopShortcuts')]
assert "[string]$OllamaBackend = 'managed'" in shortcut_cfg
assert "$OllamaBackend -eq 'windows-native'" in shortcut_cfg
assert 'nativeOllama = $nativeOllamaConfig' in shortcut_cfg
assert 'appExecutable = [string]$nativeState.AppExecutable' in shortcut_cfg
assert 'executable = [string]$nativeState.Executable' in shortcut_cfg
assert 'serviceName = [string]$nativeService.Name' in shortcut_cfg
assert 'apiEndpoint = [string]$nativeState.Endpoint' in shortcut_cfg
assert 'schema = 2' in shortcut_cfg
assert 'Install-LatticeValeDesktopShortcuts $DistroName $linuxUser $stackLinuxPath $bundleVersion $ollamaBackend' in ps

# Start probes native Ollama before WSL startup, leaves a healthy process untouched, and
# launches the tray app before using the CLI fallback. Shutdown does not stop Ollama.
start_fn = launcher[launcher.index('function Start-NativeOllamaForShortcut'):launcher.index("if (-not (Test-Path -LiteralPath $ConfigPath")]
assert 'Test-NativeOllamaApi $NativeConfig' in start_fn
assert 'already running; leaving the existing process untouched' in start_fn
assert 'Start-Service -Name $serviceName' in start_fn
assert 'Start-Process -FilePath $app' in start_fn
assert "Start-Process -FilePath $cli -ArgumentList @('serve')" in start_fn
assert 'will not launch a duplicate `ollama serve`' in start_fn
assert 'AddSeconds(45)' in start_fn
start_action = launcher[launcher.index("if ($Action -eq 'Start')"):launcher.index('$running = Get-RunningWslDistros')]
assert start_action.index('Start-NativeOllamaForShortcut $nativeConfig') < start_action.index('/usr/local/sbin/hermes-stack-start')
shutdown_action = launcher[launcher.index('$running = Get-RunningWslDistros'):]
assert 'Stop-Process' not in shutdown_action
assert 'Stop-Service' not in shutdown_action

# Pending-manual Matrix profiles are resumable, resource-valid state. The profile stage
# may complete without aborting the core install, but checkpoint bypass forces every
# Resume / repair back through the activation attempt until it succeeds.
verify = cfg[cfg.index('verify_matrix_profiles() {'):cfg.index('verify_matrix_profile_cross_signing() {')]
pending_start = verify.index('if [[ "$provisioning_state" == pending-manual ]]')
pending_end = verify.index('    fi', pending_start) + len('    fi')
pending = verify[pending_start:pending_end]
assert 'continue' in pending and 'return 1' not in pending
assert 'matrix_profile_activation_pending()' in cfg
assert 'matrix_profiles) matrix_profile_activation_pending ;;' in cfg

# Completed profiles still receive joined room/version checks. Gateway runtime health is
# retried separately so a stopped named gateway cannot invalidate the identity/room transaction.
completed = verify[pending_end:]
assert 'matrix_room_version "$token" "$room_id"' in verify
assert '/_matrix/client/v3/joined_rooms' in completed
assert '[[ "$gateway_state" == up ]] || return 1' not in verify

assert 'Start LatticeVale' in readme
assert 'pending-manual' in readme

print('v14.3.25 native Ollama shortcut + Matrix pending verification fixtures: PASS')
