#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateNotNullOrEmpty()][string]$Endpoint = 'http://127.0.0.1:11436',
    [ValidateRange(10,600)][int]$TimeoutSeconds = 240,
    [Parameter(Mandatory=$true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$base = $Endpoint.TrimEnd('/')
$health = Invoke-RestMethod -Method Get -Uri "$base/health" -TimeoutSec 15
if ($health.status -ne 'ok' -or $health.selected_backend -ne 'directml' -or
    $health.directml_ready -ne $true -or $health.force_fallback -eq $true -or
    [string]::IsNullOrWhiteSpace([string]$health.model)) {
    throw 'DirectML gateway is not ready for a non-fallback inference check.'
}

$body = @{
    model = [string]$health.model
    messages = @(@{ role='user'; content='Reply with the single word OK.' })
    max_tokens = 8
    stream = $false
} | ConvertTo-Json -Depth 8 -Compress
$timer = [Diagnostics.Stopwatch]::StartNew()
$reply = Invoke-RestMethod -Method Post -Uri "$base/v1/chat/completions" `
    -ContentType 'application/json' -Body $body -TimeoutSec $TimeoutSeconds
$timer.Stop()
$content = [string]$reply.choices[0].message.content
if ([string]::IsNullOrWhiteSpace($content)) { throw 'DirectML inference returned no completion text.' }

$result = [ordered]@{
    schema = 1
    status = 'passed'
    selectedBackendWasDirectML = $true
    directMLRuntimeReady = $true
    fallbackWasForced = $false
    adapterIdentityWasReported = -not [string]::IsNullOrWhiteSpace([string]$health.requested_adapter_name)
    inferenceReturnedContent = $true
    inferenceMilliseconds = [int]$timer.ElapsedMilliseconds
    timestampUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
}
$fullOutput = [IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $fullOutput
if ($parent) { [IO.Directory]::CreateDirectory($parent) | Out-Null }
[IO.File]::WriteAllText($fullOutput, ($result | ConvertTo-Json -Depth 4) + "`n", [Text.UTF8Encoding]::new($false))
Write-Output ($result | ConvertTo-Json -Compress)
