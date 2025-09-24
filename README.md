# FMU Gateway

## What this is
A secure, deterministic service for uploading and simulating FMI 2.0/3.0 FMUs (ME & CS) using FMPy. Deployed on Fly.io in Docker. Priorities: small API surface, security (e.g., platform checks, no network during sim), and clear schemas.

## Architecture
- FastAPI backend with endpoints: /fmus (upload), /fmus/{id}/variables (list), /simulate (run).
- Local disk storage (/app/data).
- FMPy for simulation; KPIs in kpi.py (extensible).

## Security Notes
- Rejects non-Linux binaries unless sources present.
- Validates zip paths, input arrays.
- 20s simulation timeout; document MEMORY_LIMIT env for Fly.io (e.g., --vm-memory 512).
- No external processes beyond FMPy compilation; assumes FMUs can't access network.

## How to export an FMU from OpenModelica
- GUI: Load model > Simulate > Output > Export FMU.
- CLI: `omc --translateModelFMU=ModelName`.

## Local dev
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## cURL examples
- Upload: `curl -F "file=@path/to/model.fmu" http://localhost:8000/fmus`
- Variables: `curl http://localhost:8000/fmus/{id}/variables`
- Simulate: `curl -H "Content-Type: application/json" -d '{"fmu_id":"id","stop_time":1.0,"step":0.001,"start_values":{},"input_signals":[],"kpis":["y_rms"]}' http://localhost:8000/simulate`

## Fly.io deployment steps
1. Set FLY_API_TOKEN as GitHub secret. Done
2. Push to main; CI deploys automatically.
3. Access at https://{app}.fly.dev.

## Notes on bringing Simulink/GT-SUITE FMUs later
Export as Linux-compatible or source FMU (FMPy compiles sources).
## Capabilities for AI Agents
- **FMI Support**: FMI 2.0/3.0 for Model Exchange (ME) and Co-Simulation (CS).
- **Upload FMU**: POST /fmus - Upload and register FMU, returns ID, FMI version, model name, GUID, SHA256.
- **List Variables**: GET /fmus/{id}/variables - Get list of variables with name, causality, variability, declaredType.
- **Simulate**: POST /simulate - Run simulation with stop_time, step, start_values, input_signals (time-series), kpis (e.g., y_rms; extensible).
- **Security & Limits**: 20s timeout, 5MB response cap, platform validation (Linux binaries or sources required), no network during sim.
- **Provenance**: All responses include FMI version, GUID, SHA256 for determinism.
- **Extensibility**: Easy to add custom KPIs in kpi.py.

# Test comment to trigger deploy
