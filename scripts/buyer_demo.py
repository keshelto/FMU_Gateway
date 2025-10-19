"""Example buyer workflow interacting with the Certified FMU Registry."""
from __future__ import annotations

import json
import sys

import httpx

BASE_URL = "http://localhost:8000"


def main() -> int:
    token = sys.argv[1] if len(sys.argv) > 1 else ""
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    with httpx.Client(base_url=BASE_URL) as client:
        results = client.get("/registry/search", params={"certified_only": True})
        results.raise_for_status()
        print("Search results:", json.dumps(results.json(), indent=2))

        licenses = client.get("/registry/licenses", headers=headers)
        licenses.raise_for_status()
        print("Existing licenses:", json.dumps(licenses.json(), indent=2))

    print("Purchasing and executing require real Stripe callbacks and are omitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

