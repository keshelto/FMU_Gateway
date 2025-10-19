"""Initialize the FMU Gateway private API application."""
from __future__ import annotations

from fastapi import FastAPI

from .routes import billing, execute_fmu, registry


def create_app() -> FastAPI:
    """Create a FastAPI application and register routes."""
    app = FastAPI(title="FMU Gateway Private API")
    app.include_router(execute_fmu.router)
    app.include_router(billing.router)
    app.include_router(registry.router, prefix="/registry")
    return app
