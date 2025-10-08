#!/usr/bin/env python3
"""Scavenge pump capacity workflow for FMU Gateway customer agents."""
from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests

DATA_FILE = Path(__file__).with_name("scavenge_pump_capacity_simulation.csv")
OUTPUT_DIR = Path(__file__).parent / "outputs"
DEFAULT_GATEWAY_URL = "http://localhost:8000"


@dataclass
class ScavengeRecord:
    engine_speed_rpm: float
    pressure_flow_lpm: float
    scavenge_flow_lpm: float
    pump_speed_rpm: float
    displacement_l_per_rev: float
    displacement_cm3_per_rev: float

    @property
    def flow_ratio(self) -> float:
        if self.pressure_flow_lpm == 0:
            return 0.0
        return self.scavenge_flow_lpm / self.pressure_flow_lpm


def check_gateway_health(gateway_url: str = DEFAULT_GATEWAY_URL) -> Dict[str, Optional[str]]:
    """Return gateway health information for reporting."""
    try:
        response = requests.get(f"{gateway_url.rstrip('/')}/health", timeout=3)
        response.raise_for_status()
        data = response.json()
        return {"status": "online", "version": data.get("version")}
    except Exception as exc:  # pragma: no cover - informational only
        return {"status": "offline", "error": str(exc)}


def load_records() -> List[ScavengeRecord]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Missing data file: {DATA_FILE}")

    records: List[ScavengeRecord] = []
    with open(DATA_FILE, newline="") as csv_file:
        # Skip any blank header rows (common in exported spreadsheets)
        while True:
            position = csv_file.tell()
            line = csv_file.readline()
            if not line:
                break
            if line.strip():
                csv_file.seek(position)
                break
        reader = csv.DictReader(csv_file, skipinitialspace=True)
        for row in reader:
            if not row:
                continue
            records.append(
                ScavengeRecord(
                    engine_speed_rpm=float(row["engine_speed_rpm"]),
                    pressure_flow_lpm=float(row["pressure_flow_L_per_min"]),
                    scavenge_flow_lpm=float(row["scavenge_flow_L_per_min"]),
                    pump_speed_rpm=float(row["pump_speed_rpm"]),
                    displacement_l_per_rev=float(row["displacement_L_per_rev"]),
                    displacement_cm3_per_rev=float(row["displacement_cm3_per_rev"]),
                )
            )
    return records


def build_summary(records: List[ScavengeRecord], gateway_info: Dict[str, Optional[str]]) -> Dict:
    ratios = [rec.flow_ratio for rec in records]
    displacement_cm3 = [rec.displacement_cm3_per_rev for rec in records]

    generated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    summary = {
        "generated_at": generated_at,
        "gateway": gateway_info,
        "points": len(records),
        "engine_speed_range_rpm": {
            "min": min(rec.engine_speed_rpm for rec in records),
            "max": max(rec.engine_speed_rpm for rec in records),
        },
        "scavenge_to_pressure_ratio": {
            "mean": statistics.mean(ratios),
            "min": min(ratios),
            "max": max(ratios),
        },
        "pump_displacement_cm3_per_rev": {
            "mean": statistics.mean(displacement_cm3),
            "min": min(displacement_cm3),
            "max": max(displacement_cm3),
        },
        "recommended_margin_ratio": round(statistics.mean(ratios) * 1.1, 3),
        "micropayment_quote": {
            "status": "quote_only",
            "price_usd": 0.01,
            "instructions": "Use --payment-token and --payment-method with run_fmu_simulation.py to authorize execution",
        },
    }
    return summary


def write_outputs(summary: Dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / "scavenge_capacity_summary.json"
    md_path = OUTPUT_DIR / "scavenge_capacity_summary.md"

    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    lines = [
        "# Scavenge Pump Capacity Summary",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Gateway status: {summary['gateway']['status']}",
    ]
    if summary['gateway'].get('version'):
        lines.append(f"- Gateway version: {summary['gateway']['version']}")
    if summary['gateway'].get('error'):
        lines.append(f"- Gateway error: {summary['gateway']['error']}")

    ratio = summary["scavenge_to_pressure_ratio"]
    displacement = summary["pump_displacement_cm3_per_rev"]

    lines.extend(
        [
            "",
            "## Key Ratios",
            f"- Mean scav/press ratio: {ratio['mean']:.3f}",
            f"- Range: {ratio['min']:.3f} – {ratio['max']:.3f}",
            "",
            "## Pump Displacement",
            f"- Mean: {displacement['mean']:.2f} cm^3/rev",
            f"- Range: {displacement['min']:.2f} – {displacement['max']:.2f} cm^3/rev",
            "",
            "## Revenue Hooks",
            f"- Quote amount: ${summary['micropayment_quote']['price_usd']:.2f}",
            "- Prompt agents to upsell logged data exports after payment authorization.",
        ]
    )

    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✓ Summary JSON written to {json_path}")
    print(f"✓ Markdown brief written to {md_path}")


def main():
    gateway_info = check_gateway_health()
    records = load_records()
    summary = build_summary(records, gateway_info)
    write_outputs(summary)
    print("\nScavenge pump capacity analysis complete. Use the quote data to trigger payment in your agent workflows.")


if __name__ == "__main__":
    main()
