# Turbo Spool-Up Reference Walkthrough

This hands-on example shows how an agent can exercise the FMU Gateway using a
"turbo spool" scenario.  It focuses on agent ergonomics: requesting an API key,
running a library FMU, and deriving KPIs that feel meaningful to a boost control
workflow (time-to-boost, settling, overshoot).  Until a dedicated turbocharger
FMU is published, the example uses the bundled `msl:BouncingBall` FMU as a
stand-in to keep the loop fully reproducible.

> **Why ship a placeholder?**  During repository review we noticed that the
> `Engineering_Analysis_Examples/Turbo_Spool_Up/` folder was referenced in the
> product narrative but the assets were missing.  The scripts here document the
> desired workflow and will automatically pick up a real spool FMU once it is
> dropped into `data/` or exported to the gateway's library.

## Prerequisites

1. Install the Python dependencies (`pip install -r requirements.txt`).
2. Start the FMU Gateway locally:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   The service now defaults to an embedded SQLite database, so no extra setup
   is required for local runs.

3. (Optional) Place a custom FMU named `TurboSpoolUp.fmu` inside this folder to
   replace the placeholder dynamics.  When present the runner will upload it
   automatically instead of using the library FMU.

## Running the example

```bash
python Engineering_Analysis_Examples/Turbo_Spool_Up/run_example.py
```

The script performs the following steps:

1. Detects the best gateway (local first, public fallback).
2. Requests an API key if one is not cached (`~/.fmu_gateway_key`).
3. Chooses the FMU: a local `TurboSpoolUp.fmu` if available, otherwise the
   built-in `msl:BouncingBall` library FMU.
4. Executes the simulation with the thresholds defined in
   `turbo_spool_config.json`.
5. Computes turbo-friendly metrics (time to 95% speed, settling time, overshoot)
   and writes `output/metrics.json` and `output/timeseries.csv` for downstream
   dashboards.

Console output summarises the KPIs so an agent can quickly report back to a
customer or trigger billing via the A2A/402 flow.

## Customising the run

- Edit `turbo_spool_config.json` to change stop time, step size, KPI list or the
  variable used for spool analysis (`analysis_variable`).
- Drop new FMUs into `data/` or the gateway library to expand available assets.
- Pass `--gateway-url=https://fmu-gateway.fly.dev` to target a remote instance.

## Next steps

- Swap in a physically representative turbocharger FMU.
- Extend the metrics module to push 402-compatible billing events once the
  micro-transaction backend is wired up.
- Publish screenshots / dashboards so customer agents can share spool curves in
  a single click.
