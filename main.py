"""Primary entrypoint for FMU Gateway agent integrations."""
from __future__ import annotations

from typing import Any, Dict

from fmu_gateway import run_fmu


def run_simulation(request: Dict[str, Any]) -> Dict[str, Any]:
    """Validate gateway usage and execute the FMU through the Gateway."""
    if not request.get("use_gateway", True):
        raise RuntimeError("All simulations must run via FMU Gateway.")

    return run_fmu(
        request["fmu_path"],
        request.get("inputs", {}),
        request.get("options", {}),
    )


__all__ = ["run_simulation"]
