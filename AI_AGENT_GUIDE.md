# FMU Gateway - Quick Reference for AI Agents

## Overview

FMU Gateway is a service for running FMU (Functional Mock-up Unit) simulations via HTTP/REST API. This guide provides the fastest path to results with zero configuration required.

**[Inference]** This guide is based on the designed workflow, but actual performance and reliability depend on network conditions, system configuration, and gateway availability.

## Fastest Path to Results

### One-Command Solution

```bash
python run_fmu_simulation.py --auto
```

This single command will:
1. ✓ Find available FMU files automatically
2. ✓ Detect best gateway (local or public)
3. ✓ Create API key if needed
4. ✓ Upload FMU with smart caching
5. ✓ Run simulation
6. ✓ Save results (JSON + CSV)

**Expected time: 10-20 seconds** (first run with upload)
**Expected time: 5-10 seconds** (subsequent runs with cached FMU)

## Check Service Status

### Public Gateway
```bash
curl https://fmu-gateway.fly.dev/health
```
Expected response:
```json
{"status": "healthy", "version": "1.0.0"}
```

### Local Gateway
```bash
curl http://localhost:8000/health
```

If local gateway is not running, start it with:
```bash
uvicorn app.main:app --reload
```

## Expected Performance

**[Inference]** These are target performance metrics, actual times vary based on:
- Network speed and latency
- FMU file size and complexity
- Simulation duration and step size
- Gateway server load

| Operation | First Time | Cached |
|-----------|-----------|---------|
| Service health check | <1s | <1s |
| FMU upload | 2-5s | <0.1s |
| Simulation (typical) | 5-15s | 5-15s |
| Results download | <1s | <1s |
| **Total workflow** | **~10-20s** | **~5-15s** |

## Usage Modes

### Auto Mode (Recommended)
```bash
python run_fmu_simulation.py --auto
```
- ✓ Automatically detects best configuration
- ✓ Uses gateway if available, fallback to local if needed
- ✓ Zero configuration required

### Gateway Mode
```bash
python run_fmu_simulation.py --mode=gateway
```
- Forces use of FMU Gateway
- Fails if gateway unavailable
- Use when you need gateway-specific features

### Local Mode
```bash
python run_fmu_simulation.py --mode=local
```
- Uses local Python simulation (if implemented)
- No network required
- May have different numerical results than FMU

### Benchmark Mode
```bash
python run_fmu_simulation.py --mode=benchmark
```
- Runs both gateway and local simulations
- Compares performance and results
- Useful for validation and trust building

## Custom Configuration

### Using Config File
```bash
python run_fmu_simulation.py --auto --config=params.json
```

Example `params.json`:
```json
{
  "stop_time": 10.0,
  "step": 0.01,
  "start_values": {
    "parameter1": 1.5,
    "parameter2": 2.0
  },
  "kpis": ["y_rms", "y_mean"]
}
```

### Specifying FMU File
```bash
python run_fmu_simulation.py --auto --fmu=path/to/model.fmu
```

## Success Indicators

### Command Line Output
```
✓ Found FMU: model.fmu
✓ Using public FMU Gateway (https://fmu-gateway.fly.dev)
✓ Created new API key
✓ FMU already on gateway (cached): abc123...
✓ Simulation complete (8.2s)
✓ Results saved to: simulation_results/model_results.json
```

### Exit Codes
- `0` = Success
- `1` = Error occurred

### Output Files
```
simulation_results/
├── model_results.json    # Full results with metadata
└── model_results.csv     # Time series data
```

## Common Issues & Auto-Fixes

**[Inference]** These automated fixes are designed based on common failure modes, but cannot prevent all possible errors.

### FMU Not Found
```
❌ No FMU found

Auto-fix:
1. Searches current directory
2. Checks app/library/msl/
3. Checks data/ directory
4. Attempts to compile from .mo file (if OpenModelica available)
```

**Manual fix:** Specify FMU path with `--fmu=path/to/file.fmu`

### Gateway Not Responding
```
⚠️ No gateway available

Auto-fix:
1. Tries localhost:8000 (local gateway)
2. Tries fmu-gateway.fly.dev (public gateway)
3. Falls back to local simulation (if implemented)
```

**Manual fix:**
- Start local gateway: `uvicorn app.main:app --reload`
- Check network connection
- Use `--mode=local` for offline operation

### Network Timeout
```
⚠️ Network error, retrying once...

Auto-fix:
- Automatic retry with 1s backoff
- Exponential backoff for multiple failures
```

**Manual fix:**
- Check internet connection
- Try local gateway
- Use `--mode=local`

### Invalid Parameters
```
⚠️ Invalid parameter values

Auto-fix:
- Uses validated defaults with warning
- Continues simulation with safe values
```

**Manual fix:** Check config file for valid parameter ranges

### OpenModelica Not Found (for compilation)
```
❌ OpenModelica not installed

Auto-fix:
- Provides OS-specific installation instructions
- Falls back to local simulation if available
```

**Manual fix:** Install OpenModelica or provide pre-compiled .fmu file

## Decision Tree for AI Agents

When deciding how to run an FMU simulation, follow this logic:

```
1. Is FMU file present?
   YES → Continue
   NO  → Can compile from .mo? YES → Compile, NO → Error

2. Is gateway reachable?
   YES → Use gateway (preferred)
   NO  → Local simulation available? YES → Use local, NO → Error

3. Did simulation succeed?
   YES → Save results, exit 0
   NO  → Retry once?
       YES → Retry with backoff
       NO  → Try fallback? YES → Fallback, NO → Error
```

