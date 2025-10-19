"""Authentication helpers for the FMU Gateway SDK."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class APIKeyAuth:
    """Store an API key and generate headers for authenticated requests."""

    api_key: str

    def build_headers(self) -> Dict[str, str]:
        """Return headers required by the backend for API key authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "fmu-gateway-sdk/0.1.0",
        }
