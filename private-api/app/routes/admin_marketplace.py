"""Administrative endpoints for moderation and compliance."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import AuditLog, DMCATakedown, FMUPackage, License
from ..services.frontend_service import get_current_user
from ..services.marketplace_service import marketplace_service


router = APIRouter(prefix="/admin", tags=["admin"])


def _assert_admin(user) -> None:
    if not user.email.endswith("@fmu-gateway.ai"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/unlist/{package_id}")
def unlist_package(
    package_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _assert_admin(user)
    package = session.query(FMUPackage).filter(FMUPackage.id == package_id).one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    marketplace_service.unlist_package(session, package)
    session.add(
        AuditLog(
            actor_user_id=user.id,
            action="admin_unlist",
            entity="fmu_package",
            entity_id=str(package.id),
        )
    )
    session.commit()
    return {"status": "unlisted"}


@router.post("/revoke_license/{license_id}")
def revoke_license(
    license_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _assert_admin(user)
    license_obj = session.query(License).filter(License.id == license_id).one_or_none()
    if not license_obj:
        raise HTTPException(status_code=404, detail="License not found")

    marketplace_service.revoke_license(session, license_obj)
    session.add(
        AuditLog(
            actor_user_id=user.id,
            action="admin_revoke_license",
            entity="license",
            entity_id=str(license_obj.id),
        )
    )
    session.commit()
    return {"status": "revoked"}


@router.get("/dmca")
def dmca_queue(session: Session = Depends(get_session), user=Depends(get_current_user)) -> dict:
    _assert_admin(user)
    takedowns = session.query(DMCATakedown).filter(DMCATakedown.status == "pending").all()
    return {"items": [
        {
            "id": item.id,
            "package_id": item.package_id,
            "claim_text": item.claim_text,
            "complainant_email": item.complainant_email,
            "created_at": item.created_at,
        }
        for item in takedowns
    ]}


@router.post("/dmca/{takedown_id}/resolve")
def resolve_dmca(
    takedown_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _assert_admin(user)
    takedown = session.query(DMCATakedown).filter(DMCATakedown.id == takedown_id).one_or_none()
    if not takedown:
        raise HTTPException(status_code=404, detail="Takedown request not found")

    takedown.status = "resolved"
    takedown.resolved_at = datetime.utcnow()
    session.add(
        AuditLog(
            actor_user_id=user.id,
            action="admin_dmca_resolve",
            entity="dmca_takedown",
            entity_id=str(takedown.id),
        )
    )
    session.commit()
    return {"status": "resolved"}

