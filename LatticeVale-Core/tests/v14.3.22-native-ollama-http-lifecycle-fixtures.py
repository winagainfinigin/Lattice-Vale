from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='ascii')
version=(ROOT/'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}

# WSL application-level HTTP proof is direct and authoritative; no heredoc is required.
http=ps[ps.index('function Test-WslHttpEndpointDirect'):ps.index('function Get-WslIpv4Candidates')]
assert "'curl' @('-fsS','--noproxy','*','--connect-timeout','4','--max-time','8',$url)" in http
assert "'python3' @('-c',$pythonCode,$HostAddress,[string]$Port,$Path)" in http
assert 'ConvertFrom-Json' in http and 'payload.version' in http
assert "bash' @('-lc'" not in http

# Existing direct API success is recognized before synthetic private-relay probing.
bridge=ps[ps.index('function Get-LatticeValeNativeBridgeCapability'):ps.index('function Test-WindowsTcpPortInUse')]
assert bridge.index('First trust the application-level endpoint') < bridge.index('synthetic TCP listener')
assert 'DirectApiReachable = $false' in bridge
assert "Test-WslHttpEndpointDirect $Name $directHost $targetPort '/api/version'" in bridge
assert 'Test-WindowsNativeOllamaDirectBindingDurable $targetPort' in bridge

# A transient but currently-working direct path is stabilized without an unnecessary restart.
resolve=ps[ps.index('function Resolve-LatticeValeNativeOllamaDirectFallback'):ps.index('function Get-LatticeValeNativeBridgeCapability')]
assert 'Persist and verify the currently working direct WSL access to native Windows Ollama?' in resolve
assert 'It will not restart Ollama while that endpoint remains reachable.' in resolve

# Restart lifecycle must clear the tray/server tree and wait for the port before relaunch.
stop=ps[ps.index('function Stop-DetectedWindowsNativeOllamaProcesses'):ps.index('function Resolve-WindowsNativeOllamaForQuestionnaire')]
assert "Where-Object { [string]$_.Name -ieq 'ollama app.exe' }" in stop
assert 'Wait-WindowsTcpPortReleased $port 12' in stop
assert 'will not launch a duplicate instance' in stop
assert 'Never run `ollama serve` alongside a' in stop
restart=ps[ps.index('function Restart-WindowsNativeOllamaForEnvironment'):ps.index('function Test-WindowsNativeOllamaNonLoopbackListener')]
assert 'Stop-DetectedWindowsNativeOllamaProcesses 15' in restart
assert 'Wait-WindowsTcpPortReleased $port 12' in restart
assert "Start-Process ([string]$State.AppExecutable)" in restart

# End-to-end HTTP success outranks listener introspection in direct remediation.
enable=ps[ps.index('function Enable-LatticeValeWindowsNativeOllamaDirectWslAccess'):ps.index('function Remove-LatticeValeWindowsNativeOllamaDirectWslAccess')]
assert 'A successful Ollama HTTP response from the selected distro is authoritative.' in enable
assert 'Ollama is not listening on a non-loopback address on TCP' not in enable

# No machine-specific NAT address is baked into the runtime source.
assert '172.31.240.1' not in ps
assert '172.31.241.50' not in ps

# Obsidian requires a user-entered path and supplies no suggested location.
assert "Windows Obsidian vault folder (explicit Windows-local path required)" in ps
assert 'Windows Obsidian vault folder [suggested:' not in ps
assert 'no location is assumed or suggested.' in ps
print('v14.3.22+ native Ollama HTTP/lifecycle fixtures: PASS')
