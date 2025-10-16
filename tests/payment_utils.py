from __future__ import annotations

from typing import Dict, Tuple

from app import db as db_module


def _get_api_key_id(key: str) -> int:
    with db_module.SessionLocal() as session:
        record = session.query(db_module.ApiKey).filter(db_module.ApiKey.key == key).first()
        if record is None:
            raise RuntimeError("API key not found")
        return record.id


def complete_checkout(client, key: str, session_id: str, fmu_id: str) -> str:
    api_key_id = _get_api_key_id(key)
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "metadata": {"api_key_id": str(api_key_id), "fmu_id": fmu_id},
                "amount_total": 100,
                "currency": "usd",
                "url": f"https://checkout.stripe.com/pay/{session_id}",
            }
        },
    }
    resp = client.post("/webhooks/stripe", json=event)
    if resp.status_code != 200:
        raise RuntimeError(f"Webhook failed: {resp.status_code} {resp.text}")

    token_resp = client.get(
        f"/payments/checkout/{session_id}",
        headers={"Authorization": f"Bearer {key}"},
    )
    if token_resp.status_code != 200:
        raise RuntimeError(f"Token retrieval failed: {token_resp.status_code} {token_resp.text}")
    payload = token_resp.json()
    return payload["payment_token"]


def purchase_token(client, key: str, simulate_payload: Dict) -> Tuple[str, Dict]:
    resp = client.post(
        "/simulate",
        headers={"Authorization": f"Bearer {key}"},
        json=simulate_payload,
    )
    if resp.status_code != 402:
        raise RuntimeError("Expected payment required response")
    body = resp.json()
    token = complete_checkout(client, key, body["session_id"], simulate_payload["fmu_id"])
    return token, body
