#!/usr/bin/env python3
"""Oil system balance workflow for FMU Gateway customer agents."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:  # Optional dependency, only used when available
    import requests  # type: ignore
except Exception:  # pragma: no cover - network libs optional
    requests = None  # type: ignore

DATA_FILE = Path(__file__).with_name("oil_system_dynamic_simulation.csv")
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "outputs"
DEFAULT_GATEWAY_URL = "http://localhost:8000"
REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "run_fmu_simulation.py"
LIBRARY_FMU = REPO_ROOT / "app" / "library" / "msl" / "BouncingBall.fmu"
CSV_SAVED_PATTERN = re.compile(r"✓ CSV saved to:\s*(?P<path>.+)")

RPM_BANDS = [
    ("idle", 0, 1500),
    ("low", 1500, 3000),
    ("cruise", 3000, 5000),
    ("high", 5000, 7000),
    ("redline", 7000, math.inf),
]


@dataclass
class OilSystemPoint:
    time_s: float
    engine_rpm: float
    tank_oil_volume_l: float


def _skip_blank_headers(csv_file) -> None:
    """Advance file handle until a non-empty row appears."""
    while True:
        position = csv_file.tell()
        line = csv_file.readline()
        if not line:
            break
        if line.strip():
            csv_file.seek(position)
            break


def load_records(data_file: Path = DATA_FILE) -> List[OilSystemPoint]:
    if not data_file.exists():
        raise FileNotFoundError(f"Missing data file: {data_file}")

    records: List[OilSystemPoint] = []
    with open(data_file, newline="") as csv_file:
        _skip_blank_headers(csv_file)
        reader = csv.DictReader(csv_file, skipinitialspace=True)
        for row in reader:
            if not row:
                continue
            try:
                records.append(
                    OilSystemPoint(
                        time_s=float(row["time_s"]),
                        engine_rpm=float(row["engine_rpm"]),
                        tank_oil_volume_l=float(row["tank_oil_volume_L"]),
                    )
                )
            except (TypeError, ValueError):  # pragma: no cover - defensive parsing
                continue
    return records


def check_gateway_health(gateway_url: str = DEFAULT_GATEWAY_URL) -> Dict[str, Optional[str]]:
    """Check whether a local FMU Gateway is reachable."""
    if requests is None:
        return {"status": "unknown", "error": "requests library unavailable"}

    try:
        response = requests.get(f"{gateway_url.rstrip('/')}/health", timeout=3)
        response.raise_for_status()
        payload = response.json()
        return {"status": "online", "version": payload.get("version")}
    except Exception as exc:  # pragma: no cover - network best effort
        return {"status": "offline", "error": str(exc)}


def _execute_runner(
    fmu_path: Path,
    *,
    quote_only: bool = False,
    payment_token: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Invoke ``run_fmu_simulation.py`` and capture useful metadata."""

    if not RUNNER_PATH.exists():
        return {"status": "error", "reason": "run_fmu_simulation.py not found"}

    if not fmu_path.exists():
        return {"status": "error", "reason": f"FMU missing: {fmu_path}"}

    cmd = [
        sys.executable,
        str(RUNNER_PATH),
        "--auto",
        "--fmu",
        str(fmu_path),
    ]

    if quote_only:
        cmd.append("--quote")
    if payment_token:
        cmd.extend(["--payment-token", payment_token])
    if payment_method:
        cmd.extend(["--payment-method", payment_method])

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "status": "failed",
            "returncode": str(exc.returncode),
            "stdout": exc.stdout.strip() or None,
            "stderr": exc.stderr.strip() or None,
        }

    info: Dict[str, Optional[str]] = {
        "status": "ok",
        "stdout": completed.stdout.strip() or None,
    }

    if completed.stderr:
        info["stderr"] = completed.stderr.strip()

    match = CSV_SAVED_PATTERN.search(completed.stdout)
    if match:
        info["csv_path"] = match.group("path").strip()

    return info


