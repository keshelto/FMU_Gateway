# Simple Payment Flow Test
$baseUrl = "https://fmu-gateway-long-pine-7571.fly.dev"

Write-Host "`n=== FMU Gateway Payment Flow Test ===" -ForegroundColor Cyan

# Step 1: Create API Key
Write-Host "`n[1/5] Creating API Key..." -ForegroundColor Yellow
$keyResp = Invoke-RestMethod -Method Post -Uri "$baseUrl/keys"
$apiKey = $keyResp.key
Write-Host "API Key: $apiKey" -ForegroundColor Green

# Step 2: Request Simulation
Write-Host "`n[2/5] Requesting Simulation..." -ForegroundColor Yellow
$simBody = '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01}'

try {
    $simResp = Invoke-RestMethod -Method Post -Uri "$baseUrl/simulate" `
        -Headers @{"Authorization"="Bearer $apiKey"} `
        -ContentType "application/json" `
        -Body $simBody
} catch {
    # 402 response expected
    if ($_.Exception.Response.StatusCode.value__ -eq 402) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $simResp = $reader.ReadToEnd() | ConvertFrom-Json
        $reader.Close()
        $stream.Close()
    } else {
        throw
    }
}

$sessionId = $simResp.session_id
$checkoutUrl = $simResp.checkout_url

Write-Host "Session ID: $sessionId" -ForegroundColor Green
Write-Host "Amount: `$$($simResp.amount) $($simResp.currency)" -ForegroundColor Green

# Step 3: Manual checkout
Write-Host "`n[3/5] Opening Stripe Checkout..." -ForegroundColor Yellow
Write-Host "Test Card: 4242 4242 4242 4242 | Exp: 12/25 | CVC: 123" -ForegroundColor Cyan
Start-Process $checkoutUrl
Write-Host "Press ENTER after completing checkout..." -ForegroundColor Yellow
$null = Read-Host

# Step 4: Retrieve Token
Write-Host "`n[4/5] Retrieving Payment Token..." -ForegroundColor Yellow
$tokenRetrieved = $false
for ($i=1; $i -le 10; $i++) {
    try {
        $tokenResp = Invoke-RestMethod -Method Get `
            -Uri "$baseUrl/payments/checkout/$sessionId" `
            -Headers @{"Authorization"="Bearer $apiKey"}
        $paymentToken = $tokenResp.payment_token
        Write-Host "Token Retrieved: $paymentToken" -ForegroundColor Green
        $tokenRetrieved = $true
        break
    } catch {
        Write-Host "Attempt $i - Waiting for webhook..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $tokenRetrieved) {
    Write-Host "Failed to retrieve token. Check Stripe webhook." -ForegroundColor Red
    exit 1
}

# Step 5: Execute Paid Simulation
Write-Host "`n[5/5] Executing Paid Simulation..." -ForegroundColor Yellow
$paidBody = @{
    fmu_id = "msl:BouncingBall"
    stop_time = 1.0
    step = 0.01
    payment_token = $paymentToken
} | ConvertTo-Json

$result = Invoke-RestMethod -Method Post -Uri "$baseUrl/simulate" `
    -Headers @{"Authorization"="Bearer $apiKey"} `
    -ContentType "application/json" `
    -Body $paidBody

Write-Host "Simulation Complete!" -ForegroundColor Green
Write-Host "Status: $($result.status)" -ForegroundColor White
Write-Host "Run ID: $($result.run_id)" -ForegroundColor White

Write-Host "`n=== TEST PASSED ===" -ForegroundColor Green
Write-Host "Your FMU Gateway is ready for launch!" -ForegroundColor Cyan

