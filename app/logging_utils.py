"""Utility helpers for structured logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional


def log_simulation_event(
    *,
    level: str,
    event: str,
    fmu_id: str,
    fmi: Optional[str],
    step: Optional[float],
    stop_time: Optional[float],
    status: Optional[str],
    wall_ms: Optional[int],
    job_id: str,
) -> None:
    """Emit a structured JSON log line for simulation lifecycle events."""
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "level": level.upper(),
        "event": event,
        "fmu_id": fmu_id,
        "fmi": fmi,
        "step": step,
        "stop_time": stop_time,
        "status": status,
        "wall_ms": wall_ms,
        "job_id": job_id,
    }
    print(json.dumps(payload, separators=(",", ":")))
