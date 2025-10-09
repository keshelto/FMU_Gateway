import numpy as np
import pytest

from app.validation import SimulationValidationError, validate_simulation_output


class DummyReal:
    def __init__(self, unit=None):
        self.unit = unit


class DummyVar:
    def __init__(self, name, unit=None, causality="output"):
        self.name = name
        self.causality = causality
        self.variability = "continuous"
        self.type = "Float64"
        self.real = DummyReal(unit)
        self.declaredType = None


class DummyModelDescription:
    def __init__(self, variables):
        self.modelVariables = variables


def test_validate_simulation_output_allows_reasonable_values():
    result = np.array([(0.0, 10.0), (1.0, 20.0)], dtype=[("time", "f8"), ("speed", "f8")])
    meta = DummyModelDescription([
        DummyVar("time", unit="s"),
        DummyVar("speed", unit="m/s"),
    ])
    validate_simulation_output(result, meta)


def test_validate_simulation_output_rejects_unrealistic_values():
    result = np.array([(0.0, 5.0e4)], dtype=[("time", "f8"), ("speed", "f8")])
    meta = DummyModelDescription([
        DummyVar("time", unit="s"),
        DummyVar("speed", unit="m/s"),
    ])
    with pytest.raises(SimulationValidationError):
        validate_simulation_output(result, meta)


def test_validate_simulation_output_rejects_non_monotonic_time():
    result = np.array([(0.0, 1.0), (0.5, 2.0), (0.4, 3.0)], dtype=[("time", "f8"), ("speed", "f8")])
    meta = DummyModelDescription([
        DummyVar("time", unit="s"),
        DummyVar("speed", unit="m/s"),
    ])
    with pytest.raises(SimulationValidationError):
        validate_simulation_output(result, meta)


def test_validate_simulation_output_flags_parameter_variation():
    result = np.array([(0.0, 1.0), (1.0, 2.0)], dtype=[("time", "f8"), ("mass", "f8")])
    meta = DummyModelDescription([
        DummyVar("time", unit="s"),
        DummyVar("mass", unit="kg", causality="parameter"),
    ])
    with pytest.raises(SimulationValidationError):
        validate_simulation_output(result, meta)
