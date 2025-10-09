"""Simulation result validation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np


class SimulationValidationError(Exception):
    """Raised when a simulation result fails validation checks."""


@dataclass
class VariableMetadata:
    name: str
    causality: Optional[str]
    variability: Optional[str]
    var_type: Optional[str]
    unit: Optional[str]


# Conservative bounds for common engineering units. All bounds are inclusive and
# deliberately broad so that genuinely unreasonable values are flagged while
# typical simulation magnitudes still pass validation.
_UNIT_LIMITS: Dict[str, Tuple[float, float]] = {
    "s": (0.0, 1.0e6),
    "ms": (0.0, 1.0e9),
    "kg": (0.0, 1.0e6),
    "g": (0.0, 1.0e9),
    "n": (-1.0e7, 1.0e7),
    "nm": (-1.0e7, 1.0e7),
    "m": (-1.0e6, 1.0e6),
    "cm": (-1.0e5, 1.0e5),
    "mm": (-1.0e4, 1.0e4),
    "m/s": (-3.0e4, 3.0e4),
    "m/s2": (-3.0e4, 3.0e4),
    "m/s^2": (-3.0e4, 3.0e4),
    "rad": (-1.0e4, 1.0e4),
    "rad/s": (-3.0e4, 3.0e4),
    "deg": (-1.0e4, 1.0e4),
    "degc": (-273.15, 1.0e4),
    "k": (0.0, 1.0e4),
    "pa": (0.0, 1.0e9),
    "kpa": (0.0, 1.0e7),
    "bar": (0.0, 1.0e5),
    "w": (-1.0e9, 1.0e9),
    "j": (-1.0e9, 1.0e9),
    "a": (-1.0e6, 1.0e6),
    "v": (-1.0e6, 1.0e6),
    "hz": (0.0, 1.0e6),
    "1": (-1.0e3, 1.0e3),
}

_DEFAULT_LIMITS: Tuple[float, float] = (-1.0e9, 1.0e9)


def _normalise_unit(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    unit = unit.strip()
    if not unit:
        return None
    return unit.lower()


def _extract_unit(var) -> Optional[str]:
    # FMU scalar variables may expose units via "real", "declaredType", or
    # other typed attributes. We try each in turn.
    real = getattr(var, "real", None)
    if real is not None:
        unit = getattr(real, "unit", None)
        if unit:
            return unit
    declared_type = getattr(var, "declaredType", None)
    if declared_type is not None:
        unit = getattr(declared_type, "unit", None)
        if unit:
            return unit
    return None


def _build_metadata(model_description) -> Dict[str, VariableMetadata]:
    variables = {}
    for var in getattr(model_description, "modelVariables", []):
        variables[var.name] = VariableMetadata(
            name=var.name,
            causality=getattr(var, "causality", None),
            variability=getattr(var, "variability", None),
            var_type=str(getattr(var, "type", None)),
            unit=_extract_unit(var),
        )
    return variables


def _get_limits(unit: Optional[str]) -> Tuple[float, float]:
    if unit is None:
        return _DEFAULT_LIMITS
    unit_key = _normalise_unit(unit)
    if unit_key is None:
        return _DEFAULT_LIMITS
    return _UNIT_LIMITS.get(unit_key, _DEFAULT_LIMITS)


def _ensure_finite(values: np.ndarray, label: str) -> None:
    if not np.all(np.isfinite(values)):
        raise SimulationValidationError(
            f"Non-finite values detected for '{label}'."
        )


def _check_range(values: np.ndarray, label: str, unit: Optional[str]) -> None:
    lower, upper = _get_limits(unit)
    if values.size == 0:
        raise SimulationValidationError(f"Simulation returned no samples for '{label}'.")
    min_value = float(np.min(values))
    max_value = float(np.max(values))
    if min_value < lower or max_value > upper:
        readable_unit = unit or "dimensionless"
        raise SimulationValidationError(
            f"Values for '{label}' with unit '{readable_unit}' fall outside realistic bounds "
            f"[{lower}, {upper}]."
        )


def validate_simulation_output(result: np.ndarray, model_description) -> None:
    """Validate simulation results before returning them to the client.

    The validation performs three categories of checks:
      * Structural checks (time monotonicity and presence of samples).
      * Unit availability and value range plausibility.
      * Numerical sanity (no NaNs or infinities).

    Args:
        result: Structured numpy array returned by :func:`fmpy.simulate_fmu`.
        model_description: FMU model description for metadata lookup.

    Raises:
        SimulationValidationError: If any validation step fails.
    """
    if result.size == 0:
        raise SimulationValidationError("Simulation produced no samples.")

    names = result.dtype.names
    if not names:
        raise SimulationValidationError("Simulation result did not contain any variables.")

    metadata = _build_metadata(model_description)

    if "time" in names:
        time_values = result["time"]
        _ensure_finite(time_values, "time")
        if time_values.size == 0:
            raise SimulationValidationError("Simulation produced no time samples.")
        if not np.all(np.diff(time_values) >= 0):
            raise SimulationValidationError("Time vector is not monotonically increasing.")
        _check_range(time_values, "time", metadata.get("time", VariableMetadata("time", None, None, None, "s")).unit)

    for name in names:
        if name == "time":
            continue
        values = result[name]
        _ensure_finite(values, name)
        var_meta = metadata.get(name)
        unit = var_meta.unit if var_meta else None
        _check_range(values, name, unit)

        # Parameters are expected to remain effectively constant across the
        # simulation horizon. Detecting large deviations helps catch unit
        # mismatches that manifest as drifting parameters.
        if var_meta and var_meta.causality == "parameter":
            if np.ptp(values) > 1e-6 * max(1.0, abs(float(values[0]))):
                raise SimulationValidationError(
                    f"Parameter '{name}' unexpectedly varies over time, indicating a potential unit mismatch."
                )

    # Everything passed.
    return None
