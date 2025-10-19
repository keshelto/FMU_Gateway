"""Billing routes and helpers for monetization."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import AuditLog, FMUVersion, LicenseScope, Listing, Purchase, PurchaseStatus, User
from ..services.auth_service import AuthService
from ..services.billing_service import BillingService
from ..services.marketplace_service import marketplace_service
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
        listing_id = metadata.get("marketplace_listing_id")
        if listing_id:
            buyer_id = metadata.get("buyer_user_id")
            version_id = metadata.get("marketplace_version_id")
            scope_name = metadata.get("license_scope", LicenseScope.PERSONAL.value)
            seats = int(metadata.get("seats", 1))
            runs = int(metadata.get("execute_runs", 0))

            buyer = session.query(User).filter(User.id == buyer_id).one_or_none()
            listing = session.query(Listing).filter(Listing.id == int(listing_id)).one_or_none()
            if version_id:
                version = (
                    session.query(FMUVersion)
                    .filter(FMUVersion.id == int(version_id))
                    .one_or_none()
                )
            else:
                version = (
                    session.query(FMUVersion)
                    .filter(FMUVersion.package_id == listing.package_id)
                    .order_by(FMUVersion.id.desc())
                    .first()
                )
            if not buyer or not listing or not version:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase metadata invalid")

            marketplace_service.finalize_purchase(
                session,
                buyer=buyer,
                listing=listing,
                version=version,
                stripe_payment_id=event["data"]["object"].get("id", ""),
                scope=LicenseScope(scope_name),
                seats=seats,
                execute_runs=runs,
            )
            logger.info("Marketplace license issued", extra={"buyer": buyer.id, "listing": listing.id})
        else:
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

    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        payment_id = charge.get("payment_intent") or charge.get("id")
        purchase = (
            session.query(Purchase)
            .filter(Purchase.stripe_payment_id == payment_id)
            .one_or_none()
        )
        if purchase:
            purchase.status = PurchaseStatus.REFUNDED
            if purchase.license:
                marketplace_service.revoke_license(session, purchase.license)

    elif event["type"] == "payout.paid":
        payout = event["data"]["object"]
        session.add(
            AuditLog(
                actor_user_id=None,
                action="payout_paid",
                entity="stripe_payout",
                entity_id=str(payout.get("id")),
                details_json={"amount": payout.get("amount")},
            )
        )

    return {"status": "processed"}
