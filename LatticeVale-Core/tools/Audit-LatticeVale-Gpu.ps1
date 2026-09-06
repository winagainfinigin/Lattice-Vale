[CmdletBinding()]
param(
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    if ([string]::IsNullOrWhiteSpace($desktop)) { $desktop = $env:USERPROFILE }
    $OutputPath = Join-Path $desktop ("LatticeVale-GPU-Audit-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}

function Section([string]$Title) {
    Write-Host ''
    Write-Host ('=' * 68)
    Write-Host " $Title"
    Write-Host ('=' * 68)
}

function Invoke-WslScript {
    param(
        [string]$Distro,
        [string]$User,
        [string]$Code
    )
    $bytes = [Text.Encoding]::UTF8.GetBytes($Code)
    $b64 = [Convert]::ToBase64String($bytes)
    $launcher = "printf %s '$b64' | base64 -d | bash"
    & wsl.exe -d $Distro -u $User -- bash -lc $launcher 2>&1
}

Start-Transcript -Path $OutputPath -Force | Out-Null
try {
    Section 'LATTICEVALE GPU / WSL AUDIT (READ-ONLY)'
    Write-Host "Started: $(Get-Date -Format o)"
    Write-Host "Windows: $([Environment]::OSVersion.Version)"
    Write-Host "PowerShell: $($PSVersionTable.PSVersion)"

    Section 'WINDOWS GPU INVENTORY'
    Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
        Select-Object Name, Status, PNPDeviceID, AdapterRAM, DriverVersion, DriverDate |
        Format-List

    Section 'WSL VERSION / STATUS'
    & wsl.exe --version 2>&1
    & wsl.exe --status 2>&1
    & wsl.exe --list --verbose 2>&1

    $distros = @(
        & wsl.exe --list --quiet 2>$null |
            ForEach-Object { ([string]$_ -replace "`0", '').Trim() } |
            Where-Object { $_ -and $_ -notmatch '^docker-desktop' }
    )

    $probeCode = @(
        'set +e',
        'printf ''kernel=''; uname -r',
        'printf ''arch=''; uname -m',
        'for p in /dev/dxg /dev/kfd /usr/lib/wsl/lib/libd3d12.so /usr/lib/wsl/lib/libd3d12core.so /usr/lib/wsl/lib/libdxcore.so; do [[ -e "$p" ]] && echo "$p=present" || echo "$p=missing"; done',
        'shopt -s nullglob',
        'nodes=(/dev/dri/renderD*)',
        'printf ''dri_render_nodes=%s\n'' "${#nodes[@]}"',
        'for p in "${nodes[@]}"; do ls -l "$p"; done',
        'shopt -u nullglob',
        'if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi -L 2>&1 || true; elif [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then /usr/lib/wsl/lib/nvidia-smi -L 2>&1 || true; fi'
    ) -join "`n"

    $discoverCode = @(
        'set +e',
        'find /home /root -maxdepth 4 -type f -name install-options.json -path ''*/hermes-stack/install-options.json'' -print 2>/dev/null | head -20'
    ) -join "`n"

    foreach ($distro in $distros) {
        Section "DISTRO: $distro"
        $user = ([string](& wsl.exe -d $distro -- id -un 2>$null | Select-Object -First 1) -replace "`0", '').Trim()
        if (-not $user) { $user = 'root' }
        Write-Host "Default user: $user"
        Invoke-WslScript -Distro $distro -User $user -Code $probeCode

        $stackFiles = @(
            Invoke-WslScript -Distro $distro -User 'root' -Code $discoverCode |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object { $_ -match '/hermes-stack/install-options\.json$' }
        )

        if ($stackFiles.Count -eq 0) {
            Write-Host 'No managed LatticeVale hermes-stack was discovered in this distro.'
            continue
        }

        foreach ($optionsFile in $stackFiles) {
            $stack = $optionsFile -replace '/install-options\.json$', ''
            Section "STACK: $distro :: $stack"
            $stackB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($stack))
            $stackCode = @(
                "STACK=`$(printf %s '$stackB64' | base64 -d)",
                'cd "$STACK" 2>/dev/null || exit 2',
                'echo ''--- selected GPU options''',
                'jq ''{localTextBackend,directmlAdapterName,directmlGpuVendor,directmlVramMiB,ollamaBackend,ollamaAcceleration}'' install-options.json 2>/dev/null || true',
                'echo ''--- DirectML diagnose''',
                'if [[ -x ./directml-gateway.sh ]]; then ./directml-gateway.sh diagnose 2>&1; ./directml-gateway.sh status 2>&1 || true; else echo ''directml-gateway.sh missing''; fi',
                'echo ''--- gateway log''',
                'tail -n 160 logs/directml-gateway.log 2>/dev/null || true',
                'echo ''--- Docker directml.host route''',
                'if docker inspect hermes-agent >/dev/null 2>&1; then docker inspect hermes-agent --format ''ExtraHosts={{json .HostConfig.ExtraHosts}}'' 2>&1; docker exec hermes-agent getent hosts directml.host 2>&1 || true; fi'
            ) -join "`n"
            Invoke-WslScript -Distro $distro -User $user -Code $stackCode
        }
    }

    Section 'AUDIT COMPLETE'
    Write-Host 'No packages, services, configuration, models, or fallback markers were changed.'
    Write-Host "Report: $OutputPath"
}
finally {
    try { Stop-Transcript | Out-Null } catch { }
}

Write-Host $OutputPath
