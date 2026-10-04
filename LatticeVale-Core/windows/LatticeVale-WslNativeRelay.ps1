#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [ValidateRange(1, 900)]
    [int]$WaitSeconds = 90,
    [ValidateRange(5, 300)]
    [int]$RefreshSeconds = 15,
    [switch]$EnsureDistroRunning,
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
        $log = Join-Path $dir 'native-relay.log'
        Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message) -Encoding UTF8
    } catch { }
}

function Invoke-WslBounded([string[]]$Arguments, [int]$TimeoutSeconds = 15) {
    $process = $null
    try {
        $quoted = (($Arguments | ForEach-Object {
            $a=[string]$_
            if ($a -notmatch '[\s"]') { $a } else { '"' + ($a -replace '(\\*)"','$1$1\\"' -replace '(\\+)$','$1$1') + '"' }
        }) -join ' ')

        # Use System.Diagnostics.Process directly instead of Start-Process -PassThru.
        # The latter has had host/version-specific null ExitCode behavior with
        # -NoNewWindow; the relay must work under Windows PowerShell 5.1 as well as pwsh.
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = "$env:SystemRoot\System32\wsl.exe"
        $startInfo.Arguments = $quoted
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
            $text = Normalize-WslOutput @($stdout,$stderr)
            return [pscustomobject]@{ Success=$false; ExitCode=-1; TimedOut=$true; Text=$text; StdOut=$stdout; StdErr=$stderr }
        }
        $process.WaitForExit()
        $stdout = Normalize-WslOutput @([string]$stdoutTask.Result)
        $stderr = Normalize-WslOutput @([string]$stderrTask.Result)
        $text = Normalize-WslOutput @($stdout,$stderr)
        $exitCode = [int]$process.ExitCode
        return [pscustomobject]@{ Success=($exitCode -eq 0); ExitCode=$exitCode; TimedOut=$false; Text=$text; StdOut=$stdout; StdErr=$stderr }
    } catch {
        return [pscustomobject]@{ Success=$false; ExitCode=-1; TimedOut=$false; Text=$_.Exception.Message; StdOut=''; StdErr=$_.Exception.Message }
    } finally {
        if ($process) { try { $process.Dispose() } catch { } }
    }
}

function Test-WslCliRejectedArgumentSeparator([object]$Attempt) {
    if ($null -eq $Attempt -or $Attempt.TimedOut -or $Attempt.ExitCode -eq -1) { return $false }
    $text = (([string]$Attempt.StdOut) + "`n" + ([string]$Attempt.StdErr)).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    # Fail closed: an arbitrary Linux command can itself print "invalid option --...".
    # Treat the separator as unsupported only when the diagnostic identifies the WSL
    # CLI/Windows Subsystem for Linux, otherwise retrying could duplicate side effects.
    return [bool]($text -match '(?is)(wsl(?:\.exe)?|windows subsystem for linux).{0,160}(invalid|unknown|unrecognized|unsupported).{0,100}--' -or
                  $text -match '(?is)(invalid|unknown|unrecognized|unsupported).{0,100}--.{0,160}(wsl(?:\.exe)?|windows subsystem for linux)')
}

function Invoke-WslDistroCommand(
    [string]$DistroName,
    [string]$User,
    [string]$Command,
    [string[]]$CommandArguments = @(),
    [int]$TimeoutSeconds = 15
) {
    # Use the explicit separator first. Retry without it only when wsl.exe itself
    # rejects `--`; never execute an ordinary failed Linux command twice.
    $prefix = @('-d',$DistroName)
    if (-not [string]::IsNullOrWhiteSpace($User)) { $prefix += @('-u',$User) }
    $standardArgs = [string[]]($prefix + @('--',$Command) + $CommandArguments)
    $probe = Invoke-WslBounded $standardArgs $TimeoutSeconds
    if ($probe.Success -or $probe.TimedOut -or -not (Test-WslCliRejectedArgumentSeparator $probe)) {
        if ($probe.Success) { $probe.Text = $probe.StdOut }
        return $probe
    }
    $legacyArgs = [string[]]($prefix + @($Command) + $CommandArguments)
    $legacy = Invoke-WslBounded $legacyArgs $TimeoutSeconds
    if ($legacy.Success) { $legacy.Text = $legacy.StdOut }
    return $legacy
}

