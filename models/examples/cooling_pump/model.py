"""Cooling pump sizing model implementation."""

from __future__ import annotations

from typing import Mapping

WATER_CP_J_PER_KG_K = 4180.0
WATER_DENSITY_KG_PER_M3 = 1000.0


class CoolingPumpInputError(ValueError):
    """Raised when model inputs are missing or out of the spec range."""


def _coerce_float(inputs: Mapping[str, object], key: str) -> float:
    if key not in inputs:
        raise CoolingPumpInputError(f"Missing required input: {key}")
    value = inputs[key]
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CoolingPumpInputError(f"Input '{key}' must be a number") from exc


def run(inputs: Mapping[str, object]) -> dict[str, float]:
    """Calculate required coolant mass and volumetric flow.

    Args:
        inputs: Mapping containing `heat_rejection` (kW) and `delta_t` (K).

    Returns:
        Dict with `mass_flow` (kg/s) and `volume_flow_lpm` (L/min).
    """

    heat_rejection_kw = _coerce_float(inputs, "heat_rejection")
    delta_t_k = _coerce_float(inputs, "delta_t")

    if not 0.0 <= heat_rejection_kw <= 1000.0:
        raise CoolingPumpInputError("heat_rejection must be between 0 and 1000 kW")
    if not 1.0 <= delta_t_k <= 50.0:
        raise CoolingPumpInputError("delta_t must be between 1 and 50 K")

    heat_rejection_w = heat_rejection_kw * 1000.0
    mass_flow_kg_s = heat_rejection_w / (WATER_CP_J_PER_KG_K * delta_t_k)

    volume_flow_m3_s = mass_flow_kg_s / WATER_DENSITY_KG_PER_M3
    volume_flow_lpm = volume_flow_m3_s * 60000.0

    return {
        "mass_flow": mass_flow_kg_s,
        "volume_flow_lpm": volume_flow_lpm,
    }
