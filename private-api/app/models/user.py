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

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
