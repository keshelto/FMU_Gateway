import pytest

from sdk.python.fmu_gateway_sdk.enhanced_client import (
    EnhancedFMUGatewayClient,
    SimulateRequest,
)


def test_local_simulation_blocked_in_prod(monkeypatch):
    client = EnhancedFMUGatewayClient(
        gateway_url="http://example.com",
        api_key=None,
        auto_fallback=True,
        verbose=False,
    )
    monkeypatch.setenv("FMU_GATEWAY_ENV", "PROD")

    def failing_simulation(_req: SimulateRequest, retry_once: bool = True):  # pragma: no cover - signature compliance
        raise ConnectionError("gateway unavailable")

    monkeypatch.setattr(client, "simulate", failing_simulation)

    request = SimulateRequest(fmu_id="demo", stop_time=1.0, step=0.1)

    with pytest.raises(RuntimeError, match="Local simulation disabled in PROD"):
        client.simulate_with_fallback(request, local_simulator=lambda _: {"status": "ok"})
