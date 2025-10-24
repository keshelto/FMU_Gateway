# Scavenge Pump Capacity Example

This example demonstrates how a customer-facing agent can use the FMU Gateway
outputs to validate a dry-sump scavenge pump design before charging for the
simulation through 402-style micropayments.

## Prerequisites

1. Start a local gateway instance:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. Install the Python SDK in editable mode (optional for richer logging):
   ```bash
   pip install -e ./sdk/python
   ```

## Step 1 – Quote the job

Generate a payment quote without executing the simulation by running:

```bash
python run_fmu_simulation.py --auto --fmu app/library/msl/BouncingBall.fmu --quote
```

The CLI now sends `quote_only=true` so the gateway replies with HTTP 402 and a
structured payload containing the required amount, supported methods, and next
steps for A2A/x402 compliant flows.

## Step 2 – Run the scavenge capacity analysis

Process the example data set (derived from a gateway FMU run) and produce a
customer-facing summary:

```bash
python examples/offline/Engineering_Analysis_Examples/Scav_Capacity/run_example.py
```

When you run the script it writes customer-ready artefacts to
`examples/offline/Engineering_Analysis_Examples/Scav_Capacity/outputs/`:

- `scavenge_capacity_summary.json` – machine-readable metrics for downstream agents
- `scavenge_capacity_summary.md` – ready-to-send briefing for customers
- `scavenge_capacity_overview.png` – visual bundle of inputs, calculations, and results for customer review

These generated files are ignored by git so the repository stays lightweight.
Regenerate them at any time by rerunning the command above. Each report includes
the live gateway health status so your agent can reassure the customer that the
service is online before requesting payment.

## Step 3 – Collect payment and execute

Once the customer approves the quote, call the CLI again with the payment
credentials you obtained via Google Pay or Stripe:

```bash
python run_fmu_simulation.py --auto \
    --fmu app/library/msl/BouncingBall.fmu \
    --payment-token <token_from_wallet> \
    --payment-method google_pay
```

The gateway records the transaction metadata and charges the linked account for
$0.01 per run. Results are written to `simulation_results/` as JSON and CSV for
further post-processing or upsell opportunities (plots, dashboards, etc.).

## KPIs surfaced in the summary

The analysis script reports:

- Engine speed range covered by the FMU scenario
- Mean/min/max ratio of scavenge to pressure flow (target ≥ 3x)
- Pump displacement statistics in cm³ per revolution
- Recommended 10% safety margin for flow capacity
- Annotated visualization aligning the raw data with the margin recommendation

Use these headline figures in customer proposals or integrate them into a wider
agent workflow that automates quoting, payment, execution, and report delivery.
