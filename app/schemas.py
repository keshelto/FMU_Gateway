import math
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class InputSignal(BaseModel):
    name: str
    t: List[float]
    u: List[float]


class DriveCyclePoint(BaseModel):
    time: float
    engine_speed_rpm: float
    cam_torque: float
    oil_temperature: float
    oil_viscosity: float


class FrictionParameters(BaseModel):
    mu_lubricated: float = 0.12
    mu_viscous: float = 0.0008
    mu_temperature_slope: float = -0.25
    mu_temperature_quadratic: float = 0.02
    mu_boundary: float = 0.4
    stribeck_velocity: float = 0.5
    preload_scale: float = 1.0
    h_oil: float = 5.0
    oil_temperature_bias: float = 0.0


class TorsionParameters(BaseModel):
    J_crank: float = 0.18
    J_cam: float = 0.12
    k_theta: float = 4200.0
    c_theta: float = 55.0
    gear_ratio: float = 2.0
    preload_nominal: float = 4200.0
    damping_loss_wear_threshold: float = 160e-6


class GeometryParameters(BaseModel):
    ring_radius: float = 0.045
    ring_width: float = 0.014
    ring_thickness: float = 0.003
    contact_radius: float = 0.012
    contact_area: Optional[float] = None
    thermal_mass_ring: float = 0.45
    thermal_mass_steel: float = 2.0
    contact_resistance: float = 0.02

    @model_validator(mode="after")
    def _default_contact_area(cls, values: "GeometryParameters"):
        if values.contact_area is None:
            values.contact_area = math.pi * values.contact_radius ** 2
        return values


class MaterialParameters(BaseModel):
    rho_ring: float = 8250.0
    cp_ring: float = 420.0
    k_ring: float = 120.0
    rho_steel: float = 7850.0
    cp_steel: float = 460.0
    k_steel: float = 45.0
    hardness_ref: float = 1050e6
    hardness_temp_slope: float = -1.8e6
    wear_coeff_base: float = 1.8e-8
    wear_coeff_activation: float = 210.0


class SimulationParameters(BaseModel):
    friction: FrictionParameters = Field(default_factory=FrictionParameters)
    torsion: TorsionParameters = Field(default_factory=TorsionParameters)
    geometry: GeometryParameters = Field(default_factory=GeometryParameters)
    material: MaterialParameters = Field(default_factory=MaterialParameters)
    gamma: float = 0.65


class SimulateRequest(BaseModel):
    fmu_id: str
    stop_time: float
    step: float
    start_values: Dict[str, float] = Field(default_factory=dict)
    input_signals: List[InputSignal] = Field(default_factory=list)
    kpis: List[str] = Field(default_factory=list)
    payment_token: Optional[str] = None  # Stripe/Google Pay token
    payment_method: Optional[str] = None  # e.g., 'google_pay', 'stripe_card'
    quote_only: Optional[bool] = None  # Allows agents to request a payment quote (HTTP 402)
    parameters: Optional[SimulationParameters] = None
    drive_cycle: Optional[List[DriveCyclePoint]] = None

    @model_validator(mode="after")
    def _validate_drive_cycle(cls, values: "SimulateRequest"):
        if values.drive_cycle:
            times = [point.time for point in values.drive_cycle]
            if any(b <= a for a, b in zip(times, times[1:])):
                raise ValueError("drive_cycle times must be strictly increasing")
        return values


class SimulationResult(BaseModel):
    run_id: str
    status: str
    key_results: Dict[str, float | str] = Field(default_factory=dict)
    provenance: Dict[str, str] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    summary_url: str


class SimulationSummary(SimulationResult):
    history: Dict[str, List[float]] = Field(default_factory=dict)
    parameters: Optional[SimulationParameters] = None
    drive_cycle: Optional[List[DriveCyclePoint]] = None

class FMUMeta(BaseModel):
    id: str
    fmi_version: str
    model_name: str
    guid: str
    sha256: str

class Variable(BaseModel):
    name: str
    causality: str
    variability: str
    declaredType: Optional[str] = None


class SweepParameter(BaseModel):
    path: str
    values: List[float]


class SweepRequest(BaseModel):
    base_request: SimulateRequest
    parameters: List[SweepParameter]
    post_processing: List[str] = Field(default_factory=list)


class SweepResult(BaseModel):
    sweep_id: str
    status: str
    results_url: str


class SweepPointResult(BaseModel):
    run_id: str
    parameter_values: Dict[str, float]
    key_results: Dict[str, float | str]


class SweepSummary(BaseModel):
    sweep_id: str
    status: str
    results_url: str
    points: List[SweepPointResult] = Field(default_factory=list)
    charts: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class PaymentResponse(BaseModel):
    status: str = "payment_required"
    amount: float = 0.01
    currency: str = "usd"
    methods: List[str] = ["google_pay", "stripe_card"]
    description: str = "FMU Simulation Charge"
    next_step: str = "Provide payment_token and payment_method to execute the simulation"
