# Run TurnB PPT Agent - API (8000) + React UI (3000)
$Root = $PSScriptRoot
Set-Location $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Missing .venv - create it first: python -m venv .venv" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".\frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location (Join-Path $Root "frontend")
    npm install
    Set-Location $Root
}

Write-Host ""
Write-Host "Starting TurnB PPT Agent (full stack)" -ForegroundColor Green
Write-Host "  API:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  UI:   http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Stop: close both terminal windows or Ctrl+C in each" -ForegroundColor DarkGray
Write-Host ""

$apiScript = Join-Path $Root "start-api.ps1"
Start-Process powershell.exe -WorkingDirectory $Root -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", $apiScript
)

Write-Host "Waiting for API..." -ForegroundColor Yellow
$apiReady = $false
for ($i = 1; $i -le 25; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2
        if ($health.status -eq "ok") {
            $apiReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $apiReady) {
    Write-Host ""
    Write-Host "API is not responding on port 8000." -ForegroundColor Red
    Write-Host "Check the other PowerShell window titled start-api, or run:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\python.exe -m uvicorn api_server:app --reload --port 8000" -ForegroundColor White
    Write-Host ""
}

Set-Location (Join-Path $Root "frontend")
npm run dev
