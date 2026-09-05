#Requires -Version 5.1
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$DistroName = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Pre-create this lazy compatibility cache so its first read is safe even when a caller
# deliberately invokes the core installer with PowerShell StrictMode enabled.
$script:HermesCompatibility = $null
$script:RequireExplicitQuestionnaireChoices = $false

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Info([string]$Message) {
    Write-Host "    $Message" -ForegroundColor DarkGray
}


function Show-NativeOllamaResourceWarning {
    Write-Host ''
    Write-Host '*** NATIVE WINDOWS OLLAMA GPU/RAM WARNING ***' -ForegroundColor Yellow
    Write-Host 'Native Ollama can keep model weights and context memory loaded in GPU VRAM and system RAM after a request. Large or multiple loaded models can noticeably reduce memory available to games and other applications.' -ForegroundColor Yellow
    Write-Host 'To use conservative user-level limits, run these in Windows PowerShell:' -ForegroundColor White
    Write-Host '[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "1", "User")' -ForegroundColor Cyan
    Write-Host '[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "User")' -ForegroundColor Cyan
    Write-Host '[Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "2m", "User")' -ForegroundColor Cyan
    Write-Host 'Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force' -ForegroundColor Cyan
    Write-Host 'Then reopen Ollama from the Windows Start menu. These settings keep one loaded model, one parallel request, and let an idle model unload after about two minutes unless a request overrides keep_alive.' -ForegroundColor White
    Write-Host 'Ollama also supports OLLAMA_GPU_OVERHEAD (bytes reserved per GPU) when a native-GPU VRAM reserve is needed. LatticeVale explains this control but does not silently set a global Windows value because native Ollama remains user-owned.' -ForegroundColor White
    Write-Host 'These settings affect the separately installed Windows Ollama application, not LatticeVale-managed Docker Ollama.' -ForegroundColor DarkGray
    Write-Host '*** END NATIVE WINDOWS OLLAMA WARNING ***' -ForegroundColor Yellow
    Write-Host ''
}

function Read-YesNo([string]$Question, [bool]$Default = $true) {
    $suffix = if ($Default) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $answer = Read-Host "$Question $suffix"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        switch ($answer.Trim().ToLowerInvariant()) {
            'y' { return $true }
            'yes' { return $true }
            'n' { return $false }
            'no' { return $false }
            default { Write-Host 'Enter Y or N.' -ForegroundColor Yellow }
        }
    }
}

function Read-YesNoExplicit([string]$Question, [object]$Suggested = $null) {
    while ($true) {
        $suggestedLabel = if ($null -eq $Suggested) { '' } elseif ([bool]$Suggested) { '; suggested: Y' } else { '; suggested: N' }
        $answer = Read-Host "$Question [y/n$suggestedLabel; explicit choice required]"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            if ($null -eq $Suggested) {
                Write-Host 'Enter Y or N; this choice has no assumed default.' -ForegroundColor Yellow
            } else {
                $label = if ([bool]$Suggested) { 'Y' } else { 'N' }
                Write-Host "Enter Y or N. Suggested: $label. Pressing Enter alone does not select it." -ForegroundColor Yellow
            }
            continue
        }
        switch ($answer.Trim().ToLowerInvariant()) {
            'y' { return $true }
            'yes' { return $true }
            'n' { return $false }
            'no' { return $false }
            default { Write-Host 'Enter Y or N.' -ForegroundColor Yellow }
        }
    }
}

function Read-ChoiceExplicit(
    [string]$Question,
    [string]$Description,
    [string]$NoResult,
    [bool]$NoStopsInstaller = $false,
    [object]$Suggested = $null
) {
    Write-Info $Description
    if ($NoStopsInstaller) {
        Write-Host "    NO = STOPS THIS INSTALLER RUN: $NoResult" -ForegroundColor Yellow
    } else {
        Write-Host "    NO = SAFE: $NoResult" -ForegroundColor DarkGray
    }
    return Read-YesNoExplicit $Question $Suggested
}

function Read-Choice(
    [string]$Question,
    [string]$Description,
    [string]$NoResult,
    [bool]$Default = $true,
    [bool]$NoStopsInstaller = $false
) {
    Write-Info $Description
    if ($NoStopsInstaller) {
        Write-Host "    NO = STOPS THIS INSTALLER RUN: $NoResult" -ForegroundColor Yellow
    } else {
        Write-Host "    NO = SAFE: $NoResult" -ForegroundColor DarkGray
    }
    if ($script:RequireExplicitQuestionnaireChoices) { return Read-YesNoExplicit $Question $Default }
    return Read-YesNo $Question $Default
}

function Read-Integer([string]$Question, [int]$Default, [int]$Min, [int]$Max) {
    if ($script:RequireExplicitQuestionnaireChoices) { return Read-IntegerExplicit $Question $Min $Max $Default }
    while ($true) {
        $answer = Read-Host "$Question [$Default]"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        $value = 0
        if ([int]::TryParse($answer, [ref]$value) -and $value -ge $Min -and $value -le $Max) { return $value }
        Write-Host "Enter a whole number from $Min to $Max." -ForegroundColor Yellow
    }
}

function Read-IntegerExplicit([string]$Question, [int]$Min, [int]$Max, [object]$Suggested = $null) {
    while ($true) {
        $suggestedLabel = if ($null -eq $Suggested) { '' } else { "; suggested: $Suggested" }
        $answer = Read-Host "$Question ($Min-$Max$suggestedLabel; explicit choice required)"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            if ($null -eq $Suggested) {
                Write-Host 'Enter a number; this selection has no assumed default.' -ForegroundColor Yellow
            } else {
                Write-Host "Enter a number. Suggested: $Suggested. Pressing Enter alone does not select it." -ForegroundColor Yellow
            }
            continue
        }
        $value = 0
        if ([int]::TryParse($answer, [ref]$value) -and $value -ge $Min -and $value -le $Max) { return $value }
        Write-Host "Enter a whole number from $Min to $Max." -ForegroundColor Yellow
    }
}

function Read-TcpPort([string]$Question, [int]$Default, [int[]]$Disallow = @()) {
    while ($true) {
        $prompt = if ($script:RequireExplicitQuestionnaireChoices) { "$Question (1-65535; suggested: $Default; explicit choice required)" } else { "$Question [$Default]" }
        $answer = Read-Host $prompt
        if ([string]::IsNullOrWhiteSpace($answer)) {
            if ($script:RequireExplicitQuestionnaireChoices) {
                Write-Host "Enter a TCP port. Suggested: $Default. Pressing Enter alone does not select it." -ForegroundColor Yellow
                continue
            }
            $value = $Default
        } else {
            $value = 0
            if (-not [int]::TryParse($answer, [ref]$value)) {
                Write-Host 'Enter a TCP port number from 1 to 65535.' -ForegroundColor Yellow
                continue
            }
        }
        if ($value -lt 1 -or $value -gt 65535) {
            Write-Host 'Enter a TCP port number from 1 to 65535.' -ForegroundColor Yellow
            continue
        }
        if ($Disallow -contains $value) {
            Write-Host "Port $value is already selected for another LatticeVale Tailscale service." -ForegroundColor Yellow
            continue
        }
        return $value
    }
}



function Read-Menu([string]$Question, [string[]]$Options, [int]$Default = 1) {
    if ($script:RequireExplicitQuestionnaireChoices) { return Read-MenuExplicit $Question $Options $Default }
    if ($Default -lt 1 -or $Default -gt $Options.Count) { $Default = 1 }
    while ($true) {
        Write-Host "`n$Question" -ForegroundColor White
        for ($i = 0; $i -lt $Options.Count; $i++) {
            $tag = if (($i + 1) -eq $Default) { ' [default]' } else { '' }
            Write-Host "  [$($i + 1)] $($Options[$i])$tag"
        }
        $answer = Read-Host "Select 1-$($Options.Count) [$Default]"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        $value = 0
        if ([int]::TryParse($answer, [ref]$value) -and $value -ge 1 -and $value -le $Options.Count) { return $value }
        Write-Host 'Enter one of the listed numbers.' -ForegroundColor Yellow
    }
}

function Read-MenuExplicit([string]$Question, [string[]]$Options, [int]$Suggested = 0) {
    if ($Suggested -lt 1 -or $Suggested -gt $Options.Count) { $Suggested = 0 }
    while ($true) {
        Write-Host "`n$Question" -ForegroundColor White
        for ($i = 0; $i -lt $Options.Count; $i++) {
            $tag = if (($i + 1) -eq $Suggested) { ' [suggested]' } else { '' }
            Write-Host "  [$($i + 1)] $($Options[$i])$tag"
        }
        $suggestedLabel = if ($Suggested -gt 0) { "; suggested: $Suggested" } else { '' }
        $answer = Read-Host "Select 1-$($Options.Count)$suggestedLabel (explicit choice required)"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            if ($Suggested -gt 0) {
                Write-Host "Enter one of the listed numbers. Suggested: $Suggested. Pressing Enter alone does not select it." -ForegroundColor Yellow
            } else {
                Write-Host 'Enter one of the listed numbers; this selection has no assumed default.' -ForegroundColor Yellow
            }
            continue
        }
        $value = 0
        if ([int]::TryParse($answer, [ref]$value) -and $value -ge 1 -and $value -le $Options.Count) { return $value }
        Write-Host 'Enter one of the listed numbers.' -ForegroundColor Yellow
    }
}

function Get-LinuxUserHome([string]$Name, [string]$User) {
    $probe = Invoke-WslDirectCapture $Name 'root' 'getent' @('passwd', $User)
    if (-not $probe.Success) { return $null }
    $line = (($probe.Text -split "`r?`n") | Select-Object -First 1)
    $parts = @($line -split ':')
    if ($parts.Count -ge 6 -and $parts[5].StartsWith('/')) { return $parts[5] }
    return $null
}

function Get-DetectedLinuxTimezone([string]$Name, [string]$User) {
    $script = @'
set -u
candidate=""
if command -v timedatectl >/dev/null 2>&1; then
  candidate="$(timedatectl show -p Timezone --value 2>/dev/null | head -n1 || true)"
fi
if [[ -z "$candidate" && -r /etc/timezone ]]; then
  candidate="$(head -n1 /etc/timezone 2>/dev/null || true)"
fi
if [[ -z "$candidate" && -L /etc/localtime ]]; then
  target="$(readlink -f /etc/localtime 2>/dev/null || true)"
  case "$target" in
    */zoneinfo/*) candidate="${target#*/zoneinfo/}" ;;
  esac
fi
printf '%s\n' "$candidate"
'@
    $probe = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', $script)
    if (-not $probe.Success) { return '' }
    $timezone = (($probe.Text -split "`r?`n") | Select-Object -First 1).Trim()
    if ($timezone -match '^[A-Za-z0-9._+\-/]+$') { return $timezone }
    return ''
}


function Get-OllamaWslGpuPrerequisites([string]$Name, [string]$User) {
    # Probe the selected distro itself rather than inferring GPU/container support from
    # Windows hardware. In particular, an AMD GPU or /dev/dxg alone does not satisfy the
    # current Ollama Docker ROCm path, which requires /dev/kfd plus /dev/dri.
    $script = @'
set -u
arch="$(uname -m 2>/dev/null || true)"
kfd=0
dri=0
dxg=0
nvidia=0
[[ -e /dev/kfd ]] && kfd=1
[[ -d /dev/dri ]] && dri=1
[[ -e /dev/dxg ]] && dxg=1
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  nvidia=1
elif [[ -x /usr/lib/wsl/lib/nvidia-smi ]] && /usr/lib/wsl/lib/nvidia-smi -L >/dev/null 2>&1; then
  nvidia=1
fi
printf 'arch=%s\n' "$arch"
printf 'kfd=%s\n' "$kfd"
printf 'dri=%s\n' "$dri"
printf 'dxg=%s\n' "$dxg"
printf 'nvidia=%s\n' "$nvidia"
'@
    $probe = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', $script)
    $state = [ordered]@{
        ProbeSucceeded = $false
        Arch = ''
        KfdPresent = $false
        DriPresent = $false
        DxgPresent = $false
        NvidiaSmiReady = $false
        AmdDockerReady = $false
        NvidiaWslReady = $false
    }
    if (-not $probe.Success) { return [pscustomobject]$state }
    $state.ProbeSucceeded = $true
    foreach ($line in ($probe.StdOut -split "`r?`n")) {
        if ($line -notmatch '^([^=]+)=(.*)$') { continue }
        switch ($Matches[1]) {
            'arch' { $state.Arch = $Matches[2].Trim() }
            'kfd' { $state.KfdPresent = ($Matches[2] -eq '1') }
            'dri' { $state.DriPresent = ($Matches[2] -eq '1') }
            'dxg' { $state.DxgPresent = ($Matches[2] -eq '1') }
            'nvidia' { $state.NvidiaSmiReady = ($Matches[2] -eq '1') }
        }
    }
    $state.AmdDockerReady = ($state.Arch -eq 'x86_64' -and $state.KfdPresent -and $state.DriPresent)
    $state.NvidiaWslReady = ($state.DxgPresent -and $state.NvidiaSmiReady)
    return [pscustomobject]$state
}

function Write-OllamaGpuPrerequisiteSummary([object]$GpuState) {
    if (-not $GpuState.ProbeSucceeded) {
        Write-Warning 'Could not probe GPU prerequisites inside the selected Ubuntu distro. Forced GPU modes will not be accepted until the probe succeeds; Auto or CPU remains available.'
        return
    }
    $amdState = if ($GpuState.AmdDockerReady) { 'ready' } else { "unavailable (/dev/kfd=$($GpuState.KfdPresent), /dev/dri=$($GpuState.DriPresent), arch=$($GpuState.Arch))" }
    $nvidiaState = if ($GpuState.NvidiaWslReady) { 'ready' } else { "unavailable (/dev/dxg=$($GpuState.DxgPresent), nvidia-smi=$($GpuState.NvidiaSmiReady))" }
    Write-Info "Selected-distro Ollama GPU probe: AMD Docker/ROCm=$amdState; NVIDIA WSL=$nvidiaState."
    if ($GpuState.DxgPresent -and -not $GpuState.AmdDockerReady) {
        Write-Info 'WSL exposes /dev/dxg, but that alone is not treated as current Ollama Docker ROCm readiness; LatticeVale does not infer AMD container support from the Windows GPU.'
    }
}


function Test-DirectMLWslPath(
    [string]$Name,
    [string]$User,
    [string]$Path,
    [string]$TestFlag = '-e'
) {
    # DirectML preflight intentionally uses a direct `test` invocation instead of the
    # broader Ollama GPU prerequisite parser. A normal-user miss/failure is retried as
    # root so a transient/user-context probe cannot become a false "DXG missing" result.
    $result = [ordered]@{
        ProbeSucceeded = $false
        Present = $false
        RootRetried = $false
        Detail = ''
    }
    $attempt = Invoke-WslDirectCapture $Name $User 'test' @($TestFlag, $Path)
    if ($attempt.Success) {
        $result.ProbeSucceeded = $true
        $result.Present = $true
        return [pscustomobject]$result
    }

    # Exit 1 is the ordinary `test` "not present" result, but retry as root anyway:
    # directory traversal/ACL differences or a cold WSL startup must not produce a false
    # negative in the questionnaire.
    $result.RootRetried = $true
    $rootAttempt = Invoke-WslDirectCapture $Name 'root' 'test' @($TestFlag, $Path)
    if ($rootAttempt.Success) {
        $result.ProbeSucceeded = $true
        $result.Present = $true
        return [pscustomobject]$result
    }
    if (-not $rootAttempt.TimedOut -and $rootAttempt.ExitCode -eq 1) {
        $result.ProbeSucceeded = $true
        $result.Present = $false
        return [pscustomobject]$result
    }

    $detail = Get-SafeDiagnosticExcerpt $rootAttempt.Text
    if (-not $detail) { $detail = Get-SafeDiagnosticExcerpt $attempt.Text }
    $result.Detail = if ($detail) { $detail } else { 'WSL path probe returned an unexpected failure.' }
    return [pscustomobject]$result
}

function Get-DirectMLWslPrerequisites([string]$Name, [string]$User) {
    $dxg = Test-DirectMLWslPath $Name $User '/dev/dxg' '-e'
    $d3d12 = Test-DirectMLWslPath $Name $User '/usr/lib/wsl/lib/libd3d12.so' '-e'
    $d3d12core = Test-DirectMLWslPath $Name $User '/usr/lib/wsl/lib/libd3d12core.so' '-e'
    $dxcore = Test-DirectMLWslPath $Name $User '/usr/lib/wsl/lib/libdxcore.so' '-e'

    $state = [ordered]@{
        ProbeSucceeded = [bool]$dxg.ProbeSucceeded
        DxgPresent = [bool]$dxg.Present
        DxgRootRetried = [bool]$dxg.RootRetried
        D3d12Present = [bool]$d3d12.Present
        D3d12CorePresent = [bool]$d3d12core.Present
        DxCorePresent = [bool]$dxcore.Present
        LibraryProbeSucceeded = [bool]($d3d12.ProbeSucceeded -and $d3d12core.ProbeSucceeded -and $dxcore.ProbeSucceeded)
        BridgeLibrariesReady = [bool]($d3d12.Present -and $d3d12core.Present -and $dxcore.Present)
        TensorProbeAvailable = $false
        TensorProbeSucceeded = $false
        TensorProbeDetail = ''
        Detail = [string]$dxg.Detail
    }

    # On Resume / repair, use an already-created installer-owned DirectML environment as
    # an additional real execution signal. Fresh installs normally have no venv yet, so
    # absence is not an error and does not block selection.
    $linuxHome = Get-LinuxUserHome $Name $User
    if (-not [string]::IsNullOrWhiteSpace($linuxHome)) {
        $python = "$linuxHome/hermes-stack/data/directml/venv/bin/python"
        $pythonProbe = Test-DirectMLWslPath $Name $User $python '-x'
        if ($pythonProbe.ProbeSucceeded -and $pythonProbe.Present) {
            $state.TensorProbeAvailable = $true
            $code = 'import torch,torch_directml; d=torch_directml.device(); x=(torch.tensor([1.0]).to(d)+2.0).cpu().item(); raise SystemExit(0 if abs(float(x)-3.0)<0.001 else 1)'
            $tensor = Invoke-WslDirectCapture $Name $User $python @('-c', $code) 90
            if ($tensor.Success) {
                $state.TensorProbeSucceeded = $true
            } else {
                $state.TensorProbeDetail = Get-SafeDiagnosticExcerpt $tensor.Text
                if (-not $state.TensorProbeDetail) { $state.TensorProbeDetail = 'existing DirectML tensor probe failed without diagnostic output' }
            }
        }
    }
    return [pscustomobject]$state
}


function Get-LatticeValeGpuVendor([string]$Name) {
    $n = ([string]$Name).ToLowerInvariant()
    if ($n -match 'amd|radeon|advanced micro devices') { return 'amd' }
    if ($n -match 'nvidia|geforce|quadro|tesla|rtx|gtx') { return 'nvidia' }
    if ($n -match 'intel|arc|iris|uhd graphics|hd graphics') { return 'intel' }
    if ($n -match 'qualcomm|adreno') { return 'qualcomm' }
    return 'other'
}

function Get-WindowsGpuInventory {
    $items = [System.Collections.Generic.List[object]]::new()
    try {
        foreach ($gpu in @(Get-CimInstance Win32_VideoController -ErrorAction Stop)) {
            $name = ([string]$gpu.Name).Trim()
            if ([string]::IsNullOrWhiteSpace($name)) { continue }
            if ($name -match 'Microsoft Basic|Remote Display|Indirect Display') { continue }
            $vendor = Get-LatticeValeGpuVendor $name
            $items.Add([pscustomobject]@{
                Name = $name
                Vendor = $vendor
                PnpDeviceId = [string]$gpu.PNPDeviceID
            })
        }
    } catch {
        Write-Warning "Windows GPU inventory probe failed: $($_.Exception.Message)"
    }
    return $items.ToArray()
}

function Get-LatticeValeWslGpuComponentInventory([string]$Name, [string]$User) {
    $linuxHome = Get-LinuxUserHome $Name $User
    $directmlPython = if ([string]::IsNullOrWhiteSpace($linuxHome)) { '' } else { "$linuxHome/hermes-stack/data/directml/venv/bin/python" }
    $script = @'
set -u
pkg_ready() {
  local pkg="$1"
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'ok installed'
}
directml_pkgs=1
for pkg in python3-venv libblas3 libomp5 liblapack3; do
  pkg_ready "$pkg" || directml_pkgs=0
done
nvidia_ctk=0
command -v nvidia-ctk >/dev/null 2>&1 && nvidia_ctk=1
printf 'directml_packages=%s\n' "$directml_pkgs"
printf 'nvidia_ctk=%s\n' "$nvidia_ctk"
'@
    $probe = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', $script)
    $state = [ordered]@{
        ProbeSucceeded = $false
        DirectMLPackagesReady = $false
        DirectMLVenvPresent = $false
        NvidiaToolkitPresent = $false
    }
    if ($probe.Success) {
        $state.ProbeSucceeded = $true
        foreach ($line in ($probe.StdOut -split "`r?`n")) {
            if ($line -notmatch '^([^=]+)=(.*)$') { continue }
            switch ($Matches[1]) {
                'directml_packages' { $state.DirectMLPackagesReady = ($Matches[2] -eq '1') }
                'nvidia_ctk' { $state.NvidiaToolkitPresent = ($Matches[2] -eq '1') }
            }
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($directmlPython)) {
        $venvProbe = Test-DirectMLWslPath $Name $User $directmlPython '-x'
        $state.DirectMLVenvPresent = [bool]($venvProbe.ProbeSucceeded -and $venvProbe.Present)
    }
    return [pscustomobject]$state
}

function Get-LatticeValeGpuAccelerationPlan([string]$Name, [string]$User) {
    $inventory = @(Get-WindowsGpuInventory)
    $recognized = @($inventory | Where-Object { $_.Vendor -in @('amd','nvidia','intel','qualcomm') })
    $vendors = @($recognized | ForEach-Object { $_.Vendor } | Select-Object -Unique)
    $directml = Get-DirectMLWslPrerequisites $Name $User
    $ollama = Get-OllamaWslGpuPrerequisites $Name $User
    $components = Get-LatticeValeWslGpuComponentInventory $Name $User

    $backend = 'ollama'
    $ollamaAcceleration = 'auto'
    $reason = 'No verified GPU acceleration path was found in the selected WSL distro, so stable Ollama with CPU fallback is the safest default.'

    if (($vendors -contains 'nvidia') -and $ollama.NvidiaWslReady) {
        $backend = 'ollama'
        $ollamaAcceleration = 'nvidia'
        $reason = 'An NVIDIA GPU is detected and WSL nvidia-smi is working. Managed Ollama NVIDIA acceleration is the preferred stable path; LatticeVale can install/configure the NVIDIA Container Toolkit if it is missing.'
    } elseif (($vendors -contains 'amd') -and $ollama.AmdDockerReady) {
        $backend = 'ollama'
        $ollamaAcceleration = 'amd'
        $reason = 'An AMD GPU is detected and the selected WSL distro exposes /dev/kfd plus /dev/dri. Managed Ollama ROCm is the preferred verified container path.'
    } elseif (($recognized.Count -gt 0) -and $directml.ProbeSucceeded -and $directml.DxgPresent -and $directml.BridgeLibrariesReady) {
        $backend = 'directml'
        $ollamaAcceleration = 'auto'
        if ($vendors -contains 'amd') {
            $reason = 'An AMD/Radeon GPU is detected and the WSL DirectX bridge is healthy, while the managed ROCm container path is not fully verified. DirectML is recommended so the GPU still has an installer-managed acceleration path.'
        } elseif ($vendors -contains 'intel') {
            $reason = 'An Intel GPU is detected and the WSL DirectX bridge is healthy. DirectML is recommended because it is the broad cross-vendor DirectX 12 path supported by this release.'
        } elseif ($vendors -contains 'qualcomm') {
            $reason = 'A Qualcomm/Adreno GPU is detected and the WSL DirectX bridge is healthy. DirectML is the supported cross-vendor acceleration path for this hardware class.'
        } else {
            $reason = 'A DirectX 12 GPU and healthy WSL DirectML bridge were detected. DirectML is recommended because the vendor-specific managed Ollama GPU path is not currently verified.'
        }
    } elseif (($vendors -contains 'nvidia') -and $directml.ProbeSucceeded -and $directml.DxgPresent) {
        $backend = 'directml'
        $ollamaAcceleration = 'auto'
        $reason = 'An NVIDIA GPU is visible through /dev/dxg but the CUDA/nvidia-smi WSL path is not verified. DirectML is the best available GPU attempt; Ollama remains the fallback.'
    }

    return [pscustomobject]@{
        Inventory = $recognized
        Vendors = $vendors
        DirectML = $directml
        Ollama = $ollama
        Components = $components
        RecommendedTextBackend = $backend
        RecommendedOllamaAcceleration = $ollamaAcceleration
        TextBackendDefault = $(if ($backend -eq 'directml') { 2 } else { 1 })
        OllamaAccelerationDefault = $(switch ($ollamaAcceleration) { 'cpu' {2}; 'nvidia' {3}; 'amd' {4}; default {1} })
        Reason = $reason
    }
}

function Write-LatticeValeGpuAccelerationPlan([object]$Plan) {
    $gpuNames = @($Plan.Inventory | ForEach-Object { "$($_.Name) [$($_.Vendor)]" })
    if ($gpuNames.Count -gt 0) {
        Write-Info ('Detected Windows GPU(s): ' + ($gpuNames -join '; '))
    } else {
        Write-Info 'No recognized AMD/NVIDIA/Intel/Qualcomm Windows display adapter was detected; CPU-safe defaults remain available.'
    }
    $backendLabel = if ($Plan.RecommendedTextBackend -eq 'directml') { 'PyTorch DirectML gateway' } else { 'Ollama' }
    Write-Info "GPU-aware recommendation: $backendLabel. $($Plan.Reason)"

    if ($Plan.Components.ProbeSucceeded) {
        $directmlPackages = if ($Plan.Components.DirectMLPackagesReady) { 'installed/reusable' } else { 'missing; LatticeVale will install them if DirectML is selected' }
        $directmlVenv = if ($Plan.Components.DirectMLVenvPresent) { 'existing installer-owned venv detected and will be reused if healthy' } else { 'installer-owned venv will be created if DirectML is selected' }
        $nvidiaToolkit = if ($Plan.Components.NvidiaToolkitPresent) { 'installed/reusable' } else { 'not detected; LatticeVale will install/configure it only if NVIDIA managed Ollama is selected and WSL nvidia-smi is healthy' }
        Write-Info "WSL acceleration components: DirectML base packages=$directmlPackages; DirectML environment=$directmlVenv; NVIDIA Container Toolkit=$nvidiaToolkit."
    }
    if ($Plan.Ollama.AmdDockerReady) {
        Write-Info 'AMD managed-Ollama ROCm devices are already exposed by WSL. LatticeVale uses the pinned Ollama ROCm container image; it does not replace the Windows/host display driver.'
    } elseif (($Plan.Vendors -contains 'amd') -and $Plan.DirectML.DxgPresent) {
        Write-Info 'AMD note: /dev/dxg is available but the managed ROCm container devices are not. LatticeVale will not fabricate /dev/kfd; DirectML is offered so compatible Radeon systems can still use the GPU.'
    }
}

function Select-LatticeValeDirectMLGpu(
    [string]$Name,
    [string]$User,
    [string]$SavedAdapterName = '',
    [string]$SavedVendor = ''
) {
    $wslState = Get-DirectMLWslPrerequisites $Name $User
    if (-not $wslState.ProbeSucceeded) {
        Write-Warning "The DirectML /dev/dxg probe could not complete inside the selected Ubuntu distro. This is a probe failure, not proof that /dev/dxg is absent.$(if ($wslState.Detail) { ' ' + $wslState.Detail } else { '' })"
        $choice = Read-MenuExplicit 'DirectML WSL GPU support could not be verified. Choose how to continue' @(
            'Use Ollama instead (recommended until the probe succeeds)',
            'Keep DirectML selected; Resume / repair will probe again'
        )
        if ($choice -eq 1) {
            return [pscustomobject]@{ UseDirectML=$false; AdapterName=''; Vendor='' }
        }
        return [pscustomobject]@{ UseDirectML=$true; AdapterName=$SavedAdapterName; Vendor=$SavedVendor }
    }
    if (-not $wslState.DxgPresent) {
        Write-Warning 'The selected Ubuntu distro was probed directly and /dev/dxg is not present. PyTorch DirectML in WSL2 requires the Windows GPU bridge.'
        $choice = Read-MenuExplicit 'DirectML GPU bridge is currently unavailable. Choose how to continue' @(
            'Use Ollama instead (recommended)',
            'Keep DirectML selected; Resume / repair will probe again after WSL GPU support is fixed'
        )
        if ($choice -eq 1) {
            return [pscustomobject]@{ UseDirectML=$false; AdapterName=''; Vendor='' }
        }
        return [pscustomobject]@{ UseDirectML=$true; AdapterName=$SavedAdapterName; Vendor=$SavedVendor }
    }

    $libraryState = "libd3d12=$($wslState.D3d12Present), libd3d12core=$($wslState.D3d12CorePresent), libdxcore=$($wslState.DxCorePresent)"
    Write-Info "DirectML WSL preflight: /dev/dxg=present$(if ($wslState.DxgRootRetried) { ' (confirmed by root retry)' } else { '' }); $libraryState."
    if ($wslState.LibraryProbeSucceeded -and -not $wslState.BridgeLibrariesReady) {
        Write-Warning "WSL exposes /dev/dxg, but one or more Windows DirectX bridge libraries are missing from /usr/lib/wsl/lib ($libraryState). DirectML may not activate until WSL/WSLg GPU libraries are repaired."
    } elseif (-not $wslState.LibraryProbeSucceeded) {
        Write-Warning "The DirectX bridge-library probe was inconclusive ($libraryState). /dev/dxg itself is present, so LatticeVale will continue and the isolated DirectML runtime probe remains authoritative."
    }
    if ($wslState.TensorProbeAvailable) {
        if ($wslState.TensorProbeSucceeded) {
            Write-Info 'Existing isolated DirectML environment passed a real tensor execution probe.'
        } else {
            Write-Warning "An existing isolated DirectML environment was found but its real tensor probe failed. Resume / repair will rebuild/retry the installer-owned environment and Ollama fallback remains available.$(if ($wslState.TensorProbeDetail) { ' ' + $wslState.TensorProbeDetail } else { '' })"
        }
    }

    $inventory = @(Get-WindowsGpuInventory)
    $supported = @($inventory | Where-Object { $_.Vendor -in @('amd','nvidia','intel','qualcomm') })
    if ($supported.Count -gt 0) {
        Write-Info ('Windows GPU detection: ' + (($supported | ForEach-Object { "$($_.Name) [$($_.Vendor)]" }) -join '; '))
    }

    if (-not [string]::IsNullOrWhiteSpace($SavedAdapterName)) {
        $saved = @($supported | Where-Object { $_.Name -eq $SavedAdapterName })
        if ($saved.Count -eq 1) {
            Write-Info "DirectML adapter preserved: $($saved[0].Name) [$($saved[0].Vendor)]."
            return [pscustomobject]@{ UseDirectML=$true; AdapterName=$saved[0].Name; Vendor=$saved[0].Vendor }
        }
    }

    if ($supported.Count -eq 1) {
        Write-Info "DirectML adapter auto-selected: $($supported[0].Name) [$($supported[0].Vendor)]."
        return [pscustomobject]@{ UseDirectML=$true; AdapterName=$supported[0].Name; Vendor=$supported[0].Vendor }
    }

    if ($supported.Count -gt 1) {
        $labels = @($supported | ForEach-Object { "$($_.Name) [$($_.Vendor)]" })
        $idx = Read-MenuExplicit 'Multiple DirectML-capable Windows GPUs were detected. Choose the adapter LatticeVale should use' $labels
        $picked = $supported[$idx - 1]
        return [pscustomobject]@{ UseDirectML=$true; AdapterName=$picked.Name; Vendor=$picked.Vendor }
    }

    Write-Warning 'Windows GPU vendor detection did not find a recognized AMD, NVIDIA, Intel, or Qualcomm display adapter.'
    $manual = Read-MenuExplicit 'Select your GPU vendor, or use Ollama instead' @(
        'AMD / Radeon',
        'NVIDIA / GeForce',
        'Intel / Arc / Iris',
        'Qualcomm / Adreno',
        'Use Ollama instead'
    )
    if ($manual -eq 5) {
        return [pscustomobject]@{ UseDirectML=$false; AdapterName=''; Vendor='' }
    }
    $vendor = @('amd','nvidia','intel','qualcomm')[$manual - 1]
    Write-Info "DirectML vendor recorded from explicit user selection: $vendor. Runtime adapter enumeration will still fail closed if no matching DirectML device is available."
    return [pscustomobject]@{ UseDirectML=$true; AdapterName=''; Vendor=$vendor }
}

function Get-WindowsNativeOllamaState {
    # Treat installation discovery, API readiness, and WSL bridge readiness as separate
    # facts. Ollama's Windows installer may use a custom /DIR location and OLLAMA_HOST
    # may move the local listener away from the default 127.0.0.1:11434 endpoint.
    $state = [ordered]@{
        Installed = $false
        ProcessRunning = $false
        ApiReady = $false
        Version = ''
        Executable = ''
        AppExecutable = ''
        Endpoint = 'http://127.0.0.1:11434'
        RelayTargetAddress = '127.0.0.1'
        RelayTargetPort = 11434
        ConfiguredHost = ''
        Detail = ''
    }

    $candidates = [System.Collections.Generic.List[string]]::new()
    $addCandidate = {
        param([string]$Path)
        if ([string]::IsNullOrWhiteSpace($Path)) { return }
        $expanded = [Environment]::ExpandEnvironmentVariables($Path.Trim().Trim('"'))
        if (Test-Path -LiteralPath $expanded -PathType Leaf) {
            try { $expanded = [System.IO.Path]::GetFullPath($expanded) } catch { }
            if (-not $candidates.Contains($expanded)) { $candidates.Add($expanded) }
        }
    }

    foreach ($commandName in @('ollama.exe','ollama app.exe')) {
        try {
            $cmd = Get-Command $commandName -ErrorAction SilentlyContinue
            if ($cmd -and -not [string]::IsNullOrWhiteSpace([string]$cmd.Source)) { & $addCandidate ([string]$cmd.Source) }
        } catch { }
    }

    # Elevated PowerShell can inherit a PATH that differs from the user's persisted PATH.
    # Search all persisted PATH scopes explicitly so an ordinary per-user Ollama install is
    # still detected when LatticeVale itself is elevated.
    foreach ($scope in @('Process','User','Machine')) {
        try {
            $target = switch ($scope) { 'User' { [EnvironmentVariableTarget]::User }; 'Machine' { [EnvironmentVariableTarget]::Machine }; default { [EnvironmentVariableTarget]::Process } }
            $pathValue = [Environment]::GetEnvironmentVariable('Path', $target)
            foreach ($entry in @([string]$pathValue -split ';')) {
                if ([string]::IsNullOrWhiteSpace($entry)) { continue }
                $dir = [Environment]::ExpandEnvironmentVariables($entry.Trim().Trim('"'))
                & $addCandidate (Join-Path $dir 'ollama.exe')
                & $addCandidate (Join-Path $dir 'ollama app.exe')
            }
        } catch { }
    }

    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'),
        (Join-Path $env:LOCALAPPDATA 'Ollama\ollama.exe'),
        (Join-Path $env:LOCALAPPDATA 'Ollama\ollama app.exe'),
        (Join-Path $env:ProgramFiles 'Ollama\ollama.exe'),
        (Join-Path $env:ProgramFiles 'Ollama\ollama app.exe')
    )) { & $addCandidate $candidate }

    # Bounded fallback discovery: inspect only conventional application roots and only
    # Ollama-named immediate child directories. Never recurse through user data, whole
    # drives, arbitrary mounted volumes, or unrelated application trees.
    $scanRoots = [System.Collections.Generic.List[string]]::new()
    foreach ($root in @(
        $env:LOCALAPPDATA,
        (Join-Path $env:LOCALAPPDATA 'Programs'),
        $env:ProgramFiles,
        [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    )) {
        if ([string]::IsNullOrWhiteSpace([string]$root)) { continue }
        $expandedRoot = [Environment]::ExpandEnvironmentVariables(([string]$root).Trim().Trim('"'))
        if ((Test-Path -LiteralPath $expandedRoot -PathType Container) -and -not $scanRoots.Contains($expandedRoot)) { $scanRoots.Add($expandedRoot) }
    }
    foreach ($root in $scanRoots) {
        try {
            foreach ($dir in @(Get-ChildItem -LiteralPath $root -Directory -Filter 'Ollama*' -ErrorAction SilentlyContinue)) {
                foreach ($relative in @('ollama.exe','ollama app.exe','bin\ollama.exe','bin\ollama app.exe')) {
                    & $addCandidate (Join-Path $dir.FullName $relative)
                }
            }
        } catch { }
    }

    # Discover custom installer locations from Add/Remove Programs metadata. The official
    # Ollama installer supports OllamaSetup.exe /DIR=..., so fixed-path checks alone are
    # insufficient.
    foreach ($uninstallRoot in @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )) {
        try {
            foreach ($entry in @(Get-ItemProperty -Path $uninstallRoot -ErrorAction SilentlyContinue | Where-Object { ([string]$_.DisplayName) -match '^Ollama(?:\s|$)' })) {
                $state.Installed = $true
                $installLocation = [string]$entry.InstallLocation
                if (-not [string]::IsNullOrWhiteSpace($installLocation)) {
                    & $addCandidate (Join-Path $installLocation 'ollama.exe')
                    & $addCandidate (Join-Path $installLocation 'ollama app.exe')
                }
                $displayIcon = [string]$entry.DisplayIcon
                if (-not [string]::IsNullOrWhiteSpace($displayIcon)) {
                    $iconPath = (($displayIcon -split ',')[0]).Trim().Trim('"')
                    & $addCandidate $iconPath
                    if (Test-Path -LiteralPath $iconPath -PathType Leaf) {
                        $iconDir = Split-Path -Parent $iconPath
                        & $addCandidate (Join-Path $iconDir 'ollama.exe')
                        & $addCandidate (Join-Path $iconDir 'ollama app.exe')
                    }
                }
            }
        } catch { }
    }

    # Running-process paths are another authoritative source for portable/custom installs.
    try {
        foreach ($proc in @(Get-CimInstance Win32_Process -Filter "Name='ollama.exe' OR Name='ollama app.exe'" -ErrorAction SilentlyContinue)) {
            $state.ProcessRunning = $true
            & $addCandidate ([string]$proc.ExecutablePath)
        }
    } catch { }

    foreach ($candidate in $candidates) {
        $leaf = [System.IO.Path]::GetFileName($candidate)
        if ([string]::Equals($leaf, 'ollama app.exe', [StringComparison]::OrdinalIgnoreCase) -and -not $state.AppExecutable) {
            $state.AppExecutable = $candidate
        }
        if ([string]::Equals($leaf, 'ollama.exe', [StringComparison]::OrdinalIgnoreCase) -and -not $state.Executable) {
            $state.Executable = $candidate
        }
    }
    if (-not $state.Executable -and $candidates.Count -gt 0) { $state.Executable = [string]$candidates[0] }
    if (-not $state.AppExecutable -and $state.Executable) {
        $siblingApp = Join-Path (Split-Path -Parent $state.Executable) 'ollama app.exe'
        if (Test-Path -LiteralPath $siblingApp -PathType Leaf) { $state.AppExecutable = $siblingApp }
    }
    if ($candidates.Count -gt 0) { $state.Installed = $true }

    # Probe the documented default plus loopback OLLAMA_HOST values from all environment
    # scopes. Non-loopback OLLAMA_HOST values are recognized as configuration, but are not
    # adopted for LatticeVale's WSL-only relay because that relay intentionally targets a
    # Windows-local endpoint rather than a LAN listener.
    $probeEndpoints = [System.Collections.Generic.List[string]]::new()
    $probeEndpoints.Add('http://127.0.0.1:11434')
    $probeEndpoints.Add('http://localhost:11434')
    $configuredHosts = [System.Collections.Generic.List[string]]::new()
    foreach ($scope in @('Process','User','Machine')) {
        try {
            $target = switch ($scope) { 'User' { [EnvironmentVariableTarget]::User }; 'Machine' { [EnvironmentVariableTarget]::Machine }; default { [EnvironmentVariableTarget]::Process } }
            $rawHost = [string][Environment]::GetEnvironmentVariable('OLLAMA_HOST', $target)
            if ([string]::IsNullOrWhiteSpace($rawHost)) { continue }
            $rawHost = $rawHost.Trim().Trim('"')
            if (-not $configuredHosts.Contains($rawHost)) { $configuredHosts.Add($rawHost) }
        } catch { }
    }
    if ($configuredHosts.Count -gt 0) { $state.ConfiguredHost = [string]$configuredHosts[0] }

    foreach ($rawHost in $configuredHosts) {
        try {
            $candidateUriText = $rawHost
            if ($candidateUriText.StartsWith(':')) { $candidateUriText = '127.0.0.1' + $candidateUriText }
            if ($candidateUriText -notmatch '^[A-Za-z][A-Za-z0-9+.-]*://') { $candidateUriText = 'http://' + $candidateUriText }
            $uri = [Uri]$candidateUriText
            $ollamaHost = [string]$uri.DnsSafeHost
            $port = if ($uri.IsDefaultPort) { 11434 } else { [int]$uri.Port }
            $probeHost = ''
            if ($ollamaHost -eq '0.0.0.0') { $probeHost = '127.0.0.1' }
            elseif ($ollamaHost -eq '::' -or $ollamaHost -eq '[::]') { $probeHost = '[::1]' }
            elseif ($ollamaHost -eq 'localhost' -or $ollamaHost -eq '::1' -or $ollamaHost -match '^127(?:\.|$)') {
                $probeHost = if ($ollamaHost -eq '::1') { '[::1]' } else { $ollamaHost }
            }
            if ($probeHost) {
                $endpoint = "http://${probeHost}:$port"
                if (-not $probeEndpoints.Contains($endpoint)) { $probeEndpoints.Insert(0, $endpoint) }
            }
        } catch { }
    }

    foreach ($endpoint in $probeEndpoints) {
        $response = $null
        try {
            $request = [System.Net.HttpWebRequest]::Create(($endpoint.TrimEnd('/') + '/api/version'))
            $request.Method = 'GET'
            $request.Timeout = 2500
            $request.ReadWriteTimeout = 2500
            $request.Proxy = $null
            $response = $request.GetResponse()
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            try { $json = $reader.ReadToEnd() } finally { $reader.Dispose() }
            $payload = $json | ConvertFrom-Json
            $state.ApiReady = $true
            $state.Installed = $true
            $state.ProcessRunning = $true
            $state.Endpoint = $endpoint
            if ($payload -and $payload.PSObject.Properties['version']) { $state.Version = [string]$payload.version }
            try {
                $verifiedUri = [Uri]$endpoint
                $state.RelayTargetAddress = [string]$verifiedUri.DnsSafeHost
                $state.RelayTargetPort = if ($verifiedUri.IsDefaultPort) { 11434 } else { [int]$verifiedUri.Port }
            } catch { }
            break
        } catch { }
        finally {
            if ($response) { try { $response.Close() } catch { } }
        }
    }

    if ($state.ApiReady) {
        $versionText = if ($state.Version) { " $($state.Version)" } else { '' }
        $locationText = if ($state.Executable) { " Installed binary: '$($state.Executable)'." } else { '' }
        $state.Detail = "Native Windows Ollama$versionText API is running at $($state.Endpoint).$locationText"
    } elseif ($state.Installed) {
        $where = if ($state.Executable) { " at '$($state.Executable)'" } else { '' }
        $hostNote = if ($state.ConfiguredHost) { " Configured OLLAMA_HOST='$($state.ConfiguredHost)'." } else { '' }
        $state.Detail = "Native Windows Ollama is installed$where, but no verified Windows-local Ollama API is responding.$hostNote"
    } else {
        $state.Detail = 'No native Windows Ollama installation or running local Ollama API was detected.'
    }
    return [pscustomobject]$state
}

function Get-WindowsNativeOllamaHostForChildProcess {
    # Ollama's Windows application inherits the environment of the process that launches
    # it. An elevated installer may have been opened before the user changed OLLAMA_HOST,
    # so its Process-scope value can be stale even though the persisted User value is
    # correct. Prefer the documented per-user setting, then Machine, then the current
    # process value only when neither persisted scope defines OLLAMA_HOST.
    foreach ($scopeName in @('User','Machine','Process')) {
        try {
            $target = switch ($scopeName) {
                'User' { [EnvironmentVariableTarget]::User }
                'Machine' { [EnvironmentVariableTarget]::Machine }
                default { [EnvironmentVariableTarget]::Process }
            }
            $value = [string][Environment]::GetEnvironmentVariable('OLLAMA_HOST',$target)
            if (-not [string]::IsNullOrWhiteSpace($value)) { return $value.Trim().Trim('"') }
        } catch { }
    }
    return ''
}

function Stop-DetectedWindowsNativeOllamaProcesses([int]$WaitSeconds = 15) {
    # This is called only after explicit consent to start/restart native Ollama. Stop the
    # tray application first so it cannot respawn its managed `ollama.exe serve` child,
    # then clear any remaining Ollama-named child processes. Repeat until the process tree
    # is actually gone; a single Stop-Process pass is not sufficient during app updates.
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(5,$WaitSeconds))
    do {
        $running = @()
        try {
            $running = @(Get-CimInstance Win32_Process -Filter "Name='ollama.exe' OR Name='ollama app.exe'" -ErrorAction SilentlyContinue)
        } catch { }
        if ($running.Count -eq 0) { return $true }

        foreach ($proc in @($running | Where-Object { [string]$_.Name -ieq 'ollama app.exe' })) {
            try { Stop-Process -Id ([int]$proc.ProcessId) -Force -ErrorAction Stop } catch { }
        }
        Start-Sleep -Milliseconds 250

        try {
            $running = @(Get-CimInstance Win32_Process -Filter "Name='ollama.exe' OR Name='ollama app.exe'" -ErrorAction SilentlyContinue)
        } catch { $running = @() }
        foreach ($proc in $running) {
            try { Stop-Process -Id ([int]$proc.ProcessId) -Force -ErrorAction Stop } catch { }
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    try {
        return (@(Get-CimInstance Win32_Process -Filter "Name='ollama.exe' OR Name='ollama app.exe'" -ErrorAction SilentlyContinue).Count -eq 0)
    } catch { return $false }
}

function Wait-WindowsTcpPortReleased([int]$Port, [int]$WaitSeconds = 12) {
    if ($Port -lt 1 -or $Port -gt 65535) { return $false }
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        Start-Sleep -Seconds 1
        return $true
    }
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(3,$WaitSeconds))
    do {
        try {
            if (-not (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1)) { return $true }
        } catch { return $true }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}

function Write-WindowsTcpPortOwnerWarning([int]$Port) {
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        Write-Warning "TCP port $Port did not become available after stopping Ollama."
        return
    }
    try {
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $listener) { return }
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$listener.OwningProcess)" -ErrorAction SilentlyContinue
        $ownerText = if ($owner) { "$($owner.Name) (PID $($owner.ProcessId))" } else { "PID $($listener.OwningProcess)" }
        Write-Warning "TCP port $Port is still owned by $ownerText. LatticeVale will not start another Ollama server onto an occupied port."
    } catch {
        Write-Warning "TCP port $Port did not become available after stopping Ollama."
    }
}

function Start-DetectedWindowsNativeOllama([object]$State, [int]$WaitSeconds = 30) {
    if ($State -and $State.ApiReady) { return $State }
    if (-not $State -or -not $State.Installed) { return $State }

    $processHost = Get-WindowsNativeOllamaHostForChildProcess
    if ([string]::IsNullOrWhiteSpace($processHost)) { Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue }
    else { $env:OLLAMA_HOST = $processHost }

    $port = if ($State.RelayTargetPort -ge 1 -and $State.RelayTargetPort -le 65535) { [int]$State.RelayTargetPort } else { 11434 }

    # A post-update tray process can exist while the server is absent. The user has
    # explicitly consented to starting Ollama, so clear only Ollama-named processes and
    # wait for their listener to disappear before launching one replacement instance.
    if ($State.ProcessRunning -and -not $State.ApiReady) {
        if (-not (Stop-DetectedWindowsNativeOllamaProcesses 15)) {
            Write-Warning 'Native Ollama processes did not exit cleanly; LatticeVale will not launch a duplicate instance.'
            return (Get-WindowsNativeOllamaState)
        }
        if (-not (Wait-WindowsTcpPortReleased $port 12)) {
            Write-WindowsTcpPortOwnerWarning $port
            return (Get-WindowsNativeOllamaState)
        }
    }

    $launchExe = ''
    $launchArgs = @()
    $launchedTrayApp = $false
    if ($State.AppExecutable -and (Test-Path -LiteralPath $State.AppExecutable -PathType Leaf)) {
        $launchExe = [string]$State.AppExecutable
        $launchedTrayApp = $true
    } elseif ($State.Executable -and (Test-Path -LiteralPath $State.Executable -PathType Leaf)) {
        $launchExe = [string]$State.Executable
        $launchArgs = @('serve')
    }
    if (-not $launchExe) { return $State }

    try {
        if ($launchArgs.Count -gt 0) { Start-Process $launchExe -ArgumentList $launchArgs -WindowStyle Hidden -ErrorAction Stop | Out-Null }
        else { Start-Process $launchExe -ErrorAction Stop | Out-Null }
    } catch {
        Write-Warning "Detected native Windows Ollama but could not start it: $($_.Exception.Message)"
        return (Get-WindowsNativeOllamaState)
    }

    $totalWait = [Math]::Max(10,$WaitSeconds)
    $firstDeadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(8,[Math]::Floor($totalWait / 2)))
    do {
        Start-Sleep -Seconds 1
        $current = Get-WindowsNativeOllamaState
        if ($current.ApiReady) { return $current }
    } while ([DateTime]::UtcNow -lt $firstDeadline)

    # If the normal tray app failed to restore its managed server, a CLI fallback is
    # allowed only after the app and its child process tree are fully gone and TCP 11434
    # (or the configured Ollama port) is released. Never run `ollama serve` alongside a
    # live tray application that is already responsible for that server lifecycle.
    if ($launchedTrayApp -and $State.Executable -and (Test-Path -LiteralPath $State.Executable -PathType Leaf)) {
        if (-not (Stop-DetectedWindowsNativeOllamaProcesses 15)) {
            Write-Warning 'The Ollama tray application did not exit cleanly; the CLI server fallback was skipped to avoid a duplicate listener.'
            return (Get-WindowsNativeOllamaState)
        }
        if (-not (Wait-WindowsTcpPortReleased $port 12)) {
            Write-WindowsTcpPortOwnerWarning $port
            return (Get-WindowsNativeOllamaState)
        }
        try {
            Start-Process ([string]$State.Executable) -ArgumentList @('serve') -WindowStyle Hidden -ErrorAction Stop | Out-Null
        } catch {
            Write-Warning "Native Ollama app launch did not expose its API and the CLI fallback could not start: $($_.Exception.Message)"
            return (Get-WindowsNativeOllamaState)
        }
        $secondDeadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(8,[Math]::Ceiling($totalWait / 2)))
        do {
            Start-Sleep -Seconds 1
            $current = Get-WindowsNativeOllamaState
            if ($current.ApiReady) { return $current }
        } while ([DateTime]::UtcNow -lt $secondDeadline)
    }
    return (Get-WindowsNativeOllamaState)
}

function Resolve-WindowsNativeOllamaForQuestionnaire([object]$State) {
    if (-not $State) { return $State }
    if ($State.ApiReady -or -not $State.Installed) { return $State }

    Write-Info $State.Detail
    $startNow = Read-Choice 'Start the detected native Windows Ollama now and re-check its local API?' 'LatticeVale will only launch the already-installed Windows Ollama application (or run its documented `ollama serve` command when only the CLI is available). It will not install, update, reconfigure, or change the startup policy of native Ollama.' 'Native Windows Ollama remains installed but will not be offered as a backend during this run unless its API is started separately.' $true
    if (-not $startNow) { return $State }
    $updated = Start-DetectedWindowsNativeOllama $State 25
    Write-Info $updated.Detail
    return $updated
}

function Get-WslNetworkingMode([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { return '' }
    # Keep machine-readable network discovery free of nested bash/awk quoting. Current
    # WSL exposes wslinfo directly, and older builds simply return a normal command error.
    $probe = Invoke-WslDirectCapture $Name '' 'wslinfo' @('--networking-mode') 10
    if (-not $probe.Success -or [string]::IsNullOrWhiteSpace($probe.StdOut)) { return '' }
    foreach ($line in @($probe.StdOut -split "`r?`n")) {
        $mode = ([string]$line).Trim().ToLowerInvariant()
        if ($mode -in @('nat','mirrored','virtioproxy','bridged','none')) { return $mode }
    }
    return ''
}

function Test-WslHttpEndpointDirect([string]$Name, [string]$HostAddress, [int]$Port, [string]$Path = '/api/version') {
    if ([string]::IsNullOrWhiteSpace($Name) -or [string]::IsNullOrWhiteSpace($HostAddress) -or $Port -lt 1 -or $Port -gt 65535) { return $false }
    if ([string]::IsNullOrWhiteSpace($Path) -or -not $Path.StartsWith('/')) { return $false }
    $url = "http://${HostAddress}:$Port$Path"

    # Treat a real HTTP response from the selected distro as the authoritative proof of
    # reachability. Invoke curl directly through wsl.exe instead of serializing a heredoc
    # or nested shell pipeline across the Windows/Linux command-line boundary.
    $curl = Invoke-WslDirectCapture $Name '' 'curl' @('-fsS','--noproxy','*','--connect-timeout','4','--max-time','8',$url) 12
    if ($curl.Success) {
        if ($Path -ne '/api/version') { return $true }
        try {
            $payload = ([string]$curl.StdOut) | ConvertFrom-Json
            if ($payload -and -not [string]::IsNullOrWhiteSpace([string]$payload.version)) { return $true }
        } catch { }
    }

    # Ubuntu installations normally have curl by the time LatticeVale configures the
    # stack, but Python is a safe independent fallback for minimal existing distros.
    $pythonCode = @'
import json,sys,urllib.request
host=sys.argv[1]; port=int(sys.argv[2]); path=sys.argv[3]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://%s:%d%s' % (host,port,path), timeout=6) as response:
    if response.status < 200 or response.status >= 300:
        raise SystemExit(2)
    data=response.read(4096)
    if path == '/api/version':
        payload=json.loads(data.decode('utf-8','replace'))
        if not str(payload.get('version','')).strip():
            raise SystemExit(3)
'@
    $python = Invoke-WslDirectCapture $Name '' 'python3' @('-c',$pythonCode,$HostAddress,[string]$Port,$Path) 12
    return [bool]$python.Success
}

function Get-WslIpv4Candidates([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { return @() }
    # Direct argv execution avoids the bash -lc / awk quoting boundary that can turn a
    # valid WSL network into an empty probe result under Windows process reserialization.
    $probe = Invoke-WslDirectCapture $Name '' 'ip' @('-4','-o','addr','show','scope','global') 15
    if (-not $probe.Success) { return @() }
    $result = [System.Collections.Generic.List[string]]::new()
    foreach ($line in @($probe.StdOut -split "`r?`n")) {
        $tokens = @((([string]$line).Trim()) -split '\s+')
        for ($i = 0; $i -lt ($tokens.Count - 1); $i++) {
            if ($tokens[$i] -ne 'inet') { continue }
            $candidate = ([string]$tokens[$i + 1] -split '/', 2)[0].Trim()
            if ((Test-LatticeValeBridgeIpv4 $candidate) -and -not $result.Contains($candidate)) { $result.Add($candidate) }
            break
        }
    }
    return [string[]]$result.ToArray()
}

function Get-WslDefaultIpv4GatewayCandidates([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { return @() }
    # Microsoft documents the NAT host address as the next hop from `ip route`. Invoke
    # ip directly and parse tokens in PowerShell; do not depend on shell pipelines.
    $probe = Invoke-WslDirectCapture $Name '' 'ip' @('-4','route','show','default') 15
    if (-not $probe.Success) { return @() }
    $result = [System.Collections.Generic.List[string]]::new()
    foreach ($line in @($probe.StdOut -split "`r?`n")) {
        $tokens = @((([string]$line).Trim()) -split '\s+')
        if ($tokens.Count -lt 3 -or $tokens[0] -ne 'default') { continue }
        for ($i = 1; $i -lt ($tokens.Count - 1); $i++) {
            if ($tokens[$i] -ne 'via') { continue }
            $candidate = ([string]$tokens[$i + 1]).Trim()
            if ((Test-LatticeValeBridgeIpv4 $candidate) -and -not $result.Contains($candidate)) { $result.Add($candidate) }
            break
        }
    }
    return [string[]]$result.ToArray()
}

function ConvertTo-LatticeValeIpv4UInt32([string]$Value) {
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Value, [ref]$parsed)) { return $null }
    if ($parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $null }
    $b = $parsed.GetAddressBytes()
    return [uint32]((([uint32]$b[0]) -shl 24) -bor (([uint32]$b[1]) -shl 16) -bor (([uint32]$b[2]) -shl 8) -bor ([uint32]$b[3]))
}

function Test-LatticeValeIpv4SubnetMatch([string]$AddressA, [string]$AddressB, [int]$PrefixLength) {
    if ($PrefixLength -lt 1 -or $PrefixLength -gt 32) { return $false }
    $a = ConvertTo-LatticeValeIpv4UInt32 $AddressA
    $b = ConvertTo-LatticeValeIpv4UInt32 $AddressB
    if ($null -eq $a -or $null -eq $b) { return $false }
    $mask = if ($PrefixLength -eq 32) { [uint32]0xFFFFFFFF } else { [uint32](([uint64]0xFFFFFFFF -shl (32 - $PrefixLength)) -band [uint64]0xFFFFFFFF) }
    return (($a -band $mask) -eq ($b -band $mask))
}

function Get-WindowsWslAdapterIpv4Candidates([string]$Name) {
    $wslAddresses = @(Get-WslIpv4Candidates $Name)
    if ($wslAddresses.Count -eq 0 -or -not (Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue)) { return @() }
    $adapterText = @{}
    if (Get-Command Get-NetAdapter -ErrorAction SilentlyContinue) {
        try {
            foreach ($adapter in @(Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue)) {
                $adapterText[[int]$adapter.ifIndex] = (([string]$adapter.Name) + ' ' + ([string]$adapter.InterfaceDescription)).Trim()
            }
        } catch { }
    }
    $result = [System.Collections.Generic.List[string]]::new()
    try {
        foreach ($entry in @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue)) {
            $candidate = ([string]$entry.IPAddress).Trim()
            if (-not (Test-LatticeValeBridgeIpv4 $candidate)) { continue }
            $identity = (([string]$entry.InterfaceAlias) + ' ' + ([string]$adapterText[[int]$entry.InterfaceIndex])).Trim()
            if ($identity -notmatch '(?i)(WSL|Hyper-V|vEthernet|Virtual Ethernet)') { continue }
            $prefix = [int]$entry.PrefixLength
            $sameSubnet = $false
            foreach ($wslAddress in $wslAddresses) {
                if (Test-LatticeValeIpv4SubnetMatch $candidate $wslAddress $prefix) { $sameSubnet = $true; break }
            }
            if ($sameSubnet -and -not $result.Contains($candidate)) { $result.Add($candidate) }
        }
    } catch { }
    return [string[]]$result.ToArray()
}

function Get-LatticeValeWslHyperVCreatorId {
    # Microsoft documents this creator ID for WSL. Prefer runtime discovery when the
    # cmdlet exists so the code remains self-describing, then fall back to the documented
    # stable WSL identifier.
    $documented = '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'
    if (Get-Command Get-NetFirewallHyperVVMCreator -ErrorAction SilentlyContinue) {
        try {
            $creator = Get-NetFirewallHyperVVMCreator -ErrorAction SilentlyContinue | Where-Object { ([string]$_.FriendlyName) -eq 'WSL' } | Select-Object -First 1
            if ($creator -and -not [string]::IsNullOrWhiteSpace([string]$creator.VMCreatorId)) { return [string]$creator.VMCreatorId }
        } catch { }
    }
    return $documented
}

function New-LatticeValeWslHyperVOutboundRule([string]$RuleName, [string]$RemoteAddress, [int]$RemotePort) {
    if (-not (Get-Command New-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) { return $false }
    if (-not (Test-LatticeValeBridgeIpv4 $RemoteAddress) -or $RemotePort -lt 1 -or $RemotePort -gt 65535) { return $false }
    try {
        if ((Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
            Get-NetFirewallHyperVRule -Name $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue
        }
        New-NetFirewallHyperVRule -Name $RuleName -DisplayName 'LatticeVale WSL outbound native-service bridge' -Direction Outbound -Action Allow -Enabled True -Profiles Any -VMCreatorId (Get-LatticeValeWslHyperVCreatorId) -Protocol TCP -RemoteAddresses $RemoteAddress -RemotePorts ([string]$RemotePort) -ErrorAction Stop | Out-Null
        return $true
    } catch {
        Write-Info "Hyper-V firewall rule could not be installed for the WSL native-service path: $($_.Exception.Message)"
        return $false
    }
}

function Remove-LatticeValeWslHyperVRule([string]$RuleName) {
    if ([string]::IsNullOrWhiteSpace($RuleName) -or -not (Get-Command Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) { return }
    try { Get-NetFirewallHyperVRule -Name $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue } catch { }
}

function Test-WindowsHostIpv4FromWsl([string]$Name, [string]$Candidate) {
    if (-not (Test-LatticeValeBridgeIpv4 $Candidate)) { return $false }
    if (-not (Get-Command New-NetFirewallRule -ErrorAction SilentlyContinue) -or -not (Get-Command Remove-NetFirewallRule -ErrorAction SilentlyContinue)) { return $false }
    $wslAddresses = @(Get-WslIpv4Candidates $Name)
    if ($wslAddresses.Count -eq 0) { return $false }
    $listener = $null
    $ruleName = 'LatticeVale-NativeProbe-' + [Guid]::NewGuid().ToString('N')
    $hyperVRuleName = $ruleName + '-HyperV'
    try {
        $ip = [System.Net.IPAddress]::Parse($Candidate)
        $listener = New-Object System.Net.Sockets.TcpListener($ip, 0)
        $listener.Start(2)
        $port = [int]$listener.LocalEndpoint.Port
        New-NetFirewallRule -Name $ruleName -DisplayName 'LatticeVale temporary WSL native-service probe' -Group 'LatticeVale' -Direction Inbound -Action Allow -Enabled True -Profile Any -Protocol TCP -LocalAddress $Candidate -RemoteAddress $wslAddresses -LocalPort $port | Out-Null
        [void](New-LatticeValeWslHyperVOutboundRule $hyperVRuleName $Candidate $port)
        $script = @'
set -e
host="$1"; port="$2"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
if command -v python3 >/dev/null 2>&1; then
  exec python3 - "$host" "$port" <<'PY_WSL_HOST_PROBE'
import socket,sys
s=socket.create_connection((sys.argv[1],int(sys.argv[2])),4)
s.close()
PY_WSL_HOST_PROBE
fi
exec 3<>"/dev/tcp/${host}/${port}"
exec 3>&-
'@
        $probe = Invoke-WslDirectCapture $Name '' 'bash' @('-lc',$script,'bash',$Candidate,[string]$port) 10
        return [bool]$probe.Success
    } catch { return $false }
    finally {
        try { Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue } catch { }
        Remove-LatticeValeWslHyperVRule $hyperVRuleName
        if ($listener) { try { $listener.Stop() } catch { } }
    }
}

function Test-WindowsOwnsIpv4([string]$Candidate) {
    if (-not (Test-LatticeValeBridgeIpv4 $Candidate)) { return $false }
    if (-not (Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue)) { return $false }
    try { return [bool](Get-NetIPAddress -AddressFamily IPv4 -IPAddress $Candidate -ErrorAction SilentlyContinue | Select-Object -First 1) } catch { return $false }
}

function Get-WindowsHostIpv4ForWsl([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { return '' }
    foreach ($candidate in @(Get-WslDefaultIpv4GatewayCandidates $Name)) {
        if ((Test-LatticeValeBridgeIpv4 $candidate) -and (Test-WindowsOwnsIpv4 $candidate)) { return $candidate }
    }
    foreach ($candidate in @(Get-WindowsWslAdapterIpv4Candidates $Name)) {
        if (Test-LatticeValeBridgeIpv4 $candidate) { return $candidate }
    }
    return ''
}


function Get-LatticeValeNativeOllamaDirectPaths([string]$Name) {
    $native = Get-LatticeValeNativeServicePaths $Name
    return [pscustomobject]@{
        State = (Join-Path $native.Directory ("ollama-wsl-direct-$($native.RuleKey).json"))
        RulePrefix = ("LatticeValeOllamaWslDirect-$($native.RuleKey)")
    }
}

function Send-LatticeValeEnvironmentChanged {
    # [Environment]::SetEnvironmentVariable writes the registry but does not itself
    # refresh Explorer's inherited environment. Broadcast the documented Environment
    # setting change so later Start-menu launches receive the persisted value too.
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
        $result = [UIntPtr]::Zero
        [void][LatticeValeEnvironmentBroadcast]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$result)
    } catch {
        Write-Warning "Windows environment variables were persisted, but the environment-change broadcast failed: $($_.Exception.Message)"
    }
}

function Get-WindowsNativeOllamaService {
    try {
        return @(Get-Service -ErrorAction SilentlyContinue | Where-Object {
            ([string]$_.Name) -match '(?i)ollama' -or ([string]$_.DisplayName) -match '(?i)ollama'
        } | Select-Object -First 1)[0]
    } catch { return $null }
}

function Test-WindowsNativeOllamaDirectBindingDurable([int]$Port) {
    # A custom Windows service owns its own persistent launch configuration. For the normal
    # Ollama tray application, require a persisted User/Machine OLLAMA_HOST that requests a
    # non-loopback bind; Process scope alone can disappear when the installer exits.
    if (Get-WindowsNativeOllamaService) {
        return (Test-WindowsNativeOllamaNonLoopbackListener $Port)
    }
    foreach ($target in @([EnvironmentVariableTarget]::User,[EnvironmentVariableTarget]::Machine)) {
        try {
            $raw = [string][Environment]::GetEnvironmentVariable('OLLAMA_HOST',$target)
            if ([string]::IsNullOrWhiteSpace($raw)) { continue }
            $value = $raw.Trim().Trim('"')
            if ($value.StartsWith(':')) { continue }
            $uriText = if ($value -match '^[A-Za-z][A-Za-z0-9+.-]*://') { $value } else { 'http://' + $value }
            $uri = [Uri]$uriText
            $bindHost = [string]$uri.DnsSafeHost
            if ($bindHost -eq 'localhost' -or $bindHost -match '^127(?:\.|$)' -or $bindHost -eq '::1') { continue }
            if ($bindHost -eq '0.0.0.0' -or $bindHost -eq '::') { return $true }
            $parsed = $null
            if ([IPAddress]::TryParse($bindHost,[ref]$parsed) -and -not [IPAddress]::IsLoopback($parsed)) { return $true }
        } catch { }
    }
    return $false
}

function Restart-WindowsNativeOllamaForEnvironment([object]$State, [string]$ProcessHostValue = '') {
    $service = Get-WindowsNativeOllamaService
    $port = if ($State -and $State.RelayTargetPort -ge 1 -and $State.RelayTargetPort -le 65535) { [int]$State.RelayTargetPort } else { 11434 }
    if ($service) {
        try {
            Write-Info "Restarting detected Windows Ollama service '$($service.Name)' so it can re-read its persisted environment."
            Restart-Service -Name $service.Name -Force -ErrorAction Stop
        } catch {
            Write-Warning "Could not restart the detected Windows Ollama service '$($service.Name)': $($_.Exception.Message)"
            return (Get-WindowsNativeOllamaState)
        }
    } else {
        if (-not (Stop-DetectedWindowsNativeOllamaProcesses 15)) {
            Write-Warning 'Native Ollama did not fully stop, so LatticeVale will not launch a second app/server instance.'
            return (Get-WindowsNativeOllamaState)
        }
        if (-not (Wait-WindowsTcpPortReleased $port 12)) {
            Write-WindowsTcpPortOwnerWarning $port
            return (Get-WindowsNativeOllamaState)
        }
        if ([string]::IsNullOrWhiteSpace($ProcessHostValue)) { Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue }
        else { $env:OLLAMA_HOST = $ProcessHostValue }
        try {
            if ($State.AppExecutable -and (Test-Path -LiteralPath $State.AppExecutable -PathType Leaf)) {
                # The normal Windows app owns its `ollama.exe serve` child. Launch exactly
                # one app instance and let it create the server rather than starting both.
                Start-Process ([string]$State.AppExecutable) -ErrorAction Stop | Out-Null
            } elseif ($State.Executable -and (Test-Path -LiteralPath $State.Executable -PathType Leaf)) {
                Start-Process ([string]$State.Executable) -ArgumentList @('serve') -WindowStyle Hidden -ErrorAction Stop | Out-Null
            } else {
                Write-Warning 'Native Windows Ollama needs a restart, but no launchable detected executable is available. Quit/relaunch Ollama from its tray icon/Start menu, then rerun this installer.'
                return (Get-WindowsNativeOllamaState)
            }
        } catch {
            Write-Warning "Could not relaunch native Windows Ollama after its environment changed: $($_.Exception.Message)"
            return (Get-WindowsNativeOllamaState)
        }
    }

    $requireNonLoopback = (-not [string]::IsNullOrWhiteSpace($ProcessHostValue) -and $ProcessHostValue -notmatch '^(?i)(?:https?://)?(?:localhost|127(?:\.|:)|\[?::1\]?)(?::|/|$)')
    $deadline = [DateTime]::UtcNow.AddSeconds(40)
    do {
        Start-Sleep -Seconds 1
        $current = Get-WindowsNativeOllamaState
        if ($current.ApiReady) {
            if (-not $requireNonLoopback -or (Test-WindowsNativeOllamaNonLoopbackListener $port)) { return $current }
        }
    } while ([DateTime]::UtcNow -lt $deadline)
    return (Get-WindowsNativeOllamaState)
}

function Test-WindowsNativeOllamaNonLoopbackListener([int]$Port) {
    if ($Port -lt 1 -or $Port -gt 65535) { return $false }
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) { return $true }
    try {
        foreach ($listener in @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)) {
            $address = ([string]$listener.LocalAddress).Trim()
            if ($address -in @('0.0.0.0','::')) { return $true }
            $parsed = $null
            if ([IPAddress]::TryParse($address,[ref]$parsed) -and -not [IPAddress]::IsLoopback($parsed)) { return $true }
        }
    } catch { }
    return $false
}

function Enable-LatticeValeWindowsNativeOllamaDirectWslAccess([string]$Name, [object]$State) {
    $result = [ordered]@{ Success=$false; OllamaState=$State; HostAddress=''; Detail='' }
    if (-not $State -or -not $State.Installed) { $result.Detail='Native Windows Ollama is not installed.'; return [pscustomobject]$result }
    if (-not (Get-Command New-NetFirewallRule -ErrorAction SilentlyContinue) -or -not (Get-Command Remove-NetFirewallRule -ErrorAction SilentlyContinue)) {
        $result.Detail='Windows Firewall cmdlets are unavailable, so direct WSL access cannot be scoped safely.'; return [pscustomobject]$result
    }
    $hostAddress = Get-WindowsHostIpv4ForWsl $Name
    if (-not (Test-LatticeValeBridgeIpv4 $hostAddress)) {
        $result.Detail='No Windows-host IPv4 usable by the selected WSL distro could be identified.'; return [pscustomobject]$result
    }
    $result.HostAddress = $hostAddress
    $port = if ($State.RelayTargetPort -ge 1 -and $State.RelayTargetPort -le 65535) { [int]$State.RelayTargetPort } else { 11434 }
    $desiredHost = "0.0.0.0:$port"
    $service = Get-WindowsNativeOllamaService
    $scopeName = if ($service) { 'Machine' } else { 'User' }
    $scope = if ($service) { [EnvironmentVariableTarget]::Machine } else { [EnvironmentVariableTarget]::User }
    $paths = Get-LatticeValeNativeOllamaDirectPaths $Name
    $oldOwned = $null
    if (Test-Path -LiteralPath $paths.State -PathType Leaf) {
        try { $oldOwned = Get-Content -LiteralPath $paths.State -Raw | ConvertFrom-Json } catch { $oldOwned = $null }
    }
    $previous = [Environment]::GetEnvironmentVariable('OLLAMA_HOST',$scope)
    $previousWasSet = ($null -ne $previous)
    $originalPrevious = $previous
    $originalPreviousWasSet = $previousWasSet
    if ($oldOwned -and [string]$oldOwned.environmentScope -eq $scopeName -and [string]$oldOwned.configuredHost -eq [string]$previous) {
        $originalPrevious = [string]$oldOwned.previousHost
        $originalPreviousWasSet = [bool]$oldOwned.previousHostWasSet
    }

    $wslAddresses = @(Get-WslIpv4Candidates $Name)
    if ($wslAddresses.Count -eq 0) {
        $result.Detail='The selected WSL distro did not expose an IPv4 source address for a safely scoped firewall rule.'; return [pscustomobject]$result
    }
    $tempRule = "$($paths.RulePrefix)-$([Guid]::NewGuid().ToString('N'))"
    $hyperVRuleName = $tempRule + '-HyperV'
    $firewallArgs = @{
        Name=$tempRule; DisplayName='LatticeVale native Windows Ollama - WSL only'; Group='LatticeVale'; Direction='Inbound'; Action='Allow'; Enabled='True'; Profile='Any'; Protocol='TCP'; LocalAddress=$hostAddress; RemoteAddress=$wslAddresses; LocalPort=$port
    }

    $environmentChanged = ([string]$previous -ne $desiredHost)
    $restarted = $false
    try {
        New-NetFirewallRule @firewallArgs | Out-Null
        $hyperVRuleCreated = New-LatticeValeWslHyperVOutboundRule $hyperVRuleName $hostAddress $port
        if ($environmentChanged) {
            [Environment]::SetEnvironmentVariable('OLLAMA_HOST',$desiredHost,$scope)
            $env:OLLAMA_HOST = $desiredHost
            Send-LatticeValeEnvironmentChanged
            Write-Info "Configured OLLAMA_HOST=$desiredHost at Windows $scopeName scope for native Ollama."
        } else {
            $env:OLLAMA_HOST = $desiredHost
        }
        Write-Info "Created a Windows Firewall rule for TCP $port restricted to Windows host address $hostAddress and the selected distro IPv4 source address(es); no LAN-wide Ollama firewall rule was created."
        if ($hyperVRuleCreated) { Write-Info 'Created a matching WSL Hyper-V outbound firewall rule for this host/port because modern WSL traffic can be filtered by Hyper-V firewall.' }
        Write-Info 'OLLAMA_ORIGINS was not changed: Hermes/Honcho/WSL use server-side HTTP and do not require browser CORS wildcard access.'

        if (-not (Test-WslHttpEndpointDirect $Name $hostAddress $port '/api/version')) {
            $updated = Restart-WindowsNativeOllamaForEnvironment $State $desiredHost
            $restarted = $true
        } else { $updated = Get-WindowsNativeOllamaState }
        if (-not (Test-WslHttpEndpointDirect $Name $hostAddress $port '/api/version')) { throw "WSL still cannot reach native Ollama at ${hostAddress}:$port." }
        # A successful Ollama HTTP response from the selected distro is authoritative.
        # Get-NetTCPConnection is retained as diagnostics, not as a stronger gate than the
        # real API request that Hermes will use. Refresh Windows-local state after success.
        $updated = Get-WindowsNativeOllamaState
        if (-not $updated.ApiReady) { throw 'The selected distro reached Ollama, but the Windows-local API re-check unexpectedly failed.' }

        if ($oldOwned -and $oldOwned.firewallRuleName) {
            try {
                $oldRule = Get-NetFirewallRule -Name ([string]$oldOwned.firewallRuleName) -ErrorAction SilentlyContinue
                if ($oldRule -and [string]$oldRule.Group -eq 'LatticeVale') { $oldRule | Remove-NetFirewallRule -ErrorAction SilentlyContinue }
            } catch { }
        }
        if ($oldOwned -and $oldOwned.hyperVFirewallRuleName) { Remove-LatticeValeWslHyperVRule ([string]$oldOwned.hyperVFirewallRuleName) }
        $owned = [ordered]@{
            schema=2; environmentScope=$scopeName; environmentChanged=$environmentChanged -or ($oldOwned -and [bool]$oldOwned.environmentChanged);
            previousHostWasSet=$originalPreviousWasSet; previousHost=if ($originalPreviousWasSet) { [string]$originalPrevious } else { '' };
            configuredHost=$desiredHost; firewallRuleName=$tempRule; hyperVFirewallRuleName=if ($hyperVRuleCreated) { $hyperVRuleName } else { '' };
            hostAddress=$hostAddress; wslAddresses=$wslAddresses; port=$port
        }
        [IO.File]::WriteAllText($paths.State,(($owned | ConvertTo-Json -Depth 5)+"`r`n"),[Text.UTF8Encoding]::new($false))
        $result.Success=$true; $result.OllamaState=$updated
        $result.Detail="Verified direct WSL access to native Windows Ollama at ${hostAddress}:$port with an installer-owned WSL-scoped firewall rule."
        return [pscustomobject]$result
    } catch {
        $failure = $_.Exception.Message
        try { Get-NetFirewallRule -Name $tempRule -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue } catch { }
        Remove-LatticeValeWslHyperVRule $hyperVRuleName
        if ($environmentChanged) {
            try {
                if ($previousWasSet) { [Environment]::SetEnvironmentVariable('OLLAMA_HOST',[string]$previous,$scope); $env:OLLAMA_HOST=[string]$previous }
                else { [Environment]::SetEnvironmentVariable('OLLAMA_HOST',$null,$scope); Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue }
                Send-LatticeValeEnvironmentChanged
                if ($restarted) {
                    $rollbackProcessHost = if ($previousWasSet) { [string]$previous } else { '' }
                    [void](Restart-WindowsNativeOllamaForEnvironment $State $rollbackProcessHost)
                }
            } catch { }
        }
        $result.OllamaState=Get-WindowsNativeOllamaState
        $result.Detail="Direct WSL access remediation failed and its new firewall/environment changes were rolled back where possible: $failure"
        return [pscustomobject]$result
    }
}

function Remove-LatticeValeWindowsNativeOllamaDirectWslAccess([string]$Name, [bool]$RestartOllama = $true) {
    $paths = Get-LatticeValeNativeOllamaDirectPaths $Name
    if (-not (Test-Path -LiteralPath $paths.State -PathType Leaf)) { return }
    $owned = $null
    try { $owned = Get-Content -LiteralPath $paths.State -Raw | ConvertFrom-Json } catch { }
    if (-not $owned) { return }
    if ($owned.firewallRuleName) {
        try {
            $rule = Get-NetFirewallRule -Name ([string]$owned.firewallRuleName) -ErrorAction SilentlyContinue
            if ($rule -and [string]$rule.Group -eq 'LatticeVale') { $rule | Remove-NetFirewallRule -ErrorAction SilentlyContinue }
        } catch { }
    }
    if ($owned.hyperVFirewallRuleName) { Remove-LatticeValeWslHyperVRule ([string]$owned.hyperVFirewallRuleName) }
    $restored = $false
    if ([bool]$owned.environmentChanged) {
        try {
            $scope = if ([string]$owned.environmentScope -eq 'Machine') { [EnvironmentVariableTarget]::Machine } else { [EnvironmentVariableTarget]::User }
            $current = [Environment]::GetEnvironmentVariable('OLLAMA_HOST',$scope)
            if ([string]$current -eq [string]$owned.configuredHost) {
                if ([bool]$owned.previousHostWasSet) {
                    [Environment]::SetEnvironmentVariable('OLLAMA_HOST',[string]$owned.previousHost,$scope)
                    $env:OLLAMA_HOST=[string]$owned.previousHost
                } else {
                    [Environment]::SetEnvironmentVariable('OLLAMA_HOST',$null,$scope)
                    Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue
                }
                Send-LatticeValeEnvironmentChanged
                $restored=$true
            } else {
                Write-Warning 'The installer-owned direct-Ollama state exists, but OLLAMA_HOST was changed afterward. LatticeVale removed only its firewall rule and left the newer environment value untouched.'
            }
        } catch { Write-Warning "Could not restore the prior OLLAMA_HOST value: $($_.Exception.Message)" }
    }
    Remove-Item -LiteralPath $paths.State -Force -ErrorAction SilentlyContinue
    if ($restored -and $RestartOllama) {
        $state = Get-WindowsNativeOllamaState
        $restoredProcessHost = if ([bool]$owned.previousHostWasSet) { [string]$owned.previousHost } else { '' }
        [void](Restart-WindowsNativeOllamaForEnvironment $state $restoredProcessHost)
    }
}

function Resolve-LatticeValeNativeOllamaDirectFallback([string]$Name, [object]$OllamaState, [object]$BridgeState) {
    $result=[ordered]@{ OllamaState=$OllamaState; BridgeState=$BridgeState }
    if (-not $OllamaState -or -not $OllamaState.ApiReady -or ($BridgeState -and $BridgeState.Ready)) { return [pscustomobject]$result }

    # If the selected distro already receives a real Ollama /api/version response through
    # the Windows host address, preserve that working topology. When the tray app has no
    # persistent non-loopback OLLAMA_HOST yet (for example after a prior rollback), offer
    # to persist and firewall-scope it. Enable-* re-tests HTTP first and therefore does not
    # restart an already-working Ollama merely to prove the same path again.
    if ($BridgeState -and [bool]$BridgeState.DirectApiReachable) {
        $stabilize = Read-Choice 'Persist and verify the currently working direct WSL access to native Windows Ollama?' 'The selected distro already receives Ollama /api/version through the discovered Windows-host address. LatticeVale will persist OLLAMA_HOST for future Ollama restarts and create its WSL-scoped firewall allowance, then verify the same HTTP endpoint. It will not restart Ollama while that endpoint remains reachable.' 'The current process is left unchanged. Because no persistent non-loopback Ollama bind was detected, direct WSL access may disappear after Ollama restarts.' $true
        if ($stabilize) {
            $remediation=Enable-LatticeValeWindowsNativeOllamaDirectWslAccess $Name $OllamaState
            Write-Info $remediation.Detail
            $result.OllamaState=$remediation.OllamaState
            if ($remediation.Success) {
                $result.BridgeState=Get-LatticeValeNativeBridgeCapability $Name $remediation.OllamaState
                return [pscustomobject]$result
            }
            $OllamaState=$result.OllamaState
            $BridgeState=$result.BridgeState
        }
    }

    # v14.3.41 host-safety rule: never change global WSL networking to make native
    # Ollama reachable. Mirrored mode has had host-build regressions that can surface only
    # after a cold WSL/Windows restart. Preserve an already-working user-selected topology,
    # but when no bridge is available use only the explicit, firewall-scoped direct fallback
    # below. This keeps native-Ollama remediation local to Ollama instead of rearchitecting
    # networking for every WSL2 distro on the host.
    if (-not $OllamaState -or -not $OllamaState.ApiReady) { return [pscustomobject]$result }

    $hostAddress=Get-WindowsHostIpv4ForWsl $Name
    if (-not (Test-LatticeValeBridgeIpv4 $hostAddress)) { return [pscustomobject]$result }
    $useDirect = Read-Choice 'Configure native Windows Ollama for direct WSL access as a final fallback?' 'This fallback is used only because neither the private relay nor a verified localhost/direct HTTP path is available. For the normal tray app, LatticeVale persists OLLAMA_HOST at User scope; for a detected Windows service, it uses Machine scope. It adds an exact Windows-host/WSL-source firewall rule and, when available, a matching WSL Hyper-V outbound rule; then it restarts Ollama only when the selected distro cannot already reach /api/version. It does NOT set OLLAMA_ORIGINS=* because browser CORS is not required for Hermes/Honcho.' 'No Windows Ollama environment or firewall settings are changed; native Ollama remains unavailable unless another verified path is provided.' $false
    if (-not $useDirect) { return [pscustomobject]$result }
    $remediation=Enable-LatticeValeWindowsNativeOllamaDirectWslAccess $Name $OllamaState
    Write-Info $remediation.Detail
    $result.OllamaState=$remediation.OllamaState
    if ($remediation.Success) { $result.BridgeState=Get-LatticeValeNativeBridgeCapability $Name $remediation.OllamaState }
    return [pscustomobject]$result
}

function Get-LatticeValeNativeBridgeCapability([string]$Name, [object]$OllamaState = $null) {
    $state = [ordered]@{
        Ready = $false
        WindowsHostIp = ''
        Transport = ''
        NetworkingMode = ''
        DirectApiReachable = $false
        Detail = ''
    }
    if ([string]::IsNullOrWhiteSpace($Name)) {
        $state.Detail = 'No selected WSL distro is available for native Windows service bridging.'
        return [pscustomobject]$state
    }

    $state.NetworkingMode = Get-WslNetworkingMode $Name
    $gatewayFailure = ''
    $routeCandidates = @(Get-WslDefaultIpv4GatewayCandidates $Name)

    $natCandidates = [System.Collections.Generic.List[string]]::new()
    foreach ($routeCandidate in $routeCandidates) {
        if ((Test-LatticeValeBridgeIpv4 $routeCandidate) -and -not $natCandidates.Contains($routeCandidate)) { $natCandidates.Add($routeCandidate) }
    }
    foreach ($adapterCandidate in @(Get-WindowsWslAdapterIpv4Candidates $Name)) {
        if ((Test-LatticeValeBridgeIpv4 $adapterCandidate) -and -not $natCandidates.Contains($adapterCandidate)) { $natCandidates.Add($adapterCandidate) }
    }

    # First trust the application-level endpoint that Hermes will actually use. A real
    # /api/version response from the selected distro is stronger evidence than a temporary
    # synthetic TCP listener and avoids false negatives caused by separate firewall paths.
    if ($OllamaState -and $OllamaState.ApiReady) {
        $targetAddress = [string]$OllamaState.RelayTargetAddress
        $targetPort = [int]$OllamaState.RelayTargetPort
        $ipv4LoopbackTarget = ($targetAddress -eq 'localhost' -or $targetAddress -match '^127(?:\.|$)')
        if ($ipv4LoopbackTarget -and (Test-WslHttpEndpointDirect $Name $targetAddress $targetPort '/api/version')) {
            $state.Ready = $true
            $state.WindowsHostIp = 'host-gateway'
            $state.Transport = 'wsl-localhost-relay'
            $modeLabel = if ($state.NetworkingMode) { $state.NetworkingMode } else { 'localhost-capable' }
            $state.Detail = "Verified $modeLabel WSL networking: native Windows Ollama returned /api/version to '$Name' through $targetAddress. LatticeVale will use a WSL-local Docker host-gateway relay."
            return [pscustomobject]$state
        }

        foreach ($directHost in $natCandidates) {
            if (-not (Test-WindowsOwnsIpv4 $directHost)) { continue }
            if (-not (Test-WslHttpEndpointDirect $Name $directHost $targetPort '/api/version')) { continue }
            $state.WindowsHostIp = $directHost
            $state.Transport = 'wsl-host-relay'
            $state.DirectApiReachable = $true
            if (Test-WindowsNativeOllamaDirectBindingDurable $targetPort) {
                $state.Ready = $true
                $state.Detail = "Verified direct WSL access to native Windows Ollama at ${directHost}:$targetPort with a persistent non-loopback Windows bind. LatticeVale will use a WSL-local Docker host-gateway relay for containers."
            } else {
                $state.Detail = "Native Windows Ollama currently returns /api/version to '$Name' at ${directHost}:$targetPort, but no persistent non-loopback tray-app OLLAMA_HOST setting was detected. The current process may stop being reachable after Ollama restarts; LatticeVale can persist and verify this path without restarting Ollama while it already works."
            }
            return [pscustomobject]$state
        }
    }

    # If the real Ollama endpoint is not already reachable, retain the private random-port
    # temporary WSL-scoped TCP reachability probe used to establish private relay capability. This remains the preferred way to keep Ollama on Windows
    # loopback when the WSL/Windows firewall topology supports it.
    if (-not (Get-Command New-NetFirewallRule -ErrorAction SilentlyContinue) -or -not (Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue)) {
        $gatewayFailure = 'Windows Firewall cmdlets required for the NAT-style WSL-only relay are unavailable.'
    } elseif ($natCandidates.Count -gt 0) {
        foreach ($candidate in $natCandidates) {
            if (Test-WindowsHostIpv4FromWsl $Name $candidate) {
                $state.Ready = $true
                $state.WindowsHostIp = $candidate
                $state.Transport = 'windows-gateway-relay'
                $source = if ($routeCandidates -contains $candidate) { 'WSL default route' } else { 'Windows WSL/Hyper-V virtual adapter matched to the selected distro subnet' }
                $modeLabel = if ($state.NetworkingMode) { $state.NetworkingMode } else { 'gateway-based' }
                $state.Detail = "Verified $modeLabel WSL-to-Windows private relay path at $candidate discovered from the $source."
                return [pscustomobject]$state
            }
        }
        $gatewayFailure = 'Candidate Windows-host IPv4 addresses were found, but none passed the temporary WSL-scoped private-relay probe.'
    } elseif ($routeCandidates.Count -gt 0) {
        $gatewayFailure = "WSL default-route next hop(s) '$($routeCandidates -join ', ')' did not verify as a Windows-host relay path, and no matching Windows WSL/Hyper-V adapter IPv4 passed verification."
    } else {
        $gatewayFailure = 'No usable Windows-host IPv4 was parsed from the WSL default route or from a matching Windows WSL/Hyper-V virtual adapter.'
    }

    if ($OllamaState -and $OllamaState.ApiReady) {
        $targetAddress = [string]$OllamaState.RelayTargetAddress
        $targetPort = [int]$OllamaState.RelayTargetPort
        $ipv4LoopbackTarget = ($targetAddress -eq 'localhost' -or $targetAddress -match '^127(?:\.|$)')
        if ($state.NetworkingMode -eq 'mirrored' -and $ipv4LoopbackTarget) {
            $state.Detail = "WSL reports mirrored networking, but '$Name' could not reach the running native Windows Ollama API through ${targetAddress}:$targetPort. The NAT-style private-relay probe also failed: $gatewayFailure"
            return [pscustomobject]$state
        }
    }

    $modeText = if ($state.NetworkingMode) { " Current WSL networking mode: $($state.NetworkingMode)." } else { ' The active WSL networking mode could not be queried with wslinfo.' }
    if ($state.NetworkingMode -eq 'virtioproxy') {
        $state.Detail = "The selected WSL distro '$Name' is using VirtioProxy and did not expose either a verified NAT-style Windows-host path or a functional Windows localhost path.$modeText $gatewayFailure Use managed WSL/Docker Ollama, or change WSL networking only if you independently want a topology that exposes a verified host path; LatticeVale will not change it automatically for native Ollama."
    } else {
        $modeHint = if ($state.NetworkingMode -eq 'nat') { " NAT is a supported topology for this feature. LatticeVale will not switch the host to mirrored networking; use the explicit scoped native-Ollama fallback or LatticeVale-managed WSL/Docker Ollama when no verified host path exists." } else { '' }
        $state.Detail = "The selected WSL distro '$Name' did not expose a verified Windows-host path usable for native Ollama.$modeText $gatewayFailure$modeHint"
    }
    return [pscustomobject]$state
}

function Test-WindowsTcpPortInUse([int]$Port) {
    if ($Port -lt 1 -or $Port -gt 65535) { return $true }
    try {
        if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
            return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1)
        }
    } catch { }
    # Conservative fallback: test loopback. The native-service relay later performs an
    # exact bind on the WSL host interface and fails closed if another listener owns it.
    return (Test-LocalTcpPort $Port)
}

function Test-ManagedLatticeValeStackForUser([string]$Name, [string]$User) {
    $linuxHomePath = Get-LinuxUserHome $Name $User
    if (-not $linuxHomePath) { return $false }
    $stackPath = "$linuxHomePath/hermes-stack"
    # Detection deliberately runs as root. A repair must remain discoverable even if an
    # interrupted container/install left stack metadata or the root directory owned by root.
    $probe = Invoke-WslDirectCapture $Name 'root' 'test' @('-f', "$stackPath/install-options.json", '-a', '-f', "$stackPath/compose.yaml")
    if ($probe.Success) { return $true }

    # v13.16.7: do not demote an obviously installer-managed stack to "unrecognized"
    # merely because install-options.json was deleted/truncated. Strong LatticeVale runtime
    # markers keep it on the managed recovery path; Get-ExistingInstallOptions will then
    # recover a valid snapshot or fail closed before any fresh-install choices are asked.
    $coreProbe = Invoke-WslDirectCapture $Name 'root' 'test' @(
        '-f', "$stackPath/compose.yaml", '-a',
        '-f', "$stackPath/configure-stack.sh", '-a',
        '-f', "$stackPath/manage.sh"
    )
    if (-not $coreProbe.Success) { return $false }
    $stateProbe = Invoke-WslDirectCapture $Name 'root' 'test' @('-f', "$stackPath/.installer-state.json")
    if ($stateProbe.Success) { return $true }
    # v14.5.43 universal repair: v12/v13-era managed stacks may predate the current
    # checkpoint file but still carry exact installer finalization markers. Require
    # the proven core file trio above plus one of these historical markers so an
    # arbitrary ~/hermes-stack directory is never adopted merely by name.
    $legacyMarkerProbe = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc', "test -s '$stackPath/.install-info' -o -f '$stackPath/.configured'")
    if ($legacyMarkerProbe.Success) { return $true }
    $backupProbe = Invoke-WslDirectCapture $Name 'root' 'find' @(
        "$stackPath/backups", '-mindepth', '2', '-maxdepth', '2', '-type', 'f',
        '(', '-name', 'installer-config.tar.gz', '-o', '-name', 'files.tar.gz', ')', '-print', '-quit'
    ) 15
    return [bool]($backupProbe.Success -and -not [string]::IsNullOrWhiteSpace($backupProbe.Text))
}

function Get-LatticeValeStackPathState([string]$Name, [string]$User) {
    $linuxHomePath = Get-LinuxUserHome $Name $User
    if (-not $linuxHomePath) { return 'unknown' }
    $stackPath = "$linuxHomePath/hermes-stack"
    $dirProbe = Invoke-WslDirectCapture $Name 'root' 'test' @('-d', $stackPath)
    if (-not $dirProbe.Success) { return 'absent' }
    if (Test-ManagedLatticeValeStackForUser $Name $User) { return 'managed' }
    return 'unrecognized'
}

function Get-LinuxHomeFilesystemType([string]$Name, [string]$User) {
    $probe = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', 'stat -f -c %T "$HOME" 2>/dev/null')
    if (-not $probe.Success) { return $null }
    $fsType = (($probe.Text -split "`r?`n") | Select-Object -First 1).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($fsType)) { return $null }
    return $fsType
}

function Format-LinuxNativeFilesystemLabel([string]$FsType) {
    if ([string]::IsNullOrWhiteSpace($FsType)) { return 'unknown Linux-native filesystem' }
    $normalized = $FsType.Trim().ToLowerInvariant()
    switch ($normalized) {
        'ext2/ext3' { return 'ext2/ext3/ext4-compatible Linux-native filesystem' }
        'ext2/ext3/ext4' { return 'ext2/ext3/ext4-compatible Linux-native filesystem' }
        'ext4' { return 'ext4 Linux-native filesystem' }
        'btrfs' { return 'btrfs Linux-native filesystem' }
        'xfs' { return 'xfs Linux-native filesystem' }
        default { return "$normalized Linux-native filesystem" }
    }
}

function Assert-LinuxNativeHomeFilesystem([string]$Name, [string]$User) {
    $fsType = Get-LinuxHomeFilesystemType $Name $User
    if (-not $fsType) {
        throw "Could not verify the filesystem type for '$User''s Linux home directory. This installer requires a Linux-native WSL home filesystem because Docker bind mounts and database permissions rely on normal Linux ownership/mode semantics."
    }
    $unsupported = @('9p','drvfs','fuseblk','ntfs','ntfs3','cifs','smb2','vfat','exfat')
    if ($unsupported -contains $fsType) {
        throw "The selected Ubuntu user's home directory is on filesystem '$fsType'. This stack stores Docker bind-mounted configuration and state under ~/hermes-stack and requires a Linux-native WSL filesystem. Move/use a normal Linux home inside the distro VHD, then rerun."
    }
    return $fsType
}

function Convert-LinuxPathToWslUnc([string]$Name, [string]$LinuxPath, [switch]$Legacy) {
    if ([string]::IsNullOrWhiteSpace($LinuxPath) -or -not $LinuxPath.StartsWith('/')) { return $null }
    $relative = $LinuxPath.TrimStart('/').Replace('/', '\')
    $root = if ($Legacy) { "\\wsl$\$Name" } else { "\\wsl.localhost\$Name" }
    if ([string]::IsNullOrWhiteSpace($relative)) { return $root }
    return "$root\$relative"
}


function Get-CurrentWindowsIdentityName {
    try {
        $name = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        if (-not [string]::IsNullOrWhiteSpace($name)) { return $name }
    } catch { }
    $fallback = "$env:USERDOMAIN\$env:USERNAME".Trim('\')
    if ([string]::IsNullOrWhiteSpace($fallback)) { throw 'Could not determine the current Windows account identity.' }
    return $fallback
}

function Get-LatticeValeScheduledTaskName([string]$Name) {
    $safe = ([regex]::Replace($Name, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = 'distro' }
    if ($safe.Length -gt 36) { $safe = $safe.Substring(0, 36) }
    $identity = "$(Get-CurrentWindowsIdentityName)`n$Name"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($identity)
        $hash = $sha.ComputeHash($bytes)
        $suffix = -join ($hash[0..4] | ForEach-Object { $_.ToString('x2') })
    } finally {
        $sha.Dispose()
    }
    return "LatticeVale Stack - $safe-$suffix"
}


function Get-LatticeValeBridgeTaskName([string]$Name) {
    $base = Get-LatticeValeScheduledTaskName $Name
    return ($base -replace '^LatticeVale Stack - ', 'LatticeVale Tailscale Relay - ')
}

function Get-LatticeValeNativeServiceTaskName([string]$Name) {
    $base = Get-LatticeValeScheduledTaskName $Name
    return ($base -replace '^LatticeVale Stack - ', 'LatticeVale Native Windows Bridge - ')
}


function Get-LegacyV14ScheduledTaskName([string]$Name) {
    # Compatibility only: v14.0 and earlier used this user-visible task prefix.
    $safe = ([regex]::Replace($Name, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = 'distro' }
    if ($safe.Length -gt 36) { $safe = $safe.Substring(0, 36) }
    $identity = "$(Get-CurrentWindowsIdentityName)`n$Name"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($identity)
        $hash = $sha.ComputeHash($bytes)
        $suffix = -join ($hash[0..4] | ForEach-Object { $_.ToString('x2') })
    } finally { $sha.Dispose() }
    $legacyVendor = 'Hermes'
    return "$legacyVendor WSL Docker Stack - $safe-$suffix"
}

function Get-LegacyV14BridgeTaskName([string]$Name) {
    $legacyVendor = 'Hermes'
    $oldPrefix = "$legacyVendor WSL Docker Stack - "
    $relayPrefix = "$legacyVendor WSL Tailscale Bridge - "
    $current = Get-LegacyV14ScheduledTaskName $Name
    if ($current.StartsWith($oldPrefix, [System.StringComparison]::Ordinal)) {
        return ($relayPrefix + $current.Substring($oldPrefix.Length))
    }
    return $current
}

function Get-LegacyV14ShortcutPaths([string]$Name, [string]$User, [string]$StackLinuxPath) {
    # Compatibility only: identify v14.0 project-owned shortcuts precisely so a repair
    # can migrate them without touching unrelated shortcuts.
    $safeName = ([regex]::Replace($Name, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ([string]::IsNullOrWhiteSpace($safeName)) { $safeName = 'distro' }
    if ($safeName.Length -gt 40) { $safeName = $safeName.Substring(0, 40) }
    $safeUser = ([regex]::Replace($User, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ([string]::IsNullOrWhiteSpace($safeUser)) { $safeUser = 'user' }
    if ($safeUser.Length -gt 32) { $safeUser = $safeUser.Substring(0, 32) }
    $identity = "$(Get-CurrentWindowsIdentityName)`n$Name`n$User`n$StackLinuxPath"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($identity)
        $hash = $sha.ComputeHash($bytes)
        $suffix = -join ($hash[0..5] | ForEach-Object { $_.ToString('x2') })
    } finally { $sha.Dispose() }
    $legacyVendor = 'Hermes'
    $legacyProject = 'Foundry'
    $dir = Join-Path (Join-Path $env:LOCALAPPDATA $legacyVendor) $legacyProject
    $desktop = [Environment]::GetFolderPath('Desktop')
    return [pscustomobject]@{
        Directory = $dir
        Helper = (Join-Path $dir (("{0}-{1}Shortcut-{2}-{3}-{4}.ps1" -f $legacyVendor, $legacyProject, $safeName, $safeUser, $suffix)))
        Config = (Join-Path $dir ("shortcut-$safeName-$safeUser-$suffix.json"))
        Log = (Join-Path $dir ("shortcut-$safeName-$safeUser-$suffix.log"))
        StartShortcut = (Join-Path $desktop "Start $legacyVendor $legacyProject - $safeName ($safeUser).lnk")
        ShutdownShortcut = (Join-Path $desktop "Shut Down $legacyVendor $legacyProject - $safeName ($safeUser).lnk")
    }
}

function Get-LatticeValeShortcutPaths([string]$Name, [string]$User, [string]$StackLinuxPath) {
    $safeName = ([regex]::Replace($Name, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ([string]::IsNullOrWhiteSpace($safeName)) { $safeName = 'distro' }
    if ($safeName.Length -gt 40) { $safeName = $safeName.Substring(0, 40) }
    $safeUser = ([regex]::Replace($User, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ([string]::IsNullOrWhiteSpace($safeUser)) { $safeUser = 'user' }
    if ($safeUser.Length -gt 32) { $safeUser = $safeUser.Substring(0, 32) }

    $identity = "$(Get-CurrentWindowsIdentityName)`n$Name`n$User`n$StackLinuxPath"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($identity)
        $hash = $sha.ComputeHash($bytes)
        $suffix = -join ($hash[0..5] | ForEach-Object { $_.ToString('x2') })
    } finally {
        $sha.Dispose()
    }

    $dir = Join-Path $env:LOCALAPPDATA 'LatticeVale'
    $desktop = [Environment]::GetFolderPath('Desktop')
    $config = Join-Path $dir ("shortcut-$safeName-$safeUser-$suffix.json")
    $log = Join-Path $dir ("shortcut-$safeName-$safeUser-$suffix.log")
    $helper = Join-Path $dir ("LatticeVale-Shortcut-$safeName-$safeUser-$suffix.ps1")
    return [pscustomobject]@{
        Directory = $dir
        Helper = $helper
        Config = $config
        Log = $log
        StartShortcut = (Join-Path $desktop "Start LatticeVale - $safeName ($safeUser).lnk")
        ShutdownShortcut = (Join-Path $desktop "Shut Down LatticeVale - $safeName ($safeUser).lnk")
    }
}

function Test-LatticeValeShortcutOwned([string]$ShortcutPath, [object]$Paths) {
    if (-not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf)) { return $false }
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($ShortcutPath)
        $target = [string]$shortcut.TargetPath
        $arguments = [string]$shortcut.Arguments
        $expectedPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        if (-not $target.Equals($expectedPowerShell, [StringComparison]::OrdinalIgnoreCase)) { return $false }
        if ($arguments.IndexOf([string]$Paths.Helper, [StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
        if ($arguments.IndexOf([string]$Paths.Config, [StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
        return $true
    } catch {
        return $false
    }
}

function Remove-LegacyV14DesktopShortcuts([string]$Name, [string]$User, [string]$StackLinuxPath) {
    $paths = Get-LegacyV14ShortcutPaths $Name $User $StackLinuxPath
    foreach ($shortcutPath in @($paths.StartShortcut, $paths.ShutdownShortcut)) {
        if ((Test-Path -LiteralPath $shortcutPath -PathType Leaf) -and (Test-LatticeValeShortcutOwned $shortcutPath $paths)) {
            Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
        }
    }
    # Delete old helper/config/log only if no legacy shortcut still references them.
    $stillReferenced = $false
    foreach ($shortcutPath in @($paths.StartShortcut, $paths.ShutdownShortcut)) {
        if ((Test-Path -LiteralPath $shortcutPath -PathType Leaf) -and (Test-LatticeValeShortcutOwned $shortcutPath $paths)) { $stillReferenced = $true }
    }
    if (-not $stillReferenced) {
        foreach ($ownedPath in @($paths.Config, $paths.Helper, $paths.Log)) {
            if (Test-Path -LiteralPath $ownedPath -PathType Leaf) { Remove-Item -LiteralPath $ownedPath -Force -ErrorAction SilentlyContinue }
        }
    }
}

function New-LatticeValeDesktopShortcut(
    [string]$ShortcutPath,
    [string]$Action,
    [object]$Paths,
    [string]$Description
) {
    if (Test-Path -LiteralPath $ShortcutPath -PathType Leaf) {
        if (-not (Test-LatticeValeShortcutOwned $ShortcutPath $Paths)) {
            Write-Warning "A non-LatticeVale shortcut already exists at '$ShortcutPath'. It was left untouched."
            return $false
        }
    }
    $powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $wslIcon = Join-Path $env:SystemRoot 'System32\wsl.exe'
    $shortcutArgs = @(
        '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
        '-File', [string]$Paths.Helper,
        '-ConfigPath', [string]$Paths.Config,
        '-Action', $Action
    )
    $argumentLine = (($shortcutArgs | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $powershellExe
    $shortcut.Arguments = $argumentLine
    $shortcut.WorkingDirectory = [string]$Paths.Directory
    $shortcut.IconLocation = "$wslIcon,0"
    $shortcut.Description = $Description
    $shortcut.Save()
    return (Test-LatticeValeShortcutOwned $ShortcutPath $Paths)
}

function Install-LatticeValeDesktopShortcuts(
    [string]$Name,
    [string]$User,
    [string]$StackLinuxPath,
    [string]$InstallerVersion,
    [string]$OllamaBackend = 'managed'
) {
    Remove-LegacyV14DesktopShortcuts $Name $User $StackLinuxPath
    $paths = Get-LatticeValeShortcutPaths $Name $User $StackLinuxPath
    try {
        New-Item -ItemType Directory -Path $paths.Directory -Force | Out-Null
        $helperSource = Join-Path $PSScriptRoot 'windows\LatticeVale-Shortcut.ps1'
        if (-not (Test-Path -LiteralPath $helperSource -PathType Leaf)) {
            throw "Shortcut launcher source is missing from the installer bundle: $helperSource"
        }
        Copy-Item -LiteralPath $helperSource -Destination $paths.Helper -Force

        $nativeOllamaConfig = [ordered]@{
            enabled = $false
            apiEndpoint = ''
            appExecutable = ''
            executable = ''
            serviceName = ''
        }
        if ($OllamaBackend -eq 'windows-native') {
            $nativeState = Get-WindowsNativeOllamaState
            $nativeService = Get-WindowsNativeOllamaService
            $nativeOllamaConfig.enabled = $true
            $nativeOllamaConfig.apiEndpoint = [string]$nativeState.Endpoint
            $nativeOllamaConfig.appExecutable = [string]$nativeState.AppExecutable
            $nativeOllamaConfig.executable = [string]$nativeState.Executable
            if ($nativeService) { $nativeOllamaConfig.serviceName = [string]$nativeService.Name }
        }

        $config = [ordered]@{
            schema = 4
            installerVersion = $InstallerVersion
            distroName = $Name
            linuxUser = $User
            stackLinuxPath = $StackLinuxPath
            logPath = [string]$paths.Log
            nativeOllama = $nativeOllamaConfig
        }
        $config | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $paths.Config -Encoding UTF8

        $startOk = New-LatticeValeDesktopShortcut $paths.StartShortcut 'Start' $paths "Start the selected LatticeVale services in $Name as $User"
        $shutdownOk = New-LatticeValeDesktopShortcut $paths.ShutdownShortcut 'Shutdown' $paths "Stop the selected LatticeVale services without terminating the WSL distro"
        $runtime = Test-LatticeValeShortcutRuntimeContract $paths
        if ($startOk -and $shutdownOk -and $runtime.Valid) {
            return [pscustomobject]@{ Status='CONFIGURED'; Detail="Desktop Start/Shutdown shortcuts are configured for $Name / $User; $($runtime.Detail)."; Paths=$paths }
        }
        $runtimeDetail = if (-not $runtime.Valid) { " Runtime validation: $($runtime.Detail)." } else { '' }
        return [pscustomobject]@{ Status='PARTIAL'; Detail=('One or more requested desktop shortcuts could not be created safely because an unowned conflicting shortcut exists or validation failed.' + $runtimeDetail); Paths=$paths }
    } catch {
        return [pscustomobject]@{ Status='PARTIAL'; Detail="Desktop shortcut setup failed: $($_.Exception.Message)"; Paths=$paths }
    }
}

function Remove-LatticeValeDesktopShortcuts([string]$Name, [string]$User, [string]$StackLinuxPath) {
    Remove-LegacyV14DesktopShortcuts $Name $User $StackLinuxPath
    $paths = Get-LatticeValeShortcutPaths $Name $User $StackLinuxPath
    $blocked = $false
    foreach ($shortcutPath in @($paths.StartShortcut, $paths.ShutdownShortcut)) {
        if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) { continue }
        if (Test-LatticeValeShortcutOwned $shortcutPath $paths) {
            Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
        } else {
            $blocked = $true
            Write-Warning "Shortcut '$shortcutPath' is not provably LatticeVale-owned and was left untouched."
        }
    }
    foreach ($ownedPath in @($paths.Config, $paths.Helper, $paths.Log)) {
        if (Test-Path -LiteralPath $ownedPath -PathType Leaf) {
            Remove-Item -LiteralPath $ownedPath -Force -ErrorAction SilentlyContinue
        }
    }
    if ($blocked) {
        return [pscustomobject]@{ Status='PARTIAL'; Detail='LatticeVale shortcut cleanup was requested, but at least one same-name unowned shortcut was preserved.'; Paths=$paths }
    }
    return [pscustomobject]@{ Status='DISABLED'; Detail='Desktop Start/Shutdown shortcuts are not selected.'; Paths=$paths }
}

function Test-LatticeValeShortcutRuntimeContract([object]$Paths) {
    $result = [ordered]@{ Valid = $false; Detail = '' }
    if (-not (Test-Path -LiteralPath $Paths.Config -PathType Leaf)) {
        $result.Detail = 'shortcut configuration is missing'
        return [pscustomobject]$result
    }
    if (-not (Test-Path -LiteralPath $Paths.Helper -PathType Leaf)) {
        $result.Detail = 'shortcut helper is missing'
        return [pscustomobject]$result
    }
    try {
        $config = Get-Content -LiteralPath $Paths.Config -Raw | ConvertFrom-Json
        $schema = 0
        if ($config.PSObject.Properties['schema']) { [void][int]::TryParse([string]$config.schema, [ref]$schema) }
        if ($schema -lt 4) {
            $result.Detail = "shortcut schema $schema predates the direct WSL --cd launcher contract"
            return [pscustomobject]$result
        }

        $raw = [IO.File]::ReadAllText($Paths.Helper)
        if ($raw -match '(?im)^\s*&\s*\$wslExe\s+--terminate\s+\$distro\s*$') {
            $result.Detail = 'shortcut helper still contains targeted wsl --terminate'
            return [pscustomobject]$result
        }
        if ($raw -match '(?m)^\s*\$manageCommand\s*=|bash\s+-lc\s+\$manageCommand') {
            $result.Detail = 'shortcut helper still contains the broken nested bash -lc manage.sh launcher'
            return [pscustomobject]$result
        }
        if ($raw -notmatch '(?m)^\s*&\s*\$wslExe\s+-d\s+\$distro\s+-u\s+\$user\s+--cd\s+\$stack\s+--\s+\./manage\.sh\s+start\s*$') {
            $result.Detail = 'shortcut helper is missing the direct manage.sh start launcher'
            return [pscustomobject]$result
        }
        if ($raw -notmatch '(?m)^\s*&\s*\$wslExe\s+-d\s+\$distro\s+-u\s+\$user\s+--cd\s+\$stack\s+--\s+\./manage\.sh\s+stop\s*$') {
            $result.Detail = 'shortcut helper is missing the direct manage.sh stop launcher'
            return [pscustomobject]$result
        }
        $result.Valid = $true
        $result.Detail = 'schema 4 direct WSL --cd launcher verified'
        return [pscustomobject]$result
    } catch {
        $result.Detail = "shortcut runtime contract could not be verified: $($_.Exception.Message)"
        return [pscustomobject]$result
    }
}

function Get-LatticeValeDesktopShortcutState([string]$Name, [string]$User, [string]$StackLinuxPath, [bool]$Expected) {
    $paths = Get-LatticeValeShortcutPaths $Name $User $StackLinuxPath
    $startOwned = Test-LatticeValeShortcutOwned $paths.StartShortcut $paths
    $shutdownOwned = Test-LatticeValeShortcutOwned $paths.ShutdownShortcut $paths
    $configPresent = Test-Path -LiteralPath $paths.Config -PathType Leaf
    $helperPresent = Test-Path -LiteralPath $paths.Helper -PathType Leaf
    $runtime = Test-LatticeValeShortcutRuntimeContract $paths
    if ($Expected) {
        if ($startOwned -and $shutdownOwned -and $configPresent -and $helperPresent -and $runtime.Valid) {
            return [pscustomobject]@{ Status='CONFIGURED'; Detail="Desktop Start/Shutdown shortcuts are configured for $Name / $User; $($runtime.Detail)."; Paths=$paths }
        }
        $detail = if (-not $runtime.Valid) { " Shortcut runtime repair required: $($runtime.Detail)." } else { '' }
        return [pscustomobject]@{ Status='PARTIAL'; Detail=('Desktop shortcuts were selected but one or more installer-owned shortcut files/configuration are missing or not verifiable.' + $detail); Paths=$paths }
    }
    if ($startOwned -or $shutdownOwned -or $configPresent) {
        return [pscustomobject]@{ Status='PARTIAL'; Detail='Desktop shortcuts are disabled but installer-owned shortcut state remains for reconciliation.'; Paths=$paths }
    }
    return [pscustomobject]@{ Status='DISABLED'; Detail='Desktop Start/Shutdown shortcuts are not selected.'; Paths=$paths }
}

function Test-LatticeValeBrokenShortcutLauncher(
    [string]$Name,
    [string]$User,
    [string]$StackLinuxPath
) {
    $paths = Get-LatticeValeShortcutPaths $Name $User $StackLinuxPath
    if (-not ((Test-LatticeValeShortcutOwned $paths.StartShortcut $paths) -or (Test-LatticeValeShortcutOwned $paths.ShutdownShortcut $paths))) { return $false }
    $runtime = Test-LatticeValeShortcutRuntimeContract $paths
    return (-not $runtime.Valid)
}

function Test-LatticeValeLegacyUnsafeShutdownShortcut(
    [string]$Name,
    [string]$User,
    [string]$StackLinuxPath
) {
    $paths = Get-LatticeValeShortcutPaths $Name $User $StackLinuxPath
    if (-not (Test-LatticeValeShortcutOwned $paths.ShutdownShortcut $paths)) { return $false }
    if (-not (Test-Path -LiteralPath $paths.Helper -PathType Leaf)) { return $false }
    try {
        $raw = [IO.File]::ReadAllText($paths.Helper)
        return ($raw -match '(?im)^\s*&\s*\$wslExe\s+--terminate\s+\$distro\s*$')
    } catch {
        return $false
    }
}

function Invoke-LatticeValeLegacyShortcutWslTransportRepair(
    [string]$Name,
    [string]$User,
    [string]$StackLinuxPath
) {
    Write-Step 'Repairing WSL transport after the legacy LatticeVale shutdown shortcut'
    Write-Warning 'This installation still has a pre-v14.4.84 LatticeVale shutdown helper that uses targeted `wsl --terminate`. Current WSL 2.7.x builds can leave new-session hvsocket transport unusable after that operation. LatticeVale will perform one bounded host-transport reset before replacing the shortcut helper.'

    $running = @(Get-LatticeValeRunningWslDistros)
    $others = @($running | Where-Object { -not $_.Equals($Name, [System.StringComparison]::OrdinalIgnoreCase) })
    if ($others.Count -gt 0) {
        Write-Warning ("The transport repair requires `wsl --shutdown`, which stops all running WSL2 distros. Other running distros: {0}" -f ($others -join ', '))
        if (-not (Read-ChoiceExplicit 'Temporarily stop all running WSL distros so LatticeVale can repair the host transport it previously exposed to targeted termination?' 'The repair first stops this managed stack, performs a global WSL shutdown, restarts WslService, and re-probes the same registered distro. No distro registration, VHDX, or .wslconfig setting is changed.' 'Skip the host transport reset. The shortcut helper will still be replaced later in this repair run, but any already-wedged WSL transport may require a manual `wsl --shutdown` before it is healthy.' $false $false)) {
            Write-Warning 'Legacy shortcut host-transport reset was skipped by explicit choice. Shortcut reconciliation will still remove the targeted-termination behavior.'
            return $false
        }
    }

    if ($running -contains $Name) {
        Write-Info 'Stopping the managed stack cleanly before resetting WSL host transport.'
        $stop = Invoke-NativeProcessCapture 'wsl.exe' @('-d',$Name,'-u',$User,'--cd',$StackLinuxPath,'--','./manage.sh','stop') 240
        if (-not $stop.Success) {
            $detail = Get-SafeDiagnosticExcerpt $stop.Text 420
            if (-not $detail) { $detail = 'manage.sh stop failed without diagnostic output' }
            throw "Could not stop the managed stack cleanly before the LatticeVale WSL transport repair: $detail"
        }
    }

    $shutdown = Invoke-NativeProcessCapture 'wsl.exe' @('--shutdown') 45
    if (-not $shutdown.Success) {
        $detail = Get-SafeDiagnosticExcerpt $shutdown.Text 320
        if ($shutdown.TimedOut) { $detail = 'wsl --shutdown exceeded the 45-second safety timeout' }
        if (-not $detail) { $detail = "wsl.exe exit code $($shutdown.ExitCode)" }
        throw "The LatticeVale WSL transport repair could not complete its clean shutdown: $detail"
    }

    $wslService = Get-Service -Name 'WslService' -ErrorAction SilentlyContinue
    if ($wslService) {
        Write-Info 'Restarting WslService to discard stale hvsocket/session transport state.'
        Restart-Service -Name 'WslService' -Force -ErrorAction Stop
    } else {
        Write-Warning 'WslService was not discoverable after shutdown. Continuing with the clean WSL reset; the launch probe remains authoritative.'
    }

    Start-Sleep -Seconds 5
    $ready = Wait-LatticeValeWslResponsive $Name 120
    if (-not $ready.Success) {
        throw "The LatticeVale WSL transport repair reset WSL/WslService, but '$Name' did not become responsive within 120 seconds. Last response: $($ready.Detail)`nRestart Windows once, then rerun the current LatticeVale release and choose Resume / repair. Do not unregister or recreate the distro."
    }

    Write-Host "WSL host/session transport recovered for '$Name'. The repair will now replace the legacy targeted-termination shortcut helper." -ForegroundColor Green
    return $true
}

function Get-LatticeValeBridgePaths([string]$Name) {
    $taskName = Get-LatticeValeBridgeTaskName $Name
    $key = ([regex]::Replace($taskName, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ($key.Length -gt 96) { $key = $key.Substring(0, 96) }
    $dir = Join-Path $env:LOCALAPPDATA 'LatticeVale'
    return [pscustomobject]@{
        Directory = $dir
        Script = (Join-Path $dir 'LatticeVale-WslNativeRelay.ps1')
        Config = (Join-Path $dir ("bridge-$key.json"))
        TaskName = $taskName
    }
}

function Get-LatticeValeNativeServicePaths([string]$Name) {
    $taskName = Get-LatticeValeNativeServiceTaskName $Name
    $key = ([regex]::Replace($taskName, '[^A-Za-z0-9._-]', '_')).Trim('_')
    if ($key.Length -gt 96) { $key = $key.Substring(0, 96) }
    $dir = Join-Path $env:LOCALAPPDATA 'LatticeVale'
    return [pscustomobject]@{
        Directory = $dir
        Script = (Join-Path $dir 'LatticeVale-WindowsNativeServiceRelay.ps1')
        Config = (Join-Path $dir ("native-services-$key.json"))
        Log = (Join-Path $dir 'windows-native-service-relay.log')
        RuleKey = $key
        TaskName = $taskName
    }
}

function Remove-LegacyV14BridgeSupport([string]$Name) {
    # Compatibility only: v14.0 used a product-associated task name and app-data path.
    # Remove it only when its action references the exact old relay script path.
    $taskName = Get-LegacyV14BridgeTaskName $Name
    $legacyDir = Join-Path (Join-Path $env:LOCALAPPDATA 'Hermes') 'Foundry'
    $script = Join-Path $legacyDir 'Hermes-WslNativeRelay.ps1'
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) { return }
    $owned = $false
    foreach ($action in @($task.Actions)) {
        $argsText = [string]$action.Arguments
        if ($argsText -and $argsText.IndexOf($script, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { $owned = $true; break }
    }
    if (-not $owned) {
        Write-Warning "A legacy-named relay task '$taskName' exists but is not proven to be installer-owned. It was left untouched."
        return
    }
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Info "Removed the verified v14.0 relay task so LatticeVale can register the renamed equivalent."
}

function Remove-LegacyHermesManualRelay([string]$Name) {
    # v13.12.x live troubleshooting used this exact task/script name before the
    # installer-owned native relay existed. Clean it up only when the scheduled
    # task action proves it owns the known script path; never kill arbitrary
    # listeners or remove an unrelated task with a similar name.
    $legacyTaskName = "Hermes WSL Native Relay - $Name"
    $legacyDir = Join-Path (Join-Path $env:LOCALAPPDATA 'Hermes') 'Foundry'
    $legacyScript = Join-Path $legacyDir 'Hermes-Wsl-NativeRelay.ps1'
    $legacyLog = Join-Path $legacyDir 'native-relay.log'
    $task = Get-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue
    if (-not $task) { return }

    $owned = $false
    foreach ($action in @($task.Actions)) {
        $argsText = [string]$action.Arguments
        if (-not [string]::IsNullOrWhiteSpace($argsText) -and $argsText.IndexOf($legacyScript, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $owned = $true
            break
        }
    }
    if (-not $owned) {
        Write-Warning "A scheduled task named '$legacyTaskName' exists but is not proven to be the prior legacy manual relay. It was left untouched."
        return
    }

    Stop-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $legacyTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $legacyScript,$legacyLog -Force -ErrorAction SilentlyContinue
    Write-Info "Removed the prior legacy manually-created native relay task so LatticeVale can take ownership cleanly."
}

function Get-WslGlobalNetworkingMode {
    $path = Join-Path $env:USERPROFILE '.wslconfig'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [pscustomobject]@{ Path=$path; Mode='default'; Explicit=$false }
    }
    try { $text = Get-Content -LiteralPath $path -Raw -ErrorAction Stop } catch {
        return [pscustomobject]@{ Path=$path; Mode='unknown'; Explicit=$false }
    }
    $section = ''
    foreach ($line in ($text -split "`r?`n")) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') { $section = $Matches[1].Trim().ToLowerInvariant(); continue }
        if ($section -eq 'wsl2' -and $trimmed -match '^(?i:networkingMode)\s*=\s*(.+?)\s*$') {
            return [pscustomobject]@{ Path=$path; Mode=$Matches[1].Trim().ToLowerInvariant(); Explicit=$true }
        }
    }
    return [pscustomobject]@{ Path=$path; Mode='default'; Explicit=$false }
}


# v14.3.41 intentionally contains no installer-side function that writes
# [wsl2] networkingMode. Existing user-selected networking is discovered and used
# capability-first, while host recovery is isolated in tools\Repair-LatticeVale-WslHost.ps1.

function Get-WslStorePackageVersion([object]$WslInfo) {
    if (-not $WslInfo -or -not $WslInfo.Modern -or [string]::IsNullOrWhiteSpace([string]$WslInfo.VersionText)) { return $null }
    $firstLine = (([string]$WslInfo.VersionText -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1) -as [string])
    if ($firstLine -and $firstLine -match '(\d+\.\d+\.\d+(?:\.\d+)?)') {
        try { return [version]$Matches[1] } catch { }
    }
    return $null
}

function Test-WslInstanceIdleTimeoutSupported([object]$WslInfo) {
    $version = Get-WslStorePackageVersion $WslInfo
    return ($null -ne $version -and $version -ge [version]'2.5.4')
}

function Get-WslGlobalInstanceIdleTimeout {
    $path = Join-Path $env:USERPROFILE '.wslconfig'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [pscustomobject]@{ Path=$path; Value='default'; Explicit=$false }
    }
    try { $text = Get-Content -LiteralPath $path -Raw -ErrorAction Stop } catch {
        return [pscustomobject]@{ Path=$path; Value='unknown'; Explicit=$false }
    }
    $section = ''
    foreach ($line in ($text -split "`r?`n")) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') { $section = $Matches[1].Trim().ToLowerInvariant(); continue }
        if ($section -eq 'general' -and $trimmed -match '^(?i:instanceIdleTimeout)\s*=\s*(.+?)\s*$') {
            return [pscustomobject]@{ Path=$path; Value=$Matches[1].Trim(); Explicit=$true }
        }
    }
    return [pscustomobject]@{ Path=$path; Value='default'; Explicit=$false }
}

function Get-WslGlobalVmIdleTimeout {
    $path = Join-Path $env:USERPROFILE '.wslconfig'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [pscustomobject]@{ Path=$path; Value='default'; Explicit=$false }
    }
    try { $text = Get-Content -LiteralPath $path -Raw -ErrorAction Stop } catch {
        return [pscustomobject]@{ Path=$path; Value='unknown'; Explicit=$false }
    }
    $section = ''
    foreach ($line in ($text -split "`r?`n")) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') { $section = $Matches[1].Trim().ToLowerInvariant(); continue }
        if ($section -eq 'wsl2' -and $trimmed -match '^(?i:vmIdleTimeout)\s*=\s*(.+?)\s*$') {
            return [pscustomobject]@{ Path=$path; Value=$Matches[1].Trim(); Explicit=$true }
        }
    }
    return [pscustomobject]@{ Path=$path; Value='default'; Explicit=$false }
}

function Set-WslGlobalIdleTimeoutsDisabled([string]$Path) {
    # Current WSL has separate distro/instance and VM idle timers. When the user
    # explicitly selects persistent server lifetime, disable both while preserving
    # every unrelated .wslconfig setting. A single pre-change backup covers both keys.
    $exists = Test-Path -LiteralPath $Path -PathType Leaf
    $text = if ($exists) { Get-Content -LiteralPath $Path -Raw -ErrorAction Stop } else { '' }
    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($line in ($text -split "`r?`n", -1)) { $lines.Add($line) }
    if ($lines.Count -eq 1 -and $lines[0] -eq '' -and -not $exists) { $lines.Clear() }

    function Set-LatticeValeWslConfigValue(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$SectionName,
        [string]$Key,
        [string]$Value
    ) {
        $section = ''
        $sectionHeader = -1
        $sectionEnd = $Lines.Count
        $matching = [System.Collections.Generic.List[int]]::new()
        for ($i = 0; $i -lt $Lines.Count; $i++) {
            $trimmed = $Lines[$i].Trim()
            if ($trimmed -match '^\[(.+)\]$') {
                if ($section -eq $SectionName -and $sectionEnd -eq $Lines.Count) { $sectionEnd = $i }
                $section = $Matches[1].Trim().ToLowerInvariant()
                if ($section -eq $SectionName -and $sectionHeader -lt 0) { $sectionHeader = $i; $sectionEnd = $Lines.Count }
                continue
            }
            if ($section -eq $SectionName -and $trimmed -match ('^(?i:' + [regex]::Escape($Key) + ')\s*=')) { $matching.Add($i) }
        }

        $desired = "$Key=$Value"
        $changed = $false
        if ($matching.Count -gt 0) {
            $first = $matching[0]
            $indent = ([regex]::Match($Lines[$first], '^\s*')).Value
            if ($Lines[$first].Trim() -ne $desired) { $Lines[$first] = "${indent}${desired}"; $changed = $true }
            for ($j = $matching.Count - 1; $j -ge 1; $j--) { $Lines.RemoveAt($matching[$j]); $changed = $true }
        } elseif ($sectionHeader -ge 0) {
            $Lines.Insert($sectionEnd, $desired)
            $changed = $true
        } else {
            if ($Lines.Count -gt 0 -and $Lines[$Lines.Count-1] -ne '') { $Lines.Add('') }
            $Lines.Add("[$SectionName]")
            $Lines.Add($desired)
            $changed = $true
        }
        return $changed
    }

    $changed = $false
    if (Set-LatticeValeWslConfigValue $lines 'general' 'instanceIdleTimeout' '-1') { $changed = $true }
    if (Set-LatticeValeWslConfigValue $lines 'wsl2' 'vmIdleTimeout' '-1') { $changed = $true }

    if (-not $changed) { return [pscustomobject]@{ Changed=$false; Backup=''; Path=$Path } }
    $backup = ''
    if ($exists) {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $backup = "$Path.latticevale-pre-$stamp.bak"
        Copy-Item -LiteralPath $Path -Destination $backup -Force
    }
    $newText = ($lines -join "`r`n")
    if ($newText -and -not $newText.EndsWith("`r`n")) { $newText += "`r`n" }
    [System.IO.File]::WriteAllText($Path, $newText, [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{ Changed=$true; Backup=$backup; Path=$Path }
}

function Wait-LatticeValeWslResponsive(
    [string]$Name,
    [int]$TimeoutSeconds = 180
) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastDetail = ''
    do {
        $probe = Invoke-WslDirectCapture $Name 'root' 'true' @() 10
        if ($probe.Success) {
            return [pscustomobject]@{ Success=$true; Detail=''; TimedOut=$false }
        }
        $lastDetail = Get-SafeDiagnosticExcerpt $probe.Text 320
        Start-Sleep -Seconds 3
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $lastDetail) { $lastDetail = "WSL distro '$Name' did not respond before the readiness deadline." }
    return [pscustomobject]@{ Success=$false; Detail=$lastDetail; TimedOut=$true }
}

function Get-LatticeValeRunningWslDistros {
    $probe = Invoke-NativeProcessCapture 'wsl.exe' @('--list','--running','--quiet') 15
    if (-not $probe.Success) { return @() }
    $text = ([string]$probe.StdOut).Replace([string][char]0, '')
    return @(($text -split "`r?`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Confirm-LatticeValeGlobalWslRestart([string]$TargetName) {
    $running = @(Get-LatticeValeRunningWslDistros)
    $others = @($running | Where-Object { -not $_.Equals($TargetName, [System.StringComparison]::OrdinalIgnoreCase) })
    if ($others.Count -eq 0) { return $true }
    Write-Warning ("Applying this selected global WSL setting requires 'wsl --shutdown', which will temporarily stop ALL running WSL2 distros. Other running distros: {0}" -f ($others -join ', '))
    if (-not (Read-YesNo 'Continue and temporarily stop all currently running WSL distros so the selected global WSL setting can take effect?' $false)) {
        throw 'Global WSL configuration was not changed because other WSL distros are running and shutdown confirmation was declined. Close or stop those distros when convenient, then rerun LatticeVale and choose Resume / repair.'
    }
    return $true
}

function Get-LatticeValeWslHostRepairHelperPath {
    $releaseRoot = Split-Path -Parent $PSScriptRoot
    return (Join-Path $releaseRoot 'tools\Repair-LatticeVale-WslHost.ps1')
}

function Invoke-LatticeValeWslHostLaunchRecoveryHelper(
    [string]$Name,
    [switch]$ApplyNatFallback
) {
    $helperPath = Get-LatticeValeWslHostRepairHelperPath
    if (-not (Test-Path -LiteralPath $helperPath -PathType Leaf)) {
        Write-Warning "The WSL host-repair helper is missing from this release: $helperPath"
        return 127
    }
    $hostExeName = if ($PSVersionTable.PSEdition -eq 'Core') { 'pwsh.exe' } else { 'powershell.exe' }
    $powershellExe = Join-Path $PSHOME $hostExeName
    if (-not (Test-Path -LiteralPath $powershellExe -PathType Leaf)) {
        $fallback = Get-Command powershell.exe -ErrorAction SilentlyContinue
        if ($fallback) { $powershellExe = [string]$fallback.Source }
    }
    if (-not (Test-Path -LiteralPath $powershellExe -PathType Leaf)) {
        Write-Warning 'A supported PowerShell host could not be located for the bounded WSL host-recovery helper.'
        return 127
    }
    $helperArgs = @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$helperPath,'-DistroName',$Name,'-LaunchRecoveryOnly')
    if ($ApplyNatFallback) { $helperArgs += '-ApplyNatFallback' }
    # Keep helper diagnostics visible without returning them through this function's
    # success-output stream. PowerShell captures every success-stream object from a
    # function, so streaming the child process directly here would turn $exitCode at
    # the caller into an array containing diagnostic text plus the native exit code.
    # Out-Host preserves the console output while leaving this function's sole return
    # value as the scalar native process exit code.
    & $powershellExe @helperArgs | Out-Host
    $helperExitCode = [int]$LASTEXITCODE
    return $helperExitCode
}

function Try-RecoverLatticeValeWslHostLaunch([string]$Name) {
    Write-Step "Bounded WSL launch recovery for '$Name'"
    Write-Info 'LatticeVale will not unregister, import, convert, move, recreate, or edit files inside the distro during this recovery.'

    $runningProbe = Invoke-NativeProcessCapture 'wsl.exe' @('--list','--running','--quiet') 15
    $running = @()
    if ($runningProbe.Success) {
        $runningText = ([string]$runningProbe.StdOut).Replace([string][char]0, '')
        $running = @(($runningText -split "`r?`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    $others = @($running | Where-Object { -not $_.Equals($Name, [System.StringComparison]::OrdinalIgnoreCase) })
    if (-not $runningProbe.Success) {
        $detail = Get-SafeDiagnosticExcerpt $runningProbe.Text 240
        if (-not $detail) { $detail = 'running-distro enumeration did not complete successfully' }
        Write-Warning "WSL could not reliably report which distros are currently running: $detail"
        if (-not (Read-ChoiceExplicit 'Proceed with the global WSL shutdown/restart recovery anyway?' "'wsl --shutdown' stops every running WSL2 distro. LatticeVale cannot prove whether unrelated distros are active during this host-service failure." 'No WSL process is stopped and this installer run remains blocked until the selected distro can launch.' $false $false)) {
            return $false
        }
    } elseif ($others.Count -gt 0) {
        Write-Warning ("Microsoft's first recovery step for E_UNEXPECTED is 'wsl --shutdown', which temporarily stops all running WSL2 distros. Other running distros: {0}" -f ($others -join ', '))
        if (-not (Read-ChoiceExplicit 'Temporarily stop all running WSL distros and try the bounded launch recovery now?' 'The helper first performs only a clean WSL shutdown/restart and re-probes this existing distro.' 'No host setting is changed; this installer run remains blocked until WSL can launch the selected distro.' $false $false)) {
            return $false
        }
    } else {
        Write-Info "No other running WSL distro was detected; trying Microsoft's clean WSL shutdown/restart recovery first."
    }

    $exitCode = Invoke-LatticeValeWslHostLaunchRecoveryHelper $Name
    if ($exitCode -eq 0) { return $true }

    if ($exitCode -eq 20) {
        Write-Warning 'The clean WSL restart did not recover the distro, and the host explicitly uses mirrored WSL networking.'
        if (-not (Read-ChoiceExplicit 'Apply the backed-up NAT compatibility recovery now?' 'Yes backs up %UserProfile%\.wslconfig, changes only [wsl2] networkingMode to nat (the WSL default), restarts WSL, and re-tests the same registered distro. Other .wslconfig settings are preserved.' 'No global WSL setting is changed; the distro and VHDX remain untouched.' $false $false)) {
            return $false
        }
        $exitCode = Invoke-LatticeValeWslHostLaunchRecoveryHelper $Name -ApplyNatFallback
        if ($exitCode -eq 0) { return $true }
    }

    if ($exitCode -eq 10) {
        Write-Warning 'Windows reports that a restart is required before WSL can be validated reliably.'
    } elseif ($exitCode -eq 30) {
        Write-Warning 'The bounded non-destructive recovery did not restore WSL. LatticeVale will not automatically escalate into DISM/Windows-feature repair during a normal install.'
    } elseif ($exitCode -ne 0) {
        Write-Warning "The bounded WSL launch-recovery helper exited with code $exitCode."
    }
    $helperPath = Get-LatticeValeWslHostRepairHelperPath
    Write-Host "    For deeper explicit Windows/WSL host repair, run this release helper from elevated PowerShell:`n    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$helperPath`" -DistroName `"$Name`"" -ForegroundColor Yellow
    return $false
}

function Restart-LatticeValeWslForGlobalConfigChange(
    [string]$Name,
    [int]$ReadyTimeoutSeconds = 180
) {
    Write-Info 'Stopping WSL so the global .wslconfig change can take effect. The Linux stack has already completed its repair/configuration.'
    $shutdown = Invoke-NativeProcessCapture 'wsl.exe' @('--shutdown') 30
    if (-not $shutdown.Success) {
        $detail = Get-SafeDiagnosticExcerpt $shutdown.Text 320
        if ($shutdown.TimedOut) { $detail = 'wsl --shutdown exceeded the 30-second safety timeout.' }
        if (-not $detail) { $detail = "wsl.exe exit code $($shutdown.ExitCode)" }
        throw "WSL could not be shut down cleanly after the .wslconfig change: $detail`nThe Linux stack data was preserved. Restart Windows, then rerun the installer and choose Resume / repair."
    }

    # Microsoft documents wsl --shutdown as the fast path for applying .wslconfig
    # changes. Do not assume the VM is ready two seconds later: networking/HNS can
    # take longer to rebuild, and WSL may transiently reject launches while it does.
    Start-Sleep -Seconds 3
    $ready = Wait-LatticeValeWslResponsive $Name $ReadyTimeoutSeconds
    if (-not $ready.Success) {
        throw "WSL did not become responsive within $ReadyTimeoutSeconds seconds after applying .wslconfig changes. Last WSL response: $($ready.Detail)`nThe Linux stack repair completed before this restart and its data was preserved. Restart Windows, then rerun the installer and choose Resume / repair."
    }

    # The global WSL shutdown stopped Docker and all containers. Use the installer-owned
    # helper created during bootstrap, then confirm that command itself cannot hang forever.
    $start = Invoke-WslDirectCapture $Name 'root' '/usr/local/sbin/hermes-stack-start' @() 900
    if (-not $start.Success) {
        $detail = Get-SafeDiagnosticExcerpt $start.Text 420
        if ($start.TimedOut) { $detail = 'the LatticeVale stack-start helper exceeded its 900-second safety timeout' }
        if (-not $detail) { $detail = 'the LatticeVale stack-start helper failed without diagnostic output' }
        throw "WSL restarted, but the LatticeVale stack could not be restarted cleanly: $detail`nRerun the installer and choose Resume / repair; existing data was preserved."
    }
    return $true
}

function Test-LatticeValeWslPersistence([string]$Name, [int]$ObservationSeconds = 75) {
    # Do not touch the distro during the observation window. The point is to catch
    # the exact failure class where WSL tears down an apparently healthy service
    # instance once the initiating command/session has ended.
    Write-Info "Verifying WSL service persistence for $ObservationSeconds seconds without issuing in-distro commands..."
    Start-Sleep -Seconds $ObservationSeconds
    $probe = Invoke-NativeProcessCapture 'wsl.exe' @('--list','--running','--quiet') 15
    if (-not $probe.Success) { return $false }
    $clean = $probe.Text.Replace([string][char]0,[string]::Empty).Replace([string][char]0xFEFF,[string]::Empty)
    foreach ($line in ($clean -split "`r?`n")) {
        if ($line.Trim().Equals($Name, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Test-LatticeValeLegacyTaskOwnedByCurrentUser([object]$Task, [string]$Name) {
    if (-not $Task) { return $false }
    $currentName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principalId = [string]$Task.Principal.UserId
    if ($principalId -and $currentName -and -not $principalId.Equals($currentName, [System.StringComparison]::OrdinalIgnoreCase)) {
        try {
            $sid = (New-Object System.Security.Principal.NTAccount($principalId)).Translate([System.Security.Principal.SecurityIdentifier]).Value
            $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
            if ($sid -ne $currentSid) { return $false }
        } catch { return $false }
    }
    foreach ($action in @($Task.Actions)) {
        $actionArguments = [string]$action.Arguments
        if ($actionArguments -and $actionArguments.Contains('/usr/local/sbin/hermes-stack-start') -and $actionArguments.Contains($Name)) { return $true }
    }
    return $false
}

function Get-ExistingInstallOptions([string]$Name, [string]$User, [string]$LinuxHome) {
    if (-not $LinuxHome) { return $null }
    $path = "$LinuxHome/hermes-stack/install-options.json"
    $probe = Invoke-WslDirectCapture $Name $User 'cat' @($path)
    if (-not $probe.Success -or [string]::IsNullOrWhiteSpace($probe.Text)) {
        # Recovery metadata is non-secret. Fall back to root so a permissions regression
        # cannot erase the installer's knowledge of an otherwise managed stack.
        $probe = Invoke-WslDirectCapture $Name 'root' 'cat' @($path)
    }
    if ($probe.Success -and -not [string]::IsNullOrWhiteSpace($probe.Text)) {
        try { return ($probe.Text | ConvertFrom-Json) } catch { }
    }

    # v13.16.8 recovery hardening: a truncated/corrupt current options file must never
    # make Resume silently fall through to fresh-install component questions. Recover from
    # either installer-created pre-repair snapshots (installer-config.tar.gz) or ordinary
    # ./manage.sh backup archives (files.tar.gz), newest first. Nothing is written here.
    $stackPath = "$LinuxHome/hermes-stack"
    $stackPathB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($stackPath))
    $script = @'
set -Eeuo pipefail
stack="$(printf '%s' "$1" | base64 -d)"
[[ -d "$stack/backups" ]] || exit 1
while IFS= read -r archive; do
  [[ -n "$archive" ]] || continue
  member="$(tar -tzf "$archive" 2>/dev/null | awk '$0 == "install-options.json" || $0 == "./install-options.json" { print; exit }')"
  [[ -n "$member" ]] || continue
  if candidate="$(tar -xOzf "$archive" "$member" 2>/dev/null)" && [[ -n "$candidate" ]]; then
    if printf '%s' "$candidate" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if isinstance(d,dict) else 1)' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      exit 0
    fi
  fi
done < <(find "$stack/backups" -mindepth 2 -maxdepth 2 -type f \( -name installer-config.tar.gz -o -name files.tar.gz \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | cut -d' ' -f2-)
exit 1
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script))
    $backupProbe = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc', "echo '$encoded' | base64 -d | bash -s -- '$stackPathB64'") 45
    if ($backupProbe.Success -and -not [string]::IsNullOrWhiteSpace($backupProbe.Text)) {
        try {
            $recovered = ($backupProbe.Text | ConvertFrom-Json)
            Write-Warning 'Current install-options.json is unreadable; recovered the newest valid installer options from an existing LatticeVale backup archive.'
            return $recovered
        } catch { }
    }
    return $null
}

function Get-OptionValue([object]$Object, [string]$Name, $Default) {
    if ($null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name]) { return $Object.$Name }
    return $Default
}

function ConvertTo-LatticeValeComparableVersion([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    $match = [regex]::Match($Value.Trim(), '^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?')
    if (-not $match.Success) { return $null }
    $parts = @(0,0,0,0)
    for ($i = 1; $i -le 4; $i++) {
        if ($match.Groups[$i].Success) {
            $parsed = 0
            if (-not [int]::TryParse($match.Groups[$i].Value, [ref]$parsed)) { return $null }
            $parts[$i-1] = $parsed
        }
    }
    try { return [version]("{0}.{1}.{2}.{3}" -f $parts[0],$parts[1],$parts[2],$parts[3]) } catch { return $null }
}

function Get-LatticeValeRepairOriginInfo(
    [string]$Name,
    [string]$User,
    [string]$LinuxHome,
    [object]$Options,
    [string]$BundleVersion,
    [int]$CurrentSchema,
    [int]$MinimumMajor
) {
    $optionVersion = [string](Get-OptionValue $Options 'installerVersion' '')
    $optionSchema = 0
    $schemaValue = Get-OptionValue $Options 'schema' 0
    [void][int]::TryParse([string]$schemaValue, [ref]$optionSchema)

    $stateVersion = ''
    if ($LinuxHome) {
        $statePath = "$LinuxHome/hermes-stack/.installer-state.json"
        $probe = Invoke-WslDirectCapture $Name 'root' 'cat' @($statePath) 15
        if ($probe.Success -and -not [string]::IsNullOrWhiteSpace($probe.Text)) {
            try {
                $state = ($probe.Text | ConvertFrom-Json)
                $stateVersion = [string](Get-OptionValue $state 'installerVersion' '')
            } catch { }
        }
    }

    $bundleComparable = ConvertTo-LatticeValeComparableVersion $BundleVersion
    if ($null -eq $bundleComparable) { throw "Current bundle version '$BundleVersion' is not comparable for repair migration." }
    $knownVersions = @()
    foreach ($candidate in @($optionVersion,$stateVersion)) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $parsed = ConvertTo-LatticeValeComparableVersion $candidate
        if ($null -ne $parsed) { $knownVersions += $parsed }
    }

    $newerThanBundle = $false
    $belowSupportedFloor = $false
    foreach ($parsed in $knownVersions) {
        if ($parsed -gt $bundleComparable) { $newerThanBundle = $true }
        if ($parsed.Major -lt $MinimumMajor) { $belowSupportedFloor = $true }
    }

    # If no comparable version survived, a historical schema can still prove that this
    # is an old managed options format. Schema 0 means the oldest retained formats that
    # predate an explicit schema field; ownership is separately proven before this call.
    $versionKnown = ($knownVersions.Count -gt 0)
    $schemaSupported = ($optionSchema -ge 0 -and $optionSchema -le $CurrentSchema)
    $supported = (-not $newerThanBundle) -and (-not $belowSupportedFloor) -and ($versionKnown -or $schemaSupported)

    $versionMismatch = $false
    if ($versionKnown) {
        foreach ($parsed in $knownVersions) {
            if ($parsed -ne $bundleComparable) { $versionMismatch = $true; break }
        }
    } else { $versionMismatch = $true }
    $schemaMismatch = ($optionSchema -ne $CurrentSchema)
    $metadataMismatch = (-not [string]::IsNullOrWhiteSpace($optionVersion) -and -not [string]::IsNullOrWhiteSpace($stateVersion) -and $optionVersion -ne $stateVersion)
    $needsMigration = $versionMismatch -or $schemaMismatch -or $metadataMismatch

    $origin = if (-not [string]::IsNullOrWhiteSpace($optionVersion)) { $optionVersion } elseif (-not [string]::IsNullOrWhiteSpace($stateVersion)) { $stateVersion } else { 'legacy/unknown' }
    return [pscustomobject]@{
        OriginVersion = $origin
        OptionsVersion = $optionVersion
        StateVersion = $stateVersion
        OriginSchema = $optionSchema
        BundleVersion = $BundleVersion
        CurrentSchema = $CurrentSchema
        MinimumMajor = $MinimumMajor
        VersionKnown = $versionKnown
        Supported = $supported
        NewerThanBundle = $newerThanBundle
        BelowSupportedFloor = $belowSupportedFloor
        MetadataMismatch = $metadataMismatch
        NeedsMigration = $needsMigration
    }
}

function Complete-WorkerMatrixOptions([object[]]$Workers, [bool]$GlobalMatrixEnabled, [bool]$EnableMissingByDefault, [bool]$PromptOnMissing, [bool]$AllowExistingRoomSelection = $false) {
    $result = @()
    foreach ($worker in @($Workers)) {
        if ($null -eq $worker) { continue }
        $name = [string](Get-OptionValue $worker 'name' '')
        $description = [string](Get-OptionValue $worker 'description' 'General-purpose worker')
        $clone = [bool](Get-OptionValue $worker 'clone' $true)
        $matrixExisting = $null
        $hasMatrixSetting = ($null -ne $worker.PSObject.Properties['matrix'])
        if ($hasMatrixSetting) { $matrixExisting = $worker.matrix }

        # Preserve an explicit per-profile Matrix intent even while the shared Matrix
        # service is temporarily disabled. Global Matrix gates provisioning/runtime;
        # it must not erase the saved intent needed to restore the same profile rooms
        # if Matrix is enabled again later through Change installed components.
        $matrixEnabled = if ($hasMatrixSetting) { [bool](Get-OptionValue $matrixExisting 'enabled' $false) } else { $false }
        if ($GlobalMatrixEnabled -and -not $hasMatrixSetting -and $PromptOnMissing) {
            $matrixEnabled = Read-Choice "Give profile '$name' its own Matrix/Element bot and room?" "Creates a separate Matrix identity and profile-local gateway for '$name'. Messages in that room use the model configured for profile '$name'." "Keeps '$name' as a local/Kanban-only profile with no independent Matrix gateway." $EnableMissingByDefault
        }

        # The Matrix localpart deliberately follows the installer-selected profile name.
        # Profile names already satisfy the stricter subset accepted by our Synapse localpart policy.
        $matrixLocalpart = $name
        $matrixRoomMode = 'create'
        $matrixRoomName = "LatticeVale $name"
        $matrixRoomId = ''
        if ($hasMatrixSetting) {
            $savedLocalpart = [string](Get-OptionValue $matrixExisting 'localpart' $name)
            if (-not [string]::IsNullOrWhiteSpace($savedLocalpart)) { $matrixLocalpart = $savedLocalpart.Trim().ToLowerInvariant() }
            $savedMode = [string](Get-OptionValue $matrixExisting 'roomMode' 'create')
            if ($savedMode -in @('create','existing')) { $matrixRoomMode = $savedMode }
            $savedName = [string](Get-OptionValue $matrixExisting 'roomName' $matrixRoomName)
            if (-not [string]::IsNullOrWhiteSpace($savedName)) { $matrixRoomName = $savedName.Trim() }
            $matrixRoomId = [string](Get-OptionValue $matrixExisting 'roomId' '')
        }

        if ($matrixEnabled -and $name -eq 'hermes') {
            throw "Profile 'hermes' cannot receive an independent LatticeVale Matrix identity because the default profile already owns @hermes:hermes.local. Rename this additional profile or leave its Matrix option disabled."
        }

        if ($matrixEnabled -and -not $hasMatrixSetting) {
            $useExisting = $false
            if ($AllowExistingRoomSelection) {
                $useExisting = Read-Choice "Use an existing encrypted Matrix room for '$name'?" "You will enter its room ID. LatticeVale will invite/link the '$name' bot to that room without replacing the room." "LatticeVale creates a new private encrypted room named for profile '$name'." $false
            } else {
                Write-Info "No existing LatticeVale Matrix/Synapse deployment is available yet. LatticeVale will create a new private encrypted room for '$name' after Matrix is installed."
            }
            if ($useExisting) {
                $matrixRoomMode = 'existing'
                while ($true) {
                    $matrixRoomId = (Read-Host "Existing Matrix room ID for '$name' (starts with !)").Trim()
                    if ($matrixRoomId -match '^![^:\s]+:[^\s]+$') { break }
                    Write-Host 'Enter a full Matrix room ID such as !abcdef:hermes.local.' -ForegroundColor Yellow
                }
            } else {
                $matrixRoomMode = 'create'
                $roomInput = Read-Host "Matrix room name for '$name' [suggested: $matrixRoomName; Enter accepts]"
                if (-not [string]::IsNullOrWhiteSpace($roomInput)) { $matrixRoomName = $roomInput.Trim() }
                if ($matrixRoomName.Length -gt 120) { $matrixRoomName = $matrixRoomName.Substring(0,120) }
            }
        }

        $matrixOptions = [pscustomobject]@{
            enabled = $matrixEnabled
            localpart = $matrixLocalpart
            roomMode = $matrixRoomMode
            roomName = $matrixRoomName
            roomId = $matrixRoomId
        }
        $result += [pscustomobject]@{
            name = $name
            description = $description
            clone = $clone
            modelMode = if ($clone) { 'clone-default' } else { 'profile-selected' }
            matrix = $matrixOptions
        }
    }
    return @($result)
}


function Get-RegisteredObsidianVaultPaths {
    $configPath = Join-Path $env:APPDATA 'obsidian\obsidian.json'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { return @() }
    try {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    } catch {
        Write-Warning "Could not parse Obsidian's vault registry at '$configPath'. No vault path will be assumed; enter one explicitly if Obsidian is selected."
        return @()
    }
    $paths = @()
    if ($null -ne $config.vaults) {
        foreach ($prop in @($config.vaults.PSObject.Properties)) {
            $candidate = [string]$prop.Value.path
            if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
            # Native Windows Obsidian is intentionally kept on a Windows-local drive.
            # WSL UNC vaults can fail Electron/Node file watching with EISDIR errors.
            if ($candidate -notmatch '^[A-Za-z]:\\') { continue }
            try { $candidate = [System.IO.Path]::GetFullPath($candidate) } catch { continue }
            if (Test-Path -LiteralPath $candidate -PathType Container) { $paths += $candidate }
        }
    }
    return @($paths | Select-Object -Unique)
}

function Get-DefaultObsidianVaultWindowsPath([object]$ExistingOptions) {
    $saved = [string](Get-OptionValue $ExistingOptions 'obsidianVaultWindowsPath' '')
    if (-not [string]::IsNullOrWhiteSpace($saved) -and $saved -match '^[A-Za-z]:\\') {
        try { return [System.IO.Path]::GetFullPath($saved) } catch { }
    }
    $registered = @(Get-RegisteredObsidianVaultPaths)
    if ($registered.Count -eq 1) {
        Write-Info "Detected one existing Windows Obsidian vault: $($registered[0])"
        return $registered[0]
    }
    if ($registered.Count -gt 1) {
        Write-Info "Detected $($registered.Count) existing Windows Obsidian vaults; no vault is selected automatically."
    }
    return ''
}

function Convert-WindowsLocalPathToWslPath([string]$Name, [string]$User, [string]$WindowsPath) {
    if ([string]::IsNullOrWhiteSpace($WindowsPath) -or $WindowsPath -notmatch '^[A-Za-z]:\\') {
        throw "Obsidian vault path must be a Windows-local drive path such as D:\Documents\Obsidian Vault. Do not use \\wsl.localhost or another UNC/network path."
    }
    $full = [System.IO.Path]::GetFullPath($WindowsPath)
    New-Item -ItemType Directory -Path $full -Force | Out-Null

    # Do not translate the full Windows path with wslpath. When that source path is
    # already participating in a Linux bind mount, WSL can canonicalize it through
    # the active mount and return the bind target (for example ~/hermes-stack/vault)
    # instead of the underlying DrvFs path. Translate only the drive root, which is
    # stable, then append the already-normalized Windows-relative path lexically.
    $driveRootWindows = $full.Substring(0, 2) + '\'
    $rootProbe = Invoke-WslDirectCapture $Name $User 'wslpath' @('-a','-u',$driveRootWindows)
    if (-not $rootProbe.Success) { throw "WSL could not translate Windows drive root '$driveRootWindows' for Obsidian vault '$full'." }
    $linuxRoot = ((($rootProbe.Text -split "`r?`n") | Select-Object -First 1).Trim()).TrimEnd('/')
    # WSL allows the Windows-drive automount root to be customized in /etc/wsl.conf
    # (for example /windir instead of /mnt). Require an absolute translated root,
    # then verify that the final source is actually Windows-backed rather than
    # hard-coding /mnt/<drive> as the only eligible layout.
    if ([string]::IsNullOrWhiteSpace($linuxRoot) -or -not $linuxRoot.StartsWith('/') -or $linuxRoot -eq '/') {
        throw "Windows drive root '$driveRootWindows' did not resolve to a usable absolute WSL path (resolved: '$linuxRoot')."
    }
    $relativeWindows = if ($full.Length -gt 3) { $full.Substring(3) } else { '' }
    $relativeLinux = $relativeWindows.Replace('\', '/')
    $linuxPath = if ([string]::IsNullOrWhiteSpace($relativeLinux)) { $linuxRoot } else { "$linuxRoot/$relativeLinux" }
    $verify = Invoke-WslDirectCapture $Name $User 'test' @('-d', $linuxPath)
    if (-not $verify.Success) { throw "WSL cannot access the Windows Obsidian vault at '$linuxPath'." }
    $fsProbe = Invoke-WslDirectCapture $Name $User 'findmnt' @('-n', '-o', 'FSTYPE', '-T', $linuxPath)
    $fsType = if ($fsProbe.Success) { ((($fsProbe.Text -split "`r?`n") | Select-Object -First 1).Trim()).ToLowerInvariant() } else { '' }
    if ($fsType -notin @('9p','drvfs','fuseblk','ntfs','ntfs3')) {
        $shown = if ($fsType) { $fsType } else { 'unknown' }
        throw "WSL path '$linuxPath' is not verified as a Windows-backed drive path (filesystem: $shown). Keep the Obsidian vault on a local Windows drive and ensure that drive is mounted into WSL."
    }
    return $linuxPath
}

function Repair-LegacyObsidianStackVaultMount(
    [string]$Name,
    [string]$StackPath,
    [string]$ExpectedSourcePath,
    [int]$LinuxUid,
    [int]$LinuxGid
) {
    if ([string]::IsNullOrWhiteSpace($StackPath) -or -not $StackPath.StartsWith('/') -or $StackPath -eq '/') {
        throw "Refusing legacy Obsidian reconciliation because the managed Linux stack path is invalid or empty."
    }
    if ([string]::IsNullOrWhiteSpace($ExpectedSourcePath) -or -not $ExpectedSourcePath.StartsWith('/') -or $ExpectedSourcePath -eq '/') {
        throw "Refusing legacy Obsidian reconciliation because the expected Windows-vault WSL source path is invalid: '$ExpectedSourcePath'."
    }
    if ($LinuxUid -lt 1000 -or $LinuxUid -gt 65534 -or $LinuxGid -lt 1000 -or $LinuxGid -gt 65534) {
        throw "Refusing legacy Obsidian reconciliation because the selected Linux UID:GID is invalid: $LinuxUid`:$LinuxGid."
    }

    $vaultPath = "$($StackPath.TrimEnd('/'))/vault"

    # A historical LatticeVale install may have made this exact managed target either
    # a bind mount or a symlink to the Windows-native Obsidian vault. Never chmod/chown
    # through either object. Detect it first and require explicit consent before
    # detaching the target; source data is never deleted.
    $linkProbe = Invoke-WslDirectCapture $Name 'root' 'test' @('-L', $vaultPath)
    if ($linkProbe.Success) {
        $linkTargetProbe = Invoke-WslDirectCapture $Name 'root' 'readlink' @('-f', '--', $vaultPath)
        $linkTarget = if ($linkTargetProbe.Success) { ((($linkTargetProbe.Text -split "`r?`n") | Select-Object -First 1).Trim()) } else { '<unresolved>' }
        Write-Warning "The installer-owned vault path '$vaultPath' is currently a symbolic link to '$linkTarget'. LatticeVale must restore '$vaultPath' as a normal Linux directory before Docker can mount the selected Windows Obsidian vault safely."
        if (-not (Read-ChoiceExplicit 'Detach this legacy vault symlink?' 'Only the symlink at the installer-owned stack path is removed. The linked source directory and its files are not deleted or modified.' 'Installer stops so you can inspect the link manually.' $true)) {
            throw "The legacy vault symlink was left unchanged at '$vaultPath'."
        }
        $removeLink = Invoke-WslDirectCapture $Name 'root' 'rm' @('--', $vaultPath)
        if (-not $removeLink.Success) {
            $detail = Get-SafeDiagnosticExcerpt $removeLink.Text 500
            throw "Could not remove the legacy vault symlink '$vaultPath'. The linked source was not deleted. $detail"
        }
    }

    $mountProbe = Invoke-WslDirectCapture $Name 'root' 'mountpoint' @('-q', '--', $vaultPath)
    if ($mountProbe.Success) {
        $mountInfoProbe = Invoke-WslDirectCapture $Name 'root' 'findmnt' @('-n', '-o', 'SOURCE,FSTYPE,OPTIONS', '-T', $vaultPath)
        $mountInfo = if ($mountInfoProbe.Success) { Get-SafeDiagnosticExcerpt $mountInfoProbe.Text 600 } else { 'source/filesystem could not be determined' }
        Write-Warning "The installer-owned vault path '$vaultPath' is currently a mountpoint ($mountInfo). LatticeVale will not assume this mount is safe to alter."
        if (-not (Read-ChoiceExplicit 'Detach this existing vault mount from the LatticeVale stack path?' 'Unmounts only the installer-owned target path. The mounted source and its files are not deleted. Exact legacy LatticeVale fstab entries for the selected Windows vault are removed separately.' 'Installer stops and leaves the mount unchanged.' $true)) {
            throw "The existing vault mount was left unchanged at '$vaultPath'."
        }
        $unmount = Invoke-WslDirectCapture $Name 'root' 'umount' @('--', $vaultPath) 30
        if (-not $unmount.Success) {
            $unmount = Invoke-WslDirectCapture $Name 'root' 'umount' @('-l', '--', $vaultPath) 30
        }
        if (-not $unmount.Success) {
            $detail = Get-SafeDiagnosticExcerpt $unmount.Text 600
            if (-not $detail) { $detail = "exit code $($unmount.ExitCode)" }
            throw "Could not detach the vault mount at '$vaultPath'. No source vault data was deleted. Linux detail: $detail"
        }
    }

    # Remove only fstab bind entries whose source AND destination match the selected
    # Windows vault and installer-owned stack vault. Unknown fstab entries are preserved.
    $cleanupShell = @'
set -Eeuo pipefail
target_b64="${1:-}"
source_b64="${2:-}"
[[ -n "$target_b64" && -n "$source_b64" ]] || { echo 'Missing LatticeVale vault source/target.' >&2; exit 2; }
target="$(printf '%s' "$target_b64" | base64 -d)"
source="$(printf '%s' "$source_b64" | base64 -d)"
[[ "$target" == /* ]] || { echo 'LatticeVale vault target is not an absolute Linux path.' >&2; exit 2; }
[[ "$source" == /* && "$source" != / ]] || { echo 'LatticeVale vault source is not an absolute WSL path.' >&2; exit 2; }
source_fs="$(findmnt -n -o FSTYPE -T "$source" 2>/dev/null | head -n1 || true)"
case "${source_fs,,}" in 9p|drvfs|fuseblk|ntfs|ntfs3) ;; *) echo "LatticeVale vault source is not verified as Windows-backed storage (filesystem: ${source_fs:-unknown})." >&2; exit 2;; esac
fstab="${3:-/etc/fstab}"
[[ "$fstab" == /* ]] || { echo 'fstab path must be absolute.' >&2; exit 2; }
[[ -f "$fstab" ]] || exit 0
tmp="$(mktemp)"
count_file="$(mktemp)"
trap 'rm -f "$tmp" "$count_file"' EXIT
awk -v target="$target" -v source="$source" -v count_file="$count_file" '
  /^[[:space:]]*#/ || NF < 4 { print; next }
  {
    src=$1; dest=$2
    gsub(/\\040/, " ", src); gsub(/\\040/, " ", dest)
    bind=0
    n=split($4, opts, ",")
    for (i=1; i<=n; i++) if (opts[i] == "bind") bind=1
    if (src == source && dest == target && bind) { removed++; next }
    print
  }
  END { print removed+0 > count_file }
' "$fstab" > "$tmp"
count="$(cat "$count_file")"
if [[ "$count" -gt 0 ]]; then
  backup="${fstab}.latticevale-v14.1.3.bak"
  [[ -e "$backup" ]] || cp -a -- "$fstab" "$backup"
  chmod --reference="$fstab" "$tmp" 2>/dev/null || true
  chown --reference="$fstab" "$tmp" 2>/dev/null || true
  cat "$tmp" > "$fstab"
  printf 'Removed %s exact legacy LatticeVale vault bind entry/entries from /etc/fstab.\n' "$count"
fi
awk -v target="$target" -v source="$source" '
  /^[[:space:]]*#/ || NF < 4 { next }
  {
    src=$1; dest=$2
    gsub(/\\040/, " ", src); gsub(/\\040/, " ", dest)
    n=split($4, opts, ","); bind=0
    for (i=1; i<=n; i++) if (opts[i] == "bind") bind=1
    if (src == source && dest == target && bind) exit 1
  }
' "$fstab"
'@
    $cleanupB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($cleanupShell))
    $vaultB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($vaultPath))
    $sourceB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ExpectedSourcePath))
    $cleanupRunner = "printf '%s' '$cleanupB64' | base64 -d | bash -s -- '$vaultB64' '$sourceB64'"
    $cleanup = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc', $cleanupRunner) 30
    if (-not $cleanup.Success) {
        $detail = Get-SafeDiagnosticExcerpt $cleanup.Text 700
        if (-not $detail) { $detail = "exit code $($cleanup.ExitCode)" }
        throw "Could not reconcile exact legacy /etc/fstab bind entries for '$vaultPath'. No Windows vault source data was deleted. Linux detail: $detail"
    }
    if (-not [string]::IsNullOrWhiteSpace($cleanup.Text)) { Write-Info $cleanup.Text.Trim() }

    $postMount = Invoke-WslDirectCapture $Name 'root' 'mountpoint' @('-q', '--', $vaultPath)
    $postLink = Invoke-WslDirectCapture $Name 'root' 'test' @('-L', $vaultPath)
    if ($postMount.Success -or $postLink.Success) {
        throw "The installer-owned vault path '$vaultPath' is still an external mount or symlink after reconciliation. No source vault data was deleted."
    }

    # Recreate the managed target with the selected user's real UID/GID. This also fixes
    # interrupted older repairs that left an empty root-owned directory behind.
    $mkdir = Invoke-WslDirectCapture $Name 'root' 'install' @('-d', '-m', '0750', '-o', ([string]$LinuxUid), '-g', ([string]$LinuxGid), '--', $vaultPath)
    if (-not $mkdir.Success) {
        $detail = Get-SafeDiagnosticExcerpt $mkdir.Text 500
        throw "Could not restore the local LatticeVale vault directory '$vaultPath' for UID:GID $LinuxUid`:$LinuxGid. $detail"
    }
}

function Get-OptionTcpPort([object]$Object, [string]$Name, [int]$Default) {
    $raw = Get-OptionValue $Object $Name $Default
    $value = 0
    if ($null -ne $raw -and [int]::TryParse(([string]$raw).Trim(), [ref]$value) -and $value -ge 1 -and $value -le 65535) {
        return $value
    }
    return $Default
}

function Invoke-BundledStackAudit([string]$Name, [string]$User, [string]$LinuxHome, [switch]$Json) {
    $auditSource = Join-Path $PSScriptRoot 'stack\state-audit.py'
    if (-not (Test-Path -LiteralPath $auditSource -PathType Leaf)) { return $null }
    $stageName = "latticevale-audit-$([guid]::NewGuid().ToString('N'))"
    $stageLinux = "/tmp/$stageName"
    $mkdirProbe = Invoke-WslDirectCapture $Name 'root' 'install' @('-d', '-m', '0755', $stageLinux)
    if (-not $mkdirProbe.Success) { return $null }
    try {
        Copy-LocalFileToWslRoot $Name $auditSource "$stageLinux/state-audit.py" '0644'
        $auditArguments = @("$stageLinux/state-audit.py", '--stack', "$LinuxHome/hermes-stack")
        if ($Json) { $auditArguments += '--json' }
        $probe = Invoke-WslDirectCapture $Name $User 'python3' $auditArguments 60
        if (-not $probe.Success -and [string]::IsNullOrWhiteSpace($probe.Text)) { return $null }
        return $probe.Text
    } catch {
        return $null
    } finally {
        [void](Invoke-WslDirectCapture $Name 'root' 'rm' @('-rf', $stageLinux))
    }
}

function Set-InstallerWindowsState([string]$Name, [string]$User, [string]$LinuxHome, [hashtable]$WindowsState) {
    if (-not $LinuxHome -or $null -eq $WindowsState) { return }
    try {
        $payload = $WindowsState | ConvertTo-Json -Depth 6 -Compress
        $code = @'
from pathlib import Path
import json,sys,datetime
p=Path(sys.argv[1]); payload=json.loads(sys.argv[2])
try:
    d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
except Exception:
    d={}
d.setdefault('schema',1)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
d['windows']=payload
d['windows']['verifiedAt']=now
p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
p.chmod(0o600)
log=p.parent/'logs'/'installer-events.jsonl'; log.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
summary={k:(v.get('status') if isinstance(v,dict) else 'UNKNOWN') for k,v in payload.items()}
with log.open('a',encoding='utf-8') as f:
    f.write(json.dumps({'at':now,'stage':'windows','status':'verified','components':summary},separators=(',',':'))+'\n')
log.chmod(0o600)
'@
        $probe = Invoke-WslDirectCapture $Name $User 'python3' @('-c', $code, "$LinuxHome/hermes-stack/.installer-state.json", $payload)
        if (-not $probe.Success) { Write-Warning 'Could not record Windows recovery hints in the installer state file; live state will still be checked on the next run.' }
    } catch {
        Write-Warning "Could not record Windows recovery hints: $($_.Exception.Message)"
    }
}

function ConvertFrom-WslCliOutput([object[]]$OutputLines) {
    # wsl.exe list output can arrive through PowerShell with embedded NUL characters
    # (for example, UTF-16LE bytes decoded as single-byte text). Normalize the entire
    # payload rather than trimming only the ends of each line.
    $text = (($OutputLines | ForEach-Object { [string]$_ }) -join "`n")
    if ([string]::IsNullOrEmpty($text)) { return '' }
    $text = $text.Replace([string][char]0, [string]::Empty)
    $text = $text.Replace([string][char]0xFEFF, [string]::Empty)
    # Remove ANSI control sequences if a future WSL build decorates redirected output.
    $text = [regex]::Replace($text, "`e\[[0-9;?]*[ -/]*[@-~]", '')
    return $text
}


function Get-LatticeValeCompatibility {
    if ($null -ne $script:HermesCompatibility) { return $script:HermesCompatibility }
    $path = Join-Path $PSScriptRoot 'compatibility.conf'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'Installer bundle is incomplete. Missing compatibility.conf.'
    }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $path -ErrorAction Stop) {
        $clean = ([string]$line).Trim()
        if (-not $clean -or $clean.StartsWith('#') -or $clean -notmatch '=') { continue }
        $pair = @($clean -split '=', 2)
        $key = $pair[0].Trim()
        $value = $pair[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            if ($value.Length -ge 2) { $value = $value.Substring(1, $value.Length - 2) }
        }
        if ($key) { $values[$key] = $value }
    }
    foreach ($required in @('SUPPORTED_UBUNTU_VERSIONS','MIN_WINDOWS_BUILD','MIN_HOST_PARTITION_TOTAL_GIB_EXCLUSIVE','MIN_HOST_PARTITION_FREE_GIB','MIN_MANAGED_REPAIR_FREE_GIB','MANAGED_REPAIR_REFRESH_DAYS','MANAGED_REPAIR_REFRESH_REVISION','MIN_UNIVERSAL_REPAIR_MAJOR','INSTALL_OPTIONS_SCHEMA','WSL_PROBE_TIMEOUT_SECONDS')) {
        if (-not $values.ContainsKey($required) -or [string]::IsNullOrWhiteSpace([string]$values[$required])) {
            throw "compatibility.conf is missing required value '$required'."
        }
    }
    $windowsBuild = 0; $totalGiB = 0; $freeGiB = 0; $repairFreeGiB = 0; $repairRefreshDays = 0; $repairRefreshRevision = 0; $universalRepairMajor = 0; $installOptionsSchema = 0; $probeTimeout = 0
    if (-not [int]::TryParse([string]$values['MIN_WINDOWS_BUILD'], [ref]$windowsBuild) -or $windowsBuild -lt 1) { throw 'Invalid MIN_WINDOWS_BUILD in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['MIN_HOST_PARTITION_TOTAL_GIB_EXCLUSIVE'], [ref]$totalGiB) -or $totalGiB -lt 1) { throw 'Invalid MIN_HOST_PARTITION_TOTAL_GIB_EXCLUSIVE in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['MIN_HOST_PARTITION_FREE_GIB'], [ref]$freeGiB) -or $freeGiB -lt 1) { throw 'Invalid MIN_HOST_PARTITION_FREE_GIB in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['MIN_MANAGED_REPAIR_FREE_GIB'], [ref]$repairFreeGiB) -or $repairFreeGiB -lt 1 -or $repairFreeGiB -gt $freeGiB) { throw 'Invalid MIN_MANAGED_REPAIR_FREE_GIB in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['MANAGED_REPAIR_REFRESH_DAYS'], [ref]$repairRefreshDays) -or $repairRefreshDays -lt 1 -or $repairRefreshDays -gt 365) { throw 'Invalid MANAGED_REPAIR_REFRESH_DAYS in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['MANAGED_REPAIR_REFRESH_REVISION'], [ref]$repairRefreshRevision) -or $repairRefreshRevision -lt 1 -or $repairRefreshRevision -gt 1000000) { throw 'Invalid MANAGED_REPAIR_REFRESH_REVISION in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['MIN_UNIVERSAL_REPAIR_MAJOR'], [ref]$universalRepairMajor) -or $universalRepairMajor -lt 0 -or $universalRepairMajor -gt 99) { throw 'Invalid MIN_UNIVERSAL_REPAIR_MAJOR in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['INSTALL_OPTIONS_SCHEMA'], [ref]$installOptionsSchema) -or $installOptionsSchema -lt 1 -or $installOptionsSchema -gt 1000) { throw 'Invalid INSTALL_OPTIONS_SCHEMA in compatibility.conf.' }
    if (-not [int]::TryParse([string]$values['WSL_PROBE_TIMEOUT_SECONDS'], [ref]$probeTimeout) -or $probeTimeout -lt 5 -or $probeTimeout -gt 120) { throw 'Invalid WSL_PROBE_TIMEOUT_SECONDS in compatibility.conf.' }
    $versions = @(([string]$values['SUPPORTED_UBUNTU_VERSIONS'] -split '\s+') | Where-Object { $_ })
    if ($versions.Count -eq 0) { throw 'SUPPORTED_UBUNTU_VERSIONS is empty in compatibility.conf.' }
    $script:HermesCompatibility = [pscustomobject]@{
        SupportedUbuntuVersions = $versions
        MinWindowsBuild = $windowsBuild
        MinHostPartitionTotalGiBExclusive = $totalGiB
        MinHostPartitionFreeGiB = $freeGiB
        MinManagedRepairFreeGiB = $repairFreeGiB
        ManagedRepairRefreshDays = $repairRefreshDays
        ManagedRepairRefreshRevision = $repairRefreshRevision
        MinUniversalRepairMajor = $universalRepairMajor
        InstallOptionsSchema = $installOptionsSchema
        WslProbeTimeoutSeconds = $probeTimeout
    }
    return $script:HermesCompatibility
}

function Get-SupportedUbuntuVersions {
    return @((Get-LatticeValeCompatibility).SupportedUbuntuVersions)
}

function Get-SafeDiagnosticExcerpt([string]$Text, [int]$MaxLength = 220) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return '' }
    $clean = (ConvertFrom-WslCliOutput @($Text)) -replace '[\r\n\t]+', ' '
    $clean = [regex]::Replace($clean, '\s{2,}', ' ').Trim()
    if ($clean.Length -gt $MaxLength) { return ($clean.Substring(0, $MaxLength - 3) + '...') }
    return $clean
}

function ConvertTo-WindowsProcessArgument([string]$Argument) {
    if ($null -eq $Argument -or $Argument.Length -eq 0) { return '""' }
    if ($Argument -notmatch '[\s"]') { return $Argument }
    $builder = [System.Text.StringBuilder]::new()
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

function Invoke-NativeProcessCapture(
    [string]$FilePath,
    [string[]]$Arguments,
    [int]$TimeoutSeconds = 15,
    [string]$StandardInputPath = ''
) {
    $process = $null
    $inputStream = $null
    try {
        $argumentLine = (($Arguments | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
        if (-not [string]::IsNullOrWhiteSpace($StandardInputPath) -and -not (Test-Path -LiteralPath $StandardInputPath -PathType Leaf)) {
            throw "Standard-input file does not exist: $StandardInputPath"
        }

        # Do not use Start-Process -PassThru here. Some PowerShell hosts/versions can
        # return a Process wrapper whose ExitCode is unavailable/null with -NoNewWindow.
        # A Process created directly by System.Diagnostics owns its native handle and
        # exposes a reliable exit code under both Windows PowerShell 5.1 and PowerShell 7.
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $FilePath
        $startInfo.Arguments = $argumentLine
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.RedirectStandardInput = (-not [string]::IsNullOrWhiteSpace($StandardInputPath))

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw "Could not start native process: $FilePath" }

        # Drain both redirected streams concurrently. Waiting for the process before
        # reading them can deadlock when a child fills either OS pipe buffer.
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()

        if (-not [string]::IsNullOrWhiteSpace($StandardInputPath)) {
            $inputStream = [System.IO.File]::OpenRead($StandardInputPath)
            $inputStream.CopyTo($process.StandardInput.BaseStream)
            $process.StandardInput.BaseStream.Flush()
            $process.StandardInput.Close()
            $inputStream.Dispose()
            $inputStream = $null
        }

        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch { }
            try { $process.WaitForExit(2000) | Out-Null } catch { }
            $stdout = if ($stdoutTask.IsCompleted) { [string]$stdoutTask.Result } else { '' }
            $stderr = if ($stderrTask.IsCompleted) { [string]$stderrTask.Result } else { '' }
            $cleanStdOut = ConvertFrom-WslCliOutput @($stdout)
            $cleanStdErr = ConvertFrom-WslCliOutput @($stderr)
            $combined = ConvertFrom-WslCliOutput @($stdout, $stderr)
            return [pscustomobject]@{ Success = $false; ExitCode = -1; TimedOut = $true; Text = $combined; StdOut = $cleanStdOut; StdErr = $cleanStdErr; Arguments = $Arguments }
        }

        # Complete asynchronous stream reads before disposing the process object.
        $process.WaitForExit()
        $stdout = [string]$stdoutTask.Result
        $stderr = [string]$stderrTask.Result
        $cleanStdOut = ConvertFrom-WslCliOutput @($stdout)
        $cleanStdErr = ConvertFrom-WslCliOutput @($stderr)
        $text = ConvertFrom-WslCliOutput @($stdout, $stderr)
        $exitCode = [int]$process.ExitCode
        return [pscustomobject]@{ Success = ($exitCode -eq 0); ExitCode = $exitCode; TimedOut = $false; Text = $text; StdOut = $cleanStdOut; StdErr = $cleanStdErr; Arguments = $Arguments }
    } catch {
        return [pscustomobject]@{ Success = $false; ExitCode = -1; TimedOut = $false; Text = $_.Exception.Message; StdOut = ''; StdErr = $_.Exception.Message; Arguments = $Arguments }
    } finally {
        if ($inputStream) { try { $inputStream.Dispose() } catch { } }
        if ($process) { try { $process.Dispose() } catch { } }
    }
}

function Invoke-NativeProcessPassthrough(
    [string]$FilePath,
    [string[]]$Arguments,
    [int]$TimeoutSeconds = 300
) {
    $process = $null
    try {
        $argumentLine = (($Arguments | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $FilePath
        $startInfo.Arguments = $argumentLine
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw "Could not start native process: $FilePath" }
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch { }
            try { $process.WaitForExit(2000) | Out-Null } catch { }
            return [pscustomobject]@{ Success=$false; ExitCode=-1; TimedOut=$true }
        }
        $process.WaitForExit()
        $exitCode = [int]$process.ExitCode
        return [pscustomobject]@{ Success=($exitCode -eq 0); ExitCode=$exitCode; TimedOut=$false }
    } catch {
        return [pscustomobject]@{ Success=$false; ExitCode=-1; TimedOut=$false }
    } finally {
        if ($process) { try { $process.Dispose() } catch { } }
    }
}

function Copy-LocalFileToWslRoot([string]$Name, [string]$SourcePath, [string]$DestinationLinux, [string]$Mode = '0600') {
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "Required bundle file is missing: $SourcePath"
    }
    if ([string]::IsNullOrWhiteSpace($DestinationLinux) -or -not $DestinationLinux.StartsWith('/')) {
        throw "WSL staging destination must be an absolute Linux path: $DestinationLinux"
    }
    if ($Mode -notmatch '^0[0-7]{3}$') { throw "Invalid Linux file mode '$Mode'." }

    # Stream the exact local file bytes through wsl.exe stdin. Avoid bash -c positional
    # arguments here: Start-Process/native argument reserialization can make nested shell
    # quoting brittle. dd receives the destination as its own argv value, then chmod is
    # applied separately. The enclosing staging directory is root-owned mode 0700, so the
    # file is never exposed to other Linux users while its final mode is being applied.
    $wslCopyArgs = @('-d', $Name, '-u', 'root', '--', 'dd', "of=$DestinationLinux", 'status=none')
    $probe = Invoke-NativeProcessCapture 'wsl.exe' $wslCopyArgs 60 $SourcePath
    if (-not $probe.Success) {
        $detail = Get-SafeDiagnosticExcerpt $probe.Text
        if (-not $detail) { $detail = "wsl.exe exit code $($probe.ExitCode)" }
        throw "Could not stage '$SourcePath' into '$($Name):$DestinationLinux': $detail"
    }

    $chmodProbe = Invoke-WslDirectCapture $Name 'root' 'chmod' @($Mode, $DestinationLinux) 30
    if (-not $chmodProbe.Success) {
        $detail = Get-SafeDiagnosticExcerpt $chmodProbe.Text
        if (-not $detail) { $detail = 'chmod failed after file transfer' }
        throw "Staged '$SourcePath' into '$($Name):$DestinationLinux' but could not apply mode $Mode`: $detail"
    }
}

function Invoke-LatticeValeCleanupMaintenance(
    [string]$Name,
    [string]$StackPath,
    [string[]]$Scopes,
    [string]$DistroStoragePath
) {
    if ([string]::IsNullOrWhiteSpace($Name) -or [string]::IsNullOrWhiteSpace($StackPath) -or $Scopes.Count -eq 0) {
        throw 'Cleanup maintenance requires a selected distro, managed stack path, and at least one explicit cleanup scope.'
    }
    $allowed = @('preupdate-backups','staging','apt-cache','docker-dangling','docker-build-cache','trim-root')
    foreach ($scope in $Scopes) {
        if ($allowed -notcontains $scope) { throw "Unsupported cleanup scope '$scope'." }
    }
    $cleanupScript = Join-Path $PSScriptRoot 'linux\cleanup-storage.sh'
    if (-not (Test-Path -LiteralPath $cleanupScript -PathType Leaf)) {
        throw "Bundle cleanup helper is missing: $cleanupScript"
    }

    $beforeVolume = Get-StorageVolumeForPath $DistroStoragePath
    $vhdCandidates = @()
    try {
        if (Test-Path -LiteralPath $DistroStoragePath -PathType Leaf) {
            if ([IO.Path]::GetExtension($DistroStoragePath) -ieq '.vhdx') { $vhdCandidates = @(Get-Item -LiteralPath $DistroStoragePath -ErrorAction Stop) }
        } elseif (Test-Path -LiteralPath $DistroStoragePath -PathType Container) {
            $vhdCandidates = @(Get-ChildItem -LiteralPath $DistroStoragePath -File -Filter '*.vhdx' -ErrorAction Stop | Sort-Object Length -Descending)
        }
    } catch { $vhdCandidates = @() }
    $beforeVhdBytes = if ($vhdCandidates.Count -gt 0) { [int64]$vhdCandidates[0].Length } else { -1 }

    Write-Host "`nLATTICEVALE CLEANUP / RECLAIM DISK SPACE" -ForegroundColor Cyan
    Write-Info "Cleanup scopes: $($Scopes -join ', ')"
    if ($null -ne $beforeVolume) {
        Write-Info "Host partition before cleanup: $($beforeVolume.Drive) / $([math]::Round($beforeVolume.Free / 1GB,2)) GB free of $([math]::Round($beforeVolume.Size / 1GB,2)) GB."
    }
    if ($beforeVhdBytes -ge 0) {
        Write-Info "WSL VHDX physical file before cleanup: $([math]::Round($beforeVhdBytes / 1GB,2)) GB ($($vhdCandidates[0].FullName))."
    }
    Write-Info 'Option 7 never stops/removes LatticeVale containers, removes Docker volumes/networks/tagged images, deletes configured models/application data, or modifies/moves/resizes the WSL VHDX.'

    $scopeCsv = ($Scopes -join ',')
    $wslArgs = @('-d', $Name, '-u', 'root', '--', 'bash', '-s', '--', $StackPath, $scopeCsv)
    # Stream the bundle-owned helper over stdin instead of copying it into the nearly-full
    # distro. This lets Cleanup remain reachable specifically when host-backed VHDX space is
    # critically constrained and avoids creating installer staging before reclamation.
    $probe = Invoke-NativeProcessCapture 'wsl.exe' $wslArgs 1800 $cleanupScript
    if ($probe.StdOut) { Write-Host $probe.StdOut }
    if ($probe.StdErr) { Write-Host $probe.StdErr -ForegroundColor Yellow }
    if (-not $probe.Success) {
        $detail = Get-SafeDiagnosticExcerpt $probe.Text 900
        if (-not $detail) { $detail = "wsl.exe exit code $($probe.ExitCode)" }
        throw "LatticeVale cleanup stopped without continuing into normal repair/install work: $detail"
    }

    $afterVolume = Get-StorageVolumeForPath $DistroStoragePath
    $afterVhdBytes = -1
    if ($vhdCandidates.Count -gt 0) {
        try { $afterVhdBytes = [int64](Get-Item -LiteralPath $vhdCandidates[0].FullName -ErrorAction Stop).Length } catch { }
    }
    if ($null -ne $afterVolume) {
        Write-Info "Host partition after cleanup: $($afterVolume.Drive) / $([math]::Round($afterVolume.Free / 1GB,2)) GB free of $([math]::Round($afterVolume.Size / 1GB,2)) GB."
        if ($null -ne $beforeVolume) {
            $delta = [int64]$afterVolume.Free - [int64]$beforeVolume.Free
            Write-Info "Host free-space change observed during this run: $([math]::Round($delta / 1GB,2)) GB."
        }
    }
    if ($afterVhdBytes -ge 0) {
        Write-Info "WSL VHDX physical file after cleanup: $([math]::Round($afterVhdBytes / 1GB,2)) GB."
    }
    Write-Info 'If Linux files were deleted but Windows free space did not rise equivalently, the dynamic VHDX retained allocated blocks. Option 7 intentionally leaves host-side VHDX compaction/resizing outside the installer cleanup boundary.'
}

function ConvertFrom-OsReleaseText([string]$Text) {
    $values = @{}
    if ([string]::IsNullOrWhiteSpace($Text)) { return $values }
    foreach ($line in ($Text -split "`r?`n")) {
        $clean = ([string]$line).Trim()
        if (-not $clean -or $clean.StartsWith('#') -or $clean -notmatch '=') { continue }
        $pair = @($clean -split '=', 2)
        if ($pair.Count -ne 2) { continue }
        $key = $pair[0].Trim()
        $value = $pair[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            if ($value.Length -ge 2) { $value = $value.Substring(1, $value.Length - 2) }
        }
        if ($key) { $values[$key] = $value }
    }
    return $values
}

function Test-WslCliRejectedArgumentSeparator([object]$Attempt) {
    if ($null -eq $Attempt -or $Attempt.TimedOut -or $Attempt.ExitCode -eq -1) { return $false }
    $text = (([string]$Attempt.StdOut) + "`n" + ([string]$Attempt.StdErr)).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    # Retry the legacy direct form only when wsl.exe itself rejected the separator.
    # Never retry an ordinary nonzero Linux command: many callers mutate files,
    # mounts, services, or Docker state and a blind second execution is unsafe.
    # Fail closed: an arbitrary Linux command can itself print "invalid option --...".
    # Treat the separator as unsupported only when the diagnostic identifies the WSL
    # CLI/Windows Subsystem for Linux, otherwise retrying could duplicate side effects.
    return [bool]($text -match '(?is)(wsl(?:\.exe)?|windows subsystem for linux).{0,160}(invalid|unknown|unrecognized|unsupported).{0,100}--' -or
                  $text -match '(?is)(invalid|unknown|unrecognized|unsupported).{0,100}--.{0,160}(wsl(?:\.exe)?|windows subsystem for linux)')
}

function Invoke-WslDirectCapture(
    [string]$Name,
    [string]$User,
    [string]$Command,
    [string[]]$CommandArguments = @(),
    [int]$TimeoutSeconds = 0
) {
    if ($TimeoutSeconds -le 0) { $TimeoutSeconds = [int](Get-LatticeValeCompatibility).WslProbeTimeoutSeconds }
    # Direct command execution avoids shell quoting/expansion during prerequisite probes.
    # Use the standard argument separator. A legacy no-separator retry is allowed only
    # when wsl.exe itself explicitly rejects `--`; ordinary Linux command failures are
    # returned immediately so mutating commands are never executed twice accidentally.
    $prefix = @('-d', $Name)
    if (-not [string]::IsNullOrWhiteSpace($User)) { $prefix += @('-u', $User) }
    $standardArgs = [string[]]($prefix + @('--', $Command) + $CommandArguments)
    $attempt = Invoke-NativeProcessCapture 'wsl.exe' $standardArgs $TimeoutSeconds
    if ($attempt.Success) {
        # Machine-readable WSL probes must consume stdout only. WSL itself can emit
        # startup diagnostics (for example an /etc/fstab mount warning) on stderr
        # even when the requested Linux command succeeds. Merging that diagnostic
        # into JSON, os-release, IP, or path output makes valid probe data unparsable.
        return [pscustomobject]@{ Success = $true; ExitCode = 0; TimedOut = $false; Text = $attempt.StdOut; StdOut = $attempt.StdOut; StdErr = $attempt.StdErr; Arguments = $standardArgs }
    }
    if ($attempt.TimedOut) {
        return [pscustomobject]@{ Success = $false; ExitCode = -1; TimedOut = $true; Text = $attempt.Text; StdOut = $attempt.StdOut; StdErr = $attempt.StdErr; Arguments = $standardArgs }
    }
    if (-not (Test-WslCliRejectedArgumentSeparator $attempt)) {
        return [pscustomobject]@{ Success = $false; ExitCode = $attempt.ExitCode; TimedOut = $false; Text = $attempt.Text; StdOut = $attempt.StdOut; StdErr = $attempt.StdErr; Arguments = $standardArgs }
    }

    $legacyArgs = [string[]]($prefix + @($Command) + $CommandArguments)
    $legacy = Invoke-NativeProcessCapture 'wsl.exe' $legacyArgs $TimeoutSeconds
    if ($legacy.Success) {
        return [pscustomobject]@{ Success = $true; ExitCode = 0; TimedOut = $false; Text = $legacy.StdOut; StdOut = $legacy.StdOut; StdErr = $legacy.StdErr; Arguments = $legacyArgs }
    }
    return [pscustomobject]@{ Success = $false; ExitCode = $legacy.ExitCode; TimedOut = $legacy.TimedOut; Text = $legacy.Text; StdOut = $legacy.StdOut; StdErr = $legacy.StdErr; Arguments = $legacyArgs }
}

function Get-WslOsRelease([string]$Name) {
    $result = [ordered]@{
        Success = $false
        Launchable = $false
        TimedOut = $false
        Id = ''
        VersionId = ''
        Codename = ''
        PrettyName = ''
        Source = ''
        Detail = ''
    }

    # A cold WSL2 distro can legitimately need longer than the ordinary probe budget,
    # especially when systemd/Docker services are restored as the distro boots. Treat the
    # first timeout as a slow-start signal, not immediate proof that the distro is broken.
    # The retry is safe because `cat /etc/os-release` is read-only and idempotent; we never
    # automatically terminate the distro or repeat mutating Linux commands here.
    $probeTimeout = [int](Get-LatticeValeCompatibility).WslProbeTimeoutSeconds
    $probe = Invoke-WslDirectCapture $Name 'root' 'cat' @('/etc/os-release') $probeTimeout
    if ($probe.TimedOut) {
        $coldStartRetryTimeout = [int][math]::Min(120, [math]::Max(45, ($probeTimeout * 3)))
        Start-Sleep -Milliseconds 750
        $probe = Invoke-WslDirectCapture $Name 'root' 'cat' @('/etc/os-release') $coldStartRetryTimeout
        if ($probe.TimedOut) {
            $result.TimedOut = $true
            $detail = Get-SafeDiagnosticExcerpt $probe.Text
            $prefix = "distro launch/probe timed out after ${probeTimeout}s plus a ${coldStartRetryTimeout}s cold-start retry"
            $result.Detail = if ($detail) { "$prefix; WSL output: $detail" } else { $prefix }
            return [pscustomobject]$result
        }
    }
    if ($probe.Success) { $result.Launchable = $true }
    if ($probe.Success -and -not [string]::IsNullOrWhiteSpace($probe.Text)) {
        $values = ConvertFrom-OsReleaseText $probe.Text
        $id = if ($values.ContainsKey('ID')) { [string]$values['ID'] } else { '' }
        $versionId = if ($values.ContainsKey('VERSION_ID')) { [string]$values['VERSION_ID'] } else { '' }
        $codename = if ($values.ContainsKey('UBUNTU_CODENAME')) { [string]$values['UBUNTU_CODENAME'] } elseif ($values.ContainsKey('VERSION_CODENAME')) { [string]$values['VERSION_CODENAME'] } else { '' }
        $pretty = if ($values.ContainsKey('PRETTY_NAME')) { [string]$values['PRETTY_NAME'] } elseif ($values.ContainsKey('NAME')) { [string]$values['NAME'] } else { '' }
        if ($id) {
            $result.Success = $true
            $result.Id = $id.Trim().ToLowerInvariant()
            $result.VersionId = $versionId.Trim()
            $result.Codename = $codename.Trim()
            $result.PrettyName = $pretty.Trim()
            $result.Source = '/etc/os-release'
            return [pscustomobject]$result
        }
    }

    # If cat failed, distinguish an actually broken distro from a launchable distro whose
    # os-release file is unexpectedly missing before trying the Ubuntu lsb-release fallback.
    $launchProbe = $null
    if (-not $probe.Success) {
        $launchProbe = Invoke-WslDirectCapture $Name 'root' 'true' @()
        if ($launchProbe.TimedOut) {
            $result.TimedOut = $true
            $detail = Get-SafeDiagnosticExcerpt $launchProbe.Text
            $result.Detail = if ($detail) { "distro launch check timed out; WSL output: $detail" } else { 'distro launch check timed out' }
            return [pscustomobject]$result
        }
        if ($launchProbe.Success) { $result.Launchable = $true }
    }

    # Ubuntu also ships /etc/lsb-release. Use it only when the distro itself is known
    # launchable but os-release could not be parsed/read.
    if ($result.Launchable) {
        $fallback = Invoke-WslDirectCapture $Name 'root' 'cat' @('/etc/lsb-release')
    } else {
        $fallback = [pscustomobject]@{ Success = $false; ExitCode = $probe.ExitCode; TimedOut = $false; Text = $probe.Text }
    }
    if ($fallback.TimedOut) {
        $result.TimedOut = $true
        $detail = Get-SafeDiagnosticExcerpt $fallback.Text
        $result.Detail = if ($detail) { "distro fallback probe timed out; WSL output: $detail" } else { 'distro fallback probe timed out' }
        return [pscustomobject]$result
    }
    if ($fallback.Success) { $result.Launchable = $true }
    if ($fallback.Success -and -not [string]::IsNullOrWhiteSpace($fallback.Text)) {
        $values = ConvertFrom-OsReleaseText $fallback.Text
        $distId = if ($values.ContainsKey('DISTRIB_ID')) { [string]$values['DISTRIB_ID'] } else { '' }
        $release = if ($values.ContainsKey('DISTRIB_RELEASE')) { [string]$values['DISTRIB_RELEASE'] } else { '' }
        $codename = if ($values.ContainsKey('DISTRIB_CODENAME')) { [string]$values['DISTRIB_CODENAME'] } else { '' }
        $description = if ($values.ContainsKey('DISTRIB_DESCRIPTION')) { [string]$values['DISTRIB_DESCRIPTION'] } else { '' }
        if ($distId) {
            $result.Success = $true
            $result.Id = $distId.Trim().ToLowerInvariant()
            $result.VersionId = $release.Trim()
            $result.Codename = $codename.Trim()
            $result.PrettyName = $description.Trim()
            $result.Source = '/etc/lsb-release'
            return [pscustomobject]$result
        }
    }

    $detailParts = @()
    if (-not $probe.Success) {
        $probeText = Get-SafeDiagnosticExcerpt $probe.Text
        $detailParts += if ($probeText) { "os-release probe failed (exit $($probe.ExitCode)): $probeText" } else { "os-release probe failed (exit $($probe.ExitCode))" }
        if ($null -ne $launchProbe -and -not $launchProbe.Success) {
            $launchText = Get-SafeDiagnosticExcerpt $launchProbe.Text
            if ($launchText) { $detailParts += "distro launch failed (exit $($launchProbe.ExitCode)): $launchText" }
        }
    } elseif ([string]::IsNullOrWhiteSpace($probe.Text)) { $detailParts += 'os-release returned empty output' }
    else { $detailParts += 'os-release did not contain ID' }
    if ($probe.Success) {
        if (-not $fallback.Success) {
            $fallbackText = Get-SafeDiagnosticExcerpt $fallback.Text
            $detailParts += if ($fallbackText) { "lsb-release probe failed (exit $($fallback.ExitCode)): $fallbackText" } else { "lsb-release probe failed (exit $($fallback.ExitCode))" }
        } elseif ([string]::IsNullOrWhiteSpace($fallback.Text)) { $detailParts += 'lsb-release returned empty output' }
        else { $detailParts += 'lsb-release did not contain DISTRIB_ID' }
    }
    $result.Detail = ($detailParts -join '; ')
    return [pscustomobject]$result
}

function Get-LinuxFilesystemInfo([string]$Name) {
    $result = [ordered]@{ Success = $false; TotalBytes = [int64]0; FreeBytes = [int64]0; Mount = '/'; Detail = '' }
    $probe = Invoke-WslDirectCapture $Name 'root' 'df' @('-Pk', '/')
    if (-not $probe.Success) {
        $detail = Get-SafeDiagnosticExcerpt $probe.Text
        $result.Detail = if ($probe.TimedOut) { 'df probe timed out' } elseif ($detail) { "df probe failed (exit $($probe.ExitCode)): $detail" } else { "df probe failed (exit $($probe.ExitCode))" }
        return [pscustomobject]$result
    }
    $lines = @($probe.Text -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    foreach ($line in $lines) {
        if ($line -match '^\S+\s+(\d+)\s+\d+\s+(\d+)\s+\d+%\s+(.+)$') {
            $result.Success = $true
            $result.TotalBytes = [int64]$Matches[1] * 1024
            $result.FreeBytes = [int64]$Matches[2] * 1024
            $result.Mount = $Matches[3].Trim()
            return [pscustomobject]$result
        }
    }
    $result.Detail = 'df returned output that could not be parsed'
    return [pscustomobject]$result
}

function Get-DistroWslVersionFromKernel([string]$Name) {
    $timeout = [int](Get-LatticeValeCompatibility).WslProbeTimeoutSeconds
    $probe = Invoke-NativeProcessCapture 'wsl.exe' @('-d', $Name, '--', 'uname', '-r') $timeout
    if (-not $probe.Success) { return $null }
    $kernel = $probe.StdOut.Trim()
    if ($kernel -match '(?i)WSL2') { return 2 }
    if ($kernel -match '(?i)Microsoft') { return 1 }
    return $null
}

function Get-DistroWslVersion([string]$Name) {
    # Microsoft documents `wsl --list --verbose` as the authoritative WSL1/WSL2 view.
    # Parse from the right edge so localized STATE text does not matter, and normalize
    # embedded NUL/BOM characters before applying the regex.
    $escaped = [regex]::Escape($Name)
    $timeout = [int](Get-LatticeValeCompatibility).WslProbeTimeoutSeconds
    $probe = Invoke-NativeProcessCapture 'wsl.exe' @('--list', '--verbose') $timeout
    if ($probe.Success) {
        foreach ($line in ($probe.StdOut -split "`r?`n")) {
            $clean = $line.Trim()
            if (-not $clean) { continue }
            if ($clean -match "^\*?\s*$escaped(?:\s+.*?)?\s+([12])\s*$") { return [int]$Matches[1] }
        }
    }

    # Defensive fallback for WSL versions/encodings whose table output cannot be parsed.
    $kernelVersion = Get-DistroWslVersionFromKernel $Name
    if ($kernelVersion -eq 2) {
        Write-Info "The WSL CLI table could not identify '$Name'; WSL2 was confirmed through the kernel fallback check."
        return 2
    }
    if ($kernelVersion -eq 1) {
        Write-Info "The WSL CLI table could not identify '$Name'; WSL1 was confirmed through the kernel fallback check."
        return 1
    }
    return $null
}

function Get-WindowsOptionalFeatureStateSafe([string]$FeatureName) {
    try {
        $feature = Get-WindowsOptionalFeature -Online -FeatureName $FeatureName -ErrorAction Stop
        return [string]$feature.State
    } catch {
        return ''
    }
}

function Get-WslCapabilities {
    Write-Step 'Checking required WSL installation'
    Write-Info 'PREREQUISITE: WSL and an existing Ubuntu distribution must already be installed and working.'
    Write-Info 'This installer never installs, updates, imports, unregisters, converts, or repairs WSL distributions.'

    $wslCommand = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wslCommand) {
        throw 'WSL is not installed. Install WSL and an Ubuntu distribution first, verify that "wsl --list --verbose" works, then rerun this installer.'
    }

    # Windows optional-feature state is useful diagnostic context, but modern Store/MSI
    # WSL2 can be installed independently of the legacy/inbox WSL component used for
    # WSL1 support. Do not reject a working modern WSL2 installation solely because
    # Get-WindowsOptionalFeature reports Microsoft-Windows-Subsystem-Linux=Disabled.
    # Functional WSL CLI and distro-launch probes below are authoritative for this installer.
    $wslFeatureState = Get-WindowsOptionalFeatureStateSafe 'Microsoft-Windows-Subsystem-Linux'
    $vmPlatformState = Get-WindowsOptionalFeatureStateSafe 'VirtualMachinePlatform'

    $probeTimeout = [int](Get-LatticeValeCompatibility).WslProbeTimeoutSeconds
    $versionText = ''
    $versionProbe = Invoke-NativeProcessCapture 'wsl.exe' @('--version') $probeTimeout
    $modern = $versionProbe.Success
    if ($modern) { $versionText = $versionProbe.StdOut.Trim() }

    if ($wslFeatureState -and $wslFeatureState -ne 'Enabled') {
        if ($modern) {
            Write-Info "Windows Subsystem for Linux optional feature reports '$wslFeatureState'. Modern Store/MSI WSL was detected, so this legacy/inbox feature state is advisory for WSL2; continuing with functional distro checks."
        } else {
            Write-Warning "Windows Subsystem for Linux optional feature reports '$wslFeatureState'. Continuing to functional WSL/distro checks instead of treating feature-state metadata alone as authoritative."
        }
    }
    if ($vmPlatformState -and $vmPlatformState -ne 'Enabled') {
        Write-Warning "Virtual Machine Platform reports '$vmPlatformState'. WSL2 normally depends on Virtual Machine Platform, but LatticeVale will let the bounded WSL2/distro launch checks determine whether the current host is actually usable."
    }

    $listProbe = Invoke-NativeProcessCapture 'wsl.exe' @('--list', '--quiet') $probeTimeout
    # Successful WSL commands may still emit update/startup notices on STDERR. Only
    # STDOUT contains distro names; mixing the streams can create phantom distro names
    # on localized, Store/MSI, preview, or newly-updated WSL installations.
    $listText = $listProbe.StdOut.Trim()
    if (-not $listProbe.Success) {
        $detailText = Get-SafeDiagnosticExcerpt $listProbe.Text
        $detail = if ($listProbe.TimedOut) { " The WSL enumeration timed out after $probeTimeout seconds." } elseif ($detailText) { " WSL reported: $detailText" } else { '' }
        throw "WSL is present but installed distributions could not be enumerated with 'wsl --list --quiet'.$detail Repair WSL outside this installer and rerun."
    }

    $distroNames = @($listText -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($distroNames.Count -eq 0) {
        throw 'WSL is installed, but no Linux distribution is registered. Install a supported Ubuntu distribution first; this installer does not create or import one.'
    }

    if ($modern) {
        $displayVersion = if ($versionText) { ($versionText -split "`r?`n" | Select-Object -First 1) } else { 'version available' }
        Write-Info "Detected Store/MSIX WSL ($displayVersion)."
    } else {
        Write-Info 'Detected legacy/inbox-compatible WSL. The installer does not require the newer wsl --version command.'
    }
    Write-Info "Installed WSL distributions detected: $($distroNames.Count)"

    return [pscustomobject]@{
        Modern = $modern
        VersionText = $versionText
        DistroNames = $distroNames
        WindowsSubsystemForLinuxState = $wslFeatureState
        VirtualMachinePlatformState = $vmPlatformState
    }
}

function Get-DistroRegistrationInfo([string]$Name) {
    $root = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
    if (-not (Test-Path -LiteralPath $root)) { return $null }
    try {
        foreach ($key in Get-ChildItem -LiteralPath $root -ErrorAction Stop) {
            $item = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction Stop
            if (([string]$item.DistributionName) -ieq $Name) {
                $basePath = [Environment]::ExpandEnvironmentVariables([string]$item.BasePath)
                # Normalize extended drive-letter paths (\\?\G:\...) while preserving
                # volume-GUID paths (\\?\Volume{...}\...), which are valid local storage
                # locations and must not be converted into a broken relative path.
                if ($basePath -match '^\\\\\?\\(?<drive>[A-Za-z]:\\.*)$') { $basePath = $Matches['drive'] }
                return [pscustomobject]@{
                    DistributionName = [string]$item.DistributionName
                    BasePath = $basePath
                    Flags = $item.Flags
                }
            }
        }
    } catch {
        return $null
    }
    return $null
}

function Get-LocalFixedVolumes {
    $items = @()
    foreach ($disk in @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction Stop)) {
        if (-not $disk.DeviceID -or $null -eq $disk.Size -or $null -eq $disk.FreeSpace) { continue }
        $items += [pscustomobject]@{
            Drive = ([string]$disk.DeviceID).ToUpperInvariant()
            Root = (([string]$disk.DeviceID).ToUpperInvariant() + '\')
            FileSystem = [string]$disk.FileSystem
            Size = [int64]$disk.Size
            Free = [int64]$disk.FreeSpace
        }
    }
    return $items
}

function Get-StorageVolumeForPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)

    # Prefer the Storage module when available. Unlike Win32_LogicalDisk drive-letter
    # matching, Get-Volume -FilePath can resolve local fixed volumes mounted into a
    # directory and extended volume-GUID paths used by some custom WSL installations.
    $getVolume = Get-Command Get-Volume -ErrorAction SilentlyContinue
    if ($getVolume) {
        try {
            $volume = Get-Volume -FilePath $expanded -ErrorAction Stop | Select-Object -First 1
            if ($null -ne $volume -and [string]$volume.DriveType -eq 'Fixed' -and
                $null -ne $volume.Size -and $null -ne $volume.SizeRemaining) {
                $display = 'local fixed volume'
                if ($volume.DriveLetter) { $display = (([string]$volume.DriveLetter).ToUpperInvariant() + ':') }
                elseif ($volume.Path) { $display = ([string]$volume.Path).TrimEnd('\') }
                return [pscustomobject]@{
                    Drive = $display
                    Root = [string]$volume.Path
                    FileSystem = [string]$volume.FileSystem
                    Size = [int64]$volume.Size
                    Free = [int64]$volume.SizeRemaining
                }
            }
        } catch { }
    }

    # Windows 10/older PowerShell fallback for ordinary drive-letter installations.
    try { $full = [System.IO.Path]::GetFullPath($expanded) } catch { return $null }
    if ($full.StartsWith('\\')) { return $null }
    $root = [System.IO.Path]::GetPathRoot($full)
    if (-not $root) { return $null }
    $drive = $root.TrimEnd('\').ToUpperInvariant()
    return @(Get-LocalFixedVolumes | Where-Object { $_.Drive -eq $drive } | Select-Object -First 1)[0]
}

function Assert-LatticeValeStorageVolume([string]$Path, [switch]$AllowManagedRepair, [switch]$AllowManagedCleanup) {
    $volume = Get-StorageVolumeForPath $Path
    if ($null -eq $volume) {
        throw 'The selected WSL storage must be on a resolvable local fixed Windows volume; network and removable locations are not supported.'
    }
    $compat = Get-LatticeValeCompatibility
    $minimumTotal = [int64]$compat.MinHostPartitionTotalGiBExclusive * 1GB
    $minimumFree = [int64]$compat.MinHostPartitionFreeGiB * 1GB
    # A fresh install needs the full free-space reserve. Once Hermes is already
    # installed, that same rule would make repair impossible simply because the
    # installed images/models consumed space. Managed repair therefore has a
    # smaller safety floor while preserving the original fresh-install policy.
    $managedRepairMinimumFree = [int64]$compat.MinManagedRepairFreeGiB * 1GB
    if ($volume.Size -le $minimumTotal) {
        if ($AllowManagedCleanup) {
            Write-Warning "Partition $($volume.Drive) is only $([math]::Round($volume.Size / 1GB, 1)) GB total, below the supported fresh-install capacity. A recognized managed stack may still enter Verify or Cleanup so space can be inspected/reclaimed without mutating the live installation."
        } else {
            throw "Partition $($volume.Drive) is only $([math]::Round($volume.Size / 1GB, 1)) GB. The partition hosting the selected Ubuntu WSL2 distro must be OVER $($compat.MinHostPartitionTotalGiBExclusive) GB total capacity."
        }
    }
    if ($volume.Free -lt $minimumFree) {
        if ($AllowManagedRepair -and $volume.Free -ge $managedRepairMinimumFree) {
            Write-Warning "Partition $($volume.Drive) has $([math]::Round($volume.Free / 1GB, 1)) GB free, below the $($compat.MinHostPartitionFreeGiB) GB fresh-install reserve. An existing installer-managed LatticeVale stack was detected, so Resume / repair is allowed with at least $($compat.MinManagedRepairFreeGiB) GB free."
        } elseif ($AllowManagedCleanup) {
            Write-Warning "Partition $($volume.Drive) has only $([math]::Round($volume.Free / 1GB, 1)) GB free, below the $($compat.MinManagedRepairFreeGiB) GB managed-repair floor. Verify and Cleanup remain available; mutating repair/update modes stay blocked until cleanup restores the repair reserve."
        } else {
            $suffix = if ($AllowManagedRepair) { " Managed repair requires at least $($compat.MinManagedRepairFreeGiB) GB free." } else { '' }
            throw "Partition $($volume.Drive) has only $([math]::Round($volume.Free / 1GB, 1)) GB free. A fresh install requires at least $($compat.MinHostPartitionFreeGiB) GB free.$suffix"
        }
    }
    return $volume
}

function Add-DistroBlocker([System.Collections.IDictionary]$Result, [string]$Code, [string]$Message) {
    $Result.BlockerCodes += $Code
    $Result.Blockers += $Message
}

function Add-DistroWarning([System.Collections.IDictionary]$Result, [string]$Message) {
    $Result.Warnings += $Message
}

function Get-UbuntuDistroInfo([string]$Name) {
    $compat = Get-LatticeValeCompatibility
    $result = [ordered]@{
        Name = $Name
        WslVersion = $null
        WslStatus = 'UNKNOWN'
        LaunchStatus = 'UNKNOWN'
        UbuntuStatus = 'UNKNOWN'
        UbuntuVersion = ''
        Codename = ''
        OsPrettyName = ''
        LinuxArchitecture = ''
        ArchitectureStatus = 'UNKNOWN'
        OsDetail = ''
        Registration = $null
        StorageVolume = $null
        StorageStatus = 'UNKNOWN'
        LinuxFilesystem = $null
        LinuxFilesystemStatus = 'UNKNOWN'
        NormalUsers = @()
        UserStatus = 'UNKNOWN'
        Eligible = $false
        BlockerCodes = @()
        Blockers = @()
        Warnings = @()
        ManagedStackOwners = @()
        ManagedRepairEligible = $false
        ManagedCleanupEligible = $false
        LegacyInstallerArtifact = ($Name -like 'Hermes-Ubuntu-*')
    }

    # Do not stop at the first failure. Gather every diagnostic that can be obtained safely.
    $wslVersion = Get-DistroWslVersion $Name
    $result.WslVersion = $wslVersion
    if ($null -eq $wslVersion) {
        $result.WslStatus = 'UNKNOWN'
        Add-DistroBlocker $result 'WSL_VERSION_UNKNOWN' 'WSL version could not be determined'
    } elseif ($wslVersion -ne 2) {
        $result.WslStatus = "WSL$wslVersion"
        Add-DistroBlocker $result 'WSL1' "WSL$wslVersion detected; WSL2 is required"
    } else {
        $result.WslStatus = 'WSL2'
    }

    $osRelease = Get-WslOsRelease $Name
    $result.OsDetail = $osRelease.Detail
    if ($osRelease.Launchable) { $result.LaunchStatus = 'OK' }
    elseif ($osRelease.TimedOut) {
        $result.LaunchStatus = 'UNRESPONSIVE'
        Add-DistroBlocker $result 'UNRESPONSIVE' $(if ($osRelease.Detail) { $osRelease.Detail } else { 'distro did not respond before the WSL probe timeout' })
    } else {
        $result.LaunchStatus = 'FAILED'
        $launchDetail = if ($osRelease.Detail) { $osRelease.Detail } else { 'distro could not be launched/read' }
        if ($launchDetail -match '(?i)(Wsl/Service(?:/CreateInstance(?:/CreateVm)?)?/E_UNEXPECTED|Wsl/Service/E_UNEXPECTED|Catastrophic failure)') {
            Add-DistroBlocker $result 'WSL_HOST_E_UNEXPECTED' "WSL itself failed while launching the registered distro: $launchDetail. If no eligible distro remains, the current LatticeVale release can offer a bounded in-run recovery: clean WSL shutdown/restart first, then an explicit backed-up NAT fallback only when persistent E_UNEXPECTED coincides with user-configured mirrored networking. Distro registration and the VHDX are preserved."
        } else {
            Add-DistroBlocker $result 'UNLAUNCHABLE' $launchDetail
        }
    }

    if ($result.LaunchStatus -eq 'OK') {
        $archProbe = Invoke-WslDirectCapture $Name 'root' 'dpkg' @('--print-architecture')
        if ($archProbe.Success) {
            $result.LinuxArchitecture = (($archProbe.Text -split "`r?`n") | Select-Object -First 1).Trim().ToLowerInvariant()
            if ($result.LinuxArchitecture -eq 'amd64') {
                $result.ArchitectureStatus = 'OK'
            } else {
                $result.ArchitectureStatus = 'UNSUPPORTED'
                Add-DistroBlocker $result 'UNSUPPORTED_ARCHITECTURE' "Ubuntu architecture '$($result.LinuxArchitecture)' is not supported by this x64-only bundle"
            }
        } else {
            $result.ArchitectureStatus = 'UNKNOWN'
            Add-DistroBlocker $result 'ARCHITECTURE_UNKNOWN' 'Ubuntu package architecture could not be verified with dpkg --print-architecture'
        }
    }

    if ($osRelease.Success) {
        $result.OsPrettyName = $osRelease.PrettyName
        if ($osRelease.Id -ne 'ubuntu') {
            $result.UbuntuStatus = 'NOT_UBUNTU'
            $detected = if ($osRelease.Id) { $osRelease.Id } else { 'unknown' }
            Add-DistroBlocker $result 'NOT_UBUNTU' "not Ubuntu (detected $detected)"
        } else {
            $result.UbuntuVersion = $osRelease.VersionId
            $result.Codename = $osRelease.Codename
            if (@($compat.SupportedUbuntuVersions) -notcontains $result.UbuntuVersion) {
                $result.UbuntuStatus = 'UNSUPPORTED_RELEASE'
                Add-DistroBlocker $result 'UNSUPPORTED_UBUNTU' "Ubuntu $($result.UbuntuVersion) is not in Docker's currently supported Ubuntu set ($(@($compat.SupportedUbuntuVersions) -join '/'))"
            } else {
                $result.UbuntuStatus = 'SUPPORTED'
            }
        }
    } elseif ($result.LaunchStatus -eq 'OK') {
        $result.UbuntuStatus = 'UNKNOWN'
        Add-DistroBlocker $result 'OS_IDENTITY_UNKNOWN' $(if ($osRelease.Detail) { "distro launched but OS identity could not be determined: $($osRelease.Detail)" } else { 'distro launched but OS identity could not be determined' })
    }

    # Registration/host-storage diagnostics do not require launching Linux, so gather them
    # even for broken legacy distros.
    $registration = Get-DistroRegistrationInfo $Name
    $result.Registration = $registration
    if ($null -eq $registration -or [string]::IsNullOrWhiteSpace($registration.BasePath)) {
        $result.StorageStatus = 'UNKNOWN'
        Add-DistroBlocker $result 'STORAGE_PATH_UNKNOWN' 'registered WSL storage path could not be verified'
    } else {
        $volume = Get-StorageVolumeForPath $registration.BasePath
        $result.StorageVolume = $volume
        if ($null -eq $volume) {
            $result.StorageStatus = 'UNSUPPORTED_LOCATION'
            Add-DistroBlocker $result 'STORAGE_LOCATION_UNSUPPORTED' 'distro storage is not on a verifiable local fixed partition'
        } else {
            $storageBlocked = $false
            $minTotalBytes = [int64]$compat.MinHostPartitionTotalGiBExclusive * 1GB
            $minFreeBytes = [int64]$compat.MinHostPartitionFreeGiB * 1GB
            if ($volume.Size -le $minTotalBytes) {
                Add-DistroBlocker $result 'STORAGE_TOTAL_LOW' "host partition $($volume.Drive) is $([math]::Round($volume.Size / 1GB,1)) GB total; it must be over $($compat.MinHostPartitionTotalGiBExclusive) GB"
                $storageBlocked = $true
            }
            $storageDeferred = $false
            if ($volume.Free -lt $minFreeBytes) {
                if ($result.LaunchStatus -eq 'OK') {
                    # Once Linux is responsive we can determine whether this is a fresh install
                    # or an existing managed stack. The managed-repair exception below can then
                    # replace this fresh-install blocker with the lower repair threshold.
                    Add-DistroBlocker $result 'STORAGE_FREE_LOW' "host partition $($volume.Drive) has $([math]::Round($volume.Free / 1GB,1)) GB free; at least $($compat.MinHostPartitionFreeGiB) GB is required for a fresh install"
                    $storageBlocked = $true
                } else {
                    # Do not mislabel a potentially valid repair as storage-blocked merely because
                    # WSL was too slow to launch and we therefore could not inspect ~/hermes-stack.
                    # The distro is already ineligible due to its launch blocker; storage is
                    # re-evaluated after Linux becomes responsive on the next run.
                    $storageDeferred = $true
                    Add-DistroWarning $result "Host partition $($volume.Drive) has $([math]::Round($volume.Free / 1GB,1)) GB free, below the $($compat.MinHostPartitionFreeGiB) GB fresh-install reserve. Managed-repair eligibility (minimum $($compat.MinManagedRepairFreeGiB) GB) will be evaluated once the distro responds."
                }
            }
            $result.StorageStatus = if ($storageBlocked) { 'BLOCKED' } elseif ($storageDeferred) { 'DEFERRED' } else { 'OK' }
        }
    }

    # Linux-side VHD/root-filesystem capacity is useful diagnostic context. It is not a
    # substitute for host-partition free space, and it is intentionally not a separate
    # hard policy beyond the user's host-storage prerequisite.
    if ($result.LaunchStatus -eq 'OK') {
        $linuxFs = Get-LinuxFilesystemInfo $Name
        $result.LinuxFilesystem = $linuxFs
        if ($linuxFs.Success) {
            $result.LinuxFilesystemStatus = 'OK'
            if ($linuxFs.FreeBytes -lt ([int64]$compat.MinHostPartitionFreeGiB * 1GB)) {
                Add-DistroWarning $result "Linux root filesystem reports only $([math]::Round($linuxFs.FreeBytes / 1GB,1)) GB available even though host storage is checked separately"
                $result.LinuxFilesystemStatus = 'LOW'
            }
        } else {
            $result.LinuxFilesystemStatus = 'UNKNOWN'
            if ($linuxFs.Detail) { Add-DistroWarning $result "Linux filesystem capacity could not be read: $($linuxFs.Detail)" }
        }

        $usersProbe = Get-ExistingLinuxUsers $Name -ReturnProbe
        if ($usersProbe.Success) {
            $result.NormalUsers = @($usersProbe.Users)
            if ($result.NormalUsers.Count -eq 0) {
                $result.UserStatus = 'NONE'
                Add-DistroBlocker $result 'NO_NORMAL_USER' 'no existing Hermes-compatible Ubuntu user was found (UID and primary GID must both be 1000-65534)'
            } else {
                $result.UserStatus = 'OK'
            }
        } else {
            $result.UserStatus = 'UNKNOWN'
            $detail = if ($usersProbe.Detail) { $usersProbe.Detail } else { 'existing users could not be enumerated' }
            Add-DistroBlocker $result 'USER_PROBE_FAILED' $detail
        }
    }

    # Recovery exception for an already-managed stack. Fresh installs still need
    # MIN_HOST_PARTITION_FREE_GIB. A managed stack may resume with the configured lower host
    # free because the installed Docker layers/models themselves consume the space
    # that caused a later rerun to fall below the fresh-install threshold.
    if ($result.LaunchStatus -eq 'OK' -and $result.NormalUsers.Count -gt 0) {
        foreach ($candidate in $result.NormalUsers) {
            if (Test-ManagedLatticeValeStackForUser $Name ([string]$candidate)) { $result.ManagedStackOwners += [string]$candidate }
        }
        $result.ManagedStackOwners = @($result.ManagedStackOwners | Select-Object -Unique)
    }

    if ($result.ManagedStackOwners.Count -gt 0 -and $null -ne $result.StorageVolume) {
        $storageCleanupBlockers = @('STORAGE_FREE_LOW','STORAGE_TOTAL_LOW')
        $hasCleanupStorageBlocker = @($result.BlockerCodes | Where-Object { $storageCleanupBlockers -contains $_ }).Count -gt 0
        if ($hasCleanupStorageBlocker) {
            # A recognized managed install must be able to reach read-only verification and
            # explicit cleanup even when the Windows partition is already too full for a
            # normal repair. Remove only capacity/free-space blockers; every other safety
            # blocker (WSL launch, architecture, OS identity, storage location, etc.) remains.
            $newCodes = @()
            $newBlockers = @()
            for ($i = 0; $i -lt $result.BlockerCodes.Count; $i++) {
                if ($storageCleanupBlockers -contains $result.BlockerCodes[$i]) { continue }
                $newCodes += $result.BlockerCodes[$i]
                $newBlockers += $result.Blockers[$i]
            }
            $result.BlockerCodes = $newCodes
            $result.Blockers = $newBlockers
            $result.ManagedCleanupEligible = $true

            $repairSpaceOk = $result.StorageVolume.Size -gt ([int64]$compat.MinHostPartitionTotalGiBExclusive * 1GB) -and
                             $result.StorageVolume.Free -ge ([int64]$compat.MinManagedRepairFreeGiB * 1GB)
            if ($repairSpaceOk) {
                $result.ManagedRepairEligible = $true
                if (-not ($result.BlockerCodes | Where-Object { $_ -like 'STORAGE_*' })) { $result.StorageStatus = 'REPAIR OK' }
                Add-DistroWarning $result "Existing installer-managed LatticeVale stack detected for $($result.ManagedStackOwners -join ', '); Resume / repair may proceed with $([math]::Round($result.StorageVolume.Free / 1GB,1)) GB free. Fresh installs still require $($compat.MinHostPartitionFreeGiB) GB free."
            } else {
                $result.StorageStatus = 'CLEANUP ONLY'
                Add-DistroWarning $result "Existing installer-managed LatticeVale stack detected for $($result.ManagedStackOwners -join ', '), but its host partition is below the supported managed-repair storage floor. Verify and Cleanup remain available so space can be reclaimed without changing the live stack; mutating repair/update modes remain blocked."
            }
        } elseif ($result.StorageVolume.Size -gt ([int64]$compat.MinHostPartitionTotalGiBExclusive * 1GB) -and
                  $result.StorageVolume.Free -ge ([int64]$compat.MinManagedRepairFreeGiB * 1GB)) {
            $result.ManagedRepairEligible = $true
            $result.ManagedCleanupEligible = $true
        }
    }

    $result.Eligible = ($result.Blockers.Count -eq 0)
    return [pscustomobject]$result
}

function Show-DistroDiagnostic([object]$Info, [int]$Index) {
    $ok = 'OK'
    Write-Host ("  [{0}] {1}" -f $Index, $Info.Name) -ForegroundColor White
    $wslDetail = if ($null -ne $Info.WslVersion) { "WSL$($Info.WslVersion)" } else { 'unknown' }
    Write-Host ("      WSL ............. {0} - {1}" -f $wslDetail, $(if ($Info.WslVersion -eq 2) { $ok } else { 'BLOCKED' }))
    Write-Host ("      Launch .......... {0}" -f $Info.LaunchStatus)
    $osText = if ($Info.UbuntuVersion) { "Ubuntu $($Info.UbuntuVersion)" } elseif ($Info.OsPrettyName) { $Info.OsPrettyName } else { 'unknown' }
    $osState = if ($Info.UbuntuStatus -eq 'SUPPORTED') { $ok } elseif ($Info.UbuntuStatus -eq 'UNKNOWN') { 'UNKNOWN' } else { 'BLOCKED' }
    Write-Host ("      OS .............. {0} - {1}" -f $osText, $osState)
    $archText = if ($Info.LinuxArchitecture) { $Info.LinuxArchitecture } else { 'unknown' }
    Write-Host ("      Architecture .... {0} - {1}" -f $archText, $(if ($Info.ArchitectureStatus -eq 'OK') { $ok } else { 'BLOCKED/UNKNOWN' }))
    if ($null -ne $Info.Registration -and $Info.Registration.BasePath) {
        Write-Host ("      WSL storage ..... {0}" -f $Info.Registration.BasePath)
    } else {
        Write-Host '      WSL storage ..... unknown'
    }
    if ($null -ne $Info.StorageVolume) {
        $sv = $Info.StorageVolume
        Write-Host ("      Host partition .. {0} / {1} GB total / {2} GB free - {3}" -f $sv.Drive, [math]::Round($sv.Size/1GB,1), [math]::Round($sv.Free/1GB,1), $Info.StorageStatus)
    } else {
        Write-Host ("      Host partition .. unknown - {0}" -f $Info.StorageStatus)
    }
    if ($null -ne $Info.LinuxFilesystem -and $Info.LinuxFilesystem.Success) {
        Write-Host ("      Linux filesystem  {0} GB total / {1} GB available - {2}" -f [math]::Round($Info.LinuxFilesystem.TotalBytes/1GB,1), [math]::Round($Info.LinuxFilesystem.FreeBytes/1GB,1), $Info.LinuxFilesystemStatus)
    } else {
        Write-Host ("      Linux filesystem  unknown - {0}" -f $Info.LinuxFilesystemStatus)
    }
    $userText = if ($Info.NormalUsers.Count -gt 0) { "$($Info.NormalUsers.Count) Hermes-compatible user(s) found" } elseif ($Info.UserStatus -eq 'NONE') { 'none found' } else { 'unknown/not checked' }
    Write-Host ("      Linux user ....... {0} - {1}" -f $userText, $Info.UserStatus)
    if ($Info.LegacyInstallerArtifact) { Write-Host '      Legacy artifact . Older pre-LatticeVale distro name detected; never removed automatically.' -ForegroundColor DarkYellow }
    if ($Info.Eligible) {
        Write-Host '      Result ........... ELIGIBLE' -ForegroundColor Green
    } else {
        $category = if (@($Info.BlockerCodes | Where-Object { $_ -like 'STORAGE_*' }).Count -gt 0 -and @($Info.BlockerCodes | Where-Object { $_ -notlike 'STORAGE_*' }).Count -eq 0) { 'BLOCKED BY STORAGE' } elseif ($Info.BlockerCodes -contains 'UNRESPONSIVE') { 'UNRESPONSIVE' } elseif ($Info.BlockerCodes -contains 'UNLAUNCHABLE') { 'UNLAUNCHABLE' } else { 'INELIGIBLE' }
        Write-Host ("      Result ........... {0}" -f $category) -ForegroundColor Yellow
        foreach ($reason in $Info.Blockers) { Write-Host ("        - {0}" -f $reason) -ForegroundColor Yellow }
    }
    foreach ($warning in $Info.Warnings) { Write-Host ("        ! {0}" -f $warning) -ForegroundColor DarkYellow }
}

function Select-ExistingUbuntuDistro([string]$RequestedName, [object[]]$InstalledNames) {
    $compat = Get-LatticeValeCompatibility
    Write-Step 'Choose existing Ubuntu WSL2 distribution'
    Write-Info 'The installer installs into an existing distro only. It will not create, import, move, unregister, or convert a distro.'
    Write-Info ("Docker-supported Ubuntu releases for this build: {0}." -f (@($compat.SupportedUbuntuVersions) -join ', '))
    Write-Info ("Storage prerequisite: fresh installs require the distro's host partition to be over {0} GB total with at least {1} GB free. Existing installer-managed stacks may Resume / repair with at least $($compat.MinManagedRepairFreeGiB) GB free." -f $compat.MinHostPartitionTotalGiBExclusive, $compat.MinHostPartitionFreeGiB)

    $infos = @()
    foreach ($name in $InstalledNames) {
        $infos += Get-UbuntuDistroInfo ([string]$name)
    }

    Write-Host 'Detected WSL distributions:' -ForegroundColor White
    for ($i = 0; $i -lt $infos.Count; $i++) { Show-DistroDiagnostic $infos[$i] ($i + 1) }

    $eligible = @($infos | Where-Object { $_.Eligible })
    $unexpected = @($infos | Where-Object { $_.BlockerCodes -contains 'WSL_HOST_E_UNEXPECTED' })
    $requestedUnexpected = $null
    if (-not [string]::IsNullOrWhiteSpace($RequestedName)) {
        $requestedUnexpected = $unexpected | Where-Object { $_.Name -ieq $RequestedName } | Select-Object -First 1
    }
    if ($eligible.Count -eq 0 -or $null -ne $requestedUnexpected) {
        # v14.4.81: do not strand an otherwise registered distro on the generic
        # WSL E_UNEXPECTED cold-start failure. Offer the bounded, preservation-first
        # host recovery in the same installer run, then fully re-probe before deciding
        # eligibility. This also applies when -DistroName explicitly names the broken
        # distro even if a different registered distro is otherwise eligible.
        # Deeper DISM/feature repair remains an explicit helper action.
        if ($unexpected.Count -gt 0) {
            $recoveryTarget = $null
            if ($null -ne $requestedUnexpected) {
                $recoveryTarget = $requestedUnexpected
            } elseif ([string]::IsNullOrWhiteSpace($RequestedName) -and $unexpected.Count -eq 1) {
                $recoveryTarget = $unexpected[0]
            } else {
                Write-Host 'WSL launch-recovery candidates:' -ForegroundColor White
                for ($i = 0; $i -lt $unexpected.Count; $i++) { Write-Host ("  [{0}] {1}" -f ($i + 1), $unexpected[$i].Name) }
                $recoveryChoice = Read-IntegerExplicit 'Distro to use for the WSL host recovery probe' 1 $unexpected.Count
                $recoveryTarget = $unexpected[$recoveryChoice - 1]
            }

            if ($null -ne $recoveryTarget -and (Try-RecoverLatticeValeWslHostLaunch ([string]$recoveryTarget.Name))) {
                Write-Step 'Rechecking Ubuntu WSL2 eligibility after host recovery'
                $infos = @()
                foreach ($name in $InstalledNames) { $infos += Get-UbuntuDistroInfo ([string]$name) }
                Write-Host 'Post-recovery WSL distribution diagnostics:' -ForegroundColor White
                for ($i = 0; $i -lt $infos.Count; $i++) { Show-DistroDiagnostic $infos[$i] ($i + 1) }
                $eligible = @($infos | Where-Object { $_.Eligible })
            }
        }
    }

    if ($eligible.Count -eq 0) {
        $storageOnly = @($infos | Where-Object {
            $_.WslVersion -eq 2 -and $_.UbuntuStatus -eq 'SUPPORTED' -and $_.LaunchStatus -eq 'OK' -and
            $_.BlockerCodes.Count -gt 0 -and @($_.BlockerCodes | Where-Object { $_ -notlike 'STORAGE_*' }).Count -eq 0
        })
        if ($storageOnly.Count -gt 0) {
            $details = @()
            foreach ($item in $storageOnly) {
                if ($null -ne $item.StorageVolume) {
                    $details += "'$($item.Name)' is valid Ubuntu $($item.UbuntuVersion) WSL2, but $($item.StorageVolume.Drive) has $([math]::Round($item.StorageVolume.Free/1GB,1)) GB free ($([math]::Round($item.StorageVolume.Size/1GB,1)) GB total)."
                } else {
                    $details += "'$($item.Name)' is valid Ubuntu $($item.UbuntuVersion) WSL2, but its registered host storage could not satisfy the storage prerequisite."
                }
            }
            $otherVolumes = @(Get-LocalFixedVolumes | Where-Object {
                $_.Size -gt ([int64]$compat.MinHostPartitionTotalGiBExclusive * 1GB) -and
                $_.Free -ge ([int64]$compat.MinHostPartitionFreeGiB * 1GB) -and
                @($storageOnly.StorageVolume.Drive) -notcontains $_.Drive
            })
            $otherText = ''
            if ($otherVolumes.Count -gt 0) {
                $volumeSummaries = @($otherVolumes | ForEach-Object { "$($_.Drive) ($([math]::Round($_.Free/1GB,1)) GB free)" })
                $otherText = " Other qualifying Windows partitions exist: $($volumeSummaries -join ', '), but their free space does not automatically become storage for a WSL distro whose VHD is registered elsewhere."
            }
            throw (($details -join ' ') + " No new Ubuntu installation is required.$otherText Free enough space on the partition hosting that distro, or relocate the existing distro outside this installer, then rerun. This installer does not move WSL distributions.")
        }
        throw ("No eligible existing Ubuntu WSL2 distro was found. Review the per-distro diagnostics above. If no existing distro is a supported Ubuntu release ({0}), install/configure one outside this installer; the installer will not create or convert one." -f (@($compat.SupportedUbuntuVersions) -join ', '))
    }

    if (-not [string]::IsNullOrWhiteSpace($RequestedName)) {
        $requested = @($infos | Where-Object { $_.Name -ieq $RequestedName } | Select-Object -First 1)
        if ($requested.Count -eq 0) { throw "Requested distro '$RequestedName' is not registered." }
        if (-not $requested[0].Eligible) { throw "Requested distro '$RequestedName' is not eligible. Review its diagnostics above: $($requested[0].Blockers -join '; ')." }
        Write-Info "Using requested existing distro '$($requested[0].Name)'."
        return $requested[0]
    }

    if ($eligible.Count -eq 1) {
        if (-not (Read-ChoiceExplicit "Use '$($eligible[0].Name)'?" "Docker and the selected LatticeVale services will be installed into this existing Ubuntu $($eligible[0].UbuntuVersion) WSL2 distro." 'Installer stops; the distro is left unchanged.' $true)) {
            throw 'No existing distro was selected.'
        }
        return $eligible[0]
    }

    Write-Host 'Eligible existing Ubuntu WSL2 distributions:' -ForegroundColor White
    for ($i = 0; $i -lt $eligible.Count; $i++) {
        Write-Host ("  [{0}] {1} - Ubuntu {2} / WSL2 / {3} GB host free" -f ($i + 1), $eligible[$i].Name, $eligible[$i].UbuntuVersion, [math]::Round($eligible[$i].StorageVolume.Free/1GB,1))
    }
    $choice = Read-IntegerExplicit 'Existing Ubuntu distro number' 1 $eligible.Count
    return $eligible[$choice - 1]
}

function Get-ExistingLinuxUsers([string]$Name, [switch]$ReturnProbe) {
    $probe = Invoke-WslDirectCapture $Name 'root' 'getent' @('passwd')
    if (-not $probe.Success) {
        $detailText = Get-SafeDiagnosticExcerpt $probe.Text
        $detail = if ($probe.TimedOut) { 'user enumeration timed out' } elseif ($detailText) { "user enumeration failed (exit $($probe.ExitCode)): $detailText" } else { "user enumeration failed (exit $($probe.ExitCode))" }
        if ($ReturnProbe) { return [pscustomobject]@{ Success = $false; Users = @(); Detail = $detail } }
        return @()
    }
    $users = @()
    foreach ($line in ($probe.Text -split "`r?`n")) {
        if (-not $line) { continue }
        $parts = @($line -split ':')
        if ($parts.Count -lt 7) { continue }
        $uid = 0; $gid = 0
        if (-not [int]::TryParse($parts[2], [ref]$uid)) { continue }
        if (-not [int]::TryParse($parts[3], [ref]$gid)) { continue }
        if ($uid -lt 1000 -or $uid -gt 65534 -or $gid -lt 1000 -or $gid -gt 65534 -or $parts[0] -eq 'nobody') { continue }
        if ($parts[6] -match '(nologin|/false)$') { continue }
        $users += $parts[0]
    }
    $users = @($users | Select-Object -Unique)
    if ($ReturnProbe) { return [pscustomobject]@{ Success = $true; Users = $users; Detail = '' } }
    return $users
}

function Select-ExistingLinuxUser([string]$Name) {
    Write-Step 'Choose existing Ubuntu user'
    Write-Info 'The installer reuses an existing Linux user. It does not create accounts or change the distro default user.'
    Write-Info 'Hermes Docker UID/GID remapping requires the selected account UID and primary GID to both be in the 1000-65534 range.'

    $users = @(Get-ExistingLinuxUsers $Name)
    if ($users.Count -eq 0) {
        throw "No Hermes-compatible user account was found inside '$Name'. Use an Ubuntu account whose UID and primary GID are both 1000-65534, then rerun this installer."
    }

    # Recovery must follow the existing managed stack, not whichever account happens
    # to be the WSL default today. A second stack in the same distro would collide on
    # fixed Docker container/service names, so v13 refuses that ambiguous state.
    $managedOwners = @()
    foreach ($candidate in $users) {
        if (Test-ManagedLatticeValeStackForUser $Name ([string]$candidate)) { $managedOwners += [string]$candidate }
    }
    if ($managedOwners.Count -gt 1) {
        throw "More than one installer-managed LatticeVale stack was found in '$Name' (users: $($managedOwners -join ', ')). This distro is ambiguous and unsafe to modify automatically. Keep one managed stack per WSL distro, then rerun."
    }
    if ($managedOwners.Count -eq 1) {
        Write-Info "Existing installer-managed LatticeVale stack found for Ubuntu user '$($managedOwners[0])'; recovery is locked to that account."
        return [string]$managedOwners[0]
    }

    $defaultUser = ''
    # Probe the distro without forcing a user so WSL returns its configured default account.
    # Use the same bounded probe helper so a broken distro cannot hang user selection.
    $defaultProbe = Invoke-WslDirectCapture $Name '' 'id' @('-un')
    if ($defaultProbe.Success) { $defaultUser = $defaultProbe.Text.Trim() }

    Write-Host 'Existing normal users:' -ForegroundColor White
    for ($i = 0; $i -lt $users.Count; $i++) {
        $tag = if ($users[$i] -eq $defaultUser) { ' (current WSL default)' } else { '' }
        Write-Host ("  [{0}] {1}{2}" -f ($i + 1), $users[$i], $tag)
    }
    if ($users.Count -eq 1) {
        Write-Info "Exactly one compatible existing Ubuntu user was detected: '$($users[0])'."
        if (-not (Read-ChoiceExplicit "Use Ubuntu user '$($users[0])' for Hermes?" "LatticeVale will install the stack in this detected user's actual Linux home directory." 'Installer stops; no Linux account or home path is guessed.' $true)) {
            throw 'No existing Ubuntu user was selected.'
        }
        return [string]$users[0]
    }
    $choice = Read-IntegerExplicit 'Ubuntu user for Hermes' 1 $users.Count
    return [string]$users[$choice - 1]
}

function Get-InstalledDockerConflictPackages([string]$Name) {
    $script = @'
for p in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
  if dpkg-query -W -f='${db:Status-Status}' "$p" 2>/dev/null | grep -qx installed; then
    printf '%s\n' "$p"
  fi
done
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script))
    $probe = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc', "echo '$encoded' | base64 -d | bash") 30
    if (-not $probe.Success) { return @() }
    return @($probe.Text -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Get-ExistingDockerRuntimeInfo([string]$Name) {
    $script = @'
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
export DOCKER_HOST=unix:///var/run/docker.sock
official=0
for p in docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; do
  if dpkg-query -W -f='${db:Status-Status}' "$p" 2>/dev/null | grep -qx installed; then official=$((official+1)); fi
done
runtime=0
rootless=0
server=''
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  runtime=1
  server="$(docker info --format '{{.OperatingSystem}}|{{.Name}}' 2>/dev/null || true)"
fi
if find /run/user -mindepth 2 -maxdepth 2 -type s -name docker.sock -print -quit 2>/dev/null | grep -q .; then rootless=1; fi
if ps -eo args= 2>/dev/null | grep -E '[d]ockerd-rootless|[r]ootlesskit.*dockerd' >/dev/null; then rootless=1; fi
printf 'OFFICIAL_COUNT=%s\nRUNTIME=%s\nROOTLESS=%s\nSERVER=%s\n' "$official" "$runtime" "$rootless" "$server"
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script))
    $probe = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc', "echo '$encoded' | base64 -d | bash") 30
    $result = [ordered]@{ Known=$probe.Success; OfficialCount=0; Runtime=$false; Rootless=$false; Server='' }
    if (-not $probe.Success) { return [pscustomobject]$result }
    foreach ($line in ($probe.Text -split "`r?`n")) {
        if ($line -match '^OFFICIAL_COUNT=(\d+)$') { $result.OfficialCount = [int]$Matches[1] }
        elseif ($line -match '^RUNTIME=(\d+)$') { $result.Runtime = ([int]$Matches[1] -eq 1) }
        elseif ($line -match '^ROOTLESS=(\d+)$') { $result.Rootless = ([int]$Matches[1] -eq 1) }
        elseif ($line -match '^SERVER=(.*)$') { $result.Server = $Matches[1].Trim() }
    }
    return [pscustomobject]$result
}

function Get-ExistingRootlessDockerRuntimeInfo([string]$Name, [string]$User) {
    $script = @'
uid="$(id -u)"
sock="/run/user/$uid/docker.sock"
configured=0
runtime=0
server=''
if [[ -f "$HOME/.config/systemd/user/docker.service" ]]; then configured=1; fi
if [[ -S "$sock" ]] && command -v docker >/dev/null 2>&1; then
  if DOCKER_HOST="unix://$sock" DOCKER_CONTEXT= docker info >/dev/null 2>&1; then
    runtime=1
    server="$(DOCKER_HOST="unix://$sock" DOCKER_CONTEXT= docker info --format '{{.OperatingSystem}}|{{.Name}}' 2>/dev/null || true)"
  fi
fi
printf 'CONFIGURED=%s\nRUNTIME=%s\nSERVER=%s\nSOCKET=%s\n' "$configured" "$runtime" "$server" "$sock"
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script))
    $probe = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', "echo '$encoded' | base64 -d | bash") 30
    $result = [ordered]@{ Known=$probe.Success; Configured=$false; Runtime=$false; Server=''; Socket='' }
    if (-not $probe.Success) { return [pscustomobject]$result }
    foreach ($line in ($probe.Text -split "`r?`n")) {
        if ($line -match '^CONFIGURED=(\d+)$') { $result.Configured = ([int]$Matches[1] -eq 1) }
        elseif ($line -match '^RUNTIME=(\d+)$') { $result.Runtime = ([int]$Matches[1] -eq 1) }
        elseif ($line -match '^SERVER=(.*)$') { $result.Server = $Matches[1].Trim() }
        elseif ($line -match '^SOCKET=(.*)$') { $result.Socket = $Matches[1].Trim() }
    }
    return [pscustomobject]$result
}

function Invoke-Wsl([string[]]$Arguments) {
    & wsl.exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "wsl.exe failed with exit code $LASTEXITCODE. Command: wsl.exe $($Arguments -join ' ')"
    }
}

function Invoke-LatticeValeWslInteractiveGuarded(
    [string]$Name,
    [string[]]$Arguments,
    [int]$MaxRuntimeSeconds = 14400,
    [int]$HeartbeatIntervalSeconds = 30,
    [int]$HeartbeatTimeoutSeconds = 20,
    [int]$MaxHeartbeatFailures = 6
) {
    # Start-Process without redirection inherits the current console handles. This keeps the
    # Linux setup's PTY/user prompts interactive while allowing the parent installer to watch
    # the wsl.exe process and detect a WSL VM/service that has stopped responding.
    $argumentLine = (($Arguments | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = 'wsl.exe'
    $startInfo.Arguments = $argumentLine
    $startInfo.UseShellExecute = $false
    # Do not redirect standard handles and do not request CREATE_NO_WINDOW here. With
    # UseShellExecute=false, the child inherits the calling process's standard streams;
    # this preserves the existing interactive WSL/PTY behavior while still giving us a
    # directly owned Process object with a reliable ExitCode.
    $startInfo.CreateNoWindow = $false
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw 'Could not start wsl.exe for the interactive Linux installer.' }
    $started = [DateTime]::UtcNow
    $nextHeartbeat = [DateTime]::UtcNow.AddSeconds($HeartbeatIntervalSeconds)
    $heartbeatFailures = 0
    try {
        while (-not $process.HasExited) {
            if (([DateTime]::UtcNow - $started).TotalSeconds -ge $MaxRuntimeSeconds) {
                try { $process.Kill() } catch { }
                throw "The WSL installer process exceeded the $MaxRuntimeSeconds-second safety limit. Existing data was preserved; rerun and choose Resume / repair."
            }
            if ([DateTime]::UtcNow -ge $nextHeartbeat) {
                $heartbeat = Invoke-WslDirectCapture $Name 'root' 'true' @() $HeartbeatTimeoutSeconds
                if ($heartbeat.Success) {
                    $heartbeatFailures = 0
                } else {
                    $heartbeatFailures++
                    $detail = Get-SafeDiagnosticExcerpt $heartbeat.Text 260
                    if (-not $detail) { $detail = if ($heartbeat.TimedOut) { 'WSL heartbeat timed out' } else { 'WSL heartbeat failed' } }
                    Write-Warning "WSL responsiveness check $heartbeatFailures/$MaxHeartbeatFailures failed during Linux setup: $detail"
                    if ($heartbeatFailures -ge $MaxHeartbeatFailures) {
                        try { $process.Kill() } catch { }
                        throw "WSL stopped responding during Linux setup after $MaxHeartbeatFailures consecutive bounded heartbeat failures. The current stage was not allowed to hang indefinitely. Restart Windows if WSL remains unresponsive, then rerun this installer and choose Resume / repair; persistent stack data was preserved."
                    }
                }
                $nextHeartbeat = [DateTime]::UtcNow.AddSeconds($HeartbeatIntervalSeconds)
            }
            Start-Sleep -Milliseconds 500
            try { $process.Refresh() } catch { }
        }
        if ($process.ExitCode -ne 0) {
            throw "wsl.exe failed with exit code $($process.ExitCode). The Linux installer records resumable stage state; rerun and choose Resume / repair after correcting the reported failure."
        }
    } finally {
        if ($process -and -not $process.HasExited) {
            try { $process.Kill() } catch { }
        }
        if ($process) { try { $process.Dispose() } catch { } }
    }
}

function Get-WindowsTailscaleExe {
    $command = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source)) {
        return $command.Source
    }

    $candidates = @()
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe') }
    ${pf86} = ${env:ProgramFiles(x86)}
    if (${pf86}) { $candidates += (Join-Path ${pf86} 'Tailscale\tailscale.exe') }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

function Get-WindowsTailscaleStatus([string]$TailscaleExe) {
    if (-not $TailscaleExe) {
        return [pscustomobject]@{ BackendState = 'NotInstalled'; DNSName = ''; HostName = '' }
    }
    try {
        # Some non-Running Tailscale states can return a non-zero process exit while still
        # providing useful status JSON. Parse valid JSON first; use the exit code only when
        # there is no usable JSON payload.
        $statusProbe = Invoke-NativeProcessCapture $TailscaleExe @('status','--json') 15
        $raw = ([string]$statusProbe.Text).Trim()
        $commandExit = $statusProbe.ExitCode
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
            try {
                $status = $raw | ConvertFrom-Json -ErrorAction Stop
                $dns = ''
                $hostName = ''
                if ($status.Self) {
                    if ($status.Self.DNSName) { $dns = ([string]$status.Self.DNSName).TrimEnd('.') }
                    if ($status.Self.HostName) { $hostName = [string]$status.Self.HostName }
                }
                return [pscustomobject]@{
                    BackendState = if ($status.BackendState) { [string]$status.BackendState } else { 'Unknown' }
                    DNSName = $dns
                    HostName = $hostName
                }
            } catch {
                # Fall through to Unavailable below.
            }
        }
        if ($commandExit -ne 0) {
            return [pscustomobject]@{ BackendState = 'Unavailable'; DNSName = ''; HostName = '' }
        }
    } catch {
        return [pscustomobject]@{ BackendState = 'Unavailable'; DNSName = ''; HostName = '' }
    }
    return [pscustomobject]@{ BackendState = 'Unavailable'; DNSName = ''; HostName = '' }
}

function Install-WindowsTailscale {
    Write-Step 'Installing Tailscale for Windows'
    Write-Info 'Tailscale is installed on Windows only. Nothing is installed inside WSL.'

    $installer = Join-Path $env:TEMP 'tailscale-setup-latest.exe'
    $installed = $false
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -Uri 'https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe' -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or -not $signature.SignerCertificate) {
            throw "Downloaded Tailscale installer did not have a valid Authenticode signature (status: $($signature.Status))."
        }
        $signerSubject = [string]$signature.SignerCertificate.Subject
        if ($signerSubject -notmatch '(?i)tailscale') {
            throw "Downloaded Tailscale installer is validly signed, but the signer is not identifiable as Tailscale: $signerSubject"
        }
        Write-Info "Verified downloaded Tailscale installer signature: $signerSubject"
        $installProbe = Invoke-NativeProcessPassthrough $installer @() 600
        if ($installProbe.Success) {
            $installed = $true
        } elseif ($installProbe.TimedOut) {
            Write-Warning 'The Tailscale Windows installer exceeded its 10-minute safety timeout.'
        } else {
            Write-Warning "The Tailscale Windows installer exited with code $($installProbe.ExitCode)."
        }
    } catch {
        Write-Warning "Direct Tailscale installer download/run failed: $($_.Exception.Message)"
    } finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }

    if (-not $installed -and -not (Get-WindowsTailscaleExe)) {
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Info 'Trying the Windows Package Manager fallback.'
            $wingetProbe = Invoke-NativeProcessPassthrough 'winget.exe' @('install','--exact','--id','Tailscale.Tailscale','--accept-package-agreements','--accept-source-agreements','--disable-interactivity') 1200
            if (-not $wingetProbe.Success) {
                Write-Warning 'Tailscale installation through winget failed or exceeded its 20-minute safety timeout. LatticeVale will remain local-only.'
            }
        } else {
            Write-Warning 'winget is unavailable, so Tailscale could not be installed automatically. LatticeVale will remain local-only.'
        }
    }

    # Give the installer/service registration a moment to settle, but do not make Tailscale
    # a fatal dependency for the local Hermes stack.
    for ($i = 0; $i -lt 10; $i++) {
        $exe = Get-WindowsTailscaleExe
        if ($exe) { return $exe }
        Start-Sleep -Milliseconds 750
    }
    return $null
}

function Test-LocalTcpPort([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(3000, $false)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-RemoteTcpEndpoint([string]$Address, [int]$Port, [int]$TimeoutMilliseconds = 1500) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Address, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        try { $client.Close() } catch { }
    }
}

function Get-LatticeValeWslIpv4Candidates([string]$Name) {
    $result = [System.Collections.Generic.List[string]]::new()
    $probes = @(
        (Invoke-WslDirectCapture $Name '' 'ip' @('-4','-o','addr','show','dev','eth0','scope','global') 15),
        (Invoke-WslDirectCapture $Name '' 'hostname' @('-I') 15)
    )
    foreach ($probe in $probes) {
        if (-not $probe.Success -or [string]::IsNullOrWhiteSpace($probe.Text)) { continue }
        foreach ($match in [regex]::Matches([string]$probe.Text, '(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')) {
            $address = $null
            if (-not [System.Net.IPAddress]::TryParse($match.Value, [ref]$address)) { continue }
            if ($address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { continue }
            if ([System.Net.IPAddress]::IsLoopback($address)) { continue }
            $text = $address.ToString()
            if ($text.StartsWith('169.254.')) { continue }
            if (-not $result.Contains($text)) { $result.Add($text) }
        }
    }
    return $result.ToArray()
}

function Resolve-LatticeValeReachableWslIpv4([string]$Name, [int[]]$BackendPorts, [int]$TimeoutSeconds = 20) {
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1,$TimeoutSeconds))
    do {
        foreach ($ip in @(Get-LatticeValeWslIpv4Candidates $Name)) {
            $allReady = $true
            foreach ($port in @($BackendPorts)) {
                if ($port -le 0 -or -not (Test-RemoteTcpEndpoint $ip $port 1500)) { $allReady = $false; break }
            }
            if ($allReady) { return $ip }
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    return ''
}

function Test-WindowsTcpPortAvailable([int]$Port) {
    $socket = New-Object System.Net.Sockets.Socket ([System.Net.Sockets.AddressFamily]::InterNetwork), ([System.Net.Sockets.SocketType]::Stream), ([System.Net.Sockets.ProtocolType]::Tcp)
    try {
        $socket.ExclusiveAddressUse = $true
        $socket.Bind([System.Net.IPEndPoint]::new([System.Net.IPAddress]::Loopback, $Port))
        return $true
    } catch {
        return $false
    } finally {
        try { $socket.Dispose() } catch { }
    }
}

function Test-WslTcpPortAvailable([string]$Name, [int]$Port) {
    $probeScript = @'
p="$1"
if command -v ss >/dev/null 2>&1; then
  if ss -H -ltn 2>/dev/null | awk -v p=":$p" '$4 ~ (p "$") {found=1} END {exit found?0:1}'; then exit 1; else exit 0; fi
fi
if command -v python3 >/dev/null 2>&1; then
  python3 - "$p" <<'PY_PORT'
import socket,sys
s=socket.socket()
try:
    s.bind(('127.0.0.1',int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY_PORT
  exit $?
fi
# If neither probe exists, do not invent a conflict; Windows binding is still checked.
exit 0
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probeScript))
    $probe = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc', "echo '$encoded' | base64 -d | bash -s -- '$Port'") 15
    return $probe.Success
}

function Resolve-LatticeValeLocalPort([string]$Name, [string]$Label, [int]$Preferred, [int[]]$Disallow = @()) {
    $candidates = [System.Collections.Generic.List[int]]::new()
    $candidates.Add($Preferred)
    for ($offset = 1; $offset -le 2000; $offset++) {
        $candidate = $Preferred + $offset
        if ($candidate -le 65535) { $candidates.Add($candidate) }
    }
    for ($candidate = 20000; $candidate -le 40000; $candidate++) {
        if (-not $candidates.Contains($candidate)) { $candidates.Add($candidate) }
    }
    foreach ($candidate in $candidates) {
        if ($candidate -lt 1024 -or $Disallow -contains $candidate) { continue }
        if ((Test-WindowsTcpPortAvailable $candidate) -and (Test-WslTcpPortAvailable $Name $candidate)) {
            if ($candidate -ne $Preferred) {
                Write-Warning "$Label localhost port $Preferred is already occupied/reserved. Using available port $candidate instead."
            }
            return $candidate
        }
    }
    throw "Could not find an available localhost TCP port for $Label after checking Windows and '$Name'."
}

function Get-LatticeValePublishedPortOwnership(
    [string]$Name,
    [string]$LinuxHome,
    [string]$ContainerName,
    [int]$ContainerPort,
    [int]$HostPort
) {
    $result = [ordered]@{ Known=$false; Owned=$false; Detail='' }
    if (-not $LinuxHome -or -not $ContainerName -or $ContainerPort -lt 1 -or $HostPort -lt 1) {
        $result.Detail = 'invalid ownership probe arguments'
        return [pscustomobject]$result
    }
    $probeScript = @'
set -u
expected_dir="$1"
container="$2"
container_port="$3"
host_port="$4"
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
export DOCKER_HOST=unix:///var/run/docker.sock
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  printf 'KNOWN=0\nOWNED=0\nDETAIL=docker daemon unavailable\n'
  exit 0
fi
EXPECTED_DIR="$expected_dir" CONTAINER_NAME="$container" CONTAINER_PORT="$container_port" HOST_PORT="$host_port" python3 - <<'PY_OWN'
import json, os, posixpath, subprocess
try:
    proc=subprocess.run(['docker','inspect',os.environ['CONTAINER_NAME']], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10)
    if proc.returncode != 0:
        print('KNOWN=1')
        print('OWNED=0')
        print('DETAIL=container absent')
        raise SystemExit(0)
    rows=json.loads(proc.stdout)
    row=rows[0]
    labels=((row.get('Config') or {}).get('Labels') or {})
    project=str(labels.get('com.docker.compose.project') or '')
    working=str(labels.get('com.docker.compose.project.working_dir') or '')
    expected=posixpath.normpath(os.environ['EXPECTED_DIR'])
    working_norm=posixpath.normpath(working) if working else ''
    key=f"{int(os.environ['CONTAINER_PORT'])}/tcp"
    bindings=((row.get('NetworkSettings') or {}).get('Ports') or {}).get(key) or []
    target=str(int(os.environ['HOST_PORT']))
    expected_binding=any(str(b.get('HostPort') or '') == target and str(b.get('HostIp') or '') in ('127.0.0.1','::1','0.0.0.0','::') for b in bindings)
    owned=(project == 'hermesstack' and working_norm == expected and expected_binding)
    print('KNOWN=1')
    print('OWNED=1' if owned else 'OWNED=0')
    print('DETAIL=matching Hermes Compose port' if owned else 'DETAIL=container/port is not owned by this stack')
except SystemExit:
    raise
except Exception:
    print('KNOWN=0')
    print('OWNED=0')
    print('DETAIL=inspect parse failed')
PY_OWN
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probeScript))
    $probe = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc', "echo '$encoded' | base64 -d | bash -s -- '$LinuxHome/hermes-stack' '$ContainerName' '$ContainerPort' '$HostPort'") 20
    if (-not $probe.Success) {
        $result.Detail = 'ownership probe failed'
        return [pscustomobject]$result
    }
    foreach ($line in ($probe.Text -split "`r?`n")) {
        if ($line -match '^KNOWN=(\d+)$') { $result.Known = ([int]$Matches[1] -eq 1) }
        elseif ($line -match '^OWNED=(\d+)$') { $result.Owned = ([int]$Matches[1] -eq 1) }
        elseif ($line -match '^DETAIL=(.*)$') { $result.Detail = $Matches[1].Trim() }
    }
    return [pscustomobject]$result
}

function Resolve-LatticeValeRepairLocalPort(
    [string]$Name,
    [string]$LinuxHome,
    [string]$Label,
    [int]$CurrentPort,
    [string]$ContainerName,
    [int]$ContainerPort,
    [int[]]$Disallow = @()
) {
    if ($CurrentPort -lt 1 -or $CurrentPort -gt 65535) {
        return Resolve-LatticeValeLocalPort $Name $Label $ContainerPort $Disallow
    }
    if ($Disallow -contains $CurrentPort) {
        Write-Warning "$Label saved localhost port $CurrentPort conflicts with another selected LatticeVale service. Selecting a replacement."
        return Resolve-LatticeValeLocalPort $Name $Label $CurrentPort $Disallow
    }

    $ownership = Get-LatticeValePublishedPortOwnership $Name $LinuxHome $ContainerName $ContainerPort $CurrentPort
    if ($ownership.Known -and $ownership.Owned) {
        return $CurrentPort
    }

    $windowsFree = Test-WindowsTcpPortAvailable $CurrentPort
    $wslFree = Test-WslTcpPortAvailable $Name $CurrentPort
    if ($windowsFree -and $wslFree) {
        return $CurrentPort
    }

    if ($ownership.Known) {
        Write-Warning "$Label saved localhost port $CurrentPort is occupied but is not published by this LatticeVale stack. Selecting an available replacement for repair."
    } else {
        Write-Warning "$Label saved localhost port $CurrentPort is occupied and Docker ownership could not be proven. Selecting an available replacement rather than overwriting an unknown listener."
    }
    return Resolve-LatticeValeLocalPort $Name $Label $CurrentPort $Disallow
}


function Get-WindowsPortProxyRules {
    $result = @()
    try {
        $raw = (& (Join-Path $env:SystemRoot 'System32\netsh.exe') interface portproxy dump 2>$null | Out-String)
        foreach ($line in ($raw -split "`r?`n")) {
            $trimmed = $line.Trim()
            if ($trimmed -notmatch '^add\s+v4tov4\s+') { continue }
            $entry = @{}
            foreach ($match in [regex]::Matches($trimmed, '(?<key>[A-Za-z]+)=(?<value>"[^"]*"|\S+)')) {
                $entry[$match.Groups['key'].Value.ToLowerInvariant()] = $match.Groups['value'].Value.Trim('"')
            }
            if (-not $entry.ContainsKey('listenport') -or -not $entry.ContainsKey('connectport')) { continue }
            $listenPort = 0; $connectPort = 0
            if (-not [int]::TryParse([string]$entry['listenport'], [ref]$listenPort)) { continue }
            if (-not [int]::TryParse([string]$entry['connectport'], [ref]$connectPort)) { continue }
            $result += [pscustomobject]@{
                ListenAddress = if ($entry.ContainsKey('listenaddress')) { [string]$entry['listenaddress'] } else { '0.0.0.0' }
                ListenPort = $listenPort
                ConnectAddress = if ($entry.ContainsKey('connectaddress')) { [string]$entry['connectaddress'] } else { '' }
                ConnectPort = $connectPort
            }
        }
    } catch { }
    return @($result)
}

function Test-LatticeValeBridgeTaskOwned([object]$Paths) {
    if ($null -eq $Paths) { return $false }
    $task = Get-ScheduledTask -TaskName $Paths.TaskName -ErrorAction SilentlyContinue
    if (-not $task) { return $false }
    foreach ($action in @($task.Actions)) {
        $argsText = [string]$action.Arguments
        if ([string]::IsNullOrWhiteSpace($argsText)) { continue }
        $hasScript = ($argsText.IndexOf([string]$Paths.Script, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
        $hasConfig = ($argsText.IndexOf([string]$Paths.Config, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
        if ($hasScript -and $hasConfig) { return $true }
    }
    return $false
}

function Stop-LatticeValeOwnedBridgeProcesses([object]$Paths) {
    # A task can be removed or marked stopped while a previously spawned PowerShell
    # relay remains alive. Reclaim only processes whose command line references BOTH
    # exact installer-owned paths; never kill a process merely because it owns a port.
    if ($null -eq $Paths) { return 0 }
    $stopped = 0
    try {
        foreach ($process in @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" -ErrorAction Stop)) {
            $name = ([string]$process.Name).ToLowerInvariant()
            if ($name -notin @('powershell.exe','pwsh.exe')) { continue }
            $commandLine = [string]$process.CommandLine
            if ([string]::IsNullOrWhiteSpace($commandLine)) { continue }
            $hasScript = ($commandLine.IndexOf([string]$Paths.Script, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
            $hasConfig = ($commandLine.IndexOf([string]$Paths.Config, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
            if (-not ($hasScript -and $hasConfig)) { continue }
            try {
                Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction Stop
                $stopped++
            } catch {
                Write-Warning "Could not stop verified stale LatticeVale relay process PID $($process.ProcessId): $($_.Exception.Message)"
            }
        }
    } catch {
        Write-Warning "Could not inspect Windows processes for stale LatticeVale relay ownership: $($_.Exception.Message)"
    }
    return $stopped
}

function Prepare-LatticeValeBridgePortsForReconcile([string]$Name, [int[]]$Ports = @()) {
    # Stop the CURRENT installer-owned relay before choosing bridge ports. Older
    # releases selected ports first, so their own still-running listener could make
    # canonical 19119/18008 appear foreign and cause needless 19120/18009 drift.
    $paths = Get-LatticeValeBridgePaths $Name
    $task = Get-ScheduledTask -TaskName $paths.TaskName -ErrorAction SilentlyContinue
    $ownedTask = $false
    if ($task) {
        $ownedTask = Test-LatticeValeBridgeTaskOwned $paths
        if ($ownedTask) {
            if (-not (Stop-LatticeValeBridgeTaskAndWait $paths.TaskName 15)) {
                throw "Could not stop the prior installer-owned Windows WSL relay task '$($paths.TaskName)' before bridge-port reconciliation."
            }
        } else {
            Write-Warning "A same-name relay task '$($paths.TaskName)' exists but its exact LatticeVale script/config ownership could not be proven. It was left untouched."
        }
    }

    $orphanCount = Stop-LatticeValeOwnedBridgeProcesses $paths
    if ($ownedTask -or $orphanCount -gt 0) {
        foreach ($port in @($Ports | Where-Object { $_ -ge 1 -and $_ -le 65535 } | Select-Object -Unique)) {
            if (-not (Test-WindowsTcpPortAvailable $port)) {
                if (Wait-WindowsTcpPortReleased $port 10) {
                    Write-Info "Reclaimed installer-owned Windows bridge port $port from the previous LatticeVale relay."
                }
            }
        }
    }
    return $paths
}

function Resolve-LatticeValeWindowsBridgePort(
    [string]$Label,
    [int]$Preferred,
    [int]$PriorPort = 0,
    [bool]$PriorOwned = $false,
    [int[]]$Disallow = @()
) {
    $proxyPorts = @((Get-WindowsPortProxyRules) | Where-Object { $_.ListenAddress -eq '127.0.0.1' } | ForEach-Object { $_.ListenPort })
    $candidates = [System.Collections.Generic.List[int]]::new()

    # Re-center old installs on the canonical bridge port whenever it is now free.
    # If a real foreign listener owns the canonical port, preserve a previously-owned
    # alternate before searching higher ports. Unknown listeners are never stopped.
    $candidates.Add($Preferred)
    if ($PriorOwned -and $PriorPort -ge 1 -and $PriorPort -le 65535 -and $PriorPort -ne $Preferred) {
        $candidates.Add($PriorPort)
    }
    for ($offset = 1; $offset -le 2000; $offset++) {
        $candidate = $Preferred + $offset
        if ($candidate -le 65535 -and -not $candidates.Contains($candidate)) { $candidates.Add($candidate) }
    }
    foreach ($candidate in $candidates) {
        if ($candidate -lt 1024 -or $Disallow -contains $candidate -or $proxyPorts -contains $candidate) { continue }
        if (Test-WindowsTcpPortAvailable $candidate) {
            if ($candidate -ne $Preferred) { Write-Warning "$Label Windows bridge port $Preferred is unavailable to LatticeVale after owned-state cleanup. Using $candidate instead." }
            return $candidate
        }
    }
    throw "Could not find an available Windows loopback bridge port for $Label."
}

function Stop-LatticeValeBridgeTaskAndWait([string]$TaskName, [int]$WaitSeconds = 15) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) { return $true }
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1,$WaitSeconds))
    do {
        Start-Sleep -Milliseconds 250
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if (-not $task -or [string]$task.State -ne 'Running') { return $true }
    } while ([DateTime]::UtcNow -lt $deadline)
    Write-Warning "Installer-owned Windows WSL relay task '$TaskName' did not stop within $WaitSeconds seconds."
    return $false
}

function Get-LatticeValeBridgeLogTail([object]$Paths, [int]$Lines = 8) {
    try {
        $log = Join-Path $Paths.Directory 'native-relay.log'
        if (Test-Path -LiteralPath $log -PathType Leaf) {
            return ((Get-Content -LiteralPath $log -Tail $Lines -ErrorAction SilentlyContinue) -join ' | ')
        }
    } catch { }
    return ''
}

function Write-LatticeValeBridgeConfig(
    [string]$Name,
    [bool]$DashboardEnabled,
    [int]$DashboardBackendPort,
    [int]$DashboardBridgePort,
    [bool]$MatrixEnabled,
    [int]$MatrixBackendPort,
    [int]$MatrixBridgePort,
    [string]$SeedWslIp = '',
    [string]$NetworkingMode = ''
) {
    $paths = Get-LatticeValeBridgePaths $Name
    New-Item -ItemType Directory -Path $paths.Directory -Force | Out-Null

    # A relay task is long-running. Stop any prior installer-owned instance before
    # replacing its script/config so the next start always consumes this version.
    # Repair runs must fail fast rather than starting a second copy against a stale
    # mutex/listener and then waiting silently for the verification deadline.
    if (-not (Stop-LatticeValeBridgeTaskAndWait $paths.TaskName 15)) {
        throw "Could not stop the prior installer-owned Windows WSL relay task '$($paths.TaskName)'."
    }

    # Do not mix a new task failure with stale troubleshooting output from an old
    # manual/installer relay. Preserve one previous log for forensics, then start
    # the current run with a fresh task-specific diagnostic stream.
    $relayLog = Join-Path $paths.Directory 'native-relay.log'
    $previousRelayLog = Join-Path $paths.Directory 'native-relay.previous.log'
    Remove-Item -LiteralPath $previousRelayLog -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $relayLog -PathType Leaf) {
        Move-Item -LiteralPath $relayLog -Destination $previousRelayLog -Force -ErrorAction SilentlyContinue
    }
    Add-Content -LiteralPath $relayLog -Value ("{0} Installer preparing relay task for {1}." -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$Name) -Encoding UTF8

    $source = Join-Path $PSScriptRoot 'windows\LatticeVale-WslNativeRelay.ps1'
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Installer bundle is missing windows\LatticeVale-WslNativeRelay.ps1.' }
    Copy-Item -LiteralPath $source -Destination $paths.Script -Force

    $lastIp = ''
    if (Test-LatticeValeBridgeIpv4 $SeedWslIp) {
        $lastIp = $SeedWslIp.Trim()
    } elseif (Test-Path -LiteralPath $paths.Config -PathType Leaf) {
        try {
            $old = Get-Content -LiteralPath $paths.Config -Raw | ConvertFrom-Json
            if ([string]$old.distroName -eq $Name) { $lastIp = [string]$old.lastWslIp }
        } catch { }
    }
    $services = @()
    if ($DashboardEnabled) {
        $services += [ordered]@{ label='Dashboard'; enabled=$true; backendPort=$DashboardBackendPort; bridgePort=$DashboardBridgePort; probePath='/' }
    }
    if ($MatrixEnabled) {
        $services += [ordered]@{ label='Matrix'; enabled=$true; backendPort=$MatrixBackendPort; bridgePort=$MatrixBridgePort; probePath='/_matrix/client/versions' }
    }
    $normalizedMode = ([string]$NetworkingMode).Trim().ToLowerInvariant()
    $targetMode = if ($normalizedMode -eq 'mirrored') { 'mirrored-localhost' } else { 'wsl-ip' }
    $initialTarget = if ($targetMode -eq 'mirrored-localhost') { '127.0.0.1' } else { $lastIp }
    $config = [ordered]@{
        schema=4
        transport='windows-native-tcp-relay'
        distroName=$Name
        networkingMode=$normalizedMode
        targetMode=$targetMode
        lastTargetAddress=$initialTarget
        lastWslIp=$lastIp
        lastRefreshUtc=''
        services=$services
    }
    $json = $config | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($paths.Config, ($json + "`r`n"), [System.Text.UTF8Encoding]::new($false))
    return $paths
}
function Test-LatticeValeBridgeIpv4([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Value.Trim(), [ref]$parsed)) { return $false }
    if ($parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    if ([System.Net.IPAddress]::IsLoopback($parsed)) { return $false }
    if ($parsed.ToString().StartsWith('169.254.')) { return $false }
    return $true
}

function Invoke-LatticeValeBridgeRefresh([object]$Paths, [int]$WaitSeconds = 120) {
    # Start the persistent Windows-native relay and verify it with bounded, visible
    # progress. v13.13.0 could appear frozen here for up to 900 seconds because the
    # helper invoked stack recovery before probing healthy backends and the parent
    # emitted no heartbeat while waiting.
    try {
        Start-ScheduledTask -TaskName $Paths.TaskName -ErrorAction Stop
    } catch {
        Write-Warning "Windows WSL native relay task could not be started: $($_.Exception.Message)"
        return $false
    }

    $startedUtc = [DateTime]::UtcNow
    $deadline = $startedUtc.AddSeconds([Math]::Max(5,$WaitSeconds))
    $lastHeartbeat = [DateTime]::MinValue
    do {
        $recordedTarget = Get-LatticeValeBridgeLastTargetAddress $Paths
        if (-not [string]::IsNullOrWhiteSpace($recordedTarget)) {
            try {
                $cfg = Get-Content -LiteralPath $Paths.Config -Raw | ConvertFrom-Json
                $allReady = $true
                foreach ($service in @($cfg.services | Where-Object { $_.enabled -eq $true })) {
                    $bridgePort = [int]$service.bridgePort
                    $probePath = [string]$service.probePath
                    if ([string]::IsNullOrWhiteSpace($probePath)) { $probePath = '/' }
                    if (-not (Test-LocalTcpPort $bridgePort)) { $allReady = $false; break }
                    if (-not (Test-HttpEndpointNoProxy "http://127.0.0.1:$bridgePort$probePath" 1)) { $allReady = $false; break }
                }
                if ($allReady) { return $true }
            } catch { }
        }

        $elapsed = ([DateTime]::UtcNow - $startedUtc).TotalSeconds
        $task = Get-ScheduledTask -TaskName $Paths.TaskName -ErrorAction SilentlyContinue
        if ($elapsed -ge 5 -and (-not $task -or [string]$task.State -ne 'Running')) {
            $taskResult = $null
            try { $taskResult = (Get-ScheduledTaskInfo -TaskName $Paths.TaskName -ErrorAction Stop).LastTaskResult } catch { }
            $tail = Get-LatticeValeBridgeLogTail $Paths 8
            $detail = if ($null -ne $taskResult) { " LastTaskResult=$taskResult." } else { '' }
            if ($tail) { $detail += " Relay log: $tail" }
            Write-Warning "Windows WSL native relay task exited before its listeners became ready.$detail"
            return $false
        }

        if (([DateTime]::UtcNow - $lastHeartbeat).TotalSeconds -ge 10) {
            $stateText = if ($task) { [string]$task.State } else { 'Missing' }
            Write-Info ("Waiting for Windows-native WSL relay ({0}s elapsed; task={1})..." -f [int]$elapsed,$stateText)
            $lastHeartbeat = [DateTime]::UtcNow
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)

    $recordedTarget = Get-LatticeValeBridgeLastTargetAddress $Paths
    $tail = Get-LatticeValeBridgeLogTail $Paths 8
    if ([string]::IsNullOrWhiteSpace($recordedTarget)) {
        Write-Warning 'Windows WSL native relay did not record a usable backend target before the bounded verification deadline.'
    } else {
        Write-Warning "Windows WSL native relay recorded backend target $recordedTarget, but one or more localhost relay HTTP endpoints did not become ready before the bounded verification deadline."
    }
    if ($tail) { Write-Warning "Windows WSL native relay log tail: $tail" }
    return $false
}
function Get-LatticeValeRelayPowerShellCandidates {
    # The manual relay that proved this transport on the reference machine ran
    # under PowerShell 7. Prefer pwsh when installed, but retain Windows PowerShell
    # 5.1 as a compatibility fallback only after the relay self-test succeeds.
    $items = [System.Collections.Generic.List[string]]::new()
    try {
        $pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
        if ($pwsh -and (Test-Path -LiteralPath $pwsh.Source -PathType Leaf)) { $items.Add([string]$pwsh.Source) }
    } catch { }
    try {
        if ([string]$PSVersionTable.PSEdition -eq 'Core') {
            $currentPwsh = Join-Path $PSHOME 'pwsh.exe'
            if ((Test-Path -LiteralPath $currentPwsh -PathType Leaf) -and -not $items.Contains($currentPwsh)) { $items.Insert(0,$currentPwsh) }
        }
    } catch { }
    $windowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if ((Test-Path -LiteralPath $windowsPowerShell -PathType Leaf) -and -not $items.Contains($windowsPowerShell)) { $items.Add($windowsPowerShell) }
    return $items.ToArray()
}

function Get-LatticeValeRelayArguments([object]$Paths, [bool]$EnsureStackRunning, [switch]$SelfTest) {
    # The native relay is intentionally long-running. Always request a hidden
    # console window so starting it from manage.sh / Task Scheduler never leaves
    # a visible PowerShell window that a user can accidentally close.
    $relayWaitSeconds = if ($SelfTest) { '30' } else { '120' }
    $relayArgs = @('-NoProfile','-NonInteractive','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',$Paths.Script,'-ConfigPath',$Paths.Config,'-WaitSeconds',$relayWaitSeconds,'-RefreshSeconds','15')
    if ($EnsureStackRunning) { $relayArgs += '-EnsureDistroRunning' }
    if ($SelfTest) { $relayArgs += '-SelfTest' }
    return [string[]]$relayArgs
}

function Select-LatticeValeRelayPowerShell([object]$Paths, [bool]$EnsureStackRunning) {
    $failures = [System.Collections.Generic.List[string]]::new()
    foreach ($engine in @(Get-LatticeValeRelayPowerShellCandidates)) {
        $probe = Invoke-NativeProcessCapture $engine (Get-LatticeValeRelayArguments $Paths $EnsureStackRunning -SelfTest) 45
        if ($probe.Success) {
            Add-Content -LiteralPath (Join-Path $Paths.Directory 'native-relay.log') -Value ("{0} Relay engine self-test passed: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$engine) -Encoding UTF8
            return $engine
        }
        $detail = if ($probe.TimedOut) { 'timed out' } elseif (-not [string]::IsNullOrWhiteSpace($probe.Text)) { $probe.Text.Trim() } else { "exit code $($probe.ExitCode)" }
        if ($detail.Length -gt 500) { $detail = $detail.Substring(0,500) + '...' }
        $failures.Add("$engine => $detail")
    }
    $joined = if ($failures.Count -gt 0) { $failures -join ' | ' } else { 'no PowerShell engine candidate was found' }
    Write-Warning "No available PowerShell engine passed the Windows-native relay self-test. $joined"
    return ''
}

function Register-LatticeValeBridgeRefreshTask([object]$Paths, [bool]$StartAtLogon, [bool]$EnsureStackRunning) {
    try {
        $powershell = Select-LatticeValeRelayPowerShell $Paths $EnsureStackRunning
        if ([string]::IsNullOrWhiteSpace($powershell)) { return $false }
        # This task is intentionally long-running. Use the same elevated interactive
        # user context that proved reliable during live troubleshooting. PowerShell 7
        # is preferred when available; Windows PowerShell 5.1 is accepted only when
        # this exact relay/config passes a bounded self-test under that engine.
        $argLine = (((Get-LatticeValeRelayArguments $Paths $EnsureStackRunning) | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
        $action = New-ScheduledTaskAction -Execute $powershell -Argument $argLine -WorkingDirectory $Paths.Directory
        $windowsIdentity = Get-CurrentWindowsIdentityName
        $principal = New-ScheduledTaskPrincipal -UserId $windowsIdentity -LogonType Interactive -RunLevel Highest
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
        if ($StartAtLogon) {
            $atLogon = New-ScheduledTaskTrigger -AtLogOn -User $windowsIdentity
            Register-ScheduledTask -TaskName $Paths.TaskName -Action $action -Trigger $atLogon -Principal $principal -Settings $settings -Force | Out-Null
        } else {
            # Triggerless tasks remain supported for compatibility, but v13.15 normally starts
            # the relay at logon even in manual-stack mode. The relay itself does not
            # start or keep WSL alive unless -EnsureDistroRunning was explicitly granted.
            Register-ScheduledTask -TaskName $Paths.TaskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
        }
        $mode = if ($StartAtLogon -and $EnsureStackRunning) { 'at-logon stack recovery' } elseif ($StartAtLogon) { 'at-logon passive relay' } else { 'on-demand passive relay' }
        Add-Content -LiteralPath (Join-Path $Paths.Directory 'native-relay.log') -Value ("{0} Registered relay task '{1}' using {2} at Highest run level ({3})." -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$Paths.TaskName,$powershell,$mode) -Encoding UTF8
        Write-Info "Registered Windows-native relay task '$($Paths.TaskName)' using $powershell ($mode mode)."
        return $true
    } catch {
        Write-Warning "The Windows-native WSL relay task could not be created: $($_.Exception.Message). Tailscale exposure was not claimed as configured."
        return $false
    }
}
function Remove-LatticeValeBridgeSupport([string]$Name, [switch]$PreserveArtifacts) {
    $paths = Get-LatticeValeBridgePaths $Name
    $config = $null
    if (Test-Path -LiteralPath $paths.Config -PathType Leaf) {
        try { $config = Get-Content -LiteralPath $paths.Config -Raw | ConvertFrom-Json } catch { }
    }

    Stop-ScheduledTask -TaskName $paths.TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $paths.TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 250

    # Migration cleanup only: v13.12.x used netsh portproxy. Remove a legacy rule
    # solely when its address/ports still match installer metadata; never touch an
    # unknown administrator-owned portproxy rule.
    $transport = if ($config -and $config.PSObject.Properties.Name -contains 'transport') { [string]$config.transport } else { '' }
    if ($config -and $transport -ne 'windows-native-tcp-relay') {
        $rules = @(Get-WindowsPortProxyRules)
        $lastIp = [string]$config.lastWslIp
        foreach ($service in @($config.services)) {
            $bridgePort = [int]$service.bridgePort
            $backendPort = [int]$service.backendPort
            $matching = @($rules | Where-Object { $_.ListenAddress -eq '127.0.0.1' -and $_.ListenPort -eq $bridgePort })
            if ($matching.Count -eq 1 -and $matching[0].ConnectPort -eq $backendPort -and ($matching[0].ConnectAddress -eq $lastIp -or [string]::IsNullOrWhiteSpace($lastIp))) {
                & (Join-Path $env:SystemRoot 'System32\netsh.exe') interface portproxy delete v4tov4 "listenport=$bridgePort" 'listenaddress=127.0.0.1' 'protocol=tcp' | Out-Null
            } elseif ($matching.Count -gt 0) {
                Write-Warning "Legacy Windows bridge port $bridgePort no longer matches installer-owned metadata and was left untouched."
            }
        }
    }

    if ($PreserveArtifacts) {
        Write-Info "Preserved failed relay script/config for diagnostics: $($paths.Script) ; $($paths.Config)"
        return
    }
    Remove-Item -LiteralPath $paths.Config,$paths.Script -Force -ErrorAction SilentlyContinue
    # Remove the old v13.12 helper only from LatticeVale's own application-data directory.
    Remove-Item -LiteralPath (Join-Path $paths.Directory 'Refresh-HermesWslBridge.ps1') -Force -ErrorAction SilentlyContinue
}

function Write-LatticeValeNativeOllamaBridgeConfig([string]$Name, [int]$BridgePort, [string]$TargetAddress = '127.0.0.1', [int]$TargetPort = 11434, [string]$StackPath = '') {
    if ($BridgePort -lt 1 -or $BridgePort -gt 65535) { throw "Invalid native Ollama bridge port: $BridgePort" }
    if ($TargetPort -lt 1 -or $TargetPort -gt 65535) { throw "Invalid native Ollama target port: $TargetPort" }
    if ([string]::IsNullOrWhiteSpace($TargetAddress)) { throw 'Native Ollama target address is empty.' }
    $paths = Get-LatticeValeNativeServicePaths $Name
    New-Item -ItemType Directory -Path $paths.Directory -Force | Out-Null
    $source = Join-Path $PSScriptRoot 'windows\LatticeVale-WindowsNativeServiceRelay.ps1'
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Native Windows service relay source is missing: $source" }
    Copy-Item -LiteralPath $source -Destination $paths.Script -Force
    $config = [ordered]@{
        schema = 1
        distroName = $Name
        stackPath = $StackPath
        ruleKey = $paths.RuleKey
        services = @(
            [ordered]@{
                label = 'Ollama'
                enabled = $true
                listenPort = $BridgePort
                targetAddress = $TargetAddress
                targetPort = $TargetPort
                probePath = '/api/version'
            }
        )
    }
    $json = $config | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($paths.Config, ($json + "`r`n"), [System.Text.UTF8Encoding]::new($false))
    return $paths
}

function Get-LatticeValeNativeServiceRelayArguments([object]$Paths, [switch]$SelfTest) {
    $relayArgs = @('-NoProfile','-NonInteractive','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',$Paths.Script,'-ConfigPath',$Paths.Config,'-WaitSeconds','60','-RefreshSeconds','15')
    if ($SelfTest) { $relayArgs += '-SelfTest' }
    return [string[]]$relayArgs
}

function Select-LatticeValeNativeServicePowerShell([object]$Paths) {
    $failures = [System.Collections.Generic.List[string]]::new()
    foreach ($engine in @(Get-LatticeValeRelayPowerShellCandidates)) {
        $probe = Invoke-NativeProcessCapture $engine (Get-LatticeValeNativeServiceRelayArguments $Paths -SelfTest) 45
        if ($probe.Success) {
            Add-Content -LiteralPath $Paths.Log -Value ("{0} Native-service relay engine self-test passed: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$engine) -Encoding UTF8
            return $engine
        }
        $detail = if ($probe.TimedOut) { 'timed out' } elseif (-not [string]::IsNullOrWhiteSpace($probe.Text)) { $probe.Text.Trim() } else { "exit code $($probe.ExitCode)" }
        if ($detail.Length -gt 500) { $detail = $detail.Substring(0,500) + '...' }
        $failures.Add("$engine => $detail")
    }
    $joined = if ($failures.Count -gt 0) { $failures -join ' | ' } else { 'no PowerShell engine candidate was found' }
    Write-Warning "No available PowerShell engine passed the native Windows service relay self-test. $joined"
    return ''
}

function Register-LatticeValeNativeServiceTask([object]$Paths, [bool]$StartAtLogon) {
    try {
        Stop-ScheduledTask -TaskName $Paths.TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $Paths.TaskName -Confirm:$false -ErrorAction SilentlyContinue
        $powershell = Select-LatticeValeNativeServicePowerShell $Paths
        if ([string]::IsNullOrWhiteSpace($powershell)) { return $false }
        $argLine = (((Get-LatticeValeNativeServiceRelayArguments $Paths) | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
        $action = New-ScheduledTaskAction -Execute $powershell -Argument $argLine -WorkingDirectory $Paths.Directory
        $windowsIdentity = Get-CurrentWindowsIdentityName
        $principal = New-ScheduledTaskPrincipal -UserId $windowsIdentity -LogonType Interactive -RunLevel Highest
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
        if ($StartAtLogon) {
            $trigger = New-ScheduledTaskTrigger -AtLogOn -User $windowsIdentity
            Register-ScheduledTask -TaskName $Paths.TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
        } else {
            Register-ScheduledTask -TaskName $Paths.TaskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
        }
        Write-Info "Registered native Windows service bridge task '$($Paths.TaskName)' using $powershell$(if ($StartAtLogon) { ' (at logon)' } else { ' (on demand)' })."
        return $true
    } catch {
        Write-Warning "The native Windows service bridge task could not be created: $($_.Exception.Message)"
        return $false
    }
}

function Test-LatticeValeNativeOllamaBridge([string]$Name, [int]$BridgePort) {
    $hostAddress = Get-WindowsHostIpv4ForWsl $Name
    if (-not (Test-LatticeValeBridgeIpv4 $hostAddress)) { return $false }
    $script = @'
set -e
host="$1"; port="$2"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
if command -v curl >/dev/null 2>&1; then
  exec curl -fsS --noproxy '*' --connect-timeout 3 --max-time 7 "http://${host}:${port}/api/version" -o /dev/null
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 - "$host" "$port" <<'PY_NATIVE_OLLAMA'
import sys,urllib.request
host=sys.argv[1]; port=int(sys.argv[2])
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(f'http://{host}:{port}/api/version', timeout=5) as r:
    if not r.read(1024): raise SystemExit(3)
PY_NATIVE_OLLAMA
fi
exec 3<>"/dev/tcp/${host}/${port}"
printf 'GET /api/version HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n' "$host" >&3
IFS= read -r status <&3 || true
case "$status" in *' 200 '*) exit 0;; *) exit 1;; esac
'@
    $probe = Invoke-WslDirectCapture $Name 'root' 'bash' @('-lc',$script,'bash',$hostAddress,[string]$BridgePort) 20
    return [bool]$probe.Success
}

function Start-LatticeValeNativeOllamaBridge([object]$Paths, [string]$Name, [int]$BridgePort, [int]$WaitSeconds = 45) {
    try { Start-ScheduledTask -TaskName $Paths.TaskName -ErrorAction Stop } catch {
        Write-Warning "Native Windows Ollama bridge task could not be started: $($_.Exception.Message)"
        return $false
    }
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(5,$WaitSeconds))
    do {
        if (Test-LatticeValeNativeOllamaBridge $Name $BridgePort) { return $true }
        $task = Get-ScheduledTask -TaskName $Paths.TaskName -ErrorAction SilentlyContinue
        if (-not $task -or ([string]$task.State -notin @('Running','Ready'))) { break }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    $tail = ''
    if (Test-Path -LiteralPath $Paths.Log -PathType Leaf) {
        try { $tail = ((Get-Content -LiteralPath $Paths.Log -Tail 8 -ErrorAction Stop) -join ' | ') } catch { }
    }
    if ($tail) { Write-Warning "Native Windows service bridge log tail: $tail" }
    return $false
}

function Remove-LatticeValeNativeServiceSupport([string]$Name) {
    $paths = Get-LatticeValeNativeServicePaths $Name
    Stop-ScheduledTask -TaskName $paths.TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $paths.TaskName -Confirm:$false -ErrorAction SilentlyContinue
    if ((Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallRule -ErrorAction SilentlyContinue)) {
        foreach ($rule in @(Get-NetFirewallRule -Group 'LatticeVale' -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "LatticeValeNativeBridge-$($paths.RuleKey)-*" })) {
            $rule | Remove-NetFirewallRule -ErrorAction SilentlyContinue
        }
    }
    if ((Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) -and (Get-Command Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
        foreach ($rule in @(Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue | Where-Object { ([string]$_.Name) -like "LatticeValeNativeBridge-HyperV-$($paths.RuleKey)-*" })) {
            $rule | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $paths.Config -Force -ErrorAction SilentlyContinue
}

function Get-LatticeValeBridgeLastWslIp([object]$Paths) {
    try {
        if (Test-Path -LiteralPath $Paths.Config -PathType Leaf) {
            $cfg = Get-Content -LiteralPath $Paths.Config -Raw | ConvertFrom-Json
            return [string]$cfg.lastWslIp
        }
    } catch { }
    return ''
}

function Get-LatticeValeBridgeLastTargetAddress([object]$Paths) {
    try {
        if (Test-Path -LiteralPath $Paths.Config -PathType Leaf) {
            $cfg = Get-Content -LiteralPath $Paths.Config -Raw | ConvertFrom-Json
            if ($cfg.PSObject.Properties.Name -contains 'lastTargetAddress' -and -not [string]::IsNullOrWhiteSpace([string]$cfg.lastTargetAddress)) {
                return [string]$cfg.lastTargetAddress
            }
            return [string]$cfg.lastWslIp
        }
    } catch { }
    return ''
}

function Set-SynapsePublicBaseUrl([string]$Name, [string]$User, [string]$LinuxHome, [string]$Url) {
    if ([string]::IsNullOrWhiteSpace($Url)) { return $false }
    $url = $Url.TrimEnd('/') + '/'
    $code = @'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); url=sys.argv[2]
if not p.is_file(): raise SystemExit('homeserver.yaml is missing')
text=p.read_text(encoding='utf-8')
pattern=re.compile(r'(?m)^public_baseurl\s*:\s*(.*?)\s*$')
m=pattern.search(text)
if m and m.group(1).strip().rstrip('/')+'/' == url.rstrip('/')+'/':
    print('UNCHANGED')
    raise SystemExit(0)
if m:
    text=pattern.sub('public_baseurl: '+url,text,count=1)
else:
    if text and not text.endswith('\n'): text+='\n'
    text+='public_baseurl: '+url+'\n'
p.write_text(text,encoding='utf-8')
p.chmod(0o600)
print('CHANGED')
'@
    $path = "$LinuxHome/hermes-stack/data/synapse/homeserver.yaml"
    $probe = Invoke-WslDirectCapture $Name $User 'python3' @('-c',$code,$path,$url) 30
    if (-not $probe.Success) {
        Write-Warning "Could not update Synapse public_baseurl to '$url'."
        return $false
    }
    if ([string]$probe.Text -match '(?m)^UNCHANGED\s*$') {
        return $true
    }
    $restart = Invoke-WslDirectCapture $Name $User 'bash' @('-lc','cd ~/hermes-stack && docker compose restart synapse >/dev/null') 120
    if (-not $restart.Success) {
        Write-Warning 'Synapse public_baseurl was updated, but Synapse could not be restarted automatically.'
        return $false
    }
    # A restart can briefly accept TCP before the Matrix client API is ready. Wait for
    # the same application-level endpoint Element uses before allowing the installer
    # to run the Tailscale end-to-end verification.
    $ready = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', 'cd ~/hermes-stack; p=$(sed -n "s/^MATRIX_HOST_PORT=//p" .env | head -n1); test -n "$p" || p=8008; for i in $(seq 1 120); do curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:${p}/_matrix/client/versions" >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1') 140
    if (-not $ready.Success) {
        Write-Warning 'Synapse restarted but its Matrix client endpoint did not become ready within the bounded startup window.'
        return $false
    }
    return $true
}

function Test-HttpsEndpoint([string]$Url, [int]$Attempts = 8) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $request = [System.Net.HttpWebRequest]::Create($Url)
            $request.Method = 'GET'; $request.Timeout = 5000; $request.AllowAutoRedirect = $false; $request.Proxy = $null
            try {
                $response = [System.Net.HttpWebResponse]$request.GetResponse()
                $code = [int]$response.StatusCode; $response.Close()
                if ($code -ge 200 -and $code -lt 500) { return $true }
            } catch [System.Net.WebException] {
                if ($_.Exception.Response) {
                    $code = [int]([System.Net.HttpWebResponse]$_.Exception.Response).StatusCode
                    $_.Exception.Response.Close()
                    if ($code -ge 200 -and $code -lt 500) { return $true }
                }
            }
        } catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Test-HttpEndpointNoProxy([string]$Url, [int]$Attempts = 3) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $request = [System.Net.HttpWebRequest]::Create($Url)
            $request.Method = 'GET'; $request.Timeout = 5000; $request.AllowAutoRedirect = $false; $request.Proxy = $null
            try {
                $response = [System.Net.HttpWebResponse]$request.GetResponse()
                $code = [int]$response.StatusCode; $response.Close()
                if ($code -ge 200 -and $code -lt 500) { return $true }
            } catch [System.Net.WebException] {
                if ($_.Exception.Response) {
                    $code = [int]([System.Net.HttpWebResponse]$_.Exception.Response).StatusCode
                    $_.Exception.Response.Close()
                    if ($code -ge 200 -and $code -lt 500) { return $true }
                }
            }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    return $false
}
function Get-TailscaleHttpsUrl([string]$DnsName, [int]$Port) {
    if ([string]::IsNullOrWhiteSpace($DnsName) -or $Port -le 0) { return '' }
    if ($Port -eq 443) { return "https://$DnsName" }
    return "https://$DnsName`:$Port"
}

function Get-TailscaleInfoFromWsl([string]$Name, [string]$User) {
    $result = @{}
    $probe = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', 'test -f ~/hermes-stack/.tailscale-info && cat ~/hermes-stack/.tailscale-info')
    if (-not $probe.Success) { return $result }
    $payload = $probe.Text
    foreach ($line in ($payload -split "`r?`n")) {
        $text = ([string]$line).Trim()
        if ($text -match '^([A-Z0-9_]+)=(.*)$') { $result[$Matches[1]] = $Matches[2] }
    }
    return $result
}

function Set-TailscaleInfoInWsl(
    [string]$Name,
    [string]$User,
    [string]$DnsName,
    [int]$DashboardPort,
    [int]$MatrixPort,
    [int]$DashboardBridgePort = 0,
    [int]$MatrixBridgePort = 0,
    [string]$WslBridgeIp = '',
    [string]$BridgeTaskName = '',
    [bool]$BridgeAutoStart = $false,
    [string]$BridgeTargetAddress = '',
    [string]$WslNetworkingMode = '',
    [string]$WslNetworkingModeOwner = ''
) {
    $content = @(
        'MODE=windows-host',
        'BRIDGE_MODE=windows-native-tcp-relay',
        "TAILSCALE_DNS=$DnsName",
        "DASHBOARD_HTTPS_PORT=$DashboardPort",
        "MATRIX_HTTPS_PORT=$MatrixPort",
        "DASHBOARD_BRIDGE_PORT=$DashboardBridgePort",
        "MATRIX_BRIDGE_PORT=$MatrixBridgePort",
        "WSL_BRIDGE_IP=$WslBridgeIp",
        "BRIDGE_TARGET_ADDRESS=$BridgeTargetAddress",
        "WSL_NETWORKING_MODE=$WslNetworkingMode",
        "WSL_NETWORKING_MODE_OWNER=$WslNetworkingModeOwner",
        "BRIDGE_TASK_NAME=$BridgeTaskName",
        "BRIDGE_AUTOSTART=$($BridgeAutoStart.ToString().ToLowerInvariant())"
    ) -join "`n"
    $content += "`n"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($content))
    $probe = Invoke-WslDirectCapture $Name $User 'bash' @('-lc', "umask 077; echo '$encoded' | base64 -d > ~/hermes-stack/.tailscale-info") 30
    if (-not $probe.Success) {
        $detail = Get-SafeDiagnosticExcerpt $probe.Text 320
        if (-not $detail) { $detail = 'WSL metadata write failed or timed out' }
        throw "Could not save installer-owned Tailscale metadata inside WSL: $detail"
    }
}

function Remove-TailscaleInfoInWsl([string]$Name, [string]$User) {
    [void](Invoke-WslDirectCapture $Name $User 'bash' @('-lc', 'rm -f ~/hermes-stack/.tailscale-info'))
}

function Add-WindowsTailscaleServeJsonState(
    [object]$Config,
    [int]$Port,
    [System.Collections.Generic.List[string]]$Targets,
    [ref]$InUse
) {
    if ($null -eq $Config) { return }

    # Legacy/device Serve JSON shape used by `tailscale serve status --json`.
    $configs = @($Config)
    if ($Config.PSObject.Properties.Name -contains 'Services' -and $Config.Services) {
        foreach ($service in $Config.Services.PSObject.Properties) { $configs += $service.Value }
    }
    foreach ($cfg in $configs) {
        if ($null -eq $cfg) { continue }
        if ($cfg.PSObject.Properties.Name -contains 'TCP' -and $cfg.TCP) {
            foreach ($tcp in $cfg.TCP.PSObject.Properties) {
                if ([string]$tcp.Name -eq [string]$Port) { $InUse.Value = $true }
            }
        }
        if ($cfg.PSObject.Properties.Name -contains 'Web' -and $cfg.Web) {
            foreach ($web in $cfg.Web.PSObject.Properties) {
                $hostPort = [string]$web.Name
                if ($hostPort -notmatch (':' + [regex]::Escape([string]$Port) + '$')) { continue }
                $InUse.Value = $true
                $handlers = $web.Value.Handlers
                if ($handlers) {
                    foreach ($handler in $handlers.PSObject.Properties) {
                        $proxy = $handler.Value.Proxy
                        if ($proxy) { $Targets.Add([string]$proxy) }
                    }
                }
            }
        }
    }

    # Current Tailscale Services/get-config shape:
    # { "services": { "svc:name": { "endpoints": { "tcp:443": "http://127.0.0.1:..." }}}}
    foreach ($servicesPropertyName in @('services','Services')) {
        if (-not ($Config.PSObject.Properties.Name -contains $servicesPropertyName)) { continue }
        $servicesNode = $Config.PSObject.Properties[$servicesPropertyName].Value
        if (-not $servicesNode) { continue }
        foreach ($service in $servicesNode.PSObject.Properties) {
            $serviceValue = $service.Value
            if (-not $serviceValue) { continue }
            foreach ($endpointPropertyName in @('endpoints','Endpoints')) {
                if (-not ($serviceValue.PSObject.Properties.Name -contains $endpointPropertyName)) { continue }
                $endpoints = $serviceValue.PSObject.Properties[$endpointPropertyName].Value
                if (-not $endpoints) { continue }
                foreach ($endpoint in $endpoints.PSObject.Properties) {
                    $endpointName = [string]$endpoint.Name
                    if ($endpointName -notmatch ('(^|:)' + [regex]::Escape([string]$Port) + '$')) { continue }
                    $InUse.Value = $true
                    if ($endpoint.Value -is [string] -and -not [string]::IsNullOrWhiteSpace([string]$endpoint.Value)) {
                        $Targets.Add([string]$endpoint.Value)
                    }
                }
            }
        }
    }
}

function Test-WindowsTailscaleBackendTarget([string]$Target, [int]$BackendPort) {
    if ([string]::IsNullOrWhiteSpace($Target) -or $BackendPort -le 0) { return $false }
    $text = $Target.Trim().TrimEnd('/')
    $portText = [regex]::Escape([string]$BackendPort)
    return [bool]($text -match "^(?i:http://)?(?:127\\.0\\.0\\.1|localhost):$portText$")
}

function Get-WindowsTailscaleServePortState(
    [string]$TailscaleExe,
    [int]$Port,
    [int]$ExpectedBackendPort = 0
) {
    $result = [ordered]@{
        Known = $false
        InUse = $false
        MatchesExpected = $false
        Targets = @()
    }
    if (-not $TailscaleExe -or $Port -le 0) { return [pscustomobject]$result }

    $targets = [System.Collections.Generic.List[string]]::new()
    $inUse = $false

    # Tailscale documents that `serve status --json` and the full Serve configuration
    # can differ. Inspect both when available; older clients that do not implement
    # get-config simply fall back to status JSON. This remains read-only/fail-closed.
    foreach ($serveArgs in @(
        @('serve','status','--json'),
        @('serve','get-config','--all')
    )) {
        try {
            $serveProbe = Invoke-NativeProcessCapture $TailscaleExe $serveArgs 15
            $raw = ([string]$serveProbe.StdOut).Trim()
            if (-not $serveProbe.Success -or [string]::IsNullOrWhiteSpace($raw)) { continue }
            $status = $raw | ConvertFrom-Json -ErrorAction Stop
            $result.Known = $true
            Add-WindowsTailscaleServeJsonState $status $Port $targets ([ref]$inUse)
        } catch {
            # Continue to the other read-only representation. Unknown remains conservative
            # if neither command can be parsed successfully.
        }
    }

    $result.InUse = $inUse
    $result.Targets = @($targets | Select-Object -Unique)
    if ($ExpectedBackendPort -gt 0 -and $result.InUse) {
        foreach ($target in $result.Targets) {
            if (Test-WindowsTailscaleBackendTarget ([string]$target) $ExpectedBackendPort) {
                $result.MatchesExpected = $true
                break
            }
        }
    }
    return [pscustomobject]$result
}

function Disable-WindowsTailscaleServe(
    [string]$TailscaleExe,
    [int]$Port,
    [int]$BackendPort,
    [string]$Label
) {
    if (-not $TailscaleExe -or $Port -le 0) { return $false }
    $state = Get-WindowsTailscaleServePortState $TailscaleExe $Port $BackendPort
    if (-not $state.Known) {
        Write-Warning "Could not safely inspect Tailscale Serve HTTPS port $Port. The prior $Label mapping was left untouched; check 'tailscale serve status --json' and 'tailscale serve get-config --all'."
        return $false
    }
    if (-not $state.InUse) { return $true }
    if (-not $state.MatchesExpected) {
        $targets = if ($state.Targets.Count -gt 0) { $state.Targets -join ', ' } else { 'an unknown/different target' }
        Write-Warning "Tailscale Serve HTTPS port $Port no longer points to the installer-owned $Label backend; it now references $targets. It was left untouched."
        return $false
    }

    $serveOff = Invoke-NativeProcessPassthrough $TailscaleExe @('serve',"--https=$Port",'off') 30
    if (-not $serveOff.Success) {
        Write-Warning "Could not remove the prior $Label Tailscale Serve mapping on HTTPS port $Port. Check 'tailscale serve status --json' in Windows."
        return $false
    }
    return $true
}

function Resolve-UnownedTailscaleServeConflict(
    [string]$TailscaleExe,
    [int]$HttpsPort,
    [int]$BackendPort,
    [string]$Label,
    [object]$PortState
) {
    if (-not $PortState -or -not $PortState.Known -or -not $PortState.InUse) { return 'none' }
    $targets = if ($PortState.Targets.Count -gt 0) { $PortState.Targets -join ', ' } else { 'an unknown target' }
    if ($PortState.MatchesExpected) {
        if (Read-Choice "Adopt the existing matching Tailscale $Label rule on HTTPS port $HttpsPort?" "The existing untracked rule already proxies to the exact LatticeVale Windows bridge http://127.0.0.1:$BackendPort. Yes records it as installer-owned for future repair/cleanup." 'No leaves the existing rule untouched and marks this remote exposure partial.' $true) {
            return 'adopt'
        }
        return 'leave'
    }
    if (-not (Read-Choice "Replace the existing untracked Tailscale rule on HTTPS port $HttpsPort for $Label?" "Current target(s): $targets. Yes removes ONLY this HTTPS Serve listener and replaces it with LatticeVale's http://127.0.0.1:$BackendPort bridge. Use this when migrating a manual/legacy rule." 'No leaves the existing rule untouched and skips this LatticeVale remote exposure.' $false)) {
        return 'leave'
    }
    $serveOff = Invoke-NativeProcessPassthrough $TailscaleExe @('serve',"--https=$HttpsPort",'off') 30
    if (-not $serveOff.Success) {
        Write-Warning "Could not remove the user-approved existing Tailscale rule on HTTPS port $HttpsPort."
        return 'leave'
    }
    return 'replace'
}

function Enable-WindowsTailscaleServe(
    [string]$TailscaleExe,
    [int]$HttpsPort,
    [int]$BackendPort,
    [string]$Label
) {
    if (-not (Test-LocalTcpPort $BackendPort)) {
        Write-Warning "$Label is not reachable from Windows at 127.0.0.1:$BackendPort. Its Tailscale exposure was skipped; the local stack remains installed."
        return $false
    }
    $serveOn = Invoke-NativeProcessPassthrough $TailscaleExe @('serve','--bg',"--https=$HttpsPort","http://127.0.0.1:$BackendPort") 30
    if (-not $serveOn.Success) {
        Write-Warning "Tailscale Serve could not expose $Label on HTTPS port $HttpsPort. The local service still works."
        return $false
    }
    return $true
}


function Test-WingetPackageInstalled([string]$Id) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { return $null }
    try {
        $probe = Invoke-NativeProcessCapture 'winget.exe' @('list','--exact','--id',$Id,'--disable-interactivity') 30
        if (-not $probe.Success) { return $null }
        $text = [string]$probe.Text
        return [bool]($text -match [regex]::Escape($Id))
    } catch { return $null }
}

function Show-WindowsRecoveryAudit([string]$Name, [string]$User, [object]$Options) {
    Write-Host "`n== Windows-side live audit ==" -ForegroundColor Cyan

    foreach ($pkg in @(
        @{ Label = 'Obsidian'; Id = 'Obsidian.Obsidian'; Selected = [bool](Get-OptionValue $Options 'obsidian' $false) }
    )) {
        if (-not $pkg.Selected) { Write-Info "$($pkg.Label): DISABLED"; continue }
        $present = Test-WingetPackageInstalled $pkg.Id
        if ($present -eq $true) { Write-Info "$($pkg.Label): CONFIGURED" }
        elseif ($present -eq $false) { Write-Info "$($pkg.Label): NOT_INSTALLED" }
        else { Write-Info "$($pkg.Label): UNKNOWN (winget inventory unavailable)" }
    }

    $taskExpected = [bool](Get-OptionValue $Options 'autoStart' $false)
    $taskName = Get-LatticeValeScheduledTaskName $Name
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($taskExpected) {
        Write-Info "Windows auto-start: $(if ($task) { "CONFIGURED ($($task.State))" } else { 'NOT_INSTALLED' })"
    } else {
        Write-Info "Windows auto-start: $(if ($task) { 'PARTIAL (installer task remains although option is disabled)' } else { 'DISABLED' })"
    }

    $shortcutExpected = [bool](Get-OptionValue $Options 'windowsShortcuts' $false)
    $shortcutHome = Get-LinuxUserHome $Name $User
    if ([string]::IsNullOrWhiteSpace($shortcutHome) -or -not $shortcutHome.StartsWith('/')) {
        throw "Could not determine the actual Linux home for '$User'; refusing to guess a /home/<user> path for Windows shortcuts."
    }
    $stackLinuxPathForShortcuts = "$($shortcutHome.TrimEnd('/'))/hermes-stack"
    $shortcutState = Get-LatticeValeDesktopShortcutState $Name $User $stackLinuxPathForShortcuts $shortcutExpected
    Write-Info "Windows desktop shortcuts: $($shortcutState.Status) - $($shortcutState.Detail)"

    $tailscaleExpected = [bool](Get-OptionValue $Options 'tailscale' $false)
    $tsExe = Get-WindowsTailscaleExe
    $tsInfo = Get-TailscaleInfoFromWsl $Name $User
    if (-not $tailscaleExpected) {
        if ($tsInfo.Count -gt 0) { Write-Info 'Windows Tailscale integration: PARTIAL (installer-owned mapping metadata remains)' }
        else { Write-Info 'Windows Tailscale integration: DISABLED' }
        return
    }
    if (-not $tsExe) { Write-Info 'Windows Tailscale integration: NOT_INSTALLED'; return }
    $tsStatus = Get-WindowsTailscaleStatus $tsExe
    if ($tsStatus.BackendState -ne 'Running') {
        Write-Info "Windows Tailscale integration: PARTIAL ($($tsStatus.BackendState))"
        return
    }
    Write-Info "Windows Tailscale client: RUNNING$(if ($tsStatus.DNSName) { " ($($tsStatus.DNSName))" } else { '' })"

    foreach ($mapping in @(
        @{ Label='Dashboard'; Selected=[bool](Get-OptionValue $Options 'tailscaleDashboard' $false); OptionPort=(Get-OptionTcpPort $Options 'tailscaleDashboardPort' 9443); Meta='DASHBOARD_HTTPS_PORT'; BridgeMeta='DASHBOARD_BRIDGE_PORT'; Bridge=(Get-OptionTcpPort $Options 'dashboardBridgePort' 19119) },
        @{ Label='Matrix'; Selected=[bool](Get-OptionValue $Options 'tailscaleMatrix' $false); OptionPort=(Get-OptionTcpPort $Options 'tailscaleMatrixPort' 443); Meta='MATRIX_HTTPS_PORT'; BridgeMeta='MATRIX_BRIDGE_PORT'; Bridge=(Get-OptionTcpPort $Options 'matrixBridgePort' 18008) }
    )) {
        if (-not $mapping.Selected) { Write-Info "Tailscale $($mapping.Label): DISABLED"; continue }
        $tracked = 0
        if ($tsInfo.ContainsKey($mapping.Meta)) { [void][int]::TryParse($tsInfo[$mapping.Meta], [ref]$tracked) }
        if ($tracked -le 0 -or $tracked -ne $mapping.OptionPort) {
            Write-Info "Tailscale $($mapping.Label): PARTIAL (requested HTTPS $($mapping.OptionPort) is not installer-tracked)"
            continue
        }
        $bridgePort = $mapping.Bridge
        if ($tsInfo.ContainsKey($mapping.BridgeMeta)) { [void][int]::TryParse($tsInfo[$mapping.BridgeMeta], [ref]$bridgePort) }
        $portState = Get-WindowsTailscaleServePortState $tsExe $tracked $bridgePort
        if ($portState.Known -and $portState.InUse -and $portState.MatchesExpected) {
            Write-Info "Tailscale $($mapping.Label): CONFIGURED (HTTPS $tracked -> Windows bridge $bridgePort)"
        } elseif ($portState.Known) {
            Write-Info "Tailscale $($mapping.Label): BROKEN/PARTIAL (HTTPS $tracked does not match the expected backend)"
        } else {
            Write-Info "Tailscale $($mapping.Label): UNKNOWN (Serve status unavailable)"
        }
    }
}

function Show-LatticeValeReadOnlyVerification([string]$Name, [string]$User, [string]$LinuxHome, [object]$Options) {
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host 'LatticeVale read-only verification results' -ForegroundColor Cyan
    Write-Host '============================================================' -ForegroundColor Cyan
    Write-Info 'Running a fresh bundled Linux stack audit now. This mode does not repair, restart, update, or rewrite the installation.'

    $freshAudit = Invoke-BundledStackAudit $Name $User $LinuxHome
    if (-not [string]::IsNullOrWhiteSpace([string]$freshAudit)) {
        Write-Host "`n== Linux / Docker / Hermes state ==" -ForegroundColor Cyan
        Write-Host ([string]$freshAudit).TrimEnd()
    } else {
        Write-Warning 'Linux stack audit could not be produced. This is a verification failure/limitation, not a successful empty audit.'
    }

    if ($null -ne $Options) {
        Show-WindowsRecoveryAudit $Name $User $Options
    } else {
        Write-Warning 'Saved install-options are unavailable, so Windows-side expected-state verification cannot be compared with installer intent.'
    }

    Write-Host "`n== Verification result ==" -ForegroundColor Cyan
    if (-not [string]::IsNullOrWhiteSpace([string]$freshAudit)) {
        $overall = [regex]::Match([string]$freshAudit, '(?im)^Overall:\s*([^\r\n]+)')
        if ($overall.Success) {
            Write-Host ("Linux overall state: {0}" -f $overall.Groups[1].Value.Trim())
        } else {
            Write-Host 'Linux overall state: audit completed; no Overall line was reported.'
        }
    } else {
        Write-Host 'Linux overall state: UNKNOWN (audit unavailable)' -ForegroundColor Yellow
    }
    Write-Host 'No changes were made.' -ForegroundColor Green
    Write-Host '============================================================' -ForegroundColor Cyan
    return $freshAudit
}

function Ensure-WindowsTailscaleConnected([string]$TailscaleExe) {
    $status = Get-WindowsTailscaleStatus $TailscaleExe
    if ($status.BackendState -eq 'Running') { return $status }

    Write-Warning "Windows Tailscale is installed but its current state is '$($status.BackendState)'."
    if ($status.BackendState -eq 'NeedsLogin') {
        if (-not (Read-ChoiceExplicit 'Log this Windows PC into Tailscale now?' 'Uses the normal Tailscale browser login and joins/reconnects this Windows node to your chosen tailnet.' 'Safe; Tailscale remote exposure is skipped and LatticeVale remains local-only.')) {
            return $status
        }
        & $TailscaleExe login | Out-Host
    } else {
        if (-not (Read-ChoiceExplicit 'Bring the existing Windows Tailscale client online now?' 'Runs tailscale up on the existing Windows client; use No if it is intentionally stopped or specially managed.' 'Safe; Tailscale remote exposure is skipped and LatticeVale remains local-only.')) {
            return $status
        }
        & $TailscaleExe up | Out-Host
    }

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        $status = Get-WindowsTailscaleStatus $TailscaleExe
        if ($status.BackendState -eq 'Running') { break }
    }
    return $status
}

Write-Step 'Preflight'
if (-not [string]::IsNullOrWhiteSpace($DistroName) -and ($DistroName.Length -gt 128 -or $DistroName -match '[\x00-\x1F"]')) {
    throw 'DistroName must be a valid registered WSL distribution name without control characters or double quotes.'
}
$compat = Get-LatticeValeCompatibility
$os = Get-CimInstance Win32_OperatingSystem
if ([int]$os.ProductType -ne 1) {
    throw "This installer release is validated for Windows 10/11 client editions, not Windows Server. Detected: $($os.Caption) (ProductType $($os.ProductType))."
}
if ([int]$os.BuildNumber -lt $compat.MinWindowsBuild) {
    throw "This bundle supports Windows 10/11 WSL2 environments and requires Windows build $($compat.MinWindowsBuild) or later. Detected build $($os.BuildNumber)."
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'A 64-bit Windows installation is required.'
}
try {
    $nativeArch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
} catch {
    $nativeArch = [string]$env:PROCESSOR_ARCHITEW6432
    if ([string]::IsNullOrWhiteSpace($nativeArch)) { $nativeArch = [string]$env:PROCESSOR_ARCHITECTURE }
    if ($nativeArch -match '^(?i:AMD64)$') { $nativeArch = 'X64' }
}
if ($nativeArch -ne 'X64') {
    throw "This installer build is validated for x64/AMD64 Windows + Ubuntu WSL2 only. Detected native architecture: $nativeArch. ARM64 is not treated as eligible until every bundled image is verified for it."
}
Write-Info "Windows build $($os.BuildNumber), $nativeArch"

# Fail before asking questions if the extracted bundle is incomplete.
$requiredBundleFiles = @(
    'VERSION.txt',
    'compatibility.conf',
    'linux\bootstrap.sh',
    'linux\cleanup-storage.sh',
    'stack\compose.yaml',
    'stack\Dockerfile.qmd',
    'stack\patch-qmd-bind.py',
    'stack\configure-stack.sh',
    'stack\manage.sh',
    'stack\state-audit.py',
    'stack\latticevale_readonly.py',
    'stack\repair-plan.py',
    'stack\audit-free.py',
    'stack\checkpoint-metadata.json',
    'stack\qmd-index-cycle.sh',
    'stack\directml-gateway.py',
    'stack\directml-gateway.sh',
    'stack\directml-requirements.txt',
    'windows\LatticeVale-WslNativeRelay.ps1',
    'windows\LatticeVale-WindowsNativeServiceRelay.ps1',
    'windows\LatticeVale-Shortcut.ps1'
)
foreach ($relativePath in $requiredBundleFiles) {
    $fullPath = Join-Path $PSScriptRoot $relativePath
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Installer bundle is incomplete. Missing companion file: $relativePath"
    }
}
$bundleVersion = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'VERSION.txt') -Raw).Trim()
if ($bundleVersion -notmatch '^[A-Za-z0-9._-]{1,64}$') {
    throw "VERSION.txt contains an invalid installer version identifier: '$bundleVersion'"
}
Write-Info "Installer bundle version: $bundleVersion"

$wslInfo = Get-WslCapabilities
$selectedDistro = Select-ExistingUbuntuDistro $DistroName $wslInfo.DistroNames
$DistroName = [string]$selectedDistro.Name
if ($DistroName.Length -gt 128 -or $DistroName -match '[\x00-\x1F"]') { throw "Selected WSL distro name '$DistroName' contains characters this installer cannot safely use." }
$registration = $selectedDistro.Registration

Write-Step 'Checking selected distro storage'
$existingVolume = Assert-LatticeValeStorageVolume $registration.BasePath -AllowManagedRepair:$selectedDistro.ManagedRepairEligible -AllowManagedCleanup:$selectedDistro.ManagedCleanupEligible
$DistroStoragePath = $registration.BasePath
Write-Info "Selected '$DistroName' is stored on $($existingVolume.Drive): $([math]::Round($existingVolume.Size / 1GB,1)) GB total, $([math]::Round($existingVolume.Free / 1GB,1)) GB free."
Write-Info "Registered WSL storage path: $DistroStoragePath"

$linuxUser = Select-ExistingLinuxUser $DistroName
$linuxHome = Get-LinuxUserHome $DistroName $linuxUser
if (-not $linuxHome) { throw "Could not determine the home directory for existing Ubuntu user '$linuxUser'." }
# Derive the managed stack path immediately after the selected user's home is known.
# Repair preflight uses this path before staging/bootstrap; assigning it only at the
# final summary previously passed an empty path to legacy-vault reconciliation.
$stackLinuxPath = "$($linuxHome.TrimEnd('/'))/hermes-stack"
if ([string]::IsNullOrWhiteSpace($stackLinuxPath) -or -not $stackLinuxPath.StartsWith('/') -or $stackLinuxPath -eq '/hermes-stack') {
    throw "Could not derive a safe managed stack path from Linux home '$linuxHome'."
}
$linuxHomeFs = Assert-LinuxNativeHomeFilesystem $DistroName $linuxUser
Write-Info "Linux home filesystem: $(Format-LinuxNativeFilesystemLabel $linuxHomeFs) - OK"

$stackState = Get-LatticeValeStackPathState $DistroName $linuxUser
# Low-space cleanup eligibility is granted at distro inventory time if any normal user owns a
# recognized managed stack. Reassert the ordinary fresh-install storage policy after the user is
# selected so a different/non-managed user cannot accidentally inherit that cleanup-only bypass.
if ($stackState -ne 'managed') {
    $selectedCompat = Get-LatticeValeCompatibility
    if ($existingVolume.Size -le ([int64]$selectedCompat.MinHostPartitionTotalGiBExclusive * 1GB) -or
        $existingVolume.Free -lt ([int64]$selectedCompat.MinHostPartitionFreeGiB * 1GB)) {
        throw "The selected Linux user does not own a recognized installer-managed LatticeVale stack, so the cleanup-only storage exception does not apply. Fresh/unrecognized installs still require a host partition over $($selectedCompat.MinHostPartitionTotalGiBExclusive) GB total with at least $($selectedCompat.MinHostPartitionFreeGiB) GB free."
    }
}
$existingOptions = $null
$installMode = 'fresh'
$resetCheckpoints = $false
$forceProviderSetup = $false
$forceProfileSetup = $false
$rebuildMatrixIdentity = $false
# v13.16 repair maintenance is additive and only applies to an existing installer-managed stack.
# Fresh installs keep the normal clean-install path; repair adds safe drift/storage maintenance.
$repairMaintenance = $false
# Explicit Update / repair forces the current bundle's managed software refresh now instead of waiting for the periodic repair window.
$forceManagedUpdate = $false
# v14.5.43: Resume / repair can automatically perform a cumulative migration when
# the saved installer metadata predates this full release. Same-version repair stays local-first.
$repairOriginInfo = $null
$universalRepairMigration = $false
# Existing-install option 2 uses a scoped reconciliation questionnaire. Only the
# categories explicitly selected here are allowed to change; all other saved
# installer choices are carried forward verbatim.
$changeScopes = @()

switch ($stackState) {
    'managed' {
        Write-Info "Existing installer-managed ~/hermes-stack detected for '$linuxUser'."
        $existingOptions = Get-ExistingInstallOptions $DistroName $linuxUser $linuxHome
        if ($null -eq $existingOptions) {
            throw "Existing installer-managed ~/hermes-stack was detected, but its install-options.json is missing/unreadable and no valid pre-repair options snapshot could be recovered. LatticeVale will NOT fall back to clean-install choices because that could overwrite the intended managed configuration. Preserve the stack, repair/recover install-options.json (or restore it from an installer/manage.sh backup under ~/hermes-stack/backups), then rerun Resume / repair."
        }
        $repairOriginInfo = Get-LatticeValeRepairOriginInfo $DistroName $linuxUser $linuxHome $existingOptions $bundleVersion $compat.InstallOptionsSchema $compat.MinUniversalRepairMajor
        if ($repairOriginInfo.NewerThanBundle) {
            throw "This managed stack was created or last repaired by a newer LatticeVale release than v$bundleVersion (options=$($repairOriginInfo.OptionsVersion), state=$($repairOriginInfo.StateVersion)). Refusing a repair downgrade. Run the same or newer full LatticeVale release instead."
        }
        if (-not $repairOriginInfo.Supported) {
            throw "The existing managed stack has unsupported or corrupt installer metadata/options schema (detected version=$($repairOriginInfo.OriginVersion), schema=$($repairOriginInfo.OriginSchema); current supported schema=$($repairOriginInfo.CurrentSchema)). LatticeVale preserved the stack and will not guess a destructive migration."
        }
        Write-Info "Detected managed-install metadata: version=$($repairOriginInfo.OriginVersion), options schema=$($repairOriginInfo.OriginSchema)."
        if ($repairOriginInfo.NeedsMigration) {
            Write-Warning "This installation predates the current v$bundleVersion repair schema. Choosing Resume / repair will perform a cumulative migration directly to this release; no intermediate LatticeVale installer is required."
        }
        Write-Step 'Existing installation audit'
        $auditText = Invoke-BundledStackAudit $DistroName $linuxUser $linuxHome
        if ($auditText) { Write-Host $auditText } else { Write-Warning 'The detailed audit could not run yet; recovery can still proceed from installer files and live stage verifiers.' }
        if ($null -ne $existingOptions) { Show-WindowsRecoveryAudit $DistroName $linuxUser $existingOptions }

        $modeChoice = Read-MenuExplicit 'Choose how to handle the existing LatticeVale stack:' @(
            'Resume / repair installation - recommended; reuse previous choices and repair failed/incomplete/stale stages (targeted managed software also refreshes when the periodic window is due)',
            'Change installed components - reuse the stack but choose options again',
            'Verify installation only - read-only audit; make no changes',
            'Reconfigure providers/profiles - keep services/data but rerun Hermes provider setup',
            'Advanced recovery - reset checkpoints or explicitly rebuild installer-owned identities',
            'Update / repair installer-managed software - force this bundle''s declared component versions/channels and managed package/image/source layer now, then run normal repair',
            'Cleanup / reclaim disk space - choose safe cleanup categories without changing the current LatticeVale runtime/data configuration'
        )
        switch ($modeChoice) {
            1 {
                $installMode = 'resume'
                if ($repairOriginInfo -and $repairOriginInfo.NeedsMigration) {
                    $universalRepairMigration = $true
                    $forceManagedUpdate = $true
                    Write-Host "`nCUMULATIVE REPAIR MIGRATION" -ForegroundColor Cyan
                    Write-Info "Resume / repair will migrate the proven managed stack from $($repairOriginInfo.OriginVersion) / schema $($repairOriginInfo.OriginSchema) directly to v$bundleVersion / schema $($repairOriginInfo.CurrentSchema)."
                    Write-Info 'Before managed software/source refresh, LatticeVale will create the same verified rollback backup used by controlled Update / repair. Persistent application state and user-owned overrides remain preservation-first.'
                }
            }
            2 {
                $installMode = 'change'
                Write-Host "`nSAFE CHANGE MODE" -ForegroundColor Yellow
                Write-Info 'This mode preserves existing Hermes profiles, provider/model credentials, Matrix identities/rooms, ports, paths, and every unselected installer setting.'
                Write-Info 'Provider/profile reconfiguration remains option 4. Change mode will not recreate or rename profiles merely because you are changing a component.'
                $doneSelectingChanges = $false
                while (-not $doneSelectingChanges) {
                    $scopeChoice = Read-MenuExplicit 'Select a category to change; you may select several before finishing:' @(
                        'Optional components: Dashboard, SearXNG, QMD, Obsidian',
                        'Kanban enablement and worker-concurrency limits',
                        'Matrix service and Windows Tailscale exposure',
                        'Local AI / Honcho / Ollama backend and models',
                        'Runtime/Windows policy: container limits, updates, WSL lifetime, auto-start, shortcuts, timezone',
                        'Select ALL change categories above',
                        'Finish selecting categories and continue'
                    )
                    switch ($scopeChoice) {
                        1 { if ($changeScopes -notcontains 'components') { $changeScopes += 'components' } }
                        2 { if ($changeScopes -notcontains 'kanban') { $changeScopes += 'kanban' } }
                        3 { if ($changeScopes -notcontains 'matrix-tailscale') { $changeScopes += 'matrix-tailscale' } }
                        4 { if ($changeScopes -notcontains 'local-ai') { $changeScopes += 'local-ai' } }
                        5 { if ($changeScopes -notcontains 'runtime') { $changeScopes += 'runtime' } }
                        6 { $changeScopes = @('components','kanban','matrix-tailscale','local-ai','runtime') }
                        7 {
                            if ($changeScopes.Count -eq 0) {
                                Write-Host 'Select at least one category, or choose Verify installation only from the previous menu if you do not want changes.' -ForegroundColor Yellow
                            } else { $doneSelectingChanges = $true }
                        }
                    }
                    if ($scopeChoice -ne 7) { Write-Info "Selected change categories: $($changeScopes -join ', ')" }
                }
            }
            3 {
                $installMode = 'verify'
                $auditText = Show-LatticeValeReadOnlyVerification $DistroName $linuxUser $linuxHome $existingOptions
                exit 0
            }
            4 {
                $installMode = 'reconfigure'
                $forceProviderSetup = $true
                $forceProfileSetup = $true
                if ([bool](Get-OptionValue $existingOptions 'hermesLocalAI' $false)) {
                    Write-Info 'The saved default-profile policy uses LatticeVale local Ollama. Reconfigure will reapply that selected local-AI policy and rerun secondary profile model setup; use Change installed components -> Local AI / Honcho / Ollama if you want to switch the default profile away from local Ollama.'
                }
            }
            5 {
                $installMode = 'advanced'
                $recoveryChoice = Read-MenuExplicit 'Advanced recovery action:' @(
                    'Reset installer checkpoints and re-verify/reconcile every stage (data is preserved)',
                    'Rebuild only the installer-owned Matrix bot/room identity if Matrix authentication is broken',
                    'Rerun provider/profile setup and reset checkpoints',
                    'Return to a read-only verification and exit'
                )
                switch ($recoveryChoice) {
                    1 { $resetCheckpoints = $true }
                    2 {
                        if (-not [bool](Get-OptionValue $existingOptions 'matrix' $false)) {
                            throw 'Advanced Matrix identity rebuild requires the shared Matrix service to be enabled in the saved installation. Use Change installed components to enable Matrix first, complete that run, then return to Advanced recovery if identity replacement is still needed.'
                        }
                        $rebuildMatrixIdentity = $true
                        $resetCheckpoints = $true
                    }
                    3 {
                        $forceProviderSetup = $true
                        $forceProfileSetup = $true
                        $resetCheckpoints = $true
                        if ([bool](Get-OptionValue $existingOptions 'hermesLocalAI' $false)) {
                            Write-Info 'The saved default-profile policy uses LatticeVale local Ollama. This recovery action will reapply that local-AI default while rerunning secondary profile model setup. Use Change installed components -> Local AI / Honcho / Ollama to switch the default profile away from local Ollama.'
                        }
                    }
                    4 {
                        $auditText = Show-LatticeValeReadOnlyVerification $DistroName $linuxUser $linuxHome $existingOptions
                        exit 0
                    }
                }
            }
            6 {
                $installMode = 'update'
                $forceManagedUpdate = $true
                Write-Host "`nCONTROLLED UPDATE / REPAIR" -ForegroundColor Cyan
                Write-Info 'This mode preserves saved component choices and persistent application data, creates a pre-update managed-stack backup, then forces this LatticeVale bundle''s managed package/image/source refresh instead of waiting for the periodic refresh window.'
                Write-Info 'It applies installer-managed component references only to versions/channels declared by this bundle. It does not chase arbitrary upstream latest/main versions, overwrite explicit user-owned image/source overrides, or update separately owned native Windows Ollama.'
            }
            7 {
                $installMode = 'cleanup'
                Write-Host "`nCLEANUP / RECLAIM DISK SPACE" -ForegroundColor Cyan
                Write-Info 'Cleanup is an isolated maintenance mode. It exits after cleanup and does not continue into component reconciliation, provider setup, managed software refresh, or normal install stages.'
                Write-Info 'Every offered category is bounded so selecting one or ALL cannot delete the live LatticeVale containers, Docker volumes/networks/tagged images, Hermes/Matrix/Honcho/QMD/Ollama persistent state, configured models, vault/workspace files, credentials, or user-created backups.'
                $cleanupScopes = @()
                $cleanupDone = $false
                while (-not $cleanupDone) {
                    $cleanupChoice = Read-MenuExplicit 'Select a cleanup category; you may select several before running:' @(
                        'LatticeVale Option 6 pre-update safety backups - delete only backups with exact bundle ownership metadata for this current stack',
                        'Disposable LatticeVale staging residue - stale root-owned installer/audit temp directories and incomplete pre-update .partial directories only',
                        'APT downloaded-package cache - clears downloaded package archives only; installed packages are unchanged',
                        'Docker dangling images only - untagged images not referenced by any container; never uses image prune -a',
                        'Docker dangling build cache only - default builder prune without --all; runtime images/containers/volumes/networks are unchanged',
                        'TRIM unused blocks on the WSL root filesystem - exposes freed ext4 blocks to the virtual-disk layer; does not resize/move/compact the VHDX',
                        'Select ALL safe cleanup categories above',
                        'Finish selecting categories and run cleanup',
                        'Cancel cleanup and exit without changes'
                    )
                    switch ($cleanupChoice) {
                        1 { if ($cleanupScopes -notcontains 'preupdate-backups') { $cleanupScopes += 'preupdate-backups' } }
                        2 { if ($cleanupScopes -notcontains 'staging') { $cleanupScopes += 'staging' } }
                        3 { if ($cleanupScopes -notcontains 'apt-cache') { $cleanupScopes += 'apt-cache' } }
                        4 { if ($cleanupScopes -notcontains 'docker-dangling') { $cleanupScopes += 'docker-dangling' } }
                        5 { if ($cleanupScopes -notcontains 'docker-build-cache') { $cleanupScopes += 'docker-build-cache' } }
                        6 { if ($cleanupScopes -notcontains 'trim-root') { $cleanupScopes += 'trim-root' } }
                        7 { $cleanupScopes = @('preupdate-backups','staging','apt-cache','docker-dangling','docker-build-cache','trim-root') }
                        8 {
                            if ($cleanupScopes.Count -eq 0) {
                                Write-Host 'Select at least one cleanup category, or choose Cancel cleanup.' -ForegroundColor Yellow
                            } else { $cleanupDone = $true }
                        }
                        9 {
                            Write-Info 'Cleanup cancelled. No cleanup action was executed.'
                            exit 0
                        }
                    }
                    if ($cleanupChoice -lt 8) { Write-Info "Selected cleanup categories: $($cleanupScopes -join ', ')" }
                }
                if (-not (Read-ChoiceExplicit 'Run the selected cleanup now?' "Selected categories: $($cleanupScopes -join ', '). The cleanup helper validates current managed state before deleting anything." 'Exit without cleanup.' $false $false)) {
                    Write-Info 'Cleanup cancelled. No cleanup action was executed.'
                    exit 0
                }
                Invoke-LatticeValeCleanupMaintenance $DistroName $stackLinuxPath $cleanupScopes $DistroStoragePath
                Write-Host "`nCleanup maintenance complete. Normal installer/repair stages were not run." -ForegroundColor Green
                exit 0
            }
        }
        if (-not $selectedDistro.ManagedRepairEligible -and $installMode -in @('resume','change','reconfigure','advanced','update')) {
            throw "The selected LatticeVale host partition is below the supported managed-repair storage floor. Rerun the installer and choose Cleanup / reclaim disk space (Option 7), or Verify installation only (Option 3). No mutating repair/update work was started."
        }
    }
    'absent' { }
    'unrecognized' {
        if (-not (Read-ChoiceExplicit 'Reuse the existing unrecognized ~/hermes-stack directory?' 'Installer-owned files may be replaced after a pre-change backup. Existing persistent subdirectories are not deliberately deleted.' 'Installer stops before modifying that directory.' $true)) {
            throw 'Existing ~/hermes-stack was left unchanged.'
        }
        $installMode = 'change'
    }
    default { throw "Could not safely determine whether ~/hermes-stack already exists for '$linuxUser'. Resolve the WSL/home-directory access error and rerun." }
}

# Offer profile-room adoption only when this installer can prove that an existing
# LatticeVale Synapse deployment has already been provisioned. A fresh install cannot
# possibly have a local !room:hermes.local ID yet, so asking for one before Matrix exists
# is both confusing and impossible to satisfy.
$existingMatrixDeployment = $false
if ($stackState -eq 'managed') {
    $matrixDeploymentProbe = Invoke-WslDirectCapture $DistroName $linuxUser 'test' @('-s', "$linuxHome/hermes-stack/data/synapse/homeserver.yaml") 15
    $existingMatrixDeployment = [bool]$matrixDeploymentProbe.Success
}

# Every mutating run against a recognized LatticeVale stack receives the safe repair-maintenance
# pass. It never deletes persistent application data and is intentionally not enabled for
# a clean install or an unrecognized directory merely being adopted.
$repairMaintenance = ($stackState -eq 'managed' -and $installMode -in @('resume','change','reconfigure','advanced','update'))
if ($repairMaintenance -and (Test-LatticeValeLegacyUnsafeShutdownShortcut $DistroName $linuxUser $stackLinuxPath)) {
    [void](Invoke-LatticeValeLegacyShortcutWslTransportRepair $DistroName $linuxUser $stackLinuxPath)
}
if ($repairMaintenance -and (Test-LatticeValeBrokenShortcutLauncher $DistroName $linuxUser $stackLinuxPath)) {
    Write-Warning 'The installed LatticeVale desktop shortcut helper does not satisfy the current schema-4 direct WSL --cd launcher contract. Resume / repair will replace the helper/configuration during Windows shortcut reconciliation; no distro recreation or VHDX change is required.'
}

if ($repairMaintenance) {
    if ($universalRepairMigration) {
        Write-Info 'Universal repair migration enabled: this older managed installation will receive the current bundle-owned scripts, cumulative checkpoint migrations, current managed package/image/source pins, and a fresh resource-policy calculation. Persistent application data and explicit user-owned overrides are preserved.'
    } elseif ($forceManagedUpdate) {
        Write-Info 'Managed update enabled: this run forces the installer-managed package/image/source layer to the versions and channels declared by this LatticeVale bundle, then runs normal live repair verification. Persistent application data and explicit user-owned overrides are preserved.'
    } else {
        Write-Info "Repair maintenance enabled: Resume / repair can update installer-managed prerequisites, Docker packages, images/builds, and audited source pins when the $((Get-LatticeValeCompatibility).ManagedRepairRefreshDays)-day managed refresh is due (or when the refresh policy changes). Between refresh windows it remains local-first and is not a blanket update. Persistent application data and explicit custom overrides are preserved."
    }
}

$dockerConflicts = @(Get-InstalledDockerConflictPackages $DistroName)
$dockerRuntime = Get-ExistingDockerRuntimeInfo $DistroName
if ($dockerRuntime.Known -and $dockerRuntime.Rootless) {
    throw "An active rootless Docker daemon/socket was detected inside '$DistroName'. This bundle owns a rootful in-distro Docker Engine and does not mix rootless and rootful daemons in one managed distro. Stop/remove the rootless Docker runtime or use a different eligible WSL distro, then rerun."
}
if ($dockerRuntime.Known -and $dockerRuntime.Runtime) {
    $serverText = [string]$dockerRuntime.Server
    if ($serverText -match '(?i)docker desktop') {
        throw "Docker Desktop WSL integration is currently supplying the Docker daemon inside '$DistroName'. This installer installs Docker Engine directly in the distro, and Docker documents that running both can conflict. Disable Docker Desktop WSL integration for this distro (or stop using that injected runtime), then rerun. Detected server: $serverText"
    }
    if ($dockerRuntime.OfficialCount -eq 0 -and $dockerConflicts.Count -eq 0) {
        throw "A working Docker daemon is already injected or custom-installed inside '$DistroName', but it is not managed by the Docker CE packages this installer expects. To avoid overwriting an unknown Docker runtime, remove/disable that runtime or use a different eligible WSL distro, then rerun. Detected server: $serverText"
    }
}
if ($dockerConflicts.Count -gt 0) {
    Write-Warning "Docker's official packages conflict with these currently installed distro packages: $($dockerConflicts -join ', ')."
    if (-not (Read-ChoiceExplicit 'Allow replacement of these conflicting Docker packages?' 'Docker CE cannot be installed cleanly beside these distro-provided Docker/containerd packages. The packages are removed, but /var/lib/docker and /var/lib/containerd are not deliberately deleted.' 'Installer stops before package changes; the existing distro is left untouched.' $true)) {
        throw 'Conflicting Docker packages were left unchanged.'
    }
}

$rootlessDocker = Get-ExistingRootlessDockerRuntimeInfo $DistroName $linuxUser
if ($rootlessDocker.Known -and ($rootlessDocker.Runtime -or $rootlessDocker.Configured)) {
    $detail = if ($rootlessDocker.Runtime) { "running at $($rootlessDocker.Socket) ($($rootlessDocker.Server))" } else { "configured for user '$linuxUser'" }
    throw "Rootless Docker is already $detail. This stack intentionally owns one rootful Docker Engine at /var/run/docker.sock; keeping a second per-user daemon would make containers, networks, ports, and recovery state ambiguous. Disable/remove the existing rootless Docker setup or use a different eligible WSL distro, then rerun."
}

$priorTailscaleInfo = Get-TailscaleInfoFromWsl $DistroName $linuxUser
$priorDashboardBridgePort = 0
$priorMatrixBridgePort = 0
if ($priorTailscaleInfo.ContainsKey('DASHBOARD_BRIDGE_PORT')) { [void][int]::TryParse($priorTailscaleInfo['DASHBOARD_BRIDGE_PORT'], [ref]$priorDashboardBridgePort) }
if ($priorTailscaleInfo.ContainsKey('MATRIX_BRIDGE_PORT')) { [void][int]::TryParse($priorTailscaleInfo['MATRIX_BRIDGE_PORT'], [ref]$priorMatrixBridgePort) }

$priorHermesApiPort = (Get-OptionTcpPort $existingOptions 'hermesApiPort' 8642)
$priorDashboardLocalPort = (Get-OptionTcpPort $existingOptions 'dashboardLocalPort' 9119)
$priorMatrixLocalPort = (Get-OptionTcpPort $existingOptions 'matrixLocalPort' 8008)
$priorSearxngLocalPort = (Get-OptionTcpPort $existingOptions 'searxngLocalPort' 8888)
$priorHonchoLocalPort = (Get-OptionTcpPort $existingOptions 'honchoLocalPort' 8000)

Write-Step 'Choose what to install'
Write-Info 'Prerequisites (not installed here): working WSL + an existing supported Ubuntu WSL2 distro on a qualifying partition.'
Write-Info "Core components installed into '$DistroName': Docker Engine/Compose and Hermes Agent."

$wslLifetimeSupported = Test-WslInstanceIdleTimeoutSupported $wslInfo
$wslPackageVersion = Get-WslStorePackageVersion $wslInfo
if (-not $wslLifetimeSupported) {
    $versionLabel = if ($wslPackageVersion) { [string]$wslPackageVersion } else { 'legacy/unknown' }
    Write-Warning "WSL $versionLabel does not expose the LatticeVale-validated instanceIdleTimeout policy (requires Store/MSIX WSL 2.5.4+). LatticeVale will leave the global WSL lifetime policy unchanged."
}
$reusePriorChoices = ($installMode -in @('resume','change','reconfigure','advanced','update')) -and $null -ne $existingOptions
$persistOllamaAcceleration = $true
if ($reusePriorChoices) {
    if ($installMode -eq 'change') {
        Write-Info "Mode: change. Loading the saved configuration first; only selected categories may be changed. Unselected values are preserved."
    } else {
        Write-Info "Mode: $installMode. Reusing the previous component selections; live state decides what actually needs repair."
    }
    $questionnaireMode = [string](Get-OptionValue $existingOptions 'questionnaireMode' 'custom')
    if ($questionnaireMode -notin @('quick','custom','explicit')) { $questionnaireMode = 'custom' }
    $dashboard = [bool](Get-OptionValue $existingOptions 'dashboard' $true)
    $multiAgent = [bool](Get-OptionValue $existingOptions 'multiAgent' $false)
    $workers = @((Get-OptionValue $existingOptions 'workers' @()))
    $kanban = [bool](Get-OptionValue $existingOptions 'kanban' $false)
    $kanbanMaxInProgress = [int](Get-OptionValue $existingOptions 'kanbanMaxInProgress' 2)
    if ($kanbanMaxInProgress -lt 1 -or $kanbanMaxInProgress -gt 8) { $kanbanMaxInProgress = 2 }
    $kanbanMaxInProgressPerProfile = [int](Get-OptionValue $existingOptions 'kanbanMaxInProgressPerProfile' 1)
    if ($kanbanMaxInProgressPerProfile -lt 1 -or $kanbanMaxInProgressPerProfile -gt $kanbanMaxInProgress) { $kanbanMaxInProgressPerProfile = 1 }
    $matrix = [bool](Get-OptionValue $existingOptions 'matrix' $false)
    # v14 schema migration: older installs had profiles but no explicit per-profile
    # Matrix intent. Ask once for only the missing profile settings, defaulting to No so
    # ordinary Resume / repair never creates new bot identities unexpectedly.
    $workers = @(Complete-WorkerMatrixOptions $workers $matrix $false $true $existingMatrixDeployment)
    $tailscale = [bool](Get-OptionValue $existingOptions 'tailscale' $false)
    $installWindowsTailscale = [bool](Get-OptionValue $existingOptions 'installWindowsTailscale' $false)
    $tailscaleDashboard = [bool](Get-OptionValue $existingOptions 'tailscaleDashboard' $false)
    $tailscaleDashboardPort = (Get-OptionTcpPort $existingOptions 'tailscaleDashboardPort' 9443)
    $tailscaleMatrix = [bool](Get-OptionValue $existingOptions 'tailscaleMatrix' $false)
    $tailscaleMatrixPort = (Get-OptionTcpPort $existingOptions 'tailscaleMatrixPort' 443)
    # v13.14 and earlier used 8448 as LatticeVale's Matrix default. Repair/resume
    # migrates that old installer default to standard HTTPS 443; custom ports are preserved.
    if ($tailscaleMatrix -and $tailscaleMatrixPort -eq 8448) {
        $tailscaleMatrixPort = 443
        Write-Info 'Migrating the prior LatticeVale Matrix Tailscale HTTPS default from 8448 to standard HTTPS 443.'
    }
    $dashboardBridgePort = (Get-OptionTcpPort $existingOptions 'dashboardBridgePort' 19119)
    $matrixBridgePort = (Get-OptionTcpPort $existingOptions 'matrixBridgePort' 18008)
    $searxng = [bool](Get-OptionValue $existingOptions 'searxng' $false)
    $qmd = [bool](Get-OptionValue $existingOptions 'qmd' $false)
    $honcho = [bool](Get-OptionValue $existingOptions 'honcho' $false)
    # v11 migrations preserve the existing Hermes provider by default; Honcho itself
    # still migrates to local Ollama whenever Honcho is selected.
    $hermesLocalAI = [bool](Get-OptionValue $existingOptions 'hermesLocalAI' $false)
    $localTextModel = [string](Get-OptionValue $existingOptions 'localTextModel' 'qwen3.5:4b')
    $localEmbeddingModel = [string](Get-OptionValue $existingOptions 'localEmbeddingModel' 'qwen3-embedding:4b')
    # v14.5.3: DirectML is additive and opt-in. Older installs that do not carry
    # these keys stay on the proven Ollama text path during Resume / repair.
    $localTextBackend = [string](Get-OptionValue $existingOptions 'localTextBackend' 'ollama')
    if ($localTextBackend -notin @('ollama','directml')) { $localTextBackend = 'ollama' }
    $directmlTextModel = [string](Get-OptionValue $existingOptions 'directmlTextModel' 'Qwen/Qwen2.5-1.5B-Instruct')
    if ($directmlTextModel -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') { $directmlTextModel = 'Qwen/Qwen2.5-1.5B-Instruct' }
    $directmlPort = (Get-OptionTcpPort $existingOptions 'directmlPort' 11436)
    $directmlAdapterName = [string](Get-OptionValue $existingOptions 'directmlAdapterName' '')
    $directmlGpuVendor = [string](Get-OptionValue $existingOptions 'directmlGpuVendor' '')
    if ($directmlGpuVendor -notin @('','amd','nvidia','intel','qualcomm')) { $directmlGpuVendor = '' }
    $ollamaBackend = [string](Get-OptionValue $existingOptions 'ollamaBackend' 'managed')
    if ($ollamaBackend -notin @('managed','windows-native')) { $ollamaBackend = 'managed' }
    $windowsOllamaBridgePort = (Get-OptionTcpPort $existingOptions 'windowsOllamaBridgePort' 11435)
    $windowsOllamaTransport = [string](Get-OptionValue $existingOptions 'windowsOllamaTransport' 'windows-gateway-relay')
    if ($windowsOllamaTransport -notin @('windows-gateway-relay','wsl-localhost-relay','wsl-host-relay')) { $windowsOllamaTransport = 'windows-gateway-relay' }
    $windowsOllamaTargetAddress = [string](Get-OptionValue $existingOptions 'windowsOllamaTargetAddress' '127.0.0.1')
    $windowsOllamaTargetPort = (Get-OptionTcpPort $existingOptions 'windowsOllamaTargetPort' 11434)
    $windowsOllamaHostAddress = [string](Get-OptionValue $existingOptions 'windowsOllamaHostAddress' '')
    $windowsOllamaState = $null
    $windowsNativeBridgeState = $null
    if ($honcho -or $hermesLocalAI) {
        $windowsOllamaState = Get-WindowsNativeOllamaState
        $windowsOllamaState = Resolve-WindowsNativeOllamaForQuestionnaire $windowsOllamaState
        if ($windowsOllamaState.ApiReady) { $windowsNativeBridgeState = Get-LatticeValeNativeBridgeCapability $DistroName $windowsOllamaState }
        if ($windowsNativeBridgeState -and $windowsNativeBridgeState.Ready) {
            $windowsOllamaTransport = [string]$windowsNativeBridgeState.Transport
            $windowsOllamaHostAddress = [string]$windowsNativeBridgeState.WindowsHostIp
            $windowsOllamaTargetAddress = [string]$windowsOllamaState.RelayTargetAddress
            $windowsOllamaTargetPort = [int]$windowsOllamaState.RelayTargetPort
        }
    }

    $savedAccelerationProperty = $existingOptions.PSObject.Properties['ollamaAcceleration']
    $persistOllamaAcceleration = ($null -ne $savedAccelerationProperty)
    $ollamaAcceleration = [string](Get-OptionValue $existingOptions 'ollamaAcceleration' 'cpu')
    if ($ollamaAcceleration -notin @('auto','cpu','nvidia','amd')) { $ollamaAcceleration = 'cpu' }

    if ($ollamaBackend -eq 'windows-native' -and ($honcho -or $hermesLocalAI)) {
        $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
        if (-not $nativeBackendUsable -and $windowsOllamaState.ApiReady) {
            $directFallback = Resolve-LatticeValeNativeOllamaDirectFallback $DistroName $windowsOllamaState $windowsNativeBridgeState
            $windowsOllamaState = $directFallback.OllamaState
            $windowsNativeBridgeState = $directFallback.BridgeState
            if ($windowsNativeBridgeState -and $windowsNativeBridgeState.Ready) {
                $windowsOllamaTransport = [string]$windowsNativeBridgeState.Transport
                $windowsOllamaHostAddress = [string]$windowsNativeBridgeState.WindowsHostIp
                $windowsOllamaTargetAddress = [string]$windowsOllamaState.RelayTargetAddress
                $windowsOllamaTargetPort = [int]$windowsOllamaState.RelayTargetPort
            }
            $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
        }
        if (-not $nativeBackendUsable) {
            Write-Warning 'This managed install is configured to use native Windows Ollama, but the native API and current WSL bridge path are not both usable. LatticeVale will not silently replace it.'
            Write-Info $windowsOllamaState.Detail
            if ($windowsNativeBridgeState) { Write-Info $windowsNativeBridgeState.Detail }
            if ($installMode -eq 'change' -and $changeScopes -notcontains 'local-ai') {
                Write-Info 'Scoped Change mode is preserving the saved Windows-native Ollama selection because Local AI / Ollama was not selected for change. This run may remain NEEDS_REPAIR until that backend is repaired separately.'
            } else {
                $nativeRecovery = Read-MenuExplicit 'Choose how this repair run should handle unavailable Windows-native Ollama' @(
                    'Switch this managed configuration to WSL/Docker Ollama with Auto acceleration',
                    'Switch this managed configuration to WSL/Docker Ollama with CPU only',
                    'Stop this installer run and keep Windows-native Ollama selected'
                )
                switch ($nativeRecovery) {
                    1 { $ollamaBackend = 'managed'; $ollamaAcceleration = 'auto'; $persistOllamaAcceleration = $true }
                    2 { $ollamaBackend = 'managed'; $ollamaAcceleration = 'cpu'; $persistOllamaAcceleration = $true }
                    default { throw 'Windows-native Ollama is unavailable; installation stopped without substituting another inference backend.' }
                }
            }
        } else {
            Write-Info "Saved Ollama backend: native Windows Ollama $($windowsOllamaState.Version) through the LatticeVale WSL-only relay."
            Show-NativeOllamaResourceWarning
        }
    }

    if (-not $persistOllamaAcceleration -and $universalRepairMigration) {
        # Pre-v14.2 installs had no managed acceleration field. Normalize them to an
        # explicit CPU policy so resource policy v11 owns their CPU/RAM ceilings without
        # silently opting an existing stack into GPU execution. Users can choose Auto/GPU
        # later through Change installed components.
        $ollamaAcceleration = 'cpu'
        $persistOllamaAcceleration = $true
        Write-Info 'Universal repair migration: normalized the legacy managed-Ollama acceleration setting to explicit CPU for backward-compatible policy-v11 resource ownership. GPU Auto/forced modes remain opt-in through Change installed components.'
    } elseif (-not $persistOllamaAcceleration -and ($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'managed') {
        Write-Info 'Legacy same-line repair: preserving the existing Ollama image/runtime choice. Use "Change installed components" if you want to opt into managed GPU acceleration.'
    }
    if ($ollamaBackend -eq 'managed' -and $persistOllamaAcceleration -and ($honcho -or $hermesLocalAI) -and $ollamaAcceleration -in @('amd','nvidia')) {
        $gpuState = Get-OllamaWslGpuPrerequisites $DistroName $linuxUser
        $forcedReady = if ($ollamaAcceleration -eq 'amd') { $gpuState.AmdDockerReady } else { $gpuState.NvidiaWslReady }
        if (-not $forcedReady) {
            Write-Warning "The saved forced Ollama acceleration policy '$ollamaAcceleration' is not currently usable in the selected Ubuntu distro. LatticeVale will not guess a replacement or let prepare_config fail later."
            Write-OllamaGpuPrerequisiteSummary $gpuState
            if ($installMode -eq 'change' -and $changeScopes -notcontains 'local-ai') {
                Write-Info 'Scoped Change mode is preserving the saved Ollama acceleration because Local AI / Ollama was not selected for change. This run may remain NEEDS_REPAIR until that backend is repaired separately.'
            } else {
            $repairChoices = [System.Collections.Generic.List[string]]::new()
            $nativeChoiceIndex = 0
            if ($windowsOllamaState -and $windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready) {
                $nativeChoiceIndex = 1
                $repairChoices.Add("Use detected native Windows Ollama $($windowsOllamaState.Version) through a WSL-only relay; Windows Ollama keeps ownership of its native GPU/Vulkan/ROCm backend")
            }
            $autoChoiceIndex = $repairChoices.Count + 1; $repairChoices.Add('Use WSL/Docker Ollama with Auto acceleration; fall back to CPU when no supported WSL GPU path is verified')
            $cpuChoiceIndex = $repairChoices.Count + 1; $repairChoices.Add('Use WSL/Docker Ollama with CPU only')
            $stopChoiceIndex = $repairChoices.Count + 1; $repairChoices.Add('Stop this installer run and leave the saved acceleration choice unchanged')
            $recoveryChoice = Read-MenuExplicit 'Choose how this repair run should handle the unavailable saved Ollama GPU mode' $repairChoices.ToArray()
            if ($nativeChoiceIndex -gt 0 -and $recoveryChoice -eq $nativeChoiceIndex) {
                $ollamaBackend = 'windows-native'
                Show-NativeOllamaResourceWarning
                Write-Info 'Ollama backend changed explicitly for this managed configuration: native Windows Ollama.'
            } elseif ($recoveryChoice -eq $autoChoiceIndex) {
                $ollamaAcceleration = 'auto'; Write-Info 'Ollama acceleration changed explicitly for this managed configuration: auto.'
            } elseif ($recoveryChoice -eq $cpuChoiceIndex) {
                $ollamaAcceleration = 'cpu'; Write-Info 'Ollama acceleration changed explicitly for this managed configuration: cpu.'
            } else {
                throw "Saved Ollama acceleration '$ollamaAcceleration' is unavailable; installation stopped without substituting another setting."
            }
            }
        }
    }
    # v14.2 migration: older installs had no installer-owned container ceilings. Preserve
    # that behavior during repair rather than unexpectedly constraining a working stack.
    $containerResourceLimits = [bool](Get-OptionValue $existingOptions 'containerResourceLimits' $false)
    $obsidian = [bool](Get-OptionValue $existingOptions 'obsidian' $false)
    $obsidianVaultWindowsPath = ''
    $obsidianVaultWslPath = ''
    if ($obsidian) {
        $obsidianVaultWindowsPath = Get-DefaultObsidianVaultWindowsPath $existingOptions
        $obsidianVaultWslPath = Convert-WindowsLocalPathToWslPath $DistroName $linuxUser $obsidianVaultWindowsPath
        Write-Info "Windows Obsidian vault: $obsidianVaultWindowsPath"
        Write-Info "Hermes/QMD will mount it from WSL path: $obsidianVaultWslPath"
    }
    $unattended = [bool](Get-OptionValue $existingOptions 'unattendedUpdates' $true)
    if ($wslLifetimeSupported) {
        $savedLifetimeChoice = $existingOptions.PSObject.Properties['keepWslServicesRunning']
        if ($null -ne $savedLifetimeChoice) {
            $keepWslServicesRunning = [bool](Get-OptionValue $existingOptions 'keepWslServicesRunning' $false)
        } else {
            # v13.13.4 and earlier did not record this global-policy choice. Ask once on
            # the first v13.14 repair instead of silently mutating the user's .wslconfig.
            $keepWslServicesRunning = Read-ChoiceExplicit 'Prevent WSL from auto-shutting down this running server instance?' 'Uses WSL''s supported [general] instanceIdleTimeout=-1 plus [wsl2] vmIdleTimeout=-1 policies. This is not a polling loop or Windows auto-start; your normal launcher still owns startup.' 'Leaves WSL''s instance-idle policy unchanged; on affected WSL builds the distro may terminate even while server services are intended to stay available.'
        }
    } else {
        $keepWslServicesRunning = $false
    }
    $autoStart = [bool](Get-OptionValue $existingOptions 'autoStart' $false)
    # v14 desktop shortcuts are opt-in. Legacy repair runs without this saved option
    # remain unchanged rather than unexpectedly creating Windows desktop artifacts.
    $windowsShortcuts = [bool](Get-OptionValue $existingOptions 'windowsShortcuts' $false)
    $timezone = ''
    if ($null -ne $existingOptions.PSObject.Properties['timezone']) {
        $timezone = [string](Get-OptionValue $existingOptions 'timezone' '')
    }
    if ([string]::IsNullOrWhiteSpace($timezone)) {
        $timezone = Get-DetectedLinuxTimezone $DistroName $linuxUser
        if ([string]::IsNullOrWhiteSpace($timezone)) {
            Write-Warning 'This legacy install has no saved timezone and Ubuntu timezone detection returned no value.'
            while ([string]::IsNullOrWhiteSpace($timezone)) {
                $timezone = (Read-Host 'Container timezone (explicit IANA name required)').Trim()
                if ($timezone -notmatch '^[A-Za-z0-9._+\-/]+$') {
                    Write-Host 'Use a valid IANA timezone name, for example America/Los_Angeles or Europe/London.' -ForegroundColor Yellow
                    $timezone = ''
                }
            }
        } else {
            Write-Info "No saved timezone was present; reusing the detected Ubuntu timezone: $timezone"
        }
    }
    $hermesApiPort = (Get-OptionTcpPort $existingOptions 'hermesApiPort' 8642)
    $dashboardLocalPort = (Get-OptionTcpPort $existingOptions 'dashboardLocalPort' 9119)
    $matrixLocalPort = (Get-OptionTcpPort $existingOptions 'matrixLocalPort' 8008)
    $searxngLocalPort = (Get-OptionTcpPort $existingOptions 'searxngLocalPort' 8888)
    $honchoLocalPort = (Get-OptionTcpPort $existingOptions 'honchoLocalPort' 8000)
    if ($installMode -eq 'change') {
        Write-Step 'Scoped existing-install changes'
        Write-Info "Only these categories will be changed: $($changeScopes -join ', '). Everything else remains exactly as saved."

        if ($changeScopes -contains 'components') {
            Write-Host "`n-- Optional components --" -ForegroundColor White
            $dashboard = Read-Choice 'Install Hermes Dashboard?' 'Changes only the Dashboard component selection.' 'Dashboard is disabled; existing persistent Hermes data is not deleted.' $dashboard
            $searxng = Read-Choice 'Install SearXNG + Valkey?' 'Changes only the self-hosted search component selection.' 'SearXNG is disabled; its persistent data is not deliberately deleted.' $searxng
            $qmd = Read-Choice 'Install QMD?' 'Changes only the QMD component selection.' 'QMD is disabled; existing notes/vault data are preserved.' $qmd
            $wasObsidian = $obsidian
            $obsidian = Read-Choice 'Install/configure Obsidian for Windows?' 'Changes only the installer-owned Obsidian integration selection.' 'Obsidian integration is disabled; LatticeVale does not delete the vault.' $obsidian
            if ($obsidian) {
                $needVaultPath = (-not $wasObsidian -or [string]::IsNullOrWhiteSpace($obsidianVaultWindowsPath))
                if (-not $needVaultPath) {
                    Write-Info "Preserving existing Windows Obsidian vault: $obsidianVaultWindowsPath"
                    $needVaultPath = Read-YesNo 'Change the existing Obsidian vault path?' $false
                }
                if ($needVaultPath) {
                    while ($true) {
                        $vaultInput = Read-Host 'Windows Obsidian vault folder (explicit Windows-local path required)'
                        if ([string]::IsNullOrWhiteSpace($vaultInput)) { Write-Host 'Enter a Windows-local vault folder.' -ForegroundColor Yellow; continue }
                        $vaultInput = $vaultInput.Trim().Trim('"')
                        if ($vaultInput -notmatch '^[A-Za-z]:\\') { Write-Host 'Use a Windows-local drive path, not a WSL/UNC/network path.' -ForegroundColor Yellow; continue }
                        try {
                            $obsidianVaultWindowsPath = [System.IO.Path]::GetFullPath($vaultInput)
                            $obsidianVaultWslPath = Convert-WindowsLocalPathToWslPath $DistroName $linuxUser $obsidianVaultWindowsPath
                            break
                        } catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
                    }
                }
            }
        }

        if ($changeScopes -contains 'kanban') {
            Write-Host "`n-- Kanban --" -ForegroundColor White
            $kanban = Read-Choice 'Enable Hermes Kanban?' 'Changes Kanban enablement and reapplies the managed task-context/triage policy; existing cards are not deleted.' 'Kanban orchestration is disabled; existing board data is preserved.' $kanban
            if ($kanban) {
                $kanbanMaxInProgress = Read-Integer 'Maximum concurrent Kanban workers across the board' $kanbanMaxInProgress 1 8
                if ($kanbanMaxInProgressPerProfile -gt $kanbanMaxInProgress) { $kanbanMaxInProgressPerProfile = $kanbanMaxInProgress }
                $kanbanMaxInProgressPerProfile = Read-Integer 'Maximum concurrent Kanban workers per profile' $kanbanMaxInProgressPerProfile 1 $kanbanMaxInProgress
            }
        }

        if ($changeScopes -contains 'matrix-tailscale') {
            Write-Host "`n-- Matrix and Tailscale exposure --" -ForegroundColor White
            $matrix = Read-Choice 'Install Matrix/Synapse?' 'Changes only the shared Matrix service selection. Existing Matrix database/identities/rooms are preserved.' 'Matrix service is disabled; existing Synapse data is not deliberately deleted.' $matrix
            Write-Info 'Secondary-profile Matrix identities/rooms are preserved exactly in Change mode. This category does not rename/recreate profile identities.'

            $tailscaleExeAtSelection = Get-WindowsTailscaleExe
            $tailscale = Read-Choice 'Use Windows Tailscale for private remote access?' 'Changes only LatticeVale-owned Windows Tailscale exposure rules.' 'Selected services remain localhost-only; unrelated Tailscale configuration is not overwritten.' $tailscale
            $installWindowsTailscale = [bool](Get-OptionValue $existingOptions 'installWindowsTailscale' $installWindowsTailscale)
            if ($tailscale -and -not $tailscaleExeAtSelection) {
                $installWindowsTailscale = Read-Choice 'Install Tailscale for Windows if needed?' 'Installs the official Windows client; it remains separate from WSL.' 'Tailscale remote access is disabled for this LatticeVale run.' $installWindowsTailscale
                if (-not $installWindowsTailscale) { $tailscale = $false }
            }
            if ($tailscale -and $dashboard) {
                $tailscaleDashboard = Read-Choice 'Expose Dashboard through your Windows Tailscale node?' 'Changes only the installer-owned Dashboard Serve mapping.' 'Dashboard remains localhost-only.' $tailscaleDashboard
                if ($tailscaleDashboard) { $tailscaleDashboardPort = Read-TcpPort 'Dashboard Tailscale HTTPS port' $tailscaleDashboardPort }
            } else { $tailscaleDashboard = $false }
            if ($tailscale -and $matrix) {
                $tailscaleMatrix = Read-Choice 'Expose Matrix through your Windows Tailscale node?' 'Changes only the installer-owned Matrix Serve mapping.' 'Matrix remains localhost-only.' $tailscaleMatrix
                if ($tailscaleMatrix) {
                    $disallow = if ($tailscaleDashboard -and $tailscaleDashboardPort -gt 0) { @($tailscaleDashboardPort) } else { @() }
                    $tailscaleMatrixPort = Read-TcpPort 'Matrix Tailscale HTTPS port' $tailscaleMatrixPort $disallow
                }
            } else { $tailscaleMatrix = $false }
            if ($tailscale -and -not ($tailscaleDashboard -or $tailscaleMatrix)) { $tailscale = $false; $installWindowsTailscale = $false }
        }

        if ($changeScopes -contains 'local-ai') {
            Write-Host "`n-- Local AI / Honcho / Ollama --" -ForegroundColor White
            $honcho = Read-Choice 'Install fully self-hosted Honcho memory?' 'Changes the Honcho component selection.' 'Honcho is disabled; existing persistent Honcho data is not deliberately deleted.' $honcho
            $wasHermesLocalAI = $hermesLocalAI
            $hermesLocalAI = Read-Choice 'Use a LatticeVale local AI backend as the default Hermes AI provider?' 'Changes the installer-owned default-profile local-AI selection. Local text inference can use Ollama or the experimental PyTorch DirectML gateway.' 'The existing non-LatticeVale provider/model configuration is preserved unless provider setup is explicitly requested elsewhere.' $hermesLocalAI
            if ($wasHermesLocalAI -and -not $hermesLocalAI) {
                # The previous default model block was installer-owned Ollama configuration.
                # A merely "valid" model config is not proof that the user has selected a
                # replacement provider, so force the upstream model wizard in this run.
                $forceProviderSetup = $true
                Write-Info 'Local Ollama is being removed as the default Hermes provider. LatticeVale will open the default-profile provider/model wizard later in this run so the old installer-owned Ollama model block is not silently retained.'
            }
            if ($honcho -or $hermesLocalAI) {
                $gpuPlan = Get-LatticeValeGpuAccelerationPlan $DistroName $linuxUser
                Write-LatticeValeGpuAccelerationPlan $gpuPlan
                $textBackendDefault = if ($localTextBackend -eq 'directml') { 2 } else { 1 }
                $ollamaBackendLabel = 'Ollama (stable; uses the selected Ollama runtime for text inference)' + $(if ($gpuPlan.RecommendedTextBackend -eq 'ollama') { ' [recommended for detected hardware]' } else { '' })
                $directmlBackendLabel = 'PyTorch DirectML gateway (experimental; DirectX 12 GPU acceleration in WSL2, with automatic Ollama fallback)' + $(if ($gpuPlan.RecommendedTextBackend -eq 'directml') { ' [recommended for detected hardware]' } else { '' })
                $textBackendChoice = Read-Menu 'Local text inference backend' @(
                    $ollamaBackendLabel,
                    $directmlBackendLabel
                ) $textBackendDefault
                $localTextBackend = if ($textBackendChoice -eq 2) { 'directml' } else { 'ollama' }
                if ($localTextBackend -eq 'directml') {
                    Write-Info 'DirectML accelerates Hermes and Honcho text inference through one WSL-host gateway. Ollama remains required for Honcho embeddings and as the automatic text fallback.'
                    $directmlGpu = Select-LatticeValeDirectMLGpu $DistroName $linuxUser $directmlAdapterName $directmlGpuVendor
                    if (-not $directmlGpu.UseDirectML) {
                        $localTextBackend = 'ollama'
                        $directmlAdapterName = ''
                        $directmlGpuVendor = ''
                        Write-Info 'Local text inference changed to Ollama because DirectML was not selected for the detected GPU environment.'
                    } else {
                        $directmlAdapterName = [string]$directmlGpu.AdapterName
                        $directmlGpuVendor = [string]$directmlGpu.Vendor
                    }
                    if ($localTextBackend -eq 'directml') {
                    while ($true) {
                        $candidate = Read-Host "DirectML Hugging Face text model [current: $directmlTextModel; Enter preserves]"
                        if (-not [string]::IsNullOrWhiteSpace($candidate)) { $directmlTextModel = $candidate.Trim() }
                        if ($directmlTextModel -match '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') { break }
                        Write-Host 'Use a Hugging Face repository ID in owner/model form.' -ForegroundColor Yellow
                    }
                    $directmlPort = Read-TcpPort 'DirectML WSL-host gateway port' $directmlPort
                    }
                }
                $windowsOllamaState = Get-WindowsNativeOllamaState
                Write-Info $windowsOllamaState.Detail
                $windowsNativeBridgeState = $null
                if ($windowsOllamaState.ApiReady) {
                    $windowsNativeBridgeState = Get-LatticeValeNativeBridgeCapability $DistroName $windowsOllamaState
                    if ($windowsNativeBridgeState) { Write-Info $windowsNativeBridgeState.Detail }
                }
                $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
                $backendSuggested = if ($ollamaBackend -eq 'windows-native' -and $nativeBackendUsable) { 1 } else { 2 }
                while ($true) {
                    $nativeStatus = if ($nativeBackendUsable) { 'AVAILABLE - Windows API and WSL path verified' } elseif ($windowsOllamaState.Installed) { 'NOT CURRENTLY USABLE - selecting it will re-check/start/remediate the detected installation' } else { 'UNAVAILABLE - not installed' }
                    $backendChoice = Read-Menu 'Where should Ollama run?' @("Use native Windows Ollama: $nativeStatus", 'LatticeVale-managed Ollama inside WSL/Docker') $backendSuggested
                    if ($backendChoice -eq 2) { $ollamaBackend = 'managed'; break }

                    $windowsOllamaState = Get-WindowsNativeOllamaState
                    if ($windowsOllamaState.Installed -and -not $windowsOllamaState.ApiReady) { $windowsOllamaState = Resolve-WindowsNativeOllamaForQuestionnaire $windowsOllamaState }
                    $windowsNativeBridgeState = $null
                    if ($windowsOllamaState.ApiReady) { $windowsNativeBridgeState = Get-LatticeValeNativeBridgeCapability $DistroName $windowsOllamaState }
                    $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
                    if (-not $nativeBackendUsable -and $windowsOllamaState.ApiReady) {
                        $directFallback = Resolve-LatticeValeNativeOllamaDirectFallback $DistroName $windowsOllamaState $windowsNativeBridgeState
                        $windowsOllamaState = $directFallback.OllamaState
                        $windowsNativeBridgeState = $directFallback.BridgeState
                        $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
                    }
                    if (-not $nativeBackendUsable) { Write-Warning 'Native Windows Ollama is not currently usable from the selected WSL distro. Choose managed WSL/Docker Ollama or correct the native path first.'; continue }
                    $ollamaBackend = 'windows-native'
                    $windowsOllamaTransport = [string]$windowsNativeBridgeState.Transport
                    $windowsOllamaHostAddress = [string]$windowsNativeBridgeState.WindowsHostIp
                    $windowsOllamaTargetAddress = [string]$windowsOllamaState.RelayTargetAddress
                    $windowsOllamaTargetPort = [int]$windowsOllamaState.RelayTargetPort
                    Show-NativeOllamaResourceWarning
                    $windowsOllamaBridgePort = Read-TcpPort 'WSL-only relay port for native Windows Ollama' $windowsOllamaBridgePort
                    break
                }

                while ($true) {
                    $ollamaTextRole = if ($localTextBackend -eq 'directml') { 'fallback' } else { 'text' }
                    $candidate = Read-Host "Local Ollama $ollamaTextRole model [current: $localTextModel; Enter preserves]"
                    if (-not [string]::IsNullOrWhiteSpace($candidate)) { $localTextModel = $candidate.Trim() }
                    if ($localTextModel -match '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$') { break }
                    Write-Host 'Use a valid Ollama model/tag.' -ForegroundColor Yellow
                }
                if ($honcho) {
                    while ($true) {
                        $candidate = Read-Host "Local Ollama embedding model [current: $localEmbeddingModel; Enter preserves]"
                        if (-not [string]::IsNullOrWhiteSpace($candidate)) { $localEmbeddingModel = $candidate.Trim() }
                        if ($localEmbeddingModel -match '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$') { break }
                        Write-Host 'Use a valid Ollama model/tag.' -ForegroundColor Yellow
                    }
                }
                if ($ollamaBackend -eq 'managed') {
                    $gpuState = Get-OllamaWslGpuPrerequisites $DistroName $linuxUser
                    Write-OllamaGpuPrerequisiteSummary $gpuState
                    $accelDefault = switch ($ollamaAcceleration) { 'cpu' {2}; 'nvidia' {3}; 'amd' {4}; default { $gpuPlan.OllamaAccelerationDefault } }
                    $nvidiaAccelLabel = 'NVIDIA GPU' + $(if ($gpuPlan.RecommendedOllamaAcceleration -eq 'nvidia') { ' [recommended for detected hardware]' } else { '' })
                    $amdAccelLabel = 'AMD GPU via ROCm' + $(if ($gpuPlan.RecommendedOllamaAcceleration -eq 'amd') { ' [recommended for detected hardware]' } else { '' })
                    while ($true) {
                        $accelChoice = Read-Menu 'Ollama hardware acceleration' @('Auto-detect supported acceleration; CPU fallback','CPU only',$nvidiaAccelLabel,$amdAccelLabel) $accelDefault
                        if ($accelChoice -eq 3 -and -not $gpuState.NvidiaWslReady) { Write-Warning 'NVIDIA WSL prerequisites are not currently verified.'; continue }
                        if ($accelChoice -eq 4 -and -not $gpuState.AmdDockerReady) { Write-Warning 'AMD/ROCm WSL prerequisites are not currently verified.'; continue }
                        $ollamaAcceleration = @('auto','cpu','nvidia','amd')[$accelChoice - 1]
                        $persistOllamaAcceleration = $true
                        break
                    }
                } else { $ollamaAcceleration = 'auto'; $persistOllamaAcceleration = $true }
            }
        }

        if ($changeScopes -contains 'runtime') {
            Write-Host "`n-- Runtime and Windows integration policy --" -ForegroundColor White
            $containerResourceLimits = Read-Choice 'Apply adaptive CPU/RAM ceilings to LatticeVale containers?' 'Recalculates one safe container-memory budget from the CPU/RAM currently visible to WSL, leaves extra WSL/Windows headroom, and applies conservative allocator/Synapse/PostgreSQL RAM tuning to enabled services. It auto-refreshes after a WSL restart when those limits change. User compose.override.yaml remains authoritative.' 'LatticeVale container ceilings are disabled.' $containerResourceLimits
            $unattended = Read-Choice 'Enable unattended Ubuntu security updates?' 'Changes only the managed unattended-updates policy.' 'Ubuntu security updates remain manual.' $unattended
            if ($wslLifetimeSupported) {
                $keepWslServicesRunning = Read-Choice 'Prevent WSL from auto-shutting down this running server instance?' 'Changes only LatticeVale ownership of the supported instance/VM idle-timeout keys required for persistent WSL server lifetime.' 'The existing LatticeVale WSL lifetime policy is disabled.' $keepWslServicesRunning
            }
            $autoStart = Read-Choice 'Start the stack automatically at Windows logon?' 'Changes only the LatticeVale scheduled auto-start task.' 'No full-stack auto-start task is configured.' $autoStart
            $windowsShortcuts = Read-Choice 'Create Windows desktop shortcuts to start and shut down this LatticeVale install?' 'Changes only installer-owned shortcuts for this exact install.' 'No LatticeVale desktop shortcuts are requested.' $windowsShortcuts
            Write-Info "Current container timezone: $timezone"
            if (Read-YesNo 'Change the saved container timezone?' $false) {
                while ($true) {
                    $timezoneInput = (Read-Host 'Container timezone (IANA name, e.g. America/Los_Angeles)').Trim()
                    if ($timezoneInput -match '^[A-Za-z0-9._+\-/]+$') { $timezone = $timezoneInput; break }
                    Write-Host 'Use a valid IANA timezone name.' -ForegroundColor Yellow
                }
            }
        }

        # Normalize only dependencies made impossible by an explicitly selected
        # change. This is not a second questionnaire: it prevents stale Windows
        # exposure policy from pointing at a service the user just disabled.
        if (-not $dashboard -and $tailscaleDashboard) {
            $tailscaleDashboard = $false
            Write-Info 'Dashboard was disabled, so its LatticeVale-owned Tailscale exposure will also be disabled. Other Tailscale configuration is preserved.'
        }
        if (-not $matrix -and $tailscaleMatrix) {
            $tailscaleMatrix = $false
            Write-Info 'Matrix was disabled, so its LatticeVale-owned Tailscale exposure will also be disabled. Matrix persistent data/identities remain preserved.'
        }
        if ($tailscale -and -not ($tailscaleDashboard -or $tailscaleMatrix)) {
            $tailscale = $false
            $installWindowsTailscale = $false
            Write-Info 'No LatticeVale service remains selected for Tailscale exposure, so LatticeVale-owned Tailscale integration will be disabled; unrelated Windows Tailscale configuration is not removed.'
        }

        Write-Info 'Scoped change questionnaire complete. Existing profiles, provider credentials, secondary Matrix identities/rooms, service data, and unselected settings were not replaced by questionnaire defaults except where a selected change made a dependent integration impossible.'
    }

} else {
    $old = $existingOptions
    $questionnaireMode = 'custom'
    if ($installMode -eq 'fresh') {
        $questionnaireMode = 'explicit'
        $script:RequireExplicitQuestionnaireChoices = $true
        Write-Info 'Fresh-install policy: LatticeVale will not assume optional host/system settings. Y/N, numeric, menu, and Tailscale-port choices require explicit input. Each applicable question shows a suggested choice/value for guidance; pressing Enter alone does not select it. Detected machine state is shown and may be accepted where applicable.'
    }

    if ($questionnaireMode -in @('custom','explicit')) {
        Write-Info 'Setup questionnaire: every optional item below is reviewed. Suggested choices/values are shown for guidance. On a fresh install, choices that could alter host/system behavior still require explicit input; a suggestion is not an automatic default.'
        $dashboard = Read-Choice 'Install Hermes Dashboard?' 'Browser UI for profiles, chat, config, sessions, and Kanban.' 'Dashboard is skipped; Hermes remains usable from the CLI.' ([bool](Get-OptionValue $old 'dashboard' $true))
        $multiAgent = Read-Choice 'Create multiple Hermes profiles?' 'Adds named secondary agents such as researcher/coder with separate profile state.' 'Only the default Hermes profile is configured.' ([bool](Get-OptionValue $old 'multiAgent' $true))
        $workers = @()
        $oldWorkers = @((Get-OptionValue $old 'workers' @()))
        if ($multiAgent) {
            $defaultWorkerCount = if ($oldWorkers.Count -gt 0) { $oldWorkers.Count } else { 1 }
            $workerCount = Read-Integer 'How many additional profiles should be created?' $defaultWorkerCount 1 8
            for ($i = 1; $i -le $workerCount; $i++) {
                $prior = if ($i -le $oldWorkers.Count) { $oldWorkers[$i-1] } else { $null }
                while ($true) {
                    $fallbackName = if ($i -eq 1) { 'assistant' } else { "worker$i" }
                    $defaultName = [string](Get-OptionValue $prior 'name' $fallbackName)
                    $name = Read-Host "Profile $i name [suggested: $defaultName; Enter accepts]"
                    if ([string]::IsNullOrWhiteSpace($name)) { $name = $defaultName }
                    $name = $name.Trim().ToLowerInvariant()
                    if ($name -match '^[a-z0-9][a-z0-9_-]{0,31}$' -and $name -ne 'default' -and -not ($workers.Name -contains $name)) { break }
                    Write-Host 'Use a unique name: 1-32 lowercase letters, numbers, _ or -, not "default".' -ForegroundColor Yellow
                }
                while ($true) {
                    $defaultDescription = [string](Get-OptionValue $prior 'description' 'General-purpose worker')
                    $description = Read-Host "Short role description for '$name' [suggested: $defaultDescription; Enter accepts]"
                    if ([string]::IsNullOrWhiteSpace($description)) { $description = $defaultDescription }
                    $description = $description.Trim()
                    if ($description.Length -le 240) { break }
                    Write-Host 'Keep the role description to 240 characters or fewer.' -ForegroundColor Yellow
                }
                $cloneDefault = [bool](Get-OptionValue $prior 'clone' $true)
                $shareConfig = Read-Choice "Clone the default provider/config into '$name'?" "Shares the default profile's AI provider/model credentials with '$name'." "Safe; Hermes setup runs separately for '$name' so it can use different provider/model credentials." $cloneDefault
                $workers += [pscustomobject]@{ name = $name; description = $description; clone = $shareConfig }
            }
        }

        $kanban = Read-Choice 'Enable Hermes Kanban?' 'Shared task board: substantive user work enters triage, while claimed worker lifecycle tools require real task context; simple chat stays direct.' 'Kanban is skipped; chat/profiles still work.' ([bool](Get-OptionValue $old 'kanban' $multiAgent))
        $kanbanMaxInProgress = 2
        $kanbanMaxInProgressPerProfile = 1
        if ($kanban) {
            $oldGlobalCap = [int](Get-OptionValue $old 'kanbanMaxInProgress' 2)
            if ($oldGlobalCap -lt 1 -or $oldGlobalCap -gt 8) { $oldGlobalCap = 2 }
            $kanbanMaxInProgress = Read-Integer 'Maximum concurrent Kanban workers across the board' $oldGlobalCap 1 8
            $oldProfileCap = [int](Get-OptionValue $old 'kanbanMaxInProgressPerProfile' 1)
            if ($oldProfileCap -lt 1 -or $oldProfileCap -gt $kanbanMaxInProgress) { $oldProfileCap = 1 }
            $kanbanMaxInProgressPerProfile = Read-Integer 'Maximum concurrent Kanban workers per profile' $oldProfileCap 1 $kanbanMaxInProgress
            Write-Info 'Defaults of 2 total / 1 per profile reduce provider-rate-limit bursts while still allowing two-profile parallelism.'
        }
        $matrix = Read-Choice 'Install Matrix/Synapse?' 'Private self-hosted messaging service connected to the default Hermes profile, with optional dedicated rooms for named profiles.' 'Matrix messaging is skipped; Hermes itself is unaffected.' ([bool](Get-OptionValue $old 'matrix' $false))
        # Keep each worker's identity/model choice and Matrix routing in one object. A room
        # can therefore never be provisioned independently of the profile whose model it uses.
        $workers = @(Complete-WorkerMatrixOptions $workers $matrix $true $true $existingMatrixDeployment)

        $tailscaleExeAtSelection = Get-WindowsTailscaleExe
        if ($tailscaleExeAtSelection) {
            $tsSelectionStatus = Get-WindowsTailscaleStatus $tailscaleExeAtSelection
            if ($tsSelectionStatus.BackendState -eq 'Running') {
                $label = if ($tsSelectionStatus.DNSName) { $tsSelectionStatus.DNSName } else { 'connected Windows node' }
                Write-Info "Detected Windows Tailscale: $label. This installer reuses it; nothing is installed inside WSL."
            } else { Write-Info "Detected Tailscale for Windows (state: $($tsSelectionStatus.BackendState))." }
        } else { Write-Info 'Tailscale for Windows was not detected. Installing the Windows client remains optional.' }
        $tailscale = Read-Choice 'Use Windows Tailscale for private remote access?' 'Uses this PC as the Tailscale node and proxies selected WSL localhost services.' 'All selected LatticeVale services remain local-only.' ([bool](Get-OptionValue $old 'tailscale' $false))
        $installWindowsTailscale = $false; $tailscaleDashboard = $false; $tailscaleMatrix = $false; $tailscaleDashboardPort = 0; $tailscaleMatrixPort = 0; $dashboardBridgePort = 19119; $matrixBridgePort = 18008
        if ($tailscale -and -not $tailscaleExeAtSelection) {
            $installWindowsTailscale = Read-Choice 'Install Tailscale for Windows if needed?' 'Installs the official Windows client; it remains separate from WSL.' 'Tailscale remote access is skipped; LatticeVale installation continues.' ([bool](Get-OptionValue $old 'installWindowsTailscale' $true))
            if (-not $installWindowsTailscale) { $tailscale = $false }
        }
        if ($tailscale -and $dashboard) {
            $tailscaleDashboard = Read-Choice 'Expose Dashboard through your Windows Tailscale node?' 'Publishes the authenticated Dashboard only to permitted tailnet users/devices.' 'Dashboard remains localhost-only.' ([bool](Get-OptionValue $old 'tailscaleDashboard' $false))
            if ($tailscaleDashboard) {
                $defaultDashPort = (Get-OptionTcpPort $old 'tailscaleDashboardPort' 9443); if ($defaultDashPort -lt 1) { $defaultDashPort = 9443 }
                $tailscaleDashboardPort = Read-TcpPort 'Dashboard Tailscale HTTPS port' $defaultDashPort
            }
        }
        if ($tailscale -and $matrix) {
            $tailscaleMatrix = Read-Choice 'Expose Matrix through your Windows Tailscale node?' 'Publishes Synapse privately through the same Windows Tailscale machine.' 'Matrix remains localhost-only.' ([bool](Get-OptionValue $old 'tailscaleMatrix' $false))
            if ($tailscaleMatrix) {
                $defaultMatrixPort = (Get-OptionTcpPort $old 'tailscaleMatrixPort' 443); if ($defaultMatrixPort -lt 1) { $defaultMatrixPort = 443 }
                if ($defaultMatrixPort -eq 8448) { $defaultMatrixPort = 443 }
                $disallow = if ($tailscaleDashboardPort -gt 0) { @($tailscaleDashboardPort) } else { @() }
                $tailscaleMatrixPort = Read-TcpPort 'Matrix Tailscale HTTPS port' $defaultMatrixPort $disallow
            }
        }
        if ($tailscale -and -not ($tailscaleDashboard -or $tailscaleMatrix)) { $tailscale = $false; $installWindowsTailscale = $false }

        $searxng = Read-Choice 'Install SearXNG + Valkey?' 'Self-hosted web-search routing that Hermes can use locally.' 'Self-hosted search is skipped; Hermes core still installs.' ([bool](Get-OptionValue $old 'searxng' $true))
        $qmd = Read-Choice 'Install QMD?' 'Indexes Markdown/Obsidian notes locally and exposes retrieval to Hermes through MCP.' 'Local note indexing/MCP is skipped.' ([bool](Get-OptionValue $old 'qmd' $false))
        $obsidian = Read-Choice 'Install/configure Obsidian for Windows?' 'Uses a Windows-native vault so Obsidian file watching remains reliable; Hermes/QMD mount that same folder through WSL.' 'Obsidian is skipped; QMD can still index the Linux stack vault manually.' ([bool](Get-OptionValue $old 'obsidian' $qmd))
        $obsidianVaultWindowsPath = ''
        $obsidianVaultWslPath = ''
        if ($obsidian) {
            while ($true) {
                $vaultInput = Read-Host 'Windows Obsidian vault folder (explicit Windows-local path required)'
                if ([string]::IsNullOrWhiteSpace($vaultInput)) {
                    Write-Host 'Enter the Windows-local folder you want to use as the Obsidian vault; no location is assumed or suggested.' -ForegroundColor Yellow
                    continue
                }
                $vaultInput = $vaultInput.Trim().Trim('"')
                if ($vaultInput -notmatch '^[A-Za-z]:\\') {
                    Write-Host 'Use a Windows-local drive path (for example D:\Documents\Obsidian Vault), not \\wsl.localhost, \\wsl$, or another UNC/network path.' -ForegroundColor Yellow
                    continue
                }
                try {
                    $obsidianVaultWindowsPath = [System.IO.Path]::GetFullPath($vaultInput)
                    $obsidianVaultWslPath = Convert-WindowsLocalPathToWslPath $DistroName $linuxUser $obsidianVaultWindowsPath
                    break
                } catch {
                    Write-Host $_.Exception.Message -ForegroundColor Yellow
                }
            }
            Write-Info "Windows Obsidian vault: $obsidianVaultWindowsPath"
            Write-Info "Hermes/QMD WSL source: $obsidianVaultWslPath"
        }
        Write-Info 'Ollama runtime note: when an Ollama-dependent feature is selected, LatticeVale asks explicitly where Ollama should run. Native Windows Ollama can be detected while stopped, but it must be running before LatticeVale can use and link its local API; selecting the native option will re-check it and can offer to start an already-installed copy. The alternative installs/manages Ollama inside this Ubuntu WSL distro with Docker. LatticeVale does not install or update the Windows Ollama application. LatticeVale-managed WSL/Docker Ollama can be installed automatically only when you explicitly choose that backend; native Windows Ollama is usable only after both its Windows-local API and safe WSL relay path are verified.'
        $honcho = Read-Choice 'Install fully self-hosted Honcho memory?' 'Runs Honcho API, Postgres/pgvector, Redis, plus an Ollama LLM and embedding model. If selected, the next Ollama question explicitly asks whether to reuse native Windows Ollama or install/manage Ollama inside WSL/Docker.' 'Honcho memory is skipped; Hermes built-in state remains available.' ([bool](Get-OptionValue $old 'honcho' $false))
        $hermesLocalAI = Read-Choice 'Use a LatticeVale local AI backend as the default Hermes AI provider?' 'Uses local inference for the main Hermes model. You can choose stable Ollama or the experimental PyTorch DirectML gateway; DirectML keeps Ollama as its fallback.' 'Hermes keeps the upstream interactive provider setup so you can choose an external or other provider.' ([bool](Get-OptionValue $old 'hermesLocalAI' $true))
        $localTextBackend = [string](Get-OptionValue $old 'localTextBackend' 'ollama')
        if ($localTextBackend -notin @('ollama','directml')) { $localTextBackend = 'ollama' }
        $directmlTextModel = [string](Get-OptionValue $old 'directmlTextModel' 'Qwen/Qwen2.5-1.5B-Instruct')
        if ($directmlTextModel -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') { $directmlTextModel = 'Qwen/Qwen2.5-1.5B-Instruct' }
        $directmlPort = (Get-OptionTcpPort $old 'directmlPort' 11436)
        $directmlAdapterName = [string](Get-OptionValue $old 'directmlAdapterName' '')
        $directmlGpuVendor = [string](Get-OptionValue $old 'directmlGpuVendor' '')
        if ($directmlGpuVendor -notin @('','amd','nvidia','intel','qualcomm')) { $directmlGpuVendor = '' }
        if ($honcho -or $hermesLocalAI) {
            $gpuPlan = Get-LatticeValeGpuAccelerationPlan $DistroName $linuxUser
            Write-LatticeValeGpuAccelerationPlan $gpuPlan
            $hasSavedTextBackend = ($null -ne $old -and $null -ne $old.PSObject.Properties['localTextBackend'])
            $textBackendDefault = if ($hasSavedTextBackend) { if ($localTextBackend -eq 'directml') { 2 } else { 1 } } else { $gpuPlan.TextBackendDefault }
            $ollamaBackendLabel = 'Ollama (stable; text inference uses the selected Ollama runtime)' + $(if ($gpuPlan.RecommendedTextBackend -eq 'ollama') { ' [recommended for detected hardware]' } else { '' })
            $directmlBackendLabel = 'PyTorch DirectML gateway (experimental; DirectX 12 GPU acceleration in WSL2, with automatic Ollama fallback)' + $(if ($gpuPlan.RecommendedTextBackend -eq 'directml') { ' [recommended for detected hardware]' } else { '' })
            $textBackendChoice = Read-Menu 'Local text inference backend' @(
                $ollamaBackendLabel,
                $directmlBackendLabel
            ) $textBackendDefault
            $localTextBackend = if ($textBackendChoice -eq 2) { 'directml' } else { 'ollama' }
            if ($localTextBackend -eq 'directml') {
                Write-Info 'DirectML is used for Hermes and Honcho text inference when healthy. Ollama remains installed/linked for automatic fallback and Honcho embeddings, so one backend failure does not strand the stack.'
                $directmlGpu = Select-LatticeValeDirectMLGpu $DistroName $linuxUser $directmlAdapterName $directmlGpuVendor
                if (-not $directmlGpu.UseDirectML) {
                    $localTextBackend = 'ollama'
                    $directmlAdapterName = ''
                    $directmlGpuVendor = ''
                    Write-Info 'Local text inference changed to Ollama because DirectML was not selected for the detected GPU environment.'
                } else {
                    $directmlAdapterName = [string]$directmlGpu.AdapterName
                    $directmlGpuVendor = [string]$directmlGpu.Vendor
                }
                if ($localTextBackend -eq 'directml') {
                while ($true) {
                    $candidate = Read-Host "DirectML Hugging Face text model [suggested: $directmlTextModel; Enter accepts]"
                    if (-not [string]::IsNullOrWhiteSpace($candidate)) { $directmlTextModel = $candidate.Trim() }
                    if ($directmlTextModel -match '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') { break }
                    Write-Host 'Use a Hugging Face repository ID in owner/model form.' -ForegroundColor Yellow
                }
                $directmlPort = Read-TcpPort 'DirectML WSL-host gateway port' $directmlPort
                }
            }
        }
        $ollamaBackend = 'managed'
        $windowsOllamaBridgePort = (Get-OptionTcpPort $old 'windowsOllamaBridgePort' 11435)
        $windowsOllamaTransport = [string](Get-OptionValue $old 'windowsOllamaTransport' 'windows-gateway-relay')
        if ($windowsOllamaTransport -notin @('windows-gateway-relay','wsl-localhost-relay','wsl-host-relay')) { $windowsOllamaTransport = 'windows-gateway-relay' }
        $windowsOllamaTargetAddress = [string](Get-OptionValue $old 'windowsOllamaTargetAddress' '127.0.0.1')
        $windowsOllamaTargetPort = (Get-OptionTcpPort $old 'windowsOllamaTargetPort' 11434)
        $windowsOllamaHostAddress = [string](Get-OptionValue $old 'windowsOllamaHostAddress' '')
        $windowsOllamaState = $null
        $windowsNativeBridgeState = $null
        if ($honcho -or $hermesLocalAI) {
            $windowsOllamaState = Get-WindowsNativeOllamaState
            Write-Info $windowsOllamaState.Detail
            if ($windowsOllamaState.ApiReady) {
                $windowsNativeBridgeState = Get-LatticeValeNativeBridgeCapability $DistroName $windowsOllamaState
                if ($windowsNativeBridgeState) { Write-Info $windowsNativeBridgeState.Detail }
                if ($windowsNativeBridgeState -and $windowsNativeBridgeState.Ready) {
                    $windowsOllamaTransport = [string]$windowsNativeBridgeState.Transport
                    $windowsOllamaHostAddress = [string]$windowsNativeBridgeState.WindowsHostIp
                    $windowsOllamaTargetAddress = [string]$windowsOllamaState.RelayTargetAddress
                    $windowsOllamaTargetPort = [int]$windowsOllamaState.RelayTargetPort
                }
            }
            $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
            $managedStatus = 'LatticeVale-managed Ollama inside WSL/Docker - install/manage Ollama in the selected Ubuntu distro (downloads the managed Ollama image and stores models in WSL)'
            $savedBackend = [string](Get-OptionValue $old 'ollamaBackend' '')
            $backendSuggested = if ($savedBackend -eq 'windows-native' -and $nativeBackendUsable) { 1 } elseif ($savedBackend -eq 'managed') { 2 } elseif ($nativeBackendUsable) { 1 } else { 2 }
            while ($true) {
                $nativeStatus = if ($nativeBackendUsable) {
                    if ($windowsOllamaState.Version) { "AVAILABLE - native Windows Ollama $($windowsOllamaState.Version) is running and the WSL relay path is verified" }
                    else { 'AVAILABLE - native Windows Ollama is running and the WSL relay path is verified' }
                } elseif (-not $windowsOllamaState.Installed) {
                    'UNAVAILABLE - no native Windows Ollama installation was detected'
                } elseif (-not $windowsOllamaState.ApiReady) {
                    'INSTALLED, NOT READY - native Windows Ollama must be running so its local API can be verified; choosing this option will offer to start/re-check it'
                } elseif (-not $windowsNativeBridgeState -or -not $windowsNativeBridgeState.Ready) {
                    $relayReason = if ($windowsNativeBridgeState -and $windowsNativeBridgeState.Detail) { $windowsNativeBridgeState.Detail } else { 'the Windows-to-WSL relay probe did not complete' }
                    "API READY, RELAY UNAVAILABLE - $relayReason"
                } else {
                    'UNAVAILABLE - native Windows Ollama prerequisites were not fully verified'
                }

                $backendChoice = Read-Menu 'Where should Ollama run?' @("Use native Windows Ollama: $nativeStatus", $managedStatus) $backendSuggested
                if ($backendChoice -eq 1) {
                    # Selecting native mode is also an explicit request to remediate/re-check it.
                    # This avoids a dead menu loop when Ollama is installed but stopped, while
                    # still refusing to guess or silently fall back to managed WSL Ollama.
                    $windowsOllamaState = Get-WindowsNativeOllamaState
                    if ($windowsOllamaState.Installed -and -not $windowsOllamaState.ApiReady) {
                        Write-Info 'Native Windows Ollama must be running before LatticeVale can use it. The installer can start the already-installed copy now, or you can open Ollama yourself and select this option again.'
                        $windowsOllamaState = Resolve-WindowsNativeOllamaForQuestionnaire $windowsOllamaState
                    }
                    $windowsNativeBridgeState = $null
                    if ($windowsOllamaState.ApiReady) {
                        $windowsNativeBridgeState = Get-LatticeValeNativeBridgeCapability $DistroName $windowsOllamaState
                        if ($windowsNativeBridgeState) { Write-Info $windowsNativeBridgeState.Detail }
                        if ($windowsNativeBridgeState -and $windowsNativeBridgeState.Ready) {
                            $windowsOllamaTransport = [string]$windowsNativeBridgeState.Transport
                            $windowsOllamaHostAddress = [string]$windowsNativeBridgeState.WindowsHostIp
                            $windowsOllamaTargetAddress = [string]$windowsOllamaState.RelayTargetAddress
                            $windowsOllamaTargetPort = [int]$windowsOllamaState.RelayTargetPort
                        }
                    }
                    $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
                    if (-not $nativeBackendUsable -and $windowsOllamaState.ApiReady) {
                        $directFallback = Resolve-LatticeValeNativeOllamaDirectFallback $DistroName $windowsOllamaState $windowsNativeBridgeState
                        $windowsOllamaState = $directFallback.OllamaState
                        $windowsNativeBridgeState = $directFallback.BridgeState
                        if ($windowsNativeBridgeState -and $windowsNativeBridgeState.Ready) {
                            $windowsOllamaTransport = [string]$windowsNativeBridgeState.Transport
                            $windowsOllamaHostAddress = [string]$windowsNativeBridgeState.WindowsHostIp
                            $windowsOllamaTargetAddress = [string]$windowsOllamaState.RelayTargetAddress
                            $windowsOllamaTargetPort = [int]$windowsOllamaState.RelayTargetPort
                        }
                        $nativeBackendUsable = ($windowsOllamaState.ApiReady -and $windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
                    }
                    if (-not $nativeBackendUsable) {
                        if (-not $windowsOllamaState.Installed) {
                            Write-Warning 'Native Windows Ollama is not installed. Install it on Windows first, then rerun Change installed components or choose the managed WSL/Docker backend.'
                        } elseif (-not $windowsOllamaState.ApiReady) {
                            Write-Warning "Native Windows Ollama is installed but its Windows-local API is not responding. Open/start Ollama on Windows (or allow LatticeVale to start the detected copy) and then select native Windows Ollama again. Detail: $($windowsOllamaState.Detail)"
                        } else {
                            $relayReason = if ($windowsNativeBridgeState -and $windowsNativeBridgeState.Detail) { $windowsNativeBridgeState.Detail } else { 'No safe Windows-to-WSL relay path was verified.' }
                            Write-Warning "Native Windows Ollama's API is running at $($windowsOllamaState.Endpoint), but LatticeVale cannot safely link it into the selected WSL distro. Opening Ollama again will not fix this relay condition. Detail: $relayReason"
                        }
                        Write-Info 'No managed Ollama fallback was selected automatically. Choose the WSL/Docker backend explicitly if you want LatticeVale to install/manage Ollama inside WSL.'
                        continue
                    }
                    $ollamaBackend = 'windows-native'
                    Show-NativeOllamaResourceWarning
                    Write-Info "Selected native Windows Ollama at $($windowsOllamaState.Endpoint). The installer will not pull/start the managed ollama/ollama image or create WSL Ollama model storage for this backend."
                    if ($windowsOllamaTransport -eq 'wsl-host-relay') {
                        Write-Info 'Direct WSL fallback transport selected: Ollama listens on Windows beyond loopback, but the installer-owned firewall allowance is restricted to the WSL-facing interface/local subnet. OLLAMA_ORIGINS is unchanged.'
                    } else {
                        Write-Info 'LatticeVale did not need to change OLLAMA_HOST. Only an installer-owned WSL-scoped relay is configured.'
                    }
                    while ($true) {
                        $windowsOllamaBridgePort = Read-TcpPort 'WSL-only relay port for native Windows Ollama' $windowsOllamaBridgePort
                        if ($windowsOllamaTransport -eq 'windows-gateway-relay' -and (Test-WindowsTcpPortInUse $windowsOllamaBridgePort)) {
                            $existingPaths = Get-LatticeValeNativeServicePaths $DistroName
                            $ownedTask = Get-ScheduledTask -TaskName $existingPaths.TaskName -ErrorAction SilentlyContinue
                            if ($ownedTask) { break }
                            Write-Host "Windows TCP port $windowsOllamaBridgePort is already listening and is not proven to be this LatticeVale bridge. Choose another port." -ForegroundColor Yellow
                            continue
                        }
                        if ($windowsOllamaTransport -in @('wsl-localhost-relay','wsl-host-relay')) {
                            Write-Info "WSL-local relay transport selected. Port $windowsOllamaBridgePort will bind only to Docker's WSL host-gateway interface and will be verified after Docker bootstrap."
                        }
                        break
                    }
                    break
                }
                $ollamaBackend = 'managed'
                Write-Info 'Selected LatticeVale-managed WSL/Docker Ollama. The installer will download/start the managed Ollama image and keep its models inside the selected Ubuntu distro.'
                break
            }
        }

        $localTextModel = [string](Get-OptionValue $old 'localTextModel' 'qwen3.5:4b')
        $localEmbeddingModel = [string](Get-OptionValue $old 'localEmbeddingModel' 'qwen3-embedding:4b')
        if ($honcho -or $hermesLocalAI) {
            if ($ollamaBackend -eq 'windows-native') {
                Write-Info 'Selected models are checked and, when missing, pulled through the native Windows Ollama API. They are not duplicated into WSL Ollama storage.'
            } else {
                Write-Info 'Selected Ollama models are downloaded into the selected WSL distro. The default 4B model favors broad compatibility; CPU-only inference can be slower.'
            }
            while ($true) {
                $ollamaTextRole = if ($localTextBackend -eq 'directml') { 'fallback' } else { 'text' }
                $candidate = Read-Host "Local Ollama $ollamaTextRole model [suggested: $localTextModel; Enter accepts]"
                if (-not [string]::IsNullOrWhiteSpace($candidate)) { $localTextModel = $candidate.Trim() }
                if ($localTextModel -match '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$') { break }
                Write-Host 'Use a valid Ollama model/tag (letters, numbers, ., _, :, /, -).' -ForegroundColor Yellow
            }
        }
        if ($honcho) {
            Write-Info 'Honcho uses a separate local embedding model. qwen3-embedding:4b supports the 1536-dimensional vectors used by this stack.'
            while ($true) {
                $candidate = Read-Host "Local Ollama embedding model [suggested: $localEmbeddingModel; Enter accepts]"
                if (-not [string]::IsNullOrWhiteSpace($candidate)) { $localEmbeddingModel = $candidate.Trim() }
                if ($localEmbeddingModel -match '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$') { break }
                Write-Host 'Use a valid Ollama model/tag (letters, numbers, ., _, :, /, -).' -ForegroundColor Yellow
            }
        }
        $ollamaAcceleration = 'cpu'
        if (($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'managed') {
            $savedAcceleration = [string](Get-OptionValue $old 'ollamaAcceleration' '')
            $accelDefault = if ($savedAcceleration) { switch ($savedAcceleration) { 'cpu' {2}; 'nvidia' {3}; 'amd' {4}; default {1} } } else { $gpuPlan.OllamaAccelerationDefault }
            $gpuState = Get-OllamaWslGpuPrerequisites $DistroName $linuxUser
            Write-OllamaGpuPrerequisiteSummary $gpuState
            $nvidiaLabel = if ($gpuState.NvidiaWslReady) {
                'NVIDIA GPU (selected distro currently exposes a usable WSL NVIDIA device; installer will reuse or configure NVIDIA Container Toolkit)'
            } else {
                'NVIDIA GPU [currently unavailable in selected distro: /dev/dxg + working nvidia-smi were not both verified]'
            }
            if ($gpuPlan.RecommendedOllamaAcceleration -eq 'nvidia') { $nvidiaLabel += ' [recommended for detected hardware]' }
            $amdLabel = if ($gpuState.AmdDockerReady) {
                'AMD GPU via ROCm (selected distro currently exposes /dev/kfd + /dev/dri on x86_64; installer uses the ROCm Ollama image)'
            } else {
                'AMD GPU via ROCm [currently unavailable for this Ollama Docker path: x86_64 + /dev/kfd + /dev/dri were not all verified]'
            }
            if ($gpuPlan.RecommendedOllamaAcceleration -eq 'amd') { $amdLabel += ' [recommended for detected hardware]' }
            while ($true) {
                $accelChoice = Read-Menu 'Ollama hardware acceleration' @(
                    'Auto-detect supported acceleration from the selected distro; use CPU when no supported GPU path is verified',
                    'CPU only (no GPU runtime/device changes)',
                    $nvidiaLabel,
                    $amdLabel
                ) $accelDefault
                if ($accelChoice -eq 3 -and -not $gpuState.NvidiaWslReady) {
                    Write-Warning 'NVIDIA mode was not accepted because the selected Ubuntu distro did not pass the WSL NVIDIA prerequisite probe. Choose Auto/CPU, or correct WSL GPU support and rerun.'
                    continue
                }
                if ($accelChoice -eq 4 -and -not $gpuState.AmdDockerReady) {
                    Write-Warning 'AMD/ROCm mode was not accepted because the selected Ubuntu distro does not currently expose the devices required by this Ollama Docker path. Choose Auto/CPU, link a detected native Windows Ollama instance, or configure a supported AMD WSL container path and rerun.'
                    continue
                }
                $ollamaAcceleration = @('auto','cpu','nvidia','amd')[$accelChoice - 1]
                break
            }
            Write-Info "Ollama acceleration policy: $ollamaAcceleration"
        } elseif (($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'windows-native') {
            $ollamaAcceleration = 'auto'
            Write-Info 'Ollama acceleration is owned by native Windows Ollama; LatticeVale does not assume or modify its GPU/CPU backend.'
        }
        $resourceDefault = $true
        if ($null -ne $old -and $null -ne $old.PSObject.Properties['containerResourceLimits']) {
            $resourceDefault = [bool](Get-OptionValue $old 'containerResourceLimits' $true)
        }
        $containerResourceLimits = Read-Choice 'Apply adaptive CPU/RAM ceilings to LatticeVale containers?' 'Measures the CPU/RAM actually visible inside WSL, reserves WSL/Docker/Windows headroom, divides the remaining memory budget across only enabled services, and applies conservative allocator/Synapse/PostgreSQL RAM tuning on smaller WSL VMs. It does not assume fallback hardware values and recalculates after a WSL restart if the allocation changes. Limits are ceilings, not reservations; compose.override.yaml remains authoritative.' 'Containers remain unrestricted by LatticeVale; Docker/WSL global limits and any user compose.override.yaml still apply.' $resourceDefault
        $unattended = Read-Choice 'Enable unattended Ubuntu security updates?' 'Automatically installs eligible Ubuntu security updates inside WSL.' 'Updates must be applied manually.' ([bool](Get-OptionValue $old 'unattendedUpdates' $true))
        $keepWslServicesRunning = $false
        if ($wslLifetimeSupported) {
            $keepWslServicesRunning = Read-Choice 'Prevent WSL from auto-shutting down this running server instance?' 'Uses WSL''s supported [general] instanceIdleTimeout=-1 plus [wsl2] vmIdleTimeout=-1 policies. This is not a polling loop or Windows auto-start; your normal launcher still owns startup.' 'Leaves WSL''s instance-idle policy unchanged; on affected WSL builds the distro may terminate even while server services are intended to stay available.' ([bool](Get-OptionValue $old 'keepWslServicesRunning' $tailscaleMatrix))
        }
        $autoStart = Read-Choice 'Start the stack automatically at Windows logon?' 'Creates a scheduled task that starts Docker/Hermes after sign-in. The small Windows Tailscale relay is separate and never wakes WSL unless this option is enabled.' 'Start LatticeVale with your normal launcher/./manage.sh start. The Windows relay may start at logon, but stays passive and does not start or keep WSL running.' ([bool](Get-OptionValue $old 'autoStart' $false))
        $windowsShortcuts = Read-Choice 'Create Windows desktop shortcuts to start and shut down this LatticeVale install?' 'Creates current-user Start and Shut Down shortcuts bound to this exact WSL distro, Linux user, and LatticeVale stack. Start follows install-options through manage.sh; Shut Down stops selected services/relay but intentionally does not terminate the distro, avoiding a known WSL 2.7.x hvsocket/session regression.' 'No desktop shortcuts are created. Existing non-LatticeVale shortcuts are never overwritten or removed.' ([bool](Get-OptionValue $old 'windowsShortcuts' $false))

        $savedTimezone = ''
        if ($null -ne $old -and $null -ne $old.PSObject.Properties['timezone']) {
            $savedTimezone = [string](Get-OptionValue $old 'timezone' '')
        }
        $detectedTimezone = Get-DetectedLinuxTimezone $DistroName $linuxUser
        $defaultTimezone = if (-not [string]::IsNullOrWhiteSpace($savedTimezone)) { $savedTimezone.Trim() } else { $detectedTimezone.Trim() }
        if (-not [string]::IsNullOrWhiteSpace($detectedTimezone)) { Write-Info "Detected Ubuntu timezone: $detectedTimezone" }
        Write-Info 'Container timezone uses an IANA name, for example America/Los_Angeles or Europe/London.'
        while ($true) {
            $timezonePrompt = if ([string]::IsNullOrWhiteSpace($defaultTimezone)) { 'Container timezone (explicit IANA name required)' } else { "Container timezone [detected/suggested: $defaultTimezone; Enter accepts]" }
            $timezoneInput = Read-Host $timezonePrompt
            if ([string]::IsNullOrWhiteSpace($timezoneInput)) {
                if ([string]::IsNullOrWhiteSpace($defaultTimezone)) {
                    Write-Host 'No saved or detected timezone is available; enter an IANA timezone explicitly.' -ForegroundColor Yellow
                    continue
                }
                $timezone = $defaultTimezone.Trim()
            } else {
                $timezone = $timezoneInput.Trim()
            }
            if ($timezone -match '^[A-Za-z0-9._+\-/]+$') { break }
            Write-Host 'Use a valid IANA timezone name, for example America/Los_Angeles or Europe/London.' -ForegroundColor Yellow
        }

    }

    # Explicit-choice mode is scoped to the fresh questionnaire only. Subsequent repair
    # prompts may reuse saved/detected state instead of re-asking every application choice.
    $script:RequireExplicitQuestionnaireChoices = $false

    $reservedLocalPorts = @()
    $hadPriorStackOptions = ($null -ne $old)
    if ($hadPriorStackOptions) {
        # v13.1-v13.9 used these fixed ports and did not record them. Preserve them for
        # services that were already selected so repair/change does not unexpectedly move URLs.
        $hermesApiPort = (Get-OptionTcpPort $old 'hermesApiPort' 8642)
    } else {
        $hermesApiPort = Resolve-LatticeValeLocalPort $DistroName 'Hermes API' 8642 $reservedLocalPorts
    }
    $reservedLocalPorts += $hermesApiPort

    # The Dashboard listener lives in the core Hermes container, whose port mapping is
    # present even when the Dashboard feature itself is disabled. A clean install must
    # therefore reserve a collision-free host port unconditionally.
    if ($hadPriorStackOptions) { $dashboardLocalPort = (Get-OptionTcpPort $old 'dashboardLocalPort' 9119) }
    else { $dashboardLocalPort = Resolve-LatticeValeLocalPort $DistroName 'Dashboard' 9119 $reservedLocalPorts }
    $reservedLocalPorts += $dashboardLocalPort

    $priorMatrix = [bool](Get-OptionValue $old 'matrix' $false)
    if ($matrix) {
        if ($hadPriorStackOptions -and $priorMatrix) { $matrixLocalPort = (Get-OptionTcpPort $old 'matrixLocalPort' 8008) }
        else { $matrixLocalPort = Resolve-LatticeValeLocalPort $DistroName 'Matrix' 8008 $reservedLocalPorts }
        $reservedLocalPorts += $matrixLocalPort
    } else { $matrixLocalPort = (Get-OptionTcpPort $old 'matrixLocalPort' 8008) }

    $priorSearxng = [bool](Get-OptionValue $old 'searxng' $false)
    if ($searxng) {
        if ($hadPriorStackOptions -and $priorSearxng) { $searxngLocalPort = (Get-OptionTcpPort $old 'searxngLocalPort' 8888) }
        else { $searxngLocalPort = Resolve-LatticeValeLocalPort $DistroName 'SearXNG' 8888 $reservedLocalPorts }
        $reservedLocalPorts += $searxngLocalPort
    } else { $searxngLocalPort = (Get-OptionTcpPort $old 'searxngLocalPort' 8888) }

    $priorHoncho = [bool](Get-OptionValue $old 'honcho' $false)
    if ($honcho) {
        if ($hadPriorStackOptions -and $priorHoncho) { $honchoLocalPort = (Get-OptionTcpPort $old 'honchoLocalPort' 8000) }
        else { $honchoLocalPort = Resolve-LatticeValeLocalPort $DistroName 'Honcho' 8000 $reservedLocalPorts }
        $reservedLocalPorts += $honchoLocalPort
    } else { $honchoLocalPort = (Get-OptionTcpPort $old 'honchoLocalPort' 8000) }
}

# Existing managed stacks keep their saved localhost ports when those ports are free
# or demonstrably owned by the current Compose project. If a foreign listener has
# claimed one since the prior run, move only that service to a safe free port.
if ($null -ne $existingOptions) {
    Write-Step 'Reconciling existing localhost port ownership'
    $repairReservedPorts = @()
    $hermesApiPort = Resolve-LatticeValeRepairLocalPort $DistroName $linuxHome 'Hermes API' $hermesApiPort 'hermes-agent' 8642 $repairReservedPorts
    $repairReservedPorts += $hermesApiPort
    # Dashboard is mapped by the core container even when the UI feature is disabled.
    $dashboardLocalPort = Resolve-LatticeValeRepairLocalPort $DistroName $linuxHome 'Dashboard' $dashboardLocalPort 'hermes-agent' 9119 $repairReservedPorts
    $repairReservedPorts += $dashboardLocalPort
    if ($matrix) {
        $matrixLocalPort = Resolve-LatticeValeRepairLocalPort $DistroName $linuxHome 'Matrix' $matrixLocalPort 'hermes-synapse' 8008 $repairReservedPorts
        $repairReservedPorts += $matrixLocalPort
    }
    if ($searxng) {
        $searxngLocalPort = Resolve-LatticeValeRepairLocalPort $DistroName $linuxHome 'SearXNG' $searxngLocalPort 'hermes-searxng' 8080 $repairReservedPorts
        $repairReservedPorts += $searxngLocalPort
    }
    if ($honcho) {
        $honchoLocalPort = Resolve-LatticeValeRepairLocalPort $DistroName $linuxHome 'Honcho' $honchoLocalPort 'hermes-honcho-api' 8000 $repairReservedPorts
        $repairReservedPorts += $honchoLocalPort
    }
}


# Tailscale Serve on Windows cannot reliably proxy WSL localhost directly on every WSL
# topology (upstream issue #9228). Selected remote services therefore receive an
# installer-owned Windows loopback TCP relay. In mirrored mode that relay targets WSL
# through Windows localhost; NAT/compatibility mode targets the current reachable WSL IPv4.
if ($tailscaleDashboard -or $tailscaleMatrix) {
    Remove-LegacyV14BridgeSupport $DistroName
    Remove-LegacyHermesManualRelay $DistroName
    # Stop only provably LatticeVale-owned current/orphan relays BEFORE allocating
    # bridge ports so an old install cannot reserve its own canonical ports.
    [void](Prepare-LatticeValeBridgePortsForReconcile $DistroName @(19119,18008,$dashboardBridgePort,$matrixBridgePort,$priorDashboardBridgePort,$priorMatrixBridgePort))
}
if ($tailscaleDashboard) {
    $priorOwned = ($priorDashboardBridgePort -gt 0)
    $dashboardBridgePort = Resolve-LatticeValeWindowsBridgePort 'Dashboard' 19119 $dashboardBridgePort $priorOwned @($hermesApiPort,$dashboardLocalPort,$matrixLocalPort,$searxngLocalPort,$honchoLocalPort,$tailscaleDashboardPort,$tailscaleMatrixPort)
}
if ($tailscaleMatrix) {
    $priorOwned = ($priorMatrixBridgePort -gt 0)
    $matrixBridgePort = Resolve-LatticeValeWindowsBridgePort 'Matrix' 18008 $matrixBridgePort $priorOwned @($hermesApiPort,$dashboardLocalPort,$matrixLocalPort,$searxngLocalPort,$honchoLocalPort,$tailscaleDashboardPort,$tailscaleMatrixPort,$dashboardBridgePort)
}

$wslNetworking = Get-WslGlobalNetworkingMode
$activeWslNetworkingMode = Get-WslNetworkingMode $DistroName
$wslLifetime = Get-WslGlobalInstanceIdleTimeout
$wslVmLifetime = Get-WslGlobalVmIdleTimeout
# Remote Tailscale endpoints can become unavailable if WSL is allowed to terminate,
# but LatticeVale must not silently override the user's WSL lifetime policy.
if ($wslLifetimeSupported -and ($tailscaleDashboard -or $tailscaleMatrix) -and -not $keepWslServicesRunning) {
    Write-Warning 'Remote Tailscale Dashboard/Matrix access is selected while persistent WSL service lifetime is disabled. LatticeVale will preserve that choice; remote endpoints may become unavailable when WSL terminates.'
}

$applyWslLifetimePolicy = ($keepWslServicesRunning -and ((-not $wslLifetime.Explicit -or $wslLifetime.Value -ne '-1') -or (-not $wslVmLifetime.Explicit -or $wslVmLifetime.Value -ne '-1')))
$wslNetworkingModeOwner = 'user'
$wslNetworkingModePolicy = if ($activeWslNetworkingMode) { $activeWslNetworkingMode } elseif ($wslNetworking.Mode) { $wslNetworking.Mode } else { 'unknown' }
$sharedNativeTailscale = (($tailscaleDashboard -or $tailscaleMatrix) -and ($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'windows-native')

# One observed networking policy coordinates native Windows Ollama and Windows Tailscale
# exposure, but v14.3.41 treats global WSL networkingMode as host/user-owned. Preserve a
# verified NAT/default/VirtioProxy path, and consume an already-working mirrored topology
# only when it was configured outside this installer. LatticeVale does not write or switch
# networkingMode in either clean-install or repair/update flows.
if ($activeWslNetworkingMode -eq 'mirrored') {
    Write-Warning 'Existing global WSL mirrored networking is active. LatticeVale will use this already-working user/host configuration when capability checks pass; ordinary configuration/runtime paths will not create, reapply, or require mirrored mode. If a later install/repair preflight fails with E_UNEXPECTED, the current LatticeVale release can offer bounded shutdown/retry recovery and, only after persistent failure plus explicit approval, a backed-up NAT compatibility fallback.'
}

# Native Windows Ollama and Windows-host Tailscale share the observed WSL topology,
# but v14.3.41 no longer owns or mutates networkingMode. A verified existing mirrored
# topology can still be consumed. NAT/default/VirtioProxy paths use the dynamic WSL-IP
# relay and the scoped native-Ollama bridge instead of a global .wslconfig mode switch.
if ($sharedNativeTailscale) {
    $sharedBridgeReady = ($windowsNativeBridgeState -and $windowsNativeBridgeState.Ready)
    if (-not $sharedBridgeReady) {
        Write-Warning "Native Windows Ollama and Tailscale remote exposure are both selected, but the current WSL topology does not provide a verified native-Ollama bridge. LatticeVale will not change global WSL networking. Reconfigure native Ollama with its explicit scoped direct-access fallback, or use LatticeVale-managed WSL/Docker Ollama."
    }
    if ($activeWslNetworkingMode -eq 'mirrored') {
        $wslNetworkingModeOwner = 'user-existing-mirrored'
        $wslNetworkingModePolicy = 'mirrored'
        Write-Info 'Shared WSL networking policy: existing mirrored mode (externally/user configured). LatticeVale is consuming the verified topology without taking ownership of or rewriting .wslconfig.'
    } else {
        $wslNetworkingModeOwner = 'shared-native-ollama-tailscale'
        $wslNetworkingModePolicy = if ($activeWslNetworkingMode) { $activeWslNetworkingMode } elseif ($wslNetworking.Explicit -and $wslNetworking.Mode -in @('nat','virtioproxy')) { $wslNetworking.Mode } else { 'nat' }
        if ($sharedBridgeReady) {
            Write-Info "Shared WSL networking policy: $wslNetworkingModePolicy. Native Ollama and Tailscale use verified scoped/dynamic relay paths; no global WSL networking change is required."
        } else {
            Write-Warning "Shared WSL networking policy remains '$wslNetworkingModePolicy'. No verified native-Ollama bridge is available, and LatticeVale will not change global WSL networking to create one."
        }
    }
} elseif (($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'windows-native' -and $windowsOllamaTransport -eq 'wsl-localhost-relay') {
    $wslNetworkingModeOwner = if ($activeWslNetworkingMode -eq 'mirrored') { 'user-existing-mirrored' } else { 'native-ollama' }
    $wslNetworkingModePolicy = if ($activeWslNetworkingMode) { $activeWslNetworkingMode } else { 'unknown' }
} elseif ($tailscaleDashboard -or $tailscaleMatrix) {
    $wslNetworkingModeOwner = if ($activeWslNetworkingMode -eq 'mirrored') { 'user-existing-mirrored' } else { 'tailscale' }
    $wslNetworkingModePolicy = if ($activeWslNetworkingMode) { $activeWslNetworkingMode } else { 'unknown' }
}

$repairOriginVersionForOptions = if ($repairOriginInfo) { [string]$repairOriginInfo.OriginVersion } else { $bundleVersion }
$repairOriginSchemaForOptions = if ($repairOriginInfo) { [int]$repairOriginInfo.OriginSchema } else { [int]$compat.InstallOptionsSchema }

$options = [ordered]@{
    schema = $compat.InstallOptionsSchema
    installerVersion = $bundleVersion
    installerMode = $installMode
    repairOriginVersion = $repairOriginVersionForOptions
    repairOriginSchema = $repairOriginSchemaForOptions
    universalRepairMigration = $universalRepairMigration
    questionnaireMode = $questionnaireMode
    dashboard = $dashboard
    multiAgent = $multiAgent
    workers = $workers
    kanban = $kanban
    kanbanMaxInProgress = $kanbanMaxInProgress
    kanbanMaxInProgressPerProfile = $kanbanMaxInProgressPerProfile
    matrix = $matrix
    tailscale = $tailscale
    tailscaleMode = if ($tailscale) { 'windows-host' } else { 'disabled' }
    wslNetworkingMode = $wslNetworkingModePolicy
    wslNetworkingModeOwner = $wslNetworkingModeOwner
    installWindowsTailscale = $installWindowsTailscale
    tailscaleDashboard = $tailscaleDashboard
    tailscaleDashboardPort = $tailscaleDashboardPort
    tailscaleMatrix = $tailscaleMatrix
    tailscaleMatrixPort = $tailscaleMatrixPort
    dashboardBridgePort = $dashboardBridgePort
    matrixBridgePort = $matrixBridgePort
    searxng = $searxng
    qmd = $qmd
    honcho = $honcho
    hermesLocalAI = $hermesLocalAI
    localTextBackend = $localTextBackend
    directmlTextModel = $directmlTextModel
    directmlPort = $directmlPort
    directmlAdapterName = if ($localTextBackend -eq 'directml') { $directmlAdapterName } else { '' }
    directmlGpuVendor = if ($localTextBackend -eq 'directml') { $directmlGpuVendor } else { '' }
    localTextModel = $localTextModel
    localEmbeddingModel = $localEmbeddingModel
    ollamaBackend = $ollamaBackend
    windowsOllamaBridgePort = $windowsOllamaBridgePort
    windowsOllamaTransport = if ($ollamaBackend -eq 'windows-native') { $windowsOllamaTransport } else { '' }
    windowsOllamaTargetAddress = if ($ollamaBackend -eq 'windows-native') { $windowsOllamaTargetAddress } else { '' }
    windowsOllamaTargetPort = if ($ollamaBackend -eq 'windows-native') { $windowsOllamaTargetPort } else { 11434 }
    windowsOllamaHostAddress = if ($ollamaBackend -eq 'windows-native' -and $windowsOllamaTransport -in @('windows-gateway-relay','wsl-host-relay')) { $windowsOllamaHostAddress } else { '' }
    windowsOllamaBridgeTaskName = if ($ollamaBackend -eq 'windows-native' -and $windowsOllamaTransport -eq 'windows-gateway-relay') { Get-LatticeValeNativeServiceTaskName $DistroName } else { '' }
    ollamaAcceleration = $ollamaAcceleration
    containerResourceLimits = $containerResourceLimits
    obsidian = $obsidian
    obsidianVaultWindowsPath = $obsidianVaultWindowsPath
    obsidianVaultWslPath = $obsidianVaultWslPath
    unattendedUpdates = $unattended
    keepWslServicesRunning = $keepWslServicesRunning
    autoStart = $autoStart
    windowsShortcuts = $windowsShortcuts
    timezone = $timezone
    hermesApiPort = $hermesApiPort
    dashboardLocalPort = $dashboardLocalPort
    matrixLocalPort = $matrixLocalPort
    searxngLocalPort = $searxngLocalPort
    honchoLocalPort = $honchoLocalPort
    resetCheckpoints = $resetCheckpoints
    forceProviderSetup = $forceProviderSetup
    forceProfileSetup = $forceProfileSetup
    rebuildMatrixIdentity = $rebuildMatrixIdentity
    repairMaintenance = $repairMaintenance
    forceManagedUpdate = $forceManagedUpdate
}
# Same-line legacy reconfigure/change paths may still intentionally preserve the absence
# of an acceleration-management field. Universal v14.5.43 Resume / repair migration
# normalizes that historical omission to explicit CPU before reaching this point.
if (-not $persistOllamaAcceleration) { [void]$options.Remove('ollamaAcceleration') }

Write-Host "`nSelected configuration:" -ForegroundColor White
Write-Host "  Mode: $installMode"
Write-Host "  Questionnaire: $questionnaireMode"
Write-Host "  Distro: $DistroName"
Write-Host "  Existing distro storage: $DistroStoragePath"
Write-Host "  Ubuntu release: $($selectedDistro.UbuntuVersion)"
Write-Host "  WSL distro mode: WSL2"
Write-Host "  WSL implementation: $(if ($wslInfo.Modern) { 'Store/MSIX' } else { 'legacy/inbox' })"
@(
    "Dashboard: $dashboard", "Multi-agent: $multiAgent", "Kanban: $kanban", "Matrix: $matrix",
    "Windows Tailscale integration: $tailscale", "Shared WSL networking policy: $wslNetworkingModePolicy ($wslNetworkingModeOwner)", "Tailscale Dashboard exposure: $tailscaleDashboard$(if ($tailscaleDashboard) { " (HTTPS $tailscaleDashboardPort)" } else { '' })", "Tailscale Matrix exposure: $tailscaleMatrix$(if ($tailscaleMatrix) { " (HTTPS $tailscaleMatrixPort)" } else { '' })", "SearXNG: $searxng", "QMD: $qmd", "Honcho (fully local): $honcho",
    "Hermes local AI: $hermesLocalAI$(if ($hermesLocalAI) { " (text backend=$localTextBackend)" } else { '' })", "DirectML text model: $(if (($honcho -or $hermesLocalAI) -and $localTextBackend -eq 'directml') { "$directmlTextModel (WSL-host port $directmlPort; GPU=$(if ($directmlAdapterName) { $directmlAdapterName } else { $directmlGpuVendor }))" } else { 'n/a' })", "Ollama fallback text model: $(if ($honcho -or $hermesLocalAI) { $localTextModel } else { 'n/a' })", "Honcho local embedding model: $(if ($honcho) { $localEmbeddingModel } else { 'n/a' })", "Ollama backend: $(if ($honcho -or $hermesLocalAI) { if ($ollamaBackend -eq 'windows-native') { 'native Windows Ollama via WSL-only relay' } else { 'LatticeVale-managed WSL/Docker' } } else { 'n/a' })", "Ollama acceleration: $(if ($honcho -or $hermesLocalAI) { if ($ollamaBackend -eq 'windows-native') { 'owned by native Windows Ollama' } else { $ollamaAcceleration } } else { 'n/a' })", "Native Ollama relay transport: $(if ($ollamaBackend -eq 'windows-native') { $windowsOllamaTransport } else { 'n/a' })", "Native Ollama WSL relay port: $(if ($ollamaBackend -eq 'windows-native') { $windowsOllamaBridgePort } else { 'n/a' })", "Adaptive container limits: $containerResourceLimits",
    "Local ports: Hermes API=$hermesApiPort$(if ($dashboard) { ", Dashboard=$dashboardLocalPort" } else { '' })$(if ($matrix) { ", Matrix=$matrixLocalPort" } else { '' })$(if ($searxng) { ", SearXNG=$searxngLocalPort" } else { '' })$(if ($honcho) { ", Honcho=$honchoLocalPort" } else { '' })",
    "Windows bridge ports: $(if ($tailscaleDashboard) { "Dashboard=$dashboardBridgePort " } else { '' })$(if ($tailscaleMatrix) { "Matrix=$matrixBridgePort" } else { '' })",
    "Obsidian: $obsidian$(if ($obsidian) { " ($obsidianVaultWindowsPath)" } else { '' })", "Kanban worker limits: $(if ($kanban) { "$kanbanMaxInProgress total / $kanbanMaxInProgressPerProfile per profile" } else { 'n/a' })", "Unattended updates: $unattended", "Repair maintenance: $repairMaintenance", "Universal repair migration: $universalRepairMigration", "Force managed software update now: $forceManagedUpdate", "Keep WSL services running: $keepWslServicesRunning", "Auto-start at Windows logon: $autoStart", "Windows Start/Shutdown shortcuts: $windowsShortcuts"
) | ForEach-Object { Write-Host "  $_" }
Write-Info 'Recovery model: verify live state first, preserve completed work, then resume the earliest incomplete/broken stage. Matrix precedes Hermes setup; Windows add-ons/Tailscale/auto-start remain last.'
if ($kanban) {
    Write-Info 'Kanban policy: substantive user requests enter triage; valid existing routing profiles are preserved, stale routing names are repaired from the discovered Hermes profile roster, and worker lifecycle tools require an actual claimed task context.'
}
Write-Info 'Skill-management policy: managed Hermes profiles receive validated skill-authoring/recovery guidance. Clean installs default automatic agent skill writes on; repair/update preserves an explicit existing skill write-approval choice.'
if (-not (Read-ChoiceExplicit 'Proceed with installation?' 'Confirms the selected existing Ubuntu distro, its verified storage partition, and component choices before packages or stack files are changed.' 'No changes are made; the installer exits.' $true)) {
    Write-Host 'No changes were made.'
    exit 0
}


# Do NOT restart WSL here. The Linux stack is configured/repaired first while the
# distro is already known-responsive. If a global networking change is required,
# apply it only after the resumable Linux stages finish successfully; this avoids
# putting package/build/model work immediately behind a WSL networking/HNS restart.

Write-Step 'Final existing-distro verification'
$distroVersion = Get-DistroWslVersion $DistroName
if ($distroVersion -ne 2) {
    throw "'$DistroName' is no longer confirmed as WSL2. This installer does not convert WSL1 distros; resolve the distro mode outside the installer and rerun."
}
$finalOs = Get-WslOsRelease $DistroName
$supportedUbuntu = @(Get-SupportedUbuntuVersions)
if (-not $finalOs.Success -or $finalOs.Id -ne 'ubuntu' -or $supportedUbuntu -notcontains $finalOs.VersionId) {
    $detected = if ($finalOs.Success) { "$($finalOs.Id) $($finalOs.VersionId)".Trim() } elseif ($finalOs.Detail) { $finalOs.Detail } else { 'unknown distro' }
    throw "'$DistroName' is no longer confirmed as a supported Ubuntu distro (detected: $detected). No WSL distro was created or replaced."
}
$userProbe = Invoke-WslDirectCapture $DistroName 'root' 'id' @('-u', $linuxUser)
if (-not $userProbe.Success) {
    throw "The selected existing Ubuntu user '$linuxUser' no longer exists. No account will be created automatically; fix the distro user and rerun."
}
$uidProbe = Invoke-WslDirectCapture $DistroName 'root' 'id' @('-u', $linuxUser)
$gidProbe = Invoke-WslDirectCapture $DistroName 'root' 'id' @('-g', $linuxUser)
$selectedUid = 0; $selectedGid = 0
if (-not $uidProbe.Success -or -not $gidProbe.Success -or
    -not [int]::TryParse($uidProbe.Text.Trim(), [ref]$selectedUid) -or
    -not [int]::TryParse($gidProbe.Text.Trim(), [ref]$selectedGid)) {
    throw "Could not verify UID/GID for the selected Ubuntu user '$linuxUser'."
}
if ($selectedUid -lt 1000 -or $selectedUid -gt 65534 -or $selectedGid -lt 1000 -or $selectedGid -gt 65534) {
    throw "The selected Ubuntu user '$linuxUser' has UID:GID $selectedUid`:$selectedGid. Hermes Docker remapping in this bundle requires both values to be 1000-65534."
}
$homeWritableProbe = Invoke-WslDirectCapture $DistroName $linuxUser 'bash' @('-lc', 'test -d "$HOME" -a -w "$HOME"')
if (-not $homeWritableProbe.Success) {
    throw "The selected Ubuntu user's home directory is not writable by '$linuxUser'. Repair that account/home ownership before running the installer."
}

if ($forceManagedUpdate) {
    Write-Step $(if ($universalRepairMigration) { 'Creating cumulative repair-migration safety backup' } else { 'Creating pre-update managed-stack safety backup' })
    $backupReason = if ($universalRepairMigration) { 'Cumulative Resume / repair migration requires a verified rollback backup before installer-managed software is refreshed.' } else { 'Update / repair requires a verified rollback backup before installer-managed software is refreshed.' }
    Write-Info "$backupReason This bundle supplies its own backup helper so a broken/outdated installed manage.sh cannot block the repair that would replace it."
    Write-Info 'The helper runs as WSL root only for this backup operation so container-owned persistent files can be read safely, dumps running Synapse/Honcho PostgreSQL databases, briefly stops only currently-running LatticeVale containers for a consistent filesystem snapshot, archives persistent configuration/data (including local Ollama data when present), restores the previously-running containers, and returns backup ownership to the selected Linux user.'

    $backupSource = Join-Path $PSScriptRoot 'linux\pre-update-safety-backup.sh'
    if (-not (Test-Path -LiteralPath $backupSource -PathType Leaf)) {
        throw "Update / repair cannot start because the bundled pre-update safety-backup helper is missing: $backupSource"
    }
    $backupStage = "/tmp/latticevale-preupdate-$([guid]::NewGuid().ToString('N'))"
    $backupStageCreate = Invoke-WslDirectCapture $DistroName 'root' 'install' @('-d','-m','0755',$backupStage) 30
    if (-not $backupStageCreate.Success) {
        $detail = Get-SafeDiagnosticExcerpt $backupStageCreate.Text 700
        if (-not $detail) { $detail = "wsl.exe/Linux install exited with code $($backupStageCreate.ExitCode)" }
        throw "Update / repair could not create its root-owned WSL backup staging directory '$backupStage': $detail"
    }
    try {
        $backupHelperLinux = "$backupStage/pre-update-safety-backup.sh"
        Copy-LocalFileToWslRoot $DistroName $backupSource $backupHelperLinux '0755'
        $preUpdateBackup = Invoke-WslDirectCapture $DistroName 'root' $backupHelperLinux @($stackLinuxPath,[string]$selectedUid,[string]$selectedGid) 3600
        if (-not $preUpdateBackup.Success) {
            $parts = @()
            if ($preUpdateBackup.TimedOut) { $parts += 'backup exceeded the 3600-second safety timeout' }
            if (-not [string]::IsNullOrWhiteSpace([string]$preUpdateBackup.StdErr)) { $parts += (Get-SafeDiagnosticExcerpt $preUpdateBackup.StdErr 1000) }
            if (-not [string]::IsNullOrWhiteSpace([string]$preUpdateBackup.StdOut)) { $parts += (Get-SafeDiagnosticExcerpt $preUpdateBackup.StdOut 1000) }
            if ($preUpdateBackup.ExitCode -ne $null) { $parts += "exit code $($preUpdateBackup.ExitCode)" }
            $backupDetail = (($parts | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique) -join ' | ')
            if (-not $backupDetail) { $backupDetail = 'backup helper failed without stdout/stderr diagnostics' }
            throw "The managed repair/update stopped before software refresh because the bundle-owned safety backup failed. Detail: $backupDetail`nNo installer-managed software refresh was started. The existing stack/data was left in place; correct the reported backup problem and rerun the current full installer."
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$preUpdateBackup.StdOut)) { Write-Host $preUpdateBackup.StdOut.Trim() }
        if (-not [string]::IsNullOrWhiteSpace([string]$preUpdateBackup.StdErr)) { Write-Warning $preUpdateBackup.StdErr.Trim() }
    } finally {
        [void](Invoke-WslDirectCapture $DistroName 'root' 'rm' @('-rf',$backupStage) 30)
    }
}

if ($repairMaintenance) {
    # A nearly-full managed WSL filesystem may not have enough room even for the tiny
    # installer staging directory. Reclaim only disposable root-owned package/staging
    # residue before copying bundle files. The Linux bootstrap repeats this safely after
    # entry so interrupted repair runs remain self-contained.
    Write-Step 'Preparing aged managed stack for repair staging'
    $repairPrepCommand = "apt-get clean >/dev/null 2>&1 || true; find /tmp -mindepth 1 -maxdepth 1 -type d \( -name 'latticevale-installer-*' -o -name 'latticevale-audit-*' -o -name 'hermes-installer-*' -o -name 'hermes-audit-*' \) -mmin +60 -exec rm -rf -- {} + 2>/dev/null || true"
    $repairPrep = Invoke-WslDirectCapture $DistroName 'root' 'bash' @('-lc', $repairPrepCommand) 90
    if (-not $repairPrep.Success) {
        Write-Warning 'Could not complete the pre-staging disposable-cache cleanup. Repair will still attempt normal staging; persistent application data was not touched.'
    }
}

if ($obsidian) {
    Write-Step 'Reconciling legacy Obsidian vault mounts'
    Repair-LegacyObsidianStackVaultMount $DistroName $stackLinuxPath $obsidianVaultWslPath $selectedUid $selectedGid
}

if (($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'windows-native') {
    Write-Step 'Linking native Windows Ollama to the selected WSL distro'
    if ($windowsOllamaTransport -ne 'wsl-host-relay') {
        Remove-LatticeValeWindowsNativeOllamaDirectWslAccess $DistroName $true
    }
    $nativeOllamaNow = Get-WindowsNativeOllamaState
    if (-not $nativeOllamaNow.ApiReady) {
        throw "Native Windows Ollama was selected, but its verified Windows-local API is no longer responding. Start Windows Ollama or rerun and select the managed WSL/Docker backend. No native Ollama setting was changed."
    }
    if ($windowsOllamaTransport -eq 'windows-gateway-relay') {
        $nativePaths = Write-LatticeValeNativeOllamaBridgeConfig $DistroName $windowsOllamaBridgePort $nativeOllamaNow.RelayTargetAddress $nativeOllamaNow.RelayTargetPort $stackLinuxPath
        if (-not (Register-LatticeValeNativeServiceTask $nativePaths $autoStart)) {
            throw 'Could not register the installer-owned native Windows Ollama bridge. The Windows Ollama process and its settings were left unchanged.'
        }
        if (-not (Start-LatticeValeNativeOllamaBridge $nativePaths $DistroName $windowsOllamaBridgePort 45)) {
            throw 'The native Windows Ollama API is running, but LatticeVale could not verify its NAT-style WSL-only relay from the selected Ubuntu distro. No OLLAMA_HOST or native Ollama network setting was changed.'
        }
        Write-Info "Verified native Windows Ollama $($nativeOllamaNow.Endpoint) through NAT-style WSL-only relay port $windowsOllamaBridgePort."
    } elseif ($windowsOllamaTransport -eq 'wsl-localhost-relay') {
        if (-not (Test-WslHttpEndpointDirect $DistroName ([string]$nativeOllamaNow.RelayTargetAddress) ([int]$nativeOllamaNow.RelayTargetPort) '/api/version')) {
            throw "Native Windows Ollama was selected through WSL localhost transport, but '$DistroName' can no longer reach the Windows API at $($nativeOllamaNow.RelayTargetAddress):$($nativeOllamaNow.RelayTargetPort). The stack is unchanged; verify the current WSL networking mode or select managed WSL/Docker Ollama."
        }
        Write-Info "Verified WSL-to-Windows localhost access for native Ollama $($nativeOllamaNow.Endpoint). A WSL-local relay will be bound only to Docker's host-gateway interface after Docker bootstrap so bridge-mode containers can use it."
    } elseif ($windowsOllamaTransport -eq 'wsl-host-relay') {
        $directHost = Get-WindowsHostIpv4ForWsl $DistroName
        if (-not (Test-LatticeValeBridgeIpv4 $directHost) -or -not (Test-WslHttpEndpointDirect $DistroName $directHost ([int]$nativeOllamaNow.RelayTargetPort) '/api/version')) {
            throw "Native Windows Ollama was selected through the direct WSL fallback, but '$DistroName' can no longer reach the Windows API through the WSL-facing host address. Rerun Resume / repair so LatticeVale can reconcile OLLAMA_HOST and its scoped firewall rule."
        }
        Write-Info "Verified direct WSL access to native Ollama at ${directHost}:$($nativeOllamaNow.RelayTargetPort). A WSL-local relay will expose it only to Docker's host-gateway interface for bridge-mode containers."
    } else {
        throw "Unsupported native Ollama relay transport '$windowsOllamaTransport'. Rerun setup and reselect the Ollama backend."
    }
} else {
    Remove-LatticeValeNativeServiceSupport $DistroName
    Remove-LatticeValeWindowsNativeOllamaDirectWslAccess $DistroName $true
}

Write-Step 'Bootstrapping Docker and the selected LatticeVale stack inside Ubuntu'
# Stage through wsl.exe stdin rather than Windows drive automounts or the WSL UNC
# file provider. Command execution is the only cross-boundary capability required.
$stageName = "latticevale-installer-$([guid]::NewGuid().ToString('N'))"
$stageLinux = "/tmp/$stageName"
$mkdirProbe = Invoke-WslDirectCapture $DistroName 'root' 'install' @('-d', '-m', '0700', "$stageLinux", "$stageLinux/linux", "$stageLinux/stack")
if (-not $mkdirProbe.Success) {
    throw "Could not create the private WSL staging directory '$stageLinux'."
}
try {
    Copy-LocalFileToWslRoot $DistroName (Join-Path $PSScriptRoot 'compatibility.conf') "$stageLinux/compatibility.conf" '0600'
    Copy-LocalFileToWslRoot $DistroName (Join-Path $PSScriptRoot 'linux\bootstrap.sh') "$stageLinux/linux/bootstrap.sh" '0600'
    foreach ($file in @('compose.yaml','Dockerfile.qmd','patch-qmd-bind.py','configure-stack.sh','manage.sh','state-audit.py','latticevale_readonly.py','repair-plan.py','audit-free.py','checkpoint-metadata.json','qmd-index-cycle.sh','native-ollama-relay.py','native-ollama-relay.sh','directml-gateway.py','directml-gateway.sh','directml-requirements.txt')) {
        Copy-LocalFileToWslRoot $DistroName (Join-Path $PSScriptRoot "stack\$file") "$stageLinux/stack/$file" '0600'
    }
    $optionsJson = $options | ConvertTo-Json -Depth 8 -Compress
    $optionsB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($optionsJson))
    $forceManagedUpdateArg = if ($forceManagedUpdate) { 'true' } else { 'false' }
    Invoke-LatticeValeWslInteractiveGuarded $DistroName @('-d', $DistroName, '-u', 'root', '--', 'bash', "$stageLinux/linux/bootstrap.sh", $linuxUser, $optionsB64, $bundleVersion, $forceManagedUpdateArg) 14400 30 20 4
} finally {
    [void](Invoke-WslDirectCapture $DistroName 'root' 'rm' @('-rf', $stageLinux))
}

# If an older repair used the NAT-style Windows scheduled relay and the newly verified
# transport is WSL-localhost, remove only that obsolete installer-owned Windows relay
# after the new Linux-side relay has successfully completed bootstrap.
if (($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'windows-native' -and $windowsOllamaTransport -in @('wsl-localhost-relay','wsl-host-relay')) {
    Remove-LatticeValeNativeServiceSupport $DistroName
}

# Only now, after all resumable Linux stages have completed, change global WSL
# policy. A .wslconfig restart must never interrupt model pulls, database setup, or
# other Linux repair work. Lifetime and networking changes are applied before one
# bounded WSL restart whenever possible.
$wslGlobalConfigChanged = $false
$globalWslRestartLikely = $false
if ($applyWslLifetimePolicy) { $globalWslRestartLikely = $true }
if ($globalWslRestartLikely) {
    # Ask before writing .wslconfig because applying a global WSL change requires a
    # global WSL shutdown; declining must leave the user's global config untouched.
    [void](Confirm-LatticeValeGlobalWslRestart $DistroName)
}
if ($applyWslLifetimePolicy) {
    Write-Step 'Applying persistent WSL service-instance + VM lifetime policy'
    $lifetimeUpdate = Set-WslGlobalIdleTimeoutsDisabled $wslLifetime.Path
    if ($lifetimeUpdate.Changed) {
        $wslGlobalConfigChanged = $true
        if ($lifetimeUpdate.Backup) { Write-Info "Backed up .wslconfig to: $($lifetimeUpdate.Backup)" }
    }
    $currentLifetime = Get-WslGlobalInstanceIdleTimeout
    $currentVmLifetime = Get-WslGlobalVmIdleTimeout
    if (-not $currentLifetime.Explicit -or $currentLifetime.Value -ne '-1' -or -not $currentVmLifetime.Explicit -or $currentVmLifetime.Value -ne '-1') {
        throw 'LatticeVale could not apply both [general] instanceIdleTimeout=-1 and [wsl2] vmIdleTimeout=-1 to .wslconfig. The Linux stack is preserved; correct the WSL configuration and rerun.'
    }
}
if ($wslGlobalConfigChanged) {
    [void](Restart-LatticeValeWslForGlobalConfigChange $DistroName 180)
    if (($honcho -or $hermesLocalAI) -and $ollamaBackend -eq 'windows-native') {
        Write-Step 'Refreshing native Windows Ollama bridge after WSL networking restart'
        $nativeRefresh = Invoke-WslDirectCapture $DistroName 'root' '/usr/local/sbin/hermes-stack-start' @() 360
        if (-not $nativeRefresh.Success) {
            throw 'WSL restarted successfully, but the selected native Windows Ollama bridge/consumer containers could not be refreshed against the new WSL host address. The stack is preserved; rerun Resume / repair.'
        }
    }
}
if ($keepWslServicesRunning) {
    Write-Step 'Validating WSL service-instance persistence'
    if (-not (Test-LatticeValeWslPersistence $DistroName 75)) {
        throw "WSL distro '$DistroName' stopped during the 75-second persistence test even though LatticeVale configured both WSL idle-timeout disable keys. This matches a WSL lifecycle failure rather than an application/container failure. Existing stack data is preserved. Check 'wsl --version', .wslconfig, and current Microsoft WSL issues before rerunning Resume / repair."
    }
    Write-Info "WSL distro '$DistroName' remained running through the idle observation window."
}

# The Linux-side verifier has already confirmed service health. Confirm the Windows
# host can actually reach the localhost-published endpoints too; WSL normally
# forwards these automatically, but customized WSL networking can disable/break it.
Write-Step 'Verifying Windows localhost access to WSL services'
$windowsReachability = @{}
foreach ($endpoint in @(
    @{ Key='Hermes API'; Selected=$true; Port=$hermesApiPort },
    @{ Key='Dashboard'; Selected=$dashboard; Port=$dashboardLocalPort },
    @{ Key='Matrix'; Selected=$matrix; Port=$matrixLocalPort },
    @{ Key='SearXNG'; Selected=$searxng; Port=$searxngLocalPort },
    @{ Key='Honcho'; Selected=$honcho; Port=$honchoLocalPort }
)) {
    if (-not $endpoint.Selected) { continue }
    $reachable = $false
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        if (Test-LocalTcpPort ([int]$endpoint.Port)) { $reachable = $true; break }
        Start-Sleep -Milliseconds 500
    }
    $windowsReachability[$endpoint.Key] = $reachable
    if ($reachable) {
        Write-Info "$($endpoint.Key): Windows 127.0.0.1:$($endpoint.Port) - OK"
    } else {
        Write-Warning "$($endpoint.Key) is healthy inside WSL but Windows cannot currently reach 127.0.0.1:$($endpoint.Port). WSL localhost forwarding/networking appears customized or unavailable. The Linux stack is preserved; fix WSL networking and rerun before relying on Windows/Tailscale access."
    }
}

$windowsAppsState = if ($obsidian) { 'PARTIAL' } else { 'DISABLED' }
$windowsAppsDetail = if ($obsidian) { 'Selected Windows add-on has not yet been verified in this run.' } else { 'No Windows add-ons selected.' }

# Optional Windows applications are deliberately installed only after the Linux/Docker stack has
# configured successfully. A failure in the core stack therefore does not leave unrelated Windows
# applications installed as a side effect of a partial run.
if ($obsidian) {
    Write-Step 'Installing selected Windows applications'
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Warning 'winget is not installed. The selected Obsidian Windows add-on will be skipped; the Linux stack remains installed.'
        $windowsAppsState = 'PARTIAL'
        $windowsAppsDetail = 'winget unavailable; the selected Windows add-on was skipped.'
    } else {
        $windowsAppsOk = $true
        $present = Test-WingetPackageInstalled 'Obsidian.Obsidian'
        if ($present -eq $true) {
            Write-Info 'Obsidian is already installed; treating the requested Windows add-on as configured.'
        } else {
            $appProbe = Invoke-NativeProcessPassthrough 'winget.exe' @('install','--exact','--id','Obsidian.Obsidian','--accept-package-agreements','--accept-source-agreements','--silent','--disable-interactivity') 1200
            $presentAfter = Test-WingetPackageInstalled 'Obsidian.Obsidian'
            if (-not $appProbe.Success -and $presentAfter -ne $true) { $windowsAppsOk = $false; Write-Warning 'Obsidian is still not present after the bounded WinGet install attempt; install it manually if desired.' }
        }
        if ($windowsAppsOk) {
            $windowsAppsState = 'CONFIGURED'
            $windowsAppsDetail = 'Selected Windows add-on is present/configured according to live WinGet inventory.'
        } else {
            $windowsAppsState = 'PARTIAL'
            $windowsAppsDetail = 'The selected Windows add-on did not complete.'
        }
    }
}

# Tailscale remains Windows-only. Because Windows Tailscale Serve cannot reliably proxy
# WSL localhost directly on every topology, LatticeVale inserts an installer-owned
# Windows loopback relay. Mirrored mode uses localhost as the stable relay target; NAT
# retains bounded WSL-IPv4 discovery and refresh.
$previousTailscaleInfo = Get-TailscaleInfoFromWsl $DistroName $linuxUser
$tailscaleExe = Get-WindowsTailscaleExe

$oldDashboardPort = 0; $oldMatrixPort = 0; $oldDashboardBridgePort = 0; $oldMatrixBridgePort = 0
if ($previousTailscaleInfo.ContainsKey('MODE') -and $previousTailscaleInfo['MODE'] -eq 'windows-host') {
    if ($previousTailscaleInfo.ContainsKey('DASHBOARD_HTTPS_PORT')) { [void][int]::TryParse($previousTailscaleInfo['DASHBOARD_HTTPS_PORT'], [ref]$oldDashboardPort) }
    if ($previousTailscaleInfo.ContainsKey('MATRIX_HTTPS_PORT')) { [void][int]::TryParse($previousTailscaleInfo['MATRIX_HTTPS_PORT'], [ref]$oldMatrixPort) }
    if ($previousTailscaleInfo.ContainsKey('DASHBOARD_BRIDGE_PORT')) { [void][int]::TryParse($previousTailscaleInfo['DASHBOARD_BRIDGE_PORT'], [ref]$oldDashboardBridgePort) }
    if ($previousTailscaleInfo.ContainsKey('MATRIX_BRIDGE_PORT')) { [void][int]::TryParse($previousTailscaleInfo['MATRIX_BRIDGE_PORT'], [ref]$oldMatrixBridgePort) }
}
$oldDashboardBackendPort = if ($oldDashboardBridgePort -gt 0) { $oldDashboardBridgePort } else { $priorDashboardLocalPort }
$oldMatrixBackendPort = if ($oldMatrixBridgePort -gt 0) { $oldMatrixBridgePort } else { $priorMatrixLocalPort }
$bridgePaths = $null; $bridgeReady = $false; $bridgeTaskReady = $false; $bridgeWslIp = ''; $bridgeTargetAddress = ''

if ($tailscale) {
    Write-Step 'Configuring Windows Tailscale access to selected WSL services'
    if (-not $tailscaleExe -and $installWindowsTailscale) { $tailscaleExe = Install-WindowsTailscale }

    if (-not $tailscaleExe) {
        Write-Warning 'Tailscale for Windows is unavailable. Tailscale exposure was skipped; the LatticeVale stack remains available locally.'
    } else {
        $tsStatus = Ensure-WindowsTailscaleConnected $tailscaleExe
        if ($tsStatus.BackendState -ne 'Running') {
            Write-Warning "Windows Tailscale did not reach Running state. Remote exposure was skipped; the LatticeVale stack remains available locally."
        } else {
            $trackedDashboardPort = $oldDashboardPort
            $trackedMatrixPort = $oldMatrixPort
            $dashboardCleanupBlocked = $false
            $matrixCleanupBlocked = $false

            # Remove legacy/direct or changed installer-owned Serve rules before rebuilding.
            if ($oldDashboardPort -gt 0 -and (-not $tailscaleDashboard -or $oldDashboardPort -ne $tailscaleDashboardPort -or $oldDashboardBackendPort -ne $dashboardBridgePort)) {
                if (Disable-WindowsTailscaleServe $tailscaleExe $oldDashboardPort $oldDashboardBackendPort 'Dashboard') { $trackedDashboardPort = 0 } else { $dashboardCleanupBlocked = $true }
            }
            if ($oldMatrixPort -gt 0 -and (-not $tailscaleMatrix -or $oldMatrixPort -ne $tailscaleMatrixPort -or $oldMatrixBackendPort -ne $matrixBridgePort)) {
                if (Disable-WindowsTailscaleServe $tailscaleExe $oldMatrixPort $oldMatrixBackendPort 'Matrix') { $trackedMatrixPort = 0 } else { $matrixCleanupBlocked = $true }
            }

            if (($tailscaleDashboard -and -not $dashboardCleanupBlocked) -or ($tailscaleMatrix -and -not $matrixCleanupBlocked)) {
                Write-Step 'Creating Windows-native WSL relay for Tailscale'
                $bridgeBackendPorts = @()
                if ($tailscaleDashboard -and -not $dashboardCleanupBlocked) { $bridgeBackendPorts += $dashboardLocalPort }
                if ($tailscaleMatrix -and -not $matrixCleanupBlocked) { $bridgeBackendPorts += $matrixLocalPort }
                $bridgeSeedIp = ''
                if ($wslNetworkingModePolicy -eq 'mirrored') {
                    Write-Info 'Mirrored WSL networking is active. The Windows Tailscale relay will target WSL services through 127.0.0.1 and does not require a VM IPv4.'
                } else {
                    $bridgeSeedIp = Resolve-LatticeValeReachableWslIpv4 $DistroName $bridgeBackendPorts 20
                    if (Test-LatticeValeBridgeIpv4 $bridgeSeedIp) {
                        Write-Info "Resolved and verified WSL IPv4 $bridgeSeedIp before starting the persistent relay task."
                    } else {
                        Write-Warning 'The installer could not pre-resolve a directly reachable WSL IPv4; the relay task will use its own bounded compatibility probes/recovery.'
                    }
                }
                $bridgePaths = Write-LatticeValeBridgeConfig $DistroName ($tailscaleDashboard -and -not $dashboardCleanupBlocked) $dashboardLocalPort $dashboardBridgePort ($tailscaleMatrix -and -not $matrixCleanupBlocked) $matrixLocalPort $matrixBridgePort $bridgeSeedIp $wslNetworkingModePolicy
                # The Windows relay is cheap and does not keep WSL alive. Start it at Windows logon
                # whenever remote exposure is selected so Tailscale always has a localhost listener.
                # Only the separate stack auto-start option grants permission to wake/recover WSL.
                $bridgeTaskReady = Register-LatticeValeBridgeRefreshTask $bridgePaths $true $autoStart
                if ($bridgeTaskReady) { $bridgeReady = Invoke-LatticeValeBridgeRefresh $bridgePaths 120 }
                if ($bridgeReady) {
                    $bridgeTargetAddress = Get-LatticeValeBridgeLastTargetAddress $bridgePaths
                    $bridgeWslIp = Get-LatticeValeBridgeLastWslIp $bridgePaths
                    if ($bridgeTargetAddress -eq '127.0.0.1') {
                        Write-Info 'Windows-native WSL relay active through mirrored localhost.'
                    } else {
                        Write-Info "Windows-native WSL relay active through WSL IPv4 $bridgeTargetAddress."
                    }
                } else {
                    Write-Warning 'Tailscale remote exposure was skipped because the Windows-native WSL relay could not be verified.'
                }
            }

            if ($tailscaleDashboard -and -not $dashboardCleanupBlocked -and $bridgeReady) {
                $portState = Get-WindowsTailscaleServePortState $tailscaleExe $tailscaleDashboardPort $dashboardBridgePort
                if (-not $portState.Known) {
                    Write-Warning "Could not safely inspect Tailscale Serve HTTPS port $tailscaleDashboardPort. Dashboard exposure was skipped."
                } elseif ($portState.InUse -and $portState.MatchesExpected) {
                    $trackedDashboardPort = $tailscaleDashboardPort
                    Write-Info "Adopted existing compatible Tailscale Dashboard Serve mapping on HTTPS port $tailscaleDashboardPort."
                } elseif ($portState.InUse) {
                    $resolution = Resolve-UnownedTailscaleServeConflict $tailscaleExe $tailscaleDashboardPort $dashboardBridgePort 'Dashboard' $portState
                    if ($resolution -eq 'adopt') {
                        $trackedDashboardPort = $tailscaleDashboardPort
                    } elseif ($resolution -eq 'replace' -and (Enable-WindowsTailscaleServe $tailscaleExe $tailscaleDashboardPort $dashboardBridgePort 'Dashboard')) {
                        $trackedDashboardPort = $tailscaleDashboardPort
                    } else {
                        Write-Warning "Dashboard Tailscale exposure was left unchanged/skipped on HTTPS port $tailscaleDashboardPort."
                    }
                } elseif (Enable-WindowsTailscaleServe $tailscaleExe $tailscaleDashboardPort $dashboardBridgePort 'Dashboard') {
                    $trackedDashboardPort = $tailscaleDashboardPort
                }
            }

            if ($tailscaleMatrix -and -not $matrixCleanupBlocked -and $bridgeReady) {
                $portState = Get-WindowsTailscaleServePortState $tailscaleExe $tailscaleMatrixPort $matrixBridgePort
                if (-not $portState.Known) {
                    Write-Warning "Could not safely inspect Tailscale Serve HTTPS port $tailscaleMatrixPort. Matrix exposure was skipped."
                } elseif ($portState.InUse -and $portState.MatchesExpected) {
                    $trackedMatrixPort = $tailscaleMatrixPort
                    Write-Info "Adopted existing compatible Tailscale Matrix Serve mapping on HTTPS port $tailscaleMatrixPort."
                } elseif ($portState.InUse) {
                    $resolution = Resolve-UnownedTailscaleServeConflict $tailscaleExe $tailscaleMatrixPort $matrixBridgePort 'Matrix' $portState
                    if ($resolution -eq 'adopt') {
                        $trackedMatrixPort = $tailscaleMatrixPort
                    } elseif ($resolution -eq 'replace' -and (Enable-WindowsTailscaleServe $tailscaleExe $tailscaleMatrixPort $matrixBridgePort 'Matrix')) {
                        $trackedMatrixPort = $tailscaleMatrixPort
                    } else {
                        Write-Warning "Matrix Tailscale exposure was left unchanged/skipped on HTTPS port $tailscaleMatrixPort."
                    }
                } elseif (Enable-WindowsTailscaleServe $tailscaleExe $tailscaleMatrixPort $matrixBridgePort 'Matrix') {
                    $trackedMatrixPort = $tailscaleMatrixPort
                }
            }

            $dnsName = $tsStatus.DNSName
            if (-not $dnsName -and $previousTailscaleInfo.ContainsKey('TAILSCALE_DNS')) { $dnsName = $previousTailscaleInfo['TAILSCALE_DNS'] }

            if ($tailscaleDashboard -and $trackedDashboardPort -eq $tailscaleDashboardPort -and $dnsName) {
                $dashboardPublicUrl = Get-TailscaleHttpsUrl $dnsName $tailscaleDashboardPort
                if (-not (Test-HttpsEndpoint $dashboardPublicUrl 20)) {
                    Write-Warning "Dashboard Tailscale URL did not pass its end-to-end HTTPS test: $dashboardPublicUrl"
                    [void](Disable-WindowsTailscaleServe $tailscaleExe $tailscaleDashboardPort $dashboardBridgePort 'Dashboard')
                    $trackedDashboardPort = 0
                }
            }

            if ($tailscaleMatrix -and $trackedMatrixPort -eq $tailscaleMatrixPort -and $dnsName) {
                $matrixPublicUrl = Get-TailscaleHttpsUrl $dnsName $tailscaleMatrixPort
                [void](Set-SynapsePublicBaseUrl $DistroName $linuxUser $linuxHome $matrixPublicUrl)
                if (-not (Test-HttpsEndpoint "$matrixPublicUrl/_matrix/client/versions" 30)) {
                    Write-Warning "Matrix Tailscale URL did not pass its end-to-end HTTPS test: $matrixPublicUrl"
                    [void](Disable-WindowsTailscaleServe $tailscaleExe $tailscaleMatrixPort $matrixBridgePort 'Matrix')
                    $trackedMatrixPort = 0
                    # Roll back the advertised client URL as well. A failed remote exposure
                    # must never leave an otherwise healthy local Synapse advertising a dead
                    # Tailscale endpoint after repair/reconciliation.
                    [void](Set-SynapsePublicBaseUrl $DistroName $linuxUser $linuxHome "http://localhost:$matrixLocalPort")
                }
            } elseif ($matrix) {
                [void](Set-SynapsePublicBaseUrl $DistroName $linuxUser $linuxHome "http://localhost:$matrixLocalPort")
            }

            if ($trackedDashboardPort -gt 0 -or $trackedMatrixPort -gt 0) {
                # Do not rewrite the relay config here. Write-LatticeValeBridgeConfig intentionally
                # stops a prior long-running relay before replacing files; doing that after
                # end-to-end verification would immediately tear down the working listener.
                # Any requested-but-unpublished relay remains localhost-only and harmless.
                $infoDashBridge = if ($trackedDashboardPort -gt 0) { $dashboardBridgePort } else { 0 }
                $infoMatrixBridge = if ($trackedMatrixPort -gt 0) { $matrixBridgePort } else { 0 }
                $taskNameForInfo = if ($bridgePaths) { $bridgePaths.TaskName } else { '' }
                Set-TailscaleInfoInWsl $DistroName $linuxUser $dnsName $trackedDashboardPort $trackedMatrixPort $infoDashBridge $infoMatrixBridge $bridgeWslIp $taskNameForInfo $true $bridgeTargetAddress $wslNetworkingModePolicy $wslNetworkingModeOwner
                if ($dnsName) {
                    if ($trackedDashboardPort -gt 0) { Write-Host "Tailscale Dashboard: $(Get-TailscaleHttpsUrl $dnsName $trackedDashboardPort)" -ForegroundColor Green }
                    if ($trackedMatrixPort -gt 0) { Write-Host "Tailscale Matrix: $(Get-TailscaleHttpsUrl $dnsName $trackedMatrixPort)" -ForegroundColor Green }
                }
            } else {
                Remove-TailscaleInfoInWsl $DistroName $linuxUser
                # If this run actually deployed a relay but verification failed, keep the
                # exact script/config after unregistering the dead task. This makes a later
                # diagnostic inspect the failed version instead of accidentally selecting
                # an older manual relay artifact left in the same directory.
                $preserveFailedRelay = ($null -ne $bridgePaths -and -not $bridgeReady)
                Remove-LatticeValeBridgeSupport $DistroName -PreserveArtifacts:$preserveFailedRelay
            }
        }
    }
} else {
    $trackedDashboardPort = $oldDashboardPort
    $trackedMatrixPort = $oldMatrixPort
    if ($oldDashboardPort -gt 0 -or $oldMatrixPort -gt 0) {
        if ($tailscaleExe) {
            Write-Step 'Removing prior installer-owned Windows Tailscale exposure'
            if ($oldDashboardPort -gt 0 -and (Disable-WindowsTailscaleServe $tailscaleExe $oldDashboardPort $oldDashboardBackendPort 'Dashboard')) { $trackedDashboardPort = 0 }
            if ($oldMatrixPort -gt 0 -and (Disable-WindowsTailscaleServe $tailscaleExe $oldMatrixPort $oldMatrixBackendPort 'Matrix')) { $trackedMatrixPort = 0 }
        } else {
            Write-Warning 'Windows Tailscale is unavailable, so prior Serve mappings could not be safely removed.'
        }
    }
    if ($trackedDashboardPort -eq 0 -and $trackedMatrixPort -eq 0) {
        Remove-LatticeValeBridgeSupport $DistroName
        Remove-TailscaleInfoInWsl $DistroName $linuxUser
        if ($matrix) { [void](Set-SynapsePublicBaseUrl $DistroName $linuxUser $linuxHome "http://localhost:$matrixLocalPort") }
    } else {
        $savedDns = if ($previousTailscaleInfo.ContainsKey('TAILSCALE_DNS')) { $previousTailscaleInfo['TAILSCALE_DNS'] } else { '' }
        $previousBridgeAutoStart = ([string]($previousTailscaleInfo['BRIDGE_AUTOSTART'])).Trim().ToLowerInvariant() -eq 'true'
        $previousBridgeTarget = if ($previousTailscaleInfo.ContainsKey('BRIDGE_TARGET_ADDRESS')) { [string]$previousTailscaleInfo['BRIDGE_TARGET_ADDRESS'] } else { [string]$previousTailscaleInfo['WSL_BRIDGE_IP'] }
        $previousNetworkingMode = if ($previousTailscaleInfo.ContainsKey('WSL_NETWORKING_MODE')) { [string]$previousTailscaleInfo['WSL_NETWORKING_MODE'] } else { $wslNetworkingModePolicy }
        $previousNetworkingOwner = if ($previousTailscaleInfo.ContainsKey('WSL_NETWORKING_MODE_OWNER')) { [string]$previousTailscaleInfo['WSL_NETWORKING_MODE_OWNER'] } else { $wslNetworkingModeOwner }
        Set-TailscaleInfoInWsl $DistroName $linuxUser $savedDns $trackedDashboardPort $trackedMatrixPort $oldDashboardBridgePort $oldMatrixBridgePort ([string]($previousTailscaleInfo['WSL_BRIDGE_IP'])) ([string]($previousTailscaleInfo['BRIDGE_TASK_NAME'])) $previousBridgeAutoStart $previousBridgeTarget $previousNetworkingMode $previousNetworkingOwner
        Write-Warning 'One or more prior Tailscale mappings could not be safely removed; bridge metadata was retained for a later repair run.'
    }
}
$tailscaleState = 'DISABLED'
$tailscaleDetail = 'Windows Tailscale integration not selected.'
$finalTailscaleInfo = Get-TailscaleInfoFromWsl $DistroName $linuxUser
if ($tailscale) {
    $dashTracked = (-not $tailscaleDashboard)
    $matrixTracked = (-not $tailscaleMatrix)
    if ($tailscaleDashboard -and $finalTailscaleInfo.ContainsKey('DASHBOARD_HTTPS_PORT')) {
        $dashTracked = ($finalTailscaleInfo['DASHBOARD_HTTPS_PORT'] -eq [string]$tailscaleDashboardPort)
    }
    if ($tailscaleMatrix -and $finalTailscaleInfo.ContainsKey('MATRIX_HTTPS_PORT')) {
        $matrixTracked = ($finalTailscaleInfo['MATRIX_HTTPS_PORT'] -eq [string]$tailscaleMatrixPort)
    }
    $bridgeTracked = $true
    if ($tailscaleDashboard) { $bridgeTracked = $bridgeTracked -and $finalTailscaleInfo.ContainsKey('DASHBOARD_BRIDGE_PORT') -and ($finalTailscaleInfo['DASHBOARD_BRIDGE_PORT'] -eq [string]$dashboardBridgePort) }
    if ($tailscaleMatrix) { $bridgeTracked = $bridgeTracked -and $finalTailscaleInfo.ContainsKey('MATRIX_BRIDGE_PORT') -and ($finalTailscaleInfo['MATRIX_BRIDGE_PORT'] -eq [string]$matrixBridgePort) }
    $bridgeTaskTracked = (-not ($tailscaleDashboard -or $tailscaleMatrix))
    if ($tailscaleDashboard -or $tailscaleMatrix) {
        $expectedBridgeTaskName = Get-LatticeValeBridgeTaskName $DistroName
        $bridgeTask = Get-ScheduledTask -TaskName $expectedBridgeTaskName -ErrorAction SilentlyContinue
        $bridgeTaskTracked = ($null -ne $bridgeTask)
    }
    if ($dashTracked -and $matrixTracked -and $bridgeTracked -and $bridgeTaskTracked) {
        $tailscaleState = 'CONFIGURED'
        $tailscaleDetail = 'Requested installer-owned Windows Tailscale Serve + native WSL relay mappings and persistent relay task are recorded.'
    } else {
        $tailscaleState = 'PARTIAL'
        $tailscaleDetail = 'One or more requested Windows Tailscale Serve mappings were not completed.'
    }
} elseif ($finalTailscaleInfo.Count -gt 0) {
    $tailscaleState = 'PARTIAL'
    $tailscaleDetail = 'Tailscale was disabled, but prior installer-owned mapping metadata remains for safe cleanup.'
}

$taskName = Get-LatticeValeScheduledTaskName $DistroName
$legacyV14TaskName = Get-LegacyV14ScheduledTaskName $DistroName
$legacyV14Task = Get-ScheduledTask -TaskName $legacyV14TaskName -ErrorAction SilentlyContinue
if (Test-LatticeValeLegacyTaskOwnedByCurrentUser $legacyV14Task $DistroName) {
    Unregister-ScheduledTask -TaskName $legacyV14TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Info 'Removed the verified v14.0 per-distro auto-start task; LatticeVale now uses a neutral task name.'
}
$legacyTaskName = ('Hermes' + ' WSL Docker Stack') 
$legacyTask = Get-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue
if (Test-LatticeValeLegacyTaskOwnedByCurrentUser $legacyTask $DistroName) {
    Unregister-ScheduledTask -TaskName $legacyTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Info "Removed the current user's legacy v12 auto-start task; v13 uses a per-user/per-distro task name."
}
if ($autoStart) {
    Write-Step 'Registering selected stack to start at Windows logon'
    try {
        $wslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
        $taskArgs = ((@('-d', $DistroName, '-u', 'root', '--', '/usr/local/sbin/hermes-stack-start') | ForEach-Object { ConvertTo-WindowsProcessArgument ([string]$_) }) -join ' ')
        $action = New-ScheduledTaskAction -Execute $wslExe -Argument $taskArgs
        $windowsIdentity = Get-CurrentWindowsIdentityName
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $windowsIdentity
        $principal = New-ScheduledTaskPrincipal -UserId $windowsIdentity -LogonType Interactive -RunLevel Highest
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    } catch {
        Write-Warning "The logon task could not be created: $($_.Exception.Message). The stack can still be started with ./manage.sh start."
    }
} else {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
}

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$autoStartValidated = $false
$autoStartValidationDetail = ''
if ($autoStart -and $task) {
    # Validate the exact scheduled-task action now, while the stack is known-good,
    # rather than discovering at the next logon that quoting/startup failed.
    try {
        $validationStarted = Get-Date
        Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
        $deadline = [DateTime]::UtcNow.AddSeconds(180)
        do {
            Start-Sleep -Seconds 1
            $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
            if ($task -and $taskInfo -and $task.State -ne 'Running' -and $taskInfo.LastRunTime -ge $validationStarted.AddSeconds(-2)) {
                if ([int]$taskInfo.LastTaskResult -eq 0) {
                    $autoStartValidated = $true
                    $autoStartValidationDetail = "Scheduled task executed successfully at $($taskInfo.LastRunTime)."
                } else {
                    $autoStartValidationDetail = "Scheduled task returned LastTaskResult=$($taskInfo.LastTaskResult)."
                }
                break
            }
        } while ([DateTime]::UtcNow -lt $deadline)
        if (-not $autoStartValidated -and [string]::IsNullOrWhiteSpace($autoStartValidationDetail)) {
            $autoStartValidationDetail = 'Scheduled task did not complete within the 180-second validation window.'
        }
    } catch {
        $autoStartValidationDetail = "Scheduled task validation failed: $($_.Exception.Message)"
    }
}
if ($autoStart) {
    $autoStartState = if ($task -and $autoStartValidated) { 'CONFIGURED' } else { 'PARTIAL' }
    if ($task -and $autoStartValidated) {
        $autoStartDetail = $autoStartValidationDetail
    } elseif ($task) {
        $autoStartDetail = $autoStartValidationDetail
        Write-Warning "LatticeVale auto-start task exists but did not pass its immediate execution check. $autoStartValidationDetail"
    } else {
        $autoStartDetail = 'Requested scheduled task is missing.'
    }
} else {
    $autoStartState = if ($task) { 'PARTIAL' } else { 'DISABLED' }
    $autoStartDetail = if ($task) { 'Auto-start disabled but installer task is still present.' } else { 'Auto-start not selected.' }
}

Write-Step 'Reconciling optional Windows desktop shortcuts'
if ($windowsShortcuts) {
    $shortcutResult = Install-LatticeValeDesktopShortcuts $DistroName $linuxUser $stackLinuxPath $bundleVersion $ollamaBackend
    if ($shortcutResult.Status -eq 'CONFIGURED') {
        Write-Info "Start shortcut: $($shortcutResult.Paths.StartShortcut)"
        Write-Info "Shutdown shortcut: $($shortcutResult.Paths.ShutdownShortcut)"
    } else {
        Write-Warning $shortcutResult.Detail
    }
} else {
    $shortcutResult = Remove-LatticeValeDesktopShortcuts $DistroName $linuxUser $stackLinuxPath
    if ($shortcutResult.Status -eq 'PARTIAL') { Write-Warning $shortcutResult.Detail }
}
$shortcutState = $shortcutResult.Status
$shortcutDetail = $shortcutResult.Detail

Set-InstallerWindowsState $DistroName $linuxUser $linuxHome @{
    windowsApps = @{ status = $windowsAppsState; detail = $windowsAppsDetail }
    tailscale = @{ status = $tailscaleState; detail = $tailscaleDetail }
    autoStart = @{ status = $autoStartState; detail = $autoStartDetail }
    shortcuts = @{ status = $shortcutState; detail = $shortcutDetail }
}

$stackUnc = Convert-LinuxPathToWslUnc $DistroName $stackLinuxPath
$legacyStackUnc = Convert-LinuxPathToWslUnc $DistroName $stackLinuxPath -Legacy
Write-Host "`nInstallation/configuration complete." -ForegroundColor Green
Write-Host "Stack folder: $stackUnc"
Write-Info "If an older WSL build does not resolve \\wsl.localhost, use: $legacyStackUnc"
Write-Host "Verify (recommended): wsl -d $DistroName -u $linuxUser -- bash -lc 'cd `"`$HOME/hermes-stack`" && ./manage.sh verify'"
Write-Host "Detailed audit:       wsl -d $DistroName -u $linuxUser -- bash -lc 'cd `"`$HOME/hermes-stack`" && ./manage.sh audit'"
Write-Host "Status snapshot:      wsl -d $DistroName -u $linuxUser -- bash -lc 'cd `"`$HOME/hermes-stack`" && ./manage.sh status'"
if ($windowsShortcuts -and $shortcutState -eq 'CONFIGURED') {
    Write-Host "Start shortcut:         $($shortcutResult.Paths.StartShortcut)"
    Write-Host "Shutdown shortcut:      $($shortcutResult.Paths.ShutdownShortcut)"
}
Write-Info 'Immediately after WSL/Docker starts, selected services may briefly report STARTING. The verify command waits for that normal startup window before recommending repair.'
if ($dashboard) {
    if ($windowsReachability.ContainsKey('Dashboard') -and $windowsReachability['Dashboard']) {
        Write-Host "Dashboard: http://localhost:$dashboardLocalPort (use the username/password entered during Linux configuration)"
    } else {
        Write-Warning "Dashboard is running inside WSL on port $dashboardLocalPort, but Windows localhost access did not verify in this run."
    }
}
if ($obsidian) {
    Write-Host "Obsidian vault (Windows): $obsidianVaultWindowsPath"
    Write-Host "Hermes/QMD vault source (WSL): $obsidianVaultWslPath"
    Write-Host 'Open that Windows folder as the vault in the Obsidian app. Do not open the \\wsl.localhost stack path as a Windows Obsidian vault.'
}
