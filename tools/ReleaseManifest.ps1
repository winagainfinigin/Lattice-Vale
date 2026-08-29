#Requires -Version 5.1

function Assert-LatticeValePortableReleaseRelativePath {
    param([Parameter(Mandatory=$true)][string]$RelativePath)
    Set-StrictMode -Version 2.0
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [IO.Path]::IsPathRooted($RelativePath) -or
        $RelativePath.StartsWith('/') -or $RelativePath.EndsWith('/') -or $RelativePath.Contains(':') -or
        $RelativePath -match '[<>"|?*\x00-\x1F]') { throw "Unsafe/non-portable release path: $RelativePath" }
    $segments = @($RelativePath -split '/')
    if ($segments.Count -lt 1) { throw "Unsafe/non-portable release path: $RelativePath" }
    foreach ($segment in $segments) {
        if ([string]::IsNullOrEmpty($segment) -or $segment -eq '.' -or $segment -eq '..' -or
            $segment.StartsWith(' ') -or $segment.EndsWith(' ') -or $segment.EndsWith('.') -or
            $segment -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$') {
            throw "Unsafe/non-portable release path segment '$segment' in: $RelativePath"
        }
    }
}


function Assert-LatticeValePowerShellSourceEncoding {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$RelativePath
    )
    $extension = [IO.Path]::GetExtension($RelativePath).ToLowerInvariant()
    if ($extension -notin @('.ps1','.psm1','.psd1')) { return }
    $bytes = [IO.File]::ReadAllBytes($Path)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($bytes[$i] -gt 0x7F) {
            throw "PowerShell source must be ASCII-only for Windows PowerShell 5.1 compatibility: $RelativePath (non-ASCII byte at offset $i)."
        }
    }
}

function Test-LatticeValeSourceManifest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$ReleaseRoot,
        [Parameter(Mandatory=$true)][string]$ManifestPath,
        [switch]$WriteEachFile
    )
    Set-StrictMode -Version 2.0
    $rootFull = [IO.Path]::GetFullPath($ReleaseRoot)
    $filesystemRoot = [IO.Path]::GetPathRoot($rootFull)
    # Preserve filesystem roots such as C:\, UNC share roots, and / exactly. Trimming
    # C:\ to C: would change Join-Path into drive-relative semantics in PowerShell.
    if ($rootFull -eq $filesystemRoot) { $root = $rootFull }
    else { $root = $rootFull.TrimEnd('\','/') }
    $manifest = [IO.Path]::GetFullPath($ManifestPath)
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw "Source manifest not found: $manifest" }
    $checked=0; $listed=@{}
    foreach ($line in Get-Content -LiteralPath $manifest) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) { continue }
        if ($line -notmatch '^([0-9A-Fa-f]{64})  (.+)$') { throw "Malformed source-manifest line: $line" }
        $expected=$Matches[1].ToLowerInvariant(); $manifestRelative=$Matches[2].Replace('\','/')
        Assert-LatticeValePortableReleaseRelativePath $manifestRelative
        $manifestKey=$manifestRelative.ToLowerInvariant()
        if ($listed.ContainsKey($manifestKey)) { throw "Duplicate/case-colliding source-manifest entry: $manifestRelative" }
        $listed[$manifestKey]=$true
        # Build the native path from already-validated portable path segments. This
        # avoids separator/overload edge cases between Windows PowerShell 5.1, pwsh,
        # and Linux runners while preserving the release-root escape check below.
        $target=$root
        foreach ($segment in @($manifestRelative -split '/')) {
            $target=Join-Path -Path $target -ChildPath $segment
        }
        $target=[IO.Path]::GetFullPath($target)
        $separator = [string][IO.Path]::DirectorySeparatorChar
        $altSeparator = [string][IO.Path]::AltDirectorySeparatorChar
        $rootPrefix = if ($root.EndsWith($separator) -or $root.EndsWith($altSeparator)) { $root } else { $root+[IO.Path]::DirectorySeparatorChar }
        if (-not $target.StartsWith($rootPrefix,[StringComparison]::OrdinalIgnoreCase)) { throw "Source-manifest path escapes the release root: $manifestRelative" }
        $item=Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
        if ($null -eq $item -or $item.PSIsContainer) { throw "Release source file is missing: $manifestRelative" }
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Release source file must not be a reparse point: $manifestRelative" }
        Assert-LatticeValePowerShellSourceEncoding -Path $item.FullName -RelativePath $manifestRelative
        $actual=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw "Source verification failed for '$manifestRelative'. Expected $expected, got $actual." }
        if ($WriteEachFile) { Write-Host "OK  $manifestRelative" }
        $checked++
    }
    if ($checked -lt 1) { throw 'Source manifest contained no files to verify.' }
    $items=@(Get-ChildItem -LiteralPath $root -Force -Recurse | Where-Object { $_.FullName -notmatch '[\\/]\.git(?:[\\/]|$)' })
    foreach ($item in $items) {
        $relativeItem=$item.FullName.Substring($root.Length).TrimStart('\','/').Replace('\','/')
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Release tree must not contain reparse points: $relativeItem" }
        Assert-LatticeValePortableReleaseRelativePath $relativeItem
    }
    $actualFiles=@($items | Where-Object { -not $_.PSIsContainer -and [IO.Path]::GetFullPath($_.FullName) -ne $manifest })
    foreach ($file in $actualFiles) {
        $relativeActual=$file.FullName.Substring($root.Length).TrimStart('\','/').Replace('\','/')
        if (-not $listed.ContainsKey($relativeActual.ToLowerInvariant())) {
            $deleteListPath = Join-Path $root 'installer\PATCH-DELETE.txt'
            $knownObsolete = $false
            if (Test-Path -LiteralPath $deleteListPath -PathType Leaf) {
                $obsolete = @(Get-Content -LiteralPath $deleteListPath | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
                $knownObsolete = $obsolete -contains $relativeActual
            }
            if ($knownObsolete) {
                throw "Obsolete source file remains from an older overwrite patch: $relativeActual. Run .\tools\Finalize-LatticeVale-OverwritePatch.ps1 from the repository root, then rerun verification."
            }
            throw "Unexpected release file is not covered by SOURCE-SHA256SUMS.txt: $relativeActual"
        }
    }
    if ($actualFiles.Count -ne $listed.Count) { throw "Source-manifest coverage mismatch: manifest=$($listed.Count), extracted-files=$($actualFiles.Count)." }
    return $checked
}
