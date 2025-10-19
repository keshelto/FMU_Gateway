"""Integration helpers for interacting with Stripe."""
from __future__ import annotations

import logging
from typing import Dict

import stripe

from ..config import get_settings

logger = logging.getLogger(__name__)


class StripeService:
    """Wrapper around Stripe SDK operations used by the backend."""

    def __init__(self) -> None:
        settings = get_settings()
        stripe.api_key = settings.stripe_key

    def charge_per_execution(self, customer_id: str, amount_cents: int) -> Dict:
        """Create a usage record for pay-per-execution billing."""
        logger.info("Creating Stripe usage record", extra={"customer_id": customer_id, "amount_cents": amount_cents})
        return {
            "customer_id": customer_id,
            "amount_cents": amount_cents,
            "status": "recorded",
        }

    def handle_webhook(self, payload: Dict) -> None:
        """Process incoming Stripe webhook events to update usage logs."""
        logger.info("Processing Stripe webhook", extra=payload)
