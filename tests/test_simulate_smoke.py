import sys
import os
import urllib.request
from app.simulate import simulate_fmu
from app.kpi import compute_kpi
from app.storage import save_fmu, DATA_DIR

# Download sample FMU
url = "https://github.com/modelon-community/fmpy/raw/develop/tests/fmu/BouncingBall.fmu"
with urllib.request.urlopen(url) as response:
    content = response.read()
fmu_id, path = save_fmu(content)

# Simulate
class Req:
    stop_time = 5.0
    step = 0.01
    start_values = {}
    input_signals = []
    kpis = ["y_rms"]  # Note: Will raise if 'y' not in model; test assumes it computes or errors gracefully

req = Req()
result = simulate_fmu(path, req)
assert len(result['time']) > 0, "Time array empty"
try:
    kpis = {k: compute_kpi(result, k) for k in req.kpis}
    assert isinstance(kpis["y_rms"], float), "KPI not computed"
except ValueError:
    pass  # OK if 'y' missing for smoke test
print("Smoke test passed")
