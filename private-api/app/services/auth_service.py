"""Authentication helpers for issuing and validating JWT tokens."""
from __future__ import annotations

import datetime as dt
from typing import Dict

import jwt

from ..config import get_settings


class AuthService:
    """Provide JWT issuance for the private API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.jwt_secret = settings.jwt_secret

    def issue_token(self, user_id: str, expires_minutes: int = 60) -> str:
        """Create a signed JWT for a user."""
        payload = {
            "sub": user_id,
            "exp": dt.datetime.utcnow() + dt.timedelta(minutes=expires_minutes),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_token(self, token: str) -> Dict:
        """Decode the JWT and return the payload."""
        return jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
