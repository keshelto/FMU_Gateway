"""Helpers for managing credit balances."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import UsageLog, User


class BillingService:
    """Utility functions to modify credit balances."""

    def add_credits(self, session: Session, user: User, amount: int) -> User:
        user.credits += amount
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    def deduct_credits(self, session: Session, user: User, amount: int) -> User:
        if user.credits < amount:
            raise ValueError("Insufficient credits")
        user.credits -= amount
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    def log_usage(self, session: Session, user: User, fmu_name: str, credits_used: int) -> UsageLog:
        log = UsageLog(user_id=user.id, fmu_name=fmu_name, credits_used=credits_used)
        session.add(log)
        session.commit()
        session.refresh(log)
        return log
