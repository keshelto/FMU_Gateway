"""Configuration settings for the FMU Gateway private API."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict


class Settings:
    """Read environment variables for services and secrets."""

    def __init__(self) -> None:
        self.stripe_secret_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_placeholder")
        self.stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.jwt_secret = os.getenv("JWT_SECRET", "development-secret")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./fmu_gateway.db")
        self.public_billing_portal = os.getenv(
            "PUBLIC_BILLING_PORTAL", "https://fmu-gateway.ai/billing"
        )
        self.free_tier_credits = int(os.getenv("FREE_TIER_CREDITS", "25"))
        self.jwt_cookie_name = os.getenv("JWT_COOKIE_NAME", "fmu_session")
        self.jwt_cookie_secure = os.getenv("JWT_COOKIE_SECURE", "false").lower() == "true"
        self.csrf_cookie_name = os.getenv("CSRF_COOKIE_NAME", "fmu_csrf")
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

        self.pricing: Dict[str, Dict[str, int | str]] = {
            "pro": {
                "credits": int(os.getenv("PRICING_PRO_CREDITS", "120")),
                "amount_cents": int(os.getenv("PRICING_PRO_AMOUNT_CENTS", "4900")),
                "description": "Pro plan",
            },
            "enterprise": {
                "credits": int(os.getenv("PRICING_ENTERPRISE_CREDITS", "600")),
                "amount_cents": int(os.getenv("PRICING_ENTERPRISE_AMOUNT_CENTS", "19900")),
                "description": "Enterprise plan",
            },
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
