"""Service responsible for executing FMUs in an isolated environment."""
from __future__ import annotations

import time
from typing import Dict


class FMURunner:
    """Placeholder FMU runner used for unit tests and documentation."""

    def run(self, fmu_bytes: bytes, parameters: Dict | None = None) -> Dict[str, str]:
        """Pretend to execute an FMU and return a deterministic response."""
        _ = fmu_bytes  # The placeholder implementation does not inspect the payload.
        time.sleep(0.01)
        return {
            "status": "succeeded",
            "log": f"Executed with parameters: {parameters or {}}",
        }
