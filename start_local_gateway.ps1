# FMU Gateway - Local Development Startup Script (PowerShell)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "FMU GATEWAY - LOCAL SERVER" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to script directory
Set-Location -Path $PSScriptRoot

# Set environment variables for local development
$env:DATABASE_URL = "sqlite:///./local.db"
$env:STRIPE_ENABLED = "false"
$env:REDIS_URL = ""
$env:REQUIRE_AUTH = "false"

Write-Host "Starting local FMU Gateway..." -ForegroundColor Green
Write-Host "Server will be available at: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Health check at: http://localhost:8000/health" -ForegroundColor Yellow
Write-Host "API docs at: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "NOTE: Authentication is DISABLED for local development" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press CTRL+C to stop the server" -ForegroundColor Red
Write-Host ""

# Start uvicorn
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

