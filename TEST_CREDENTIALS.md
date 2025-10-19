# 🔑 Test Credentials & Quick Commands

## Your Test API Key

**API Key:** `610a95d6-3397-43f8-913d-75501a199a79`

**Created:** October 17, 2025

⚠️ **Note:** This is a test key for the current deployment. It will persist unless the database is reset.

---

## Quick Test Commands

### 1. Health Check
```bash
curl https://fmu-gateway-long-pine-7571.fly.dev/health
```

**Expected:** `{"status":"healthy","version":"1.0.0"}`

---

### 2. Request Simulation (Get Payment Quote)
```bash
curl -X POST "https://fmu-gateway-long-pine-7571.fly.dev/simulate" \
  -H "Authorization: Bearer 610a95d6-3397-43f8-913d-75501a199a79" \
  -H "Content-Type: application/json" \
  -d '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01}'
```

**Expected:** HTTP 402 with `checkout_url` and `session_id`

---

### 3. List Library Models
```bash
curl "https://fmu-gateway-long-pine-7571.fly.dev/library" \
  -H "Authorization: Bearer 610a95d6-3397-43f8-913d-75501a199a79"
```

---

### 4. Check Payment Token Status
```bash
curl "https://fmu-gateway-long-pine-7571.fly.dev/payments/checkout/YOUR_SESSION_ID" \
  -H "Authorization: Bearer 610a95d6-3397-43f8-913d-75501a199a79"
```

**Replace** `YOUR_SESSION_ID` with the session ID from step 2.

---

## Stripe Test Cards

### Successful Payment
**Card Number:** `4242 4242 4242 4242`  
**Expiry:** Any future date (e.g., 12/25)  
**CVC:** Any 3 digits (e.g., 123)  
**ZIP:** Any (e.g., 12345)

### Declined Payment
**Card Number:** `4000 0000 0000 0002`

### Requires Authentication (3D Secure)
**Card Number:** `4000 0027 6000 3184`

More test cards: https://stripe.com/docs/testing

---

## PowerShell Test (Windows)

Since you're on Windows, here's a PowerShell-friendly test:

```powershell
# Save this as test_payment_flow.ps1

$apiKey = "610a95d6-3397-43f8-913d-75501a199a79"
$baseUrl = "https://fmu-gateway-long-pine-7571.fly.dev"

# 1. Request simulation (get 402)
Write-Host "1. Requesting simulation..." -ForegroundColor Cyan
$response = Invoke-RestMethod -Method Post `
  -Uri "$baseUrl/simulate" `
  -Headers @{"Authorization"="Bearer $apiKey"} `
  -ContentType "application/json" `
  -Body '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01}' `
  -StatusCodeVariable statusCode

Write-Host "   Status: $statusCode" -ForegroundColor Yellow
Write-Host "   Amount: $($response.amount) $($response.currency)" -ForegroundColor Green
Write-Host "   Checkout URL: $($response.checkout_url)" -ForegroundColor Green
Write-Host "   Session ID: $($response.session_id)" -ForegroundColor Green

# 2. Show next steps
Write-Host "`n2. Next Steps:" -ForegroundColor Cyan
Write-Host "   a) Open checkout URL in browser" -ForegroundColor White
Write-Host "   b) Pay with: 4242 4242 4242 4242" -ForegroundColor White
Write-Host "   c) Get token from: $baseUrl/payments/checkout/$($response.session_id)" -ForegroundColor White
Write-Host "   d) Run simulation with payment_token" -ForegroundColor White
```

---

## Monitoring Commands

### Watch Logs Live
```bash
fly logs -a fmu-gateway-long-pine-7571
```

### Check App Status
```bash
fly status -a fmu-gateway-long-pine-7571
```

### List Secrets
```bash
fly secrets list -a fmu-gateway-long-pine-7571
```

### SSH Into Machine
```bash
fly ssh console -a fmu-gateway-long-pine-7571
```

---

## API Documentation

**Interactive Docs:** https://fmu-gateway-long-pine-7571.fly.dev/docs

**OpenAPI Spec:** https://fmu-gateway-long-pine-7571.fly.dev/openapi.json

---

## Current Configuration

| Setting | Value |
|---------|-------|
| Gateway URL | https://fmu-gateway-long-pine-7571.fly.dev |
| API Key | `610a95d6-3397-43f8-913d-75501a199a79` |
| Price | $1.00 USD |
| Currency | USD |
| Token TTL | 30 minutes |
| Session TTL | 60 minutes |
| Stripe Mode | Test |

---

## ✅ What's Working

- [x] External HTTPS access
- [x] API key generation
- [x] HTTP 402 payment flow
- [x] Stripe Checkout session creation
- [x] Health checks passing
- [x] Library endpoint accessible

## 🔄 What's Next

- [ ] Configure Stripe webhook (see STRIPE_WEBHOOK_SETUP.md)
- [ ] Complete test transaction
- [ ] Switch to live mode
- [ ] Launch!

---

**Created:** October 17, 2025  
**Valid Until:** Database reset or redeployment

