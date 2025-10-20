"""SQLAlchemy models used by the private API."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    """Persisted user with billing metadata and API credentials."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    api_key = Column(String(36), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    credits = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    creator_profile = relationship(
        "Creator",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    purchases = relationship(
        "Purchase",
        back_populates="buyer",
        cascade="all, delete-orphan",
    )
    ratings = relationship(
        "Rating",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    licenses = relationship(
        "License",
        back_populates="buyer",
        cascade="all, delete-orphan",
    )

    @property
    def user_id(self) -> str:
        """Expose a stable attribute for compatibility with older Pydantic."""

        return self.id


class APIKey(Base):
    """User-managed API keys for accessing the FMU Gateway."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="api_keys")
    usage_logs = relationship("UsageLog", back_populates="api_key")


class UsageLog(Base):
    """Track FMU execution events for auditing and billing."""

    __tablename__ = "usage_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    fmu_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    credits_used = Column(Integer, nullable=False, default=1)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True, index=True)

    user = relationship("User", back_populates="usage_logs")
    api_key = relationship("APIKey", back_populates="usage_logs")
