"""Initialize the FMU Gateway private API application."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import engine
from .models import Base
from .routes import (
    admin_marketplace,
    api_keys,
    auth,
    billing,
    creator,
    dashboard,
    execute_fmu,
    marketplace,
    registry,
    usage,
)


def create_app() -> FastAPI:
    """Create a FastAPI application and register routes."""
    Base.metadata.create_all(bind=engine)

    app = FastAPI(title="FMU Gateway Private API")
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(dashboard.router)
    app.include_router(auth.router)
    app.include_router(execute_fmu.router)
    app.include_router(billing.router)
    app.include_router(registry.router, prefix="/registry")
    app.include_router(usage.router)
    app.include_router(api_keys.router)
    app.include_router(creator.router)
    app.include_router(marketplace.router)
    app.include_router(admin_marketplace.router)
    return app
