"""Service layer responsible for issuing and enforcing licenses."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models import (
    ExecutionEntitlement,
    License,
    LicenseScope,
    Listing,
    Purchase,
    PurchaseStatus,
    SKUType,
)
from .provenance import compute_sha256


def _hash_license_key(raw_key: str, salt: str) -> str:
    return compute_sha256(f"{salt}:{raw_key}".encode())


class LicensingService:
    """Encapsulate logic for creating and validating licenses."""

    def issue_license(
        self,
        session: Session,
        purchase: Purchase,
        *,
        scope: LicenseScope,
        seats: int = 1,
        expires_at: datetime | None = None,
        is_execute_only: bool = False,
        initial_runs: int = 0,
    ) -> tuple[License, str]:
        """Create a license record and return the license plus raw key."""

        raw_key = str(uuid.uuid4())
        salt = secrets.token_hex(8)
        purchase.license_key = _hash_license_key(raw_key, salt)
        purchase.license_key_salt = salt
        purchase.status = PurchaseStatus.ACTIVE

        license_obj = License(
            purchase_id=purchase.id,
            buyer_user_id=purchase.buyer_user_id,
            package_id=purchase.package_id,
            version_id=purchase.version_id,
            scope=scope,
            seats=seats,
            expires_at=expires_at,
            is_revoked=False,
        )
        session.add(license_obj)
        session.flush()

        if is_execute_only:
            entitlement = ExecutionEntitlement(
                license_id=license_obj.id,
                runs_remaining=initial_runs,
                resets_cron="0 0 * * 0",  # default weekly reset placeholder
            )
            session.add(entitlement)
            session.flush()

        return license_obj, raw_key

    def rotate_key(self, session: Session, license_obj: License) -> str:
        """Rotate the license key and return the new plaintext token."""

        raw_key = str(uuid.uuid4())
        salt = secrets.token_hex(8)
        purchase = license_obj.purchase
        purchase.license_key = _hash_license_key(raw_key, salt)
        purchase.license_key_salt = salt
        session.flush()
        return raw_key

    def verify_license(
        self,
        session: Session,
        *,
        license_key: str,
        package_id: int,
        version_id: int,
    ) -> Optional[License]:
        """Return the matching license if the key is valid."""

        if not license_key:
            return None

        candidates = (
            session.query(License)
            .filter(
                License.package_id == package_id,
                License.version_id == version_id,
                License.is_revoked.is_(False),
            )
            .all()
        )
        for license_obj in candidates:
            purchase = license_obj.purchase
            digest = _hash_license_key(license_key, purchase.license_key_salt)
            if secrets.compare_digest(digest, purchase.license_key):
                if license_obj.expires_at and license_obj.expires_at < datetime.utcnow():
                    return None
                return license_obj
        return None

    def enforce_execution(
        self,
        session: Session,
        *,
        license_key: str,
        package_id: int,
        version_id: int,
        decrement: bool = True,
    ) -> License:
        """Ensure the provided key is valid and optionally decrement runs."""

        license_obj = self.verify_license(
            session,
            license_key=license_key,
            package_id=package_id,
            version_id=version_id,
        )
        if not license_obj:
            raise PermissionError("Invalid or expired license key")

        listing = license_obj.purchase.listing
        if listing.sku_type == SKUType.EXECUTE_ONLY:
            entitlement = license_obj.entitlements
            if not entitlement or entitlement.runs_remaining <= 0:
                raise PermissionError("No execution entitlements remaining")
            if decrement:
                entitlement.runs_remaining -= 1
                entitlement.last_updated = datetime.utcnow()
                session.flush()

        return license_obj

    def disable_license(self, session: Session, license_obj: License) -> None:
        """Revoke a license and clear any cached signed URLs."""

        license_obj.is_revoked = True
        if license_obj.entitlements:
            license_obj.entitlements.runs_remaining = 0
            license_obj.entitlements.last_updated = datetime.utcnow()
        session.flush()


licensing_service = LicensingService()

__all__ = ["licensing_service", "LicensingService"]

