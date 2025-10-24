"""Structured surrogate model for the flexible compound gear analysis."""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Tuple

from . import schemas

DEFAULT_DRIVE_CYCLE_PATH = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "offline"
    / "Engineering_Analysis_Examples"
    / "Flexible_Compound_Gear"
    / "engine_cam_drive_cycle.csv"
)


def _load_drive_cycle_from_csv(path: Path) -> List[schemas.DriveCyclePoint]:
    points: List[schemas.DriveCyclePoint] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            points.append(
                schemas.DriveCyclePoint(
                    time=float(row["time_s"]),
                    engine_speed_rpm=float(row["engine_speed_rpm"]),
                    cam_torque=float(row["cam_torque_Nm"]),
                    oil_temperature=float(row["oil_temperature_C"]),
                    oil_viscosity=float(row["oil_viscosity_cSt"]),
                )
            )
    return points


def load_drive_cycle(drive_cycle: List[schemas.DriveCyclePoint] | None) -> List[schemas.DriveCyclePoint]:
    if drive_cycle:
        return drive_cycle
    if DEFAULT_DRIVE_CYCLE_PATH.exists():
        return _load_drive_cycle_from_csv(DEFAULT_DRIVE_CYCLE_PATH)
    raise FileNotFoundError("Default drive cycle CSV not found; provide drive_cycle explicitly")


def simulate(
    req: schemas.SimulateRequest,
    parameters: schemas.SimulationParameters,
    drive_cycle: List[schemas.DriveCyclePoint],
) -> Tuple[Dict[str, List[float]], Dict[str, float]]:
    torsion = parameters.torsion
    geom = parameters.geometry
    material = parameters.material
    config = parameters.friction
    gamma = parameters.gamma

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

    dt_list = [
        drive_cycle[i + 1].time - drive_cycle[i].time
        for i in range(len(drive_cycle) - 1)
    ]
    if drive_cycle:
        dt_list.append(dt_list[-1] if dt_list else 0.01)
    else:
        dt_list = []

    duty_total = sum(dt_list)
    time_above_260 = 0.0
    time_above_315 = 0.0
    time_above_370 = 0.0
    wear_integral = 0.0

    preload = torsion.preload_nominal * config.preload_scale
    h_area = 2 * math.pi * geom.ring_radius * geom.ring_width

    time_to_half_damping = math.inf

    prev_omega_crank = (
        drive_cycle[0].engine_speed_rpm * 2 * math.pi / 60.0 if drive_cycle else 0.0
    )

    for idx, point in enumerate(drive_cycle):
        dt = dt_list[idx] if idx < len(dt_list) else (req.step or 0.01)
        omega_crank = point.engine_speed_rpm * 2 * math.pi / 60.0
        omega_cam_in = omega_crank / torsion.gear_ratio

        domega_input = (omega_crank - prev_omega_crank) / max(dt, 1e-6)
        base_slip = abs(domega_input) / torsion.gear_ratio * 0.05
        prev_omega_crank = omega_crank

        v_slip = geom.ring_radius * base_slip
        v_abs = abs(v_slip)

        stribeck = config.mu_lubricated + (
            config.mu_boundary - config.mu_lubricated
        ) * math.exp(-max(v_abs, 1e-6) / max(config.stribeck_velocity, 1e-6))
        delta_temp = max(-200.0, min(T_surface - 120.0, 400.0))
        mu_temp = 1.0 + config.mu_temperature_slope * delta_temp / 100.0
        mu_temp += config.mu_temperature_quadratic * delta_temp ** 2 / 10000.0
        mu_eff = max(0.02, min(stribeck * mu_temp + config.mu_viscous * v_abs, 0.9))

        tau_capacity = mu_eff * preload * geom.ring_radius
        tau_required = point.cam_torque
        tau_transmitted = min(tau_required, tau_capacity)
        slip_excess = max(0.0, tau_required - tau_capacity)
        phi_rel_dot = max(1e-3, base_slip + slip_excess * 0.015)
        v_slip = geom.ring_radius * phi_rel_dot
        v_abs = abs(v_slip)

        q_abs = min(abs(tau_transmitted * phi_rel_dot), 5.0e4)

        v_effective = max(v_abs, 0.05)
        flash_ring = gamma * q_abs / (
            math.pi * geom.contact_radius * v_effective * material.k_ring
        )
        flash_ring = min(flash_ring, 250.0)
        flash_steel = (1.0 - gamma) * q_abs / (
            math.pi * geom.contact_radius * v_effective * material.k_steel
        )
        flash_steel = min(flash_steel, 120.0)

        m_ring = geom.thermal_mass_ring
        m_steel = geom.thermal_mass_steel
        conv_ring = config.h_oil * 1000.0 * h_area * (T_ring - point.oil_temperature)
        conduct = (T_ring - T_steel) / max(geom.contact_resistance, 1e-5)

        dT_ring = (gamma * q_abs - conv_ring - conduct) / (m_ring * material.cp_ring)
        dT_steel = ((1.0 - gamma) * q_abs + conduct) / (m_steel * material.cp_steel)

        T_ring += dT_ring * dt
        T_steel += dT_steel * dt
        T_ring = max(point.oil_temperature - 40.0, min(T_ring, 800.0))
        T_steel = max(point.oil_temperature - 40.0, min(T_steel, 800.0))
        T_surface = max(point.oil_temperature, min(T_ring + flash_ring, 900.0))

        hardness = max(
            300e6,
            material.hardness_ref
            + material.hardness_temp_slope * (T_surface - 25.0),
        )
        activation = max(0.0, T_surface - 200.0) / material.wear_coeff_activation
        wear_coeff = material.wear_coeff_base * math.exp(min(activation, 60.0))
        wear_rate_inst = wear_coeff * preload * v_abs / (
            hardness * max(geom.contact_area, 1e-9)
        )
        h_wear += wear_rate_inst * dt
        wear_integral += wear_rate_inst * dt
        damping_factor = max(
            0.0,
            1.0 - h_wear / torsion.damping_loss_wear_threshold,
        )
        if damping_factor <= 0.5 and math.isinf(time_to_half_damping):
            time_to_half_damping = point.time

        if T_surface > 260.0:
            time_above_260 += dt
        if T_surface > 315.0:
            time_above_315 += dt
        if T_surface > 370.0:
            time_above_370 += dt

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
            time_to_half_damping = (drive_cycle[-1].time if drive_cycle else 0.0) + remaining / last_rate
        else:
            time_to_half_damping = math.inf

    if duty_above_315 > 0.02 or time_to_half_damping < 500.0:
        verdict = "VALID"
    elif peak_surface < 260.0 and peak_ring < 260.0 and time_to_half_damping > 2000.0:
        verdict = "INVALID"
    else:
        verdict = "NEEDS_REVIEW"

    history = {
        "time": time,
        "ring_bulk": ring_bulk,
        "steel_bulk": steel_bulk,
        "surface_peak": surface_peak,
        "mu_effective": mu_effective,
        "q_fric": q_fric,
        "wear_rate": wear_rate,
        "wear_depth": wear_depth,
        "friction_torque": friction_torque,
        "slip_rate": slip_rate,
    }

    summary = {
        "peak_surface_temp": peak_surface,
        "peak_ring_temp": peak_ring,
        "duty_above_260": duty_above_260,
        "duty_above_315": duty_above_315,
        "duty_above_370": duty_above_370,
        "mean_wear_rate": mean_wear_rate,
        "final_wear_depth": h_wear,
        "damping_loss_factor": damping_factor,
        "time_to_half_damping": time_to_half_damping,
        "verdict": verdict,
    }

    return history, summary
