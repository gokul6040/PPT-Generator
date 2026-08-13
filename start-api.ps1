# Launched by run-dev.ps1 in a separate window
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Missing .venv. Run: python -m venv .venv" -ForegroundColor Red
    Write-Host "Then: pip install -r requirements.txt" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Starting API on http://localhost:8000" -ForegroundColor Cyan
try {
    & $python -m uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
} catch {
    Write-Host "API failed to start: $_" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
