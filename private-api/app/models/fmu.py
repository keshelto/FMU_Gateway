"""Data model for FMU payloads exchanged with the backend."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FMUExecutionRequest(BaseModel):
    """Schema describing an FMU execution request."""

    parameters: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class FMUExecutionResult(BaseModel):
    """Schema describing the result returned after FMU execution."""

    status: str
    output_url: str
    execution_time: float
    credits_consumed: int
