# Manual Payment Flow Test

## ⚠️ Important: Database Issue Discovered

Your gateway has **2 machines but no persistent volume**, so each machine has its own SQLite database. This means API keys created on one machine won't work on the other.

**Quick Fix Options:**
1. **Manual Test (do this now)** - Use curl commands below
2. **Persistent Volume (do before launch)** - See instructions at bottom

---

## Quick Test (5 Minutes)

### Step 1: Create Checkout URL

```bash
curl -X POST "https://fmu-gateway-long-pine-7571.fly.dev/keys"
```

**Save the API key**, then:

```bash
curl -X POST "https://fmu-gateway-long-pine-7571.fly.dev/simulate" \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01}'
```

**Expected:** HTTP 402 response with `checkout_url` and `session_id`

### Step 2: Complete Stripe Checkout

1. Copy the `checkout_url` from the response
2. Open it in your browser
3. Use test card: **4242 4242 4242 4242**
4. Expiry: **12/25** (any future date)
5. CVC: **123** (any 3 digits)
6. Complete payment

### Step 3: Get Payment Token

```bash
curl "https://fmu-gateway-long-pine-7571.fly.dev/payments/checkout/SESSION_ID_HERE" \
  -H "Authorization: Bearer YOUR_API_KEY_HERE"
```

**Replace** `SESSION_ID_HERE` with the session ID from Step 1.

**If you get 404:** Wait 5-10 seconds for the webhook to process, then retry.

**Expected:** `{"payment_token":"...","session_id":"...","expires_at":"..."}`

### Step 4: Run Paid Simulation

```bash
curl -X POST "https://fmu-gateway-long-pine-7571.fly.dev/simulate" \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01,"payment_token":"TOKEN_FROM_STEP_3"}'
```

**Expected:** HTTP 200 with simulation results!

---

## ✅ Success Indicators

If Step 4 returns something like this, **YOU'RE READY TO LAUNCH!**

```json
{
  "run_id": "...",
  "status": "ok",
  "key_results": {
    "final_time": 1.0,
    "final_h": ...,
    "final_v": ...
  },
  "summary_url": "/simulations/..."
}
```

---

## 🔧 Fix Database Issue Before Launch

### Option 1: Create Persistent Volume (Recommended)

```bash
# 1. Create volume
fly volumes create fmu_data --size 1 -a fmu-gateway-long-pine-7571

# 2. Update fly.toml - add after [env] section:
[[mounts]]
  source = "fmu_data"
  destination = "/data"

# 3. Redeploy
fly deploy --remote-only -a fmu-gateway-long-pine-7571
```

### Option 2: Scale to 1 Machine (Quick Fix)

```bash
fly scale count 1 -a fmu-gateway-long-pine-7571
```

This ensures all requests go to the same machine/database.

---

## 🐛 Troubleshooting

### "Invalid API key" Error

**Problem:** Request routed to different machine than where key was created.

**Solution:** Create a new key and immediately use it (pray it stays on same machine), OR fix the persistence issue above.

### Webhook Not Firing

**Check webhook in Stripe:**
1. Go to https://dashboard.stripe.com/test/webhooks
2. Find your webhook
3. Click to see delivery attempts
4. If failing, check the error message

**Check app logs:**
```bash
fly logs -a fmu-gateway-long-pine-7571 | grep webhook
```

### Token Not Found (404)

**Wait longer:** Webhooks can take 5-30 seconds

**Check logs:**
```bash
fly logs -a fmu-gateway-long-pine-7571 -n
```

Look for: `POST /webhooks/stripe`

---

## 🚀 After Successful Test

You're ready to:

1. ✅ Fix database persistence (volume or scale to 1)
2. ✅ Switch to Stripe live keys
3. ✅ Test with real card
4. ✅ Deploy landing page
5. ✅ Launch!

See `LAUNCH_CHECKLIST.md` for full details.

---

## Alternative: Test in Stripe Dashboard

Instead of manual steps, you can:

1. Go to https://dashboard.stripe.com/test/webhooks
2. Find your webhook endpoint
3. Click "Send test webhook"
4. Select `checkout.session.completed`
5. Customize the JSON to include your API key ID
6. Send it
7. Check app logs to verify it was processed

---

**Created:** October 17, 2025  
**Status:** Database issue discovered, workarounds provided  
**Next:** Fix persistence, then launch