function Test-WslDistroRunning([string]$DistroName) {
    # `wsl --list --running --quiet` is a host-side status query; unlike a command
    # executed inside the distro, it does not start a stopped distribution. Passive
    # relay mode uses this gate so a Tailscale bridge cannot silently recreate
    # full-stack auto-start semantics.
    $probe = Invoke-WslBounded @('--list','--running','--quiet') 10
    if (-not $probe.Success) { return $false }
    foreach ($line in ([string]$probe.Text -split "`r?`n")) {
        if ($line.Trim().Equals($DistroName, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Get-ActiveWslNetworkingMode([string]$DistroName) {
    if (-not (Test-WslDistroRunning $DistroName)) { return '' }
    $probe = Invoke-WslDistroCommand $DistroName '' 'wslinfo' @('--networking-mode') 5
    if (-not $probe.Success) { return '' }
    $mode = (([string]$probe.Text).Trim().ToLowerInvariant() -split '\s+')[0]
    if ($mode -in @('mirrored','nat','virtioproxy','none')) { return $mode }
    return ''
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

function Test-UsableWslIpv4([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $address = $null
    if (-not [System.Net.IPAddress]::TryParse($Value.Trim(), [ref]$address)) { return $false }
    if ($address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    if ([System.Net.IPAddress]::IsLoopback($address)) { return $false }
    if ($address.ToString().StartsWith('169.254.')) { return $false }
    return $true
}

function Test-LoopbackPortAvailable([int]$Port) {
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
        $listener.Server.SetSocketOption([System.Net.Sockets.SocketOptionLevel]::Socket, [System.Net.Sockets.SocketOptionName]::ReuseAddress, $false)
        $listener.Start(1)
        return $true
    } catch { return $false } finally { if ($listener) { try { $listener.Stop() } catch { } } }
}

function Start-HermesStack([string]$DistroName) {
    if (-not $EnsureDistroRunning) { return $true }
    $wake = Invoke-WslDistroCommand $DistroName '' 'true' @() 30
    if (-not $wake.Success) {
        Write-RelayLog "WSL wake failed for ${DistroName}: $($wake.Text)"
        return $false
    }
    # The root helper can legitimately use up to three 240-second Compose attempts plus Docker startup.
    # Keep the Windows wrapper outside that bound so it does not kill a healthy recovery in progress.
    $start = Invoke-WslDistroCommand $DistroName 'root' '/usr/local/sbin/hermes-stack-start' @() 900
    if (-not $start.Success) {
        Write-RelayLog "Hermes stack start helper failed for ${DistroName}: $($start.Text)"
        return $false
    }
    return $true
}

function Get-WslIpv4Candidates([string]$DistroName) {
    $result = [System.Collections.Generic.List[string]]::new()
    $diagnostics = [System.Collections.Generic.List[string]]::new()
    $probes = @(
        [pscustomobject]@{ Label='eth0'; Result=(Invoke-WslDistroCommand $DistroName '' 'ip' @('-4','-o','addr','show','dev','eth0','scope','global') 15) },
        [pscustomobject]@{ Label='hostname'; Result=(Invoke-WslDistroCommand $DistroName '' 'hostname' @('-I') 15) }
    )
    foreach ($item in $probes) {
        $probe = $item.Result
        if (-not $probe.Success) {
            $detail = if ($probe.TimedOut) { 'timed out' } elseif ($probe.Text) { $probe.Text } else { 'no output' }
            $diagnostics.Add("$($item.Label): $detail")
            continue
        }
        foreach ($match in [regex]::Matches([string]$probe.Text, '(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')) {
            $token = $match.Value
            $address = $null
            if (-not [System.Net.IPAddress]::TryParse($token, [ref]$address)) { continue }
            if ($address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { continue }
            if ([System.Net.IPAddress]::IsLoopback($address)) { continue }
            $text = $address.ToString()
            if ($text.StartsWith('169.254.')) { continue }
            if (-not $result.Contains($text)) { $result.Add($text) }
        }
    }
    $script:LastWslIpProbeDiagnostic = ($diagnostics -join ' | ')
    return $result.ToArray()
}

function Test-WslIpForServices([string]$Ip, [object[]]$Services) {
    if ([string]::IsNullOrWhiteSpace($Ip)) { return $false }
    $address = $null
    if (-not [System.Net.IPAddress]::TryParse($Ip.Trim(), [ref]$address)) { return $false }
    if ($address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    if ([System.Net.IPAddress]::IsLoopback($address) -or $address.ToString().StartsWith('169.254.')) { return $false }
    foreach ($service in $Services) {
        if (-not (Test-TcpEndpoint $address.ToString() ([int]$service.backendPort) 1500)) { return $false }
    }
    return $true
}

function Test-RelayTargetForServices([string]$Address, [object[]]$Services) {
    if ([string]::IsNullOrWhiteSpace($Address)) { return $false }
    $candidate = $Address.Trim()
    if ($candidate -eq '127.0.0.1' -or $candidate -eq 'localhost') {
        foreach ($service in $Services) {
            if (-not (Test-TcpEndpoint '127.0.0.1' ([int]$service.backendPort) 1500)) { return $false }
        }
        return $true
    }
    return (Test-WslIpForServices $candidate $Services)
}

function Find-ReachableWslIp([string]$DistroName, [object[]]$Services, [int]$TimeoutSeconds) {
    # In passive/on-demand mode, never use an in-distro probe to discover the IP
    # while the distro is stopped: invoking such a probe would itself wake WSL.
    if (-not $EnsureDistroRunning -and -not (Test-WslDistroRunning $DistroName)) { return '' }
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1,$TimeoutSeconds))
    do {
        if (-not $EnsureDistroRunning -and -not (Test-WslDistroRunning $DistroName)) { return '' }
        foreach ($ip in @(Get-WslIpv4Candidates $DistroName)) {
            $ok = $true
            foreach ($service in $Services) {
                if (-not (Test-TcpEndpoint $ip ([int]$service.backendPort) 1500)) { $ok = $false; break }
            }
            if ($ok) { return $ip }
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    return ''
}

function Get-ReachableWslIp([string]$DistroName, [object[]]$Services, [int]$TimeoutSeconds) {
    # Mirrored mode uses the stable Windows<->WSL localhost path documented by Microsoft,
    # avoiding DHCP-assigned VM addresses. NAT/other modes retain WSL IPv4 discovery.
    if ($script:RelayTargetMode -eq 'mirrored-localhost') {
        if (Test-RelayTargetForServices '127.0.0.1' $Services) { return '127.0.0.1' }
        if (-not $EnsureDistroRunning) { return '' }
        Write-RelayLog 'Mirrored localhost backend is not reachable; invoking installer-owned stack recovery once.'
        if (Start-HermesStack $DistroName) {
            $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Min([Math]::Max($TimeoutSeconds,10),120))
            do {
                if (Test-RelayTargetForServices '127.0.0.1' $Services) { return '127.0.0.1' }
                Start-Sleep -Seconds 2
            } while ([DateTime]::UtcNow -lt $deadline)
        }
        return ''
    }

    $initialProbeSeconds = [Math]::Min([Math]::Max($TimeoutSeconds,1),15)
    $ip = Find-ReachableWslIp $DistroName $Services $initialProbeSeconds
    if ($ip) { return $ip }
    if (-not $EnsureDistroRunning) {
        $remaining = [Math]::Max(1,$TimeoutSeconds - $initialProbeSeconds)
        return (Find-ReachableWslIp $DistroName $Services $remaining)
    }
    Write-RelayLog 'Initial WSL backend probe did not find all requested services; invoking installer-owned stack recovery.'
    if (Start-HermesStack $DistroName) {
        return (Find-ReachableWslIp $DistroName $Services ([Math]::Min([Math]::Max($TimeoutSeconds,30),120)))
    }
    return ''
}

function Write-RelayState([object]$Config, [string]$Address, [string]$LastError = '') {
    try {
        if (Test-UsableWslIpv4 $Address) { $Config.lastWslIp = $Address }
        if ($Config.PSObject.Properties.Name -contains 'lastTargetAddress') { $Config.lastTargetAddress = $Address }
        else { $Config | Add-Member -NotePropertyName lastTargetAddress -NotePropertyValue $Address }
        $Config.lastRefreshUtc = [DateTime]::UtcNow.ToString('o')
        if ($Config.PSObject.Properties.Name -contains 'lastError') { $Config.lastError = $LastError }
        else { $Config | Add-Member -NotePropertyName lastError -NotePropertyValue $LastError }
        $tmp = "$ConfigPath.tmp"
        $json = $Config | ConvertTo-Json -Depth 8
        [System.IO.File]::WriteAllText($tmp, ($json + "`r`n"), [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $tmp -Destination $ConfigPath -Force
    } catch { }
}

trap {
    Write-RelayLog ("FATAL: " + $_.Exception.Message)
    throw $_.Exception
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "Hermes WSL relay configuration is missing: $ConfigPath"
}

$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$distro = [string]$config.distroName
$services = @($config.services | Where-Object { $_.enabled -eq $true })
$script:RelayTargetMode = if ($config.PSObject.Properties.Name -contains 'targetMode' -and [string]$config.targetMode -eq 'mirrored-localhost') { 'mirrored-localhost' } else { 'wsl-ip' }
$liveNetworkingMode = Get-ActiveWslNetworkingMode $distro
if ($liveNetworkingMode -eq 'mirrored') { $script:RelayTargetMode = 'mirrored-localhost' }
elseif ($liveNetworkingMode) { $script:RelayTargetMode = 'wsl-ip' }
if ([string]::IsNullOrWhiteSpace($distro) -or $services.Count -eq 0) { exit 0 }

Write-RelayLog ("Relay process entered under {0} {1}; pid={2}; selfTest={3}." -f [string]$PSVersionTable.PSEdition,[string]$PSVersionTable.PSVersion,$PID,[bool]$SelfTest)

$mutexKey = ([regex]::Replace($ConfigPath.ToLowerInvariant(), '[^a-z0-9]', '_'))
if ($mutexKey.Length -gt 160) { $mutexKey = $mutexKey.Substring($mutexKey.Length - 160) }
$mutex = New-Object System.Threading.Mutex($false, "Local\HermesWslRelay_$mutexKey")
if (-not $mutex.WaitOne(0)) { exit 0 }

# Fail synchronously if another process owns a requested listener. The installer
# resolves ports before launching this task, but this catches races and stale manual
# listeners with an actionable task failure instead of a silent background exception.
foreach ($service in $services) {
    $bridgePort = [int]$service.bridgePort
    $backendPort = [int]$service.backendPort
    if ($bridgePort -lt 1 -or $bridgePort -gt 65535 -or $backendPort -lt 1 -or $backendPort -gt 65535) {
        throw "Invalid relay port configuration for $([string]$service.label)."
    }
    if (-not (Test-LoopbackPortAvailable $bridgePort)) {
        throw "Windows loopback relay port $bridgePort for $([string]$service.label) is already in use."
    }
}

$source = @'
using System;
using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;

public static class HermesWslRelay
{
    public static volatile string TargetAddress = "127.0.0.1";
    public static readonly ConcurrentDictionary<int, int> PortMap = new ConcurrentDictionary<int, int>();
    private static readonly ConcurrentDictionary<int, TcpListener> Listeners = new ConcurrentDictionary<int, TcpListener>();
    private static readonly ConcurrentQueue<string> Events = new ConcurrentQueue<string>();
    private static readonly SemaphoreSlim Gate = new SemaphoreSlim(64, 64);
    private const int ConnectTimeoutMs = 5000;
    private const int SessionTimeoutMs = 7200000;

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

    public static void Start(int listenPort, int targetPort)
    {
        if (!PortMap.TryAdd(listenPort, targetPort)) return;
        var listener = new TcpListener(IPAddress.Loopback, listenPort);
        listener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, false);
        listener.Start(128); // synchronous bind: port conflicts surface to PowerShell
        if (!Listeners.TryAdd(listenPort, listener))
        {
            listener.Stop();
            throw new InvalidOperationException("Duplicate relay listener port " + listenPort);
        }
        Task.Run(() => AcceptLoop(listener, targetPort));
    }

    private static async Task AcceptLoop(TcpListener listener, int targetPort)
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
            var ignored = HandleClient(client, targetPort);
        }
    }

    private static async Task HandleClient(TcpClient client, int targetPort)
    {
        try
        {
            using (client)
            using (var upstream = new TcpClient())
            {
                upstream.NoDelay = true;
                client.NoDelay = true;
                var connect = upstream.ConnectAsync(TargetAddress, targetPort);
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

$chosenIp = ''
$seedTarget = if ($config.PSObject.Properties.Name -contains 'lastTargetAddress') { [string]$config.lastTargetAddress } else { [string]$config.lastWslIp }
if ($script:RelayTargetMode -eq 'mirrored-localhost') { $seedTarget = '127.0.0.1' }
if (Test-RelayTargetForServices $seedTarget $services) {
    $chosenIp = $seedTarget.Trim()
    Write-RelayLog "Using verified relay target $chosenIp; all selected backends are reachable."
} elseif ($SelfTest) {
    $chosenIp = Get-ReachableWslIp $distro $services $WaitSeconds
    if (-not $chosenIp) {
        $probeDetail = if ($script:LastWslIpProbeDiagnostic) { " WSL probe detail: $script:LastWslIpProbeDiagnostic" } else { '' }
        $modeDetail = if ($script:RelayTargetMode -eq 'mirrored-localhost') { ' Mirrored mode expected Windows localhost to reach the WSL backend.' } else { '' }
        throw "No reachable WSL backend target was found for '$distro' during relay self-test.$modeDetail$probeDetail"
    }
} elseif ($script:RelayTargetMode -eq 'mirrored-localhost') {
    $chosenIp = '127.0.0.1'
    Write-RelayLog "Starting passive mirrored relay listeners on Windows localhost; waiting for '$distro' services."
} elseif (Test-UsableWslIpv4 $seedTarget) {
    $chosenIp = $seedTarget.Trim()
    Write-RelayLog "Starting passive relay listeners with cached WSL IPv4 $chosenIp; backend is not reachable yet."
} else {
    $chosenIp = Find-ReachableWslIp $distro $services 3
    if (-not $chosenIp) {
        $chosenIp = '127.0.0.1'
        Write-RelayLog "Starting relay listeners without a live WSL target; waiting for '$distro' to be started manually."
    }
}
[HermesWslRelay]::TargetAddress = $chosenIp

if ($SelfTest) {
    Write-RelayState $config $chosenIp ''
    Write-RelayLog "SELFTEST PASS under $([string]$PSVersionTable.PSEdition) $([string]$PSVersionTable.PSVersion); WSL target=$chosenIp."
    try { $mutex.ReleaseMutex() } catch { }
    exit 0
}

foreach ($service in $services) {
    [HermesWslRelay]::Start([int]$service.bridgePort, [int]$service.backendPort)
}

$initialStateTarget = if (-not [string]::IsNullOrWhiteSpace($chosenIp)) { $chosenIp } else { $seedTarget }
$initialDetail = if (Test-RelayTargetForServices $chosenIp $services) { '' } else { 'Relay listeners are ready; waiting for the WSL backend.' }
Write-RelayState $config $initialStateTarget $initialDetail
Write-RelayLog "Started native relay listeners for $distro; current target=$chosenIp; mode=$script:RelayTargetMode"

$lastRecoveryAttempt = [DateTime]::MinValue
while ($true) {
    Start-Sleep -Seconds $RefreshSeconds
    try {
        foreach ($eventLine in @([HermesWslRelay]::DrainEvents())) {
            if (-not [string]::IsNullOrWhiteSpace([string]$eventLine)) { Write-RelayLog ("TCP: " + [string]$eventLine) }
        }
        $currentIp = [HermesWslRelay]::TargetAddress
        $newIp = ''

        # Healthy cached targets require no wsl.exe invocation. Only after the target
        # fails do we consult the live networking mode of an already-running distro.
        if (Test-RelayTargetForServices $currentIp $services) {
            $newIp = $currentIp
        } else {
            $liveMode = Get-ActiveWslNetworkingMode $distro
            if ($liveMode -eq 'mirrored') {
                if ($script:RelayTargetMode -ne 'mirrored-localhost') {
                    Write-RelayLog "Live WSL networking changed to mirrored; switching relay target policy to localhost."
                    $script:RelayTargetMode = 'mirrored-localhost'
                }
                if (Test-RelayTargetForServices '127.0.0.1' $services) { $newIp = '127.0.0.1' }
            } else {
                if ($liveMode -and $script:RelayTargetMode -ne 'wsl-ip') {
                    Write-RelayLog "Live WSL networking changed to $liveMode; switching relay target policy to WSL IPv4 discovery."
                    $script:RelayTargetMode = 'wsl-ip'
                }
                $newIp = Find-ReachableWslIp $distro $services ([Math]::Min($RefreshSeconds, 8))
            }
        }

        if (-not $newIp -and $EnsureDistroRunning -and ([DateTime]::UtcNow - $lastRecoveryAttempt).TotalSeconds -ge 60) {
            $lastRecoveryAttempt = [DateTime]::UtcNow
            if (Start-HermesStack $distro) {
                if ($script:RelayTargetMode -eq 'mirrored-localhost') {
                    if (Test-RelayTargetForServices '127.0.0.1' $services) { $newIp = '127.0.0.1' }
                } else {
                    $newIp = Find-ReachableWslIp $distro $services 60
                }
            }
        }
        if ($newIp) {
            if ($newIp -ne [HermesWslRelay]::TargetAddress) {
                $oldIp = [HermesWslRelay]::TargetAddress
                [HermesWslRelay]::TargetAddress = $newIp
                Write-RelayLog "WSL target changed $oldIp -> $newIp"
            }
            $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
            $liveModeForState = Get-ActiveWslNetworkingMode $distro
            if ($liveModeForState) { $config.networkingMode = $liveModeForState }
            $config.targetMode = $script:RelayTargetMode
            Write-RelayState $config $newIp ''
        } else {
            $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
            $unreachableDetail = if ($EnsureDistroRunning) { 'WSL backend temporarily unreachable; recovery will retry.' } else { 'WSL backend temporarily unreachable; passive relay is waiting for the user to start Hermes.' }
            $lastKnownTarget = if (-not [string]::IsNullOrWhiteSpace([HermesWslRelay]::TargetAddress)) { [HermesWslRelay]::TargetAddress } elseif ($config.PSObject.Properties.Name -contains 'lastTargetAddress') { [string]$config.lastTargetAddress } else { [string]$config.lastWslIp }
            Write-RelayState $config $lastKnownTarget $unreachableDetail
        }
    } catch {
        Write-RelayLog ("Refresh warning: " + $_.Exception.Message)
    }
}
