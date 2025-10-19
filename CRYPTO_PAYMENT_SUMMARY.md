# 💎 Crypto Payment Integration Summary

## ✅ What We Just Added

You can now accept **stablecoin and cryptocurrency payments** alongside Stripe!

### Supported Cryptocurrencies
- **USDC** (USD Coin) - ⚡ Recommended (fast, stable, low fees)
- **USDT** (Tether) - Stable
- **ETH** (Ethereum)
- **BTC** (Bitcoin)
- **DAI** - Decentralized stablecoin
- **LTC** (Litecoin)
- **BCH** (Bitcoin Cash)

---

## 🏗️ Implementation Details

### New Endpoints

1. **`POST /pay/crypto`**
   - Creates a Coinbase Commerce charge
   - Returns checkout URL with crypto payment options
   - Similar to `/pay` but for crypto

2. **`GET /payments/crypto/{charge_code}`**
   - Retrieves payment token after crypto payment confirmation
   - Similar to `/payments/checkout/{session_id}` but for crypto

3. **`POST /webhooks/coinbase`**
   - Receives payment confirmations from Coinbase Commerce
   - Automatically issues tokens when payments are confirmed

### Enhanced Endpoints

- **`POST /simulate`** - Now accepts `payment_method` parameter:
  ```json
  {
    "fmu_id": "msl:BouncingBall",
    "stop_time": 1.0,
    "step": 0.01,
    "payment_method": "crypto"  // or "stripe"
  }
  ```
  
  When no payment token is provided and `payment_method: "crypto"`, the 402 response will include crypto payment options.

---

## 🔧 Configuration

### Environment Variables Added

```bash
COINBASE_ENABLED=true|false          # Enable/disable crypto payments
COINBASE_API_KEY=<your-api-key>      # From Coinbase Commerce dashboard
COINBASE_WEBHOOK_SECRET=<secret>     # For webhook signature verification
```

### Dependencies Added

```txt
coinbase-commerce==1.0.1
```

---

## 📊 HTTP 402 Response Format

### With Crypto Enabled

```json
{
  "status": "payment_required",
  "amount": 1.0,
  "currency": "usd",
  "methods": ["stripe_checkout", "crypto"],
  "checkout_url": "https://commerce.coinbase.com/charges/ABC123XYZ",
  "session_id": "ABC123XYZ",
  "code": "ABC123XYZ",
  "payment_method": "crypto",
  "hosted_url": "https://commerce.coinbase.com/charges/ABC123XYZ",
  "next_step": "Complete crypto payment and call /payments/crypto/{code} to retrieve your simulation token"
}
```

---

## 💰 Cost Benefits

| Payment Method | Fees | Settlement | You Get (per $1) |
|----------------|------|------------|------------------|
| **Stripe (Card)** | 2.9% + $0.30 | 2-7 days | $0.67 |
| **Coinbase Commerce** | ~1% | 1 day | $0.99 |
| **USDC on Base** | ~1% + ~$0.01 gas | Instant | $0.98 |

**For $1 transactions, crypto saves you ~$0.30 per transaction!**

---

## 🚀 User Experience

### Option 1: Direct Endpoint Selection

**For card payments:**
```bash
curl -X POST /pay \
  -H "Authorization: Bearer <api_key>" \
  -d '{"fmu_id":"msl:BouncingBall"}'
```

**For crypto payments:**
```bash
curl -X POST /pay/crypto \
  -H "Authorization: Bearer <api_key>" \
  -d '{"fmu_id":"msl:BouncingBall"}'
```

### Option 2: Payment Method in Simulate Request

**Automatic crypto checkout (no explicit /pay call):**
```bash
curl -X POST /simulate \
  -H "Authorization: Bearer <api_key>" \
  -d '{
    "fmu_id": "msl:BouncingBall",
    "stop_time": 1.0,
    "step": 0.01,
    "payment_method": "crypto"
  }'
```

**Returns 402 with crypto payment options:**
```json
{
  "status": "payment_required",
  "checkout_url": "https://commerce.coinbase.com/charges/...",
  "code": "ABC12345"
}
```

**User completes payment, then retrieves token:**
```bash
curl -X GET /payments/crypto/ABC12345 \
  -H "Authorization: Bearer <api_key>"
```

**Then runs simulation with token:**
```bash
curl -X POST /simulate \
  -H "Authorization: Bearer <api_key>" \
  -d '{
    "fmu_id": "msl:BouncingBall",
    "stop_time": 1.0,
    "step": 0.01,
    "payment_token": "long-token-string"
  }'
```

---

## 🔄 Payment Flow Comparison

### Stripe Flow
1. `POST /simulate` (no token) → 402 with Stripe checkout URL
2. User completes Stripe checkout
3. Stripe webhook → Token issued
4. `GET /payments/checkout/{session_id}` → Get token
5. `POST /simulate` (with token) → Simulation runs

### Crypto Flow
1. `POST /simulate` (no token, `payment_method: "crypto"`) → 402 with Coinbase charge URL
2. User sends crypto payment
3. Coinbase webhook → Token issued
4. `GET /payments/crypto/{charge_code}` → Get token
5. `POST /simulate` (with token) → Simulation runs

**Same pattern, different payment gateway!**

---

## 🎯 Next Steps to Enable

1. **Sign up for Coinbase Commerce** (free)
   - https://commerce.coinbase.com/

2. **Get your API key**
   - Dashboard → Settings → API Keys

3. **Configure webhook**
   - Webhook URL: `https://your-app.fly.dev/webhooks/coinbase`
   - Events: `charge:confirmed`, `charge:failed`, `charge:expired`

4. **Add secrets to Fly.io**
   ```bash
   fly secrets set COINBASE_ENABLED=true
   fly secrets set COINBASE_API_KEY="your-api-key"
   fly secrets set COINBASE_WEBHOOK_SECRET="your-webhook-secret"
   ```

5. **Deploy**
   ```bash
   fly deploy
   ```

6. **Test** using `test_crypto_payment.ps1`

---

## 📚 Documentation Files

- **`COINBASE_SETUP.md`** - Detailed setup guide
- **`test_crypto_payment.ps1`** - Test script for crypto payments
- **`CRYPTO_PAYMENT_SUMMARY.md`** (this file) - Implementation summary

---

## 🎉 Benefits

### For You (Business Owner)
- ✅ Lower transaction fees (~1% vs ~3%)
- ✅ Faster settlement (1 day vs 7 days)
- ✅ Global reach (no banking required)
- ✅ Appeal to Web3-native users
- ✅ Instant on-chain settlement

### For Your Users
- ✅ Pay with crypto wallet (Coinbase, MetaMask, etc.)
- ✅ No credit card required
- ✅ Privacy-friendly (no bank statements)
- ✅ Fast confirmation (~30 seconds for USDC)
- ✅ Choose their preferred coin

---

## 🔒 Security

- **Webhook signature verification** ensures only Coinbase can trigger token issuance
- **Same token mechanism** as Stripe (one-time use, expires after 30 minutes)
- **API key authentication** required for all endpoints
- **No crypto custody** - payments go directly to your Coinbase Commerce account

---

## 💡 Marketing Ideas

Update your landing page:

```markdown
## 💳 Pay Your Way

Choose your preferred payment method:

- **Credit Card** - Stripe checkout (Visa, MasterCard, Amex, Apple Pay, Google Pay)
- **Crypto** - USDC, USDT, ETH, BTC, and more via Coinbase Commerce

**Crypto users:** Save on fees and get instant settlement! 💎
```

---

**The HTTP 402 protocol works perfectly with both payment methods!** 🎉

