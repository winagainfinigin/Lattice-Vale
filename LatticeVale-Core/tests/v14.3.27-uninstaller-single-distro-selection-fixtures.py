#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}, version
un=(ROOT/'Uninstall-LatticeVale.ps1').read_text(encoding='ascii')

# Source invariant: both branches explicitly assign an array before numeric indexing.
assert "if ($candidates.Count -gt 0) { $shown=@($candidates) } else { $shown=@($distros) }" in un
assert "return $shown[$choice-1]" in un

# Regression model: the old scalar fallback indexed a string and returned 'U';
# preserving the one-item fallback as a collection returns the complete distro name.
distros=['Ubuntu-24.04']
old_scalar=distros[0]
assert old_scalar[0] == 'U'
shown=list(distros)
choice=1
assert shown[choice-1] == 'Ubuntu-24.04'

print('v14.3.27 uninstaller single-distro selection fixtures: PASS')
