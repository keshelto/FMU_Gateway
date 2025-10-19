# Test Crypto Payment Flow
# Run this after setting up Coinbase Commerce

$API_KEY = "b4def8bc-c217-41cc-a3f9-11fb9bfdf655"
$BASE_URL = "https://fmu-gateway-long-pine-7571.fly.dev"

Write-Host "`n=== Testing Crypto Payment Flow ===" -ForegroundColor Cyan

# Step 1: Create a crypto payment
Write-Host "`nStep 1: Creating crypto payment..." -ForegroundColor Yellow
$createResponse = curl.exe -X POST "$BASE_URL/pay/crypto" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"fmu_id":"msl:BouncingBall"}' `
  -s

Write-Host "Response:" -ForegroundColor Green
$createResponse | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Extract the checkout URL and code
$payment = $createResponse | ConvertFrom-Json
$checkoutUrl = $payment.checkout_url
$chargeCode = $payment.code

Write-Host "`n=== Payment Created ===" -ForegroundColor Cyan
Write-Host "Checkout URL: $checkoutUrl" -ForegroundColor Green
Write-Host "Charge Code: $chargeCode" -ForegroundColor Green

Write-Host "`nStep 2: Open this URL in your browser to pay with crypto:" -ForegroundColor Yellow
Write-Host $checkoutUrl -ForegroundColor White

Write-Host "`nSupported cryptocurrencies:" -ForegroundColor Cyan
Write-Host "  - USDC (recommended - fast & stable)" -ForegroundColor Green
Write-Host "  - USDT" -ForegroundColor Green
Write-Host "  - ETH" -ForegroundColor Green
Write-Host "  - BTC" -ForegroundColor Green
Write-Host "  - DAI" -ForegroundColor Green

Write-Host "`nAfter paying, wait 30-60 seconds for confirmation, then run:" -ForegroundColor Yellow
Write-Host "curl.exe -X GET `"$BASE_URL/payments/crypto/$chargeCode`" -H `"Authorization: Bearer $API_KEY`"" -ForegroundColor White

Write-Host "`nPress Enter to check payment status (or wait until you've paid)..." -ForegroundColor Yellow
Read-Host

# Step 3: Check payment status
Write-Host "`nStep 3: Checking payment status..." -ForegroundColor Yellow
$statusResponse = curl.exe -X GET "$BASE_URL/payments/crypto/$chargeCode" `
  -H "Authorization: Bearer $API_KEY" `
  -s `
  -w "`nHTTP Status: %{http_code}"

Write-Host "Response:" -ForegroundColor Green
Write-Host $statusResponse

# If payment is complete, extract token and run simulation
if ($statusResponse -match '"payment_token"') {
    $tokenData = ($statusResponse -split "`nHTTP")[0] | ConvertFrom-Json
    $paymentToken = $tokenData.payment_token
    
    Write-Host "`n=== Payment Confirmed! ===" -ForegroundColor Green
    Write-Host "Payment Token: $paymentToken" -ForegroundColor White
    
    # Create simulation request with token
    $simRequest = @{
        fmu_id = "msl:BouncingBall"
        stop_time = 3.0
        step = 0.01
        payment_token = $paymentToken
    } | ConvertTo-Json
    
    $simRequest | Out-File -FilePath "crypto_simulation_request.json" -Encoding UTF8
    
    Write-Host "`nStep 4: Running paid simulation..." -ForegroundColor Yellow
    $simResponse = curl.exe -X POST "$BASE_URL/simulate" `
      -H "Authorization: Bearer $API_KEY" `
      -H "Content-Type: application/json" `
      --data-binary "@crypto_simulation_request.json" `
      -s `
      -w "`nHTTP Status: %{http_code}"
    
    Write-Host "Simulation Result:" -ForegroundColor Green
    Write-Host $simResponse
    
    Write-Host "`n=== SUCCESS! Crypto payment flow working! ===" -ForegroundColor Green
} else {
    Write-Host "`nPayment not yet confirmed. Please:" -ForegroundColor Yellow
    Write-Host "1. Complete the payment at: $checkoutUrl" -ForegroundColor White
    Write-Host "2. Wait 30-60 seconds for blockchain confirmation" -ForegroundColor White
    Write-Host "3. Run this command to check again:" -ForegroundColor White
    Write-Host "   curl.exe -X GET `"$BASE_URL/payments/crypto/$chargeCode`" -H `"Authorization: Bearer $API_KEY`"" -ForegroundColor Cyan
}

