"""Agent tool registrations for FMU Gateway."""
from __future__ import annotations

from fmu_gateway import run_fmu


tools = [
    {
        "name": "FMU Gateway",
        "func": run_fmu,
        "description": "Executes FMU simulations via the FMU Gateway service.",
    }
]


__all__ = ["tools"]
