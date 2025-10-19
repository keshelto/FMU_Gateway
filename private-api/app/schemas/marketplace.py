"""Pydantic schemas for marketplace endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from ..models import LicenseScope, SKUType, ValidationStatus


class CreatorApplyRequest(BaseModel):
    display_name: str = Field(..., min_length=3, max_length=255)


class CreatorResponse(BaseModel):
    id: int
    display_name: str
    stripe_connect_id: str | None = None

    class Config:
        from_attributes = True


class PackageCreateRequest(BaseModel):
    name: str
    short_desc: str
    long_desc: str
    tags: List[str] = Field(default_factory=list)
    category: str | None = None


class PackageResponse(BaseModel):
    id: int
    name: str
    short_desc: str
    long_desc: str
    tags: List[str]
    category: str | None
    is_listed: bool
    is_certified: bool

    class Config:
        from_attributes = True


class VersionUploadResponse(BaseModel):
    id: int
    semver: str
    validation_status: ValidationStatus
    file_key: str
    file_sha256: str
    signature_hex: str | None

    class Config:
        from_attributes = True


class ListingCreateRequest(BaseModel):
    sku: str
    sku_type: SKUType
    price_cents: int
    currency: str = "usd"
    license_template_id: str
    revenue_share_bps: int = 8500


class ListingResponse(BaseModel):
    id: int
    sku: str
    sku_type: SKUType
    price_cents: int
    currency: str
    is_active: bool

    class Config:
        from_attributes = True


class ValidationStatusResponse(BaseModel):
    version_id: int
    status: str
    report_key: str | None
    issues: list


class SearchResponse(BaseModel):
    items: list[PackageResponse]


class PurchaseRequest(BaseModel):
    listing_id: int
    version_id: int
    scope: LicenseScope = LicenseScope.PERSONAL
    seats: int = 1
    execute_runs: int = 0


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class LicenseResponse(BaseModel):
    id: int
    package_id: int
    version_id: int
    scope: LicenseScope
    seats: int
    expires_at: datetime | None
    is_revoked: bool
    runs_remaining: int | None = None
    license_key_preview: str | None = None
    download_url: str | None = None


class RotateLicenseResponse(BaseModel):
    license_id: int
    new_license_key: str


class RatingRequest(BaseModel):
    package_id: int
    stars: int = Field(ge=1, le=5)
    title: str
    comment: str | None = None


class RatingResponse(BaseModel):
    id: int
    package_id: int
    user_id: str
    stars: int
    title: str
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True

