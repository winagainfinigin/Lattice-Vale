from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.4.85','14.5.0','14.5.1','14.5.2'}, version

launcher = (ROOT / 'windows' / 'LatticeVale-Shortcut.ps1').read_text(encoding='ascii')
installer = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='ascii')
repair = (REPO / 'tools' / 'Repair-LatticeVale-WslHost.ps1').read_text(encoding='ascii')
root_readme = (REPO / 'README.md').read_text(encoding='utf-8')

# The installed shutdown launcher must never target-terminate the selected distro.
assert '& $wslExe --terminate $distro' not in launcher
assert 'manage.sh stop exited with code $stopExit' in launcher
assert 'intentionally left running to preserve WSL session transport' in launcher
assert '$manageCommand' not in launcher
assert 'bash -lc $manageCommand' not in launcher
assert '& $wslExe -d $distro -u $user --cd $stack -- ./manage.sh start' in launcher
assert '& $wslExe -d $distro -u $user --cd $stack -- ./manage.sh stop' in launcher
assert "schema = 4" in installer
assert 'Stop the selected LatticeVale services without terminating the WSL distro' in installer

# Fresh-install coverage: a clean install must get the fixed launcher on its first
# shortcut reconciliation. This must not depend on repair-mode drift detection.
assert "Copy-Item -LiteralPath $helperSource -Destination $paths.Helper -Force" in installer
assert "$config = [ordered]@{" in installer
assert "schema = 4" in installer
assert "Write-Step 'Reconciling optional Windows desktop shortcuts'" in installer
assert "if ($windowsShortcuts) {" in installer
assert "Install-LatticeValeDesktopShortcuts $DistroName $linuxUser $stackLinuxPath $bundleVersion $ollamaBackend" in installer
bootstrap = (ROOT / 'linux' / 'bootstrap.sh').read_text(encoding='utf-8')
assert 'install -m 0755 -o "$linux_uid" -g "$linux_gid"' in bootstrap
assert '"$bundle_root/stack/manage.sh" "$stack_dir/manage.sh"' in bootstrap
# Repair-only transport migration remains gated to an already-managed stack; a fresh
# install must not need a legacy helper or WSL transport reset before shortcut creation.
assert "$repairMaintenance = ($stackState -eq 'managed' -and $installMode -in @('resume','change','reconfigure','advanced','update'))" in installer

# Existing-install repair must recognize the exact legacy owned helper, reset host
# transport preservation-first, and then rely on normal shortcut reconciliation.
assert 'function Test-LatticeValeLegacyUnsafeShutdownShortcut' in installer
assert "Test-LatticeValeShortcutOwned $paths.ShutdownShortcut $paths" in installer
assert "--terminate\\s+\\$distro" in installer
assert 'function Invoke-LatticeValeLegacyShortcutWslTransportRepair' in installer
assert "Invoke-NativeProcessCapture 'wsl.exe' @('--shutdown') 45" in installer
assert "Restart-Service -Name 'WslService' -Force" in installer
assert 'Wait-LatticeValeWslResponsive $Name 120' in installer
assert 'Test-LatticeValeLegacyUnsafeShutdownShortcut $DistroName $linuxUser $stackLinuxPath' in installer
assert 'function Test-LatticeValeShortcutRuntimeContract' in installer
assert 'function Test-LatticeValeBrokenShortcutLauncher' in installer
assert 'schema 4 direct WSL --cd launcher verified' in installer
assert "Invoke-NativeProcessCapture 'wsl.exe' @('-d',$Name,'-u',$User,'--cd',$StackLinuxPath,'--','./manage.sh','stop') 240" in installer
assert 'Resume / repair will replace the helper/configuration' in installer

# The launch-recovery helper also resets the Windows WSL service after shutdown,
# but must not mutate distro registration or VHDX state as part of that recovery.
assert "Restart-Service -Name 'WslService' -Force" in repair
assert 'wsl.exe --terminate' not in repair

# Root public guidance must direct existing installs to the full current release
# and keep the source-only overwrite patch separate from live-stack repair.
assert ('# LatticeVale v14.5.2' in root_readme) if version == '14.5.2' else ('# LatticeVale v14.5.1' in root_readme)
assert ('For an existing LatticeVale installation, launch the **full v14.5.2 release**' in root_readme) if version == '14.5.2' else ('For an existing LatticeVale installation, launch the **full v14.5.1 release**' in root_readme)
assert 'choose **Resume / repair installation** first' in root_readme
assert 'The separate patch ZIP is for overwriting a source checkout, not for layering files over a live installed stack.' in root_readme

print('v14.4.84 WSL shortcut/transport fixtures: PASS')
