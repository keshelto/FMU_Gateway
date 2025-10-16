import pytest

from tests.payment_utils import purchase_token


def test_402_unpaid(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key = resp.json()["key"]
    assert len(stripe_stub.records) == baseline + 1

    before = len(stripe_stub.records)

    resp = client.post(
        "/simulate",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "fmu_id": "msl:BouncingBall",
            "stop_time": 1.0,
            "step": 0.01,
        },
    )
    assert resp.status_code == 402
    body = resp.json()
    assert body["amount"] == pytest.approx(1.0)
    assert body["methods"] == ["stripe_checkout"]
    assert body["session_id"].startswith("cs_test")
    assert body["checkout_url"].startswith("https://")

    after = len(stripe_stub.records)
    new_records = stripe_stub.records[before:after]
    assert any(entry["path"] == "/v1/checkout/sessions" for entry in new_records)


def test_paid_simulation(client, stripe_stub):
    baseline = len(stripe_stub.records)
    resp = client.post("/keys")
    key = resp.json()["key"]
    assert len(stripe_stub.records) == baseline + 1

    simulate_payload = {
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01,
    }

    before = len(stripe_stub.records)
    token, checkout_body = purchase_token(client, key, simulate_payload)
    session_id = checkout_body["session_id"]
    assert session_id.startswith("cs_test")

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
    body = resp.json()
    assert body["status"] == "ok"

    # No additional Stripe payment intent calls should be made during execution
    final_records = stripe_stub.records[before:]
    assert not any(entry["path"] == "/v1/payment_intents" for entry in final_records)
