def test_402_unpaid(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key = resp.json()["key"]
    assert len(stripe_stub.records) == baseline + 1

    before = len(stripe_stub.records)

    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01
    })
    assert resp.status_code == 402
    assert resp.json()["amount"] == 0.01
    assert "google_pay" in resp.json()["methods"]
    after = len(stripe_stub.records)
    assert after == before  # No additional Stripe calls without payment

def test_paid_simulation(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key = resp.json()["key"]
    assert len(stripe_stub.records) == baseline + 1

    before = len(stripe_stub.records)

    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01,
        "payment_token": "tok_visa",
        "payment_method": "google_pay"
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    new_records = stripe_stub.records[before:]
    assert any(entry["path"] == "/v1/payment_intents" for entry in new_records)
