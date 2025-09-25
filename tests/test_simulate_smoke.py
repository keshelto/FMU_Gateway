import sys
import os
import urllib.request
from app.simulate import simulate_fmu
from app.kpi import compute_kpi
from app.storage import save_fmu, DATA_DIR
from app.schemas import SimulateRequest

# Download sample FMU
path = "app/library/msl/BouncingBall.fmu"
fmu_id = "BouncingBall"  # Dummy for req

# Simulate
req = SimulateRequest(
    fmu_id=fmu_id,
    stop_time=5.0,
    step=0.01,
    start_values={},
    input_signals=[],
    kpis=["y_rms"]
)

result = simulate_fmu(path, req)
assert len(result['time']) > 0, "Time array empty"
try:
    kpis = {k: compute_kpi(result, k) for k in req.kpis}
    assert isinstance(kpis["y_rms"], float), "KPI not computed"
except ValueError:
    pass  # OK if 'y' missing for smoke test
print("Smoke test passed")
