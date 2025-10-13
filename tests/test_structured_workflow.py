import math


def _structured_payload(preload_scale: float) -> dict:
    drive_cycle = [
        {
            "time": 0.0,
            "engine_speed_rpm": 1500.0,
            "cam_torque": 60.0,
            "oil_temperature": 90.0,
            "oil_viscosity": 20.0,
        },
        {
            "time": 0.5,
            "engine_speed_rpm": 2200.0,
            "cam_torque": 120.0,
            "oil_temperature": 100.0,
            "oil_viscosity": 18.0,
        },
        {
            "time": 1.0,
            "engine_speed_rpm": 1800.0,
            "cam_torque": 80.0,
            "oil_temperature": 110.0,
            "oil_viscosity": 16.0,
        },
    ]

    parameters = {
        "friction": {
            "mu_lubricated": 0.12,
            "mu_viscous": 0.0008,
            "mu_temperature_slope": -0.25,
            "mu_temperature_quadratic": 0.02,
            "mu_boundary": 0.38,
            "stribeck_velocity": 0.5,
            "preload_scale": preload_scale,
            "h_oil": 5.0,
        },
    }

    return {
        "fmu_id": "structured:flexible_compound_gear",
        "stop_time": 1.0,
        "step": 0.05,
        "parameters": parameters,
        "drive_cycle": drive_cycle,
    }


def test_structured_simulation_returns_summary(client):
    key = client.post("/keys").json()["key"]

    payload = _structured_payload(preload_scale=1.0)
    resp = client.post(
        "/simulate",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "ok"
    assert "final_wear_depth" in result["key_results"]

    summary_resp = client.get(
        result["summary_url"],
        headers={"Authorization": f"Bearer {key}"},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["parameters"]["friction"]["preload_scale"] == 1.0
    assert len(summary["drive_cycle"]) == 3
    assert len(summary["history"].get("time", [])) == 3


def test_structured_parameters_change_results(client):
    key = client.post("/keys").json()["key"]

    first = client.post(
        "/simulate",
        headers={"Authorization": f"Bearer {key}"},
        json=_structured_payload(preload_scale=0.8),
    ).json()
    second = client.post(
        "/simulate",
        headers={"Authorization": f"Bearer {key}"},
        json=_structured_payload(preload_scale=1.4),
    ).json()

    wear_a = first["key_results"]["final_wear_depth"]
    wear_b = second["key_results"]["final_wear_depth"]
    assert not math.isclose(wear_a, wear_b)


def test_parameter_sweep_generates_chart(client):
    key = client.post("/keys").json()["key"]

    sweep_payload = {
        "base_request": _structured_payload(preload_scale=1.0),
        "parameters": [
            {
                "path": "parameters.friction.preload_scale",
                "values": [0.8, 1.0, 1.2],
            }
        ],
        "post_processing": ["load_vs_wear"],
    }

    resp = client.post(
        "/sweep",
        headers={"Authorization": f"Bearer {key}"},
        json=sweep_payload,
    )
    assert resp.status_code == 200
    sweep_start = resp.json()
    assert sweep_start["status"] == "pending"

    result_resp = client.get(
        sweep_start["results_url"],
        headers={"Authorization": f"Bearer {key}"},
    )
    assert result_resp.status_code == 200
    sweep = result_resp.json()
    assert sweep["status"] == "complete"
    assert len(sweep["points"]) == 3
    assert "load_vs_wear" in sweep["charts"]
    assert sweep["charts"]["load_vs_wear"]
