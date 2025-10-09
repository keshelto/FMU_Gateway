# FMU Gateway

## What this is
A secure, deterministic service for uploading and simulating FMI 2.0/3.0 FMUs (ME & CS) using FMPy. Deployed on Fly.io in Docker. Priorities: small API surface, security (e.g., platform checks, no network during sim), and clear schemas.

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
402 response with amount, supported methods, and next steps. When you have a
Google Pay or Stripe token, reuse the same command with
`--payment-token <token> --payment-method google_pay` to execute and charge.

See [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md) for complete guide.

## Engineering Analysis Examples

### Scavenge pump capacity workflow

1. Start the gateway locally (`uvicorn app.main:app --host 0.0.0.0 --port 8000`).
2. Quote the job: `python run_fmu_simulation.py --auto --fmu app/library/msl/BouncingBall.fmu --quote`.
3. Generate a customer report: `python Engineering_Analysis_Examples/Scav_Capacity/run_example.py`.
4. Collect payment and rerun with `--payment-token` once authorised.

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
- Pre-built FMUs in `/app/library/msl/` (generated via `scripts/export_msl_fmus.py` using OpenModelica).
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
2. Secrets: `fly secrets set DATABASE_URL=$(fly postgres config show -a fmu-gateway-db | grep PRIMARY) STRIPE_SECRET_KEY=sk_...`
3. Redis (optional): Use Upstash or Fly Redis, set REDIS_URL.
4. Deploy: Push to main.

### A2A & 402 Protocol Compatibility (Future-Proofing)
- Supports Google's Agent-to-Agent (A2A) interactions with HTTP 402 "Payment Required" for unpaid simulations.
- In `/simulate`, if `STRIPE_ENABLED=true` and no `payment_token`, returns 402 with payment details (0.01 USD, methods: google_pay/stripe_card).
- Agents send `payment_token` (Stripe/Google Pay) and `payment_method` in request body to pay and simulate in one call.
- Verification via Stripe (PaymentIntent for tokens). Set `STRIPE_SECRET_KEY` for live; mocks in tests.
- Example for agents: POST /simulate with token → 200 if paid, else 402. Usage tracked for billing reconciliation.

cURL example (with payment token):
- `curl -H "Authorization: Bearer <key>" -H "Content-Type: application/json" -d '{"fmu_id":"msl:BouncingBall","stop_time":1.0,"step":0.01,"kpis":["y_rms"],"payment_token":"tok_visa","payment_method":"stripe_card"}' http://localhost:8000/simulate`

For Google Pay: Agents use Google Pay API to get token, send as `payment_token`. Extend for full A2A chaining (e.g., /pay endpoint if needed).

## Tests
- Phase 1: `pytest tests/`