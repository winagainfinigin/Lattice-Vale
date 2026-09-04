#Requires -Version 5.1
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$RemoveWslRuntime,
    [switch]$RemoveLegacyHermesFoundry,
    [switch]$DeleteLatticeValeSource,
    [string]$LatticeValeSourcePath = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-Info([string]$Message) { Write-Host "    $Message" -ForegroundColor DarkGray }
function Write-Would([string]$Message) { Write-Host "    WOULD: $Message" -ForegroundColor Yellow }
function Invoke-ResetAction([string]$Description, [scriptblock]$Action) {
    if (-not $Execute) { Write-Would $Description; return }
    Write-Info $Description
    & $Action
}
function ConvertTo-NativeArgument([string]$Argument) {
    if ($null -eq $Argument -or $Argument.Length -eq 0) { return '""' }
    if ($Argument -notmatch '[\s"]') { return $Argument }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($ch in $Argument.ToCharArray()) {
        if ([int]$ch -eq 92) { $slashes++; continue }
        if ($ch -eq '"') {
            [void]$builder.Append(('\' * (($slashes * 2) + 1)))
            [void]$builder.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) { [void]$builder.Append(('\' * $slashes)); $slashes = 0 }
        [void]$builder.Append($ch)
    }
    if ($slashes -gt 0) { [void]$builder.Append(('\' * ($slashes * 2))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}
function Invoke-NativeCapture([string]$FilePath,[string[]]$Arguments,[int]$TimeoutSeconds=30) {
    $psi=New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName=$FilePath
    $psi.Arguments=(($Arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }) -join ' ')
    $psi.UseShellExecute=$false
    $psi.RedirectStandardOutput=$true
    $psi.RedirectStandardError=$true
    $psi.CreateNoWindow=$true
    $p=New-Object System.Diagnostics.Process
    $p.StartInfo=$psi
    [void]$p.Start()
    $outTask=$p.StandardOutput.ReadToEndAsync(); $errTask=$p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($TimeoutSeconds*1000)) {
        try { $p.Kill() } catch {}
        return [pscustomobject]@{Success=$false;ExitCode=-1;Text='Timed out'}
    }
    $out=$outTask.GetAwaiter().GetResult(); $err=$errTask.GetAwaiter().GetResult()
    return [pscustomobject]@{Success=($p.ExitCode -eq 0);ExitCode=$p.ExitCode;Text=(($out+"`n"+$err).Trim())}
}
function Get-WslDistros {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return @() }
    $r=Invoke-NativeCapture 'wsl.exe' @('--list','--quiet') 20
    if (-not $r.Success) { return @() }
    return @(($r.Text.Replace([string][char]0,'') -split "`r?`n") | ForEach-Object {$_.Trim()} | Where-Object {$_})
}
function Get-WslRegistrationSnapshot {
    $root='HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
    if (-not (Test-Path $root)) { return @() }
    $items=[System.Collections.Generic.List[object]]::new()
    foreach ($key in Get-ChildItem $root -ErrorAction SilentlyContinue) {
        try {
            $p=Get-ItemProperty $key.PSPath
            $items.Add([pscustomobject]@{Name=[string]$p.DistributionName;BasePath=[string]$p.BasePath;Key=$key.PSPath})
        } catch {}
    }
    return $items.ToArray()
}
function Get-OwnedWindowsRoots {
    return @(
        (Join-Path $env:LOCALAPPDATA 'LatticeVale'),
        (Join-Path (Join-Path $env:LOCALAPPDATA 'Hermes') 'Foundry')
    )
}
function Test-TextOwned([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    foreach ($root in Get-OwnedWindowsRoots) {
        if ($Text.IndexOf($root,[StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    }
    if ($Text -match '(?i)\bLatticeVale\b') { return $true }
    if ($RemoveLegacyHermesFoundry -and $Text -match '(?i)Hermes(?: WSL)? Foundry|Hermes WSL (?:Docker Stack|Tailscale Bridge|Native Relay)') { return $true }
    return $false
}
function Get-OptionalPropertyString([object]$Object,[string]$Name) {
    if ($null -eq $Object -or [string]::IsNullOrWhiteSpace($Name)) { return '' }
    $property=$Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) { return '' }
    return [string]$property.Value
}
function Get-ScheduledTaskActionText([object]$Action) {
    if ($null -eq $Action) { return '' }
    $parts=[System.Collections.Generic.List[string]]::new()
    # Task Scheduler supports heterogeneous action types (Exec, COM handler,
    # and legacy action forms). Read only properties that actually exist so
    # StrictMode and unrelated non-Exec tasks cannot break a clean-host audit.
    foreach ($name in @('Type','Id','Execute','Path','Arguments','WorkingDirectory','ClassId','Data')) {
        $value=Get-OptionalPropertyString $Action $name
        if (-not [string]::IsNullOrWhiteSpace($value)) { $parts.Add($value) }
    }
    return ($parts -join ' ')
}
function Remove-OwnedTasks {
    foreach ($task in @(Get-ScheduledTask -ErrorAction SilentlyContinue)) {
        $actionText=((@($task.Actions) | ForEach-Object { Get-ScheduledTaskActionText $_ }) -join ' ; ')
        $blob=([string]$task.TaskName)+' '+([string]$task.TaskPath)+' '+$actionText
        if (-not (Test-TextOwned $blob)) { continue }
        if (-not $Execute) { Write-Would "remove scheduled task '$($task.TaskPath)$($task.TaskName)'"; continue }
        Stop-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Confirm:$false -ErrorAction SilentlyContinue
        Write-Info "Removed scheduled task '$($task.TaskPath)$($task.TaskName)'."
    }
}
function Stop-OwnedRelayProcesses {
    foreach ($p in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
        if ($p.Name -notmatch '^(?i:pwsh|powershell|wscript|cscript)\.exe$') { continue }
        if (-not (Test-TextOwned ([string]$p.CommandLine))) { continue }
        if (-not $Execute) { Write-Would "stop installer/Foundry relay process PID $($p.ProcessId) ($($p.Name))"; continue }
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Info "Stopped owned relay/helper process PID $($p.ProcessId)."
    }
}
function Remove-OwnedFirewallRules {
    if (Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue) {
        foreach ($r in @(Get-NetFirewallRule -ErrorAction SilentlyContinue)) {
            $blob=([string]$r.Name)+' '+([string]$r.DisplayName)+' '+([string]$r.Description)+' '+([string]$r.Group)
            if (-not (Test-TextOwned $blob)) { continue }
            if (-not $Execute) { Write-Would "remove firewall rule '$($r.DisplayName)'"; continue }
            $r | Remove-NetFirewallRule -ErrorAction SilentlyContinue
            Write-Info "Removed firewall rule '$($r.DisplayName)'."
        }
    }
    if ((Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
        foreach ($r in @(Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
            $blob=([string]$r.Name)+' '+([string]$r.DisplayName)
            if (-not (Test-TextOwned $blob)) { continue }
            if (-not $Execute) { Write-Would "remove Hyper-V firewall rule '$($r.DisplayName)'"; continue }
            $r | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue
            Write-Info "Removed Hyper-V firewall rule '$($r.DisplayName)'."
        }
    }
}
function Get-ShortcutRoots {
    $roots=@(
        [Environment]::GetFolderPath('Desktop'),
        [Environment]::GetFolderPath('CommonDesktopDirectory'),
        [Environment]::GetFolderPath('StartMenu'),
        [Environment]::GetFolderPath('CommonStartMenu'),
        [Environment]::GetFolderPath('Startup'),
        [Environment]::GetFolderPath('CommonStartup'),
        (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'),
        (Join-Path $env:APPDATA 'Microsoft\Windows\Recent')
    )
    return @($roots | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique)
}
function Remove-OwnedShortcuts {
    $shell=New-Object -ComObject WScript.Shell
    $files=[System.Collections.Generic.List[object]]::new()
    $seen=[System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($root in Get-ShortcutRoots) {
        foreach ($file in @(Get-ChildItem -LiteralPath $root -Filter '*.lnk' -Recurse -Force -ErrorAction SilentlyContinue)) {
            if ($seen.Add($file.FullName)) { $files.Add($file) }
        }
    }
    # Older LatticeVale/Foundry builds could place Start/Shutdown shortcuts at
    # the root of a fixed local drive. Inspect only root-level .lnk files and
    # still require content/name ownership proof before removing anything.
    foreach ($disk in @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction SilentlyContinue)) {
        $driveRoot=([string]$disk.DeviceID)+'\'
        foreach ($file in @(Get-ChildItem -LiteralPath $driveRoot -Filter '*.lnk' -File -Force -ErrorAction SilentlyContinue)) {
            if ($seen.Add($file.FullName)) { $files.Add($file) }
        }
    }
    foreach ($file in @($files)) {
        $blob=$file.Name
        try {
            $s=$shell.CreateShortcut($file.FullName)
            $blob += ' '+([string]$s.TargetPath)+' '+([string]$s.Arguments)+' '+([string]$s.WorkingDirectory)
        } catch {}
        if (-not (Test-TextOwned $blob)) { continue }
        if (-not $Execute) { Write-Would "remove shortcut/recent link '$($file.FullName)'"; continue }
        Remove-Item -LiteralPath $file.FullName -Force -ErrorAction SilentlyContinue
        Write-Info "Removed '$($file.FullName)'."
    }
}
function Remove-LegacyHermesPathEntries {
    if (-not $RemoveLegacyHermesFoundry) { return }
    $path=[Environment]::GetEnvironmentVariable('Path',[EnvironmentVariableTarget]::User)
    if ([string]::IsNullOrWhiteSpace($path)) { return }
    $legacyBin=(Join-Path (Join-Path $env:LOCALAPPDATA 'hermes') 'bin').TrimEnd('\')
    $legacyFoundry=(Join-Path (Join-Path $env:LOCALAPPDATA 'Hermes') 'Foundry').TrimEnd('\')
    $latticeRoot=(Join-Path $env:LOCALAPPDATA 'LatticeVale').TrimEnd('\')
    $parts=@($path -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $kept=[System.Collections.Generic.List[string]]::new()
    $removed=[System.Collections.Generic.List[string]]::new()
    foreach ($part in $parts) {
        $trim=$part.Trim().TrimEnd('\')
        $owned=$trim.Equals($legacyBin,[StringComparison]::OrdinalIgnoreCase) -or $trim.StartsWith($legacyFoundry+'\',[StringComparison]::OrdinalIgnoreCase) -or $trim.Equals($legacyFoundry,[StringComparison]::OrdinalIgnoreCase) -or $trim.StartsWith($latticeRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $trim.Equals($latticeRoot,[StringComparison]::OrdinalIgnoreCase)
        if ($owned) { $removed.Add($part) } else { $kept.Add($part) }
    }
    if ($removed.Count -eq 0) { return }
    if (-not $Execute) { Write-Would ('remove these user PATH entries: '+($removed -join '; ')); return }
    [Environment]::SetEnvironmentVariable('Path',($kept -join ';'),[EnvironmentVariableTarget]::User)
    Write-Info ('Removed legacy LatticeVale/Foundry user PATH entries: '+($removed -join '; '))
}
function Remove-OwnedAppData {
    $lattice=Join-Path $env:LOCALAPPDATA 'LatticeVale'
    Invoke-ResetAction "remove '$lattice'" { Remove-Item -LiteralPath $lattice -Recurse -Force -ErrorAction SilentlyContinue }
    if ($RemoveLegacyHermesFoundry) {
        $hermesRoot=Join-Path $env:LOCALAPPDATA 'Hermes'
        $foundry=Join-Path $hermesRoot 'Foundry'
        $start=Join-Path $hermesRoot 'Start-Hermes-WSL.vbs'
        Invoke-ResetAction "remove legacy Foundry directory '$foundry'" { Remove-Item -LiteralPath $foundry -Recurse -Force -ErrorAction SilentlyContinue }
        Invoke-ResetAction "remove legacy Foundry launcher '$start'" { Remove-Item -LiteralPath $start -Force -ErrorAction SilentlyContinue }
        if ($Execute -and (Test-Path -LiteralPath $hermesRoot -PathType Container) -and @(Get-ChildItem -LiteralPath $hermesRoot -Force -ErrorAction SilentlyContinue).Count -eq 0) {
            Remove-Item -LiteralPath $hermesRoot -Force -ErrorAction SilentlyContinue
        }
        $temp=$env:TEMP
        foreach ($item in @(Get-ChildItem -LiteralPath $temp -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^(?i:hermes-relay-wsl-|HermesFoundry\.ico$)' })) {
            Invoke-ResetAction "remove legacy temporary artifact '$($item.FullName)'" { Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction SilentlyContinue }
        }
        $wslDvc=Join-Path $temp 'WSLDVCPlugin'
        if (Test-Path -LiteralPath $wslDvc -PathType Container) {
            foreach ($item in @(Get-ChildItem -LiteralPath $wslDvc -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^(?i:Hermes-|LatticeVale-)' })) {
                Invoke-ResetAction "remove legacy WSLDVC artifact '$($item.FullName)'" { Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction SilentlyContinue }
            }
        }
    }
}
function Get-TailscaleExe {
    $cmd=Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate=Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    return ''
}
function Get-LatticeValeTailscalePairs {
    $pairs=[System.Collections.Generic.List[object]]::new()
    $seen=[System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    function Add-Pair([int]$Https,[int]$Backend,[string]$Label) {
        if ($Https -le 0 -or $Backend -le 0) { return }
        $key="$Https/$Backend"
        if ($seen.Add($key)) { $pairs.Add([pscustomobject]@{Https=$Https;Backend=$Backend;Label=$Label}) }
    }
    # Canonical defaults remain useful when the distro is already unavailable.
    Add-Pair 9443 19119 'Dashboard'
    Add-Pair 443 18008 'Matrix'
    if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        foreach ($d in @(Get-WslDistros)) {
            $find=Invoke-NativeCapture 'wsl.exe' @('-d',$d,'-u','root','--','find','/home','-mindepth','3','-maxdepth','3','-type','f','-path','*/hermes-stack/.tailscale-info','-print') 20
            if (-not $find.Success) { continue }
            foreach ($path in @($find.Text -split "`r?`n" | ForEach-Object {$_.Trim()} | Where-Object {$_})) {
                $cat=Invoke-NativeCapture 'wsl.exe' @('-d',$d,'-u','root','--','cat',$path) 20
                if (-not $cat.Success) { continue }
                $kv=@{}
                foreach ($line in ($cat.Text -split "`r?`n")) { if ($line -match '^([A-Z0-9_]+)=(.*)$') { $kv[$Matches[1]]=$Matches[2].Trim() } }
                $hp=0; $bp=0
                if ([int]::TryParse([string]$kv['DASHBOARD_HTTPS_PORT'],[ref]$hp) -and [int]::TryParse([string]$kv['DASHBOARD_BRIDGE_PORT'],[ref]$bp)) { Add-Pair $hp $bp 'Dashboard' }
                $hp=0; $bp=0
                if ([int]::TryParse([string]$kv['MATRIX_HTTPS_PORT'],[ref]$hp) -and [int]::TryParse([string]$kv['MATRIX_BRIDGE_PORT'],[ref]$bp)) { Add-Pair $hp $bp 'Matrix' }
            }
        }
    }
    return $pairs.ToArray()
}
function Remove-KnownLatticeValeTailscaleServe {
    $exe=Get-TailscaleExe
    if (-not $exe) { return }
    $probe=Invoke-NativeCapture $exe @('serve','status','--json') 20
    if (-not $probe.Success -or [string]::IsNullOrWhiteSpace($probe.Text)) { return }
    $raw=$probe.Text
    foreach ($pair in @(Get-LatticeValeTailscalePairs)) {
        $backendPattern='(?i)(?:127\.0\.0\.1|localhost):'+[regex]::Escape([string]$pair.Backend)
        $httpsPattern='(?i)(?:"|:|\b)'+[regex]::Escape([string]$pair.Https)+'(?:"|\b)'
        if ($raw -notmatch $backendPattern -or $raw -notmatch $httpsPattern) { continue }
        if (-not $Execute) { Write-Would "disable Tailscale Serve HTTPS $($pair.Https) because it points at the canonical LatticeVale $($pair.Label) bridge port $($pair.Backend)"; continue }
        $off=Invoke-NativeCapture $exe @('serve',"--https=$($pair.Https)",'off') 20
        if ($off.Success) { Write-Info "Disabled LatticeVale $($pair.Label) Tailscale Serve listener on HTTPS $($pair.Https)." }
        else { Write-Warning "Could not disable Tailscale Serve HTTPS $($pair.Https); inspect it manually before reusing that port." }
    }
}
function Remove-WslConfigState {
    foreach ($item in @(Get-ChildItem -LiteralPath $env:USERPROFILE -Force -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '.wslconfig*' })) {
        Invoke-ResetAction "remove global WSL configuration/backup '$($item.FullName)'" { Remove-Item -LiteralPath $item.FullName -Force -ErrorAction SilentlyContinue }
    }
}
function Remove-WslRuntimeAndDistros {
    if (-not $RemoveWslRuntime) { return }
    $registrations=@(Get-WslRegistrationSnapshot)
    $distros=@(Get-WslDistros)
    if ($distros.Count -gt 0) {
        Write-Host "Registered WSL distributions selected for permanent removal:" -ForegroundColor Yellow
        foreach ($d in $distros) { Write-Host "  - $d" -ForegroundColor Yellow }
    }
    foreach ($d in $distros) {
        Invoke-ResetAction "PERMANENTLY unregister WSL distro '$d'" {
            $r=Invoke-NativeCapture 'wsl.exe' @('--unregister',$d) 180
            if (-not $r.Success) { throw "wsl --unregister '$d' failed: $($r.Text)" }
        }
    }
    foreach ($reg in $registrations) {
        if ([string]::IsNullOrWhiteSpace($reg.BasePath)) { continue }
        $base=[string]$reg.BasePath
        if ($base -match '^[A-Za-z]:\\' -and (Test-Path -LiteralPath $base)) {
            Invoke-ResetAction "remove former distro storage '$base' after unregister" { Remove-Item -LiteralPath $base -Recurse -Force -ErrorAction SilentlyContinue }
        }
        $parent=Split-Path -Parent $base
        if ($parent -and ([System.IO.Path]::GetFileName($parent.TrimEnd('\\')) -ieq 'WSL')) {
            if (-not $Execute) { Write-Would "remove parent WSL storage directory '$parent' if it is empty after all distros are removed" }
            elseif ((Test-Path -LiteralPath $parent -PathType Container) -and @(Get-ChildItem -LiteralPath $parent -Force -ErrorAction SilentlyContinue).Count -eq 0) { Remove-Item -LiteralPath $parent -Force -ErrorAction SilentlyContinue }
        }
    }
    Remove-WslConfigState
    if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
        Invoke-ResetAction 'uninstall the Microsoft Store/MSI Windows Subsystem for Linux package (Microsoft.WSL)' {
            $p=Start-Process -FilePath 'winget.exe' -ArgumentList @('uninstall','--id','Microsoft.WSL','-e','--silent','--accept-source-agreements','--disable-interactivity') -Wait -PassThru -NoNewWindow
            if ($p.ExitCode -ne 0) { Write-Warning "winget could not uninstall Microsoft.WSL (exit $($p.ExitCode)). Use Settings > Apps > Installed apps > Windows Subsystem for Linux if it remains installed." }
        }
    } else {
        Write-Warning 'winget.exe is unavailable. The WSL distributions/global configuration can still be removed, but uninstall the Windows Subsystem for Linux app manually afterward.'
    }
}
function Remove-SourceTree {
    if (-not $DeleteLatticeValeSource) { return }
    $path=$LatticeValeSourcePath
    if ([string]::IsNullOrWhiteSpace($path)) { $path=Split-Path -Parent $PSScriptRoot }
    $resolved=''
    try { $resolved=[System.IO.Path]::GetFullPath($path) } catch { throw "Invalid LatticeValeSourcePath: $path" }
    if ($resolved -eq [System.IO.Path]::GetPathRoot($resolved)) { throw 'Refusing to delete a filesystem root.' }
    $version=Join-Path $resolved 'LatticeVale-Core\VERSION.txt'
    $install=Join-Path $resolved 'installer\Install-LatticeVale.ps1'
    if (-not (Test-Path -LiteralPath $version -PathType Leaf) -or -not (Test-Path -LiteralPath $install -PathType Leaf)) {
        throw "Refusing to delete source path '$resolved' because it is not recognizably a LatticeVale release root."
    }
    $current=(Get-Location).Path
    if ($current.StartsWith($resolved,[StringComparison]::OrdinalIgnoreCase)) { Set-Location ($env:SystemDrive + '\\') }
    Invoke-ResetAction "remove LatticeVale source tree '$resolved'" { Remove-Item -LiteralPath $resolved -Recurse -Force }
}

Write-Host 'LatticeVale clean-host reset utility' -ForegroundColor Cyan
Write-Host 'This is intentionally separate from installer\Uninstall-LatticeVale.ps1 because it can remove WSL itself and legacy Hermes Foundry state.'
Write-Host 'It does NOT remove Tailscale, Obsidian, Hyper-V, HypervisorPlatform, VirtualMachinePlatform, unrelated firewall rules, unrelated HNS networks, or a standalone %USERPROFILE%\.hermes directory.'
if (-not $Execute) { Write-Host "`nDRY RUN ONLY. Re-run with -Execute after reviewing the WOULD lines." -ForegroundColor Yellow }
if ($Execute) {
    Write-Host "`nDESTRUCTIVE RESET requested." -ForegroundColor Red
    if ($RemoveWslRuntime) { Write-Host 'All currently registered WSL distributions will be permanently unregistered.' -ForegroundColor Red }
    $confirm=Read-Host 'Type CLEAN-RESET to continue'
    if ($confirm -cne 'CLEAN-RESET') { Write-Host 'Cancelled. Nothing was changed.'; exit 0 }
}

Write-Step 'Stopping LatticeVale / legacy Foundry Windows helpers'
Remove-OwnedTasks
Stop-OwnedRelayProcesses
Remove-KnownLatticeValeTailscaleServe

Write-Step 'Removing installer-owned Windows integrations'
Remove-OwnedFirewallRules
Remove-OwnedShortcuts
Remove-LegacyHermesPathEntries
Remove-OwnedAppData

if ($RemoveWslRuntime) {
    Write-Step 'Stopping WSL before destructive distro/runtime removal'
    if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        if ($Execute) { & wsl.exe --shutdown 2>$null | Out-Null } else { Write-Would 'run wsl --shutdown' }
    }
    Write-Step 'Removing registered WSL distributions, global .wslconfig state, and the WSL app package'
    Remove-WslRuntimeAndDistros
}

Write-Step 'Optional source-tree cleanup'
Remove-SourceTree

Write-Host "`nClean-host reset $(if($Execute){'completed'}else{'dry run completed'})." -ForegroundColor Green
if ($RemoveWslRuntime) {
    Write-Host 'Reboot Windows before reinstalling WSL. Shared Hyper-V/VirtualMachinePlatform/HNS infrastructure was deliberately not torn down.' -ForegroundColor Yellow
}
