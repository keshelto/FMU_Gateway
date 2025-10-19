"""Client for interacting with the FMU Gateway backend API."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .auth import APIKeyAuth
from .utils import read_binary_file


class FMUGatewayClient:
    """Simple synchronous client for executing FMUs via the FMU Gateway backend."""

    def __init__(self, api_key: str, base_url: str = "https://api.fmu-gateway.com") -> None:
        """Store authentication context and default endpoint."""
        self.base_url = base_url.rstrip("/")
        self.auth = APIKeyAuth(api_key)

    def execute_fmu(
        self,
        fmu_path: str | Path,
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upload an FMU file and trigger execution on the backend."""
        target = f"{self.base_url}/execute_fmu"
        payload = {
            "parameters": parameters or {},
            "metadata": metadata or {},
        }

        files = {
            "fmu": (Path(fmu_path).name, read_binary_file(fmu_path), "application/octet-stream"),
            "payload": (None, json.dumps(payload), "application/json"),
        }

        headers = self.auth.build_headers()
        response = requests.post(target, files=files, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()

    def get_usage(self) -> Dict[str, Any]:
        """Retrieve credit usage information for the authenticated user."""
        target = f"{self.base_url}/usage"
        headers = self.auth.build_headers()
        response = requests.get(target, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def register_webhook(self, url: str) -> Dict[str, Any]:
        """Register a billing webhook for Stripe event forwarding."""
        target = f"{self.base_url}/billing/webhook"
        headers = self.auth.build_headers()
        response = requests.post(target, json={"url": url}, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
