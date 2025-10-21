import pytest

from main import run_simulation


def test_gateway_required():
    with pytest.raises(RuntimeError):
        run_simulation({"use_gateway": False, "fmu_path": "demo.fmu"})
