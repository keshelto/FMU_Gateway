from app.db import Usage, ApiKey, SessionLocal
from tests.payment_utils import purchase_token


def test_usage_logged(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key = resp.json()["key"]
    assert len(stripe_stub.records) == baseline + 1

    simulate_payload = {
        "fmu_id": "msl:BouncingBall",
        "stop_time": 0.1,
        "step": 0.01,
    }

    before = len(stripe_stub.records)
    token, _ = purchase_token(client, key, simulate_payload)

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

    # Check DB
    db = SessionLocal()
    api_key_obj = db.query(ApiKey).filter(ApiKey.key == key).first()
    usages = db.query(Usage).filter(Usage.api_key_id == api_key_obj.id).all()
    assert len(usages) == 1
    assert usages[0].fmu_id == "msl:BouncingBall"
    assert usages[0].duration_ms > 0
    db.close()
