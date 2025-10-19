"""Business logic for the Certified FMU Registry."""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from ..models import (
    AuditLog,
    Creator,
    DMCATakedown,
    ExecutionEntitlement,
    FMUPackage,
    FMUVersion,
    License,
    LicenseScope,
    Listing,
    Purchase,
    PurchaseStatus,
    Rating,
    SKUType,
    User,
    ValidationJob,
    ValidationStatus,
)
from .licensing_service import licensing_service
from .object_storage import save_fmu_bytes
from .provenance import build_metadata, compute_sha256, sign_digest


class MarketplaceService:
    """Encapsulate orchestration around models and external systems."""

    PLATFORM_FEE_BPS = 1500

    # ------------------------------------------------------------------ Creator
    def apply_creator(self, session: Session, user: User, display_name: str) -> Creator:
        existing = session.query(Creator).filter(Creator.user_id == user.id).one_or_none()
        if existing:
            return existing

        creator = Creator(user_id=user.id, display_name=display_name)
        session.add(creator)
        session.flush()

        log = AuditLog(
            actor_user_id=user.id,
            action="creator_apply",
            entity="creator",
            entity_id=str(creator.id),
            details_json={"display_name": display_name},
        )
        session.add(log)
        session.flush()
        return creator

    def create_package(
        self,
        session: Session,
        creator: Creator,
        *,
        name: str,
        short_desc: str,
        long_desc: str,
        tags: Iterable[str],
        category: str | None,
    ) -> FMUPackage:
        package = FMUPackage(
            creator_id=creator.id,
            name=name,
            short_desc=short_desc,
            long_desc=long_desc,
            tags=list(tags),
            category=category,
        )
        session.add(package)
        session.flush()

        session.add(
            AuditLog(
                actor_user_id=creator.user_id,
                action="package_create",
                entity="fmu_package",
                entity_id=str(package.id),
                details_json={"name": name},
            )
        )
        session.flush()
        return package

    def record_version(
        self,
        session: Session,
        package: FMUPackage,
        *,
        version: int,
        semver: str,
        fmu_bytes: bytes,
        metadata_extra: dict | None = None,
        changelog: str | None = None,
        min_gateway_version: str | None = None,
    ) -> FMUVersion:
        file_key = f"packages/{package.id}/{uuid.uuid4().hex}.fmu"
        save_fmu_bytes(fmu_bytes, file_key)

        digest = compute_sha256(fmu_bytes)
        signature = sign_digest(digest)
        metadata = build_metadata(**(metadata_extra or {}))

        version_obj = FMUVersion(
            package_id=package.id,
            version=version,
            semver=semver,
            file_key=file_key,
            file_sha256=digest,
            size_bytes=len(fmu_bytes),
            metadata_json=metadata,
            changelog=changelog,
            min_gateway_version=min_gateway_version,
            signature_hex=signature,
        )
        session.add(version_obj)
        session.flush()

        job = ValidationJob(version_id=version_obj.id, status=ValidationStatus.PENDING.value)
        session.add(job)
        session.flush()

        session.add(
            AuditLog(
                actor_user_id=package.creator.user_id,
                action="version_upload",
                entity="fmu_version",
                entity_id=str(version_obj.id),
                details_json={"semver": semver},
            )
        )
        session.flush()
        return version_obj

    def create_listing(
        self,
        session: Session,
        package: FMUPackage,
        *,
        sku: str,
        sku_type: SKUType,
        price_cents: int,
        currency: str,
        license_template_id: str,
        revenue_share_bps: int,
    ) -> Listing:
        listing = Listing(
            package_id=package.id,
            sku=sku,
            sku_type=sku_type,
            price_cents=price_cents,
            currency=currency,
            license_template_id=license_template_id,
            revenue_share_bps=revenue_share_bps,
        )
        session.add(listing)
        session.flush()

        session.add(
            AuditLog(
                actor_user_id=package.creator.user_id,
                action="listing_create",
                entity="listing",
                entity_id=str(listing.id),
                details_json={"sku": sku, "price_cents": price_cents},
            )
        )
        session.flush()
        return listing

    def mark_package_listed(self, session: Session, package: FMUPackage) -> FMUPackage:
        package.is_listed = True
        session.flush()
        return package

    # ------------------------------------------------------------------ Search
    def search_packages(
        self,
        session: Session,
        *,
        query: str | None,
        tags: list[str] | None,
        certified_only: bool,
        sort: str | None,
    ) -> list[FMUPackage]:
        stmt = session.query(FMUPackage).filter(FMUPackage.is_listed.is_(True))
        if query:
            like = f"%{query.lower()}%"
            tag_text = cast(FMUPackage.tags, String)
            stmt = stmt.filter(
                or_(
                    func.lower(FMUPackage.name).like(like),
                    func.lower(FMUPackage.long_desc).like(like),
                    func.lower(tag_text).like(like),
                )
            )
        if tags:
            for tag in tags:
                stmt = stmt.filter(cast(FMUPackage.tags, String).like(f"%{tag}%"))
        if certified_only:
            stmt = stmt.filter(FMUPackage.is_certified.is_(True))

        if sort == "rating":
            stmt = stmt.order_by(FMUPackage.rating_avg.desc(), FMUPackage.rating_count.desc())
        elif sort == "recent":
            stmt = stmt.order_by(FMUPackage.created_at.desc())
        else:
            stmt = stmt.order_by(FMUPackage.is_certified.desc(), FMUPackage.rating_avg.desc())

        return stmt.all()

    # ---------------------------------------------------------------- Purchases
    def calculate_payout(self, price_cents: int, revenue_share_bps: int | None = None) -> tuple[int, int]:
        platform_bps = revenue_share_bps or (10000 - self.PLATFORM_FEE_BPS)
        creator_cut = math.floor(price_cents * platform_bps / 10000)
        platform_cut = price_cents - creator_cut
        return creator_cut, platform_cut

    def snapshot_license(self, template_name: str) -> str:
        templates_dir = Path(__file__).resolve().parent.parent / "templates" / "licenses"
        if not templates_dir.exists():
            return f"License template {template_name}"
        template_path = templates_dir / template_name
        if not template_path.exists():
            return f"License template {template_name}"
        return template_path.read_text(encoding="utf-8")

    def finalize_purchase(
        self,
        session: Session,
        *,
        buyer: User,
        listing: Listing,
        version: FMUVersion,
        stripe_payment_id: str,
        scope: LicenseScope,
        seats: int,
        execute_runs: int,
    ) -> tuple[Purchase, str]:
        license_text = self.snapshot_license(f"{listing.license_template_id}.md")
        purchase = Purchase(
            buyer_user_id=buyer.id,
            listing_id=listing.id,
            package_id=listing.package_id,
            version_id=version.id,
            stripe_payment_id=stripe_payment_id,
            license_terms_snapshot=license_text,
            status=PurchaseStatus.PENDING,
            license_key="",
            license_key_salt="",
        )
        session.add(purchase)
        session.flush()

        is_execute_only = listing.sku_type == SKUType.EXECUTE_ONLY
        license_obj, raw_key = licensing_service.issue_license(
            session,
            purchase,
            scope=scope,
            seats=seats,
            is_execute_only=is_execute_only,
            initial_runs=execute_runs,
        )

        session.add(
            AuditLog(
                actor_user_id=buyer.id,
                action="license_issued",
                entity="license",
                entity_id=str(license_obj.id),
                details_json={"listing_id": listing.id},
            )
        )
        session.flush()
        return purchase, raw_key

    # ----------------------------------------------------------------- Ratings
    def upsert_rating(
        self,
        session: Session,
        *,
        user: User,
        package: FMUPackage,
        stars: int,
        title: str,
        comment: str,
    ) -> Rating:
        rating = (
            session.query(Rating)
            .filter(Rating.package_id == package.id, Rating.user_id == user.id)
            .one_or_none()
        )
        if rating:
            rating.stars = stars
            rating.title = title
            rating.comment = comment
        else:
            rating = Rating(
                package_id=package.id,
                user_id=user.id,
                stars=stars,
                title=title,
                comment=comment,
            )
            session.add(rating)
        session.flush()

        agg = (
            session.query(func.avg(Rating.stars), func.count(Rating.id))
            .filter(Rating.package_id == package.id)
            .one()
        )
        package.rating_avg = float(agg[0]) if agg[0] else 0
        package.rating_count = int(agg[1])
        session.flush()
        return rating

    # --------------------------------------------------------------- Moderation
    def unlist_package(self, session: Session, package: FMUPackage) -> None:
        package.is_listed = False
        session.flush()

    def revoke_license(self, session: Session, license_obj: License) -> None:
        licensing_service.disable_license(session, license_obj)


marketplace_service = MarketplaceService()

__all__ = ["marketplace_service", "MarketplaceService"]

