"""Buyer-facing marketplace endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import (
    FMUPackage,
    FMUVersion,
    License,
    Listing,
    Purchase,
    PurchaseStatus,
    Rating,
    SKUType,
    User,
)
from ..schemas.marketplace import (
    CheckoutResponse,
    LicenseResponse,
    PackageResponse,
    PurchaseRequest,
    RatingRequest,
    RatingResponse,
    RotateLicenseResponse,
    SearchResponse,
)
from ..services.frontend_service import get_current_user
from ..services.licensing_service import licensing_service
from ..services.marketplace_service import marketplace_service
from ..services.object_storage import generate_signed_url


router = APIRouter(prefix="/registry")


@router.get("/search", response_model=SearchResponse)
def search_registry(
    q: str | None = None,
    tags: str | None = None,
    certified_only: bool = False,
    sort: str | None = None,
    session: Session = Depends(get_session),
):
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
    packages = marketplace_service.search_packages(
        session,
        query=q,
        tags=tag_list,
        certified_only=certified_only,
        sort=sort,
    )
    return SearchResponse(items=packages)


@router.get("/packages/{package_id}")
def package_detail(package_id: int, session: Session = Depends(get_session)) -> dict:
    package = session.query(FMUPackage).filter(FMUPackage.id == package_id).one_or_none()
    if not package or not package.is_listed:
        raise HTTPException(status_code=404, detail="Package not found")

    versions = []
    for version in sorted(package.versions, key=lambda v: v.id, reverse=True):
        latest_job = version.validation_jobs[0] if version.validation_jobs else None
        report_url = None
        if latest_job and latest_job.report_key:
            report_url = generate_signed_url(latest_job.report_key)
        versions.append(
            {
                "id": version.id,
                "semver": version.semver,
                "validated_at": version.validated_at,
                "validation_status": version.validation_status.value,
                "changelog": version.changelog,
                "report_url": report_url,
            }
        )

    badges = []
    if package.is_certified:
        badges.append("Certified")
    if package.creator.user and package.creator.user.email.endswith("@fmu-gateway.ai"):
        badges.append("Verified Creator")
    if versions and versions[0]["validated_at"]:
        badges.append("Recently Updated")

    return {
        "package": PackageResponse.model_validate(package).model_dump(),
        "versions": versions,
        "badges": badges,
        "ratings": [
            {
                "user": rating.user.email,
                "stars": rating.stars,
                "title": rating.title,
                "comment": rating.comment,
            }
            for rating in package.ratings
        ],
    }


@router.post("/purchase", response_model=CheckoutResponse)
def create_purchase(
    payload: PurchaseRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    listing = session.query(Listing).filter(Listing.id == payload.listing_id).one_or_none()
    if not listing or not listing.is_active:
        raise HTTPException(status_code=404, detail="Listing not found")

    version = (
        session.query(FMUVersion)
        .filter(FMUVersion.id == payload.version_id, FMUVersion.package_id == listing.package_id)
        .one_or_none()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Placeholder checkout session.  Production integrates Stripe Checkout.
    session_id = f"sess_{listing.id}_{version.id}_{user.id}"
    checkout_url = f"https://payments.local/checkout/{session_id}"

    _purchase, _raw_key = marketplace_service.finalize_purchase(
        session,
        buyer=user,
        listing=listing,
        version=version,
        stripe_payment_id=session_id,
        scope=payload.scope,
        seats=payload.seats,
        execute_runs=payload.execute_runs,
    )
    session.commit()
    return CheckoutResponse(checkout_url=checkout_url, session_id=session_id)


@router.get("/licenses", response_model=list[LicenseResponse])
def list_licenses(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    licenses = (
        session.query(License)
        .filter(License.buyer_user_id == user.id)
        .join(Purchase)
        .join(Listing)
        .all()
    )

    results: list[LicenseResponse] = []
    for license_obj in licenses:
        entitlement = license_obj.entitlements
        preview = None
        if license_obj.purchase.license_key:
            preview = license_obj.purchase.license_key[:6] + "***"
        download_url = None
        if (
            not license_obj.is_revoked
            and license_obj.purchase.listing.sku_type == SKUType.DOWNLOAD
        ):
            download_url = generate_signed_url(license_obj.version.file_key)
        results.append(
            LicenseResponse(
                id=license_obj.id,
                package_id=license_obj.package_id,
                version_id=license_obj.version_id,
                scope=license_obj.scope,
                seats=license_obj.seats,
                expires_at=license_obj.expires_at,
                is_revoked=license_obj.is_revoked,
                runs_remaining=entitlement.runs_remaining if entitlement else None,
                license_key_preview=preview,
                download_url=download_url,
            )
        )
    return results


@router.post("/licenses/{license_id}/rotate_key", response_model=RotateLicenseResponse)
def rotate_license(
    license_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    license_obj = (
        session.query(License)
        .filter(License.id == license_id, License.buyer_user_id == user.id)
        .one_or_none()
    )
    if not license_obj:
        raise HTTPException(status_code=404, detail="License not found")

    new_key = licensing_service.rotate_key(session, license_obj)
    session.commit()
    return RotateLicenseResponse(license_id=license_id, new_license_key=new_key)


@router.post("/ratings", response_model=RatingResponse)
def upsert_rating(
    payload: RatingRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    package = session.query(FMUPackage).filter(FMUPackage.id == payload.package_id).one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    owned = (
        session.query(Purchase)
        .filter(
            Purchase.package_id == package.id,
            Purchase.buyer_user_id == user.id,
            Purchase.status == PurchaseStatus.ACTIVE,
        )
        .count()
    )
    if not owned:
        raise HTTPException(status_code=403, detail="Purchase required for rating")

    rating = marketplace_service.upsert_rating(
        session,
        user=user,
        package=package,
        stars=payload.stars,
        title=payload.title,
        comment=payload.comment or "",
    )
    session.commit()
    return RatingResponse.model_validate(rating)

