"""Marketplace ORM models for the Certified FMU Registry."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .entities import Base


class ValidationStatus(str, Enum):
    """Lifecycle state for automated validation runs."""

    PENDING = "pending"
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class SKUType(str, Enum):
    """Available SKU types for monetising FMUs."""

    DOWNLOAD = "download"
    EXECUTE_ONLY = "execute_only"
    SEAT = "seat"
    ORG = "org"


class PurchaseStatus(str, Enum):
    """Track payment outcomes and lifecycle transitions."""

    PENDING = "pending"
    ACTIVE = "active"
    REFUNDED = "refunded"


class LicenseScope(str, Enum):
    """Permitted usage scope for a granted license."""

    PERSONAL = "personal"
    COMMERCIAL = "commercial"
    ORG = "org"


class Creator(Base):
    """Registered marketplace creator that can publish FMUs."""

    __tablename__ = "creators"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    stripe_connect_id = Column(String(255), nullable=True, index=True)
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="creator_profile")
    packages = relationship("FMUPackage", back_populates="creator", cascade="all, delete-orphan")


class FMUPackage(Base):
    """Metadata describing an FMU product listed in the marketplace."""

    __tablename__ = "fmu_packages"

    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey("creators.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    short_desc = Column(String(255), nullable=False)
    long_desc = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    category = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_listed = Column(Boolean, default=False, nullable=False)
    is_certified = Column(Boolean, default=False, nullable=False)
    rating_avg = Column(Integer, default=0, nullable=False)
    rating_count = Column(Integer, default=0, nullable=False)

    creator = relationship("Creator", back_populates="packages")
    versions = relationship("FMUVersion", back_populates="package", cascade="all, delete-orphan")
    listings = relationship("Listing", back_populates="package", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="package")
    ratings = relationship("Rating", back_populates="package", cascade="all, delete-orphan")


class FMUVersion(Base):
    """Concrete binary uploaded by the creator."""

    __tablename__ = "fmu_versions"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("fmu_packages.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    semver = Column(String(32), nullable=False)
    file_key = Column(String(512), nullable=False)
    file_sha256 = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    metadata_json = Column(JSON, default=dict)
    validated_at = Column(DateTime, nullable=True)
    validation_status = Column(SQLEnum(ValidationStatus), default=ValidationStatus.PENDING, nullable=False)
    min_gateway_version = Column(String(32), nullable=True)
    changelog = Column(Text, nullable=True)
    signature_hex = Column(String(512), nullable=True)

    package = relationship("FMUPackage", back_populates="versions")
    validation_jobs = relationship(
        "ValidationJob",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="ValidationJob.started_at.desc()",
    )
    purchases = relationship("Purchase", back_populates="version")
    licenses = relationship("License", back_populates="version")


class Listing(Base):
    """Commercial offering for a package (download vs execute only, etc.)."""

    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("fmu_packages.id"), nullable=False, index=True)
    sku = Column(String(64), nullable=False, unique=True)
    sku_type = Column(SQLEnum(SKUType), nullable=False)
    price_cents = Column(Integer, nullable=False)
    currency = Column(String(8), default="usd", nullable=False)
    license_template_id = Column(String(64), nullable=False)
    revenue_share_bps = Column(Integer, default=8500, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    package = relationship("FMUPackage", back_populates="listings")
    purchases = relationship("Purchase", back_populates="listing")


class Purchase(Base):
    """Record of a buyer purchasing access to a package version."""

    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    buyer_user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("fmu_packages.id"), nullable=False)
    version_id = Column(Integer, ForeignKey("fmu_versions.id"), nullable=False)
    stripe_payment_id = Column(String(255), nullable=True, index=True)
    license_key = Column(String(128), nullable=False)
    license_key_salt = Column(String(64), nullable=False)
    license_terms_snapshot = Column(Text, nullable=False)
    status = Column(SQLEnum(PurchaseStatus), default=PurchaseStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    buyer = relationship("User", back_populates="purchases")
    listing = relationship("Listing", back_populates="purchases")
    package = relationship("FMUPackage", back_populates="purchases")
    version = relationship("FMUVersion", back_populates="purchases")
    license = relationship("License", back_populates="purchase", uselist=False, cascade="all, delete-orphan")


class License(Base):
    """Issued license granting usage rights to a buyer."""

    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False, unique=True)
    buyer_user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey("fmu_packages.id"), nullable=False)
    version_id = Column(Integer, ForeignKey("fmu_versions.id"), nullable=False)
    scope = Column(SQLEnum(LicenseScope), nullable=False, default=LicenseScope.PERSONAL)
    seats = Column(Integer, default=1, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)

    purchase = relationship("Purchase", back_populates="license")
    buyer = relationship("User", back_populates="licenses")
    version = relationship("FMUVersion", back_populates="licenses")
    package = relationship("FMUPackage")
    entitlements = relationship(
        "ExecutionEntitlement",
        back_populates="license",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ExecutionEntitlement(Base):
    """Track how many executions remain for execute-only SKUs."""

    __tablename__ = "execution_entitlements"

    id = Column(Integer, primary_key=True)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False, unique=True)
    runs_remaining = Column(Integer, default=0, nullable=False)
    resets_cron = Column(String(64), nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)

    license = relationship("License", back_populates="entitlements")


class Rating(Base):
    """Buyer supplied review data."""

    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("fmu_packages.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    stars = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    package = relationship("FMUPackage", back_populates="ratings")
    user = relationship("User", back_populates="ratings")


class ValidationJob(Base):
    """Asynchronous validation task for an FMU upload."""

    __tablename__ = "validation_jobs"

    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey("fmu_versions.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default=ValidationStatus.PENDING.value)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    report_key = Column(String(512), nullable=True)
    issues_json = Column(JSON, default=list)

    version = relationship("FMUVersion", back_populates="validation_jobs")


class WebhookDelivery(Base):
    """Store webhook payloads and retry metadata."""

    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True)
    event = Column(String(128), nullable=False)
    payload_json = Column(JSON, default=dict)
    delivered_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="pending", nullable=False)


class DMCATakedown(Base):
    """DMCA complaints and resolution tracking."""

    __tablename__ = "dmca_takedowns"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("fmu_packages.id"), nullable=False, index=True)
    status = Column(String(32), default="pending", nullable=False)
    complainant_email = Column(String(255), nullable=False)
    claim_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    package = relationship("FMUPackage")


class AuditLog(Base):
    """Immutable audit entries for sensitive actions."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(128), nullable=False)
    entity = Column(String(128), nullable=False)
    entity_id = Column(String(64), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    details_json = Column(JSON, default=dict)

    actor = relationship("User")

