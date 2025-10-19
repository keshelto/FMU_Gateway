"""Billing routes and helpers for monetization."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import User
from ..services.auth_service import AuthService
from ..services.billing_service import BillingService
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)

router = APIRouter()

settings = get_settings()
stripe_service = StripeService()
auth_service = AuthService()
billing_service = BillingService()


class PurchaseRequest(BaseModel):
    api_key: str
    plan: str


@router.post("/purchase")
def purchase(
    payload: PurchaseRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Initiate a Stripe checkout session for purchasing credits."""
    user = auth_service.authenticate_api_key(session, payload.api_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    plan_name = payload.plan
    plan_details = settings.pricing.get(plan_name)
    if not plan_details:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

    metadata = {
        "user_id": user.id,
        "plan": plan_name,
        "success_url": f"{settings.public_billing_portal}/success",
        "cancel_url": f"{settings.public_billing_portal}/cancel",
    }

    checkout = stripe_service.create_checkout_session(
        customer_id=user.stripe_customer_id,
        plan=plan_name,
        amount_cents=int(plan_details["amount_cents"]),
        description=str(plan_details["description"]),
        metadata=metadata,
    )

    return {"checkout_url": checkout["url"], "session_id": checkout["id"]}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, session: Session = Depends(get_session)) -> dict:
    """Process Stripe webhook events and update credit balances."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    event = stripe_service.parse_event(payload, signature)

    if event["type"] == "checkout.session.completed":
        metadata = event["data"]["object"].get("metadata", {})
        user_id = metadata.get("user_id")
        plan = metadata.get("plan")
        if not user_id or not plan:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing metadata")

        plan_details = settings.pricing.get(plan)
        if not plan_details:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

        user = session.query(User).filter(User.id == user_id).one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        billing_service.add_credits(session, user, int(plan_details["credits"]))
        logger.info(
            "Credits added",
            extra={"user_id": user.id, "credits": plan_details["credits"], "plan": plan},
        )

    return {"status": "processed"}
