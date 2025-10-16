from tests.payment_utils import purchase_token


def test_simulate_library(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key = resp.json()["key"]
    assert len(stripe_stub.records) == baseline + 1

    simulate_payload = {
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01,
        "kpis": ["h_rms"],
    }

    before = len(stripe_stub.records)
    token, checkout_body = purchase_token(client, key, simulate_payload)
    assert checkout_body["session_id"].startswith("cs_test")

    new_records = stripe_stub.records[before:]
    assert any(entry["path"] == "/v1/checkout/sessions" for entry in new_records)

    paid_payload = dict(simulate_payload)
    paid_payload["payment_token"] = token

    resp = client.post(
        "/simulate",
        headers={"Authorization": f"Bearer {key}"},
        json=paid_payload,
    )
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

    final_records = stripe_stub.records[before:]
    assert not any(entry["path"] == "/v1/payment_intents" for entry in final_records)
