# FMU Gateway Python SDK

## Installation
```bash
pip install -e ./sdk/python  # From local repo (development mode)
# Or: pip install ./sdk/python
# Or publish to PyPI later
```

## Quick Start (Enhanced Client - Recommended)

```python
from fmu_gateway_sdk import EnhancedFMUGatewayClient, SimulateRequest

# Auto-detect best gateway
client = EnhancedFMUGatewayClient(gateway_url="auto")

# Upload with smart caching (avoids re-uploading same FMU)
fmu_meta = client.upload_fmu_smart('path/to/model.fmu')

# Simulate
req = SimulateRequest(
    fmu_id=fmu_meta['id'],
    stop_time=10.0,
    step=0.01,
    kpis=['y_rms']
)
result = client.simulate(req)

# Access results
print(f"Status: {result['status']}")
print(f"Variables: {list(result['y'].keys())}")
print(f"KPIs: {result['kpis']}")
```

## Enhanced Features

### Auto-Detection
```python
# Automatically tries:
# 1. Local gateway (http://localhost:8000)
# 2. Public gateway (https://fmu-gateway.fly.dev)
client = EnhancedFMUGatewayClient(gateway_url="auto")
```

### Smart Caching
```python
# Checks if FMU already uploaded via SHA256 hash
# Avoids re-uploading same file
fmu_meta = client.upload_fmu_smart('model.fmu')
```

### Fallback Support
```python
def my_local_simulator(req):
    # Your local simulation implementation
    return {"status": "ok", "t": [...], "y": {...}}

# Tries gateway first, falls back to local if unavailable
result = client.simulate_with_fallback(req, local_simulator=my_local_simulator)
```

### Parameter Sweep (Parallel)
```python
base_req = SimulateRequest(fmu_id=fmu_id, stop_time=10.0, step=0.01)

results = client.parameter_sweep_parallel(
    base_req,
    param_name="stiffness",
    param_values=[1.0, 1.5, 2.0, 2.5, 3.0],
    max_workers=10
)
```

## Basic Client (Original)

For simpler use cases without auto-detection:

```python
from fmu_gateway_sdk import FMUGatewayClient

client = FMUGatewayClient('https://fmu-gateway.fly.dev', api_key='your-key')

# Upload FMU
meta = client.upload_fmu('path/to/model.fmu')
fmu_id = meta['id']

# Get variables
vars = client.get_variables(fmu_id)

# Simulate
from fmu_gateway_sdk import SimulateRequest
req = SimulateRequest(
    fmu_id=fmu_id,
    stop_time=1.0,
    step=0.001,
    kpis=['y_rms']
)
result = client.simulate(req)

# Library
library = client.get_library('Bouncing')
```

## API Keys

### Getting a Key
```python
import requests
response = requests.post('https://fmu-gateway.fly.dev/keys')
api_key = response.json()['key']
```

### Using a Key
```python
client = EnhancedFMUGatewayClient(
    gateway_url="auto",
    api_key="your-api-key-here"
)
```

The enhanced client can also auto-create keys if needed.

## Library Models

Use pre-validated models from the Modelica Standard Library:

```python
# List available models
library = client.get_library(query="Bouncing")

# Simulate library model (no upload needed)
req = SimulateRequest(
    fmu_id="msl:BouncingBall",  # Library prefix
    stop_time=5.0,
    step=0.01,
    kpis=["y_rms"]
)
result = client.simulate(req)
```

## Configuration Options

### EnhancedFMUGatewayClient
```python
client = EnhancedFMUGatewayClient(
    gateway_url="auto",      # "auto", None, or specific URL
    api_key=None,             # Optional API key
    auto_fallback=True,       # Enable fallback to local
    verbose=True              # Print status messages
)
```

### SimulateRequest
```python
from fmu_gateway_sdk import SimulateRequest, InputSignal

req = SimulateRequest(
    fmu_id="abc123",
    stop_time=10.0,           # Simulation end time
    step=0.01,                # Time step
    start_values={            # Initial parameter values
        "param1": 1.5,
        "param2": 2.0
    },
    input_signals=[           # Time-varying inputs
        InputSignal(
            name="input1",
            t=[0.0, 1.0, 2.0],
            u=[0.0, 1.0, 0.0]
        )
    ],
    kpis=["y_rms", "y_mean"]  # Key Performance Indicators to compute
)
```

## Error Handling

```python
try:
    result = client.simulate(req)
except ConnectionError as e:
    print(f"Gateway unavailable: {e}")
except requests.HTTPError as e:
    print(f"API error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

The enhanced client provides detailed error messages with actionable guidance.

## See Also

- [AI_AGENT_GUIDE.md](../../AI_AGENT_GUIDE.md) - Complete guide for AI agents
- [README.md](../../README.md) - Main project documentation
