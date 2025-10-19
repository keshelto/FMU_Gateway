"""Integration helpers for interacting with Stripe."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

import stripe

from ..config import get_settings

logger = logging.getLogger(__name__)


class StripeService:
    """Wrapper around Stripe SDK operations used by the backend."""

    def __init__(self) -> None:
        self.settings = get_settings()
        stripe.api_key = self.settings.stripe_secret_key

    def create_customer(self, email: str, name: str | None) -> str:
        """Create a Stripe customer and return the customer ID."""
        customer = stripe.Customer.create(email=email, name=name)
        return customer["id"]

    def create_checkout_session(
        self,
        customer_id: str,
        plan: str,
        amount_cents: int,
        description: str,
        metadata: Dict[str, str],
    ) -> Dict[str, Any]:
        """Create a checkout session for purchasing credits."""
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="payment",
            metadata=metadata,
            success_url=metadata.get("success_url") or "https://fmu-gateway.ai/success",
            cancel_url=metadata.get("cancel_url") or "https://fmu-gateway.ai/cancel",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": description},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
        )
        return {"id": session["id"], "url": session["url"]}

    def parse_event(self, payload: bytes, signature: str | None) -> stripe.Event:
        """Validate and decode a Stripe webhook event."""
        webhook_secret = self.settings.stripe_webhook_secret
        if webhook_secret:
            return stripe.Webhook.construct_event(payload, signature or "", webhook_secret)
        return stripe.Event.construct_from(json.loads(payload.decode("utf-8")), stripe.api_key)
