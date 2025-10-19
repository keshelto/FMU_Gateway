# SDK Usage Guide

## Installation
1. Clone the `open-sdk` directory into your project or install via `pip install -e .`.
2. Ensure you have Python 3.9+ and `requests` installed.

## Authentication
- Obtain an API key from the FMU Gateway dashboard.
- Set `FMU_GATEWAY_API_KEY` in your environment or pass directly to `FMUGatewayClient`.

## Executing an FMU
```python
from fmu_gateway_sdk.client import FMUGatewayClient

client = FMUGatewayClient(api_key="YOUR_API_KEY", base_url="https://api.fmu-gateway.com")
result = client.execute_fmu("/path/to/plant.fmu", parameters={"steps": 500})
print(result["status"], result["output_url"])
```

## Monitoring Usage
```python
usage = client.get_usage()
print("Remaining credits:", usage["user_123"]["credits"])
```

## Webhook Registration
```python
client.register_webhook("https://example.com/stripe-webhook")
```

## Local Testing
- Use `deploy/docker-compose.yml` to run the SDK and private API locally.
- Execute `make run` to start both containers for rapid integration testing.
