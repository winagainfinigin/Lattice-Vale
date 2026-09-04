from pathlib import Path

root = Path(__file__).resolve().parents[1]
ps = (root / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
assert (root / 'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}

# Native process capture must preserve stdout/stderr independently while keeping a
# combined Text field for failure diagnostics.
assert 'StdOut = $cleanStdOut; StdErr = $cleanStdErr' in ps
assert '$cleanStdOut = ConvertFrom-WslCliOutput @($stdout)' in ps
assert '$cleanStdErr = ConvertFrom-WslCliOutput @($stderr)' in ps

# A successful WSL direct probe must expose stdout only through Text. This prevents
# WSL startup diagnostics (notably /etc/fstab warnings) from corrupting JSON and
# other machine-readable output even though the Linux command itself returned 0.
needle = 'Text = $attempt.StdOut; StdOut = $attempt.StdOut; StdErr = $attempt.StdErr'
assert needle in ps
assert 'startup diagnostics (for example an /etc/fstab mount warning) on stderr' in ps

# Existing recovery paths still rely on direct capture, so they inherit isolation.
assert "Get-ExistingInstallOptions" in ps
assert '$probe.Text | ConvertFrom-Json' in ps
assert '$backupProbe.Text | ConvertFrom-Json' in ps

# Legacy Obsidian fstab cleanup remains in repair and should now be reachable even
# when that legacy entry itself causes WSL to emit a startup warning.
assert 'Repair-LegacyObsidianStackVaultMount $DistroName $stackLinuxPath' in ps
assert '.latticevale-v14.1.3.bak' in ps and 'backup="${fstab}.latticevale-v14.1.3.bak"' in ps

print('V13.16.9 WSL STDERR ISOLATION FIXTURES: PASS')
