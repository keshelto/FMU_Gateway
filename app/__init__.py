"""Application package initialisation and compatibility helpers."""

from __future__ import annotations

from inspect import signature

try:  # pragma: no cover - optional dependency
    import httpx
except Exception:  # pragma: no cover - safety fallback
    httpx = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from pydantic import BaseModel
except Exception:  # pragma: no cover - safety fallback
    BaseModel = None  # type: ignore


def _patch_httpx_client_app_kwarg() -> None:
    """Re-introduce the deprecated ``app`` kwarg for ``httpx.Client``."""

    if httpx is None:  # pragma: no cover - nothing to patch
        return

    if "app" in signature(httpx.Client.__init__).parameters:
        return

    original_init = httpx.Client.__init__

    def patched_init(self, *args, app=None, **kwargs):  # type: ignore[override]
        if app is not None and "transport" not in kwargs:
            kwargs["transport"] = httpx.ASGITransport(app=app)
        return original_init(self, *args, **kwargs)

    httpx.Client.__init__ = patched_init  # type: ignore[assignment]


def _patch_pydantic_v1_compat() -> None:
    """Backport key Pydantic v2 APIs when running on Pydantic v1."""

    if BaseModel is None:  # pragma: no cover - nothing to patch
        return

    if not hasattr(BaseModel, "model_dump"):
        BaseModel.model_dump = BaseModel.dict  # type: ignore[assignment]

    if not hasattr(BaseModel, "model_dump_json"):
        BaseModel.model_dump_json = BaseModel.json  # type: ignore[assignment]

    if not hasattr(BaseModel, "model_copy"):
        BaseModel.model_copy = BaseModel.copy  # type: ignore[assignment]

    if not hasattr(BaseModel, "model_validate"):
        @classmethod  # type: ignore[misc]
        def model_validate(cls, data, **kwargs):
            return cls.parse_obj(data)

        BaseModel.model_validate = model_validate  # type: ignore[assignment]

    if not hasattr(BaseModel, "model_validate_json"):
        @classmethod  # type: ignore[misc]
        def model_validate_json(cls, data, **kwargs):
            return cls.parse_raw(data)

        BaseModel.model_validate_json = model_validate_json  # type: ignore[assignment]


_patch_httpx_client_app_kwarg()
_patch_pydantic_v1_compat()

__all__ = [
    "_patch_httpx_client_app_kwarg",
    "_patch_pydantic_v1_compat",
]
