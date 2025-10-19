"""Helpers for serving the server-rendered dashboard experience."""
from __future__ import annotations

import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import User
from .auth_service import AuthService


class FrontendService:
    """Encapsulate template rendering, CSRF, and rate limiting."""

    def __init__(self) -> None:
        self.settings = get_settings()
        templates_path = Path(__file__).resolve().parent.parent / "templates"
        self.templates = Jinja2Templates(directory=str(templates_path))
        self.templates.env.globals.update(now=datetime.utcnow)
        self._rate_limit_buckets: dict[str, tuple[float, int]] = {}
        self.auth_service = AuthService()

    def render(self, request: Request, template: str, context: Dict[str, Any]) -> Response:
        """Render a template with CSRF token injection and cookie handling."""
        context = dict(context)
        context.setdefault("request", request)
        context.setdefault("user", None)
        context.setdefault("docs_url", "/docs/sdk_usage.md")
        csrf_token = self._get_or_create_csrf_token(request)
        context.setdefault("csrf_token", csrf_token)
        context.setdefault("static_prefix", "/static")
        response = self.templates.TemplateResponse(template, context)
        if request.cookies.get(self.settings.csrf_cookie_name) != csrf_token:
            self._set_csrf_cookie(response, csrf_token)
        return response

    def rate_limit(self, request: Request) -> None:
        """Simple in-memory rate limiting keyed by client IP."""
        client = request.client.host if request.client else "anonymous"
        now = time.time()
        window_start, count = self._rate_limit_buckets.get(client, (now, 0))
        if now - window_start >= 60:
            window_start, count = now, 0
        if count >= self.settings.rate_limit_per_minute:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        self._rate_limit_buckets[client] = (window_start, count + 1)

    def create_session_response(self, token: str, redirect_to: str = "/dashboard") -> RedirectResponse:
        """Create a redirect response that stores the session JWT."""
        response = RedirectResponse(url=redirect_to, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            self.auth_service.jwt_cookie_name,
            token,
            httponly=True,
            secure=self.auth_service.jwt_cookie_secure,
            samesite="lax",
            max_age=60 * 60,
        )
        return response

    def clear_session(self) -> RedirectResponse:
        """Clear the session cookie and redirect to login."""
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(self.auth_service.jwt_cookie_name)
        response.delete_cookie(self.settings.csrf_cookie_name)
        return response

    def _get_or_create_csrf_token(self, request: Request) -> str:
        token = request.cookies.get(self.settings.csrf_cookie_name)
        if not token:
            token = secrets.token_urlsafe(32)
        return token

    def _set_csrf_cookie(self, response: Response, token: str) -> None:
        response.set_cookie(
            self.settings.csrf_cookie_name,
            token,
            httponly=False,
            secure=self.auth_service.jwt_cookie_secure,
            samesite="strict",
            max_age=60 * 60 * 12,
        )

    def assert_csrf(self, request: Request, supplied_token: str | None) -> None:
        expected = request.cookies.get(self.settings.csrf_cookie_name)
        if not expected or not supplied_token or supplied_token != expected:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")


frontend_service = FrontendService()

auth_service = frontend_service.auth_service


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> User:
    """Retrieve the authenticated user from the session cookie."""
    token = request.cookies.get(auth_service.jwt_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = auth_service.verify_token(token)
    except jwt.ExpiredSignatureError as exc:  # pragma: no cover - library exception path
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired") from exc
    except jwt.InvalidTokenError as exc:  # pragma: no cover - library exception path
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    user = auth_service.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
