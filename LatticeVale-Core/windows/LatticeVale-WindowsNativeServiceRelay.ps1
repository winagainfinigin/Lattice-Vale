#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [ValidateRange(10, 300)]
    [int]$WaitSeconds = 60,
    [ValidateRange(5, 300)]
    [int]$RefreshSeconds = 15,
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Normalize-WslOutput([object[]]$Lines) {
    $text = (($Lines | ForEach-Object { [string]$_ }) -join "`n")
    return $text.Replace([string][char]0, [string]::Empty).Replace([string][char]0xFEFF, [string]::Empty).Trim()
}

function Write-RelayLog([string]$Message) {
    try {
        $dir = Split-Path -Parent $ConfigPath
        if ($dir) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $log = Join-Path $dir 'windows-native-service-relay.log'
        Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message) -Encoding UTF8
    } catch { }
}

function ConvertTo-WindowsProcessArgument([string]$Value) {
    if ($null -eq $Value) { return '""' }
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"')
    $slashes = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ([int]$ch -eq 92) { $slashes++; continue }
        if ($ch -eq '"') {
            [void]$sb.Append(('\' * (($slashes * 2) + 1)))
            [void]$sb.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) { [void]$sb.Append(('\' * $slashes)); $slashes = 0 }
        [void]$sb.Append($ch)
    }
    if ($slashes -gt 0) { [void]$sb.Append(('\' * ($slashes * 2))) }
    [void]$sb.Append('"')
    return $sb.ToString()
}

function Invoke-WslBounded([string[]]$Arguments, [int]$TimeoutSeconds = 15) {
    $process = $null
    try {
        $argLine = (($Arguments | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = "$env:SystemRoot\System32\wsl.exe"
        $startInfo.Arguments = $argLine
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw 'Could not start wsl.exe.' }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch { }
            try { $process.WaitForExit(2000) | Out-Null } catch { }
            $stdout = if ($stdoutTask.IsCompleted) { Normalize-WslOutput @([string]$stdoutTask.Result) } else { '' }
            $stderr = if ($stderrTask.IsCompleted) { Normalize-WslOutput @([string]$stderrTask.Result) } else { '' }
            return [pscustomobject]@{ Success=$false; ExitCode=-1; TimedOut=$true; StdOut=$stdout; StdErr=$stderr; Text=(Normalize-WslOutput @($stdout,$stderr)) }
        }
        $process.WaitForExit()
        $stdout = Normalize-WslOutput @([string]$stdoutTask.Result)
        $stderr = Normalize-WslOutput @([string]$stderrTask.Result)
        $exitCode = [int]$process.ExitCode
        return [pscustomobject]@{ Success=($exitCode -eq 0); ExitCode=$exitCode; TimedOut=$false; StdOut=$stdout; StdErr=$stderr; Text=(Normalize-WslOutput @($stdout,$stderr)) }
    } finally {
        if ($process) { try { $process.Dispose() } catch { } }
    }
}

function Invoke-WslDistro([string]$DistroName, [string]$User, [string]$Command, [string[]]$CommandArguments = @(), [int]$TimeoutSeconds = 15) {
    $wslArgs = @('-d',$DistroName)
    if (-not [string]::IsNullOrWhiteSpace($User)) { $wslArgs += @('-u',$User) }
    $wslArgs += @('--',$Command)
    $wslArgs += $CommandArguments
    return Invoke-WslBounded $wslArgs $TimeoutSeconds
}

function Test-WslDistroRunning([string]$DistroName) {
    $probe = Invoke-WslBounded @('--list','--running','--quiet') 10
    if (-not $probe.Success) { return $false }
    foreach ($line in ([string]$probe.StdOut -split "`r?`n")) {
        if ($line.Trim().Equals($DistroName, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Test-UsableIpv4([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $ip = $null
    if (-not [System.Net.IPAddress]::TryParse($Value.Trim(), [ref]$ip)) { return $false }
    if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    if ([System.Net.IPAddress]::IsLoopback($ip)) { return $false }
    if ($ip.ToString().StartsWith('169.254.')) { return $false }
    return $true
}

function ConvertTo-Ipv4UInt32([string]$Value) {
    $ip = $null
    if (-not [System.Net.IPAddress]::TryParse($Value, [ref]$ip)) { return $null }
    if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $null }
    $b = $ip.GetAddressBytes()
    return [uint32]((([uint32]$b[0]) -shl 24) -bor (([uint32]$b[1]) -shl 16) -bor (([uint32]$b[2]) -shl 8) -bor ([uint32]$b[3]))
}

function Test-Ipv4SubnetMatch([string]$AddressA, [string]$AddressB, [int]$PrefixLength) {
    if ($PrefixLength -lt 1 -or $PrefixLength -gt 32) { return $false }
    $a = ConvertTo-Ipv4UInt32 $AddressA
    $b = ConvertTo-Ipv4UInt32 $AddressB
    if ($null -eq $a -or $null -eq $b) { return $false }
    $mask = if ($PrefixLength -eq 32) { [uint32]0xFFFFFFFF } else { [uint32](([uint64]0xFFFFFFFF -shl (32 - $PrefixLength)) -band [uint64]0xFFFFFFFF) }
    return (($a -band $mask) -eq ($b -band $mask))
}

function Get-WslDefaultIpv4GatewayCandidates([string]$DistroName) {
    $probe = Invoke-WslDistro $DistroName '' 'ip' @('-4','route','show','default') 15
    if (-not $probe.Success) { return @() }
    $result = New-Object System.Collections.Generic.List[string]
    foreach ($line in @($probe.StdOut -split "`r?`n")) {
        $tokens = @((([string]$line).Trim()) -split '\s+')
        if ($tokens.Count -lt 3 -or $tokens[0] -ne 'default') { continue }
        for ($i = 1; $i -lt ($tokens.Count - 1); $i++) {
            if ($tokens[$i] -ne 'via') { continue }
            $candidate = ([string]$tokens[$i + 1]).Trim()
            if ((Test-UsableIpv4 $candidate) -and -not $result.Contains($candidate)) { $result.Add($candidate) }
            break
        }
    }
    return [string[]]$result.ToArray()
}

function Get-WindowsHostIpv4FromWsl([string]$DistroName) {
    foreach ($candidate in @(Get-WslDefaultIpv4GatewayCandidates $DistroName)) {
        if ((Test-UsableIpv4 $candidate) -and (Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue)) {
            try { if (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $candidate -ErrorAction SilentlyContinue | Select-Object -First 1) { return $candidate } } catch { }
        }
    }

    $wslIp = Get-WslIpv4 $DistroName
    if (-not (Test-UsableIpv4 $wslIp) -or -not (Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue)) { return '' }
    $adapterText = @{}
    if (Get-Command Get-NetAdapter -ErrorAction SilentlyContinue) {
        try {
            foreach ($adapter in @(Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue)) {
                $adapterText[[int]$adapter.ifIndex] = (([string]$adapter.Name) + ' ' + ([string]$adapter.InterfaceDescription)).Trim()
            }
        } catch { }
    }
    try {
        foreach ($entry in @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue)) {
            $candidate = ([string]$entry.IPAddress).Trim()
            if (-not (Test-UsableIpv4 $candidate)) { continue }
            $identity = (([string]$entry.InterfaceAlias) + ' ' + ([string]$adapterText[[int]$entry.InterfaceIndex])).Trim()
            if ($identity -notmatch '(?i)(WSL|Hyper-V|vEthernet|Virtual Ethernet)') { continue }
            if (Test-Ipv4SubnetMatch $candidate $wslIp ([int]$entry.PrefixLength)) { return $candidate }
        }
    } catch { }
    return ''
}


function Get-WslIpv4([string]$DistroName) {
    $probe = Invoke-WslDistro $DistroName '' 'hostname' @('-I') 15
    if (-not $probe.Success) { return '' }
    foreach ($token in ([string]$probe.StdOut -split '\s+')) {
        if (Test-UsableIpv4 $token) { return $token.Trim() }
    }
    return ''
}

function Write-WslHostAddressState([string]$DistroName, [string]$StackPath, [string]$GatewayIp) {
    if ([string]::IsNullOrWhiteSpace($StackPath) -or -not (Test-UsableIpv4 $GatewayIp)) { return }
    $script = @'
set -e
stack="$1"; value="$2"
case "$stack" in /*) ;; *) exit 2 ;; esac
if [[ -d "$stack" ]]; then
  umask 022
  printf '%s\n' "$value" > "$stack/.windows-native-host-ip"
fi
'@
    $result = Invoke-WslDistro $DistroName 'root' 'bash' @('-lc',$script,'bash',$StackPath,$GatewayIp) 15
    if (-not $result.Success) { throw "Could not publish the current Windows-host IPv4 into WSL stack '$StackPath'." }
}

function Test-TcpEndpoint([string]$Address, [int]$Port, [int]$TimeoutMilliseconds = 1500) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Address, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch { return $false } finally { try { $client.Close() } catch { } }
}

function Test-BindAvailable([string]$Address, [int]$Port) {
    $listener = $null
    try {
        $ip = [System.Net.IPAddress]::Parse($Address)
        $listener = New-Object System.Net.Sockets.TcpListener($ip, $Port)
        $listener.Server.SetSocketOption([System.Net.Sockets.SocketOptionLevel]::Socket, [System.Net.Sockets.SocketOptionName]::ReuseAddress, $false)
        $listener.Start(1)
        return $true
    } catch { return $false } finally { if ($listener) { try { $listener.Stop() } catch { } } }
}

function Get-FirewallRuleName([string]$Key, [string]$Label) {
    $safe = ([regex]::Replace("$Key-$Label", '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ($safe.Length -gt 160) { $safe = $safe.Substring(0,160) }
    return "LatticeValeNativeBridge-$safe"
}

function Get-WslHyperVCreatorId {
    $documented = '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'
    if (Get-Command Get-NetFirewallHyperVVMCreator -ErrorAction SilentlyContinue) {
        try {
            $creator = Get-NetFirewallHyperVVMCreator -ErrorAction SilentlyContinue | Where-Object { ([string]$_.FriendlyName) -eq 'WSL' } | Select-Object -First 1
            if ($creator -and -not [string]::IsNullOrWhiteSpace([string]$creator.VMCreatorId)) { return [string]$creator.VMCreatorId }
        } catch { }
    }
    return $documented
}

function Get-HyperVFirewallRuleName([string]$Key, [string]$Label) {
    $safe = ([regex]::Replace("$Key-$Label", '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ($safe.Length -gt 150) { $safe = $safe.Substring(0,150) }
    return "LatticeValeNativeBridge-HyperV-$safe"
}

function Set-RelayFirewall([object]$Config, [string]$GatewayIp, [string]$WslIp) {
    if (-not (Get-Command New-NetFirewallRule -ErrorAction SilentlyContinue)) {
        throw 'Windows Firewall cmdlets are unavailable; the WSL-only native-service bridge cannot be safely exposed.'
    }
    foreach ($service in @($Config.services | Where-Object { $_.enabled -eq $true })) {
        $ruleName = Get-FirewallRuleName ([string]$Config.ruleKey) ([string]$service.label)
        Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
        New-NetFirewallRule -Name $ruleName -DisplayName ("LatticeVale WSL-only native bridge: {0}" -f [string]$service.label) -Group 'LatticeVale' -Direction Inbound -Action Allow -Enabled True -Profile Any -Protocol TCP -LocalAddress $GatewayIp -RemoteAddress $WslIp -LocalPort ([int]$service.listenPort) | Out-Null
        if ((Get-Command New-NetFirewallHyperVRule -ErrorAction SilentlyContinue) -and (Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
            $hyperVName = Get-HyperVFirewallRuleName ([string]$Config.ruleKey) ([string]$service.label)
            Get-NetFirewallHyperVRule -Name $hyperVName -ErrorAction SilentlyContinue | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue
            try {
                New-NetFirewallHyperVRule -Name $hyperVName -DisplayName ("LatticeVale WSL outbound native bridge: {0}" -f [string]$service.label) -Direction Outbound -Action Allow -Enabled True -Profiles Any -VMCreatorId (Get-WslHyperVCreatorId) -Protocol TCP -RemoteAddresses $GatewayIp -RemotePorts ([string][int]$service.listenPort) -ErrorAction Stop | Out-Null
            } catch {
                Write-RelayLog ("Hyper-V firewall rule was unavailable for {0}: {1}" -f [string]$service.label,$_.Exception.Message)
            }
        }
    }
}

function Test-WslHttpThroughRelay([string]$DistroName, [string]$Url, [int]$TimeoutSeconds = 10) {
    $uri = New-Object System.Uri($Url)
    $hostName = [string]$uri.Host
    $port = [int]$uri.Port
    $path = [string]$uri.PathAndQuery
    if ([string]::IsNullOrWhiteSpace($path)) { $path = '/' }
    $script = @'
set -e
host="$1"; port="$2"; path="$3"
if command -v python3 >/dev/null 2>&1; then
  python3 - "$host" "$port" "$path" <<'PY_RELAY_HTTP'
import sys,urllib.request
host=sys.argv[1]; port=int(sys.argv[2]); path=sys.argv[3]
with urllib.request.urlopen(f'http://{host}:{port}{path}', timeout=5) as r:
    data=r.read(1024)
    if not data:
        raise RuntimeError('empty response')
PY_RELAY_HTTP
  exit $?
fi
if command -v curl >/dev/null 2>&1; then
  exec curl -fsS --connect-timeout 3 --max-time 6 "http://${host}:${port}${path}" -o /dev/null
fi
# Fresh Ubuntu images normally have Python or curl, but the relay self-test runs
# before package repair. Bash /dev/tcp keeps the bridge probe independent of both.
exec 3<>"/dev/tcp/${host}/${port}"
printf 'GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n' "$path" "$host" >&3
IFS= read -r status <&3 || true
case "$status" in
  *' 200 '*|*' 204 '*) exit 0 ;;
  *) exit 1 ;;
esac
'@
    $probe = Invoke-WslDistro $DistroName '' 'bash' @('-lc',$script,'bash',$hostName,[string]$port,$path) $TimeoutSeconds
    return $probe.Success
}

trap {
    Write-RelayLog ("FATAL: " + $_.Exception.Message)
    throw
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "Native-service relay configuration is missing: $ConfigPath" }
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$distro = [string]$config.distroName
$services = @($config.services | Where-Object { $_.enabled -eq $true })
if ([string]::IsNullOrWhiteSpace($distro) -or $services.Count -eq 0) { exit 0 }

$gateway = Get-WindowsHostIpv4FromWsl $distro
$wslIp = Get-WslIpv4 $distro
$stackPath = if ($config.PSObject.Properties.Name -contains 'stackPath') { [string]$config.stackPath } else { '' }
if (-not (Test-UsableIpv4 $gateway)) { throw "Could not determine the Windows-host IPv4 from inside WSL distro '$distro'." }
if (-not (Test-UsableIpv4 $wslIp)) { throw "Could not determine a usable WSL IPv4 for distro '$distro'." }
Write-WslHostAddressState $distro $stackPath $gateway

foreach ($service in $services) {
    $listenPort = [int]$service.listenPort
    $targetPort = [int]$service.targetPort
    $targetAddress = [string]$service.targetAddress
    if ($listenPort -lt 1 -or $listenPort -gt 65535 -or $targetPort -lt 1 -or $targetPort -gt 65535) { throw "Invalid relay port configuration for $([string]$service.label)." }
    if (-not (Test-TcpEndpoint $targetAddress $targetPort 1500)) { throw "Windows-native target for $([string]$service.label) is not reachable at ${targetAddress}:$targetPort." }
    if (-not (Test-BindAvailable $gateway $listenPort)) { throw "WSL-only Windows relay endpoint ${gateway}:$listenPort is already in use." }
}

Set-RelayFirewall $config $gateway $wslIp

$source = @'
using System;
using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;

public static class LatticeValeWindowsNativeRelay
{
    private static readonly ConcurrentDictionary<string, TcpListener> Listeners = new ConcurrentDictionary<string, TcpListener>();
    private static readonly ConcurrentQueue<string> Events = new ConcurrentQueue<string>();
    private static SemaphoreSlim Gate = new SemaphoreSlim(64, 64);
    private static int ConnectTimeoutMs = 5000;
    private static int SessionTimeoutMs = 7200000;

    public static void Configure(int maxConnections, int connectTimeoutMs, int sessionTimeoutMs)
    {
        if (Listeners.Count != 0) throw new InvalidOperationException("Cannot reconfigure relay while listeners are active.");
        if (maxConnections < 1 || maxConnections > 1024) throw new ArgumentOutOfRangeException("maxConnections");
        Gate.Dispose();
        Gate = new SemaphoreSlim(maxConnections, maxConnections);
        ConnectTimeoutMs = connectTimeoutMs;
        SessionTimeoutMs = sessionTimeoutMs;
    }

    private static void Event(string message)
    {
        Events.Enqueue(DateTime.UtcNow.ToString("o") + " " + message);
        while (Events.Count > 256) { string ignored; Events.TryDequeue(out ignored); }
    }

    public static string[] DrainEvents()
    {
        var result = new System.Collections.Generic.List<string>();
        string item;
        while (Events.TryDequeue(out item)) result.Add(item);
        return result.ToArray();
    }

    public static void Start(string listenAddress, int listenPort, string targetAddress, int targetPort)
    {
        string key = listenAddress + ":" + listenPort;
        var listener = new TcpListener(IPAddress.Parse(listenAddress), listenPort);
        listener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, false);
        listener.Start(128);
        if (!Listeners.TryAdd(key, listener))
        {
            listener.Stop();
            throw new InvalidOperationException("Duplicate native relay listener " + key);
        }
        Task.Run(() => AcceptLoop(listener, targetAddress, targetPort));
    }

    public static void StopAll()
    {
        foreach (var pair in Listeners)
        {
            TcpListener listener;
            if (Listeners.TryRemove(pair.Key, out listener))
            {
                try { listener.Stop(); } catch { }
            }
        }
    }

    private static async Task AcceptLoop(TcpListener listener, string targetAddress, int targetPort)
    {
        while (true)
        {
            TcpClient client = null;
            try { client = await listener.AcceptTcpClientAsync().ConfigureAwait(false); }
            catch (ObjectDisposedException) { break; }
            catch (SocketException) { break; }
            catch (Exception ex) { Event("accept failed: " + ex.GetType().Name + ": " + ex.Message); await Task.Delay(250).ConfigureAwait(false); continue; }
            if (!Gate.Wait(0))
            {
                Event("connection rejected: relay concurrency limit reached");
                try { client.Close(); } catch { }
                continue;
            }
            var ignored = HandleClient(client, targetAddress, targetPort);
        }
    }

    private static async Task HandleClient(TcpClient client, string targetAddress, int targetPort)
    {
        try
        {
            using (client)
            using (var upstream = new TcpClient())
            {
                client.NoDelay = true;
                upstream.NoDelay = true;
                var connect = upstream.ConnectAsync(targetAddress, targetPort);
                if (await Task.WhenAny(connect, Task.Delay(ConnectTimeoutMs)).ConfigureAwait(false) != connect)
                    throw new TimeoutException("upstream connect timeout");
                await connect.ConfigureAwait(false);
                using (var a = client.GetStream())
                using (var b = upstream.GetStream())
                {
                    var ab = a.CopyToAsync(b);
                    var ba = b.CopyToAsync(a);
                    var session = Task.Delay(SessionTimeoutMs);
                    var first = await Task.WhenAny(ab, ba, session).ConfigureAwait(false);
                    if (first == session) Event("connection closed: session timeout reached");
                    try { client.Client.Shutdown(SocketShutdown.Both); } catch { }
                    try { upstream.Client.Shutdown(SocketShutdown.Both); } catch { }
                    try { await Task.WhenAll(ab, ba).ConfigureAwait(false); } catch (Exception ex) { Event("copy completed with " + ex.GetType().Name); }
                }
            }
        }
        catch (Exception ex) { Event("connection failed: " + ex.GetType().Name + ": " + ex.Message); }
        finally { Gate.Release(); }
    }
}
'@
Add-Type -TypeDefinition $source -Language CSharp

[LatticeValeWindowsNativeRelay]::Configure(64, 5000, 7200000)

function Start-NativeRelayListeners([string]$ListenAddress) {
    foreach ($service in $services) {
        [LatticeValeWindowsNativeRelay]::Start($ListenAddress, [int]$service.listenPort, [string]$service.targetAddress, [int]$service.targetPort)
    }
}

function Write-NativeRelayEvents {
    foreach ($eventLine in @([LatticeValeWindowsNativeRelay]::DrainEvents())) {
        if (-not [string]::IsNullOrWhiteSpace([string]$eventLine)) { Write-RelayLog ("TCP: " + [string]$eventLine) }
    }
}

function Test-AllNativeRelayServices([string]$ListenAddress) {
    foreach ($service in $services) {
        if (-not (Test-TcpEndpoint ([string]$service.targetAddress) ([int]$service.targetPort) 1500)) { return $false }
        $probePath = [string]$service.probePath
        if ([string]::IsNullOrWhiteSpace($probePath)) { $probePath = '/' }
        $url = "http://${ListenAddress}:$([int]$service.listenPort)$probePath"
        if (-not (Test-WslHttpThroughRelay $distro $url 12)) { return $false }
    }
    return $true
}

Start-NativeRelayListeners $gateway
Start-Sleep -Milliseconds 300
if (-not (Test-AllNativeRelayServices $gateway)) {
    [LatticeValeWindowsNativeRelay]::StopAll()
    throw "WSL could not verify one or more native Windows service relays at Windows host address $gateway."
}

Write-RelayLog "Relay ready for '$distro': WSL=$wslIp WindowsHost=$gateway services=$($services.Count) maxConnections=64 refresh=${RefreshSeconds}s."
if ($SelfTest) { [LatticeValeWindowsNativeRelay]::StopAll(); exit 0 }

$currentGateway = $gateway
$currentWslIp = $wslIp
$lastRunningState = $true
$lastHealthCheck = [DateTime]::UtcNow
while ($true) {
    Start-Sleep -Seconds $RefreshSeconds
    try {
        Write-NativeRelayEvents
        $running = Test-WslDistroRunning $distro
        if (-not $running) {
            if ($lastRunningState) { Write-RelayLog "WSL distro '$distro' is stopped; relay is preserving current listeners without waking WSL." }
            $lastRunningState = $false
            continue
        }
        if (-not $lastRunningState) { Write-RelayLog "WSL distro '$distro' is running again; refreshing relay topology." }
        $lastRunningState = $true

        $newGateway = Get-WindowsHostIpv4FromWsl $distro
        $newWslIp = Get-WslIpv4 $distro
        if (-not (Test-UsableIpv4 $newGateway) -or -not (Test-UsableIpv4 $newWslIp)) {
            Write-RelayLog 'Refresh warning: current WSL/Windows relay addresses could not be resolved; retaining the last known topology.'
            continue
        }

        if ($newGateway -ne $currentGateway -or $newWslIp -ne $currentWslIp) {
            if ($newGateway -ne $currentGateway) {
                foreach ($service in $services) {
                    if (-not (Test-BindAvailable $newGateway ([int]$service.listenPort))) {
                        throw "Refusing topology refresh because ${newGateway}:$([int]$service.listenPort) is already in use."
                    }
                }
            }
            Set-RelayFirewall $config $newGateway $newWslIp
            if ($newGateway -ne $currentGateway) {
                [LatticeValeWindowsNativeRelay]::StopAll()
                Start-Sleep -Milliseconds 150
                Start-NativeRelayListeners $newGateway
                Start-Sleep -Milliseconds 300
            }
            Write-WslHostAddressState $distro $stackPath $newGateway
            if (-not (Test-AllNativeRelayServices $newGateway)) { throw 'Refreshed topology did not pass the end-to-end WSL HTTP probe.' }
            Write-RelayLog "Relay topology refreshed: WSL $currentWslIp -> $newWslIp ; WindowsHost $currentGateway -> $newGateway."
            $currentGateway = $newGateway
            $currentWslIp = $newWslIp
            $lastHealthCheck = [DateTime]::UtcNow
            continue
        }

        if (([DateTime]::UtcNow - $lastHealthCheck).TotalSeconds -ge 60) {
            $lastHealthCheck = [DateTime]::UtcNow
            if (-not (Test-AllNativeRelayServices $currentGateway)) {
                $targetsHealthy = $true
                foreach ($service in $services) {
                    if (-not (Test-TcpEndpoint ([string]$service.targetAddress) ([int]$service.targetPort) 1500)) { $targetsHealthy = $false; break }
                }
                if ($targetsHealthy) {
                    Write-RelayLog 'Relay health probe failed while Windows targets remain healthy; rebuilding listeners in place.'
                    [LatticeValeWindowsNativeRelay]::StopAll()
                    Start-Sleep -Milliseconds 150
                    Start-NativeRelayListeners $currentGateway
                    Start-Sleep -Milliseconds 300
                    if (-not (Test-AllNativeRelayServices $currentGateway)) { Write-RelayLog 'Relay listener rebuild did not restore end-to-end HTTP health; retrying on the next refresh cycle.' }
                } else {
                    Write-RelayLog 'Relay health probe failed because one or more Windows-native targets are unavailable; listeners remain ready for target recovery.'
                }
            }
        }
    } catch {
        Write-RelayLog ("Refresh warning: " + $_.Exception.Message)
    }
}
