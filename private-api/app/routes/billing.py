"""Billing routes and helpers for monetization."""
from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Request

from ..models.user import User
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory user store keyed by API key for demonstration purposes.
USER_STORE: Dict[str, User] = {
    "demo-key": User(id="user_123", email="demo@example.com", api_key="demo-key", credits=1000),
}

stripe_service = StripeService()


def get_user_by_api_key(api_key: str) -> User | None:
    """Return the user associated with the provided API key."""
    return USER_STORE.get(api_key)


def decrement_user_credits(user: User, amount: int) -> int:
    """Decrement credits for the given user and return the remaining total."""
    if user.credits < amount:
        raise HTTPException(status_code=402, detail="Insufficient credits for execution")
    user.credits -= amount
    USER_STORE[user.api_key] = user
    logger.info("Credits decremented", extra={"user_id": user.id, "remaining": user.credits})
    return user.credits


@router.get("/usage")
def usage() -> Dict[str, Dict[str, int]]:
    """Return usage metrics for all users (placeholder for demo)."""
    return {user_id: {"credits": user.credits} for user_id, user in ((u.id, u) for u in USER_STORE.values())}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request) -> Dict[str, str]:
    """Receive Stripe webhooks and forward payload to the Stripe service handler."""
    payload = await request.json()
    stripe_service.handle_webhook(payload)
    return {"status": "received"}
