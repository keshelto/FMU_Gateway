import math
from datetime import datetime
from typing import Dict, List, Optional

try:  # pragma: no cover - compatibility shim for Pydantic v1/v2
    from pydantic import BaseModel, Field, model_validator
except ImportError:  # pragma: no cover
    from pydantic import BaseModel, Field, root_validator

    def model_validator(*, mode=None):  # type: ignore
        def decorator(func):
            return root_validator(pre=False, allow_reuse=True)(func)

        return decorator


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
    payment_token: Optional[str] = None  # Session token issued after payment
    payment_method: Optional[str] = "stripe"  # "stripe" or "crypto"
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
    """Defines a parameter to sweep using a dot-notation path."""

    path: str = Field(..., example="start_values.heatLoad")
    values: List[float]


class XYPlotRequest(BaseModel):
    chart_type: str = "xy_plot"
    chart_title: str
    x_axis_param: str = Field(..., example="start_values.heatLoad")
    y_axis_kpi: str = Field(..., example="kpis.y_max")


class SweepRequest(BaseModel):
    """A request to run a parameter sweep."""

    base_request: SimulateRequest
    sweep_parameters: List[SweepParameter]
    post_processing: List[XYPlotRequest] = Field(default_factory=list)


class SweepResponse(BaseModel):
    """The immediate response after submitting a sweep job."""

    sweep_id: str
    status: str = "ACCEPTED"
    results_url: str


class SingleRunResult(BaseModel):
    parameters: Dict[str, float]
    kpis: Dict[str, float]


class GeneratedChart(BaseModel):
    chart_title: str
    image_base64: str


class SweepResultData(BaseModel):
    sweep_id: str
    status: str = "COMPLETED"
    results: List[SingleRunResult]
    charts: List[GeneratedChart]


class PaymentResponse(BaseModel):
    status: str = "payment_required"
    amount: float = 1.0
    currency: str = "usd"
    methods: List[str] = Field(default_factory=lambda: ["stripe_checkout"])
    description: str = "FMU Simulation Charge"
    next_step: str = "Complete checkout and call /payments/checkout/{session_id} to retrieve your simulation token"
    checkout_url: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None
    # Crypto-specific fields
    payment_method: Optional[str] = None
    crypto_addresses: Optional[Dict[str, str]] = None
    hosted_url: Optional[str] = None
    code: Optional[str] = None


class PayRequest(BaseModel):
    fmu_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class PaymentTokenStatus(BaseModel):
    session_id: str
    payment_token: str
    expires_at: datetime
