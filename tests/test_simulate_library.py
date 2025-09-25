import pytest

def test_simulate_library(client):
    resp = client.post("/keys")
    key = resp.json()["key"]

    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01,
        "kpis": ["y_rms"]
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "ok"
    assert len(result["t"]) > 0
    assert "y_rms" in result["kpis"]
