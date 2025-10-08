from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class InputSignal(BaseModel):
    name: str
    t: List[float]
    u: List[float]

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

class SimulateResponse(BaseModel):
    id: str
    status: str
    t: List[float]
    y: Dict[str, List[float]]
    kpis: Dict[str, float]
    provenance: Dict[str, str]

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

class PaymentResponse(BaseModel):
    status: str = "payment_required"
    amount: float = 0.01
    currency: str = "usd"
    methods: List[str] = ["google_pay", "stripe_card"]
    description: str = "FMU Simulation Charge"
    next_step: str = "Provide payment_token and payment_method to execute the simulation"
