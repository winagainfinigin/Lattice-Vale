#Requires -Version 5.1
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$DistroName = '',
    [string]$LinuxUser = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-Info([string]$Message) { Write-Host "    $Message" -ForegroundColor DarkGray }
function Read-YesNo([string]$Question, [bool]$Default = $false) {
    $suffix = if ($Default) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $answer = Read-Host "$Question $suffix"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        switch ($answer.Trim().ToLowerInvariant()) {
            'y' { return $true }; 'yes' { return $true }; 'n' { return $false }; 'no' { return $false }
            default { Write-Host 'Enter Y or N.' -ForegroundColor Yellow }
        }
    }
}
function Read-Menu([string]$Question, [string[]]$Options, [int]$Default = 1) {
    while ($true) {
        Write-Host "`n$Question" -ForegroundColor White
        for ($i=0; $i -lt $Options.Count; $i++) {
            $tag = if (($i+1) -eq $Default) { ' [default]' } else { '' }
            Write-Host "  [$($i+1)] $($Options[$i])$tag"
        }
        $answer = Read-Host "Select 1-$($Options.Count) [$Default]"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        $value=0
        if ([int]::TryParse($answer,[ref]$value) -and $value -ge 1 -and $value -le $Options.Count) { return $value }
        Write-Host 'Enter one of the listed numbers.' -ForegroundColor Yellow
    }
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
    $psi.FileName=$FilePath; $psi.Arguments=(($Arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }) -join ' '); $psi.UseShellExecute=$false; $psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true; $psi.CreateNoWindow=$true
    $p=New-Object System.Diagnostics.Process; $p.StartInfo=$psi
    [void]$p.Start(); $outTask=$p.StandardOutput.ReadToEndAsync(); $errTask=$p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($TimeoutSeconds*1000)) { try { $p.Kill() } catch {}; return [pscustomobject]@{Success=$false;TimedOut=$true;ExitCode=-1;Text='Timed out'} }
    $out=$outTask.GetAwaiter().GetResult(); $err=$errTask.GetAwaiter().GetResult()
    return [pscustomobject]@{Success=($p.ExitCode -eq 0);TimedOut=$false;ExitCode=$p.ExitCode;Text=(($out+"`n"+$err).Trim())}
}
function Invoke-Wsl([string]$Name,[string]$User,[string]$Command,[string[]]$CommandArgs=@(),[int]$TimeoutSeconds=60) {
    $all=@('-d',$Name,'-u',$User,'--',$Command)+$CommandArgs
    return Invoke-NativeCapture 'wsl.exe' $all $TimeoutSeconds
}
function Get-WslDistros {
    $r=Invoke-NativeCapture 'wsl.exe' @('--list','--quiet') 20
    if (-not $r.Success) { throw "Could not enumerate WSL distributions: $($r.Text)" }
    return @(($r.Text.Replace([string][char]0,'') -split "`r?`n") | ForEach-Object {$_.Trim()} | Where-Object {$_})
}
function Test-WslDistro([string]$Name) { return [bool](@(Get-WslDistros) | Where-Object {$_.Equals($Name,[StringComparison]::OrdinalIgnoreCase)}) }
function Get-WslPasswdEntries([string]$Name) {
    # Avoid sending a large discovery program through `bash -lc`. Each field is read
    # through a direct WSL invocation so Windows argument serialization cannot turn a
    # probe failure into a false "no stack found" result.
    $r=Invoke-Wsl $Name 'root' 'getent' @('passwd') 20
    if (-not $r.Success) { throw "Could not read Linux accounts from '$Name': $($r.Text)" }
    $entries=New-Object System.Collections.Generic.List[object]
    foreach ($line in ($r.Text -split "`r?`n")) {
        if (-not $line) { continue }
        $parts=$line -split ':',7
        if ($parts.Count -lt 7) { continue }
        $uid=0; $gid=0
        if (-not [int]::TryParse($parts[2],[ref]$uid)) { continue }
        if (-not [int]::TryParse($parts[3],[ref]$gid)) { continue }
        $user=$parts[0]; $homePath=$parts[5]; $shell=$parts[6]
        if (-not $user -or $user -eq 'nobody') { continue }
        if (-not $homePath -or -not $homePath.StartsWith('/')) { continue }
        if ($shell -match '(?:nologin|/false)$') { continue }
        # Prefer normal interactive accounts, but do not reject an otherwise proven
        # LatticeVale stack solely because a distribution uses a nonstandard primary GID.
        if ($uid -lt 1000 -or $uid -gt 65534) { continue }
        $entries.Add([pscustomobject]@{User=$user;Uid=$uid;Gid=$gid;Home=$homePath;Shell=$shell})
    }
    return @($entries)
}
function Test-WslPath([string]$Name,[string]$Path,[ValidateSet('e','d','f','L')] [string]$Kind='e') {
    $r=Invoke-Wsl $Name 'root' '/usr/bin/test' @("-$Kind",$Path) 15
    return [bool]$r.Success
}
function Get-LatticeValeUsers([string]$Name) {
    $results=New-Object System.Collections.Generic.List[object]
    foreach ($entry in @(Get-WslPasswdEntries $Name)) {
        $stack=$entry.Home.TrimEnd('/')+'/hermes-stack'
        if (-not (Test-WslPath $Name $stack 'd')) { continue }
        if (Test-WslPath $Name $stack 'L') {
            $results.Add([pscustomobject]@{User=$entry.User;Home=$entry.Home;Stack=$stack;Classification='unsafe-symlink';Evidence='stack-symlink'})
            continue
        }
        $evidence=New-Object System.Collections.Generic.List[string]
        $metadata=$false
        foreach ($marker in @('install-options.json','.installer-state.json','.install-info','.configured')) {
            if (Test-WslPath $Name ($stack+'/'+$marker) 'f') { $evidence.Add($marker); $metadata=$true }
        }
        $core=$true
        foreach ($marker in @('compose.yaml','configure-stack.sh','manage.sh')) {
            if (Test-WslPath $Name ($stack+'/'+$marker) 'f') { $evidence.Add($marker) } else { $core=$false }
        }
        foreach ($marker in @('state-audit.py','compose.latticevale.yaml')) {
            if (Test-WslPath $Name ($stack+'/'+$marker) 'f') { $evidence.Add($marker) }
        }
        $backup=$false
        $backupDir=$stack+'/backups'
        if (Test-WslPath $Name $backupDir 'd') {
            $find=Invoke-Wsl $Name 'root' 'find' @($backupDir,'-mindepth','2','-maxdepth','2','-type','f','(','-name','installer-config.tar.gz','-o','-name','files.tar.gz',')','-print','-quit') 20
            if ($find.Success -and $find.Text.Trim()) { $backup=$true; $evidence.Add('backup-metadata') }
        }
        $classification=''
        if ($metadata) { $classification='managed-metadata' }
        elseif ($core -and $backup) { $classification='managed-recovery' }
        elseif ($core) { $classification='partial-runtime' }
        if ($classification) {
            $results.Add([pscustomobject]@{User=$entry.User;Home=$entry.Home;Stack=$stack;Classification=$classification;Evidence=($evidence -join ',')})
        }
    }
    return @($results)
}
function Get-HermesStackDiagnostics([string]$Name) {
    $diagnostics=New-Object System.Collections.Generic.List[string]
    try { $entries=@(Get-WslPasswdEntries $Name) } catch { return @("Discovery probe failed: $($_.Exception.Message)") }
    foreach ($entry in $entries) {
        $stack=$entry.Home.TrimEnd('/')+'/hermes-stack'
        if (-not (Test-WslPath $Name $stack 'e')) { continue }
        $markers=New-Object System.Collections.Generic.List[string]
        foreach ($f in @('install-options.json','.installer-state.json','.install-info','.configured','compose.yaml','configure-stack.sh','manage.sh','state-audit.py','compose.latticevale.yaml')) {
            if (Test-WslPath $Name ($stack+'/'+$f) 'e') { $markers.Add($f) }
        }
        if (Test-WslPath $Name $stack 'L') { $markers.Add('STACK_IS_SYMLINK') }
        if ($markers.Count -eq 0) { $markers.Add('no-recognized-markers') }
        $diagnostics.Add("$($entry.User): $stack [$($markers -join ',')]")
    }
    if ($diagnostics.Count -eq 0) {
        # Last-resort read-only scan catches home-directory/account metadata that is
        # unusual enough not to appear in the interactive-account pass. It never makes
        # a path deletable by itself; selection still requires ownership markers and
        # Assert-SelectedStackTarget validates the exact passwd home before deletion.
        $scan=Invoke-Wsl $Name 'root' 'find' @('/home','-mindepth','2','-maxdepth','2','-type','d','-name','hermes-stack','-print') 20
        if ($scan.Success) {
            foreach ($path in ($scan.Text -split "`r?`n")) { if ($path.Trim()) { $diagnostics.Add("unmapped candidate: $($path.Trim())") } }
        }
    }
    return @($diagnostics)
}
function Assert-SelectedStackTarget([string]$Name,[string]$User,[string]$Stack) {
    $script=@'
set -e
user="$1"; stack="$2"
entry="$(getent passwd "$user" || true)"
[ -n "$entry" ] || { echo "Selected Linux user no longer exists: $user" >&2; exit 2; }
home="$(printf '%s\n' "$entry" | cut -d: -f6)"
[ -n "$home" ] && [ "${home#/}" != "$home" ] || { echo 'Selected Linux user has no absolute home directory.' >&2; exit 2; }
expected="${home%/}/hermes-stack"
[ "$stack" = "$expected" ] || { echo "Refusing unexpected stack path '$stack'; expected '$expected'." >&2; exit 3; }
[ -d "$stack" ] || { echo "Selected stack directory no longer exists: $stack" >&2; exit 3; }
[ ! -L "$stack" ] || { echo "Refusing symbolic-link stack path: $stack" >&2; exit 3; }
'@
    $r=Invoke-Wsl $Name 'root' 'bash' @('-lc',$script,'bash',$User,$Stack) 20
    if (-not $r.Success) { throw "Unsafe or stale uninstall target: $($r.Text)" }
}
function Select-Distro {
    $distros=@(Get-WslDistros)
    if ($distros.Count -eq 0) { throw 'No WSL distributions are registered. There is no WSL LatticeVale stack to uninstall.' }
    $candidates=New-Object System.Collections.Generic.List[string]
    foreach ($d in $distros) { if (@(Get-LatticeValeUsers $d).Count -gt 0) { $candidates.Add($d) } }
    if ($candidates.Count -eq 1) { return $candidates[0] }
    # Keep the menu choices as an array even when the fallback contains exactly one distro.
    # A scalar string would make $shown[0] return only the first character of the distro name.
    if ($candidates.Count -gt 0) { $shown=@($candidates) } else { $shown=@($distros) }
    $choice=Read-Menu 'Which existing WSL distro should LatticeVale be removed from?' $shown 1
    return $shown[$choice-1]
}
function Select-User([string]$Name) {
    $users=@(Get-LatticeValeUsers $Name | Where-Object {$_.Classification -ne 'unsafe-symlink'})
    if ($users.Count -eq 0) {
        $diagnostics=@(Get-HermesStackDiagnostics $Name)
        $detail=if ($diagnostics.Count -gt 0) { " Detected candidate paths: " + ($diagnostics -join '; ') } else { '' }
        throw "No safely recognizable LatticeVale ~/hermes-stack was found for a compatible normal user in '$Name'. The uninstaller now recognizes completed installs, installer-state recovery installs, backup-recoverable installs, and staged partial runtimes. Nothing was deleted.$detail"
    }
    if ($users.Count -eq 1) {
        Write-Info "Detected LatticeVale stack for '$($users[0].User)' as $($users[0].Classification) (evidence: $($users[0].Evidence))."
        return $users[0]
    }
    $labels=@($users | ForEach-Object { "$($_.User) - $($_.Stack) [$($_.Classification)]" })
    $choice=Read-Menu 'Which LatticeVale stack should be removed?' $labels 1
    return $users[$choice-1]
}
function Get-CurrentWindowsIdentityName {
    try { $n=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name; if ($n) { return $n } } catch {}
    return "$env:USERDOMAIN\$env:USERNAME".Trim('\')
}
function Get-TaskBase([string]$Name) {
    $safe=([regex]::Replace($Name,'[^A-Za-z0-9._-]','_')).Trim('_'); if (-not $safe) {$safe='distro'}; if ($safe.Length -gt 36) {$safe=$safe.Substring(0,36)}
    $identity="$(Get-CurrentWindowsIdentityName)`n$Name"; $sha=[Security.Cryptography.SHA256]::Create()
    try { $hash=$sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($identity)); $suffix=-join($hash[0..4] | ForEach-Object {$_.ToString('x2')}) } finally {$sha.Dispose()}
    return "LatticeVale Stack - $safe-$suffix"
}
function Get-ArtifactPaths([string]$Name,[string]$User,[string]$StackLinuxPath) {
    $base=Get-TaskBase $Name
    $safeName=([regex]::Replace($Name,'[^A-Za-z0-9._-]','_')).Trim('_'); if (-not $safeName) {$safeName='distro'}; if ($safeName.Length -gt 40) {$safeName=$safeName.Substring(0,40)}
    $safeUser=([regex]::Replace($User,'[^A-Za-z0-9._-]','_')).Trim('_'); if (-not $safeUser) {$safeUser='user'}; if ($safeUser.Length -gt 32) {$safeUser=$safeUser.Substring(0,32)}
    $identity="$(Get-CurrentWindowsIdentityName)`n$Name`n$User`n$StackLinuxPath"; $sha=[Security.Cryptography.SHA256]::Create()
    try { $hash=$sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($identity)); $suffix=-join($hash[0..5] | ForEach-Object {$_.ToString('x2')}) } finally {$sha.Dispose()}
    $dir=Join-Path $env:LOCALAPPDATA 'LatticeVale'; $desktop=[Environment]::GetFolderPath('Desktop')
    $nativeTask=$base -replace '^LatticeVale Stack - ','LatticeVale Native Windows Bridge - '
    $relayTask=$base -replace '^LatticeVale Stack - ','LatticeVale Tailscale Relay - '
    $nativeKey=([regex]::Replace($nativeTask,'[^A-Za-z0-9._-]','_')).Trim('_'); if ($nativeKey.Length -gt 96) {$nativeKey=$nativeKey.Substring(0,96)}
    $relayKey=([regex]::Replace($relayTask,'[^A-Za-z0-9._-]','_')).Trim('_'); if ($relayKey.Length -gt 96) {$relayKey=$relayKey.Substring(0,96)}
    return [pscustomobject]@{
        Directory=$dir; StackTask=$base; RelayTask=$relayTask; NativeTask=$nativeTask; NativeKey=$nativeKey; RelayKey=$relayKey
        RelayConfig=(Join-Path $dir "bridge-$relayKey.json"); NativeConfig=(Join-Path $dir "native-services-$nativeKey.json"); DirectState=(Join-Path $dir "ollama-wsl-direct-$nativeKey.json")
        ShortcutConfig=(Join-Path $dir "shortcut-$safeName-$safeUser-$suffix.json"); ShortcutHelper=(Join-Path $dir "LatticeVale-Shortcut-$safeName-$safeUser-$suffix.ps1"); ShortcutLog=(Join-Path $dir "shortcut-$safeName-$safeUser-$suffix.log")
        StartShortcut=(Join-Path $desktop "Start LatticeVale - $safeName ($safeUser).lnk"); ShutdownShortcut=(Join-Path $desktop "Shut Down LatticeVale - $safeName ($safeUser).lnk")
    }
}
function Test-AnyScheduledTaskReferencesPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try {
        foreach ($task in @(Get-ScheduledTask -ErrorAction SilentlyContinue)) {
            foreach ($a in @($task.Actions)) {
                $blob=([string]$a.Execute)+' '+([string]$a.Arguments)
                if ($blob.IndexOf($Path,[StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
            }
        }
    } catch { return $true }
    return $false
}
function Remove-TaskIfOwned([string]$TaskName,[string[]]$Needles) {
    $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) { return }
    $owned=$false
    foreach ($a in @($task.Actions)) {
        $blob=([string]$a.Execute)+' '+([string]$a.Arguments)
        $match=$true; foreach ($needle in $Needles) { if ($blob.IndexOf($needle,[StringComparison]::OrdinalIgnoreCase) -lt 0) {$match=$false;break} }
        if ($match) {$owned=$true;break}
    }
    if (-not $owned) { Write-Warning "Scheduled task '$TaskName' is not provably LatticeVale-owned; it was left untouched."; return }
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Info "Removed scheduled task '$TaskName'."
}
function Test-ShortcutOwned([string]$Path,[string]$Helper,[string]$Config) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try { $s=(New-Object -ComObject WScript.Shell).CreateShortcut($Path); return (([string]$s.Arguments).IndexOf($Helper,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and ([string]$s.Arguments).IndexOf($Config,[StringComparison]::OrdinalIgnoreCase) -ge 0) } catch { return $false }
}
function Test-AnyDesktopShortcutReferencesPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    $desktop=[Environment]::GetFolderPath('Desktop')
    if ([string]::IsNullOrWhiteSpace($desktop) -or -not (Test-Path -LiteralPath $desktop -PathType Container)) { return $false }
    try {
        $shell=New-Object -ComObject WScript.Shell
        $inspectionFailed=$false
        foreach ($link in @(Get-ChildItem -LiteralPath $desktop -Filter '*.lnk' -File -Recurse -ErrorAction SilentlyContinue)) {
            try {
                $shortcut=$shell.CreateShortcut($link.FullName)
                $blob=([string]$shortcut.TargetPath)+' '+([string]$shortcut.Arguments)
                if ($blob.IndexOf($Path,[StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
            } catch { $inspectionFailed=$true }
        }
        if ($inspectionFailed) { return $true }
    } catch { return $true }
    return $false
}
function Remove-Shortcuts([object]$Paths) {
    foreach ($p in @($Paths.StartShortcut,$Paths.ShutdownShortcut)) {
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            if (Test-ShortcutOwned $p $Paths.ShortcutHelper $Paths.ShortcutConfig) { Remove-Item -LiteralPath $p -Force; Write-Info "Removed shortcut '$p'." }
            else { Write-Warning "Shortcut '$p' is not provably LatticeVale-owned; it was left untouched." }
        }
    }
    $stillReferenced=(Test-AnyDesktopShortcutReferencesPath $Paths.ShortcutHelper) -or (Test-AnyDesktopShortcutReferencesPath $Paths.ShortcutConfig)
    if ($stillReferenced) {
        Write-Warning 'A desktop shortcut still references this stack-specific LatticeVale shortcut helper/config, so those supporting files were preserved.'
    } else {
        Remove-Item -LiteralPath $Paths.ShortcutConfig,$Paths.ShortcutHelper,$Paths.ShortcutLog -Force -ErrorAction SilentlyContinue
    }
}
function Remove-NativeFirewall([object]$Paths) {
    if ((Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallRule -ErrorAction SilentlyContinue)) {
        foreach ($r in @(Get-NetFirewallRule -Group 'LatticeVale' -ErrorAction SilentlyContinue | Where-Object {([string]$_.Name) -like "LatticeValeNativeBridge-$($Paths.NativeKey)-*"})) { $r | Remove-NetFirewallRule -ErrorAction SilentlyContinue }
    }
    if ((Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
        foreach ($r in @(Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue | Where-Object {([string]$_.Name) -like "LatticeValeNativeBridge-HyperV-$($Paths.NativeKey)-*"})) { $r | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue }
    }
}
function Send-LatticeValeEnvironmentChanged {
    try {
        if (-not ('LatticeValeEnvironmentBroadcast' -as [type])) {
            Add-Type -Language CSharp -ErrorAction Stop -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LatticeValeEnvironmentBroadcast {
    [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
    public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint flags, uint timeout, out UIntPtr result);
}
'@
        }
        $result=[UIntPtr]::Zero
        [void][LatticeValeEnvironmentBroadcast]::SendMessageTimeout([IntPtr]0xffff,0x1A,[UIntPtr]::Zero,'Environment',2,5000,[ref]$result)
    } catch { Write-Warning "Restored the Windows environment value, but the environment-change broadcast failed: $($_.Exception.Message)" }
}
function Restore-DirectOllamaState([object]$Paths) {
    if (-not (Test-Path -LiteralPath $Paths.DirectState -PathType Leaf)) { return }
    try { $s=Get-Content -LiteralPath $Paths.DirectState -Raw | ConvertFrom-Json } catch { Write-Warning 'Could not parse installer-owned direct Ollama state; leaving environment/firewall state untouched.'; return }
    if ($s.firewallRuleName -and (Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallRule -ErrorAction SilentlyContinue)) {
        $rule=Get-NetFirewallRule -Name ([string]$s.firewallRuleName) -ErrorAction SilentlyContinue
        if ($rule -and [string]$rule.Group -eq 'LatticeVale') { $rule | Remove-NetFirewallRule -ErrorAction SilentlyContinue }
        elseif ($rule) { Write-Warning 'The saved direct-Ollama firewall rule name now belongs to a non-LatticeVale rule, so it was preserved.' }
    }
    if ($s.hyperVFirewallRuleName -and (Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
        Get-NetFirewallHyperVRule -Name ([string]$s.hyperVFirewallRuleName) -ErrorAction SilentlyContinue | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue
    }
    $target=if ([string]$s.environmentScope -eq 'Machine') {[EnvironmentVariableTarget]::Machine} else {[EnvironmentVariableTarget]::User}
    $current=[Environment]::GetEnvironmentVariable('OLLAMA_HOST',$target)
    if ([string]$current -eq [string]$s.configuredHost) {
        $restore=if ([bool]$s.previousHostWasSet) {[string]$s.previousHost} else {$null}
        [Environment]::SetEnvironmentVariable('OLLAMA_HOST',$restore,$target)
        Send-LatticeValeEnvironmentChanged
        Write-Info "Restored the pre-LatticeVale OLLAMA_HOST value at $($s.environmentScope) scope. Native Ollama will consume the restored value the next time it is restarted."
    } else { Write-Warning 'OLLAMA_HOST no longer matches the installer-owned value, so the current setting was preserved.' }
    Remove-Item -LiteralPath $Paths.DirectState -Force -ErrorAction SilentlyContinue
}
function Read-StackMetadata([string]$Name,[string]$User,[string]$Stack) {
    $script=@'
set -e
stack="$1"
for f in .tailscale-info .windows-native-info install-options.json .install-info; do
  if [ -f "$stack/$f" ]; then
    printf '---%s---\n' "$f"
    cat "$stack/$f"
    printf '\n---END---\n'
  fi
done
'@
    $r=Invoke-Wsl $Name 'root' 'bash' @('-lc',$script,'bash',$Stack) 20
    if (-not $r.Success) { throw "Could not read uninstall metadata from '$Stack': $($r.Text)" }
    return $r.Text
}
function Get-MetadataBlock([string]$Text,[string]$Name) {
    $pattern='(?s)---'+[regex]::Escape($Name)+'---\r?\n(.*?)\r?\n---END---'
    $m=[regex]::Match($Text,$pattern); if ($m.Success) {return $m.Groups[1].Value}; return ''
}
function Get-KeyValue([string]$Text,[string]$Key) {
    foreach ($line in ($Text -split "`r?`n")) { if ($line -match ('^'+[regex]::Escape($Key)+'=(.*)$')) {return $Matches[1].Trim()} }
    return ''
}
function Find-TailscaleExe {
    $candidates=New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) { $candidates.Add((Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe')) }
    $pf86=[Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if (-not [string]::IsNullOrWhiteSpace($pf86)) { $candidates.Add((Join-Path $pf86 'Tailscale\tailscale.exe')) }
    foreach ($p in $candidates) { if (Test-Path -LiteralPath $p -PathType Leaf) {return $p} }
    $cmd=Get-Command tailscale.exe -ErrorAction SilentlyContinue; if ($cmd) {return $cmd.Source}; return ''
}
function Add-TailscaleServeJsonState([object]$Config,[int]$Port,[System.Collections.Generic.List[string]]$Targets,[ref]$InUse) {
    if ($null -eq $Config) { return }
    $configs=@($Config)
    if ($Config.PSObject.Properties.Name -contains 'Services' -and $Config.Services) {
        foreach ($service in $Config.Services.PSObject.Properties) { $configs += $service.Value }
    }
    foreach ($cfg in $configs) {
        if ($null -eq $cfg) { continue }
        if ($cfg.PSObject.Properties.Name -contains 'TCP' -and $cfg.TCP) {
            foreach ($tcp in $cfg.TCP.PSObject.Properties) { if ([string]$tcp.Name -eq [string]$Port) { $InUse.Value=$true } }
        }
        if ($cfg.PSObject.Properties.Name -contains 'Web' -and $cfg.Web) {
            foreach ($web in $cfg.Web.PSObject.Properties) {
                if ([string]$web.Name -notmatch (':' + [regex]::Escape([string]$Port) + '$')) { continue }
                $InUse.Value=$true
                if ($web.Value.Handlers) {
                    foreach ($handler in $web.Value.Handlers.PSObject.Properties) {
                        $proxy=$handler.Value.Proxy; if ($proxy) { $Targets.Add([string]$proxy) }
                    }
                }
            }
        }
    }
    foreach ($servicesPropertyName in @('services','Services')) {
        if (-not ($Config.PSObject.Properties.Name -contains $servicesPropertyName)) { continue }
        $servicesNode=$Config.PSObject.Properties[$servicesPropertyName].Value
        if (-not $servicesNode) { continue }
        foreach ($service in $servicesNode.PSObject.Properties) {
            foreach ($endpointPropertyName in @('endpoints','Endpoints')) {
                if (-not ($service.Value.PSObject.Properties.Name -contains $endpointPropertyName)) { continue }
                $endpoints=$service.Value.PSObject.Properties[$endpointPropertyName].Value
                if (-not $endpoints) { continue }
                foreach ($endpoint in $endpoints.PSObject.Properties) {
                    if ([string]$endpoint.Name -notmatch ('(^|:)' + [regex]::Escape([string]$Port) + '$')) { continue }
                    $InUse.Value=$true
                    if ($endpoint.Value -is [string] -and -not [string]::IsNullOrWhiteSpace([string]$endpoint.Value)) { $Targets.Add([string]$endpoint.Value) }
                }
            }
        }
    }
}
function Test-TailscaleBackendTarget([string]$Target,[int]$BackendPort) {
    if ([string]::IsNullOrWhiteSpace($Target) -or $BackendPort -le 0) { return $false }
    $text=$Target.Trim().TrimEnd('/'); $portText=[regex]::Escape([string]$BackendPort)
    return [bool]($text -match "^(?i:http://)?(?:127\.0\.0\.1|localhost):$portText$")
}
function Get-TailscaleServePortState([string]$Exe,[int]$Port,[int]$BackendPort) {
    $result=[ordered]@{Known=$false;InUse=$false;MatchesExpected=$false;Targets=@()}
    $targets=New-Object System.Collections.Generic.List[string]; $inUse=$false
    foreach ($cmdArgs in @(@('serve','status','--json'),@('serve','get-config','--all'))) {
        try {
            $probe=Invoke-NativeCapture $Exe $cmdArgs 20
            if (-not $probe.Success -or [string]::IsNullOrWhiteSpace($probe.Text)) { continue }
            $cfg=$probe.Text | ConvertFrom-Json -ErrorAction Stop
            $result.Known=$true
            Add-TailscaleServeJsonState $cfg $Port $targets ([ref]$inUse)
        } catch {}
    }
    $result.InUse=$inUse; $result.Targets=@($targets | Select-Object -Unique)
    if ($result.InUse) { foreach ($target in $result.Targets) { if (Test-TailscaleBackendTarget ([string]$target) $BackendPort) { $result.MatchesExpected=$true; break } } }
    return [pscustomobject]$result
}
function Remove-TailscaleServe([string]$Info) {
    if (-not $Info) { return }
    $exe=Find-TailscaleExe; if (-not $exe) { Write-Warning 'Tailscale metadata exists but tailscale.exe is unavailable; Serve mappings could not be removed automatically.'; return }
    foreach ($pair in @(@('DASHBOARD_HTTPS_PORT','DASHBOARD_BRIDGE_PORT','Dashboard'),@('MATRIX_HTTPS_PORT','MATRIX_BRIDGE_PORT','Matrix'))) {
        $port=Get-KeyValue $Info $pair[0]; $backend=Get-KeyValue $Info $pair[1]
        if ($port -notmatch '^\d+$' -or [int]$port -le 0 -or $backend -notmatch '^\d+$' -or [int]$backend -le 0) { continue }
        $state=Get-TailscaleServePortState $exe ([int]$port) ([int]$backend)
        if (-not $state.Known) { Write-Warning "Could not safely inspect Tailscale Serve HTTPS port $port; the recorded $($pair[2]) mapping was left untouched."; continue }
        if (-not $state.InUse) { continue }
        if (-not $state.MatchesExpected) { Write-Warning "Tailscale HTTPS port $port no longer points to the recorded LatticeVale $($pair[2]) backend and was left untouched."; continue }
        $off=Invoke-NativeCapture $exe @('serve',"--https=$port",'off') 30
        if ($off.Success) { Write-Info "Removed installer-tracked Tailscale $($pair[2]) Serve listener on HTTPS port $port." }
        else { Write-Warning "Could not remove the installer-tracked Tailscale $($pair[2]) Serve listener on HTTPS port $port." }
    }
}
function Stop-And-RemoveStack([string]$Name,[string]$User,[string]$Stack,[bool]$Purge) {
    $script=@'
set -u
stack="$1"; purge="$2"
if [ ! -d "$stack" ]; then exit 0; fi
cd "$stack" || exit 2
if [ -x ./manage.sh ] && [ -f .configured ]; then timeout --foreground --kill-after=10s 90s ./manage.sh stop >/dev/null 2>&1 || true; fi
if [ -x ./native-ollama-relay.sh ]; then ./native-ollama-relay.sh stop >/dev/null 2>&1 || true; fi
if [ -f compose.yaml ]; then
  runtime_may_exist=false
  if [ -f .configured ] || [ -f .install-info ]; then runtime_may_exist=true; fi
  if [ -s .installer-state.json ] && command -v python3 >/dev/null 2>&1; then
    if python3 - .installer-state.json <<'PY_RUNTIME_EVIDENCE' >/dev/null 2>&1
import json,sys
try: d=json.load(open(sys.argv[1],encoding='utf-8'))
except Exception: raise SystemExit(1)
st=(d.get('stages') or {}).get('infrastructure') or {}
raise SystemExit(0 if st.get('status') in ('running','done','broken') else 1)
PY_RUNTIME_EVIDENCE
    then runtime_may_exist=true; fi
  fi
  if command -v docker >/dev/null 2>&1 && timeout --foreground --kill-after=5s 15s docker info >/dev/null 2>&1; then
    if ! timeout --foreground --kill-after=10s 120s docker compose down --remove-orphans >/dev/null 2>&1; then
      echo 'Docker is running, but the LatticeVale Compose runtime could not be removed safely. Stack data was preserved.' >&2
      exit 4
    fi
  elif [ "$runtime_may_exist" = true ]; then
    echo 'The selected stack may still have Docker runtime state, but the Docker daemon is unavailable. Refusing a partial uninstall/purge that could leave restartable containers behind. Start/repair Docker, then rerun the uninstaller.' >&2
    exit 5
  fi
fi
if [ "$purge" = true ]; then
  expected="${HOME%/}/hermes-stack"
  [ "$stack" = "$expected" ] || { echo "Refusing unsafe purge path: $stack (expected $expected for the selected user)" >&2; exit 3; }
  [ ! -L "$stack" ] || { echo "Refusing to purge symlink stack: $stack" >&2; exit 3; }
  mountpoint -q -- "$stack" 2>/dev/null && { echo "Refusing to purge mountpoint stack: $stack" >&2; exit 3; }
  if command -v findmnt >/dev/null 2>&1; then
    while IFS= read -r target; do
      case "$target" in "$stack"/*) echo "Refusing to purge stack containing nested mountpoint: $target" >&2; exit 3;; esac
    done < <(findmnt -rn -o TARGET 2>/dev/null || true)
  fi
  rm -rf --one-file-system -- "$stack"
fi
'@
    $r=Invoke-Wsl $Name $User 'bash' @('-lc',$script,'bash',$Stack,($(if($Purge){'true'}else{'false'}))) 180
    if (-not $r.Success) { throw "WSL stack cleanup failed: $($r.Text)" }
}
function Remove-LinuxHostArtifacts([string]$Name,[string]$Stack,[bool]$Purge) {
    $script=@'
set -e
stack="$1"; purge="$2"
helper=/usr/local/sbin/hermes-stack-start
if [ -f "$helper" ] && grep -Fq "$stack" "$helper" 2>/dev/null; then rm -f "$helper"; fi
relay_unit=/etc/systemd/system/latticevale-native-ollama-relay.service
if [ -f "$relay_unit" ] && grep -Fq "$stack/native-ollama-relay.sh" "$relay_unit" 2>/dev/null; then
  if command -v systemctl >/dev/null 2>&1; then systemctl disable --now latticevale-native-ollama-relay.service >/dev/null 2>&1 || true; fi
  rm -f "$relay_unit"
  if command -v systemctl >/dev/null 2>&1; then systemctl daemon-reload >/dev/null 2>&1 || true; fi
fi
policy=/etc/apt/apt.conf.d/52hermes-unattended-upgrades
other_stack=false
while IFS=: read -r candidate_user _ candidate_uid _ _ candidate_home candidate_shell; do
  case "$candidate_uid" in ''|*[!0-9]*) continue;; esac
  [ "$candidate_uid" -ge 1000 ] && [ "$candidate_uid" -le 65534 ] || continue
  case "$candidate_shell" in *nologin|*/false) continue;; esac
  case "$candidate_home" in /*) ;; *) continue;; esac
  candidate="${candidate_home%/}/hermes-stack"
  [ -d "$candidate" ] || continue
  [ "$candidate" = "$stack" ] && continue
  if [ -f "$candidate/install-options.json" ] || [ -f "$candidate/.installer-state.json" ] || [ -f "$candidate/.install-info" ] || [ -f "$candidate/.configured" ]; then other_stack=true; break; fi
  if [ -f "$candidate/compose.yaml" ] && [ -f "$candidate/configure-stack.sh" ] && [ -f "$candidate/manage.sh" ]; then other_stack=true; break; fi
done < <(getent passwd 2>/dev/null || true)
if [ "$other_stack" = false ]; then
  if [ -f "$policy" ] && grep -Fq 'Installer-owned policy' "$policy"; then rm -f "$policy"; fi
  rm -f /var/log/hermes-dockerd.log 2>/dev/null || true
fi
# Shared Docker/prerequisite packages, repositories, Ubuntu Pro, GPU runtime, and the distro itself are deliberately preserved.
'@
    $r=Invoke-Wsl $Name 'root' 'bash' @('-lc',$script,'bash',$Stack,($(if($Purge){'true'}else{'false'}))) 30
    if (-not $r.Success) { Write-Warning "Some installer-owned Linux host helpers could not be removed: $($r.Text)" }
}
function Mark-PreservedStackUninstalled([string]$Name,[string]$User,[string]$Stack) {
    $script=@'
set -e
stack="$1"
[ -d "$stack" ] || exit 0
rm -f "$stack/.tailscale-info" "$stack/.windows-native-info" "$stack/.windows-native-host-ip"
printf 'UNINSTALLED_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$stack/.latticevale-uninstalled"
chmod 0600 "$stack/.latticevale-uninstalled"
'@
    $r=Invoke-Wsl $Name $User 'bash' @('-lc',$script,'bash',$Stack) 20
    if (-not $r.Success) { Write-Warning "Could not mark the preserved stack as uninstalled: $($r.Text)" }
}
function Cleanup-AppData([object]$Paths) {
    foreach ($ownedConfig in @($Paths.RelayConfig,$Paths.NativeConfig)) {
        if (-not (Test-Path -LiteralPath $ownedConfig -PathType Leaf)) { continue }
        if (Test-AnyScheduledTaskReferencesPath $ownedConfig) {
            Write-Warning "A scheduled task still references '$ownedConfig', so that installer-owned config was preserved instead of breaking the remaining task."
        } else {
            Remove-Item -LiteralPath $ownedConfig -Force -ErrorAction SilentlyContinue
        }
    }
    if (Test-Path -LiteralPath $Paths.Directory -PathType Container) {
        $specific=@(Get-ChildItem -LiteralPath $Paths.Directory -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -like "*-$($Paths.RelayKey).*" -or $_.Name -like "*-$($Paths.NativeKey).*"
        })
        foreach ($f in $specific) {
            if (Test-AnyScheduledTaskReferencesPath $f.FullName) {
                Write-Warning "A scheduled task still references '$($f.FullName)', so that stack-specific integration file was preserved."
            } else {
                Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            }
        }
        $configs=@(Get-ChildItem -LiteralPath $Paths.Directory -File -Filter 'bridge-*.json' -ErrorAction SilentlyContinue)+@(Get-ChildItem -LiteralPath $Paths.Directory -File -Filter 'native-services-*.json' -ErrorAction SilentlyContinue)
        if ($configs.Count -eq 0) {
            foreach ($shared in @('LatticeVale-WslNativeRelay.ps1','LatticeVale-WindowsNativeServiceRelay.ps1','native-relay.log','windows-native-service-relay.log','Refresh-HermesWslBridge.ps1')) {
                $sharedPath=Join-Path $Paths.Directory $shared
                if ((Test-Path -LiteralPath $sharedPath -PathType Leaf) -and (Test-AnyScheduledTaskReferencesPath $sharedPath)) {
                    Write-Warning "A scheduled task still references '$sharedPath', so the shared relay file was preserved."
                } else {
                    Remove-Item -LiteralPath $sharedPath -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if (@(Get-ChildItem -LiteralPath $Paths.Directory -Force -ErrorAction SilentlyContinue).Count -eq 0) { Remove-Item -LiteralPath $Paths.Directory -Force -ErrorAction SilentlyContinue }
    }
}
function Offer-WslConfigRestore {
    $path=Join-Path $env:USERPROFILE '.wslconfig'
    $backups=@(Get-ChildItem -LiteralPath $env:USERPROFILE -File -Filter '.wslconfig.latticevale-pre-*.bak' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($backups.Count -eq 0) { return }
    Write-Host "`nLatticeVale backup(s) of the global .wslconfig were found." -ForegroundColor Yellow
    Write-Host 'Restoring one can undo LatticeVale WSL settings, but it also replaces the current global .wslconfig and could overwrite later manual changes.' -ForegroundColor Yellow
    if (Read-YesNo "Restore the newest pre-LatticeVale .wslconfig backup '$($backups[0].Name)'?" $false) {
        Copy-Item -LiteralPath $backups[0].FullName -Destination $path -Force
        Write-Info "Restored '$path' from '$($backups[0].FullName)'. Run 'wsl --shutdown' later when convenient for global WSL settings to take effect."
    } else { Write-Info 'Current .wslconfig was preserved.' }
}

Write-Host 'LatticeVale uninstaller' -ForegroundColor Cyan
Write-Host 'This removes LatticeVale from an existing WSL installation. It never unregisters the WSL distro.'
if ([string]::IsNullOrWhiteSpace($DistroName)) { $DistroName=Select-Distro }
if (-not (Test-WslDistro $DistroName)) { throw "WSL distro '$DistroName' is not registered." }
if ([string]::IsNullOrWhiteSpace($LinuxUser)) { $selected=Select-User $DistroName } else {
    $selected=@(Get-LatticeValeUsers $DistroName | Where-Object {$_.User -eq $LinuxUser -and $_.Classification -ne 'unsafe-symlink'} | Select-Object -First 1)[0]
    if (-not $selected) {
        $diagnostics=@(Get-HermesStackDiagnostics $DistroName)
        $detail=if ($diagnostics.Count -gt 0) { " Detected candidate paths: " + ($diagnostics -join '; ') } else { '' }
        throw "No safely recognizable LatticeVale stack was found for user '$LinuxUser' in '$DistroName'. Nothing was deleted.$detail"
    }
}
$LinuxUser=$selected.User; $stack=$selected.Stack
Assert-SelectedStackTarget $DistroName $LinuxUser $stack
$paths=Get-ArtifactPaths $DistroName $LinuxUser $stack
$metadata=Read-StackMetadata $DistroName $LinuxUser $stack
$tailscaleInfo=Get-MetadataBlock $metadata '.tailscale-info'
$windowsNativeInfo=Get-MetadataBlock $metadata '.windows-native-info'

Write-Host "`nTarget: $DistroName / $LinuxUser / $stack" -ForegroundColor White
$mode=Read-Menu 'Choose uninstall mode:' @(
    'Remove LatticeVale runtime/integrations but PRESERVE ~/hermes-stack data for reinstall/recovery',
    'FULL PURGE: remove LatticeVale runtime/integrations AND permanently delete ~/hermes-stack data',
    'Cancel'
) 1
if ($mode -eq 3) { Write-Host 'Uninstall cancelled.'; exit 0 }
$purge=($mode -eq 2)
if ($purge) {
    Write-Host "`nFULL PURGE permanently deletes: $stack" -ForegroundColor Red
    Write-Host 'This can include Hermes configuration, Matrix/Honcho databases, QMD state, managed Ollama models, secrets, logs, backups, and the default internal vault/workspace.' -ForegroundColor Yellow
    Write-Host 'A separately selected Windows-backed Obsidian vault is outside this stack and is not deleted.' -ForegroundColor Yellow
    $confirm=Read-Host "Type PURGE to permanently delete the LatticeVale stack data"
    if ($confirm -cne 'PURGE') { Write-Host 'Full purge cancelled; nothing has been removed.'; exit 0 }
}

Write-Step 'Stopping the selected LatticeVale stack'
Stop-And-RemoveStack $DistroName $LinuxUser $stack $purge

Write-Step 'Removing installer-owned Windows integrations'
Remove-TaskIfOwned $paths.StackTask @('wsl.exe',$DistroName,'hermes-stack-start')
Remove-TaskIfOwned $paths.RelayTask @($paths.RelayConfig)
Remove-TaskIfOwned $paths.NativeTask @($paths.NativeConfig)
Remove-Shortcuts $paths
Remove-TailscaleServe $tailscaleInfo
Restore-DirectOllamaState $paths
Remove-NativeFirewall $paths
Cleanup-AppData $paths
if (-not $purge) { Mark-PreservedStackUninstalled $DistroName $LinuxUser $stack }

Write-Step 'Removing installer-owned Linux host helpers'
Remove-LinuxHostArtifacts $DistroName $stack $purge

Offer-WslConfigRestore

Write-Host "`nLatticeVale uninstall completed for $DistroName / $LinuxUser." -ForegroundColor Green
if (-not $purge) { Write-Host "Preserved stack data: $stack" -ForegroundColor Yellow }
Write-Host 'Preserved by design: the WSL distro, Docker Engine/packages, general Ubuntu prerequisite packages, Ubuntu Pro attachment, Windows Ollama/Tailscale/Obsidian apps, external Windows-backed Obsidian vaults, and unrelated firewall/tasks/settings.'
