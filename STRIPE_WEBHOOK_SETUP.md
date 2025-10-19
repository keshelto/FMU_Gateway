# Stripe Webhook Setup Instructions

## Step 1: Access Stripe Dashboard

1. Go to: https://dashboard.stripe.com/test/webhooks
2. Click **"Add endpoint"**

## Step 2: Configure Endpoint

**Endpoint URL:**
```
https://fmu-gateway-long-pine-7571.fly.dev/webhooks/stripe
```

**Description:**
```
FMU Gateway payment notifications
```

**Events to send:**
Select these events:
- ✅ `checkout.session.completed`
- ✅ `checkout.session.expired`

## Step 3: Get Signing Secret

After creating the endpoint, Stripe will show you the signing secret.

It looks like: `whsec_...`

## Step 4: Update Fly.io Secret

Run this command with your actual signing secret:

```bash
fly secrets set STRIPE_WEBHOOK_SECRET=whsec_YOUR_ACTUAL_SECRET_HERE -a fmu-gateway-long-pine-7571
```

## Step 5: Test the Webhook

1. In Stripe dashboard, go to your webhook endpoint
2. Click **"Send test webhook"**
3. Select `checkout.session.completed`
4. Click **"Send test webhook"**
5. You should see a 200 OK response

## Verification

Check your app logs to confirm webhook receipt:

```bash
fly logs -a fmu-gateway-long-pine-7571
```

You should see entries like:
```
INFO: POST /webhooks/stripe
```

---

## Complete Payment Flow Test

Once webhook is configured:

### 1. Request a Simulation (gets 402)
```bash
curl -X POST "https://fmu-gateway-long-pine-7571.fly.dev/simulate" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01}'
```

### 2. Complete Checkout
- Copy the `checkout_url` from the response
- Open it in a browser
- Use test card: **4242 4242 4242 4242**
- Any future expiry date
- Any CVC

### 3. Get Payment Token
```bash
curl "https://fmu-gateway-long-pine-7571.fly.dev/payments/checkout/SESSION_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Response will include: `{"payment_token": "..."}`

### 4. Run Paid Simulation
```bash
curl -X POST "https://fmu-gateway-long-pine-7571.fly.dev/simulate" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01,"payment_token":"TOKEN_FROM_STEP_3"}'
```

Should return HTTP 200 with simulation results!

---

## Switching to Live Mode

When ready for real payments:

### 1. Get Live Stripe Keys
- Dashboard → Developers → API Keys
- Copy **Live Secret Key** (starts with `sk_live_`)

### 2. Update Fly Secrets
```bash
fly secrets set \
  STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_KEY \
  -a fmu-gateway-long-pine-7571
```

### 3. Create Live Webhook
- Go to: https://dashboard.stripe.com/webhooks (remove `/test`)
- Add same endpoint URL
- Copy new live signing secret
- Update: `fly secrets set STRIPE_WEBHOOK_SECRET=whsec_LIVE_SECRET`

### 4. Test with Real Card
- Use your own card for first transaction
- Verify payment appears in Stripe dashboard
- Check simulation completes successfully

---

**Current Status:**
- ✅ Gateway accessible externally
- ✅ HTTP 402 payment flow working
- ✅ Stripe test sessions creating successfully
- 🔄 Webhook configuration pending
- 🔄 End-to-end test pending

**Next:** Configure webhook, test complete flow, then go live!

