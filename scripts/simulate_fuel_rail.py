"""Simulate and visualize pressure fluctuations in a fuel rail.

This script implements a lightweight analytical model of a common-rail fuel
system so that agents can explore pressure fluctuations without requiring a
pre-built FMU.  The rail is treated as a single control volume whose pressure
tracks a commanded set-point from the high-pressure pump while being disturbed
by injector events.  Injector firings are modelled as short square pulses that
remove fuel and momentarily drop the rail pressure.

The model purposefully favours clarity over physical fidelity: a first-order
response pulls the rail pressure back to the pump set-point and the pulses are
parameterised directly in bar.  Despite the simplifications the resulting time
series demonstrates the characteristic saw-tooth behaviour observed in real
common-rail systems.

Running the script produces two artefacts in the ``data/`` directory:

* ``fuel_rail_pressure.csv`` – time history of the rail pressure, pump set-point
  and injector activity.
* ``fuel_rail_pressure.png`` – a plot summarising the simulation.

Use the script as-is for quick experimentation or adapt it to feed more
realistic FMU-based plant models.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np

BAR_TO_PA = 1e5


@dataclass
class FuelRailParameters:
    """Configuration for the analytical fuel rail model."""

    target_pressure_bar: float = 160.0
    pressure_time_constant: float = 0.015  # seconds
    pump_ripple_bar: float = 5.0  # amplitude of pump pressure ripple
    pump_ripple_hz: float = 150.0

    injector_drop_bar: float = 8.0  # instantaneous drop per firing
    injector_pulse_width: float = 0.001  # seconds
    injector_frequency: float = 100.0  # Hz firing frequency per cylinder
    num_cylinders: int = 4

    stop_time: float = 0.05  # seconds
    step: float = 1e-4  # seconds

    @property
    def target_pressure(self) -> float:
        return self.target_pressure_bar * BAR_TO_PA

    @property
    def injector_drop(self) -> float:
        return self.injector_drop_bar * BAR_TO_PA


@dataclass
class FuelRailResult:
    time: np.ndarray
    pressure: np.ndarray
    pump_setpoint: np.ndarray
    injector_activity: np.ndarray
    injector_dp_rate: np.ndarray

    def to_csv(self, path: Path) -> None:
        """Write the simulation results to ``path`` in CSV format."""

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(
                [
                    "time_s",
                    "pressure_bar",
                    "pump_setpoint_bar",
                    "active_injectors",
                    "injector_dp_rate_bar_per_s",
                ]
            )
            writer.writerows(
                zip(
                    self.time,
                    self.pressure / BAR_TO_PA,
                    self.pump_setpoint / BAR_TO_PA,
                    self.injector_activity,
                    self.injector_dp_rate / BAR_TO_PA,
                )
            )


def injector_activity_profile(params: FuelRailParameters, time: np.ndarray) -> np.ndarray:
    """Return the number of injectors firing at each time instant."""

    period = 1.0 / params.injector_frequency
    activity = np.zeros_like(time)

    for cylinder in range(params.num_cylinders):
        phase = (period / params.num_cylinders) * cylinder
        phase_time = (time - phase) % period
        activity += (phase_time < params.injector_pulse_width).astype(float)

    return activity


def simulate(params: FuelRailParameters) -> FuelRailResult:
    """Run the analytical fuel rail simulation."""

    time = np.arange(0.0, params.stop_time + params.step, params.step)
    pump_setpoint = params.target_pressure + params.pump_ripple_bar * BAR_TO_PA * np.sin(
        2.0 * np.pi * params.pump_ripple_hz * time
    )
    injector_activity = injector_activity_profile(params, time)
    injector_dp_rate = -(
        params.injector_drop / params.injector_pulse_width
    ) * injector_activity  # Pa / s removed by injectors

    pressure = np.empty_like(time)
    pressure[0] = params.target_pressure

    for i in range(1, time.size):
        dp_dt = (pump_setpoint[i - 1] - pressure[i - 1]) / params.pressure_time_constant
        dp_dt += injector_dp_rate[i - 1]
        pressure[i] = max(pressure[i - 1] + dp_dt * params.step, 0.0)

    return FuelRailResult(
        time=time,
        pressure=pressure,
        pump_setpoint=pump_setpoint,
        injector_activity=injector_activity,
        injector_dp_rate=injector_dp_rate,
    )


def plot_results(result: FuelRailResult, path: Path) -> None:
    """Create a PNG plot summarising the simulation results."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax_pressure, ax_injection) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    ax_pressure.plot(result.time, result.pressure / BAR_TO_PA, label="Rail Pressure")
    ax_pressure.plot(result.time, result.pump_setpoint / BAR_TO_PA, label="Pump Set-point", linestyle="--")
    ax_pressure.set_ylabel("Pressure [bar]")
    ax_pressure.set_title("Fuel Rail Pressure Fluctuations")
    ax_pressure.grid(True, which="both", alpha=0.3)
    ax_pressure.legend(loc="upper right")

    ax_injection.step(result.time, result.injector_activity, where="post", label="Active Injectors", color="tab:orange")
    ax_injection.set_ylabel("Active Injectors")
    ax_injection.set_xlabel("Time [s]")
    ax_injection.set_ylim(-0.2, result.injector_activity.max() + 0.5)
    ax_injection.grid(True, which="both", alpha=0.3)

    ax_dp = ax_injection.twinx()
    ax_dp.plot(result.time, result.injector_dp_rate / BAR_TO_PA, color="tab:red", label="Injector dP/dt")
    ax_dp.set_ylabel("Injector dP/dt [bar/s]")

    handles, labels = ax_injection.get_legend_handles_labels()
    handles2, labels2 = ax_dp.get_legend_handles_labels()
    ax_injection.legend(handles + handles2, labels + labels2, loc="upper right")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> Tuple[Path, Path]:
    params = FuelRailParameters()
    result = simulate(params)

    data_dir = Path("data")
    csv_path = data_dir / "fuel_rail_pressure.csv"
    plot_path = data_dir / "fuel_rail_pressure.png"

    result.to_csv(csv_path)
    plot_results(result, plot_path)

    rail_pressure_bar = result.pressure / BAR_TO_PA
    print(f"Saved simulation data to {csv_path}")
    print(f"Saved plot to {plot_path}")
    print(
        "Pressure statistics: min={:.2f} bar, max={:.2f} bar, std={:.2f} bar".format(
            rail_pressure_bar.min(), rail_pressure_bar.max(), rail_pressure_bar.std()
        )
    )

    return csv_path, plot_path


if __name__ == "__main__":
    main()
