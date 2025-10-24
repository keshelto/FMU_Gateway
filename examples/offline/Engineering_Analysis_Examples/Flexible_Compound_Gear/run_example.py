"""Offline helper for the flexible compound gear friction ring study.

The surrogate follows the variable flow outlined in the customer brief so that
agents can rehearse the workflow, generate the deliverables, and brief
stakeholders even when the paid FMU Gateway run is unavailable.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import itertools
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class DrivePoint:
    time: float
    engine_speed_rpm: float
    cam_torque: float
    oil_temperature: float
    oil_viscosity: float


@dataclasses.dataclass
class SimulationConfig:
    mu_lubricated: float
    mu_viscous: float
    mu_temperature_slope: float
    mu_temperature_quadratic: float
    mu_boundary: float
    stribeck_velocity: float
    preload_scale: float
    h_oil: float
    oil_temperature_bias: float = 0.0


@dataclasses.dataclass
class MaterialProperties:
    rho_ring: float = 8250.0  # kg/m3
    cp_ring: float = 420.0  # J/kg-K
    k_ring: float = 120.0  # W/m-K
    rho_steel: float = 7850.0
    cp_steel: float = 460.0
    k_steel: float = 45.0
    hardness_ref: float = 1050e6  # Pa
    hardness_temp_slope: float = -1.8e6
    wear_coeff_base: float = 1.8e-8
    wear_coeff_activation: float = 210.0


@dataclasses.dataclass
class Geometry:
    ring_radius: float = 0.045
    ring_width: float = 0.014
    ring_thickness: float = 0.003
    contact_radius: float = 0.012
    contact_area: float = math.pi * contact_radius ** 2
    thermal_mass_ring: float = 0.45
    thermal_mass_steel: float = 2.0
    contact_resistance: float = 0.02  # K/W


@dataclasses.dataclass
class TorsionalParams:
    J_crank: float = 0.18
    J_cam: float = 0.12
    k_theta: float = 4200.0
    c_theta: float = 55.0
    gear_ratio: float = 2.0
    preload_nominal: float = 4200.0
    damping_loss_wear_threshold: float = 160e-6


@dataclasses.dataclass
class SimulationHistory:
    time: List[float]
    ring_bulk: List[float]
    steel_bulk: List[float]
    surface_peak: List[float]
    mu_effective: List[float]
    q_fric: List[float]
    wear_rate: List[float]
    wear_depth: List[float]
    friction_torque: List[float]
    slip_rate: List[float]


@dataclasses.dataclass
class Summary:
    peak_surface_temp: float
    peak_ring_temp: float
    duty_above_260: float
    duty_above_315: float
    duty_above_370: float
    mean_wear_rate: float
    final_wear_depth: float
    damping_loss_factor: float
    time_to_half_damping: float
    verdict: str


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def load_drive_cycle(path: Path) -> List[DrivePoint]:
    drive: List[DrivePoint] = []
    with path.open() as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            drive.append(
                DrivePoint(
                    time=float(row["time_s"]),
                    engine_speed_rpm=float(row["engine_speed_rpm"]),
                    cam_torque=float(row["cam_torque_Nm"]),
                    oil_temperature=float(row["oil_temperature_C"]),
                    oil_viscosity=float(row["oil_viscosity_cSt"]),
                )
            )
    return drive


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Surrogate FMU implementations
# ---------------------------------------------------------------------------


def simulate_run(
    drive: List[DrivePoint],
    config: SimulationConfig,
    torsion: TorsionalParams,
    geom: Geometry,
    material: MaterialProperties,
    gamma: float = 0.65,
) -> Tuple[SimulationHistory, Summary]:
    time: List[float] = []
    ring_bulk: List[float] = []
    steel_bulk: List[float] = []
    surface_peak: List[float] = []
    mu_effective: List[float] = []
    q_fric: List[float] = []
    wear_rate: List[float] = []
    wear_depth: List[float] = []
    friction_torque: List[float] = []
    slip_rate: List[float] = []

    T_ring = 110.0 + config.oil_temperature_bias
    T_steel = 105.0 + config.oil_temperature_bias
    T_surface = T_ring
    h_wear = 0.0
    damping_factor = 1.0

    dt_list = [drive[i + 1].time - drive[i].time for i in range(len(drive) - 1)]
    dt_list.append(dt_list[-1] if dt_list else 0.01)

    duty_total = sum(dt_list)
    time_above_260 = 0.0
    time_above_315 = 0.0
    time_above_370 = 0.0
    wear_integral = 0.0

    preload = torsion.preload_nominal * config.preload_scale
    h_area = 2 * math.pi * geom.ring_radius * geom.ring_width

    time_to_half_damping = math.inf

    prev_omega_crank = drive[0].engine_speed_rpm * 2 * math.pi / 60.0

    for i, point in enumerate(drive):
        dt = dt_list[i]
        omega_crank = point.engine_speed_rpm * 2 * math.pi / 60.0
        omega_cam_in = omega_crank / torsion.gear_ratio

        # Slip demand based on engine acceleration (torsional compliance surrogate)
        domega_input = (omega_crank - prev_omega_crank) / max(dt, 1e-6)
        base_slip = abs(domega_input) / torsion.gear_ratio * 0.05
        prev_omega_crank = omega_crank

        # Friction model
        # Use last surface temperature for temperature feedback
        v_slip = geom.ring_radius * base_slip
        v_abs = abs(v_slip)

        stribeck = config.mu_lubricated + (
            config.mu_boundary - config.mu_lubricated
        ) / (1.0 + (v_abs / max(config.stribeck_velocity, 1e-3)))
        delta_temp = clamp(T_surface - 120.0, -200.0, 400.0)
        mu_temp = 1.0 + config.mu_temperature_slope * delta_temp / 100.0
        mu_temp += config.mu_temperature_quadratic * delta_temp ** 2 / 10000.0
        mu_eff = clamp(stribeck * mu_temp + config.mu_viscous * v_abs, 0.02, 0.9)

        tau_capacity = mu_eff * preload * geom.ring_radius
        tau_required = point.cam_torque
        tau_transmitted = min(tau_required, tau_capacity)
        slip_excess = max(0.0, tau_required - tau_capacity)
        phi_rel_dot = max(1e-3, base_slip + slip_excess * 0.015)
        v_slip = geom.ring_radius * phi_rel_dot
        v_abs = abs(v_slip)

        # Friction power (signed)
        q_abs = min(abs(tau_transmitted * phi_rel_dot), 5.0e4)

        # Flash temperature model (very approximate but monotonic)
        v_effective = max(v_abs, 0.05)
        flash_ring = (
            gamma * q_abs / (math.pi * geom.contact_radius * v_effective * material.k_ring)
        )
        flash_ring = min(flash_ring, 250.0)
        flash_steel = (
            (1.0 - gamma) * q_abs / (math.pi * geom.contact_radius * v_effective * material.k_steel)
        )
        flash_steel = min(flash_steel, 120.0)

        # Thermal network (two node with contact resistance)
        m_ring = geom.thermal_mass_ring
        m_steel = geom.thermal_mass_steel
        conv_ring = config.h_oil * 1000.0 * h_area * (T_ring - point.oil_temperature)
        conduct = (T_ring - T_steel) / max(geom.contact_resistance, 1e-5)

        dT_ring = (
            gamma * q_abs
            - conv_ring
            - conduct
        ) / (m_ring * material.cp_ring)
        dT_steel = (
            (1.0 - gamma) * q_abs + conduct
        ) / (m_steel * material.cp_steel)

        T_ring += dT_ring * dt
        T_steel += dT_steel * dt
        T_ring = clamp(T_ring, point.oil_temperature - 40.0, 800.0)
        T_steel = clamp(T_steel, point.oil_temperature - 40.0, 800.0)
        T_surface = clamp(T_ring + flash_ring, point.oil_temperature, 900.0)

        # Wear model (Archard)
        hardness = max(
            300e6,
            material.hardness_ref + material.hardness_temp_slope * (T_surface - 25.0),
        )
        activation = max(0.0, T_surface - 200.0) / material.wear_coeff_activation
        wear_coeff = material.wear_coeff_base * math.exp(min(activation, 60.0))
        wear_rate_inst = wear_coeff * preload * v_abs / (hardness * geom.contact_area)
        h_wear += wear_rate_inst * dt
        wear_integral += wear_rate_inst * dt
        damping_factor = max(
            0.0,
            1.0 - h_wear / torsion.damping_loss_wear_threshold,
        )
        if damping_factor <= 0.5 and math.isinf(time_to_half_damping):
            time_to_half_damping = point.time

        # Duty tracking
        if T_surface > 260.0:
            time_above_260 += dt
        if T_surface > 315.0:
            time_above_315 += dt
        if T_surface > 370.0:
            time_above_370 += dt

        # Logging
        time.append(point.time)
        ring_bulk.append(T_ring)
        steel_bulk.append(T_steel)
        surface_peak.append(T_surface)
        mu_effective.append(mu_eff)
        q_fric.append(q_abs)
        wear_rate.append(wear_rate_inst)
        wear_depth.append(h_wear)
        friction_torque.append(tau_transmitted)
        slip_rate.append(phi_rel_dot)

    duty_above_260 = time_above_260 / duty_total if duty_total else 0.0
    duty_above_315 = time_above_315 / duty_total if duty_total else 0.0
    duty_above_370 = time_above_370 / duty_total if duty_total else 0.0

    peak_surface = max(surface_peak) if surface_peak else 0.0
    peak_ring = max(ring_bulk) if ring_bulk else 0.0
    mean_wear_rate = wear_integral / duty_total if duty_total else 0.0

    if math.isinf(time_to_half_damping):
        last_rate = wear_rate[-1] if wear_rate else 0.0
        remaining = max(0.0, torsion.damping_loss_wear_threshold - h_wear)
        if last_rate > 1e-15:
            time_to_half_damping = drive[-1].time + remaining / last_rate
        else:
            time_to_half_damping = math.inf

    # Verdict logic per the brief
    if duty_above_315 > 0.02 or time_to_half_damping < 500.0:
        verdict = "VALID"
    elif peak_surface < 260.0 and peak_ring < 260.0 and time_to_half_damping > 2000.0:
        verdict = "INVALID"
    else:
        verdict = "NEEDS_REVIEW"

    history = SimulationHistory(
        time=time,
        ring_bulk=ring_bulk,
        steel_bulk=steel_bulk,
        surface_peak=surface_peak,
        mu_effective=mu_effective,
        q_fric=q_fric,
        wear_rate=wear_rate,
        wear_depth=wear_depth,
        friction_torque=friction_torque,
        slip_rate=slip_rate,
    )

    summary = Summary(
        peak_surface_temp=peak_surface,
        peak_ring_temp=peak_ring,
        duty_above_260=duty_above_260,
        duty_above_315=duty_above_315,
        duty_above_370=duty_above_370,
        mean_wear_rate=mean_wear_rate,
        final_wear_depth=h_wear,
        damping_loss_factor=damping_factor,
        time_to_half_damping=time_to_half_damping,
        verdict=verdict,
    )

    return history, summary


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_timeseries_csv(path: Path, history: SimulationHistory) -> None:
    with path.open("w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "time_s",
                "T_ring_bulk_C",
                "T_steel_bulk_C",
                "T_surface_peak_C",
                "mu_effective",
                "Q_fric_W",
                "wear_rate_m_per_s",
                "wear_depth_m",
                "tau_fric_Nm",
                "phi_rel_dot_rad_per_s",
            ]
        )
        for idx in range(len(history.time)):
            writer.writerow(
                [
                    history.time[idx],
                    history.ring_bulk[idx],
                    history.steel_bulk[idx],
                    history.surface_peak[idx],
                    history.mu_effective[idx],
                    history.q_fric[idx],
                    history.wear_rate[idx],
                    history.wear_depth[idx],
                    history.friction_torque[idx],
                    history.slip_rate[idx],
                ]
            )


def plot_time_histories(path: Path, history: SimulationHistory) -> None:
    plt.figure(figsize=(10, 6))
    plt.plot(history.time, history.ring_bulk, label="T_ring_bulk")
    plt.plot(history.time, history.surface_peak, label="T_surface_peak")
    plt.xlabel("Time [s]")
    plt.ylabel("Temperature [°C]")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path / "temperature_history.png", dpi=200)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(history.time, history.mu_effective, label="mu(T)")
    plt.plot(history.time, history.q_fric, label="Q_fric [W]")
    plt.xlabel("Time [s]")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path / "friction_history.png", dpi=200)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(history.time, [w * 1e6 for w in history.wear_depth], label="h_wear [µm]")
    plt.xlabel("Time [s]")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path / "wear_history.png", dpi=200)
    plt.close()


def build_life_map(
    summaries: Dict[Tuple[float, float, float], Summary],
    mu_target: float,
    output_dir: Path,
) -> None:
    # Filter scenarios for target friction
    combos = [
        (h_oil, preload)
        for (mu_lub, h_oil, preload), summary in summaries.items()
        if abs(mu_lub - mu_target) < 1e-6
    ]
    if not combos:
        return

    h_values = sorted({combo[0] for combo in combos})
    preload_values = sorted({combo[1] for combo in combos})

    grid = [[math.nan for _ in h_values] for _ in preload_values]
    for (mu_lub, h_oil, preload), summary in summaries.items():
        if abs(mu_lub - mu_target) > 1e-6:
            continue
        row = preload_values.index(preload)
        col = h_values.index(h_oil)
        wear_rate = max(summary.mean_wear_rate, 1e-15)
        target_wear = 0.5 * TorsionalParams().damping_loss_wear_threshold
        life_hours = target_wear / wear_rate / 3600.0
        grid[row][col] = life_hours

    plt.figure(figsize=(8, 6))
    for r, preload in enumerate(preload_values):
        for c, h_oil in enumerate(h_values):
            value = grid[r][c]
            if math.isnan(value):
                continue
            plt.scatter(h_oil, preload, c=value, cmap="viridis", vmin=0, vmax=max(5.0, value))
    plt.colorbar(label="Predicted life [hours]")
    plt.xlabel("h_oil [kW/m²-K]")
    plt.ylabel("Normal load scale [-]")
    plt.title(f"Predicted life map at μ_lub={mu_target:.2f}")
    plt.tight_layout()
    plt.savefig(output_dir / "life_map.png", dpi=200)
    plt.close()


def write_summary_markdown(
    path: Path,
    summaries: Dict[Tuple[float, float, float], Summary],
    reference_key: Tuple[float, float, float],
    gateway_metadata: Dict[str, str],
) -> None:
    reference = summaries[reference_key]
    verdict_counts: Dict[str, int] = {}
    for summary in summaries.values():
        verdict_counts[summary.verdict] = verdict_counts.get(summary.verdict, 0) + 1

    def fmt_pct(value: float) -> str:
        return f"{value * 100.0:.2f}%"

    with path.open("w") as fp:
        fp.write("# Flexible Compound Gear – Co-Simulation Summary\n\n")
        fp.write("## Data provenance\n\n")
        if gateway_metadata:
            fp.write("- Source: FMU Gateway run\n")
            for key, value in gateway_metadata.items():
                fp.write(f"- {key}: {value}\n")
        else:
            fp.write("- Source: Offline surrogate packaged with the repository\n")
        fp.write("\n")

        fp.write("## Reference scenario KPIs\n\n")
        fp.write(f"- Peak surface temperature: {reference.peak_surface_temp:.1f} °C\n")
        fp.write(f"- Peak ring bulk temperature: {reference.peak_ring_temp:.1f} °C\n")
        fp.write(
            f"- Duty >260/315/370 °C: {fmt_pct(reference.duty_above_260)} / "
            f"{fmt_pct(reference.duty_above_315)} / {fmt_pct(reference.duty_above_370)}\n"
        )
        fp.write(
            f"- Final wear depth: {reference.final_wear_depth * 1e6:.1f} µm\n"
        )
        fp.write(
            f"- Mean wear rate: {reference.mean_wear_rate * 3.6e9:.3f} µm/hr\n"
        )
        time_to_loss = (
            "> simulated window"
            if math.isinf(reference.time_to_half_damping)
            else f"{reference.time_to_half_damping / 3600.0:.2f} h"
        )
        fp.write(f"- Time to 50% damping: {time_to_loss}\n")
        fp.write(f"- Verdict: {reference.verdict}\n\n")

        fp.write("## Sweep verdict distribution\n\n")
        for verdict, count in sorted(verdict_counts.items()):
            fp.write(f"- {verdict}: {count}\n")
        fp.write("\n")

        fp.write("## Recommended levers\n\n")
        if reference.verdict == "VALID":
            fp.write(
                "- Increase oil-side convection (larger jet, higher flow, lower oil inlet temperature).\n"
            )
            fp.write(
                "- Reduce friction coefficient via coatings or surface finishing to limit flash temperature.\n"
            )
            fp.write(
                "- Revisit torsional compliance to reduce slip energy while maintaining torque capacity.\n"
            )
        elif reference.verdict == "INVALID":
            fp.write(
                "- Focus on preload stability, debris management, or alternate damping fade mechanisms.\n"
            )
            fp.write(
                "- Validate contact geometry and alignment as thermal risks appear controlled.\n"
            )
        else:
            fp.write(
                "- Perform instrumented testing to close the gap on flash temperature predictions.\n"
            )
            fp.write(
                "- Refine friction and wear coefficients with material coupons around 300 °C.\n"
            )
        fp.write("\n")

        fp.write("## Parameter sweeps\n\n")
        fp.write("| μ_lub | h_oil [kW/m²-K] | N scale | Peak T_surface [°C] | Duty >315 °C | Wear @ end [µm] | Verdict |\n")
        fp.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        for key in sorted(summaries.keys()):
            summary = summaries[key]
            fp.write(
                "| {mu:.2f} | {h:.1f} | {n:.2f} | {peak:.1f} | {duty:.2%} | {wear:.1f} | {verdict} |\n".format(
                    mu=key[0],
                    h=key[1],
                    n=key[2],
                    peak=summary.peak_surface_temp,
                    duty=summary.duty_above_315,
                    wear=summary.final_wear_depth * 1e6,
                    verdict=summary.verdict,
                )
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--drive-cycle",
        type=Path,
        default=Path(__file__).with_name("engine_cam_drive_cycle.csv"),
        help="CSV drive cycle to use when offline.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).with_name("outputs") / "reference_offline_run",
        help="Directory where artefacts will be written.",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Flag a live FMU Gateway run (metadata only in this surrogate).",
    )
    parser.add_argument(
        "--simulate-fmu",
        action="append",
        default=[],
        help="Placeholder for FMU paths when exercising the real gateway.",
    )
    parser.add_argument(
        "--payment-token",
        help="Payment token used for a live run (recorded in the summary).",
    )
    parser.add_argument(
        "--payment-method",
        help="Payment method used for a live run (recorded in the summary).",
    )
    parser.add_argument(
        "--quote-only",
        action="store_true",
        help="Record that the run executed the quote path only.",
    )
    return parser.parse_args()


MU_SWEEP = [0.06, 0.12, 0.2, 0.35]
H_OIL_SWEEP = [1.0, 2.5, 5.0, 10.0]
PRELOAD_SWEEP = [0.5, 1.0, 1.5]


def main() -> None:
    args = parse_args()
    drive = load_drive_cycle(args.drive_cycle)

    torsion = TorsionalParams()
    geom = Geometry()
    material = MaterialProperties()

    ensure_directory(args.output_dir)

    summaries: Dict[Tuple[float, float, float], Summary] = {}
    histories: Dict[Tuple[float, float, float], SimulationHistory] = {}

    for mu_lub, h_oil, preload in itertools.product(MU_SWEEP, H_OIL_SWEEP, PRELOAD_SWEEP):
        config = SimulationConfig(
            mu_lubricated=mu_lub,
            mu_viscous=0.0008,
            mu_temperature_slope=-0.25,
            mu_temperature_quadratic=0.02,
            mu_boundary=min(0.8, mu_lub + 0.28),
            stribeck_velocity=0.5,
            preload_scale=preload,
            h_oil=h_oil,
        )
        history, summary = simulate_run(drive, config, torsion, geom, material)
        key = (mu_lub, h_oil, preload)
        summaries[key] = summary
        if math.isclose(mu_lub, 0.12, abs_tol=1e-9) and math.isclose(h_oil, 5.0, abs_tol=1e-9) and math.isclose(preload, 1.0, abs_tol=1e-9):
            histories[key] = history

    reference_key = (0.12, 5.0, 1.0)
    reference_history = histories[reference_key]

    write_timeseries_csv(args.output_dir / "reference_timeseries.csv", reference_history)
    plot_time_histories(args.output_dir, reference_history)
    build_life_map(summaries, 0.12, args.output_dir)

    gateway_metadata: Dict[str, str] = {}
    if args.online:
        gateway_metadata["Mode"] = "online"
        if args.simulate_fmu:
            gateway_metadata["FMUs"] = ", ".join(args.simulate_fmu)
        if args.payment_token:
            gateway_metadata["Payment token"] = args.payment_token
        if args.payment_method:
            gateway_metadata["Payment method"] = args.payment_method
        if args.quote_only:
            gateway_metadata["Quote only"] = "true"
    write_summary_markdown(args.output_dir / "summary.md", summaries, reference_key, gateway_metadata)

    with (args.output_dir / "summary.json").open("w") as fp:
        json.dump(
            {
                "reference_key": reference_key,
                "summaries": {
                    str(key): dataclasses.asdict(summary) for key, summary in summaries.items()
                },
                "metadata": gateway_metadata,
            },
            fp,
            indent=2,
        )

    print(f"Wrote artefacts to {args.output_dir}")


if __name__ == "__main__":
    main()
