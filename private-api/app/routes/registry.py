"""Routes for managing FMU registry metadata."""
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/fmus")
def list_fmus() -> Dict[str, str]:
    """Return a placeholder list of registered FMUs."""
    return {"items": []}