## When to Use Gateway vs Local

### Use Gateway When:
- ✓ Running parameter sweeps (parallel execution)
- ✓ Production runs requiring provenance tracking
- ✓ Need advanced solvers (CVODE, IDA, etc.)
- ✓ Using standardized model library
- ✓ Results need to be reproducible across systems
- ✓ Want automatic caching and optimization

### Use Local When:
- ✓ Quick tests and development
- ✓ No network available (offline)
- ✓ Gateway unavailable
- ✓ Very simple models
- ✓ Custom solver requirements

### Default Strategy:
**Try gateway first, fallback to local automatically**

This provides the best of both worlds:
- Gateway speed and features when available
- Reliability through local fallback
- Zero configuration required

## Python SDK Usage

For more control, use the SDK directly:

```python
from fmu_gateway_sdk.enhanced_client import EnhancedFMUGatewayClient, SimulateRequest

# Auto-detect best gateway
client = EnhancedFMUGatewayClient(gateway_url="auto")

# Upload FMU with smart caching
fmu_meta = client.upload_fmu_smart("model.fmu")

# Run simulation
req = SimulateRequest(
    fmu_id=fmu_meta['id'],
    stop_time=10.0,
    step=0.01,
    kpis=["y_rms"]
)
result = client.simulate(req)

# Access results
time = result['t']
variables = result['y']
kpis = result['kpis']
```

### With Fallback

```python
def local_simulator(req):
    # Your local simulation implementation
    pass

result = client.simulate_with_fallback(req, local_simulator=local_simulator)
```

## Advanced Features

### Parameter Sweep (Parallel)

```python
from fmu_gateway_sdk.enhanced_client import EnhancedFMUGatewayClient, SimulateRequest

client = EnhancedFMUGatewayClient(gateway_url="auto")
fmu_meta = client.upload_fmu_smart("model.fmu")

base_req = SimulateRequest(
    fmu_id=fmu_meta['id'],
    stop_time=10.0,
    step=0.01
)

# Run parameter sweep
param_values = [1.0, 1.5, 2.0, 2.5, 3.0]
results = client.parameter_sweep_parallel(
    base_req,
    param_name="stiffness",
    param_values=param_values,
    max_workers=10
)
```

**[Inference]** Parallel execution may provide speedup over sequential local execution, depending on gateway resources and network overhead.

### Model Library

```python
# List available pre-validated models
library = client.get_library(query="Bouncing")

# Use library model (no upload needed)
req = SimulateRequest(
    fmu_id="msl:BouncingBall",  # Library prefix
    stop_time=5.0,
    step=0.01,
    kpis=["y_rms"]
)
result = client.simulate(req)
```

## Troubleshooting

### Debug Mode

Run with verbose output:
```bash
python run_fmu_simulation.py --auto  # Already verbose by default
python run_fmu_simulation.py --auto --quiet  # Suppress output
```

### Check Logs

Gateway logs (if running locally):
```bash
# Terminal running uvicorn will show request logs
```

### Test API Key

```bash
curl -X POST https://fmu-gateway.fly.dev/keys
```

Returns:
```json
{"key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}
```

### Test Upload

```bash
curl -H "Authorization: Bearer YOUR_KEY" \
     -F "file=@model.fmu" \
     https://fmu-gateway.fly.dev/fmus
```

## Performance Optimization Tips

**[Inference]** These optimizations may improve performance in typical scenarios, but actual impact depends on specific use cases.

1. **Reuse FMUs**: Upload once, simulate many times
2. **Use Caching**: Let smart caching detect duplicate FMUs
3. **Batch Simulations**: Use parameter sweep for multiple runs
4. **Choose Step Size Carefully**: Smaller steps = longer simulation
5. **Request Only Needed KPIs**: Reduces data transfer
6. **Use Local Gateway**: Eliminates network latency

## Security Notes

- API keys are stored in `~/.fmu_gateway_key`
- Keys are UUIDs (not sensitive, but treat as credentials)
- Gateway validates FMU files before execution
- Simulations run in isolated environment
- 20-second timeout per simulation
- No external network access during simulation

## Error Reference

| Error | Cause | Solution |
|-------|-------|----------|
| `No gateway available` | Cannot reach local or public gateway | Start local gateway or check network |
| `FMU not found` | No .fmu file in search paths | Specify with --fmu or compile from .mo |
| `Upload failed` | Network issue or invalid FMU | Check file and connection |
| `Simulation timeout` | Model took >20s | Reduce stop_time or increase step size |
| `Invalid API key` | Key expired or invalid | Delete ~/.fmu_gateway_key and retry |
| `402 Payment Required` | Simulation requires payment | Provide payment token (A2A protocol) |

## Support

- **Documentation**: `README.md`
- **Source**: Check project repository
- **Issues**: Report bugs via issue tracker
- **API Docs**: Visit `/docs` endpoint on gateway

## Version Compatibility

- **FMI**: 2.0 and 3.0 supported
- **Python**: 3.8+
- **FMPy**: 0.3.22+
- **Platform**: Windows, Linux, macOS

---

**Last Updated**: 2025-10-05

**Note**: All performance estimates and automated behaviors are based on typical usage patterns and may vary in practice. Always validate results for production use.