def attempt_payment_quote(
    *,
    fmu_path: Path = LIBRARY_FMU,
    payment_token: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Run the CLI in quote mode to exercise the payment handshake."""

    return _execute_runner(
        fmu_path,
        quote_only=True,
        payment_token=payment_token,
        payment_method=payment_method,
    )


def run_gateway_simulation(
    fmu_path: Path,
    *,
    payment_token: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Execute an FMU through the gateway and capture the saved results."""

    return _execute_runner(
        fmu_path,
        quote_only=False,
        payment_token=payment_token,
        payment_method=payment_method,
    )


def _band_for_rpm(rpm: float) -> str:
    for name, lower, upper in RPM_BANDS:
        if lower <= rpm < upper:
            return name
    return RPM_BANDS[-1][0]


def build_summary(
    records: List[OilSystemPoint],
    data_source: Dict[str, Optional[str]],
    gateway_info: Dict[str, Optional[str]],
    quote_attempt: Dict[str, Optional[str]],
    simulation_info: Dict[str, Optional[str]],
) -> Dict:
    if not records:
        raise ValueError("No simulation records to analyse")

    duration_s = records[-1].time_s - records[0].time_s if len(records) > 1 else 0.0
    rpm_values = [pt.engine_rpm for pt in records]
    volume_values = [pt.tank_oil_volume_l for pt in records]

    dt_values = [
        curr.time_s - prev.time_s
        for prev, curr in zip(records, records[1:])
        if curr.time_s >= prev.time_s
    ]
    mean_step = statistics.mean(dt_values) if dt_values else 0.0
    max_step = max(dt_values) if dt_values else 0.0

    rpm_band_time: Counter[str] = Counter()
    total_band_time = 0.0
    for prev, curr in zip(records, records[1:]):
        dt = curr.time_s - prev.time_s
        if dt <= 0:
            continue
        rpm_band_time[_band_for_rpm(curr.engine_rpm)] += dt
        total_band_time += dt

    def _fraction(seconds: float) -> float:
        return (seconds / total_band_time) if total_band_time else 0.0

    rpm_change_rates: List[float] = []
    for prev, curr in zip(records, records[1:]):
        dt = curr.time_s - prev.time_s
        if dt <= 0:
            continue
        rpm_change_rates.append((curr.engine_rpm - prev.engine_rpm) / dt)
    max_ramp = max((abs(rate) for rate in rpm_change_rates), default=0.0)
    median_ramp = statistics.median(rpm_change_rates) if rpm_change_rates else 0.0

    volume_deltas = [curr - prev for prev, curr in zip(volume_values, volume_values[1:])]
    max_drop = min(volume_deltas) if volume_deltas else 0.0
    max_rise = max(volume_deltas) if volume_deltas else 0.0

    summary = {
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "data_source": data_source,
        "gateway": gateway_info,
        "points": len(records),
        "duration_s": round(duration_s, 3),
        "time_step_s": {
            "mean": round(mean_step, 6),
            "max": round(max_step, 6),
        },
        "engine_rpm": {
            "min": min(rpm_values),
            "max": max(rpm_values),
            "mean": statistics.mean(rpm_values),
            "median": statistics.median(rpm_values),
            "band_durations_s": {band: round(seconds, 3) for band, seconds in rpm_band_time.items()},
            "band_fraction": {band: round(_fraction(seconds), 3) for band, seconds in rpm_band_time.items()},
            "max_ramp_rpm_per_s": round(max_ramp, 2),
            "median_ramp_rpm_per_s": round(median_ramp, 2),
        },
        "tank_volume_l": {
            "min": min(volume_values),
            "max": max(volume_values),
            "mean": statistics.mean(volume_values),
            "stdev": statistics.pstdev(volume_values),
            "max_drop_per_step": round(max_drop, 6),
            "max_rise_per_step": round(max_rise, 6),
        },
        "quote_attempt": quote_attempt,
        "simulation": simulation_info,
    }

    if summary["tank_volume_l"]["min"] > 0:
        summary["tank_volume_l"]["relative_variation_pct"] = round(
            (summary["tank_volume_l"]["max"] - summary["tank_volume_l"]["min"]) / summary["tank_volume_l"]["min"] * 100.0,
            3,
        )
    else:
        summary["tank_volume_l"]["relative_variation_pct"] = 0.0

    if summary["tank_volume_l"]["min"] >= 6.0:
        summary["assessment"] = (
            "Oil tank volume remained at or above 6 L throughout the transient; "
            "no starvation risk observed during the 8 s sweep."
        )
    else:
        summary["assessment"] = (
            "Oil volume dipped below the 6 L safety margin; investigate return flow capacity."
        )

    return summary


def write_outputs(summary: Dict, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    output_dir.mkdir(exist_ok=True)
    json_path = output_dir / "oil_system_balance_summary.json"
    md_path = output_dir / "oil_system_balance_summary.md"

    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    lines = [
        "# Oil System Balance Summary",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Data points analysed: {summary['points']}",
        f"- Simulation duration: {summary['duration_s']:.3f} s",
    ]

    data_source = summary.get("data_source", {})
    source_desc = data_source.get("description") or data_source.get("type")
    if source_desc:
        lines.append(f"- Data source: {source_desc}")
    if data_source.get("path"):
        lines.append(f"- Data path: {data_source['path']}")

    gateway = summary.get("gateway", {})
    lines.append(f"- Gateway status: {gateway.get('status', 'unknown')}")
    if gateway.get("version"):
        lines.append(f"- Gateway version: {gateway['version']}")
    if gateway.get("error"):
        lines.append(f"- Gateway error: {gateway['error']}")

    rpm_info = summary["engine_rpm"]
    volume_info = summary["tank_volume_l"]

    lines.extend(
        [
            "",
            "## Engine Speed Profile",
            f"- RPM range: {rpm_info['min']:.0f} – {rpm_info['max']:.0f} rpm",
            f"- Mean / median RPM: {rpm_info['mean']:.0f} / {rpm_info['median']:.0f} rpm",
            f"- Max ramp rate: {rpm_info['max_ramp_rpm_per_s']:.0f} rpm/s",
            "",
            "### Time spent per band",
        ]
    )

    for band in (band for band, *_ in RPM_BANDS if band in rpm_info["band_durations_s"]):
        duration = rpm_info["band_durations_s"][band]
        fraction = rpm_info["band_fraction"][band]
        lines.append(f"- {band.title()} band: {duration:.3f} s ({fraction*100:.1f} % of runtime)")

    lines.extend(
        [
            "",
            "## Oil Volume Findings",
            f"- Volume range: {volume_info['min']:.2f} – {volume_info['max']:.2f} L",
            f"- Mean volume: {volume_info['mean']:.2f} L",
            f"- Step-wise variation: Δmin {volume_info['max_drop_per_step']:.6f} L / Δmax {volume_info['max_rise_per_step']:.6f} L",
            f"- Relative variation: {volume_info['relative_variation_pct']:.3f} %",
            "",
            "## Assessment",
            summary.get("assessment", "No assessment available."),
            "",
            "## Payment & Gateway Exercise",
        ]
    )

    quote = summary.get("quote_attempt", {})
    lines.append(f"- Quote status: {quote.get('status', 'unknown')}")
    if quote.get("returncode"):
        lines.append(f"- CLI return code: {quote['returncode']}")
    if quote.get("stdout"):
        lines.append("- CLI stdout preview:\n")
        lines.append("```")
        lines.extend(quote["stdout"].splitlines())
        lines.append("```")
    if quote.get("stderr"):
        lines.append("- CLI stderr preview:\n")
        lines.append("```")
        lines.extend(quote["stderr"].splitlines())
        lines.append("```")

    simulation = summary.get("simulation", {})
    if simulation:
        lines.append("")
        lines.append("### Latest Gateway Simulation")
        lines.append(f"- Simulation status: {simulation.get('status', 'unknown')}")
        if simulation.get("csv_path"):
            lines.append(f"- Result CSV: {simulation['csv_path']}")
        if simulation.get("stdout"):
            lines.append("- Runner stdout preview:\n")
            lines.append("```")
            lines.extend(simulation["stdout"].splitlines())
            lines.append("```")
        if simulation.get("stderr"):
            lines.append("- Runner stderr preview:\n")
            lines.append("```")
            lines.extend(simulation["stderr"].splitlines())
            lines.append("```")

    lines.extend(
        [
            "",
            "## Next Steps",
            "1. Ensure the FMU Gateway is running and that your agent holds a valid API key/payment method.",
            "2. Re-run this helper with `--simulate-fmu /path/to/OilSystem.fmu` to produce a fresh validated data set (add `--quote-only` to capture the 402 payload only).",
            "3. Supply the authorised `--payment-token`/`--payment-method` pair from the customer's wallet when executing the paid run.",
            "4. Share the regenerated Markdown brief and JSON summary with the customer.",
        ]
    )

    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--online",
        action="store_true",
        help=(
            "Attempt to reach a running FMU Gateway instance and rehearse the "
            "payment quote handshake."
        ),
    )
    parser.add_argument(
        "--gateway-url",
        default=DEFAULT_GATEWAY_URL,
        help="Gateway base URL to probe when --online is provided",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write the Markdown and JSON summaries",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DATA_FILE,
        help="Time history CSV produced by a validated FMU Gateway run",
    )
    parser.add_argument(
        "--simulate-fmu",
        type=Path,
        help=(
            "FMU to execute through the gateway before analysis. The resulting "
            "CSV will replace --input-csv when the run succeeds."
        ),
    )
    parser.add_argument(
        "--quote-only",
        action="store_true",
        help="Request a payment quote instead of running the FMU when --simulate-fmu is supplied",
    )
    parser.add_argument(
        "--payment-token",
        type=str,
        help="Payment token authorised by the customer's wallet",
    )
    parser.add_argument(
        "--payment-method",
        type=str,
        help="Payment method identifier associated with --payment-token",
    )
    parser.add_argument(
        "--quote-fmu",
        type=Path,
        default=LIBRARY_FMU,
        help="FMU used when rehearsing the quote flow via --online",
    )

    args = parser.parse_args(argv)

    data_file = args.input_csv
    data_source: Dict[str, Optional[str]] = {
        "type": "archived_dataset" if data_file == DATA_FILE else "user_supplied_dataset",
        "path": str(data_file.resolve()) if data_file.exists() else str(data_file),
    }
    if data_file == DATA_FILE:
        data_source["description"] = "Packaged FMU Gateway oil system run (validated snapshot)"

    gateway_info = {"status": "skipped", "reason": "no online checks requested"}
    quote_attempt = {"status": "skipped", "reason": "no quote requested"}
    simulation_info = {"status": "skipped", "reason": "no gateway simulation requested"}

    needs_gateway_probe = args.online or args.simulate_fmu is not None or args.quote_only
    if needs_gateway_probe:
        gateway_info = check_gateway_health(args.gateway_url)

    if args.quote_only and args.simulate_fmu:
        quote_attempt = attempt_payment_quote(
            fmu_path=args.simulate_fmu,
            payment_token=args.payment_token,
            payment_method=args.payment_method,
        )
    elif args.quote_only:
        quote_attempt = {"status": "error", "reason": "--quote-only requires --simulate-fmu"}
    elif args.online:
        quote_attempt = attempt_payment_quote(
            fmu_path=args.quote_fmu,
            payment_token=args.payment_token,
            payment_method=args.payment_method,
        )

    if args.simulate_fmu and not args.quote_only:
        simulation_info = run_gateway_simulation(
            args.simulate_fmu,
            payment_token=args.payment_token,
            payment_method=args.payment_method,
        )
        if simulation_info.get("csv_path"):
            data_file = Path(simulation_info["csv_path"]).expanduser().resolve()
            data_source = {
                "type": "gateway_simulation",
                "path": str(data_file),
                "description": f"Fresh FMU Gateway run of {args.simulate_fmu.name}",
            }
        else:
            simulation_info.setdefault("reason", "gateway run did not emit a CSV path")

    try:
        records = load_records(data_file)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    summary = build_summary(records, data_source, gateway_info, quote_attempt, simulation_info)
    write_outputs(summary, args.output_dir)

    print("Generated:")
    print(f"  - {args.output_dir / 'oil_system_balance_summary.json'}")
    print(f"  - {args.output_dir / 'oil_system_balance_summary.md'}")


if __name__ == "__main__":
    main()
