import pytest
from app.db import Usage, ApiKey
from sqlalchemy.orm import Session

def test_usage_logged(client):
    resp = client.post("/keys")
    key_data = resp.json()
    key = key_data["key"]

    # Simulate
    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 0.1,  # short
        "step": 0.01,
    })
    assert resp.status_code == 200

    # Check DB
    db = SessionLocal()
    api_key_obj = db.query(ApiKey).filter(ApiKey.key == key).first()
    usages = db.query(Usage).filter(Usage.api_key_id == api_key_obj.id).all()
    assert len(usages) == 1
    assert usages[0].fmu_id == "msl:BouncingBall"
    assert usages[0].duration_ms > 0
    db.close()
