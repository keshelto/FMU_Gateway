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
1. Set FLY_API_TOKEN as GitHub secret.
2. Push to main; CI deploys automatically.
3. Access at https://{app}.fly.dev.

## Notes on bringing Simulink/GT-SUITE FMUs later
Export as Linux-compatible or source FMU (FMPy compiles sources).
