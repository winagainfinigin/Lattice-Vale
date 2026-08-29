#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT.parent
reset=(REL/'tools/Reset-LatticeVale-CleanHost.ps1').read_text(encoding='ascii')
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85'}, version
assert 'function Get-OptionalPropertyString' in reset
assert 'function Get-ScheduledTaskActionText' in reset
assert "$Object.PSObject.Properties[$Name]" in reset
assert "foreach ($name in @('Type','Id','Execute','Path','Arguments','WorkingDirectory','ClassId','Data'))" in reset
assert 'Get-ScheduledTaskActionText $_' in reset
# Regression: never blindly dereference Exec-only members on every action.
assert '([string]$_.Execute)' not in reset
assert '([string]$_.Arguments)' not in reset
assert '([string]$_.WorkingDirectory)' not in reset
# Ownership and destructive boundaries remain intact.
assert 'if (-not (Test-TextOwned $blob)) { continue }' in reset
assert "Type CLEAN-RESET to continue" in reset
assert 'Remove-HnsNetwork' not in reset
assert 'tailscale serve reset' not in reset.lower()
print('v14.3.43 scheduled-task action compatibility fixtures: PASS')
