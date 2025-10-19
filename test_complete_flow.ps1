# Complete Payment Flow Test
# This script tests the entire payment flow from request to execution

$baseUrl = "https://fmu-gateway-long-pine-7571.fly.dev"
$ErrorActionPreference = "Continue"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  FMU Gateway Payment Flow Test" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 1: Create API Key
Write-Host "Step 1: Creating API Key..." -ForegroundColor Yellow
try {
    $keyResponse = Invoke-RestMethod -Method Post -Uri "$baseUrl/keys"
    $apiKey = $keyResponse.key
    Write-Host "✓ API Key Created: $apiKey" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to create API key: $_" -ForegroundColor Red
    exit 1
}

# Step 2: Request Simulation (Get 402 with checkout URL)
Write-Host "`nStep 2: Requesting Simulation (expect 402)..." -ForegroundColor Yellow
try {
    $body = @{
        fmu_id = "msl:BouncingBall"
        stop_time = 1.0
        step = 0.01
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Method Post `
        -Uri "$baseUrl/simulate" `
        -Headers @{"Authorization"="Bearer $apiKey"} `
        -ContentType "application/json" `
        -Body $body `
        -StatusCodeVariable statusCode
    
    # If we got here without error, response should be 402
    Write-Host "✓ Payment Required (HTTP 402)" -ForegroundColor Green
    Write-Host "  Amount: `$$($response.amount) $($response.currency.ToUpper())" -ForegroundColor White
    Write-Host "  Session ID: $($response.session_id)" -ForegroundColor White
    
    $sessionId = $response.session_id
    $checkoutUrl = $response.checkout_url
    
} catch {
    # Check if it's a 402 response (PowerShell treats non-200 as errors)
    if ($_.Exception.Response.StatusCode.value__ -eq 402) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd() | ConvertFrom-Json
        
        Write-Host "✓ Payment Required (HTTP 402)" -ForegroundColor Green
        Write-Host "  Amount: `$$($responseBody.amount) $($responseBody.currency.ToUpper())" -ForegroundColor White
        Write-Host "  Session ID: $($responseBody.session_id)" -ForegroundColor White
        
        $sessionId = $responseBody.session_id
        $checkoutUrl = $responseBody.checkout_url
    } else {
        Write-Host "✗ Unexpected error: $_" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Show checkout instructions
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  MANUAL STEP REQUIRED" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nStep 3: Complete Stripe Checkout" -ForegroundColor Yellow
Write-Host "`nCheckout URL (opening in browser):" -ForegroundColor White
Write-Host $checkoutUrl -ForegroundColor Blue

# Open checkout in browser
Start-Process $checkoutUrl

Write-Host "`n📝 Use this test card:" -ForegroundColor Yellow
Write-Host "   Card: 4242 4242 4242 4242" -ForegroundColor White
Write-Host "   Expiry: 12/25 (any future date)" -ForegroundColor White
Write-Host "   CVC: 123 (any 3 digits)" -ForegroundColor White
Write-Host "   ZIP: 12345 (any)" -ForegroundColor White

Write-Host "`nPress ENTER after completing checkout..." -ForegroundColor Yellow
$null = Read-Host

# Step 4: Retrieve Payment Token
Write-Host "`nStep 4: Retrieving Payment Token..." -ForegroundColor Yellow
$maxAttempts = 10
$attempt = 0
$tokenRetrieved = $false

while ($attempt -lt $maxAttempts -and -not $tokenRetrieved) {
    $attempt++
    try {
        $tokenResponse = Invoke-RestMethod -Method Get `
            -Uri "$baseUrl/payments/checkout/$sessionId" `
            -Headers @{"Authorization"="Bearer $apiKey"}
        
        $paymentToken = $tokenResponse.payment_token
        Write-Host "✓ Payment Token Retrieved: $paymentToken" -ForegroundColor Green
        $tokenRetrieved = $true
        
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 404) {
            Write-Host "  Attempt $attempt`: Waiting for webhook... (retry in 2s)" -ForegroundColor Gray
            Start-Sleep -Seconds 2
        } else {
            Write-Host "✗ Error retrieving token: $_" -ForegroundColor Red
            Write-Host "  This might mean the webhook has not fired yet. Check Stripe dashboard." -ForegroundColor Yellow
            exit 1
        }
    }
}

if (-not $tokenRetrieved) {
    Write-Host "✗ Failed to retrieve payment token after $maxAttempts attempts" -ForegroundColor Red
    Write-Host "`n⚠️  Troubleshooting:" -ForegroundColor Yellow
    Write-Host "   1. Check Stripe dashboard for webhook delivery" -ForegroundColor White
    Write-Host "   2. Verify webhook secret is correct" -ForegroundColor White
    Write-Host "   3. Check: fly logs -a fmu-gateway-long-pine-7571" -ForegroundColor White
    exit 1
}

# Step 5: Execute Paid Simulation
Write-Host "`nStep 5: Executing Paid Simulation..." -ForegroundColor Yellow
try {
    $paidBody = @{
        fmu_id = "msl:BouncingBall"
        stop_time = 1.0
        step = 0.01
        payment_token = $paymentToken
    } | ConvertTo-Json

    $result = Invoke-RestMethod -Method Post `
        -Uri "$baseUrl/simulate" `
        -Headers @{"Authorization"="Bearer $apiKey"} `
        -ContentType "application/json" `
        -Body $paidBody
    
    Write-Host "✓ Simulation Complete!" -ForegroundColor Green
    Write-Host "  Status: $($result.status)" -ForegroundColor White
    Write-Host "  Run ID: $($result.run_id)" -ForegroundColor White
    Write-Host "  Results URL: $baseUrl$($result.summary_url)" -ForegroundColor White
    
    # Show some key results
    if ($result.key_results) {
        Write-Host "`n📊 Key Results:" -ForegroundColor Yellow
        $result.key_results.PSObject.Properties | ForEach-Object {
            Write-Host "   $($_.Name): $($_.Value)" -ForegroundColor White
        }
    }
    
} catch {
    Write-Host "✗ Simulation failed: $_" -ForegroundColor Red
    exit 1
}

# Success!
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  ✓ TEST COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Write-Host "`n🎉 Your FMU Gateway is fully operational and ready for launch!" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Switch to Stripe live keys" -ForegroundColor White
Write-Host "  2. Test with a real card" -ForegroundColor White
Write-Host "  3. Deploy landing page" -ForegroundColor White
Write-Host "  4. Post launch announcements" -ForegroundColor White
Write-Host "`nSee LAUNCH_CHECKLIST.md for details.`n" -ForegroundColor Gray

