"""Authentication helpers for issuing and validating JWT tokens."""
from __future__ import annotations

import datetime as dt
from typing import Optional

import jwt
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import User


class AuthService:
    """Provide JWT issuance and API key validation."""

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

    def verify_token(self, token: str) -> dict:
        """Decode the JWT and return the payload."""
        return jwt.decode(token, self.jwt_secret, algorithms=["HS256"])

    def authenticate_api_key(self, session: Session, api_key: str) -> Optional[User]:
        """Return the user matching the provided API key."""
        return session.query(User).filter(User.api_key == api_key).one_or_none()

    def get_user(self, session: Session, user_id: str) -> Optional[User]:
        """Fetch a user by identifier."""
        return session.query(User).filter(User.id == user_id).one_or_none()
