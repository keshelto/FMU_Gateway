#!/usr/bin/env python3
"""Turbo spool-up walkthrough for FMU Gateway agents."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EXAMPLE_DIR = Path(__file__).parent
REPO_ROOT = EXAMPLE_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from fmu_gateway_sdk.enhanced_client import (
    EnhancedFMUGatewayClient,
    SimulateRequest,
)

CONFIG_PATH = EXAMPLE_DIR / "turbo_spool_config.json"
OUTPUT_DIR = EXAMPLE_DIR / "output"
LOCAL_TURBO_FMU = EXAMPLE_DIR / "TurboSpoolUp.fmu"
KEY_FILE = Path.home() / ".fmu_gateway_key"


def load_config() -> Dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Configuration file missing: {CONFIG_PATH}")
    with CONFIG_PATH.open() as f:
        return json.load(f)


def ensure_gateway_client(gateway_url: Optional[str]) -> EnhancedFMUGatewayClient:
    client = EnhancedFMUGatewayClient(gateway_url=gateway_url or "auto")
    if not client.gateway_url:
        raise SystemExit(
            "No FMU Gateway detected. Start a local instance or pass --gateway-url."
        )
    return client


def ensure_api_key(client: EnhancedFMUGatewayClient) -> str:
    if KEY_FILE.exists():
        cached = KEY_FILE.read_text().strip()
        if cached:
            client.api_key = cached
            client.session.headers['Authorization'] = f'Bearer {cached}'
            try:
                response = client.session.get(f"{client.gateway_url}/library", timeout=5)
                if response.status_code == 401:
                    raise ValueError("cached key rejected")
                return cached
            except Exception:
                pass
    return client.create_api_key(save_to_file=True, key_path=KEY_FILE)


def choose_fmu(client: EnhancedFMUGatewayClient) -> Tuple[str, str]:
    """Return (fmu_id, human_readable_name)."""
    if LOCAL_TURBO_FMU.exists():
        meta = client.upload_fmu_smart(LOCAL_TURBO_FMU)
        return meta['id'], meta.get('model_name', LOCAL_TURBO_FMU.stem)
    config = load_config()
    return config['fmu_id'], config['fmu_id']


def simulate(client: EnhancedFMUGatewayClient, fmu_id: str, config: Dict) -> Dict:
    request = SimulateRequest(
        fmu_id=fmu_id,
        stop_time=config.get('stop_time', 3.0),
        step=config.get('step', 0.001),
        start_values=config.get('start_values', {}),
        input_signals=config.get('input_signals', []),
        kpis=config.get('kpis', []),
    )
    return client.simulate(request)


def compute_metrics(time: List[float], signal: List[float], *,
                    threshold: float, settling_band: float) -> Dict[str, Optional[float]]:
    if not time or not signal:
        return {"spool_time_95": None, "settling_time": None, "peak_speed": None, "overshoot": None}

    absolute_signal = [abs(v) for v in signal]
    peak_speed = max(absolute_signal)
    final_value = sum(absolute_signal[-10:]) / min(len(absolute_signal), 10)

    spool_time = None
    target_value = threshold * peak_speed
    for t, value in zip(time, absolute_signal):
        if value >= target_value:
            spool_time = t
            break

    overshoot = peak_speed - final_value

    settling_time = None
    if final_value > 0:
        band = settling_band * final_value
        for idx, t in enumerate(time):
            window = absolute_signal[idx:]
            if all(abs(v - final_value) <= band for v in window):
                settling_time = t
                break

    return {
        "spool_time_95": spool_time,
        "settling_time": settling_time,
        "peak_speed": peak_speed,
        "overshoot": overshoot,
    }


def save_outputs(result: Dict, metrics: Dict[str, Optional[float]]):
    OUTPUT_DIR.mkdir(exist_ok=True)

    metrics_path = OUTPUT_DIR / "metrics.json"
    with metrics_path.open('w') as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")

    csv_path = OUTPUT_DIR / "timeseries.csv"
    time_points = result.get('t', [])
    variables = result.get('y', {})
    max_points = 500
    indices: List[int]
    if len(time_points) > max_points:
        stride = max(1, len(time_points) // max_points)
        indices = list(range(0, len(time_points), stride))
        if indices[-1] != len(time_points) - 1:
            indices.append(len(time_points) - 1)
    else:
        indices = list(range(len(time_points)))

    with csv_path.open('w', newline='') as f:
        writer = csv.writer(f)
        header = ['time'] + list(variables.keys())
        writer.writerow(header)
        for idx in indices:
            row = [time_points[idx]] + [variables[name][idx] for name in variables.keys()]
            writer.writerow(row)

    summary_path = OUTPUT_DIR / "summary.json"
    summary = {
        "gateway": result.get('id'),
        "status": result.get('status'),
        "kpis": result.get('kpis', {}),
        "provenance": result.get('provenance', {}),
        "metrics": metrics,
    }
    with summary_path.open('w') as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    return metrics_path, csv_path, summary_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway-url', help='Override automatic gateway detection')
    args = parser.parse_args()

    config = load_config()
    client = ensure_gateway_client(args.gateway_url)
    api_key = ensure_api_key(client)

    print(f"✓ Using gateway: {client.gateway_url}")
    print(f"✓ API key ready: {api_key[:8]}…")

    fmu_id, label = choose_fmu(client)
    print(f"✓ Selected FMU: {label} ({fmu_id})")

    result = simulate(client, fmu_id, config)
    analysis_var = config.get('analysis_variable', 'v')
    variable = result.get('y', {}).get(analysis_var)
    if variable is None:
        raise SystemExit(f"Variable '{analysis_var}' not found in simulation output")

    metrics = compute_metrics(
        result.get('t', []),
        variable,
        threshold=config.get('spool_threshold', 0.95),
        settling_band=config.get('settling_band', 0.02),
    )

    metrics_path, csv_path, summary_path = save_outputs(result, metrics)

    print("\n=== Turbo Spool Metrics ===")
    for key, value in metrics.items():
        if value is None:
            print(f"- {key}: not available")
        else:
            print(f"- {key}: {value:.4f}")

    print("\nArtifacts saved:")
    print(f"- {metrics_path}")
    print(f"- {csv_path}")
    print(f"- {summary_path}")


if __name__ == "__main__":
    main()
