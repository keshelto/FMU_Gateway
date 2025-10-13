import pytest

def test_simulate_library(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key = resp.json()["key"]
    assert len(stripe_stub.records) == baseline + 1

    before = len(stripe_stub.records)

    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01,
        "kpis": ["h_rms"],
        "payment_token": "tok_visa",
        "payment_method": "google_pay"
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "ok"
    assert "summary_url" in result
    assert "h_rms" in result["key_results"]
    summary_resp = client.get(result["summary_url"], headers={"Authorization": f"Bearer {key}"})
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert "history" in summary
    assert len(summary["history"].get("time", [])) > 0
    new_records = stripe_stub.records[before:]
    assert any(entry["path"] == "/v1/payment_intents" for entry in new_records)
