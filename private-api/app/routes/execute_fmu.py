"""Route for executing FMUs through the private API."""
from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from ..config import get_settings
from ..models.fmu import FMUExecutionRequest, FMUExecutionResult
from ..services.fmu_runner import FMURunner
from .billing import decrement_user_credits, get_user_by_api_key, stripe_service

logger = logging.getLogger(__name__)

router = APIRouter()
runner = FMURunner()
settings = get_settings()


@router.post("/execute_fmu", response_model=FMUExecutionResult)
async def execute_fmu(
    fmu: UploadFile = File(...),
    payload: str = Form("{}"),
    authorization: str | None = Header(default=None),
) -> FMUExecutionResult:
    """Validate API key, run the FMU in a sandbox, and return the execution result."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API key")

    api_key = authorization.removeprefix("Bearer ").strip()
    user = get_user_by_api_key(api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        payload_dict = json.loads(payload or "{}")
        request_model = FMUExecutionRequest(**payload_dict)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload JSON") from exc

    fmu_bytes = await fmu.read()
    start_time = time.monotonic()
    runner_result = runner.run(fmu_bytes, request_model.parameters)
    elapsed = time.monotonic() - start_time

    credits_consumed = max(1, int(request_model.metadata.get("credit_cost", 1)))
    remaining_credits = decrement_user_credits(user, credits_consumed)
    stripe_service.charge_per_execution(user.id, int(credits_consumed * 10))

    logger.info(
        "FMU executed",
        extra={
            "user_id": user.id,
            "status": runner_result["status"],
            "remaining_credits": remaining_credits,
        },
    )

    return FMUExecutionResult(
        status=runner_result["status"],
        output_url=f"{settings.s3_bucket_url}/results/{user.id}/{int(time.time())}.zip",
        execution_time=elapsed,
        credits_consumed=credits_consumed,
    )
