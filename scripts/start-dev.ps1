# ---------------------------------------------------------------------------
# AgriVision AI - start the backend and the frontend together.
#
#   .\scripts\start-dev.ps1
#
# Opens two windows: uvicorn with auto-reload on :8000 and Vite on :5173.
# ---------------------------------------------------------------------------
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root '.venv\Scripts\python.exe'

function Write-Step([string]$message) {
    Write-Host ''
    Write-Host "==> $message" -ForegroundColor Cyan
}

if (-not (Test-Path $venvPython)) {
    Write-Error "The virtual environment was not found at $venvPython. Create it first: python -m venv .venv"
}

if (-not $FrontendOnly) {
    Write-Step 'Starting the FastAPI backend on http://localhost:8000'
    $backend = Start-Process -FilePath $venvPython `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1', '--port', '8000' `
        -WorkingDirectory (Join-Path $root 'backend') `
        -PassThru
    Write-Host "    backend PID: $($backend.Id)"
    Write-Host '    docs:       http://localhost:8000/docs'
}

if (-not $BackendOnly) {
    Write-Step 'Starting the Vite dev server on http://localhost:5173'
    $frontend = Start-Process -FilePath 'npm.cmd' `
        -ArgumentList 'run', 'dev' `
        -WorkingDirectory (Join-Path $root 'frontend') `
        -PassThru
    Write-Host "    frontend PID: $($frontend.Id)"
}

Write-Host ''
Write-Host 'Press Ctrl+C to stop this launcher.' -ForegroundColor Yellow

if (-not $BackendOnly) {
    try { Wait-Process -Id $backend.Id } catch { }
}
if (-not $FrontendOnly) {
    try { Wait-Process -Id $frontend.Id } catch { }
}
