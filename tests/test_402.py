import pytest

def test_402_unpaid(client):
    resp = client.post("/keys")
    key = resp.json()["key"]
    
    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01
    })
    assert resp.status_code == 402
    assert resp.json()["amount"] == 0.01
    assert "google_pay" in resp.json()["methods"]

def test_paid_simulation(client, monkeypatch):
    resp = client.post("/keys")
    key = resp.json()["key"]
    
    # Mock Stripe success
    mock_stripe = Mock()
    mock_stripe.PaymentIntent.create.return_value = Mock(id="pi_success")
    monkeypatch.setattr('app.main.stripe', mock_stripe)
    
    resp = client.post("/simulate", headers={"Authorization": f"Bearer {key}"}, json={
        "fmu_id": "msl:BouncingBall",
        "stop_time": 1.0,
        "step": 0.01,
        "payment_token": "tok_mock",
        "payment_method": "google_pay"
    })
    assert resp.status_code == 200
    assert mock_stripe.PaymentIntent.create.called
