$ErrorActionPreference = 'Stop'
$launcherRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$launcherPython = Join-Path $launcherRoot '.venv\Scripts\python.exe'
Push-Location -LiteralPath $launcherRoot
try {
    & $launcherPython (Join-Path $launcherRoot 'main.py') @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
