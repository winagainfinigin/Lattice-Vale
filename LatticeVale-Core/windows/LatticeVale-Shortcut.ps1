#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ConfigPath,
    [Parameter(Mandatory=$true)][ValidateSet('Start','Shutdown')][string]$Action
)

$ErrorActionPreference = 'Stop'

function Write-ShortcutLog([string]$Message) {
    try {
        $target = [string]$script:Config.logPath
        if ([string]::IsNullOrWhiteSpace($target)) { return }
        $dir = Split-Path -Parent $target
        if ($dir) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $line = "{0} [{1}] {2}" -f ([DateTimeOffset]::Now.ToString('o')), $Action.ToUpperInvariant(), $Message
        Add-Content -LiteralPath $target -Value $line -Encoding UTF8
    } catch { }
}

function Get-RunningWslDistros([string]$WslExe) {
    try {
        $raw = (& $WslExe --list --running --quiet 2>$null | Out-String).Replace([string][char]0, '')
        return @(($raw -split "`r?`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    } catch {
        return @()
    }
}

function Test-NativeOllamaApi([object]$NativeConfig) {
    if (-not $NativeConfig) { return $false }
    $endpoint = [string]$NativeConfig.apiEndpoint
    if ([string]::IsNullOrWhiteSpace($endpoint)) { $endpoint = 'http://127.0.0.1:11434' }
    $response = $null
    try {
        $request = [System.Net.HttpWebRequest]::Create(($endpoint.TrimEnd('/') + '/api/version'))
        $request.Method = 'GET'
        $request.Timeout = 3000
        $request.ReadWriteTimeout = 3000
        $request.Proxy = $null
        $response = $request.GetResponse()
        $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
        try { $json = $reader.ReadToEnd() } finally { $reader.Dispose() }
        $payload = $json | ConvertFrom-Json
        return ($payload -and $payload.PSObject.Properties['version'] -and -not [string]::IsNullOrWhiteSpace([string]$payload.version))
    } catch {
        return $false
    } finally {
        if ($response) { try { $response.Close() } catch { } }
    }
}

function Set-NativeOllamaLaunchEnvironment {
    # A fresh shortcut process should normally inherit current user variables, but read
    # the persisted scopes explicitly so an older Windows logon environment cannot make
    # a newly-persisted OLLAMA_HOST disappear when the shortcut starts the tray app.
    $value = ''
    foreach ($scope in @('User','Machine')) {
        try {
            $target = if ($scope -eq 'User') { [EnvironmentVariableTarget]::User } else { [EnvironmentVariableTarget]::Machine }
            $candidate = [string][Environment]::GetEnvironmentVariable('OLLAMA_HOST',$target)
            if (-not [string]::IsNullOrWhiteSpace($candidate)) { $value = $candidate.Trim().Trim('"'); break }
        } catch { }
    }
    if ([string]::IsNullOrWhiteSpace($value)) { Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue }
    else { $env:OLLAMA_HOST = $value }
}

function Start-NativeOllamaForShortcut([object]$NativeConfig) {
    if (-not $NativeConfig) { return }
    $enabled = $false
    try { $enabled = [bool]$NativeConfig.enabled } catch { }
    if (-not $enabled) { return }

    if (Test-NativeOllamaApi $NativeConfig) {
        Write-ShortcutLog 'Native Windows Ollama API is already running; leaving the existing process untouched.'
        return
    }

    Set-NativeOllamaLaunchEnvironment
    $app = [string]$NativeConfig.appExecutable
    $cli = [string]$NativeConfig.executable
    $serviceName = [string]$NativeConfig.serviceName
    $launched = $false

    if (-not [string]::IsNullOrWhiteSpace($serviceName)) {
        $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
        if ($service) {
            if ($service.Status -ne 'Running') {
                Write-ShortcutLog "Native Windows Ollama API is stopped; starting configured Windows service '$serviceName'."
                try { Start-Service -Name $serviceName -ErrorAction Stop } catch {
                    throw "Native Windows Ollama is installed as service '$serviceName', but the Start shortcut could not start it: $($_.Exception.Message)"
                }
            } else {
                Write-ShortcutLog "Configured native Ollama service '$serviceName' is already running; waiting for its API instead of launching a second server."
            }
            $launched = $true
        }
    }

    if (-not $launched -and -not [string]::IsNullOrWhiteSpace($app) -and (Test-Path -LiteralPath $app -PathType Leaf)) {
        Write-ShortcutLog "Native Windows Ollama API is stopped; starting the configured Ollama application '$app'."
        Start-Process -FilePath $app -ErrorAction Stop | Out-Null
        $launched = $true
    } elseif (-not $launched -and -not [string]::IsNullOrWhiteSpace($cli) -and (Test-Path -LiteralPath $cli -PathType Leaf)) {
        # The CLI is a fallback only when no tray application path was recorded. Refuse
        # to start a second server when an Ollama-named process is already alive.
        $existing = @()
        try { $existing = @(Get-CimInstance Win32_Process -Filter "Name='ollama.exe' OR Name='ollama app.exe'" -ErrorAction SilentlyContinue) } catch { }
        if ($existing.Count -gt 0) {
            throw 'Native Windows Ollama processes are running but the configured local API is unavailable. The Start shortcut will not launch a duplicate `ollama serve`; restart Ollama normally or rerun LatticeVale Resume / repair.'
        }
        Write-ShortcutLog "Native Windows Ollama API is stopped; starting the configured Ollama CLI server '$cli serve'."
        Start-Process -FilePath $cli -ArgumentList @('serve') -WindowStyle Hidden -ErrorAction Stop | Out-Null
        $launched = $true
    }

    if (-not $launched) {
        throw 'Native Windows Ollama is selected, but the startup shortcut no longer has a valid Ollama application/CLI path. Rerun LatticeVale Resume / repair to refresh the shortcut configuration.'
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        Start-Sleep -Seconds 1
        if (Test-NativeOllamaApi $NativeConfig) {
            Write-ShortcutLog 'Native Windows Ollama API became ready.'
            return
        }
    } while ([DateTime]::UtcNow -lt $deadline)

    throw 'Native Windows Ollama was started by the LatticeVale shortcut but its configured local API did not become ready within 45 seconds.'
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "LatticeVale shortcut configuration not found: $ConfigPath"
}
$script:Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
foreach ($name in @('distroName','linuxUser','stackLinuxPath')) {
    if (-not $script:Config.PSObject.Properties[$name] -or [string]::IsNullOrWhiteSpace([string]$script:Config.$name)) {
        throw "LatticeVale shortcut configuration is missing '$name'."
    }
}
$distro = [string]$script:Config.distroName
$user = [string]$script:Config.linuxUser
$stack = [string]$script:Config.stackLinuxPath
if (-not $stack.StartsWith('/')) { throw 'stackLinuxPath must be an absolute Linux path.' }
$wslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
if (-not (Test-Path -LiteralPath $wslExe -PathType Leaf)) { throw "wsl.exe not found at $wslExe" }
$manageCommand = 'cd -- "$1" && ./manage.sh "$2"'

try {
    if ($Action -eq 'Start') {
        Write-ShortcutLog "Starting distro '$distro' and its selected LatticeVale services."
        $nativeConfig = $null
        if ($script:Config.PSObject.Properties['nativeOllama']) { $nativeConfig = $script:Config.nativeOllama }
        Start-NativeOllamaForShortcut $nativeConfig
        & $wslExe -d $distro -u root -- /usr/local/sbin/hermes-stack-start
        if ($LASTEXITCODE -ne 0) { throw "WSL root startup helper exited with code $LASTEXITCODE." }
        & $wslExe -d $distro -u $user -- bash -lc $manageCommand bash $stack start
        if ($LASTEXITCODE -ne 0) { throw "manage.sh start exited with code $LASTEXITCODE." }
        Write-ShortcutLog 'Start completed successfully.'
        exit 0
    }

    $running = Get-RunningWslDistros $wslExe
    if (-not ($running -contains $distro)) {
        Write-ShortcutLog "Distro '$distro' is already stopped; nothing to shut down."
        exit 0
    }

    Write-ShortcutLog "Stopping selected LatticeVale services in '$distro'."
    & $wslExe -d $distro -u $user -- bash -lc $manageCommand bash $stack stop
    $stopExit = $LASTEXITCODE
    if ($stopExit -ne 0) {
        Write-ShortcutLog "manage.sh stop returned code $stopExit; continuing with distro termination."
    }
    & $wslExe --terminate $distro
    if ($LASTEXITCODE -ne 0) { throw "wsl.exe --terminate exited with code $LASTEXITCODE." }
    Write-ShortcutLog "Distro '$distro' terminated successfully."
    exit 0
} catch {
    Write-ShortcutLog ("FAILED: " + $_.Exception.Message)
    exit 1
}
