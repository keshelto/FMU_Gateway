"""Example script showing a creator workflow using the private API."""
from __future__ import annotations

import json
import sys

import httpx

BASE_URL = "http://localhost:8000"


def main() -> int:
    token = sys.argv[1] if len(sys.argv) > 1 else ""
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    with httpx.Client(base_url=BASE_URL) as client:
        response = client.post(
            "/creator/apply",
            json={"display_name": "Demo Creator"},
            headers=headers,
        )
        response.raise_for_status()
        creator = response.json()
        print("Creator profile:", json.dumps(creator, indent=2))

        package_payload = {
            "name": "Electric Motor FMU",
            "short_desc": "High fidelity EV motor model",
            "long_desc": "Detailed model including thermal limits and torque curves.",
            "tags": ["ev", "motor", "thermal"],
            "category": "powertrain",
        }
        response = client.post("/creator/packages", json=package_payload, headers=headers)
        response.raise_for_status()
        package = response.json()
        print("Package created:", json.dumps(package, indent=2))

    print("Upload and listing steps require interactive file submission and are omitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

