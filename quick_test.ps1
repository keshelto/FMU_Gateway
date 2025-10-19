# Quick Payment Flow Test - Using existing API key
$baseUrl = "https://fmu-gateway-long-pine-7571.fly.dev"
$apiKey = "610a95d6-3397-43f8-913d-75501a199a79"  # From earlier

Write-Host "`n=== Testing Payment Flow ===" -ForegroundColor Cyan
Write-Host "Using API Key: $apiKey" -ForegroundColor Gray

# Request Simulation (get 402)
Write-Host "`n[1/4] Requesting Simulation..." -ForegroundColor Yellow
$simBody = '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01}'

try {
    $simResp = Invoke-RestMethod -Method Post -Uri "$baseUrl/simulate" `
        -Headers @{"Authorization"="Bearer $apiKey"} `
        -ContentType "application/json" `
        -Body $simBody
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 402) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $simResp = $reader.ReadToEnd() | ConvertFrom-Json
        $reader.Close()
        $stream.Close()
    } else {
        Write-Host "Error: $_" -ForegroundColor Red
        exit 1
    }
}

$sessionId = $simResp.session_id
Write-Host "Session: $sessionId" -ForegroundColor Green
Write-Host "Amount: `$$($simResp.amount)" -ForegroundColor Green

# Open Stripe Checkout
Write-Host "`n[2/4] Opening Checkout..." -ForegroundColor Yellow
Write-Host "Card: 4242 4242 4242 4242 | Exp: 12/25 | CVC: 123" -ForegroundColor Cyan
Start-Process $simResp.checkout_url
$null = Read-Host "Press ENTER after paying"

# Get Token
Write-Host "`n[3/4] Getting Token..." -ForegroundColor Yellow
for ($i=1; $i -le 15; $i++) {
    try {
        $tokenResp = Invoke-RestMethod -Method Get `
            -Uri "$baseUrl/payments/checkout/$sessionId" `
            -Headers @{"Authorization"="Bearer $apiKey"}
        $token = $tokenResp.payment_token
        Write-Host "Token: $token" -ForegroundColor Green
        break
    } catch {
        Write-Host "Waiting ($i/15)..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
}

if (-not $token) {
    Write-Host "Timeout waiting for webhook" -ForegroundColor Red
    Write-Host "Check: fly logs -a fmu-gateway-long-pine-7571" -ForegroundColor Yellow
    exit 1
}

# Execute Paid Simulation
Write-Host "`n[4/4] Running Simulation..." -ForegroundColor Yellow
$paidBody = "{`"fmu_id`":`"msl:BouncingBall`",`"stop_time`":1.0,`"step`":0.01,`"payment_token`":`"$token`"}"
$result = Invoke-RestMethod -Method Post -Uri "$baseUrl/simulate" `
    -Headers @{"Authorization"="Bearer $apiKey"} `
    -ContentType "application/json" `
    -Body $paidBody

Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
Write-Host "Status: $($result.status)" -ForegroundColor White
Write-Host "Run ID: $($result.run_id)" -ForegroundColor White
Write-Host "`nYour gateway is READY FOR LAUNCH!" -ForegroundColor Cyan

