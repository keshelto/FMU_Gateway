"""Data model representing users of the FMU Gateway."""
from __future__ import annotations

from pydantic import BaseModel


class User(BaseModel):
    """Minimal user model with billing and authentication context."""

    id: str
    email: str
    api_key: str
    credits: int
