import pytest

def test_get_library(client):
    # First, create key
    resp = client.post("/keys")
    assert resp.status_code == 200
    key_data = resp.json()
    key = key_data["key"]

    # Get library without auth
    resp = client.get("/library")
    assert resp.status_code == 401

    # With auth
    resp = client.get("/library", headers={"Authorization": f"Bearer {key}"})
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) > 0
    assert "BouncingBall" in str(models)

def test_library_search(client):
    resp = client.post("/keys")
    key = resp.json()["key"]

    resp = client.get("/library", headers={"Authorization": f"Bearer {key}"}, params={"query": "Bouncing"})
    assert resp.status_code == 200
    models = resp.json()
    assert any("Bouncing" in m["model_name"] for m in models)
