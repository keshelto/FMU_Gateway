"""Authentication helpers for issuing and validating JWT tokens."""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from typing import Optional

import jwt
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import APIKey, User


class AuthService:
    """Provide JWT issuance and API key validation."""

    def __init__(self) -> None:
        settings = get_settings()
        self.jwt_secret = settings.jwt_secret
        self.jwt_cookie_name = settings.jwt_cookie_name
        self.jwt_cookie_secure = settings.jwt_cookie_secure

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
        api_key_obj = (
            session.query(APIKey)
            .filter(APIKey.key == api_key, APIKey.is_active.is_(True))
            .one_or_none()
        )
        if api_key_obj:
            return api_key_obj.user

        # Fallback for legacy keys stored directly on the user model.
        return session.query(User).filter(User.api_key == api_key).one_or_none()

    def get_user(self, session: Session, user_id: str) -> Optional[User]:
        """Fetch a user by identifier."""
        return session.query(User).filter(User.id == user_id).one_or_none()

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using a salted SHA-256 digest."""
        salt = secrets.token_hex(16)
        digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def verify_password(password: str, hashed: str | None) -> bool:
        """Validate a password against a salted digest."""
        if not hashed or "$" not in hashed:
            return False
        salt, stored_digest = hashed.split("$", 1)
        digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return secrets.compare_digest(digest, stored_digest)

    def authenticate_credentials(
        self, session: Session, *, email: str, password: str
    ) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = session.query(User).filter(User.email == email).one_or_none()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def create_api_key(session: Session, user: User, label: str | None = None) -> APIKey:
        """Generate and persist a new API key for a user."""
        key_value = secrets.token_hex(32)
        api_key = APIKey(user_id=user.id, key=key_value, label=label)
        session.add(api_key)
        session.flush()
        return api_key
