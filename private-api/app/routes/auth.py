"""Authentication and registration routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import User
from ..models.user import LoginRequest, UserCreate, UserResponse
from ..services.auth_service import AuthService
from ..services.billing_service import BillingService
from ..services.stripe_service import StripeService


router = APIRouter()

auth_service = AuthService()
stripe_service = StripeService()
billing_service = BillingService()
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: Session = Depends(get_session)) -> UserResponse:
    """Create a user, Stripe customer, and API key."""
    existing = session.query(User).filter(User.email == payload.email).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    customer_id = stripe_service.create_customer(payload.email, payload.name)

    user = User(
        id=str(uuid.uuid4()),
        email=payload.email,
        name=payload.name,
        api_key=str(uuid.uuid4()),
        stripe_customer_id=customer_id,
        credits=settings.free_tier_credits,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    billing_service.log_usage(session, user, "registration_bonus", 0)

    return UserResponse.from_orm(user)


@router.post("/login")
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> dict:
    """Issue a JWT when an API key is provided."""
    user = auth_service.authenticate_api_key(session, payload.api_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    token = auth_service.issue_token(user.id)
    return {"token": token, "user_id": user.id, "credits": user.credits}
