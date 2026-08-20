from pathlib import Path

root = Path(__file__).resolve().parents[1]
text = (root / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')

start = text.index('function Invoke-BundledStackAudit')
end = text.index('function Set-InstallerWindowsState', start)
block = text[start:end]

# Audit staging is private/root-owned and no longer depends on the WSL UNC provider.
assert "Invoke-WslDirectCapture $Name 'root' 'install' @('-d', '-m', '0755', $stageLinux)" in block
assert 'Copy-LocalFileToWslRoot $Name $auditSource "$stageLinux/state-audit.py"' in block
assert 'Copy-Item -LiteralPath $auditSource' not in block
assert "Invoke-WslDirectCapture $Name 'root' 'rm' @('-rf', $stageLinux)" in block

# Main staging likewise streams files through wsl.exe stdin and never opens a 0777 window.
assert 'function Copy-LocalFileToWslRoot' in text
assert 'RedirectStandardInput' in text
assert 'Stage through wsl.exe stdin' in text
assert "'0700'" in text
assert "chmod -R 0777" not in text

# The persistent stack must never be made broadly writable by staging logic.
assert "chmod' @('0777', \"$LinuxHome/hermes-stack\")" not in text

print('AUDIT STAGING PERMISSIONS: PASS')
