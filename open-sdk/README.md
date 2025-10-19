# FMU Gateway SDK

The FMU Gateway SDK provides Python tooling for interacting with the FMU Gateway service. It enables engineers to authenticate with API keys, upload Functional Mock-up Units (FMUs), and execute simulations remotely through the monetized backend.

## Features
- Lightweight API client with synchronous FMU execution support
- API key and JWT authentication helpers
- Utilities for FMU validation and request construction
- Examples demonstrating SDK usage

## Installation
```bash
pip install -e .
```

## Quick Start
```python
from fmu_gateway_sdk.client import FMUGatewayClient

client = FMUGatewayClient(api_key="YOUR_API_KEY", base_url="https://api.fmu-gateway.com")
response = client.execute_fmu("/path/to/model.fmu", parameters={"steps": 100})
print(response)
```

## Development
- `make build` to build the SDK test image.
- `make run` to run example scripts.
- `make deploy` to publish the SDK package (placeholder instructions).

