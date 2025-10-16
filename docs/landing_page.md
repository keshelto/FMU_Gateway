# FMU Gateway — Run Any FMU Online for £1

A lightweight launch page for sharing publicly.

---

## Why FMU Gateway?
- Upload and execute FMI 2.0/3.0 FMUs from anywhere
- Deterministic runs powered by FMPy
- Stripe-backed pay-per-simulation checkout (no accounts required)
- First run costs just £1 (configurable)

## How It Works
1. Request a run via `/simulate` and receive a Stripe Checkout link.
2. Pay securely with card, Apple Pay, or Google Pay.
3. Retrieve your simulation token from `/payments/checkout/{session_id}`.
4. Re-run `/simulate` with the token to get results instantly.

## Useful Links
- **API Docs:** https://fmu-gateway-long-pine-7571.fly.dev/docs
- **GitHub Repo:** https://github.com/fmu-gateway/FMU_Gateway
- **Get Help:** support@fmu-gateway.dev

## Pricing
- £1 per on-demand simulation (default)
- Discounted credit packs coming soon
- Enterprise pilots available on request

## Ready to Launch?
Call the `/pay` endpoint or hit the checkout link returned by `/simulate` to get started. Your first paid run can be live in minutes.
