import numpy as np


def compute_kpi(result, kpi: str) -> float:
    if kpi.endswith("_rms"):
        variable = kpi[:-4]
        if variable not in result.dtype.names:
            raise ValueError(f"Variable '{variable}' not found for {kpi} KPI")
        values = result[variable]
        return float(np.sqrt(np.mean(np.square(values))))
    raise ValueError(f"Unknown KPI: {kpi}")
