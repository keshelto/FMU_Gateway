"""Route for executing FMUs through the private API."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import SKUType, User
from ..models.fmu import FMUExecutionRequest, FMUExecutionResult
from ..services.auth_service import AuthService
from ..services.billing_service import BillingService
from ..services.fmu_runner import FMURunner
from ..services.licensing_service import licensing_service

logger = logging.getLogger(__name__)

router = APIRouter()
runner = FMURunner()
settings = get_settings()
auth_service = AuthService()
billing_service = BillingService()

_RATE_LIMIT_BUCKETS: defaultdict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_WINDOW = 60.0
_RATE_LIMIT_MAX = 5


def _enforce_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    bucket = _RATE_LIMIT_BUCKETS[user_id]
    while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    bucket.append(now)


def _resolve_user(
    session: Session,
    authorization: str | None,
    api_key_header: str | None,
) -> User:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = auth_service.verify_token(token)
        user = auth_service.get_user(session, payload.get("sub"))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user

    if api_key_header:
        user = auth_service.authenticate_api_key(session, api_key_header.strip())
        if user:
            return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


@router.post("/execute_fmu", response_model=FMUExecutionResult)
async def execute_fmu(
    fmu: UploadFile = File(...),
    payload: str = Form("{}"),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    license_key: str | None = Form(default=None),
    package_id: int | None = Form(default=None),
    version_id: int | None = Form(default=None),
    session: Session = Depends(get_session),
) -> FMUExecutionResult:
    """Validate credentials, run the FMU, and deduct credits."""
    user = _resolve_user(session, authorization, x_api_key)
    _enforce_rate_limit(user.id)

    try:
        payload_dict = json.loads(payload or "{}")
        request_model = FMUExecutionRequest(**payload_dict)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload JSON") from exc

    license_obj = None
    if license_key or package_id or version_id:
        if not all([license_key, package_id, version_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License enforcement requires license_key, package_id, and version_id",
            )
        try:
            license_obj = licensing_service.enforce_execution(
                session,
                license_key=license_key or "",
                package_id=int(package_id),
                version_id=int(version_id),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if user.credits <= 0 and not license_obj:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Your credits are low. Visit billing portal at {settings.public_billing_portal}",
        )

    fmu_bytes = await fmu.read()
    start_time = time.monotonic()
    runner_result = runner.run(fmu_bytes, request_model.parameters)
    elapsed = time.monotonic() - start_time

    credits_consumed = max(1, int(request_model.metadata.get("credit_cost", 1)))
    should_deduct = True
    if license_obj and license_obj.purchase.listing.sku_type == SKUType.DOWNLOAD:
        should_deduct = False

    if should_deduct:
        try:
            billing_service.deduct_credits(session, user, credits_consumed)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Your credits are low. Visit billing portal at {settings.public_billing_portal}",
            ) from None

    billing_service.log_usage(
        session,
        user,
        request_model.metadata.get("fmu_name", fmu.filename or "unknown"),
        credits_consumed,
    )

    logger.info(
        "FMU executed",
        extra={
            "user_id": user.id,
            "status": runner_result["status"],
            "remaining_credits": user.credits,
        },
    )

    return FMUExecutionResult(
        status=runner_result["status"],
        output_url=f"{settings.public_billing_portal}/results/{user.id}/{int(time.time())}.zip",
        execution_time=elapsed,
        credits_consumed=credits_consumed,
    )
