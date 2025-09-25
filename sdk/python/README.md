# FMU Gateway Python SDK

## Installation
```bash
pip install ./sdk/python  # From local repo
# Or publish to PyPI later
```

## Usage
```python
from fmu_gateway_sdk import FMUGatewayClient

client = FMUGatewayClient('https://your-app.fly.dev')

# Upload FMU
meta = client.upload_fmu('path/to/model.fmu')
fmu_id = meta['id']

# Get variables
vars = client.get_variables(fmu_id)

# Simulate
from fmu_gateway_sdk.client import SimulateRequest, InputSignal
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

For API keys, pass api_key to client.
