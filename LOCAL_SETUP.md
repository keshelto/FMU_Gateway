# Local Development Setup - FMU Gateway

## Quick Start (2 Simple Steps!)

### Step 1: Start the Local Gateway

**Option A - Double-click the file:**
- Just double-click `start_local_gateway.bat`
- A window will open showing the server is running

**Option B - From command line:**
```bash
start_local_gateway.bat
```

**Option C - PowerShell:**
```powershell
.\start_local_gateway.ps1
```

### Step 2: Test the Simulation

**Open a NEW terminal/command prompt** and run:
```bash
python run_fmu_simulation.py --auto --fmu=app/library/msl/BouncingBall.fmu
```

Or just double-click `test_simulation.bat`!

---

## What You Should See

### Terminal 1 (Gateway Server):
```
======================================================================
FMU GATEWAY - LOCAL SERVER
======================================================================

Starting local FMU Gateway...
Server will be available at: http://localhost:8000
Health check at: http://localhost:8000/health
API docs at: http://localhost:8000/docs

Press CTRL+C to stop the server

INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Terminal 2 (Simulation Test):
```
======================================================================
FMU GATEWAY - AUTOMATIC MODE
======================================================================

✓ Found FMU: app\library\msl\BouncingBall.fmu

🔍 Auto-detecting gateway...
✓ Using local FMU Gateway (http://localhost:8000)
✓ Created new API key
✓ FMU already on gateway (cached): ...

🚀 Running simulation (stop_time=10.0s, step=0.01s)...
✓ Simulation complete (X.Xs)

======================================================================
SIMULATION RESULTS
======================================================================
Status: ok
Variables: [...]
Time points: 1001

✓ Results saved to: simulation_results/BouncingBall_results.json
✓ CSV saved to: simulation_results/BouncingBall_results.csv
```

---

## Troubleshooting

### Port 8000 already in use?
Kill the process:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F
```

### Database errors?
Delete the local database:
```bash
del local.db
```

### Module not found errors?
Install requirements:
```bash
pip install -r requirements.txt
pip install -e ./sdk/python
```

---

## What the Scripts Do

### `start_local_gateway.bat`
- Sets `DATABASE_URL=sqlite:///./local.db` (uses local SQLite)
- Sets `STRIPE_ENABLED=false` (no payment required)
- Starts uvicorn with auto-reload
- Server runs at http://localhost:8000

### `test_simulation.bat`
- Runs the simulation with auto-detection
- Uses the BouncingBall example from the library
- Shows results and pauses so you can read them

---

## API Endpoints (Local)

- **Health Check**: http://localhost:8000/health
- **API Documentation**: http://localhost:8000/docs
- **Upload FMU**: POST http://localhost:8000/fmus
- **Simulate**: POST http://localhost:8000/simulate
- **Library**: GET http://localhost:8000/library

---

## Features Working Locally

✅ Auto-detection (finds localhost first)  
✅ Smart FMU caching via hash  
✅ API key generation  
✅ No payment required  
✅ Full simulation workflow  
✅ Result saving (JSON + CSV)  

---

## Stop the Server

Press **CTRL+C** in the terminal running the gateway.

---

## Need Help?

1. Check that you're in the project directory
2. Make sure requirements are installed
3. Verify Python 3.8+ is installed
4. Check the logs in the gateway terminal

**All scripts are ready to use! Just double-click `start_local_gateway.bat` to begin!**

