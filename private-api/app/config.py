"""Configuration settings for the FMU Gateway private API."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


class Settings:
    """Read environment variables for services and secrets."""

    stripe_key: str
    jwt_secret: str
    s3_bucket_url: str

    def __init__(self) -> None:
        self.stripe_key = os.getenv("STRIPE_KEY", "test-stripe-key")
        self.jwt_secret = os.getenv("JWT_SECRET", "development-secret")
        self.s3_bucket_url = os.getenv("S3_BUCKET_URL", "https://s3.amazonaws.com/fmu-gateway")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
