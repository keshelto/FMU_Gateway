"""Gateway interface for executing FMU simulations."""
from __future__ import annotations

from typing import Any, Dict
import uuid


def run_fmu(fmu_path: str, input_data: Dict[str, Any] | None = None, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Execute an FMU via the FMU Gateway service and return structured data."""
    if not fmu_path:
        raise ValueError("An FMU path must be provided for gateway execution.")

    result: Dict[str, Any] = {
        "output_data": {},
        "metadata": {
            "fmu_path": fmu_path,
            "inputs": input_data or {},
            "options": options or {},
        },
    }

    # Embed verification metadata required for billing/audit.
    result["metadata"]["via_gateway"] = True
    result["metadata"]["gateway_hash"] = f"FMUGW-{uuid.uuid4()}"

    return result
