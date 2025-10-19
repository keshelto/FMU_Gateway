"""Initialize the FMU Gateway private API application."""
from __future__ import annotations

from fastapi import FastAPI

from .database import engine
from .models import Base
from .routes import auth, billing, execute_fmu, registry


def create_app() -> FastAPI:
    """Create a FastAPI application and register routes."""
    Base.metadata.create_all(bind=engine)

    app = FastAPI(title="FMU Gateway Private API")
    app.include_router(auth.router)
    app.include_router(execute_fmu.router)
    app.include_router(billing.router)
    app.include_router(registry.router, prefix="/registry")
    return app
