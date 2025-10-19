# Coinbase Commerce Setup Guide

## 🎯 Overview

This guide will help you set up Coinbase Commerce to accept crypto payments (USDC, USDT, ETH, BTC) alongside Stripe.

## 📋 Prerequisites

- A Coinbase Commerce account (free)
- Your FMU Gateway already deployed on Fly.io

---

## Step 1: Create Coinbase Commerce Account

1. **Go to Coinbase Commerce:**
   - Visit: https://commerce.coinbase.com/
   - Click "Get Started"

2. **Sign Up:**
   - Use your Coinbase wallet email or create a new account
   - Verify your email
   - Complete onboarding

3. **Get Your API Key:**
   - Go to Settings → API Keys
   - Click "Create an API Key"
   - Copy the API key (keep it secret!)
   - Name it "FMU Gateway"

---

## Step 2: Configure Webhook (Important!)

1. **Get Your Webhook URL:**
   ```
   https://fmu-gateway-long-pine-7571.fly.dev/webhooks/coinbase
   ```

2. **Add Webhook in Coinbase:**
   - Go to Settings → Webhook subscriptions
   - Click "Add an endpoint"
   - Paste your webhook URL
   - Select events to listen for:
     - ✅ charge:confirmed (required)
     - ✅ charge:failed (recommended)
     - ✅ charge:expired (recommended)
   - Click "Add endpoint"
   - Copy the "Shared secret" (you'll need this!)

---

## Step 3: Add Secrets to Fly.io

Open PowerShell in your FMU_Gateway directory and run:

```powershell
# Enable Coinbase Commerce
fly secrets set COINBASE_ENABLED=true -a fmu-gateway-long-pine-7571

# Add your API key (replace with your actual key)
fly secrets set COINBASE_API_KEY="your-api-key-here" -a fmu-gateway-long-pine-7571

# Add webhook secret (replace with your actual secret)
fly secrets set COINBASE_WEBHOOK_SECRET="your-webhook-secret-here" -a fmu-gateway-long-pine-7571
```

**Example:**
```powershell
fly secrets set COINBASE_API_KEY="a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6" -a fmu-gateway-long-pine-7571
fly secrets set COINBASE_WEBHOOK_SECRET="whsec_abc123xyz789" -a fmu-gateway-long-pine-7571
```

---

## Step 4: Deploy Updated Code

1. **Install the new dependency:**
   ```powershell
   # This is already in requirements.txt now
   ```

2. **Deploy to Fly.io:**
   ```powershell
   fly deploy -a fmu-gateway-long-pine-7571
   ```

3. **Wait for deployment:**
   The app will automatically restart with crypto payment support.

---

## Step 5: Test Crypto Payments

### Test the crypto payment endpoint:

```powershell
# Use your existing API key
$API_KEY = "b4def8bc-c217-41cc-a3f9-11fb9bfdf655"

# Create a crypto payment
curl.exe -X POST "https://fmu-gateway-long-pine-7571.fly.dev/pay/crypto" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"fmu_id":"msl:BouncingBall"}' `
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected response:**
```json
{
  "status": "payment_required",
  "amount": 1.0,
  "currency": "usd",
  "methods": ["stripe_checkout", "crypto"],
  "checkout_url": "https://commerce.coinbase.com/charges/XXXXXX",
  "code": "XXXXXX",
  "payment_method": "crypto",
  "next_step": "Complete crypto payment and call /payments/crypto/{code} to retrieve your simulation token"
}
```

### Complete the payment:

1. Open the `checkout_url` in your browser
2. Choose payment method (USDC recommended for speed):
   - **USDC on Base** (cheapest, fastest)
   - **USDC on Ethereum**
   - **ETH, BTC, etc.**
3. Connect your Coinbase wallet or scan QR code
4. Send the payment
5. Wait for confirmation (~30 seconds for USDC on Base)

### Retrieve your token:

```powershell
# Use the "code" from the payment response
curl.exe -X GET "https://fmu-gateway-long-pine-7571.fly.dev/payments/crypto/XXXXXX" `
  -H "Authorization: Bearer $API_KEY" `
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected response:**
```json
{
  "session_id": "XXXXXX",
  "payment_token": "long-token-string",
  "expires_at": "2025-10-19T12:00:00Z"
}
```

### Run your simulation:

```powershell
# Update paid_simulation_request.json with the new token
# Then run:
curl.exe -X POST "https://fmu-gateway-long-pine-7571.fly.dev/simulate" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  --data-binary "@paid_simulation_request.json" `
  -w "\nHTTP Status: %{http_code}\n"
```

---

## 🎮 Usage: Stripe vs Crypto

### Option 1: Let users choose via /pay endpoints

**For Stripe (card payments):**
```bash
POST /pay
```

**For Crypto:**
```bash
POST /pay/crypto
```

### Option 2: Specify payment_method in /simulate

**Stripe (default):**
```json
{
  "fmu_id": "msl:BouncingBall",
  "stop_time": 1.0,
  "step": 0.01,
  "payment_method": "stripe"
}
```

**Crypto:**
```json
{
  "fmu_id": "msl:BouncingBall",
  "stop_time": 1.0,
  "step": 0.01,
  "payment_method": "crypto"
}
```

---

## 💰 Supported Cryptocurrencies

Coinbase Commerce automatically accepts:

- **USDC** (USD Coin) - ⚡ Recommended (fast, stable)
- **USDT** (Tether) - Stable
- **ETH** (Ethereum) - Volatile but popular
- **BTC** (Bitcoin) - Volatile but popular
- **DAI** - Decentralized stablecoin
- **LTC** (Litecoin) - Fast
- **BCH** (Bitcoin Cash) - Fast

Users choose their preferred crypto at checkout.

---

## 📊 Fees Comparison

| Method | Fees | Settlement | You Receive |
|--------|------|------------|-------------|
| Stripe | 2.9% + $0.30 | 2-7 days | $0.67 |
| Coinbase Commerce | ~1% | 1 day | $0.99 |
| USDC on Base | ~1% + ~$0.01 gas | Instant | $0.98 |

For $1 transactions, crypto is significantly better!

---

## 🔒 Security Notes

1. **Never share your API keys publicly**
2. **Always use webhook secrets** for production
3. **Test with small amounts first**
4. **Monitor for unusual activity** in Coinbase dashboard

---

## 🐛 Troubleshooting

### Webhook not working?

**Check:**
1. Is the webhook URL correct?
2. Did you add the webhook secret to Fly.io?
3. Is `COINBASE_ENABLED=true` set?

**Test manually:**
```powershell
curl.exe -X POST "https://fmu-gateway-long-pine-7571.fly.dev/webhooks/coinbase" `
  -H "Content-Type: application/json" `
  -d '{"type":"charge:confirmed","data":{"code":"TEST123"}}' `
  -w "\nHTTP Status: %{http_code}\n"
```

### Payment confirmed but no token?

**Check Fly.io logs:**
```powershell
fly logs -a fmu-gateway-long-pine-7571
```

Look for webhook processing messages.

---

## 🎉 Success!

You now accept both credit cards (Stripe) AND crypto (USDC, USDT, etc.)!

**Marketing benefits:**
- ✅ Appeal to Web3 users
- ✅ Lower transaction fees
- ✅ Global reach (no banking required)
- ✅ Instant settlement
- ✅ Modern payment option

**Next steps:**
- Update your README.md to mention crypto payments
- Add "We accept crypto! 💎" to your marketing
- Consider USDC-only option for lowest fees

