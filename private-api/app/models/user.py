"""Pydantic schemas for user payloads."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """Request schema for registering a new user."""

    email: str
    name: str | None = None
    password: str | None = None


class LoginRequest(BaseModel):
    """Request schema for login using an API key."""

    email: str | None = None
    password: str | None = None
    api_key: str | None = None


class UserResponse(BaseModel):
    """Response schema for exposing user context to clients."""

    user_id: str = Field(..., alias="id", serialization_alias="user_id")
    email: str
    api_key: str | None = None
    credits: int

    if hasattr(BaseModel, "model_config"):
        model_config = ConfigDict(populate_by_name=True, from_attributes=True)
    else:
        class Config:
            orm_mode = True
            allow_population_by_field_name = True

    def dict(self, *args, **kwargs):  # type: ignore[override]
        by_alias = kwargs.get("by_alias")
        kwargs["by_alias"] = False
        data = super().dict(*args, **kwargs)
        if by_alias and "user_id" in data:
            return {**data}
        return data

    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        return self.dict(*args, **kwargs)
