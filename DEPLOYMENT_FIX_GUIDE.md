# FMU Gateway Deployment Fix Guide

## Issue Identified: Missing TLS Certificate

**Problem:** External connections to `https://fmu-gateway-long-pine-7571.fly.dev` fail with TLS handshake error.

**Root Cause:** No TLS certificate configured for the hostname.

**Evidence:**
```bash
$ fly certs list -a fmu-gateway-long-pine-7571
Host Name                 Added                Status
(empty)
```

---

## Quick Fix

Fly.io apps should automatically get certificates for `*.fly.dev` subdomains. The missing certificate indicates a provisioning issue.

### Solution 1: Force Certificate Provisioning

```bash
# Add the certificate explicitly
fly certs add fmu-gateway-long-pine-7571.fly.dev -a fmu-gateway-long-pine-7571

# Check status (may take a few minutes)
fly certs show fmu-gateway-long-pine-7571.fly.dev -a fmu-gateway-long-pine-7571

# Expected output after provisioning:
# Host Name = fmu-gateway-long-pine-7571.fly.dev
# Status = Ready
# Certificate Authority = Let's Encrypt
```

### Solution 2: Restart App to Trigger Auto-Provisioning

```bash
# Restart all machines
fly apps restart -a fmu-gateway-long-pine-7571

# Wait 30 seconds, then check certificate
fly certs list -a fmu-gateway-long-pine-7571
```

### Solution 3: Redeploy

```bash
# Force a new deployment
fly deploy --remote-only -a fmu-gateway-long-pine-7571

# This should trigger automatic certificate provisioning
```

---

## Verification

Once certificate is provisioned, test:

```bash
# Test health endpoint
curl https://fmu-gateway-long-pine-7571.fly.dev/health
# Expected: {"status":"healthy","version":"1.0.0"}

# Test docs endpoint
curl https://fmu-gateway-long-pine-7571.fly.dev/docs
# Expected: HTML page with OpenAPI documentation

# Test key creation
curl -X POST https://fmu-gateway-long-pine-7571.fly.dev/keys
# Expected: {"key":"<uuid>"}
```

---

## Alternative: Custom Domain (Optional)

If you prefer a custom domain (e.g., `fmu-gateway.dev`):

```bash
# Add custom domain
fly certs add fmu-gateway.dev -a fmu-gateway-long-pine-7571

# Get DNS instructions
fly certs show fmu-gateway.dev -a fmu-gateway-long-pine-7571

# Add DNS records as instructed (usually CNAME to *.fly.dev)

# Update PUBLIC_BASE_URL
fly secrets set PUBLIC_BASE_URL=https://fmu-gateway.dev -a fmu-gateway-long-pine-7571
```

---

## Internal vs External Access

**Current Status:**
- ✅ Internal health checks: PASSING (all 200 OK)
- ✅ App is running and healthy
- ❌ External TLS connections: FAILING (certificate issue)

The app is working correctly; only the TLS certificate needs provisioning.

---

## Post-Fix Steps

After certificate is provisioned:

1. **Test Full Payment Flow:**
   ```bash
   # Create API key
   KEY=$(curl -s -X POST https://fmu-gateway-long-pine-7571.fly.dev/keys | jq -r .key)
   
   # Request simulation (should return 402)
   curl -H "Authorization: Bearer $KEY" \
        -H "Content-Type: application/json" \
        -d '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01}' \
        https://fmu-gateway-long-pine-7571.fly.dev/simulate
   ```

2. **Configure Stripe Webhook:**
   - Go to https://dashboard.stripe.com/webhooks
   - Add endpoint: `https://fmu-gateway-long-pine-7571.fly.dev/webhooks/stripe`
   - Select events: `checkout.session.completed`, `checkout.session.expired`
   - Copy signing secret
   - Update: `fly secrets set STRIPE_WEBHOOK_SECRET=whsec_... -a fmu-gateway-long-pine-7571`

3. **Complete Test Transaction:**
   - Use Stripe test mode
   - Complete checkout flow
   - Verify webhook delivery
   - Confirm simulation executes with payment token

4. **Switch to Live Mode:**
   - Replace test keys with live keys in Fly secrets
   - Update webhook endpoint in Stripe dashboard
   - Monitor first live transaction

---

## Expected Timeline

- Certificate provisioning: 1-5 minutes
- DNS propagation (if custom domain): 5-60 minutes
- Test transaction: 5 minutes
- Launch readiness: 10-15 minutes after certificate

---

## Support Commands

```bash
# Check machine status
fly status -a fmu-gateway-long-pine-7571

# View live logs
fly logs -a fmu-gateway-long-pine-7571

# Check secrets
fly secrets list -a fmu-gateway-long-pine-7571

# SSH into machine for debugging
fly ssh console -a fmu-gateway-long-pine-7571

# Check certificate status
fly certs list -a fmu-gateway-long-pine-7571
```

---

**Last Updated:** October 17, 2025

