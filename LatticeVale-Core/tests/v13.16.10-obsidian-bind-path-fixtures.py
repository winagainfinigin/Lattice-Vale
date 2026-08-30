from pathlib import Path

root = Path(__file__).resolve().parents[1]
ps = (root / 'Install-LatticeVale.ps1').read_text()
assert (root / 'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1'}

start = ps.index('function Convert-WindowsLocalPathToWslPath')
end = ps.index('\nfunction Repair-LegacyObsidianStackVaultMount', start)
body = ps[start:end]

# The full vault path must not be sent through wslpath: active bind mounts can
# canonicalize it to the bind target and break Resume / repair.
assert "'wslpath' @('-a','-u',$full)" not in body
assert '$driveRootWindows = $full.Substring(0, 2)' in body
assert "'wslpath' @('-a','-u',$driveRootWindows)" in body
assert "$relativeLinux = $relativeWindows.Replace('\\', '/')" in body
assert '$linuxPath = if ([string]::IsNullOrWhiteSpace($relativeLinux))' in body
assert "'test' @('-d', $linuxPath)" in body
assert "-not $linuxRoot.StartsWith('/mnt/')" not in body
assert "'findmnt' @('-n', '-o', 'FSTYPE', '-T', $linuxPath)" in body
assert "@('9p','drvfs','fuseblk','ntfs','ntfs3')" in body

print('V13.16.10 OBSIDIAN BIND PATH FIXTURES: PASS')
