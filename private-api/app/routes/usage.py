"""Usage reporting endpoints for the dashboard."""
from __future__ import annotations

from datetime import datetime

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import UsageLog
from ..services.frontend_service import get_current_user

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageLogResponse(BaseModel):
    """Serialized representation of a usage log entry."""

    id: int
    timestamp: datetime
    fmu_name: str
    credits_used: int
    api_key_id: int | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=list[UsageLogResponse])
async def list_usage(
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[UsageLogResponse]:
    logs = (
        session.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.timestamp.desc())
        .limit(250)
        .all()
    )
    return [UsageLogResponse.model_validate(log) for log in logs]


@router.get("/recent", response_model=list[UsageLogResponse])
async def recent_usage(
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[UsageLogResponse]:
    logs = (
        session.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.timestamp.desc())
        .limit(30)
        .all()
    )
    return [UsageLogResponse.model_validate(log) for log in logs]


@router.get("/export")
async def export_usage(
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    logs = (
        session.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.timestamp.desc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "FMU Name", "Credits Used", "API Key ID"])
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat(),
            log.fmu_name,
            log.credits_used,
            log.api_key_id or "-",
        ])
    buffer.seek(0)

    headers = {"Content-Disposition": "attachment; filename=usage_logs.csv"}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)
