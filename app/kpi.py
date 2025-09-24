import numpy as np

def compute_kpi(result, kpi: str) -> float:
    if kpi == "y_rms":
        if "y" not in result.dtype.names:
            raise ValueError("Variable 'y' not found for y_rms KPI")
        values = result["y"]
        return np.sqrt(np.mean(np.square(values)))
    raise ValueError(f"Unknown KPI: {kpi}")
