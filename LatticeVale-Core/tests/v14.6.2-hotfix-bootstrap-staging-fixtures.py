#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() == '14.6.8'
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
assert "$ReleaseDisplayVersion = $ReleaseVersion" in wrapper

syntax = subprocess.run(["bash", "-n", str(bootstrap_path)], capture_output=True, text=True)
assert syntax.returncode == 0, syntax.stderr
# Copy every explicit staged bundle file with the real GNU install utility.
# This reproduces the later 14.6.6 gateway.parked two-pair staging bug,
# which shell syntax checking alone does not detect.
import os
import re
import tempfile
pairs = re.findall(r'(?m)^install -m (0[0-7]{3}) -o "\$linux_uid" -g "\$linux_gid" \\\n  "\$bundle_root/([^"]+)" "\$stack_dir/([^"]+)"$', bootstrap)
assert len(pairs) >= 25, pairs
assert ('0755','stack/gateway-multiplex-verify.py','gateway-multiplex-verify.py') in pairs
assert ('0755','stack/gateway-park-policy.py','gateway-park-policy.py') in pairs
with tempfile.TemporaryDirectory() as td:
    target = Path(td)
    for mode, source, relative in pairs:
        source_file=ROOT/source
        assert source_file.is_file(), source_file
        result=subprocess.run(['install', '-m', mode, '-o', str(os.getuid()), '-g', str(os.getgid()),
                               str(source_file), str(target/relative)], text=True, capture_output=True)
        assert result.returncode == 0, (source,relative,result.stderr)
        assert (target/relative).read_bytes()==source_file.read_bytes()
        assert ((target/relative).stat().st_mode & 0o777) == int(mode,8)

print("V14.6.2 HOTFIX BOOTSTRAP STAGING FIXTURES: PASS")
