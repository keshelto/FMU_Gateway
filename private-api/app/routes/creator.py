"""Creator-facing endpoints for managing FMU packages."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Creator, FMUPackage, FMUVersion, ValidationJob, ValidationStatus
from ..schemas.marketplace import (
    CreatorApplyRequest,
    CreatorResponse,
    ListingCreateRequest,
    ListingResponse,
    PackageCreateRequest,
    PackageResponse,
    ValidationStatusResponse,
    VersionUploadResponse,
)
from ..services.frontend_service import get_current_user
from ..services.marketplace_service import marketplace_service


router = APIRouter(prefix="/creator")


@router.post("/apply", response_model=CreatorResponse)
def apply_creator(
    payload: CreatorApplyRequest,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    creator = marketplace_service.apply_creator(session, user, payload.display_name)
    session.commit()
    return creator


def _get_creator(session: Session, user_id: str) -> Creator:
    creator = session.query(Creator).filter(Creator.user_id == user_id).one_or_none()
    if not creator:
        raise HTTPException(status_code=403, detail="Creator profile required")
    return creator


@router.post("/packages", response_model=PackageResponse)
def create_package(
    payload: PackageCreateRequest,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    creator = _get_creator(session, user.id)
    package = marketplace_service.create_package(
        session,
        creator,
        name=payload.name,
        short_desc=payload.short_desc,
        long_desc=payload.long_desc,
        tags=payload.tags,
        category=payload.category,
    )
    session.commit()
    return package


@router.post("/packages/{package_id}/versions", response_model=VersionUploadResponse)
async def upload_version(
    package_id: int,
    semver: str = Form(...),
    version: int = Form(...),
    changelog: str | None = Form(default=None),
    min_gateway_version: str | None = Form(default=None),
    metadata: str | None = Form(default=None),
    fmu_file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    creator = _get_creator(session, user.id)
    package = (
        session.query(FMUPackage)
        .filter(FMUPackage.id == package_id, FMUPackage.creator_id == creator.id)
        .one_or_none()
    )
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    fmu_bytes = await fmu_file.read()
    metadata_extra = {}
    if metadata:
        try:
            metadata_extra = json.loads(metadata)
        except ValueError as exc:  # pragma: no cover - defensive path
            raise HTTPException(status_code=400, detail="Invalid metadata JSON") from exc

    version_obj = marketplace_service.record_version(
        session,
        package,
        version=version,
        semver=semver,
        fmu_bytes=fmu_bytes,
        metadata_extra=metadata_extra,
        changelog=changelog,
        min_gateway_version=min_gateway_version,
    )
    session.commit()
    return version_obj


@router.post("/packages/{package_id}/listings", response_model=ListingResponse)
def create_listing(
    package_id: int,
    payload: ListingCreateRequest,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    creator = _get_creator(session, user.id)
    package = (
        session.query(FMUPackage)
        .filter(FMUPackage.id == package_id, FMUPackage.creator_id == creator.id)
        .one_or_none()
    )
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    listing = marketplace_service.create_listing(
        session,
        package,
        sku=payload.sku,
        sku_type=payload.sku_type,
        price_cents=payload.price_cents,
        currency=payload.currency,
        license_template_id=payload.license_template_id,
        revenue_share_bps=payload.revenue_share_bps,
    )
    session.commit()
    return listing


@router.get("/validation/{version_id}", response_model=ValidationStatusResponse)
def validation_status(
    version_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    job = (
        session.query(ValidationJob)
        .join(FMUVersion)
        .join(FMUPackage)
        .join(Creator)
        .filter(ValidationJob.version_id == version_id, Creator.user_id == user.id)
        .order_by(ValidationJob.started_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Validation job not found")
    return ValidationStatusResponse(
        version_id=version_id,
        status=job.status,
        report_key=job.report_key,
        issues=job.issues_json or [],
    )


@router.post("/packages/{package_id}/publish")
def publish_package(
    package_id: int,
    override: bool = False,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    creator = _get_creator(session, user.id)
    package = (
        session.query(FMUPackage)
        .filter(FMUPackage.id == package_id, FMUPackage.creator_id == creator.id)
        .one_or_none()
    )
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    latest_version = (
        session.query(FMUVersion)
        .filter(FMUVersion.package_id == package.id)
        .order_by(FMUVersion.id.desc())
        .first()
    )
    if not latest_version:
        raise HTTPException(status_code=400, detail="Upload a version before publishing")

    if not override and latest_version.validation_status != ValidationStatus.PASS:
        raise HTTPException(status_code=400, detail="Latest version must pass validation")

    marketplace_service.mark_package_listed(session, package)
    session.commit()
    return {"status": "published", "package_id": package.id}

