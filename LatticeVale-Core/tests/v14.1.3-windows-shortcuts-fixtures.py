#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ps1=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
launcher=(ROOT/'windows/LatticeVale-Shortcut.ps1').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
readme=(ROOT/'README.md').read_text(encoding='utf-8')

# The feature is explicit and persisted; legacy Resume does not create desktop artifacts unexpectedly.
assert "Read-Choice 'Create Windows desktop shortcuts to start and shut down this LatticeVale install?'" in ps1
assert "Get-OptionValue $existingOptions 'windowsShortcuts' $false" in ps1
assert 'windowsShortcuts = $windowsShortcuts' in ps1
assert "$windowsShortcuts = [bool](Get-OptionValue $existingOptions 'windowsShortcuts' $false)" in ps1
assert 'LatticeVale-Shortcut-$safeName-$safeUser-$suffix.ps1' in ps1, 'shortcut helper must be unique per LatticeVale install'

# Shortcuts bind to the actual distro/user/managed stack, not hard-coded local machine names.
assert 'Get-LatticeValeShortcutPaths([string]$Name, [string]$User, [string]$StackLinuxPath)' in ps1
for forbidden in ('Ubuntu-Example', 'examplelinuxuser', 'ExampleWindowsUser'):
    assert forbidden not in launcher
assert 'distroName = $Name' in ps1
assert 'linuxUser = $User' in ps1
assert 'stackLinuxPath = $StackLinuxPath' in ps1

# Start follows installer-selected service intent through manage.sh, after using the root helper to ensure Docker is available.
assert '/usr/local/sbin/hermes-stack-start' in launcher
assert '$manageCommand' not in launcher
assert 'bash -lc $manageCommand' not in launcher
assert '& $wslExe -d $distro -u $user --cd $stack -- ./manage.sh start' in launcher
assert '& $wslExe -d $distro -u $user --cd $stack -- ./manage.sh stop' in launcher

# Shutdown is per-distro and idempotent: do not globally terminate every WSL distro and do not wake an already-stopped distro.
assert '--list --running --quiet' in launcher
assert "if (-not ($running -contains $distro))" in launcher
assert '& $wslExe --terminate $distro' not in launcher
assert 'manage.sh stop exited with code $stopExit' in launcher
assert 'intentionally left running to preserve WSL session transport' in launcher
assert '& $wslExe --shutdown' not in launcher

# Desktop .lnk launch uses process-only Bypass, hidden UI, and the source-visible helper.
assert "'-ExecutionPolicy', 'Bypass'" in ps1
assert "'-WindowStyle', 'Hidden'" in ps1
assert "'windows\\LatticeVale-Shortcut.ps1'" in ps1
assert 'LatticeVale-Shortcut.ps1' in ps1

assert 'start_selected_matrix_profile_gateways' in manage, 'manage.sh must reconcile selected Matrix profile gateways on Start'
assert 'docker compose up -d --pull never --no-build; start_selected_matrix_profile_gateways' in manage, 'Start shortcut lifecycle must restore selected Matrix profile gateways'
assert 'select(.matrix.enabled == true)' in manage, 'gateway reconciliation must be driven by the installer-selected profile objects'

assert "Join-Path $env:LOCALAPPDATA 'LatticeVale'" in ps1
assert 'return "LatticeVale Stack - $safe-$suffix"' in ps1
assert 'Get-LegacyV14ScheduledTaskName' in ps1 and 'Get-LegacyV14ShortcutPaths' in ps1

# Ownership safety: never overwrite/delete a same-name shortcut unless it resolves to this exact LatticeVale helper/config pair.
assert 'Test-LatticeValeShortcutOwned' in ps1
assert 'A non-LatticeVale shortcut already exists' in ps1
assert 'is not provably LatticeVale-owned and was left untouched' in ps1
assert 'Remove-LatticeValeDesktopShortcuts' in ps1

# Windows-side audit/state exposes shortcut drift as optional follow-up rather than hiding it.
assert 'Windows desktop shortcuts:' in ps1
assert 'shortcuts = @{ status = $shortcutState; detail = $shortcutDetail }' in ps1

# Technical documentation explains that manage.sh makes the shortcuts option-aware.
assert 'Windows Start/Shutdown shortcuts' in readme
assert 'manage.sh' in readme

print('V14.3.0 WINDOWS SHORTCUT FIXTURES: PASS')
