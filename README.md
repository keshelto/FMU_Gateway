# FMU Gateway

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![API Status](https://img.shields.io/badge/API-Live-brightgreen)](https://fmu-gateway-long-pine-7571.fly.dev/health)
[![Pricing](https://img.shields.io/badge/Pricing-$1%2Fsim-blue)](https://fmu-gateway-long-pine-7571.fly.dev/docs)
[![Accepts Crypto](https://img.shields.io/badge/Accepts-Crypto-orange?logo=bitcoin)](https://commerce.coinbase.com/)

Run any FMI 2.0/3.0 FMU instantly via REST API — **$1 per simulation**.

## What this is
A secure, deterministic service for uploading and simulating FMI 2.0/3.0 FMUs (ME & CS) using FMPy. Deployed on Fly.io in Docker. Priorities: small API surface, security (e.g., platform checks, no network during sim), and clear schemas.

---

## 🚀 Hosted Service (Recommended)

**Don't want to self-host? Use our managed API:**

- ✅ **$1.00 per simulation** — No subscription, pay per use
- ✅ **Instant access** — No setup, Docker, or infrastructure needed
- ✅ **Pre-validated FMU library** — Modelica Standard Library models ready to use
- ✅ **Secure & reliable** — Professional hosting with 99.9% uptime
- ✅ **Smart caching** — Upload once, simulate many times

### 💳 Pay Your Way

Choose your preferred payment method:

**Credit/Debit Cards** 💳
- Stripe checkout with all major cards, Apple Pay, Google Pay
- Instant confirmation

**Cryptocurrency** 💎 *(Lower fees!)*
- Pay with USDC, USDT, ETH, BTC, and more via Coinbase Commerce
- ⚡ ~30 second confirmations for stablecoins
- 🌍 No bank account required
- 🔒 Privacy-friendly payments
- Works with MetaMask, Coinbase Wallet, WalletConnect, and any Web3 wallet

### Try It Now

```bash
# 1. Get API key
curl -X POST https://fmu-gateway-long-pine-7571.fly.dev/keys

# 2. Run a simulation (choose payment method)

# Option A: Pay with credit card (default)
curl -X POST https://fmu-gateway-long-pine-7571.fly.dev/simulate \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"fmu_id":"msl:BouncingBall","stop_time":5.0,"step":0.01}'

# Option B: Pay with crypto (USDC, ETH, BTC, etc.)
curl -X POST https://fmu-gateway-long-pine-7571.fly.dev/simulate \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"fmu_id":"msl:BouncingBall","stop_time":5.0,"step":0.01,"payment_method":"crypto"}'

# 3. Complete payment and get results
```

**Live API:** https://fmu-gateway-long-pine-7571.fly.dev  
**Documentation:** https://fmu-gateway-long-pine-7571.fly.dev/docs

---

## 💻 Self-Hosting (Open Source)

This software is MIT licensed — you're free to run your own instance:

**Benefits:**
- Full control over infrastructure
- No per-simulation fees
- Customize for your needs

**Requirements:**
- Docker or Python 3.8+
- FMPy and dependencies
- Your own FMU files
- Server/compute resources

**Cost Comparison:**
- Hosted: $1/simulation, zero setup
- Self-hosted: $0/simulation, but server costs + maintenance time

**Most users find the hosted service more economical for occasional use.**

---

## Quick Start (AI Agent Friendly)

**Zero-configuration simulation:**
```bash
python run_fmu_simulation.py --auto
```

This automatically:
- ✓ Detects best gateway (local or public)
- ✓ Creates API key if needed
- ✓ Uploads FMU with smart caching
- ✓ Runs simulation and saves results

**Expected time: 10-20 seconds**

Need an upfront payment quote before executing? Add `--quote` to receive an HTTP
402 response with the amount, Stripe Checkout link, and next steps. Complete the
checkout using the returned `checkout_url` (or the `/pay` endpoint), call
`/payments/checkout/{session_id}` to retrieve the issued simulation token, and
rerun with `--payment-token <token>` to execute the paid simulation.

See [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md) for complete guide.

## Engineering Analysis Examples

### Scavenge pump capacity workflow

1. Start the gateway locally (`uvicorn app.main:app --host 0.0.0.0 --port 8000`).
2. Quote the job: `python run_fmu_simulation.py --auto --fmu app/library/msl/BouncingBall.fmu --quote`.
3. Generate a customer report: `python Engineering_Analysis_Examples/Scav_Capacity/run_example.py`.
4. Complete checkout (Stripe) and rerun with the token from `/payments/checkout/{session_id}`.

The analysis script stores JSON + Markdown briefs (and a PNG overview chart)
inside `Engineering_Analysis_Examples/Scav_Capacity/outputs/`. Those artefacts
are generated on demand and ignored by git so you can recreate them per run and
share the fresh outputs with customers as soon as payment clears.

### Fuel rail pressure example (no FMU required)

To generate a quick demonstration of rail pressure dynamics without sourcing a
full fuel-system FMU, run the lightweight analytical model:

```bash
python scripts/simulate_fuel_rail.py
```

This produces `data/fuel_rail_pressure.csv` with the time history plus a plot
(`data/fuel_rail_pressure.png`) that visualises pump and injector flows against
the resulting pressure fluctuations.

## Architecture
- FastAPI backend with endpoints: /fmus (upload), /fmus/{id}/variables (list), /simulate (run).
- Local disk storage (/app/data).
- FMPy for simulation; KPIs in kpi.py (extensible).
- Enhanced SDK with auto-detection and fallback support.
- Deterministic SQLite persistence when Postgres is unavailable.

## Security Notes
- Rejects non-Linux binaries unless sources present.
- Validates zip paths, input arrays.
- 20s simulation timeout; document MEMORY_LIMIT env for Fly.io (e.g., --vm-memory 512).
- No external processes beyond FMPy compilation; assumes FMUs can't access network.

## How to export an FMU from OpenModelica
- GUI: Load model > Simulate > Output > Export FMU.
- CLI: `omc --translateModelFMU=ModelName`.

## Database-free deployment
The gateway automatically falls back to SQLite when `DATABASE_URL` is unset. The
resolver tries, in order:

1. `FMU_GATEWAY_DB_PATH` if you want to provide an explicit path.
2. `/data/fmu_gateway.sqlite3` which maps to Fly.io's persistent volume mount.
3. `local.db` in the repository root for ad-hoc local runs.

This allows the service to operate with zero external dependencies while still
persisting API keys and usage counters. Set `STRIPE_ENABLED=false` to run fully
offline.

## Local dev
```bash
pip install -r requirements.txt
pip install -e ./sdk/python  # Install SDK
uvicorn app.main:app --reload
```

## Python SDK Usage

### Basic Usage
```python
from fmu_gateway_sdk.enhanced_client import EnhancedFMUGatewayClient, SimulateRequest

# Auto-detect best gateway
client = EnhancedFMUGatewayClient(gateway_url="auto")

# Upload with smart caching
fmu_meta = client.upload_fmu_smart("model.fmu")

# Simulate
req = SimulateRequest(fmu_id=fmu_meta['id'], stop_time=10.0, step=0.01)
result = client.simulate(req)
```

### With Fallback
```python
result = client.simulate_with_fallback(req, local_simulator=my_local_sim)
```

See [sdk/python/README.md](sdk/python/README.md) for full SDK documentation.

## cURL examples
- Upload: `curl -F "file=@path/to/model.fmu" http://localhost:8000/fmus`
- Variables: `curl http://localhost:8000/fmus/{id}/variables`
- Simulate: `curl -H "Content-Type: application/json" -d '{"fmu_id":"id","stop_time":1.0,"step":0.001,"start_values":{},"input_signals":[],"kpis":["y_rms"]}' http://localhost:8000/simulate`

## Fly.io deployment steps
1. Set FLY_API_TOKEN as GitHub secret. Done
2. Push to main; CI deploys automatically.
3. Access at https://{app}.fly.dev.

## Phase 2: MSL Library, SDKs, Auth, Tracking & Billing

### Modelica Standard Library (MSL)
- Pre-built FMUs in `/app/library/msl/` (generated via `scripts/msl_catalog_exporter.py` using OpenModelica).
- GET /library?query=<search> : List models with metadata (model_name, fmi_version, guid, description).
- Simulate with fmu_id = "msl:<model_name>" (no upload needed).

See [docs/library_management.md](docs/library_management.md) for detailed instructions on exporting additional FMUs from OpenModelica, dropping in externally sourced FMUs, and verifying that the gateway exposes them via `/library`.

### SDKs
#### Python
See `sdk/python/README.md` for installation and usage. Supports all endpoints, including library and auth.

#### JavaScript (Node.js)
See `sdk/js/README.md` for installation and usage. Supports all endpoints, including auth.

### API Keys & Authentication
- POST /keys : Generate API key (requires no auth).
- All other endpoints require `Authorization: Bearer <key>` header.
- Keys persisted in Postgres, usage tracked.

### Usage Tracking & Billing
- Postgres (Fly Postgres) tracks simulations per key (timestamp, fmu_id, duration).
- Stripe integration: $0.01 per simulation charged to customer linked to key.
- Set env: `STRIPE_SECRET_KEY`, `DATABASE_URL` (from `fly postgres attach`).

cURL example with auth:
- Key: `curl -X POST http://localhost:8000/keys` → {"key": "uuid"}
- Upload: `curl -H "Authorization: Bearer uuid" -F "file=@model.fmu" http://localhost:8000/fmus`
- Simulate library: `curl -H "Authorization: Bearer uuid" -H "Content-Type: application/json" -d '{"fmu_id":"msl:BouncingBall","stop_time":5.0,"step":0.01,"kpis":["y_rms"]}' http://localhost:8000/simulate`

### Fly.io Setup for Phase 2
1. Postgres: `fly postgres create --name fmu-gateway-db` then `fly postgres attach fmu-gateway-db --app fmu-gateway`
2. Secrets: `fly secrets set DATABASE_URL=$(fly postgres config show -a fmu-gateway-db | grep PRIMARY) STRIPE_SECRET_KEY=sk_... STRIPE_WEBHOOK_SECRET=whsec_... STRIPE_ENABLED=true PUBLIC_BASE_URL=https://<your-app>.fly.dev`
3. Redis (optional): Use Upstash or Fly Redis, set REDIS_URL.
4. Deploy: Push to main.
5. Optional: set `STRIPE_SIMULATION_PRICE_CENTS` (price in cents), `STRIPE_SIMULATION_CURRENCY`, `STRIPE_SUCCESS_URL`/`STRIPE_CANCEL_URL`, and `CHECKOUT_TOKEN_TTL_MINUTES` to tune pricing and session handling.

### A2A & 402 Protocol Compatibility (Future-Proofing)
- Supports Google's Agent-to-Agent (A2A) interactions with HTTP 402 "Payment Required" for unpaid simulations.
- When `STRIPE_ENABLED=true`, `/simulate` returns 402 with a Stripe Checkout link, price (default 1.00 USD), and session id whenever no valid payment token is supplied.
- Agents may also call `POST /pay` with an optional `fmu_id` to pre-create a checkout session and reuse the returned `session_id`/`checkout_url`.
- After Stripe emits `checkout.session.completed`, call `GET /payments/checkout/{session_id}` with the same API key to exchange the session for a short-lived simulation token.
- Submit that token via `/simulate` to consume the paid run; tokens expire automatically after use.
- Webhook endpoint: `POST /webhooks/stripe` (set `STRIPE_WEBHOOK_SECRET` for signature verification).

Example agent flow:
1. `POST /simulate` → receives HTTP 402 with `session_id` + `checkout_url`.
2. User completes Stripe Checkout (or agent opens the link).
3. `GET /payments/checkout/{session_id}` → returns `{"payment_token": ...}` once the webhook fires.
4. `POST /simulate` with `{"payment_token": ...}` to execute the simulation.

## Tests
- Phase 1: `pytest tests/`

---

## 📊 Pricing & Plans

### Pay-Per-Use (Current)
- **$1.00 per simulation**
- No commitment, pay as you go
- Instant access with test card
- Perfect for: Occasional simulations, evaluation, demos

### Credit Packs (Coming Soon)
- **10 simulations for $8** (20% discount)
- **50 simulations for $35** (30% discount)
- Pre-paid, never expires
- Perfect for: Regular users, batch analysis

### Enterprise (Contact Us)
- **Custom pricing** for high volume
- Priority support
- Custom models and integrations
- SLA guarantees
- Perfect for: Production systems, teams, partners

---

## 🌟 Why Choose Hosted FMU Gateway?

### vs. Running Locally
- **No setup time** (save hours of configuration)
- **No maintenance** (we handle updates, security, scaling)
- **Better performance** (optimized infrastructure)
- **Cost-effective** (no server costs for occasional use)

### vs. Other Simulation Services
- **Simple pricing** ($1 flat fee, no hidden costs)
- **Open source** (audit the code, trust the process)
- **Modern API** (REST + OpenAPI, easy integration)
- **Payment flexibility** (pay per use or bulk credits)

### vs. Manual FMPy
- **Instant results** (no local installation needed)
- **Model library** (pre-validated MSL models)
- **Provenance tracking** (reproducible results)
- **Parallel execution** (parameter sweeps)

---

## 🤝 Contributing

We welcome contributions! This is open source software under MIT License.

- **Report bugs:** Open an issue
- **Suggest features:** Create a discussion
- **Submit PRs:** Improvements welcome
- **Share:** Star the repo, tell colleagues

**Note:** Contributions to the code are MIT licensed. The hosted service and FMU library remain commercial offerings.

---

## 📄 License

This software is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

The hosted API service and FMU library are commercial services with separate terms.

---

## 🆘 Support

- **Documentation:** See [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md)
- **API Docs:** https://fmu-gateway-long-pine-7571.fly.dev/docs
- **Issues:** GitHub Issues for bugs and features
- **Enterprise:** Contact for custom support

---

## Tests
- Phase 1: `pytest tests/`