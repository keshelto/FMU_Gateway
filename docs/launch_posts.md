# Soft Launch Copy — FMU Gateway £1 Simulation API

## LinkedIn Post
🚀 **FMU Gateway is live!**

Upload any FMI 2.0/3.0 FMU and run it in the cloud for just **£1 per simulation**.

✅ Hosted `/simulate` API
✅ Stripe Checkout with instant tokens
✅ Deterministic runs powered by FMPy

How it works:
1. Hit `/simulate` → receive a Stripe Checkout link (HTTP 402).
2. Pay with card/Apple Pay/Google Pay.
3. Call `/payments/checkout/{session_id}` to grab your token.
4. Re-run `/simulate` with the token and collect the results.

Perfect for engineering teams that need to demo or validate FMUs without standing up infrastructure.

👉 API & docs: https://fmu-gateway-long-pine-7571.fly.dev/docs
👉 GitHub: https://github.com/fmu-gateway/FMU_Gateway

DM me if you want credit packs or an enterprise pilot. Let’s get your models running online today! 💡

---

## Reddit (r/controltheory / r/simulations)
Title: Run FMI FMUs in the cloud for £1 per simulation (Stripe checkout)

Body:
Hey folks — we just shipped **FMU Gateway**, a hosted API for executing FMI 2.0/3.0 FMUs. No servers to manage, just upload + run.

* Pay-per-simulation via Stripe Checkout (defaults to £1)
* HTTPS `/simulate` endpoint with deterministic outputs
* Token-based flow so you can charge clients before delivering results

Flow:
1. Call `/simulate` → it responds 402 with a `checkout_url`.
2. Pay (card / Apple Pay / Google Pay).
3. Fetch a short-lived token from `/payments/checkout/{session_id}`.
4. Call `/simulate` again with the token to run the model and grab KPIs/history.

Docs + Open Source: https://github.com/fmu-gateway/FMU_Gateway
API Playground: https://fmu-gateway-long-pine-7571.fly.dev/docs

Would love feedback from anyone running Modelica/Simulink FMUs or building engineering tools! 💬
