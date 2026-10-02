#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() == "14.6.2"
bootstrap_path = ROOT / "linux/bootstrap.sh"
bootstrap = bootstrap_path.read_text(encoding="utf-8")

# Regression for the original v14.6.2 bootstrap staging failure:
# a duplicated line-continuation made GNU install treat compatibility.conf as a directory.
bad = '''install -m 0644 -o "$linux_uid" -g "$linux_gid" \\
install -m 0644 -o "$linux_uid" -g "$linux_gid" \\
  "$bundle_root/compatibility.conf" "$stack_dir/compatibility.conf"'''
assert bad not in bootstrap
expected = '''install -m 0644 -o "$linux_uid" -g "$linux_gid" \\
  "$bundle_root/compatibility.conf" "$stack_dir/compatibility.conf"'''
assert expected in bootstrap
assert bootstrap.count('"$bundle_root/compatibility.conf" "$stack_dir/compatibility.conf"') == 1

# Public entrypoint distinguishes the hotfix without changing the machine-readable version.
wrapper = (REPO / "installer/Install-LatticeVale.ps1").read_text(encoding="utf-8")
assert "14.6.2 Hotfix" in wrapper

syntax = subprocess.run(["bash", "-n", str(bootstrap_path)], capture_output=True, text=True)
assert syntax.returncode == 0, syntax.stderr
print("V14.6.2 HOTFIX BOOTSTRAP STAGING FIXTURES: PASS")
