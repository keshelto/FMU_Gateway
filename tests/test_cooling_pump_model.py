import pytest

from models.examples.cooling_pump.model import CoolingPumpInputError, run


def test_run_returns_expected_outputs():
    result = run({"heat_rejection": 100.0, "delta_t": 10.0})

    assert result["mass_flow"] == pytest.approx(2.3923444976)
    assert result["volume_flow_lpm"] == pytest.approx(143.540669856)


def test_run_rejects_out_of_range_inputs():
    with pytest.raises(CoolingPumpInputError):
        run({"heat_rejection": 1200.0, "delta_t": 10.0})

    with pytest.raises(CoolingPumpInputError):
        run({"heat_rejection": 100.0, "delta_t": 0.5})


def test_run_requires_expected_fields():
    with pytest.raises(CoolingPumpInputError):
        run({"heat_rejection": 100.0})
