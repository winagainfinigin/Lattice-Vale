from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ps1 = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
configure = (ROOT / 'stack' / 'configure-stack.sh').read_text(encoding='utf-8')
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'}
# Fresh installs must not expose the old default-heavy Quick setup path.
assert "questionnaireMode = 'explicit'" in ps1
assert "$script:RequireExplicitQuestionnaireChoices = $true" in ps1
assert 'Fresh-install policy: LatticeVale will not assume optional host/system settings.' in ps1
assert 'Choose setup questionnaire:' not in ps1
assert 'Quick setup — recommended defaults' not in ps1
# Generic questionnaire readers become non-defaulting while fresh explicit mode is active.
assert 'if ($script:RequireExplicitQuestionnaireChoices) { return Read-YesNoExplicit $Question $Default }' in ps1
assert 'if ($script:RequireExplicitQuestionnaireChoices) { return Read-IntegerExplicit $Question $Min $Max $Default }' in ps1
assert 'if ($script:RequireExplicitQuestionnaireChoices) { return Read-MenuExplicit $Question $Options $Default }' in ps1
assert 'Pressing Enter alone does not select it.' in ps1
assert 'suggested: $Default; explicit choice required' in ps1
# Distro/user/path/timezone decisions must be detected or explicitly confirmed, never guessed.
assert "Read-ChoiceExplicit \"Use '$($eligible[0].Name)'?\"" in ps1
assert "Read-ChoiceExplicit \"Use Ubuntu user '$($users[0])' for Hermes?\"" in ps1
assert "refusing to guess a /home/<user> path" in ps1
assert "Get-DetectedLinuxTimezone $DistroName $linuxUser" in ps1
assert "Get-OptionValue $old 'timezone' 'Etc/UTC'" not in ps1
# Remote access may warn, but cannot silently force a global WSL lifetime setting.
assert 'LatticeVale will preserve that choice; remote endpoints may become unavailable when WSL terminates.' in ps1
assert '$keepWslServicesRunning = $true\n    Write-Info \'Enabling persistent WSL service-instance lifetime' not in ps1
assert ("Use mirrored WSL networking as the shared mode for native Windows Ollama and Tailscale remote access?" not in ps1 and 'LatticeVale will not change global WSL networking' in ps1) if version in {'14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'} else (("Use mirrored WSL networking as the shared mode for native Windows Ollama and Tailscale remote access?" in ps1) if version in {'14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40'} else ("Read-ChoiceExplicit 'Switch global WSL2 networkingMode to nat" in ps1))
# Legacy external vault targets are inspected and explicitly detached before ownership/mode changes.
assert "Detach this legacy vault symlink?" in ps1
assert "Detach this existing vault mount from the LatticeVale stack path?" in ps1
assert "install' @('-d', '-m', '0750', '-o', ([string]$LinuxUid), '-g', ([string]$LinuxGid)" in ps1
# Linux configure must never chmod through a symlink/mountpoint.
assert 'if [[ -L vault ]]; then' in configure
assert 'if mountpoint -q -- vault' in configure
assert "chmod 0750 vault\n\n# Windows Obsidian" in configure
assert 'chmod 0750 vault workspace' not in configure
assert "not in ('quick','custom','explicit')" in configure
print('v14.3.4 explicit-host/vault fixtures: PASS')
