"""API endpoints for managing user API keys."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import APIKey, UsageLog
from ..services.auth_service import AuthService
from ..services.frontend_service import frontend_service, get_current_user

router = APIRouter(prefix="/api_keys", tags=["api_keys"])

auth_service = AuthService()


class APIKeyResponse(BaseModel):
    """Serialized API key payload."""

    id: int
    label: str | None
    key: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    usage_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class APIKeyCreateRequest(BaseModel):
    """Payload for generating a new API key."""

    label: str | None = None


@router.get("/", response_model=list[APIKeyResponse])
async def list_api_keys(
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[APIKeyResponse]:
    keys = (
        session.query(APIKey)
        .filter(APIKey.user_id == user.id)
        .order_by(APIKey.created_at.desc())
        .all()
    )
    responses: list[APIKeyResponse] = []
    for key in keys:
        usage_count = (
            session.query(UsageLog)
            .filter(UsageLog.api_key_id == key.id, UsageLog.user_id == user.id)
            .count()
        )
        responses.append(
            APIKeyResponse(
                id=key.id,
                label=key.label,
                key=key.key,
                is_active=key.is_active,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                usage_count=usage_count,
            )
        )
    return responses


@router.post("/new", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: Request,
    payload: APIKeyCreateRequest,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> APIKeyResponse:
    frontend_service.assert_csrf(request, request.headers.get("X-CSRF-Token"))
    api_key = auth_service.create_api_key(session, user, label=payload.label)
    session.commit()
    session.refresh(api_key)
    return APIKeyResponse(
        id=api_key.id,
        label=api_key.label,
        key=api_key.key,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        usage_count=0,
    )


@router.post("/revoke/{key_id}", response_model=APIKeyResponse)
async def revoke_api_key(
    request: Request,
    key_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> APIKeyResponse:
    frontend_service.assert_csrf(request, request.headers.get("X-CSRF-Token"))
    api_key = (
        session.query(APIKey)
        .filter(APIKey.id == key_id, APIKey.user_id == user.id)
        .one_or_none()
    )
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    api_key.is_active = False
    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    usage_count = (
        session.query(UsageLog)
        .filter(UsageLog.api_key_id == api_key.id, UsageLog.user_id == user.id)
        .count()
    )

    return APIKeyResponse(
        id=api_key.id,
        label=api_key.label,
        key=api_key.key,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        usage_count=usage_count,
    )
