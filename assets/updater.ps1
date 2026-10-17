param([Parameter(Mandatory=$true)][string]$Plan)
$ErrorActionPreference = 'Stop'
$stage = [IO.Path]::GetFullPath((Split-Path -Parent $Plan))
$result = Join-Path $stage 'result.json'
$backup = Join-Path $stage 'backup'
$changed = [Collections.Generic.List[string]]::new()
$existed = @{}
$installLock = $null
$targetRoot = $null
$protectedNames = @('builds','cores','libs','logs','cache','themes','theme_sources','.git','.venv','.idea','betathemes','themeworkbench','serpantinelauncher.json','serpantinethemehealth.json','catalog.json')

function SafePath([string]$Root, [string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative) -or $Relative.Contains('\') -or $Relative.Contains(':')) { throw 'Unsafe update path' }
    $parts = $Relative.Split('/')
    if ($protectedNames -contains $parts[0].ToLowerInvariant()) { throw 'Protected user data in update' }
    foreach ($part in $parts) {
        if ($part -in @('','.', '..') -or $part.EndsWith('.') -or $part.EndsWith(' ') -or $part -match '^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$') { throw 'Unsafe update path' }
    }
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $full = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Update path escapes root' }
    $cursor = $full
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Update path contains a reparse point' }
        if ($cursor.TrimEnd('\') -eq $Root.TrimEnd('\')) { break }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}

function Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

try {
    $config = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.schema -ne 1 -or $config.executable -ne 'SerpantineLauncher.exe') { throw 'Invalid updater plan' }
    $targetRoot = [IO.Path]::GetFullPath($config.target).TrimEnd('\')
    if ($targetRoot -eq [IO.Path]::GetPathRoot($targetRoot).TrimEnd('\') -or -not (Test-Path -LiteralPath $targetRoot -PathType Container)) { throw 'Invalid installation directory' }
    $launcher = SafePath $targetRoot $config.executable
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'Installed launcher is missing' }
    $payload = Join-Path $stage 'payload'
    $manifestPath = Join-Path $payload 'launcher-update.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.schema -ne 1 -or ([string]$manifest.version).TrimStart('v','V') -ne ([string]$config.version).TrimStart('v','V') -or $manifest.platform -ne 'windows-x64' -or $manifest.executable -ne $config.executable -or -not $manifest.files) { throw 'Invalid update manifest' }
    $newNames = @{}
    foreach ($entry in $manifest.files.PSObject.Properties) {
        if ($newNames.ContainsKey($entry.Name) -or $entry.Name -eq 'launcher-update.json') { throw 'Duplicate update file' }
        $newNames[$entry.Name] = $true
        $source = SafePath $payload $entry.Name
        $null = SafePath $targetRoot $entry.Name
        if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or (Get-Item -LiteralPath $source).Length -ne $entry.Value.size -or (Sha256 $source) -ne $entry.Value.sha256) { throw 'Update checksum mismatch' }
    }
    if (-not $newNames.ContainsKey($config.executable)) { throw 'Update has no launcher executable' }
    $parentProcess = Get-Process -Id $config.pid -ErrorAction SilentlyContinue
    if ($parentProcess) {
        if ([IO.Path]::GetFullPath($parentProcess.Path) -ne $launcher) { throw 'Unexpected parent process' }
        $null = $parentProcess.Handle
        if (-not $parentProcess.WaitForExit(600000)) { throw 'Launcher did not exit; update cancelled' }
    }
    if (Test-Path -LiteralPath ($Plan + '.cancel')) { throw 'Update cancelled by launcher' }
    $lockPath = Join-Path $targetRoot 'launcher-update.lock'
    $installLock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $oldNames = @{}
    $oldManifestPath = SafePath $targetRoot 'launcher-update.json'
    if (Test-Path -LiteralPath $oldManifestPath -PathType Leaf) {
        $oldManifest = Get-Content -LiteralPath $oldManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($oldManifest.schema -ne 1 -or $oldManifest.executable -ne $config.executable) { throw 'Invalid installed manifest' }
        foreach ($entry in $oldManifest.files.PSObject.Properties) {
            $null = SafePath $targetRoot $entry.Name
            $oldNames[$entry.Name] = $true
        }
    }
    $allNames = @($oldNames.Keys) + @($newNames.Keys) + @('launcher-update.json') | Sort-Object -Unique
    foreach ($name in $allNames) {
        $installed = SafePath $targetRoot $name
        if (Test-Path -LiteralPath $installed) {
            if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) { throw 'Update collides with an existing directory' }
            $saved = SafePath $backup $name
            $null = New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force
            Copy-Item -LiteralPath $installed -Destination $saved
            $existed[$name] = $true
        }
    }
    $installNames = @($newNames.Keys | Sort-Object | Where-Object { $_ -ne $config.executable }) + @($config.executable, 'launcher-update.json')
    foreach ($name in $installNames) {
        $installed = SafePath $targetRoot $name
        $source = SafePath $payload $name
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $installed) -Force
        $changed.Add($name)
        Copy-Item -LiteralPath $source -Destination $installed -Force
    }
    foreach ($name in $oldNames.Keys) {
        if (-not $newNames.ContainsKey($name)) {
            $installed = SafePath $targetRoot $name
            if (Test-Path -LiteralPath $installed -PathType Leaf) {
                $changed.Add($name)
                Remove-Item -LiteralPath $installed -Force
            }
        }
    }
    @{status='installed';version=$config.version;target=$targetRoot} | ConvertTo-Json | Set-Content -LiteralPath $result -Encoding UTF8
    $installLock.Dispose()
    $installLock = $null
    if ($config.restart -eq $true) { Start-Process -FilePath $launcher -WorkingDirectory $targetRoot -WindowStyle Normal }
} catch {
    $failure = $_.Exception.Message
    $rollbackErrors = @()
    foreach ($name in $changed) {
        try {
            $installed = SafePath $targetRoot $name
            if ($existed.ContainsKey($name)) {
                $saved = SafePath $backup $name
                if (-not (Test-Path -LiteralPath $installed -PathType Leaf) -or (Sha256 $installed) -ne (Sha256 $saved)) {
                    Copy-Item -LiteralPath $saved -Destination $installed -Force
                }
            } elseif (Test-Path -LiteralPath $installed -PathType Leaf) {
                Remove-Item -LiteralPath $installed -Force
            }
        } catch { $rollbackErrors += $_.Exception.Message }
    }
    @{status='failed';error=$failure;rollbackErrors=$rollbackErrors;target=$targetRoot} | ConvertTo-Json | Set-Content -LiteralPath $result -Encoding UTF8
    exit 1
} finally {
    if ($installLock) { $installLock.Dispose() }
}
