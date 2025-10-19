"""Example script demonstrating how to execute an FMU using the SDK."""
from __future__ import annotations

from fmu_gateway_sdk.client import FMUGatewayClient


def main() -> None:
    """Load an API key from the environment and run a sample FMU."""
    import os

    api_key = os.environ.get("FMU_GATEWAY_API_KEY", "demo-key")
    client = FMUGatewayClient(api_key=api_key, base_url="http://localhost:8000")
    response = client.execute_fmu("./sample.fmu", parameters={"steps": 10})
    print(response)


if __name__ == "__main__":
    main()
