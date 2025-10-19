"""Test the payments and credit pipeline."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Tuple

import pytest
from fastapi.testclient import TestClient


def _load_private_api(tmp_path: Path) -> Tuple[TestClient, object]:
    base_dir = Path(__file__).resolve().parents[1] / "private-api" / "app"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'payments.db'}"
    os.environ["STRIPE_SECRET_KEY"] = "sk_test"
    os.environ["STRIPE_WEBHOOK_SECRET"] = ""
    os.environ["JWT_SECRET"] = "unit-test-secret"

    if "jwt" not in sys.modules:
        import types

        jwt_stub = types.SimpleNamespace(
            encode=lambda payload, secret, algorithm: f"token-{payload['sub']}",
            decode=lambda token, secret, algorithms: {"sub": token.removeprefix("token-")},
        )
        sys.modules["jwt"] = jwt_stub

    spec = importlib.util.spec_from_file_location("private_api_app", base_dir / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["private_api_app"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    app = module.create_app()
    client = TestClient(app)
    return client, module


@pytest.fixture()
def private_api(tmp_path: Path):
    client, module = _load_private_api(tmp_path)
    try:
        yield client, module
    finally:
        sys.modules.pop("private_api_app", None)
        sys.modules.pop("private_api_app.routes.auth", None)
        sys.modules.pop("private_api_app.routes.billing", None)
        if sys.modules.get("jwt", None) and sys.modules["jwt"].__class__.__name__ == "SimpleNamespace":
            sys.modules.pop("jwt", None)


def test_credit_purchase_and_execution(monkeypatch: pytest.MonkeyPatch, private_api):
    client, module = private_api

    auth_module = sys.modules["private_api_app.routes.auth"]
    billing_module = sys.modules["private_api_app.routes.billing"]

    monkeypatch.setattr(auth_module.stripe_service, "create_customer", lambda email, name: "cus_123")

    def fake_checkout(**kwargs):
        return {"id": "cs_123", "url": "https://checkout.stripe.com/pay/cs_123"}

    monkeypatch.setattr(billing_module.stripe_service, "create_checkout_session", fake_checkout)

    def fake_event(payload: bytes, signature: str | None):
        body = json.loads(payload.decode("utf-8"))
        return {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": body["metadata"]}},
        }

    monkeypatch.setattr(billing_module.stripe_service, "parse_event", fake_event)

    register_resp = client.post("/register", json={"email": "tester@example.com", "name": "Tester"})
    assert register_resp.status_code == 201
    data = register_resp.json()
    api_key = data["api_key"]

    login_resp = client.post("/login", json={"api_key": api_key})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]

    purchase_resp = client.post("/purchase", json={"api_key": api_key, "plan": "pro"})
    assert purchase_resp.status_code == 200
    assert "checkout_url" in purchase_resp.json()

    webhook_payload = {
        "metadata": {"user_id": data["user_id"], "plan": "pro"},
    }
    webhook_resp = client.post("/stripe/webhook", json=webhook_payload)
    assert webhook_resp.status_code == 200

    files = {
        "fmu": ("model.fmu", b"0" * 10, "application/octet-stream"),
    }
    payload = {
        "payload": (None, json.dumps({"parameters": {}, "metadata": {"credit_cost": 1}}), "application/json"),
    }
    execute_resp = client.post(
        "/execute_fmu",
        files={**files, **payload},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert execute_resp.status_code == 200
    body = execute_resp.json()
    assert body["status"] == "succeeded"
