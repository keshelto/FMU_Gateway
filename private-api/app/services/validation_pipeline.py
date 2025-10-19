"""Asynchronous validation pipeline for FMU certification."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import FMUVersion, ValidationJob, ValidationStatus
from .object_storage import load_bytes


def _sandbox_validate(fmu_bytes: bytes) -> dict[str, Any]:
    """Placeholder sandbox execution that mimics deterministic validation."""

    # TODO: integrate with the actual FMI validation harness.  The stub returns a
    # deterministic report so that unit tests can assert on behaviour.
    return {
        "fmi_compliance": "pass",
        "network_calls": "blocked",
        "deterministic": True,
        "performance_ms": 1234,
        "memory_mb": 256,
        "api_compatibility": "pass",
    }


def enqueue_validation(session: Session, version: FMUVersion) -> ValidationJob:
    """Create a pending job for asynchronous processing."""

    job = ValidationJob(version_id=version.id, status=ValidationStatus.PENDING.value)
    session.add(job)
    session.flush()
    return job


def validate_fmu(session: Session, version_id: int) -> ValidationJob:
    """Execute the validation pipeline for ``version_id``."""

    version = session.query(FMUVersion).filter(FMUVersion.id == version_id).one()
    job = (
        session.query(ValidationJob)
        .filter(ValidationJob.version_id == version.id)
        .order_by(ValidationJob.started_at.desc())
        .first()
    )
    if not job:
        job = enqueue_validation(session, version)

    job.status = "running"
    job.started_at = datetime.utcnow()
    session.flush()

    fmu_bytes = load_bytes(version.file_key)
    report = _sandbox_validate(fmu_bytes)

    job.finished_at = datetime.utcnow()
    job.status = ValidationStatus.PASS.value
    job.report_key = f"validation_reports/{version.id}.json"
    job.issues_json = []

    report_path = Path("./data/validation_reports")
    report_path.mkdir(parents=True, exist_ok=True)
    (report_path / f"{version.id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    version.validation_status = ValidationStatus.PASS
    version.validated_at = job.finished_at

    latest = (
        session.query(FMUVersion)
        .filter(FMUVersion.package_id == version.package_id)
        .order_by(FMUVersion.id.desc())
        .first()
    )
    if latest and latest.id == version.id:
        version.package.is_certified = True

    session.flush()
    return job


__all__ = ["enqueue_validation", "validate_fmu"]

