import pytest
from app.db import Usage, ApiKey, SessionLocal

def test_usage_logged(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key_data = resp.json()
    key = key_data["key"]
    assert len(stripe_stub.records) == baseline + 1

    # Simulate
    before = len(stripe_stub.records)

    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 0.1,  # short
        "step": 0.01,
        "payment_token": "tok_visa",
        "payment_method": "google_pay"
    })
    assert resp.status_code == 200
    new_records = stripe_stub.records[before:]
    assert any(entry["path"] == "/v1/payment_intents" for entry in new_records)

    # Check DB
    db = SessionLocal()
    api_key_obj = db.query(ApiKey).filter(ApiKey.key == key).first()
    usages = db.query(Usage).filter(Usage.api_key_id == api_key_obj.id).all()
    assert len(usages) == 1
    assert usages[0].fmu_id == "msl:BouncingBall"
    assert usages[0].duration_ms > 0
    db.close()
