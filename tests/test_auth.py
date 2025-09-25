import pytest

def test_create_key(client):
    resp = client.post("/keys")
    assert resp.status_code == 200
    key_data = resp.json()
    assert "key" in key_data
    assert len(key_data["key"]) == 36  # uuid

def test_protected_endpoint_without_auth(client):
    resp = client.get("/library")
    assert resp.status_code == 401

def test_protected_with_valid_key(client):
    resp = client.post("/keys")
    key = resp.json()["key"]
    resp = client.get("/library", headers={"Authorization": f"Bearer {key}"})
    assert resp.status_code == 200

def test_invalid_key(client):
    resp = client.post("/keys")
    key = resp.json()["key"]
    invalid_key = key + "invalid"
    resp = client.get("/library", headers={"Authorization": f"Bearer {invalid_key}"})
    assert resp.status_code == 401
