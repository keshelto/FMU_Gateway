"""SQLAlchemy models used by the private API."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    """Persisted user with billing metadata and API credentials."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    api_key = Column(String(36), unique=True, nullable=False, index=True)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    credits = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")


class UsageLog(Base):
    """Track FMU execution events for auditing and billing."""

    __tablename__ = "usage_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    fmu_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    credits_used = Column(Integer, nullable=False, default=1)

    user = relationship("User", back_populates="usage_logs")
