import numpy as np
from fmpy import simulate_fmu

def simulate_fmu(path: str, req):
    inputs = None
    if req.input_signals:
        signals = req.input_signals
        if not signals:
            raise ValueError("Empty input signals")
        t = np.array(signals[0]['t'])
        for sig in signals:
            if not np.all(np.diff(sig['t']) > 0):
                raise ValueError("Time must be monotonic increasing")
            if len(sig['t']) != len(sig['u']):
                raise ValueError("Time and value lengths must match")
            if not np.array_equal(t, sig['t']):
                raise ValueError("All inputs must share the same time vector")
        names = [sig['name'] for sig in signals]
        matrix = np.column_stack([t] + [sig['u'] for sig in signals])
        inputs = (np.array(names), matrix)
    return simulate_fmu(
        path,
        start_time=0,
        stop_time=req.stop_time,
        step_size=req.step,
        start_values=req.start_values,
        input=inputs,
        timeout=20
    )
