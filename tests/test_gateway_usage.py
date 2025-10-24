import logging
import math
from typing import Dict, Iterable, Optional

import pytest

from sdk.python.fmu_gateway_sdk.enhanced_client import (
    EnhancedFMUGatewayClient,
    SimulateRequest,
)

from tests.payment_utils import purchase_token


def _issue_key(client) -> str:
    response = client.post("/keys")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "key" in payload
    return payload["key"]


def _authorized_headers(key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.mark.parametrize("query", ["BouncingBall", "bouncing"])
def test_library_query_returns_items(client, query):
    """Smoke test the /library search endpoint."""
    key = _issue_key(client)

    response = client.get("/library", headers=_authorized_headers(key), params={"query": query})
    assert response.status_code == 200, response.text

    items = response.json().get("items", [])
    assert items, "Expected at least one catalog entry"
    assert any("BouncingBall" in item.get("model_name", "") for item in items)


def _pick_history_series(history: dict[str, list[float]], candidates: Iterable[str]) -> Optional[list[float]]:
    for name in candidates:
        if name in history:
            return history[name]
    return None


def test_simulate_bouncing_ball(client, caplog, stripe_stub):
    _ = stripe_stub  # ensure stub lifecycle for payment flows
    key = _issue_key(client)

    simulate_payload = {
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 1e-3,
    }

    token, _ = purchase_token(client, key, simulate_payload)

    gateway = EnhancedFMUGatewayClient(
        gateway_url=str(client.base_url),
        api_key=key,
        auto_fallback=False,
        verbose=False,
    )

    original_session = gateway.session
    try:
        gateway.session = client
        client.headers.update(_authorized_headers(key))

        simulate_request = SimulateRequest(**simulate_payload, payment_token=token)
        with caplog.at_level(logging.INFO, logger="sdk.python.fmu_gateway_sdk.enhanced_client"):
            result = gateway.simulate(simulate_request)
    finally:
        gateway.session = original_session
        try:
            del client.headers["Authorization"]
        except KeyError:  # pragma: no cover - defensive cleanup
            pass

    assert result["status"] == "ok"
    assert "summary_url" in result

    summary_response = client.get(result["summary_url"], headers=_authorized_headers(key))
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()

    history = summary.get("history", {})
    time_series = history.get("time", [])
    assert len(time_series) > 10, "Expected time vector with multiple samples"

    height_series = _pick_history_series(history, ("height", "Height", "h", "ball.h"))
    assert height_series is not None, f"Height-like signal missing: {history.keys()}"
    assert len(height_series) == len(time_series)
    assert all(math.isfinite(value) for value in height_series)

    assert any("Executed via FMU Gateway" in message for message in caplog.messages)
