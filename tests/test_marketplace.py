"""Tests covering Certified FMU Registry workflows."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


PRIVATE_API_ROOT = Path(__file__).resolve().parents[1] / "private-api"
PRIVATE_APP_PACKAGE = types.ModuleType("private_api_app")
PRIVATE_APP_PACKAGE.__path__ = [str(PRIVATE_API_ROOT / "app")]
sys.modules.setdefault("private_api_app", PRIVATE_APP_PACKAGE)

from private_api_app.models import (  # type: ignore
    Base,
    FMUPackage,
    LicenseScope,
    PurchaseStatus,
    SKUType,
    User,
)
from private_api_app.services.licensing_service import licensing_service  # type: ignore
from private_api_app.services.marketplace_service import marketplace_service  # type: ignore
from private_api_app.services.object_storage import generate_signed_url  # type: ignore
from private_api_app.services.validation_pipeline import validate_fmu  # type: ignore


@pytest.fixture()
def session(tmp_path) -> Session:
    os.environ.setdefault("OBJECT_STORAGE_ROOT", str(tmp_path / "objects"))
    database_url = f"sqlite:///{tmp_path}/marketplace.db"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def _create_user(session: Session, email: str) -> User:
    user = User(id=email, email=email, name="Tester", api_key=f"key-{email}", credits=10)
    session.add(user)
    session.flush()
    return user


def test_upload_validation_publish(session: Session) -> None:
    creator_user = _create_user(session, "creator@example.com")
    creator = marketplace_service.apply_creator(session, creator_user, "Example Creator")
    package = marketplace_service.create_package(
        session,
        creator,
        name="Battery Pack",
        short_desc="High fidelity battery model",
        long_desc="Detailed electrochemical behaviour",
        tags=["battery", "ev"],
        category="energy",
    )

    version = marketplace_service.record_version(
        session,
        package,
        version=1,
        semver="1.0.0",
        fmu_bytes=b"dummy fmu",
        metadata_extra={"fmi_version": "2.0"},
    )
    session.commit()

    validate_fmu(session, version.id)
    session.commit()

    assert version.validation_status.name == "PASS"
    assert version.package.is_certified is True

    marketplace_service.mark_package_listed(session, package)
    session.commit()
    assert package.is_listed is True


def test_purchase_and_signed_url(session: Session) -> None:
    buyer = _create_user(session, "buyer@example.com")
    creator = marketplace_service.apply_creator(session, _create_user(session, "creator2@example.com"), "Creator Two")
    package = marketplace_service.create_package(
        session,
        creator,
        name="Motor",
        short_desc="Motor model",
        long_desc="Detailed description",
        tags=["motor"],
        category="powertrain",
    )
    version = marketplace_service.record_version(
        session,
        package,
        version=1,
        semver="0.1.0",
        fmu_bytes=b"content",
    )
    listing = marketplace_service.create_listing(
        session,
        package,
        sku="MOTOR-DL",
        sku_type=SKUType.DOWNLOAD,
        price_cents=1200,
        currency="usd",
        license_template_id="personal-noncommercial",
        revenue_share_bps=9000,
    )

    purchase, raw_key = marketplace_service.finalize_purchase(
        session,
        buyer=buyer,
        listing=listing,
        version=version,
        stripe_payment_id="sess_123",
        scope=LicenseScope.PERSONAL,
        seats=1,
        execute_runs=0,
    )
    session.commit()

    assert purchase.status == PurchaseStatus.ACTIVE
    assert purchase.license is not None
    assert len(raw_key) == 36

    url = generate_signed_url(version.file_key)
    assert "token=" in url


def test_execute_only_entitlement(session: Session) -> None:
    buyer = _create_user(session, "exec@example.com")
    creator = marketplace_service.apply_creator(session, _create_user(session, "creator3@example.com"), "Creator Three")
    package = marketplace_service.create_package(
        session,
        creator,
        name="Plant",
        short_desc="Process plant",
        long_desc="Plant description",
        tags=["process"],
        category="industrial",
    )
    version = marketplace_service.record_version(
        session,
        package,
        version=1,
        semver="2.0.0",
        fmu_bytes=b"abc",
    )
    listing = marketplace_service.create_listing(
        session,
        package,
        sku="PLANT-EXEC",
        sku_type=SKUType.EXECUTE_ONLY,
        price_cents=2000,
        currency="usd",
        license_template_id="execute-only",
        revenue_share_bps=8500,
    )
    purchase, key = marketplace_service.finalize_purchase(
        session,
        buyer=buyer,
        listing=listing,
        version=version,
        stripe_payment_id="sess_exec",
        scope=LicenseScope.PERSONAL,
        seats=1,
        execute_runs=3,
    )
    session.commit()

    assert licensing_service.verify_license(
        session,
        license_key=key,
        package_id=package.id,
        version_id=version.id,
    ) is not None

    licensing_service.enforce_execution(
        session,
        license_key=key,
        package_id=package.id,
        version_id=version.id,
        decrement=True,
    )
    session.commit()
    assert purchase.license.entitlements.runs_remaining == 2

    licensing_service.enforce_execution(
        session,
        license_key=key,
        package_id=package.id,
        version_id=version.id,
        decrement=True,
    )
    licensing_service.enforce_execution(
        session,
        license_key=key,
        package_id=package.id,
        version_id=version.id,
        decrement=True,
    )
    session.commit()
    assert purchase.license.entitlements.runs_remaining == 0

    with pytest.raises(PermissionError):
        licensing_service.enforce_execution(
            session,
            license_key=key,
            package_id=package.id,
            version_id=version.id,
            decrement=True,
        )


def test_takedown_unlists_package(session: Session) -> None:
    creator_user = _create_user(session, "takedown@example.com")
    creator = marketplace_service.apply_creator(session, creator_user, "Creator Four")
    package = marketplace_service.create_package(
        session,
        creator,
        name="Hydraulics",
        short_desc="Hydraulic system",
        long_desc="Detailed hydraulic model",
        tags=["hydraulic"],
        category="industrial",
    )
    marketplace_service.mark_package_listed(session, package)
    assert package.is_listed is True
    marketplace_service.unlist_package(session, package)
    assert package.is_listed is False
